"""E-coord episode runner: two-agent interleaved coordination episodes.

Implements §2 of preregistration/design-e-coord-draft-3.md (the spec of
record): seeded first mover, strict alternation via multi-turn headless
resume, per-turn slice injection (arm-dependent), atomic per-turn
checkpointing to the `episode_turns` table, pause-not-abort rate-limit
gates, tree-hash-verified resume, the merged-tree third slot (O5), and the
M4 mechanical defect detectors. Raw inputs for C1/C3/C4/C5 (§4), the M7
exposure descriptives, and the M9 per-turn context/compaction logs land in
results/episodes/<episode_id>/episode.json.

Topology (O10): one long-lived process on the drain2 pattern — claim
episode, execute turns via direct subprocess invocations of `claude`,
heartbeat per claim, mark, claim next. Episodes are strictly serial (O9):
there is never more than one in-flight episode, so the three fixed slots
(agent-a, agent-b, merged, each under its own root per §2's
sibling-path-isolation rule) are episode-exclusive by construction.

Arms (§1): coord-none (control: prompt + title-only static disclosure),
coord-ledger (adds the shared ratified ledger as a per-turn slice),
coord-pylgrim (adds the ledger plus a per-turn presence brief derived from
the sibling's transcript-so-far). Per O7/O8 the slice is INJECTED into the
turn message and archived in the results dir; it is never materialized on
disk inside any worktree.

Where draft 3 under-specifies an implementation detail, the choice made
here is documented below. These are freeze inputs (prereg-v6-coord or
later must ratify or amend them):

1. SCENARIO FILE FORMAT (§3 defines the scenario's content, not a file
   format). A scenario is one YAML file under scenarios/ (recursively;
   the pilot set lives in scenarios/pilot/). Two equivalent surface
   shapes are accepted and normalized by load_scenario (schema in
   scenarios/README.md): the runner's stub shape (`base_sha`, plain
   `pressure` string, `work_items: {a, b}`) and the authored pilot shape
   (`pinned_sha`, `pressure: {stratum, rationale}`, `cards: [a, b]`,
   optional `status: pilot`). Each work item is a FULL task card in the
   tasks/*.yaml schema; `kind: coord` validates under the authored-card
   rules (source.authored: true); both cards' base_sha must equal the
   scenario pin. Config lives in scenarios/config.yaml: `arms`, `reps`,
   `model`, `turn_cap` (R, default 6), `schedule_seed` (default 42).
   Converging on ONE shape is a freeze decision.
2. EPISODE QUEUE LOCATION: a separate results/episodes.db (the skills.db
   precedent) holding `episodes` + `episode_turns` + `meta`, so the
   run-granular runs.db stays untouched (O1: its rows cannot represent an
   episode).
3. COMPLETION DETECTION ("an agent that declares completion before the cap
   stops resuming"): the continuation nudge is frozen verbatim, so there
   is no explicit protocol signal. The mechanical detector used: a turn
   counts as a completion declaration iff the agent's worktree tree hash
   is UNCHANGED from its previous turn AND the turn used no tools (zero
   new tool_use events in the transcript-so-far; when no transcript is
   available, cli num_turns <= 1). A no-op reply to "Continue working on
   your task. Stop when your acceptance criteria are met." is the closest
   observable to a declaration. False completion remains an outcome (C5),
   never rescued (OQ-9).
4. OUTCOME_TIMEOUT_S = 240: the single constant governing every
   outcome-command execution (§3 rule 4). Set at 2x the 120 s authoring
   floor so a command that measured <=120 s on the pinned host cannot
   flake into a timeout under load; the floor itself is an authoring rule,
   not a runner kill line.
5. MERGED-TREE OUTCOME RUNS: outcome commands run on the merged tree only
   when the merge is clean. On conflict the merged tree (with conflict
   markers) is still materialized and archived, but C3 is not-evaluable
   and C5 already failed, so executing commands over conflict markers
   would only add noise.
6. PAUSE SEMANTICS: a rate-limit gate returns the episode to `pending`
   with `resume_after` set and pause_count incremented; `attempt` is NOT
   decremented (unlike single-run rate limits, part of the episode's
   budget was genuinely consumed). An in-flight episode (one with
   checkpointed turns) blocks all other claims until it completes — the
   O9 strictly-serial pin is what makes the fixed slots safe across a
   pause.
7. FIRST-TURN PRESENCE BRIEF: "recomposed at every resume turn" leaves
   turn 1 open; here the bundle arm's slice carries the brief on EVERY
   turn, with an explicit "(none yet)" touched-set on turns where the
   sibling has no transcript, so slice structure is constant within arm.
8. TITLE-ONLY DISCLOSURE WORDING (all three arms, first turn, verbatim):
   see TITLE_DISCLOSURE_TEMPLATE. Presence-brief wording: paths only,
   advisory, per docs/04 §10 schema constraints (see presence_brief()).
9. BRANCH LABEL in the presence brief is wi/<sibling card id> (the
   product-realistic name); the durable refs pinning episode objects are
   refs/episodes/<episode_id>/{a,b,merged}.
10. ATOMIC session_id PERSISTENCE (O6): the episode_turns INSERT is a
    single SQLite WAL transaction committed BEFORE any other post-turn
    step, plus a belt-and-braces temp-file-write + os.replace of
    turns/turn-<idx>-<agent>-session.json. A crash after the CLI returns
    leaves an `invoked` row whose session is accountable and resumable;
    resume completes the row's post-turn steps.
11. TOUCHED-PATH SET for the presence brief: every tool_use file path in
    the sibling's transcript-so-far that resolves inside the sibling's
    worktree, relativized, deduplicated, sorted (mirrors the daemon's
    PostToolUse working-set window; read+write tools both count, as §2
    says "tool-call file paths = the touched set").
12. COMPACTION DETECTOR (M9): transcript events with type == "system" and
    subtype == "compact_boundary", or a truthy isCompactSummary field;
    logged per turn as the delta of the cumulative count.
13. SURVIVING-PID ASSERTION (O6): the last turn's CLI pid is persisted
    (temp+rename) per episode; before each turn, if that pid is still
    alive it is tree-killed and a `surviving_pid` note is recorded on the
    episode row. This is an observability note, not one of the four M4
    excludable classes.
14. CLI RETRY BOUND (M4 ii): one retry per turn on non-rate-limit CLI
    failure (nonzero exit, non-JSON output, or missing session_id); the
    second failure records the `cli_invocation_failure` defect and errors
    the episode. RateLimited is never retried — it pauses.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from harness import arms, headless, queue, workspace
from harness import taskcards as taskcards_mod
from harness import transcripts as transcripts_mod
from harness.headless import RateLimited
from harness.metrics import tests_outcome as tests_metric
from harness.taskcards import TaskCard

EPISODE_ARMS = ("coord-none", "coord-ledger", "coord-pylgrim")
AGENTS = ("a", "b")
DEFAULT_TURN_CAP = 6  # R (§2); config scenarios/config.yaml `turn_cap` overrides
DEFAULT_MODEL = "sonnet"  # §5: one mid-tier alias, single tier
DEFAULT_SCHEDULE_SEED = 42  # §5 master seed
TURN_TIMEOUT_S = headless.RUN_TIMEOUT_S  # timeout class: episode-turn
OUTCOME_TIMEOUT_S = 240  # single outcome constant (docstring choice 4)
CLI_RETRIES = 1  # bounded retry per M4(ii)
PRESSURE_STRATA = ("low", "medium", "high")
DEFAULT_PRESERVE = ("node_modules", ".venv", "target")

# Belt-and-braces O8: harness paths excluded from every C1 clause and overlap
# computation (the slice-only delivery already keeps them out of worktrees).
HARNESS_PATH_PREFIXES = (".pylgrim/",)
HARNESS_PATHS_EXACT = (".pylgrim",)

# §2, verbatim and identical across arms.
CONTINUATION_NUDGE = (
    "Continue working on your task. Stop when your acceptance criteria are met."
)

# Docstring choice 8: the OQ-1 title-only static disclosure, first turn, all arms.
TITLE_DISCLOSURE_TEMPLATE = (
    "Note: another agent is concurrently working an adjacent task in this "
    'repository. That task is titled: "{title}".'
)

# The four M4 excludable defect classes (mechanical detectors) plus the
# non-excludable observability notes this runner also records.
DEFECT_UNRESUMABLE_CRASH = "unresumable_crash"
DEFECT_CLI_FAILURE = "cli_invocation_failure"
DEFECT_TREE_HASH_MISMATCH = "tree_hash_mismatch"
DEFECT_UNRESUMABLE_SESSION = "unresumable_session"
DEFECT_SLICE_HASH_MISMATCH = "slice_hash_mismatch"
NOTE_SURVIVING_PID = "surviving_pid"


class EpisodeDefect(RuntimeError):
    """A mechanical defect detector fired; the episode is errored, not resumed."""

    def __init__(self, defect_class: str, detail: str) -> None:
        super().__init__(f"{defect_class}: {detail}")
        self.defect_class = defect_class
        self.detail = detail


# ---------------------------------------------------------------------------
# Scenario loading (format: docstring choice 1 + scenarios/README.md)
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    scenario_id: str
    repo: str
    base_sha: str
    pressure: str
    cards: dict[str, TaskCard]  # keys "a" and "b"
    status: str = "confirmatory"  # "pilot" scenarios run identically; §6 excludes them at analysis
    raw: dict[str, Any] = field(default_factory=dict)


def _validate_scenario_card(card_data: Any) -> list[str]:
    """taskcards.validate, with the E-coord `kind: coord` accepted.

    Coord cards are authored (source.authored: true), so they validate
    under the authored-card rules; the original kind is preserved on the
    loaded TaskCard."""
    if isinstance(card_data, dict) and card_data.get("kind") == "coord":
        card_data = {**card_data, "kind": "bait"}
    return taskcards_mod.validate(card_data)


def load_scenario(path: Path | str) -> tuple[Scenario | None, list[str]]:
    """Load and validate one scenario file. Returns (scenario, errors).

    Two equivalent surface shapes are accepted and normalized (both are
    freeze inputs; see scenarios/README.md):
      - `work_items: {a: <card>, b: <card>}` with `base_sha` and a plain
        `pressure` stratum string (the runner's original stub shape);
      - the authored pilot shape: `cards: [<card>, <card>]` (list order is
        a, b), `pinned_sha`, and `pressure: {stratum: ..., rationale: ...}`.
    """
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return None, [f"{path.name}: cannot parse: {exc}"]
    errors: list[str] = []
    if not isinstance(data, dict):
        return None, [f"{path.name}: scenario must be a YAML mapping"]
    scenario_id = data.get("scenario_id")
    if not isinstance(scenario_id, str) or not scenario_id:
        errors.append(f"{path.name}: missing required field: scenario_id")
    repo = data.get("repo")
    if not isinstance(repo, str) or not repo:
        errors.append(f"{path.name}: missing required field: repo")
    base_sha = data.get("base_sha") or data.get("pinned_sha")
    if not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha or ""):
        errors.append(
            f"{path.name}: base_sha/pinned_sha must be a 40-character lowercase hex string"
        )
    raw_pressure = data.get("pressure")
    pressure = (
        raw_pressure.get("stratum") if isinstance(raw_pressure, dict) else raw_pressure
    )
    if pressure not in PRESSURE_STRATA:
        errors.append(
            f"{path.name}: pressure (or pressure.stratum) must be one of "
            f"{list(PRESSURE_STRATA)}"
        )
    status = data.get("status") or "confirmatory"

    work_items = data.get("work_items")
    cards_list = data.get("cards")
    card_inputs: dict[str, Any] | None = None
    if isinstance(work_items, dict) and set(work_items) == set(AGENTS):
        card_inputs = {agent: work_items[agent] for agent in AGENTS}
    elif isinstance(cards_list, list) and len(cards_list) == 2:
        card_inputs = {"a": cards_list[0], "b": cards_list[1]}
    cards: dict[str, TaskCard] = {}
    if card_inputs is None:
        errors.append(
            f"{path.name}: work_items must be a mapping with exactly keys 'a' "
            "and 'b', or cards must be a list of exactly 2 task cards"
        )
    else:
        for agent in AGENTS:
            card_data = card_inputs[agent]
            card_errors = _validate_scenario_card(card_data)
            errors.extend(f"{path.name}: work_items.{agent}: {e}" for e in card_errors)
            if isinstance(card_data, dict):
                card = taskcards_mod.from_dict(card_data)
                if isinstance(base_sha, str) and card.base_sha and card.base_sha != base_sha:
                    errors.append(
                        f"{path.name}: work_items.{agent}.base_sha differs from scenario base_sha"
                    )
                cards[agent] = card
    if errors or len(cards) != 2:
        return None, errors
    return Scenario(scenario_id, repo, base_sha, pressure, cards, str(status), data), errors


def load_all_scenarios(scenarios_dir: Path | str) -> tuple[list[Scenario], list[str]]:
    """Load every scenario under scenarios/ recursively (subdirectories like
    scenarios/pilot/ included; config.yaml skipped). Duplicate ids error."""
    scenarios_dir = Path(scenarios_dir)
    scenarios: list[Scenario] = []
    errors: list[str] = []
    seen: set[str] = set()
    for path in sorted(scenarios_dir.rglob("*.yaml")):
        if path.name == "config.yaml":
            continue
        scenario, errs = load_scenario(path)
        errors.extend(errs)
        if scenario is None:
            continue
        if scenario.scenario_id in seen:
            errors.append(f"{path.name}: duplicate scenario_id {scenario.scenario_id!r}")
            continue
        seen.add(scenario.scenario_id)
        scenarios.append(scenario)
    return scenarios, errors


def load_config(scenarios_dir: Path | str) -> dict[str, Any]:
    """scenarios/config.yaml with spec defaults for anything absent."""
    config_path = Path(scenarios_dir) / "config.yaml"
    data: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data = loaded
    return {
        "arms": list(data.get("arms") or EPISODE_ARMS),
        "reps": int(data.get("reps") or 3),
        "model": str(data.get("model") or DEFAULT_MODEL),
        "turn_cap": int(data.get("turn_cap") or DEFAULT_TURN_CAP),
        "schedule_seed": int(data.get("schedule_seed") or DEFAULT_SCHEDULE_SEED),
    }


# ---------------------------------------------------------------------------
# First mover and schedule (M3: sha256(scenario_id, rep) ONLY)
# ---------------------------------------------------------------------------


def first_mover(scenario_id: str, rep: int) -> str:
    """Deterministic first mover from sha256(scenario_id, rep) alone.

    The derivation string is f"{scenario_id}:{rep}" — it deliberately
    excludes run/episode id and arm (M3), so all three arms of a paired
    (scenario, rep) share the same first mover."""
    digest = hashlib.sha256(f"{scenario_id}:{rep}".encode("utf-8")).digest()
    return AGENTS[digest[0] % 2]


def episode_id_for(scenario_id: str, arm: str, rep: int) -> str:
    return f"{scenario_id}--{arm}--r{rep}"


def generate_schedule(
    scenarios: list[Scenario],
    arms_list: list[str],
    reps: int,
    seed: int,
    model: str,
    turn_cap: int,
) -> list[dict[str, Any]]:
    """Rep-blocked shuffled episode schedule (§5 randomization bullet)."""
    for arm in arms_list:
        if arm not in EPISODE_ARMS:
            raise ValueError(f"unknown episode arm: {arm!r}")
    rng = random.Random(seed)
    cells = [(s.scenario_id, s.repo) for s in scenarios]
    rows: list[dict[str, Any]] = []
    order_key = 0
    for rep in range(1, reps + 1):
        block = [(sid, repo, arm) for sid, repo in cells for arm in arms_list]
        rng.shuffle(block)
        for scenario_id, repo, arm in block:
            eid = episode_id_for(scenario_id, arm, rep)
            digest = hashlib.sha256(f"{seed}:{eid}".encode("utf-8")).hexdigest()
            rows.append(
                {
                    "episode_id": eid,
                    "scenario_id": scenario_id,
                    "repo": repo,
                    "arm": arm,
                    "model": model,
                    "rep": rep,
                    "seed": int(digest[:8], 16),
                    "order_key": order_key,
                    "first_mover": first_mover(scenario_id, rep),
                    "turn_cap": turn_cap,
                }
            )
            order_key += 1
    return rows


# ---------------------------------------------------------------------------
# Episode queue (results/episodes.db; queue.py idioms)
# ---------------------------------------------------------------------------

EPISODE_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id   TEXT PRIMARY KEY,
    scenario_id  TEXT NOT NULL,
    repo         TEXT NOT NULL,
    arm          TEXT NOT NULL,
    model        TEXT NOT NULL,
    rep          INTEGER NOT NULL,
    seed         INTEGER NOT NULL,
    order_key    INTEGER NOT NULL,
    first_mover  TEXT NOT NULL CHECK (first_mover IN ('a','b')),
    turn_cap     INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','running','done','error','skipped')),
    attempt      INTEGER NOT NULL DEFAULT 0,
    pause_count  INTEGER NOT NULL DEFAULT 0,
    baseline_tree_a TEXT,
    baseline_tree_b TEXT,
    defects      TEXT,
    results_path TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    error        TEXT,
    resume_after TEXT,
    heartbeat_at TEXT
);

CREATE TABLE IF NOT EXISTS episode_turns (
    episode_id   TEXT NOT NULL,
    turn_idx     INTEGER NOT NULL,
    agent        TEXT NOT NULL CHECK (agent IN ('a','b')),
    round_idx    INTEGER NOT NULL,
    session_id   TEXT,
    slice_path   TEXT,
    slice_sha256 TEXT,
    tree_hash    TEXT,
    status       TEXT NOT NULL DEFAULT 'invoked'
                 CHECK (status IN ('invoked','done')),
    agent_completed   INTEGER NOT NULL DEFAULT 0,
    context_tokens    INTEGER,
    compaction_events INTEGER,
    tool_use_total    INTEGER,
    wall_s       REAL,
    created_at   TEXT,
    finished_at  TEXT,
    PRIMARY KEY (episode_id, turn_idx)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_episode_db(conn: sqlite3.Connection, meta: dict[str, str] | None = None) -> None:
    """Create the episode tables; idempotent (queue.py's migration style)."""
    with conn:
        conn.executescript(EPISODE_SCHEMA)
        # Additive migrations for pre-existing episodes.db files (the
        # heartbeat_at idiom): old rows keep NULL for the new column.
        queue._ensure_column(conn, "episode_turns", "wall_s", "REAL")
        for key, value in (meta or {}).items():
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, str(value))
            )


