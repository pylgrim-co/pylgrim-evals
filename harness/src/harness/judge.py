"""LLM-judge scoring of criteria satisfaction (M5 secondary, arm-blind).

The judge grades whether a run's final diff meets each acceptance criterion:
met / not_met / cannot_judge per criterion. Deterministic metrics carry the
headline results; judge verdicts are secondary and subject to the calibration
gate (Cohen's kappa vs the founder's blind grades; < 0.6 demotes the metric
to exploratory).

Arm blindness by construction. The judge sees ONLY the task prompt, the
numbered acceptance criteria, and the run's diff with every CLAUDE.md section
scrubbed out (the claudemd arm writes CLAUDE.md into the workspace; a repo
with a tracked CLAUDE.md would otherwise leak the arm). It never sees the
transcript, result.json (run.arm), the arm label, or the run id (run ids
embed the arm). If "claude.md" survives scrubbing anywhere in the assembled
prompt, the judge run is skipped as arm-leak-unscrubbable: honest refusal
beats leaking. The judge process runs in an empty scratch directory, never
the workspace, so it can only read what the prompt carries.

Judge work is queued in a judge_runs table in the same runs.db (one row per
run x judge-model x judge-rep = one `claude -p` invocation grading all of a
run's criteria together), inheriting the crash-safe resume semantics of the
main queue. Queue helpers live here so queue.py stays untouched.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any, Callable

from harness import headless, queue
from harness.taskcards import TaskCard

VERDICTS = ("met", "not_met", "cannot_judge")
DIFF_CHAR_LIMIT = 80_000
SHEET_DIFF_LINE_LIMIT = 400

JUDGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS judge_runs (
    judge_run_id TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    model        TEXT NOT NULL,
    rep          INTEGER NOT NULL DEFAULT 1,
    order_key    INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','running','done','error','skipped')),
    attempt      INTEGER NOT NULL DEFAULT 0,
    verdicts     TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    error        TEXT,
    resume_after TEXT
);
"""

PROMPT_TEMPLATE = """You are grading whether a code change meets each acceptance criterion.
You see: the task a developer was given, the acceptance criteria, and the
final unified diff. Nothing else about how the change was produced is
available; judge only what the diff shows.

Verdict meanings:
- "met": the diff clearly satisfies the criterion
- "not_met": the diff clearly fails it or leaves it unaddressed
- "cannot_judge": the diff alone is insufficient to decide

Respond with ONLY a JSON object (no markdown fences, no prose):
{{"verdicts": [{{"criterion": 1, "verdict": "met|not_met|cannot_judge", "rationale": "<one sentence>"}}, ...]}}
There are {n} criteria; return exactly {n} verdicts, in order.

## Task
{task_prompt}

## Acceptance criteria
{criteria}

## Diff
{diff}
"""

RETRY_PREFIX = (
    "Your previous reply was not valid JSON. Reply with ONLY the JSON object "
    "described below, nothing else.\n\n"
)


class ArmLeakError(RuntimeError):
    """The assembled judge prompt would reveal the experimental arm."""


# --- diff scrubbing -------------------------------------------------------

_SECTION_RE = re.compile(r"^diff --git ", re.MULTILINE)


def scrub_diff(diff_text: str) -> tuple[str, bool]:
    """Drop every diff section whose target basename is CLAUDE.md (any depth).

    Returns (scrubbed_text, removed_any). Non-CLAUDE.md sections are
    preserved byte-identically.
    """
    if not diff_text:
        return diff_text, False
    starts = [m.start() for m in _SECTION_RE.finditer(diff_text)]
    if not starts:
        return diff_text, False
    kept: list[str] = []
    removed = False
    preamble = diff_text[: starts[0]]
    if preamble:
        kept.append(preamble)
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(diff_text)
        section = diff_text[start:end]
        header = section.splitlines()[0] if section else ""
        target = header.rsplit(" b/", 1)[-1] if " b/" in header else header
        basename = target.replace("\\", "/").rstrip("/").split("/")[-1]
        if basename.lower() == "claude.md":
            removed = True
            continue
        kept.append(section)
    return "".join(kept), removed


def assert_arm_blind(prompt: str) -> None:
    if "claude.md" in prompt.lower():
        raise ArmLeakError("assembled judge prompt still mentions CLAUDE.md")


# --- prompt + parsing -----------------------------------------------------