def episode_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]


def insert_schedule(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
    with conn:
        conn.executemany(
            """
            INSERT INTO episodes (episode_id, scenario_id, repo, arm, model, rep,
                                  seed, order_key, first_mover, turn_cap)
            VALUES (:episode_id, :scenario_id, :repo, :arm, :model, :rep,
                    :seed, :order_key, :first_mover, :turn_cap)
            """,
            rows,
        )


def _inflight_episode(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """The pending episode with checkpointed turns, if any (at most one can
    exist under the O9 strictly-serial pin, but ORDER BY keeps it stable)."""
    return conn.execute(
        """
        SELECT e.* FROM episodes e
        WHERE e.status = 'pending'
          AND EXISTS (SELECT 1 FROM episode_turns t WHERE t.episode_id = e.episode_id)
        ORDER BY e.order_key LIMIT 1
        """
    ).fetchone()


def claim_next_episode(
    conn: sqlite3.Connection, now: str | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    """Atomically claim the next episode. Returns (row, gated_until).

    An in-flight episode (checkpointed turns, status pending) ALWAYS takes
    priority and, while gated by resume_after, BLOCKS every other claim —
    the fixed slots hold its state (docstring choice 6). Returns
    (None, resume_after) when everything eligible is gated, (None, None)
    when the queue is exhausted."""
    now = now or queue.now_iso()
    with conn:
        inflight = _inflight_episode(conn)
        if inflight is not None:
            if inflight["resume_after"] and inflight["resume_after"] > now:
                return None, inflight["resume_after"]
            eid = inflight["episode_id"]
        else:
            row = conn.execute(
                """
                SELECT episode_id FROM episodes
                WHERE status = 'pending'
                  AND (resume_after IS NULL OR resume_after <= ?)
                ORDER BY order_key LIMIT 1
                """,
                (now,),
            ).fetchone()
            if row is None:
                gated = conn.execute(
                    "SELECT MIN(resume_after) AS ra FROM episodes "
                    "WHERE status = 'pending' AND resume_after IS NOT NULL"
                ).fetchone()
                return None, (gated["ra"] if gated else None)
            eid = row["episode_id"]
        cur = conn.execute(
            """
            UPDATE episodes
            SET status = 'running', attempt = attempt + 1,
                started_at = COALESCE(started_at, ?), heartbeat_at = ?,
                resume_after = NULL, error = NULL
            WHERE episode_id = ? AND status = 'pending'
            """,
            (now, now, eid),
        )
        if cur.rowcount != 1:
            return None, None
    claimed = conn.execute("SELECT * FROM episodes WHERE episode_id = ?", (eid,)).fetchone()
    return dict(claimed), None


def mark_episode_done(conn: sqlite3.Connection, episode_id: str, results_path: str) -> None:
    with conn:
        conn.execute(
            "UPDATE episodes SET status = 'done', finished_at = ?, results_path = ? "
            "WHERE episode_id = ?",
            (queue.now_iso(), results_path, episode_id),
        )


def mark_episode_error(conn: sqlite3.Connection, episode_id: str, error: str) -> None:
    with conn:
        conn.execute(
            "UPDATE episodes SET status = 'error', finished_at = ?, error = ? "
            "WHERE episode_id = ?",
            (queue.now_iso(), error[:4000], episode_id),
        )


def mark_episode_skipped(conn: sqlite3.Connection, episode_id: str, reason: str) -> None:
    with conn:
        conn.execute(
            "UPDATE episodes SET status = 'skipped', finished_at = ?, error = ? "
            "WHERE episode_id = ?",
            (queue.now_iso(), reason, episode_id),
        )


def mark_episode_gated(conn: sqlite3.Connection, episode_id: str, resume_after: str) -> None:
    """O2 pause-not-abort: back to pending with resume_after; pause counted;
    attempt kept (docstring choice 6). Turn checkpoints are already durable."""
    with conn:
        conn.execute(
            """
            UPDATE episodes
            SET status = 'pending', resume_after = ?, pause_count = pause_count + 1
            WHERE episode_id = ?
            """,
            (resume_after, episode_id),
        )


def heartbeat_episode(conn: sqlite3.Connection, episode_id: str, now: str | None = None) -> None:
    with conn:
        conn.execute(
            "UPDATE episodes SET heartbeat_at = ? WHERE episode_id = ? AND status = 'running'",
            (now or queue.now_iso(), episode_id),
        )


def reclaim_stale_episodes(
    conn: sqlite3.Connection,
    stale_after_s: int = queue.HEARTBEAT_STALE_S,
    now: str | None = None,
) -> int:
    """Heartbeat-stale 'running' episodes back to 'pending' (drain2 pattern).

    A dead process's episode keeps its turn checkpoints, so the reclaim
    makes it the in-flight episode and the next claim resumes it after the
    tree-hash gate."""
    from datetime import datetime, timedelta, timezone

    now_dt = datetime.fromisoformat(now) if now is not None else datetime.now(timezone.utc)
    cutoff = (now_dt - timedelta(seconds=stale_after_s)).isoformat(timespec="seconds")
    with conn:
        cur = conn.execute(
            """
            UPDATE episodes SET status = 'pending', heartbeat_at = NULL
            WHERE status = 'running'
              AND COALESCE(heartbeat_at, started_at) < ?
            """,
            (cutoff,),
        )
        return cur.rowcount


def record_defect(conn: sqlite3.Connection, episode_id: str, defect: dict[str, Any]) -> None:
    """Append one M4 detector record (or observability note) to the row."""
    with conn:
        row = conn.execute(
            "SELECT defects FROM episodes WHERE episode_id = ?", (episode_id,)
        ).fetchone()
        defects = json.loads(row["defects"]) if row and row["defects"] else []
        defects.append({**defect, "at": queue.now_iso()})
        conn.execute(
            "UPDATE episodes SET defects = ? WHERE episode_id = ?",
            (json.dumps(defects), episode_id),
        )


def episode_status_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    by_status = {
        row["status"]: row["n"]
        for row in conn.execute("SELECT status, COUNT(*) AS n FROM episodes GROUP BY status")
    }
    by_arm = {
        row["arm"]: row["n"]
        for row in conn.execute(
            "SELECT arm, COUNT(*) AS n FROM episodes WHERE status = 'done' GROUP BY arm"
        )
    }
    pauses = {
        row["arm"]: row["p"]
        for row in conn.execute(
            "SELECT arm, SUM(pause_count) AS p FROM episodes GROUP BY arm"
        )
    }
    total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    meta = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")}
    return {
        "total": total,
        "by_status": by_status,
        "done_by_arm": by_arm,
        "pauses_by_arm": pauses,
        "meta": meta,
    }


class EpisodeHeartbeatPump:
    """drain2.HeartbeatPump for the episodes table (own connection per thread)."""

    def __init__(self, db_path: Path | str, episode_id: str, interval_s: float) -> None:
        self._db_path = db_path
        self._episode_id = episode_id
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, name=f"episode-heartbeat-{episode_id}", daemon=True
        )

    def _loop(self) -> None:
        conn = queue.connect(self._db_path)
        try:
            while not self._stop.wait(self._interval_s):
                heartbeat_episode(conn, self._episode_id)
        finally:
            conn.close()

    def __enter__(self) -> "EpisodeHeartbeatPump":
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=10)


# ---------------------------------------------------------------------------
# Slice composition (§1 arm table, §2 injection point; O7/O8 slice-only)
# ---------------------------------------------------------------------------


def render_shared_ledger(card_a: TaskCard, card_b: TaskCard) -> str:
    """BOTH ratified work items (and both cards' constraints) as one
    path-labelled .pylgrim blob, rendered OUTSIDE any worktree.

    Reuses arms.build_pylgrim_ledger (the mechanical spec-v0 ledger) for
    each card into one scratch root; file names are ULID-seeded by card id,
    so the two cards' artifacts coexist."""
    with tempfile.TemporaryDirectory(prefix="pylgrim-shared-ledger-") as tmp:
        root = Path(tmp)
        arms.build_pylgrim_ledger(card_a, root)
        arms.build_pylgrim_ledger(card_b, root)
        parts: list[str] = []
        for path in sorted((root / ".pylgrim").rglob("*.md")):
            rel = path.relative_to(root).as_posix()
            parts.append(f"=== {rel} ===\n{path.read_text(encoding='utf-8')}")
        return "\n".join(parts)


def presence_brief(sibling: TaskCard, touched_paths: list[str]) -> str:
    """The live presence brief: sibling branch, work-item id, touched paths.

    Schema constraints of docs/04 §10: paths only, never content, advisory
    only. Branch label per docstring choice 9."""
    lines = [
        "## Presence brief (live sibling session; advisory only)",
        "",
        f"- sibling work item: {sibling.id}",
        f"- sibling branch: wi/{sibling.id}",
        "- sibling touched paths so far:",
    ]
    if touched_paths:
        lines += [f"  - {p}" for p in touched_paths]
    else:
        lines.append("  - (none yet)")
    lines += [
        "",
        "Paths only, never content. This brief is advisory; it does not "
        "change your task or acceptance criteria.",
    ]
    return "\n".join(lines)


def compose_slice(
    arm: str,
    scenario: Scenario,
    agent: str,
    sibling_touched: list[str],
) -> str | None:
    """The per-turn slice for this arm, or None (control gets no slice)."""
    if arm == "coord-none":
        return None
    sibling = scenario.cards[_sibling(agent)]
    own = scenario.cards[agent]
    parts = [
        "## Shared .pylgrim ledger (both ratified work items)",
        "",
        render_shared_ledger(scenario.cards["a"], scenario.cards["b"]),
        "",
        f"Your work item is {own.id}. The other work item is owned by a "
        "concurrent agent.",
    ]
    if arm == "coord-pylgrim":
        parts += ["", presence_brief(sibling, sibling_touched)]
    elif arm != "coord-ledger":
        raise ValueError(f"unknown episode arm: {arm!r}")
    return "\n".join(parts)


def title_disclosure(sibling: TaskCard) -> str:
    return TITLE_DISCLOSURE_TEMPLATE.format(title=sibling.title)


def first_turn_prompt(own: TaskCard, sibling: TaskCard) -> str:
    """The task prompt (Wave-1 arm-A discipline: the card's specified prompt)
    plus the title-only static disclosure, identical across all three arms."""
    return f"{own.prompt}\n\n{title_disclosure(sibling)}"


def turn_message(
    arm: str,
    scenario: Scenario,
    agent: str,
    is_first_turn: bool,
    sibling_touched: list[str],
) -> tuple[str, str | None]:
    """(full message for this turn, archived slice text or None).

    §2: every turn's message is topped with the recomposed slice; the base
    is the task prompt on the agent's first turn, else the verbatim nudge."""
    base = (
        first_turn_prompt(scenario.cards[agent], scenario.cards[_sibling(agent)])
        if is_first_turn
        else CONTINUATION_NUDGE
    )
    slice_text = compose_slice(arm, scenario, agent, sibling_touched)
    if slice_text is None:
        return base, None
    return f"{slice_text}\n\n{base}", slice_text


def _sibling(agent: str) -> str:
    return "b" if agent == "a" else "a"


def touched_paths_from_transcript(
    transcript_path: Path | str | None, worktree_root: Path | str
) -> list[str]:
    """Tool-call file paths inside the worktree, relativized, deduped, sorted
    (docstring choice 11)."""
    if transcript_path is None or not Path(transcript_path).exists():
        return []
    root = Path(worktree_root).resolve()
    summary = transcripts_mod.summarize_file(transcript_path)
    touched: set[str] = set()
    for entry in summary["tool_file_paths"]:
        raw = entry["path"]
        p = Path(raw)
        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(root)
            except (ValueError, OSError):
                continue  # outside the sibling worktree: not presence material
            touched.add(rel.as_posix())
        else:
            touched.add(p.as_posix())
    return sorted(touched)


def _count_transcript_signals(transcript_path: Path | str | None) -> dict[str, int]:
    """Cumulative tool_use and compaction counts over a transcript snapshot."""
    counts = {"tool_use": 0, "compactions": 0}
    if transcript_path is None or not Path(transcript_path).exists():
        return counts
    for event in transcripts_mod.iter_events(transcript_path):
        if event.get("type") == "system" and event.get("subtype") == "compact_boundary":
            counts["compactions"] += 1
        elif event.get("isCompactSummary"):
            counts["compactions"] += 1
        if event.get("type") != "assistant":
            continue
        content = (event.get("message") or {}).get("content")
        if isinstance(content, list):
            counts["tool_use"] += sum(
                1
                for block in content
                if isinstance(block, dict) and block.get("type") == "tool_use"
            )
    return counts


# ---------------------------------------------------------------------------
# Per-episode filesystem layout
# ---------------------------------------------------------------------------


def episode_results_dir(results_dir: Path | str, episode_id: str) -> Path:
    return Path(results_dir) / "episodes" / episode_id


def agent_slot_dir(results_dir: Path | str, agent: str) -> Path:
    """Fixed slot per role, each under its OWN root (§2: sibling paths are
    never disclosed; separate roots keep an agent's own-root globbing from
    ever listing the sibling). Safe as fixed dirs because episodes are
    strictly serial (O9) and an in-flight episode blocks all other claims."""
    return Path(results_dir) / "episode-slots" / f"agent-{agent}" / "0"


def merged_slot_dir(results_dir: Path | str) -> Path:
    return Path(results_dir) / "episode-slots" / "merged" / "0"


def _atomic_write_text(dest: Path, text: str) -> None:
    """Temp-file write + rename (the O6 atomic-persistence file motion)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=dest.name, dir=str(dest.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp_name, dest)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True
        )
        return re.search(rf"\b{pid}\b", out.stdout or "") is not None
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill_pid_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        import signal

        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# The episode state machine
# ---------------------------------------------------------------------------


def _default_invoke(
    prompt: str,
    model: str,
    workspace_dir: Path,
    timeout_s: int,
    resume_session: str | None = None,
    pid_callback: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Real CLI invocation: own process group per turn (O6, Linux form)."""
    return headless.invoke_claude(
        prompt,
        model,
        workspace_dir,
        timeout_s,
        resume_session=resume_session,
        timeout_class="episode-turn",
        process_group=True,
        pid_callback=pid_callback,
    )


@dataclass
class _AgentState:
    rounds_done: int = 0
    completed: bool = False
    session_id: str | None = None
    last_tree_hash: str | None = None
    last_transcript: Path | None = None
    tool_use_total: int = 0
    compactions_total: int = 0


def _turn_paths(ep_dir: Path, turn_idx: int, agent: str) -> dict[str, Path]:
    turns = ep_dir / "turns"
    stem = f"turn-{turn_idx:02d}-{agent}"
    return {
        "session": turns / f"{stem}-session.json",
        "result": turns / f"{stem}-result.json",
        "transcript": turns / f"{stem}-transcript.jsonl",
        "slice": ep_dir / "slices" / f"{stem}.md",
    }


def _load_turn_rows(conn: sqlite3.Connection, episode_id: str) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM episode_turns WHERE episode_id = ? ORDER BY turn_idx",
            (episode_id,),
        )
    ]


def _verify_resume_state(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    turn_rows: list[dict[str, Any]],
    ep_dir: Path,
    slots: dict[str, Path],
    preserve: tuple[str, ...],
) -> None:
    """The O1 resume gate: archived slice hashes and both worktree tree
    hashes must match the checkpoints; any mismatch is an M4 defect."""
    episode_id = row["episode_id"]
    for turn in turn_rows:
        if not turn["slice_path"]:
            continue
        slice_file = Path(turn["slice_path"])
        if not slice_file.exists():
            raise EpisodeDefect(
                DEFECT_SLICE_HASH_MISMATCH,
                f"archived slice missing for turn {turn['turn_idx']}: {slice_file}",
            )
        actual = _sha256_text(slice_file.read_text(encoding="utf-8"))
        if actual != turn["slice_sha256"]:
            raise EpisodeDefect(
                DEFECT_SLICE_HASH_MISMATCH,
                f"turn {turn['turn_idx']} slice hash {actual[:12]} != "
                f"checkpointed {str(turn['slice_sha256'])[:12]}",
            )
    baselines = {"a": row.get("baseline_tree_a"), "b": row.get("baseline_tree_b")}
    for agent in AGENTS:
        rows_for_agent = [t for t in turn_rows if t["agent"] == agent]
        if rows_for_agent and rows_for_agent[-1]["status"] == "invoked":
            # The crash hit between session persistence and the turn's 'done'
            # update: the worktree legitimately moved during that turn, and
            # _finish_invoked_turns will checkpoint its current state.
            continue
        agent_turns = [t for t in rows_for_agent if t["status"] == "done"]
        expected = agent_turns[-1]["tree_hash"] if agent_turns else baselines[agent]
        if expected is None:
            continue  # agent never prepared/checkpointed; fresh prepare handles it
        slot = slots[agent]
        if not slot.exists() or not (slot / ".git").exists():
            if agent_turns:
                raise EpisodeDefect(
                    DEFECT_TREE_HASH_MISMATCH,
                    f"agent {agent} worktree missing at resume: {slot}",
                )
            continue
        actual = workspace.worktree_tree_hash(slot, preserve)
        if actual != expected:
            raise EpisodeDefect(
                DEFECT_TREE_HASH_MISMATCH,
                f"agent {agent} worktree {actual[:12]} != checkpointed {expected[:12]}",
            )