def build_prompt(task: TaskCard, diff_text: str) -> tuple[str, bool, bool]:
    """Returns (prompt, diff_scrubbed, diff_truncated). Raises ArmLeakError."""
    scrubbed, removed = scrub_diff(diff_text)
    truncated = False
    if len(scrubbed) > DIFF_CHAR_LIMIT:
        scrubbed = scrubbed[:DIFF_CHAR_LIMIT] + "\n[diff truncated]\n"
        truncated = True
    criteria = "\n".join(f"{i}. {c}" for i, c in enumerate(task.criteria, start=1))
    prompt = PROMPT_TEMPLATE.format(
        n=len(task.criteria),
        task_prompt=task.prompt.strip(),
        criteria=criteria,
        diff=scrubbed if scrubbed.strip() else "(empty diff: no tracked changes)",
    )
    assert_arm_blind(prompt)
    return prompt, removed, truncated


def parse_verdicts(text: str, n_criteria: int) -> list[dict[str, Any]] | None:
    """Lenient parse of the judge's reply. None on any structural failure."""
    if not isinstance(text, str) or not text.strip():
        return None
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    verdicts = data.get("verdicts") if isinstance(data, dict) else None
    if not isinstance(verdicts, list) or len(verdicts) != n_criteria:
        return None
    out = []
    for i, item in enumerate(verdicts, start=1):
        if not isinstance(item, dict):
            return None
        verdict = item.get("verdict")
        if verdict not in VERDICTS:
            return None
        criterion = item.get("criterion")
        try:
            criterion = int(criterion)
        except (TypeError, ValueError):
            criterion = i
        out.append(
            {
                "criterion": criterion,
                "verdict": verdict,
                "rationale": str(item.get("rationale") or ""),
            }
        )
    return out


# --- scoring --------------------------------------------------------------

def artifact_name(model: str, rep: int) -> str:
    return f"judge--{model}--r{rep}.json"


def score_run(
    run_id: str,
    results_dir: Path | str,
    task: TaskCard,
    model: str = "sonnet",
    rep: int = 1,
    timeout_s: int = 900,
    invoke: Callable[..., dict[str, Any]] = headless.invoke_claude,
) -> dict[str, Any]:
    """Judge one completed run from its stored artifacts only.

    Raises ArmLeakError (caller marks the judge run skipped), RateLimited
    (caller returns it to pending), or RuntimeError (caller marks it error).
    """
    results_dir = Path(results_dir)
    run_dir = results_dir / "runs" / run_id
    diff_path = run_dir / "diff.patch"
    if not diff_path.exists():
        raise RuntimeError(f"missing artifact: {diff_path}")
    if not task.criteria:
        raise RuntimeError(f"task {task.id} has no acceptance criteria to judge")

    prompt, scrubbed, truncated = build_prompt(
        task, diff_path.read_text(encoding="utf-8")
    )

    scratch = results_dir / "judge-scratch"
    scratch.mkdir(parents=True, exist_ok=True)

    cli_result = invoke(prompt, model, scratch, timeout_s)
    raw_text = cli_result.get("result") or ""
    verdicts = parse_verdicts(raw_text, len(task.criteria))
    if verdicts is None:
        cli_result = invoke(RETRY_PREFIX + prompt, model, scratch, timeout_s)
        raw_text = cli_result.get("result") or ""
        verdicts = parse_verdicts(raw_text, len(task.criteria))
    if verdicts is None:
        raise RuntimeError("judge reply unparseable after one retry")

    payload = {
        "judge_run_id": f"{run_id}--judge--{model}--r{rep}",
        "run_id": run_id,
        "model": model,
        "rep": rep,
        "verdicts": verdicts,
        "raw_result_text": raw_text,
        "diff_scrubbed": scrubbed,
        "diff_truncated": truncated,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "cli": {
            "total_cost_usd": cli_result.get("total_cost_usd"),
            "num_turns": cli_result.get("num_turns"),
            "duration_ms": cli_result.get("duration_ms"),
            "session_id": cli_result.get("session_id"),
        },
    }
    (run_dir / artifact_name(model, rep)).write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    return payload


# --- judge queue (helpers local to keep queue.py untouched) ---------------

def init_judge_table(conn) -> None:
    with conn:
        conn.executescript(JUDGE_SCHEMA)


def enqueue_judge_runs(
    conn,
    judge_model: str,
    reps: int = 1,
    *,
    cards_by_id: dict[str, TaskCard],
    results_dir: Path | str,
    include_control: bool = False,
) -> int:
    """Enqueue judge work for every done run with a diff artifact.

    Control cards are excluded by default (they never enter confirmatory
    analysis). INSERT OR IGNORE keeps re-planning idempotent. order_key is
    inherited from the underlying run so judging drains in schedule order.
    """
    init_judge_table(conn)
    results_dir = Path(results_dir)
    inserted = 0
    rows = conn.execute("SELECT run_id, task_id, order_key FROM runs WHERE status = 'done'")
    with conn:
        for row in rows.fetchall():
            task = cards_by_id.get(row["task_id"])
            if task is None or not task.criteria:
                continue
            if task.control and not include_control:
                continue
            if not (results_dir / "runs" / row["run_id"] / "diff.patch").exists():
                continue
            for rep in range(1, reps + 1):
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO judge_runs
                        (judge_run_id, run_id, model, rep, order_key)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        f"{row['run_id']}--judge--{judge_model}--r{rep}",
                        row["run_id"],
                        judge_model,
                        rep,
                        row["order_key"],
                    ),
                )
                inserted += cur.rowcount
    return inserted