def run_episode(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    scenario: Scenario,
    repo_url: str,
    results_dir: Path | str,
    *,
    timeout_s: int = TURN_TIMEOUT_S,
    outcome_timeout_s: int = OUTCOME_TIMEOUT_S,
    preserve: tuple[str, ...] = DEFAULT_PRESERVE,
    invoke: Callable[..., dict[str, Any]] | None = None,
    copy_transcript_fn: Callable[..., Path | None] | None = None,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Execute (or resume) one claimed episode end to end.

    Raises RateLimited after checkpointing + gating the episode (caller
    exits the drain), EpisodeDefect after recording the defect and marking
    the episode error, and lets other exceptions propagate for the caller
    to mark as orchestrator errors."""
    invoke = invoke or _default_invoke
    copy_transcript_fn = copy_transcript_fn or headless.copy_transcript
    results_dir = Path(results_dir).resolve()
    episode_id = row["episode_id"]
    model = row["model"]
    turn_cap = int(row["turn_cap"])
    mover = row["first_mover"]
    order = (mover, _sibling(mover))
    ep_dir = episode_results_dir(results_dir, episode_id)
    ep_dir.mkdir(parents=True, exist_ok=True)
    slots = {agent: agent_slot_dir(results_dir, agent) for agent in AGENTS}

    turn_rows = _load_turn_rows(conn, episode_id)
    state = {agent: _AgentState() for agent in AGENTS}

    try:
        if not turn_rows:
            # Fresh episode: prepare both agent worktrees and pin baselines.
            for agent in AGENTS:
                slot = workspace.prepare_dir(
                    results_dir, slots[agent], scenario.repo, repo_url,
                    scenario.base_sha, preserve,
                )
                baseline = workspace.worktree_tree_hash(slot, preserve)
                state[agent].last_tree_hash = baseline
                with conn:
                    conn.execute(
                        f"UPDATE episodes SET baseline_tree_{agent} = ? WHERE episode_id = ?",
                        (baseline, episode_id),
                    )
        else:
            _verify_resume_state(conn, row, turn_rows, ep_dir, slots, preserve)
            turn_rows = _finish_invoked_turns(
                conn, row, turn_rows, ep_dir, slots, preserve, copy_transcript_fn
            )
            baselines = {"a": row.get("baseline_tree_a"), "b": row.get("baseline_tree_b")}
            for agent in AGENTS:
                agent_turns = [
                    t for t in turn_rows if t["agent"] == agent and t["status"] == "done"
                ]
                st = state[agent]
                st.rounds_done = len(agent_turns)
                st.completed = bool(agent_turns and agent_turns[-1]["agent_completed"])
                st.session_id = agent_turns[-1]["session_id"] if agent_turns else None
                st.last_tree_hash = (
                    agent_turns[-1]["tree_hash"] if agent_turns else baselines[agent]
                )
                st.tool_use_total = int(agent_turns[-1]["tool_use_total"] or 0) if agent_turns else 0
                st.compactions_total = (
                    sum(int(t["compaction_events"] or 0) for t in agent_turns)
                )
                if agent_turns:
                    tp = _turn_paths(ep_dir, agent_turns[-1]["turn_idx"], agent)
                    if tp["transcript"].exists():
                        st.last_transcript = tp["transcript"]
                if st.last_tree_hash is None:
                    # Agent never checkpointed; its worktree must be (re)prepared.
                    slot = workspace.prepare_dir(
                        results_dir, slots[agent], scenario.repo, repo_url,
                        scenario.base_sha, preserve,
                    )
                    st.last_tree_hash = workspace.worktree_tree_hash(slot, preserve)
                    with conn:
                        conn.execute(
                            f"UPDATE episodes SET baseline_tree_{agent} = ? "
                            "WHERE episode_id = ?",
                            (st.last_tree_hash, episode_id),
                        )
    except EpisodeDefect as exc:
        record_defect(
            conn, episode_id, {"class": exc.defect_class, "detail": exc.detail}
        )
        mark_episode_error(conn, episode_id, str(exc))
        raise

    executed = {(t["agent"], t["round_idx"]) for t in turn_rows if t["status"] == "done"}
    next_turn_idx = max((t["turn_idx"] for t in turn_rows), default=-1) + 1

    # --- the turn loop: strict alternation, seeded first mover -------------
    for round_idx in range(turn_cap):
        for agent in order:
            if (agent, round_idx) in executed:
                continue
            st = state[agent]
            if st.completed:
                continue
            sibling_st = state[_sibling(agent)]
            sibling_touched = (
                touched_paths_from_transcript(
                    sibling_st.last_transcript, slots[_sibling(agent)]
                )
                if row["arm"] == "coord-pylgrim"
                else []
            )
            try:
                _execute_turn(
                    conn, row, scenario, ep_dir, slots, preserve, state,
                    agent, round_idx, next_turn_idx, sibling_touched,
                    invoke=invoke, copy_transcript_fn=copy_transcript_fn,
                    timeout_s=timeout_s, echo=echo,
                )
            except RateLimited as exc:
                mark_episode_gated(conn, episode_id, exc.resume_after)
                echo(
                    f"{episode_id}: rate-limit PAUSE at turn {next_turn_idx} "
                    f"(agent {agent}); resume after {exc.resume_after}"
                )
                raise
            except EpisodeDefect as exc:
                record_defect(
                    conn, episode_id, {"class": exc.defect_class, "detail": exc.detail}
                )
                mark_episode_error(conn, episode_id, str(exc))
                raise
            next_turn_idx += 1
            if all(state[a].completed for a in AGENTS):
                break
        if all(state[a].completed for a in AGENTS):
            break

    # --- completion: merge, third slot, outcomes, metrics inputs -----------
    try:
        record = _finalize_episode(
            conn, row, scenario, repo_url, results_dir, ep_dir, slots, preserve,
            state, outcome_timeout_s=outcome_timeout_s, echo=echo,
        )
    except EpisodeDefect as exc:
        record_defect(
            conn, episode_id, {"class": exc.defect_class, "detail": exc.detail}
        )
        mark_episode_error(conn, episode_id, str(exc))
        raise
    mark_episode_done(conn, episode_id, str(ep_dir / "episode.json"))
    return record


def _finish_invoked_turns(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    turn_rows: list[dict[str, Any]],
    ep_dir: Path,
    slots: dict[str, Path],
    preserve: tuple[str, ...],
    copy_transcript_fn: Callable[..., Path | None],
) -> list[dict[str, Any]]:
    """Complete post-turn steps for rows left 'invoked' by a crash (O6): the
    session is accountable (session_id was persisted first), so the turn is
    finished from current worktree state rather than lost. wall_s was
    checkpointed atomically with the 'invoked' row, so resume never re-times
    a completed invocation (the UPDATE below leaves it untouched)."""
    episode_id = row["episode_id"]
    for turn in turn_rows:
        if turn["status"] != "invoked":
            continue
        agent = turn["agent"]
        turn_idx = turn["turn_idx"]
        tp = _turn_paths(ep_dir, turn_idx, agent)
        tree_hash = workspace.worktree_tree_hash(slots[agent], preserve)
        if turn["session_id"] and not tp["transcript"].exists():
            try:
                copy_transcript_fn(slots[agent], turn["session_id"], tp["transcript"])
            except Exception:
                pass  # transcript recovery is best-effort; the session_id is the record
        signals = _count_transcript_signals(
            tp["transcript"] if tp["transcript"].exists() else None
        )
        prev = [
            t for t in turn_rows
            if t["agent"] == agent and t["status"] == "done" and t["turn_idx"] < turn_idx
        ]
        prev_hash = prev[-1]["tree_hash"] if prev else (
            row.get(f"baseline_tree_{agent}")
        )
        prev_tools = int(prev[-1]["tool_use_total"] or 0) if prev else 0
        prev_compactions = sum(int(t["compaction_events"] or 0) for t in prev)
        completed = _detect_completion(
            tree_hash, prev_hash, signals["tool_use"], prev_tools, None,
            transcript_available=tp["transcript"].exists(),
        )
        with conn:
            conn.execute(
                """
                UPDATE episode_turns
                SET status = 'done', tree_hash = ?, agent_completed = ?,
                    tool_use_total = ?, compaction_events = ?, finished_at = ?
                WHERE episode_id = ? AND turn_idx = ?
                """,
                (
                    tree_hash, int(completed), signals["tool_use"],
                    max(0, signals["compactions"] - prev_compactions),
                    queue.now_iso(), episode_id, turn_idx,
                ),
            )
    return _load_turn_rows(conn, episode_id)


def _detect_completion(
    tree_hash: str,
    prev_tree_hash: str | None,
    tool_use_total: int,
    prev_tool_use_total: int,
    num_turns: int | None,
    transcript_available: bool,
) -> bool:
    """Docstring choice 3: no worktree change AND no tool use this turn."""
    if prev_tree_hash is None or tree_hash != prev_tree_hash:
        return False
    if transcript_available:
        return tool_use_total - prev_tool_use_total <= 0
    if num_turns is not None:
        return num_turns <= 1
    return False


def _execute_turn(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    scenario: Scenario,
    ep_dir: Path,
    slots: dict[str, Path],
    preserve: tuple[str, ...],
    state: dict[str, _AgentState],
    agent: str,
    round_idx: int,
    turn_idx: int,
    sibling_touched: list[str],
    *,
    invoke: Callable[..., dict[str, Any]],
    copy_transcript_fn: Callable[..., Path | None],
    timeout_s: int,
    echo: Callable[[str], None],
) -> None:
    episode_id = row["episode_id"]
    st = state[agent]
    tp = _turn_paths(ep_dir, turn_idx, agent)
    slot = slots[agent]

    # Pre-turn assertion (O6): no surviving PID from a prior turn.
    _assert_no_surviving_pid(conn, episode_id, ep_dir)

    # Compose + archive the slice BEFORE invocation, so the archived file is
    # exactly what the agent saw (and the M4 slice-hash detector has ground
    # truth even if we crash mid-invoke).
    message, slice_text = turn_message(
        row["arm"], scenario, agent, round_idx == 0, sibling_touched
    )
    slice_sha = None
    if slice_text is not None:
        _atomic_write_text(tp["slice"], slice_text)
        slice_sha = _sha256_text(slice_text)

    pid_holder: dict[str, int] = {}

    def _pid_cb(pid: int) -> None:
        pid_holder["pid"] = pid
        _atomic_write_text(
            ep_dir / "last-turn-pid.json",
            json.dumps({"pid": pid, "turn_idx": turn_idx, "agent": agent}),
        )

    cli_result: dict[str, Any] | None = None
    last_error: Exception | None = None
    wall_s: float | None = None
    for attempt in range(CLI_RETRIES + 1):
        # wall_s SCOPE: monotonic wall seconds around the claude invocation
        # ONLY — slice composition, checkpointing, transcript copy, and tree
        # hashing are all outside the window. On a bounded retry, wall_s is
        # the successful attempt's duration alone.
        invoke_start = time.perf_counter()
        try:
            result = invoke(
                message, row["model"], slot, timeout_s,
                resume_session=st.session_id, pid_callback=_pid_cb,
            )
        except RateLimited:
            raise  # pause, never retry (O2)
        except Exception as exc:
            last_error = exc
            if st.session_id and _looks_unresumable(exc):
                raise EpisodeDefect(
                    DEFECT_UNRESUMABLE_SESSION,
                    f"resume of session {st.session_id} rejected: {exc}",
                )
            continue
        if result.get("session_id"):
            wall_s = time.perf_counter() - invoke_start
            cli_result = result
            break
        last_error = RuntimeError("CLI returned no session_id")
    if cli_result is None:
        raise EpisodeDefect(
            DEFECT_CLI_FAILURE,
            f"turn {turn_idx} (agent {agent}) failed after {CLI_RETRIES + 1} "
            f"attempts: {last_error}",
        )
    session_id = str(cli_result["session_id"])

    # O6: persist the session id ATOMICALLY before any other post-turn step.
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO episode_turns
                (episode_id, turn_idx, agent, round_idx, session_id,
                 slice_path, slice_sha256, wall_s, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'invoked', ?)
            """,
            (
                episode_id, turn_idx, agent, round_idx, session_id,
                str(tp["slice"]) if slice_text is not None else None,
                slice_sha, wall_s, queue.now_iso(),
            ),
        )
    _atomic_write_text(
        tp["session"],
        json.dumps(
            {"episode_id": episode_id, "agent": agent, "turn_idx": turn_idx,
             "session_id": session_id}
        ),
    )

    # Post-turn steps (each recoverable via _finish_invoked_turns on crash).
    _atomic_write_text(tp["result"], json.dumps(cli_result, indent=2, default=str))
    transcript = None
    try:
        transcript = copy_transcript_fn(slot, session_id, tp["transcript"])
    except Exception:
        transcript = None
    tree_hash = workspace.worktree_tree_hash(slot, preserve)
    signals = _count_transcript_signals(transcript)
    usage = cli_result.get("usage") or {}
    context_tokens = None
    token_fields = (
        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"
    )
    if any(isinstance(usage.get(k), (int, float)) for k in token_fields):
        context_tokens = int(sum(usage.get(k) or 0 for k in token_fields))
    completed = _detect_completion(
        tree_hash, st.last_tree_hash, signals["tool_use"], st.tool_use_total,
        cli_result.get("num_turns"), transcript_available=transcript is not None,
    )
    compaction_delta = max(0, signals["compactions"] - st.compactions_total)
    with conn:
        conn.execute(
            """
            UPDATE episode_turns
            SET status = 'done', tree_hash = ?, agent_completed = ?,
                context_tokens = ?, compaction_events = ?, tool_use_total = ?,
                finished_at = ?
            WHERE episode_id = ? AND turn_idx = ?
            """,
            (
                tree_hash, int(completed), context_tokens, compaction_delta,
                signals["tool_use"], queue.now_iso(), episode_id, turn_idx,
            ),
        )

    st.rounds_done = round_idx + 1
    st.completed = completed
    st.session_id = session_id
    st.last_tree_hash = tree_hash
    st.tool_use_total = signals["tool_use"]
    st.compactions_total += compaction_delta
    if transcript is not None:
        st.last_transcript = Path(transcript)
    echo(
        f"{episode_id}: turn {turn_idx} done (agent {agent}, round "
        f"{round_idx + 1}/{row['turn_cap']}"
        + (", declared complete)" if completed else ")")
    )


def _looks_unresumable(exc: Exception) -> bool:
    """M4 class (iv): the CLI rejected the resume itself (session missing)."""
    text = str(exc).lower()
    return "session" in text and any(
        marker in text for marker in ("no conversation", "not found", "cannot resume", "no session")
    )


def _assert_no_surviving_pid(
    conn: sqlite3.Connection, episode_id: str, ep_dir: Path
) -> None:
    pid_file = ep_dir / "last-turn-pid.json"
    if not pid_file.exists():
        return
    try:
        data = json.loads(pid_file.read_text(encoding="utf-8"))
        pid = int(data["pid"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return
    if _pid_alive(pid):
        _kill_pid_tree(pid)
        record_defect(
            conn, episode_id,
            {"class": NOTE_SURVIVING_PID,
             "detail": f"pid {pid} from turn {data.get('turn_idx')} survived; killed"},
        )


# ---------------------------------------------------------------------------
# Finalization: merge, merged-tree slot, outcomes, metric raw inputs
# ---------------------------------------------------------------------------


def _is_harness_path(path: str) -> bool:
    return path in HARNESS_PATHS_EXACT or any(
        path.startswith(prefix) for prefix in HARNESS_PATH_PREFIXES
    )


def _diff_churn(patch_text: str) -> dict[str, int]:
    added = deleted = 0
    for line in patch_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            deleted += 1
    return {"added": added, "deleted": deleted}


def _finalize_episode(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    scenario: Scenario,
    repo_url: str,
    results_dir: Path,
    ep_dir: Path,
    slots: dict[str, Path],
    preserve: tuple[str, ...],
    state: dict[str, _AgentState],
    *,
    outcome_timeout_s: int,
    echo: Callable[[str], None],
) -> dict[str, Any]:
    episode_id = row["episode_id"]
    clone = workspace.bare_clone_path(results_dir, scenario.repo)
    base = scenario.base_sha

    # Commit each agent's final state (harness-authored; O5 raw material).
    branches: dict[str, dict[str, Any]] = {}
    for agent in AGENTS:
        committed = workspace.commit_worktree(
            slots[agent], base, f"episode {episode_id} agent {agent}", preserve
        )
        workspace.update_ref(
            clone, f"refs/episodes/{episode_id}/{agent}", committed["commit"]
        )
        patch = workspace.diff_text(clone, base, committed["commit"])
        patch_path = ep_dir / f"branch-{agent}.patch"
        _atomic_write_text(patch_path, patch)
        changed = workspace.changed_files(clone, base, committed["commit"])
        branches[agent] = {
            **committed,
            "patch_path": str(patch_path),
            "changed_files": changed,
            "churn": _diff_churn(patch),
        }

    # Merge from the common base (C1's symmetric three-way detection).
    merge = workspace.merge_tree_write_tree(
        clone, base, branches["a"]["commit"], branches["b"]["commit"]
    )
    merged_commit = workspace.commit_tree(
        clone,
        str(merge["tree"]),
        [branches["a"]["commit"], branches["b"]["commit"]],
        f"episode {episode_id} merged tree",
    )
    workspace.update_ref(clone, f"refs/episodes/{episode_id}/merged", merged_commit)

    # Materialize the merged tree in the third slot (O5), tree-hash-verified.
    merged_dir = workspace.prepare_dir(
        results_dir, merged_slot_dir(results_dir), scenario.repo, repo_url,
        merged_commit, preserve,
    )
    materialized = workspace.worktree_tree_hash(merged_dir, preserve)
    if materialized != merge["tree"]:
        raise EpisodeDefect(
            DEFECT_TREE_HASH_MISMATCH,
            f"merged slot tree {materialized[:12]} != merge-tree {str(merge['tree'])[:12]}",
        )

    # Outcome commands: each branch (own card) + merged tree (both cards),
    # one timeout constant (§3 rule 4; docstring choices 4-5).
    outcomes: dict[str, Any] = {"own_branch": {}, "merged": {}}
    for agent in AGENTS:
        card = scenario.cards[agent]
        outcomes["own_branch"][agent] = tests_metric.compute(
            card.test_command, slots[agent], card.deterministic_checks, outcome_timeout_s
        )
    if merge["clean"]:
        for agent in AGENTS:
            card = scenario.cards[agent]
            outcomes["merged"][agent] = tests_metric.compute(
                card.test_command, merged_dir, card.deterministic_checks, outcome_timeout_s
            )
    else:
        outcomes["merged"] = {
            agent: {"skipped": "merge conflicted; C3 not-evaluable, C5 failed"}
            for agent in AGENTS
        }

    # --- C1 raw inputs ------------------------------------------------------
    changed_paths = {
        agent: {p for _s, p in branches[agent]["changed_files"] if not _is_harness_path(p)}
        for agent in AGENTS
    }
    file_overlap = sorted(changed_paths["a"] & changed_paths["b"])
    added_paths = {
        agent: {
            p for s, p in branches[agent]["changed_files"]
            if s == "A" and not _is_harness_path(p)
        }
        for agent in AGENTS
    }
    untracked_collisions = []
    for path in sorted(added_paths["a"] & added_paths["b"]):
        blob_a = workspace.blob_oid(clone, branches["a"]["commit"], path)
        blob_b = workspace.blob_oid(clone, branches["b"]["commit"], path)
        if blob_a is not None and blob_b is not None and blob_a != blob_b:
            untracked_collisions.append({"path": path, "blob_a": blob_a, "blob_b": blob_b})
    conflicted_files = [
        f for f in merge["conflicted_files"] if not _is_harness_path(str(f))
    ]
    c1 = {
        "merge_clean": merge["clean"],
        "conflicted_files": conflicted_files,
        "conflicted_file_count": len(conflicted_files),
        "untracked_path_collisions": untracked_collisions,  # SEPARATE subcomponent (M7)
        "any_collision": (not merge["clean"]) or bool(untracked_collisions),
        "file_overlap": file_overlap,
        "changed_files": {a: sorted(changed_paths[a]) for a in AGENTS},
        "merge_raw_output": merge["raw"],
    }

    # --- C3 raw inputs ------------------------------------------------------
    c3 = {
        "evaluable": merge["clean"],
        "per_work_item": {
            agent: {
                "own_branch_pass": bool(outcomes["own_branch"][agent].get("passed")),
                "merged_pass": (
                    bool(outcomes["merged"][agent].get("passed"))
                    if merge["clean"] else None
                ),
            }
            for agent in AGENTS
        },
    }
    if merge["clean"]:
        c3["contradiction"] = any(
            c3["per_work_item"][a]["own_branch_pass"]
            and c3["per_work_item"][a]["merged_pass"] is False
            for a in AGENTS
        )
    else:
        c3["contradiction"] = None  # not-evaluable

    # --- C4 raw inputs (unconditional spend, CLI modelUsage basis) ----------
    turn_rows = _load_turn_rows(conn, episode_id)
    per_turn_spend: list[dict[str, Any]] = []
    model_usage_total: dict[str, dict[str, float]] = {}
    total_cost = 0.0
    for turn in turn_rows:
        tp = _turn_paths(ep_dir, turn["turn_idx"], turn["agent"])
        cli: dict[str, Any] = {}
        if tp["result"].exists():
            try:
                cli = json.loads(tp["result"].read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                cli = {}
        cost = cli.get("total_cost_usd")
        if isinstance(cost, (int, float)):
            total_cost += float(cost)
        for model_name, fields in (cli.get("modelUsage") or {}).items():
            if not isinstance(fields, dict):
                continue
            bucket = model_usage_total.setdefault(model_name, {})
            for key, value in fields.items():
                if isinstance(value, (int, float)):
                    bucket[key] = bucket.get(key, 0) + value
        per_turn_spend.append(
            {
                "turn_idx": turn["turn_idx"],
                "agent": turn["agent"],
                "total_cost_usd": cost,
                "usage": cli.get("usage"),
                "modelUsage": cli.get("modelUsage"),
            }
        )
    c4 = {
        "total_cost_usd": total_cost,
        "model_usage": model_usage_total,
        "per_turn": per_turn_spend,
    }

    # --- C5 raw inputs ------------------------------------------------------
    own_pass = {a: bool(outcomes["own_branch"][a].get("passed")) for a in AGENTS}
    merged_pass = {
        a: (bool(outcomes["merged"][a].get("passed")) if merge["clean"] else False)
        for a in AGENTS
    }
    c5 = {
        "merge_clean": merge["clean"],
        "own_branch_pass": own_pass,
        "merged_pass": merged_pass,
        "combined_success": (
            merge["clean"] and all(own_pass.values()) and all(merged_pass.values())
        ),
    }

    # --- M7 exposure descriptives + M9 logs ---------------------------------
    m7 = {
        agent: {
            "turns_used": state[agent].rounds_done,
            "cap_hit": state[agent].rounds_done >= int(row["turn_cap"])
                       and not state[agent].completed,
            "declared_complete": state[agent].completed,
            "churn": branches[agent]["churn"],
            "files_touched": len(changed_paths[agent]),
        }
        for agent in AGENTS
    }
    m9 = [
        {
            "turn_idx": t["turn_idx"],
            "agent": t["agent"],
            "context_tokens": t["context_tokens"],
            "compaction_events": t["compaction_events"],
            "wall_s": t["wall_s"],
        }
        for t in turn_rows
    ]

    defects_row = conn.execute(
        "SELECT defects, pause_count FROM episodes WHERE episode_id = ?", (episode_id,)
    ).fetchone()
    record = {
        "episode": {
            k: row[k]
            for k in (
                "episode_id", "scenario_id", "repo", "arm", "model", "rep",
                "seed", "first_mover", "turn_cap",
            )
        },
        "scenario": {
            "scenario_id": scenario.scenario_id,
            "repo": scenario.repo,
            "base_sha": scenario.base_sha,
            "pressure": scenario.pressure,
            "work_items": {a: scenario.cards[a].id for a in AGENTS},
        },
        "turns": [
            {k: t[k] for k in (
                "turn_idx", "agent", "round_idx", "session_id", "slice_path",
                "slice_sha256", "tree_hash", "agent_completed",
                "context_tokens", "compaction_events", "wall_s",
            )}
            for t in turn_rows
        ],
        "branches": branches,
        "merged": {"commit": merged_commit, "tree": merge["tree"]},
        "outcomes": outcomes,
        "metrics_inputs": {"c1": c1, "c3": c3, "c4": c4, "c5": c5, "m7": m7, "m9": m9},
        "pause_count": defects_row["pause_count"] if defects_row else 0,
        "defects": json.loads(defects_row["defects"]) if defects_row and defects_row["defects"] else [],
    }
    _atomic_write_text(ep_dir / "episode.json", json.dumps(record, indent=2, default=str))
    echo(
        f"{episode_id}: finalized (merge {'clean' if merge['clean'] else 'CONFLICT'}, "
        f"combined_success={c5['combined_success']})"
    )
    return record


# ---------------------------------------------------------------------------
# The continuous drain (drain2 pattern; strictly serial per O9)
# ---------------------------------------------------------------------------


def run_episode_drain(
    db_path: Path | str,
    results_dir: Path | str,
    scenarios_by_id: dict[str, Scenario],
    repos_cfg: dict[str, dict],
    *,
    timeout_s: int = TURN_TIMEOUT_S,
    outcome_timeout_s: int = OUTCOME_TIMEOUT_S,
    heartbeat_s: float = 60,
    stale_after_s: int = queue.HEARTBEAT_STALE_S,
    invoke: Callable[..., dict[str, Any]] | None = None,
    copy_transcript_fn: Callable[..., Path | None] | None = None,
    echo: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Claim episodes one at a time until exhausted or gated (O9: no
    parallelism, ever — the slots are episode-exclusive)."""
    conn = queue.connect(db_path)
    init_episode_db(conn)
    reclaimed = reclaim_stale_episodes(conn, stale_after_s)
    if reclaimed:
        echo(f"reclaimed {reclaimed} heartbeat-stale episode(s) to pending")

    stats: dict[str, Any] = {
        "reclaimed": reclaimed, "done": 0, "error": 0, "skipped": 0,
        "resume_after": None,
    }
    while True:
        row, gated_until = claim_next_episode(conn)
        if row is None:
            if gated_until:
                stats["resume_after"] = gated_until
                echo(f"gated: next episode eligible after {gated_until}")
            else:
                echo("no eligible pending episodes")
            break
        episode_id = row["episode_id"]
        scenario = scenarios_by_id.get(row["scenario_id"])
        repo_cfg = repos_cfg.get(row["repo"])
        if scenario is None or repo_cfg is None:
            mark_episode_skipped(conn, episode_id, "scenario or repo config missing")
            echo(f"{episode_id}: skipped (missing scenario or repo config)")
            stats["skipped"] += 1
            continue
        preserve = tuple(repo_cfg.get("preserve") or DEFAULT_PRESERVE)
        echo(f"{episode_id}: running (first mover {row['first_mover']})")
        try:
            with EpisodeHeartbeatPump(db_path, episode_id, heartbeat_s):
                run_episode(
                    conn, row, scenario, repo_cfg["url"], results_dir,
                    timeout_s=timeout_s, outcome_timeout_s=outcome_timeout_s,
                    preserve=preserve, invoke=invoke,
                    copy_transcript_fn=copy_transcript_fn, echo=echo,
                )
        except RateLimited as exc:
            stats["resume_after"] = exc.resume_after
            break  # episode already gated by run_episode; exit the drain cleanly
        except EpisodeDefect as exc:
            echo(f"{episode_id}: DEFECT {exc}")
            stats["error"] += 1
            continue
        except Exception as exc:  # orchestrator crash: record, keep draining
            record_defect(
                conn, episode_id,
                {"class": DEFECT_UNRESUMABLE_CRASH, "detail": str(exc)[:2000]},
            )
            mark_episode_error(conn, episode_id, str(exc))
            echo(f"{episode_id}: error: {exc}")
            stats["error"] += 1
            continue
        echo(f"{episode_id}: done")
        stats["done"] += 1
    stats["summary"] = episode_status_summary(conn)
    conn.close()
    return stats