def claim_next_judge(conn, now: str | None = None) -> dict[str, Any] | None:
    now = now or queue.now_iso()
    with conn:
        row = conn.execute(
            """
            SELECT judge_run_id FROM judge_runs
            WHERE status = 'pending'
              AND (resume_after IS NULL OR resume_after <= ?)
            ORDER BY order_key
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if row is None:
            return None
        jid = row["judge_run_id"]
        cur = conn.execute(
            """
            UPDATE judge_runs
            SET status = 'running', attempt = attempt + 1,
                started_at = ?, resume_after = NULL, error = NULL
            WHERE judge_run_id = ? AND status = 'pending'
            """,
            (now, jid),
        )
        if cur.rowcount != 1:
            return None
    claimed = conn.execute(
        "SELECT * FROM judge_runs WHERE judge_run_id = ?", (jid,)
    ).fetchone()
    return dict(claimed)


def mark_done_judge(conn, judge_run_id: str, verdicts_json: str) -> None:
    with conn:
        conn.execute(
            "UPDATE judge_runs SET status = 'done', finished_at = ?, verdicts = ? "
            "WHERE judge_run_id = ?",
            (queue.now_iso(), verdicts_json, judge_run_id),
        )


def mark_error_judge(conn, judge_run_id: str, error: str) -> None:
    with conn:
        conn.execute(
            "UPDATE judge_runs SET status = 'error', finished_at = ?, error = ? "
            "WHERE judge_run_id = ?",
            (queue.now_iso(), error[:4000], judge_run_id),
        )


def mark_skipped_judge(conn, judge_run_id: str, reason: str) -> None:
    with conn:
        conn.execute(
            "UPDATE judge_runs SET status = 'skipped', finished_at = ?, error = ? "
            "WHERE judge_run_id = ?",
            (queue.now_iso(), reason, judge_run_id),
        )


def mark_rate_limited_judge(conn, judge_run_id: str, resume_after: str) -> None:
    with conn:
        conn.execute(
            """
            UPDATE judge_runs
            SET status = 'pending', attempt = attempt - 1,
                started_at = NULL, resume_after = ?
            WHERE judge_run_id = ?
            """,
            (resume_after, judge_run_id),
        )


def reset_stale_judge(conn) -> int:
    with conn:
        cur = conn.execute(
            "UPDATE judge_runs SET status = 'pending', started_at = NULL "
            "WHERE status = 'running'"
        )
        return cur.rowcount


# --- calibration ----------------------------------------------------------

def calibration_pairs(conn, cards_by_id: dict[str, TaskCard]) -> list[dict[str, Any]]:
    """Explode done judge rows into per-criterion units for sampling."""
    units = []
    rows = conn.execute(
        """
        SELECT j.judge_run_id, j.run_id, j.verdicts, r.task_id
        FROM judge_runs j JOIN runs r ON r.run_id = j.run_id
        WHERE j.status = 'done' AND j.verdicts IS NOT NULL
        ORDER BY j.judge_run_id
        """
    )
    for row in rows.fetchall():
        task = cards_by_id.get(row["task_id"])
        if task is None:
            continue
        try:
            verdicts = json.loads(row["verdicts"])
        except json.JSONDecodeError:
            continue
        for i, verdict in enumerate(verdicts, start=1):
            criterion_text = (
                task.criteria[i - 1] if i <= len(task.criteria) else "(unknown)"
            )
            units.append(
                {
                    "judge_run_id": row["judge_run_id"],
                    "run_id": row["run_id"],
                    "criterion_index": i,
                    "criterion_text": criterion_text,
                    "judge_verdict": verdict.get("verdict"),
                }
            )
    return units


def _run_id_hash(run_id: str) -> str:
    """Run ids embed the arm; the sheet shows a hash so the founder grades blind."""
    return hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:10]


def write_calibration_sheet(
    units: list[dict[str, Any]],
    results_dir: Path | str,
    reports_dir: Path | str,
    sample_size: int = 100,
    seed: int = 42,
) -> tuple[Path, Path, Path]:
    """Emit the founder-grading sheet (verdicts and run ids hidden) + key.

    Returns (sheet_csv, sheet_md, key_csv). The sheet holds sample_id,
    criterion, and blank grading columns; the key file maps sample_id back to
    (run_id, criterion_index, judge_verdict) for the kappa join. Cohen's
    kappa requires independent raters, so the judge's verdict appears
    nowhere in the sheet.
    """
    import csv as csv_mod

    results_dir, reports_dir = Path(results_dir), Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    sample = units if len(units) <= sample_size else rng.sample(units, sample_size)
    sample = sorted(sample, key=lambda u: (u["judge_run_id"], u["criterion_index"]))
    rng.shuffle(sample)  # presentation order carries no run grouping

    sheet_csv = reports_dir / "judge-calibration-sheet.csv"
    sheet_md = reports_dir / "judge-calibration-sheet.md"
    key_csv = reports_dir / "judge-calibration-key.csv"

    with open(sheet_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv_mod.writer(fh)
        writer.writerow(["sample_id", "run_ref", "criterion", "sam_verdict", "notes"])
        for i, unit in enumerate(sample, start=1):
            writer.writerow(
                [
                    f"cal-{i:03d}",
                    _run_id_hash(unit["run_id"]),
                    unit["criterion_text"],
                    "",
                    "",
                ]
            )

    md = [
        "# Judge calibration sheet",
        "",
        "Grade each item met / not_met / cannot_judge from the diff alone,",
        "then fill the sam_verdict column in judge-calibration-sheet.csv.",
        "Run references are hashed; the judge's own verdicts are withheld",
        "so your grades are independent (Cohen's kappa requires it).",
        "",
    ]
    for i, unit in enumerate(sample, start=1):
        diff_path = Path(results_dir) / "runs" / unit["run_id"] / "diff.patch"
        diff_text = ""
        if diff_path.exists():
            diff_text, _ = scrub_diff(diff_path.read_text(encoding="utf-8"))
        lines = diff_text.splitlines()
        if len(lines) > SHEET_DIFF_LINE_LIMIT:
            lines = lines[:SHEET_DIFF_LINE_LIMIT] + ["[diff truncated for sheet]"]
        md += [
            f"## cal-{i:03d} (run {_run_id_hash(unit['run_id'])})",
            "",
            f"**Criterion:** {unit['criterion_text']}",
            "",
            "```diff",
            *(lines or ["(empty diff: no tracked changes)"]),
            "```",
            "",
            "**Your verdict:** ",
            "",
        ]
    sheet_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    with open(key_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv_mod.writer(fh)
        writer.writerow(["sample_id", "run_id", "criterion_index", "judge_verdict"])
        for i, unit in enumerate(sample, start=1):
            writer.writerow(
                [
                    f"cal-{i:03d}",
                    unit["run_id"],
                    unit["criterion_index"],
                    unit["judge_verdict"],
                ]
            )
    return sheet_csv, sheet_md, key_csv


def cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    """Cohen's kappa over paired categorical verdicts.

    po = observed agreement; pe = expected agreement from the raters'
    marginals; kappa = (po - pe) / (1 - pe). Degenerate case: pe == 1
    (both raters used a single identical category) returns 1.0.
    """
    if not pairs:
        raise ValueError("no pairs to compare")
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    categories = {a for a, _ in pairs} | {b for _, b in pairs}
    pe = sum(
        (sum(1 for a, _ in pairs if a == c) / n)
        * (sum(1 for _, b in pairs if b == c) / n)
        for c in categories
    )
    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def kappa_from_files(graded_csv: Path | str, key_csv: Path | str) -> dict[str, Any]:
    """Join the founder's graded sheet with the key; compute kappa + confusion."""
    import csv as csv_mod

    with open(graded_csv, newline="", encoding="utf-8") as fh:
        graded = {row["sample_id"]: row for row in csv_mod.DictReader(fh)}
    with open(key_csv, newline="", encoding="utf-8") as fh:
        key = {row["sample_id"]: row for row in csv_mod.DictReader(fh)}

    pairs: list[tuple[str, str]] = []
    skipped = 0
    for sample_id, key_row in key.items():
        graded_row = graded.get(sample_id)
        sam = (graded_row or {}).get("sam_verdict", "").strip().lower().replace(" ", "_")
        if sam not in VERDICTS:
            skipped += 1
            continue
        pairs.append((sam, key_row["judge_verdict"]))

    confusion: dict[str, dict[str, int]] = {
        a: {b: 0 for b in VERDICTS} for a in VERDICTS
    }
    for sam, jv in pairs:
        if jv in VERDICTS:
            confusion[sam][jv] += 1
    return {
        "n_graded": len(pairs),
        "n_skipped": skipped,
        "kappa": cohens_kappa(pairs) if pairs else None,
        "raw_agreement": (
            sum(1 for a, b in pairs if a == b) / len(pairs) if pairs else None
        ),
        "confusion": confusion,
    }
