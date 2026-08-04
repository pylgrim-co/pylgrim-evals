"""E-coord episode runner: checkpoint/resume round-trip, pause-not-abort
gates, first-mover determinism, per-arm slice composition, merged-tree slot
lifecycle, and the M4 defect detectors — with claude mocked throughout."""

import json
import subprocess
import sys
from collections import deque
from pathlib import Path

import pytest

from harness import episode, queue, workspace
from harness.headless import RateLimited
from harness.taskcards import TaskCard

# --- fixtures ----------------------------------------------------------------


def _git(*args, cwd):
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path):
    """A tiny origin repo with one base commit (cloned bare by the runner)."""
    r = tmp_path / "origin"
    r.mkdir()
    _git("init", cwd=r)
    _git("config", "user.email", "t@t", cwd=r)
    _git("config", "user.name", "t", cwd=r)
    (r / "shared.txt").write_text("line1\nline2\nline3\n", encoding="utf-8")
    (r / "docs.txt").write_text("docs\n", encoding="utf-8")
    _git("add", ".", cwd=r)
    _git("commit", "-m", "base", cwd=r)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(r), capture_output=True, text=True
    ).stdout.strip()
    return r, sha


def _exists_cmd(filename):
    """Cross-platform outcome command: pass iff the file exists in the tree."""
    return (
        f'"{sys.executable}" -c "import pathlib,sys; '
        f"sys.exit(0 if pathlib.Path('{filename}').exists() else 1)\""
    )


def make_card(card_id, title, base_sha, outcome_file):
    return TaskCard(
        id=card_id,
        kind="real",
        title=title,
        base_sha=base_sha,
        prompt=f"Implement {title}.",
        constraints=[f"Constraint for {card_id}."],
        criteria=[f"{outcome_file} exists."],
        scope_paths=["*"],
        out_of_scope=[],
        test_command=_exists_cmd(outcome_file),
    )


def make_scenario(base_sha, scenario_id="demo-s01", repo_name="demo",
                  file_a="feature_a.txt", file_b="feature_b.txt"):
    return episode.Scenario(
        scenario_id=scenario_id,
        repo=repo_name,
        base_sha=base_sha,
        pressure="medium",
        cards={
            "a": make_card(f"{scenario_id}-a", "task alpha", base_sha, file_a),
            "b": make_card(f"{scenario_id}-b", "task beta", base_sha, file_b),
        },
    )


class ProcessDeath(BaseException):
    """Simulated hard process death: not an Exception, so the runner's
    bounded-retry and orchestrator-error paths cannot swallow it."""


class MockCLI:
    """Scripted claude: per-agent action queues, transcript fabrication.

    Actions: ("edit", filename, content), ("noop",),
    ("gate", resume_after) -> raises RateLimited once,
    ("error", msg) -> raises RuntimeError once,
    ("die",) -> raises ProcessDeath once."""

    def __init__(self, plan):
        self.plan = {agent: deque(actions) for agent, actions in plan.items()}
        self.calls = []
        self.executed = {"a": 0, "b": 0}
        self.tool_paths = {"a": [], "b": []}

    def _agent_for(self, workspace_dir):
        text = str(workspace_dir)
        return "a" if "agent-a" in text else "b"

    def __call__(self, prompt, model, workspace_dir, timeout_s,
                 resume_session=None, pid_callback=None, **kwargs):
        agent = self._agent_for(workspace_dir)
        self.calls.append(
            {"agent": agent, "prompt": prompt, "resume_session": resume_session}
        )
        action = self.plan[agent].popleft() if self.plan[agent] else ("noop",)
        if action[0] == "gate":
            raise RateLimited("usage cap", resume_after=action[1])
        if action[0] == "error":
            raise RuntimeError(action[1])
        if action[0] == "die":
            raise ProcessDeath()
        if action[0] == "edit":
            target = Path(workspace_dir) / action[1]
            target.write_text(action[2], encoding="utf-8")
            self.tool_paths[agent].append(str(target))
        ordinal = self.executed[agent]
        self.executed[agent] += 1
        return {
            "session_id": f"sess-{agent}-{ordinal}",
            "num_turns": 3 if action[0] == "edit" else 1,
            "usage": {
                "input_tokens": 100,
                "cache_read_input_tokens": 10,
                "cache_creation_input_tokens": 5,
            },
            "total_cost_usd": 0.01,
            "modelUsage": {"sonnet": {"inputTokens": 100, "outputTokens": 20}},
            "result": "ok",
        }

    def copy_transcript(self, cwd, session_id, dest):
        agent = self._agent_for(cwd)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        events = []
        for path in self.tool_paths[agent]:
            events.append({
                "type": "assistant",
                "timestamp": "2026-08-01T00:00:00Z",
                "message": {
                    "model": "sonnet",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                    "content": [{
                        "type": "tool_use", "name": "Write",
                        "input": {"file_path": path},
                    }],
                },
            })
        dest.write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )
        return dest


def seed_episode_db(tmp_path, scenario, arm, rep=1, turn_cap=2):
    db_path = tmp_path / "episodes.db"
    conn = queue.connect(db_path)
    episode.init_episode_db(conn)
    rows = [{
        "episode_id": episode.episode_id_for(scenario.scenario_id, arm, rep),
        "scenario_id": scenario.scenario_id,
        "repo": scenario.repo,
        "arm": arm,
        "model": "sonnet",
        "rep": rep,
        "seed": 1,
        "order_key": 0,
        "first_mover": episode.first_mover(scenario.scenario_id, rep),
        "turn_cap": turn_cap,
    }]
    episode.insert_schedule(conn, rows)
    return db_path, conn


def run_one(conn, scenario, repo_dir, results_dir, mock, **kwargs):
    row, gated = episode.claim_next_episode(conn)
    assert row is not None, f"nothing claimable (gated until {gated})"
    return episode.run_episode(
        conn, row, scenario, str(repo_dir), results_dir,
        preserve=(), invoke=mock, copy_transcript_fn=mock.copy_transcript,
        echo=lambda _m: None, **kwargs,
    )


# --- schema migration (wall_s; heartbeat_at idiom) ---------------------------


def test_wall_s_migration_is_idempotent_and_leaves_old_rows_null(tmp_path):
    """A pre-wall_s episodes.db picks up the column via init_episode_db;
    existing rows read back NULL; re-running the init is a no-op."""
    db_path = tmp_path / "episodes.db"
    conn = queue.connect(db_path)
    old_schema = episode.EPISODE_SCHEMA.replace("wall_s       REAL,\n", "")
    assert "wall_s" not in old_schema  # guard: the pilot-era table shape
    with conn:
        conn.executescript(old_schema)
        conn.execute(
            "INSERT INTO episode_turns (episode_id, turn_idx, agent, round_idx) "
            "VALUES ('old-ep', 0, 'a', 0)"
        )
    episode.init_episode_db(conn)  # migrates
    episode.init_episode_db(conn)  # idempotent second pass
    cols = {r[1] for r in conn.execute("PRAGMA table_info(episode_turns)")}
    assert "wall_s" in cols
    assert conn.execute("SELECT wall_s FROM episode_turns").fetchone()["wall_s"] is None
    conn.close()


# --- first mover (M3) --------------------------------------------------------


def test_first_mover_deterministic_and_arm_independent():
    for rep in (1, 2, 3):
        movers = {episode.first_mover("demo-s01", rep) for _ in range(5)}
        assert len(movers) == 1  # deterministic (arm and episode id are not inputs)
    # movers vary across (scenario, rep) pairs somewhere in a small sweep
    values = {
        episode.first_mover(f"scen-{i}", rep) for i in range(10) for rep in (1, 2, 3)
    }
    assert values == {"a", "b"}


def test_schedule_first_mover_same_across_arms(repo):
    _r, sha = repo
    scenario = make_scenario(sha)
    rows = episode.generate_schedule(
        [scenario], list(episode.EPISODE_ARMS), reps=2, seed=42,
        model="sonnet", turn_cap=6,
    )
    assert len(rows) == 6
    for rep in (1, 2):
        movers = {r["first_mover"] for r in rows if r["rep"] == rep}
        assert len(movers) == 1
        assert movers == {episode.first_mover(scenario.scenario_id, rep)}


# --- slice composition per arm (§1 arm table) --------------------------------


def test_control_arm_gets_prompt_and_title_disclosure_only(repo):
    _r, sha = repo
    scenario = make_scenario(sha)
    message, slice_text = episode.turn_message("coord-none", scenario, "a", True, [])
    assert slice_text is None
    assert scenario.cards["a"].prompt in message
    assert 'titled: "task beta"' in message  # title-only disclosure
    assert ".pylgrim" not in message  # no ledger channel in the control
    # resume turn: the verbatim nudge, nothing else
    resume_msg, resume_slice = episode.turn_message("coord-none", scenario, "a", False, [])
    assert resume_msg == episode.CONTINUATION_NUDGE
    assert resume_slice is None


def test_ledger_arm_slice_has_both_work_items_no_presence(repo):
    _r, sha = repo
    scenario = make_scenario(sha)
    message, slice_text = episode.turn_message("coord-ledger", scenario, "a", True, [])
    assert slice_text is not None
    assert "demo-s01-a" in slice_text and "feature_a.txt exists." in slice_text
    assert "feature_b.txt exists." in slice_text  # BOTH ratified work items
    assert "Presence brief" not in slice_text  # NO per-turn presence, ever
    assert message.startswith(slice_text)  # slice tops the message
    assert 'titled: "task beta"' in message  # same disclosure discipline


def test_bundle_arm_slice_adds_presence_brief_with_touched_paths(repo):
    _r, sha = repo
    scenario = make_scenario(sha)
    _msg, slice_text = episode.turn_message(
        "coord-pylgrim", scenario, "a", False, ["src/registry.py", "docs.txt"]
    )
    assert "Presence brief" in slice_text
    assert "- src/registry.py" in slice_text and "- docs.txt" in slice_text
    assert "sibling branch: wi/demo-s01-b" in slice_text
    assert "sibling work item: demo-s01-b" in slice_text
    # empty touched set is explicit, so slice structure is constant within arm
    _msg2, slice2 = episode.turn_message("coord-pylgrim", scenario, "b", True, [])
    assert "(none yet)" in slice2


def test_touched_paths_relativized_and_outside_root_dropped(tmp_path):
    root = tmp_path / "wt"
    root.mkdir()
    transcript = tmp_path / "t.jsonl"
    events = [
        {"type": "assistant", "message": {"usage": {}, "content": [
            {"type": "tool_use", "name": "Edit",
             "input": {"file_path": str(root / "src" / "x.py")}}]}},
        {"type": "assistant", "message": {"usage": {}, "content": [
            {"type": "tool_use", "name": "Read",
             "input": {"file_path": str(tmp_path / "elsewhere.txt")}}]}},
        {"type": "assistant", "message": {"usage": {}, "content": [
            {"type": "tool_use", "name": "Write",
             "input": {"file_path": "relative/y.py"}}]}},
    ]
    transcript.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    touched = episode.touched_paths_from_transcript(transcript, root)
    assert touched == ["relative/y.py", "src/x.py"]  # outside-root path dropped


# --- full episode: merged-tree slot lifecycle + metric raw inputs ------------


def test_clean_episode_end_to_end_with_merged_slot(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-ledger", turn_cap=2)
    mock = MockCLI({
        "a": [("edit", "feature_a.txt", "alpha\n"), ("noop",)],
        "b": [("edit", "feature_b.txt", "beta\n"), ("noop",)],
    })
    record = run_one(conn, scenario, repo_dir, results_dir, mock)

    c1 = record["metrics_inputs"]["c1"]
    assert c1["merge_clean"] is True
    assert c1["any_collision"] is False
    assert c1["untracked_path_collisions"] == []
    assert c1["changed_files"]["a"] == ["feature_a.txt"]
    c5 = record["metrics_inputs"]["c5"]
    assert c5["combined_success"] is True
    assert c5["own_branch_pass"] == {"a": True, "b": True}
    c3 = record["metrics_inputs"]["c3"]
    assert c3["evaluable"] is True and c3["contradiction"] is False
    c4 = record["metrics_inputs"]["c4"]
    assert c4["total_cost_usd"] == pytest.approx(0.04)
    assert c4["model_usage"]["sonnet"]["inputTokens"] == 400
    m9 = record["metrics_inputs"]["m9"]
    assert len(m9) == 4 and all(t["context_tokens"] == 115 for t in m9)
    # per-turn wall time (invocation-only scope) present and plausible
    # everywhere a turn is mirrored: episode.json turns, m9, and the DB rows
    assert all(
        isinstance(t["wall_s"], float) and t["wall_s"] > 0 for t in record["turns"]
    )
    assert all(isinstance(t["wall_s"], float) and t["wall_s"] > 0 for t in m9)

    # merged-tree slot: materialized, both features present, HEAD = merged commit
    merged = episode.merged_slot_dir(results_dir)
    assert (merged / "feature_a.txt").exists() and (merged / "feature_b.txt").exists()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(merged), capture_output=True, text=True
    ).stdout.strip()
    assert head == record["merged"]["commit"]

    # both agents declared completion on their noop turn (before the cap)
    m7 = record["metrics_inputs"]["m7"]
    assert all(m7[a]["declared_complete"] for a in ("a", "b"))
    assert not any(m7[a]["cap_hit"] for a in ("a", "b"))

    # queue row done, results archived
    row = conn.execute("SELECT * FROM episodes").fetchone()
    assert row["status"] == "done"
    assert Path(row["results_path"]).exists()
    # per-turn slices archived for every ledger-arm turn, hash-recorded
    turns = conn.execute(
        "SELECT * FROM episode_turns ORDER BY turn_idx").fetchall()
    assert len(turns) == 4
    assert all(t["slice_path"] and t["slice_sha256"] for t in turns)
    assert all(t["status"] == "done" for t in turns)
    assert all(t["wall_s"] is not None and t["wall_s"] > 0 for t in turns)


def test_conflict_episode_records_c1_collision_and_c5_failure(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha, file_a="feature_a.txt", file_b="feature_b.txt")
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-none", turn_cap=1)
    mock = MockCLI({
        "a": [("edit", "shared.txt", "agent-a version\n")],
        "b": [("edit", "shared.txt", "agent-b version\n")],
    })
    record = run_one(conn, scenario, repo_dir, results_dir, mock)
    c1 = record["metrics_inputs"]["c1"]
    assert c1["merge_clean"] is False
    assert c1["any_collision"] is True
    assert "shared.txt" in c1["conflicted_files"]
    assert c1["file_overlap"] == ["shared.txt"]
    c3 = record["metrics_inputs"]["c3"]
    assert c3["evaluable"] is False and c3["contradiction"] is None
    assert record["metrics_inputs"]["c5"]["combined_success"] is False
    assert "skipped" in record["outcomes"]["merged"]["a"]


def test_same_new_path_different_content_hits_untracked_clause(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha, file_a="new.txt", file_b="feature_b.txt")
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-none", turn_cap=1)
    mock = MockCLI({
        "a": [("edit", "new.txt", "from a\n")],
        "b": [("edit", "new.txt", "from b\n")],
    })
    record = run_one(conn, scenario, repo_dir, results_dir, mock)
    c1 = record["metrics_inputs"]["c1"]
    collisions = c1["untracked_path_collisions"]
    assert [c["path"] for c in collisions] == ["new.txt"]
    assert c1["any_collision"] is True


def test_bundle_arm_presence_brief_carries_sibling_touched_paths(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-pylgrim", turn_cap=1)
    mock = MockCLI({
        "a": [("edit", "feature_a.txt", "alpha\n")],
        "b": [("edit", "feature_b.txt", "beta\n")],
    })
    run_one(conn, scenario, repo_dir, results_dir, mock)
    mover = episode.first_mover(scenario.scenario_id, 1)
    second = "b" if mover == "a" else "a"
    mover_file = "feature_a.txt" if mover == "a" else "feature_b.txt"
    # the second mover's turn-1 slice must list the first mover's touched path
    eid = episode.episode_id_for(scenario.scenario_id, "coord-pylgrim", 1)
    second_row = conn.execute(
        "SELECT * FROM episode_turns WHERE episode_id = ? AND agent = ?",
        (eid, second),
    ).fetchone()
    slice_text = Path(second_row["slice_path"]).read_text(encoding="utf-8")
    assert f"- {mover_file}" in slice_text
    # and the first mover's slice saw "(none yet)"
    mover_row = conn.execute(
        "SELECT * FROM episode_turns WHERE episode_id = ? AND agent = ?",
        (eid, mover),
    ).fetchone()
    assert "(none yet)" in Path(mover_row["slice_path"]).read_text(encoding="utf-8")


# --- checkpoint / resume round-trip (O1) -------------------------------------


def test_kill_mid_episode_then_resume_from_checkpoint(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-ledger", turn_cap=2)
    mover = episode.first_mover(scenario.scenario_id, 1)
    second = "b" if mover == "a" else "a"
    mover_file = "feature_a.txt" if mover == "a" else "feature_b.txt"
    second_file = "feature_b.txt" if mover == "a" else "feature_a.txt"
    # order of invocations: mover r0, second r0, mover r1, second r1.
    # the process "dies" on the second mover's first turn.
    mock = MockCLI({
        mover: [("edit", mover_file, "v1\n"), ("noop",)],
        second: [("die",), ("edit", second_file, "v1\n"), ("noop",)],
    })
    with pytest.raises(ProcessDeath):
        run_one(conn, scenario, repo_dir, results_dir, mock)
    # died mid-claim: row still 'running', one checkpointed turn survives
    row = conn.execute("SELECT * FROM episodes").fetchone()
    assert row["status"] == "running"
    assert conn.execute("SELECT COUNT(*) FROM episode_turns").fetchone()[0] == 1

    # heartbeat-stale reclaim (the dead process stopped stamping), then resume
    assert episode.reclaim_stale_episodes(conn, 0, now="2999-01-01T00:00:00+00:00") == 1
    # plant a sentinel wall_s on the checkpointed turn: resume must NOT
    # re-time completed turns, so the sentinel has to survive verbatim
    sentinel_wall_s = 123.456
    with conn:
        conn.execute("UPDATE episode_turns SET wall_s = ?", (sentinel_wall_s,))
    record = run_one(conn, scenario, repo_dir, results_dir, mock)
    assert record["metrics_inputs"]["c5"]["combined_success"] is True
    # the mover's checkpointed turn was NOT re-invoked: it executed exactly 2
    # actions (edit + noop) across both runs, and turn order stayed strict
    agents_called = [c["agent"] for c in mock.calls]
    assert agents_called == [mover, second, second, mover, second]
    turns = conn.execute(
        "SELECT agent, round_idx, status FROM episode_turns ORDER BY turn_idx"
    ).fetchall()
    assert [(t["agent"], t["round_idx"]) for t in turns] == [
        (mover, 0), (second, 0), (mover, 1), (second, 1)
    ]
    # resume chained the mover's session, not a fresh one
    mover_calls = [c for c in mock.calls if c["agent"] == mover]
    assert mover_calls[0]["resume_session"] is None
    assert mover_calls[1]["resume_session"] == f"sess-{mover}-0"
    # checkpointed wall_s survived resume unchanged; freshly executed turns
    # got their own measured (plausible, > 0) wall times
    wall_rows = conn.execute(
        "SELECT turn_idx, wall_s FROM episode_turns ORDER BY turn_idx"
    ).fetchall()
    assert wall_rows[0]["wall_s"] == sentinel_wall_s
    assert all(r["wall_s"] is not None and r["wall_s"] > 0 for r in wall_rows[1:])
    assert record["turns"][0]["wall_s"] == sentinel_wall_s


def test_resume_tree_hash_gate_fires_on_tampered_worktree(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-ledger", turn_cap=2)
    mover = episode.first_mover(scenario.scenario_id, 1)
    second = "b" if mover == "a" else "a"
    mock = MockCLI({
        mover: [("edit", "feature_a.txt", "v1\n")],
        second: [("die",)],
    })
    with pytest.raises(ProcessDeath):
        run_one(conn, scenario, repo_dir, results_dir, mock)
    episode.reclaim_stale_episodes(conn, 0, now="2999-01-01T00:00:00+00:00")
    # tamper the mover's worktree between death and resume
    slot = episode.agent_slot_dir(results_dir, mover)
    (slot / "tampered.txt").write_text("junk\n", encoding="utf-8")
    with pytest.raises(episode.EpisodeDefect) as exc_info:
        run_one(conn, scenario, repo_dir, results_dir, mock)
    assert exc_info.value.defect_class == episode.DEFECT_TREE_HASH_MISMATCH
    row = conn.execute("SELECT * FROM episodes").fetchone()
    assert row["status"] == "error"
    defects = json.loads(row["defects"])
    assert defects[0]["class"] == episode.DEFECT_TREE_HASH_MISMATCH


def test_invoked_row_is_completed_on_resume_without_reinvoking(repo, tmp_path):
    """A crash between session persistence and the turn's 'done' update loses
    nothing: resume finishes the row from current worktree state (O6)."""
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-none", turn_cap=1)
    mock = MockCLI({
        "a": [("edit", "feature_a.txt", "v1\n")],
        "b": [("edit", "feature_b.txt", "v1\n")],
    })
    run_one(conn, scenario, repo_dir, results_dir, mock)
    calls_before = len(mock.calls)
    eid = episode.episode_id_for(scenario.scenario_id, "coord-none", 1)
    # simulate the crash window: last turn back to 'invoked', episode pending
    # (wall_s was checkpointed with the 'invoked' row; plant a sentinel to
    # prove the finish path never re-times it)
    sentinel_wall_s = 777.5
    with conn:
        conn.execute(
            "UPDATE episode_turns SET status = 'invoked', tree_hash = NULL, "
            "wall_s = ? WHERE episode_id = ? AND turn_idx = "
            "(SELECT MAX(turn_idx) FROM episode_turns WHERE episode_id = ?)",
            (sentinel_wall_s, eid, eid),
        )
        conn.execute(
            "UPDATE episodes SET status = 'pending', finished_at = NULL "
            "WHERE episode_id = ?", (eid,),
        )
    record = run_one(conn, scenario, repo_dir, results_dir, mock)
    assert len(mock.calls) == calls_before  # no re-invocation
    turns = conn.execute(
        "SELECT status, tree_hash, wall_s FROM episode_turns "
        "WHERE episode_id = ? ORDER BY turn_idx", (eid,)
    ).fetchall()
    assert all(t["status"] == "done" and t["tree_hash"] for t in turns)
    assert turns[-1]["wall_s"] == sentinel_wall_s  # finished, not re-timed
    assert record["metrics_inputs"]["c5"]["combined_success"] is True


# --- pause-not-abort rate-limit gates (O2) -----------------------------------


def test_rate_limit_pauses_episode_and_resume_preserves_order(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-ledger", turn_cap=2)
    mover = episode.first_mover(scenario.scenario_id, 1)
    second = "b" if mover == "a" else "a"
    mover_file = "feature_a.txt" if mover == "a" else "feature_b.txt"
    second_file = "feature_b.txt" if mover == "a" else "feature_a.txt"
    gate_time = "2999-01-01T00:00:00+00:00"
    # gate fires on the second mover's ROUND-1 turn (the 4th invocation)
    mock = MockCLI({
        mover: [("edit", mover_file, "v1\n"), ("noop",)],
        second: [("edit", second_file, "v1\n"), ("gate", gate_time), ("noop",)],
    })
    with pytest.raises(RateLimited):
        run_one(conn, scenario, repo_dir, results_dir, mock)
    row = conn.execute("SELECT * FROM episodes").fetchone()
    assert row["status"] == "pending"  # PAUSED, not aborted
    assert row["resume_after"] == gate_time
    assert row["pause_count"] == 1
    assert conn.execute("SELECT COUNT(*) FROM episode_turns").fetchone()[0] == 3

    # while gated, the in-flight episode BLOCKS all claims (slots hold state)
    claimed, gated_until = episode.claim_next_episode(conn)
    assert claimed is None and gated_until == gate_time

    # after the gate opens, resume claims the SAME episode and finishes it in
    # the same turn order, resuming the same sessions
    with conn:
        conn.execute("UPDATE episodes SET resume_after = '2000-01-01T00:00:00+00:00'")
    record = run_one(conn, scenario, repo_dir, results_dir, mock)
    turns = conn.execute(
        "SELECT agent, round_idx FROM episode_turns ORDER BY turn_idx").fetchall()
    assert [(t["agent"], t["round_idx"]) for t in turns] == [
        (mover, 0), (second, 0), (mover, 1), (second, 1)
    ]
    second_calls = [c for c in mock.calls if c["agent"] == second]
    # 3 invocations of the second mover: edit, the gated attempt, the resume
    assert len(second_calls) == 3
    assert second_calls[2]["resume_session"] == f"sess-{second}-0"
    assert record["pause_count"] == 1
    assert record["metrics_inputs"]["c5"]["combined_success"] is True


# --- defect detectors (M4 + item 5) ------------------------------------------


def test_cli_failure_after_bounded_retry_records_defect(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-none", turn_cap=1)
    mover = episode.first_mover(scenario.scenario_id, 1)
    other = "b" if mover == "a" else "a"
    mock = MockCLI({
        mover: [("error", "exit 1"), ("error", "exit 1 again")],
        other: [],
    })
    with pytest.raises(episode.EpisodeDefect) as exc_info:
        run_one(conn, scenario, repo_dir, results_dir, mock)
    assert exc_info.value.defect_class == episode.DEFECT_CLI_FAILURE
    row = conn.execute("SELECT * FROM episodes").fetchone()
    assert row["status"] == "error"
    defects = json.loads(row["defects"])
    assert defects[0]["class"] == episode.DEFECT_CLI_FAILURE
    # exactly CLI_RETRIES + 1 attempts were made
    assert len([c for c in mock.calls if c["agent"] == mover]) == episode.CLI_RETRIES + 1


def test_tampered_archived_slice_fires_slice_hash_detector(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-ledger", turn_cap=2)
    mover = episode.first_mover(scenario.scenario_id, 1)
    second = "b" if mover == "a" else "a"
    mock = MockCLI({
        mover: [("edit", "feature_a.txt", "v1\n")],
        second: [("die",)],
    })
    with pytest.raises(ProcessDeath):
        run_one(conn, scenario, repo_dir, results_dir, mock)
    episode.reclaim_stale_episodes(conn, 0, now="2999-01-01T00:00:00+00:00")
    slice_path = conn.execute(
        "SELECT slice_path FROM episode_turns").fetchone()["slice_path"]
    Path(slice_path).write_text("tampered slice\n", encoding="utf-8")
    with pytest.raises(episode.EpisodeDefect) as exc_info:
        run_one(conn, scenario, repo_dir, results_dir, mock)
    assert exc_info.value.defect_class == episode.DEFECT_SLICE_HASH_MISMATCH
    row = conn.execute("SELECT * FROM episodes").fetchone()
    assert row["status"] == "error"
    assert json.loads(row["defects"])[0]["class"] == episode.DEFECT_SLICE_HASH_MISMATCH


def test_unresumable_session_defect_class(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-none", turn_cap=2)
    mover = episode.first_mover(scenario.scenario_id, 1)
    other = "b" if mover == "a" else "a"
    mock = MockCLI({
        mover: [
            ("edit", "feature_a.txt", "v1\n"),
            ("error", "No conversation found with session ID sess-x"),
        ],
        other: [("noop",)],
    })
    with pytest.raises(episode.EpisodeDefect) as exc_info:
        run_one(conn, scenario, repo_dir, results_dir, mock)
    assert exc_info.value.defect_class == episode.DEFECT_UNRESUMABLE_SESSION


# --- schedule + scenario loading ---------------------------------------------


def test_generate_schedule_rep_blocked_and_arm_balanced(repo):
    _r, sha = repo
    scenarios = [make_scenario(sha, scenario_id=f"demo-s{i:02d}") for i in range(3)]
    rows = episode.generate_schedule(
        scenarios, list(episode.EPISODE_ARMS), reps=2, seed=42,
        model="sonnet", turn_cap=6,
    )
    assert len(rows) == 18
    # rep-blocked: all rep-1 order keys precede all rep-2 order keys
    max_r1 = max(r["order_key"] for r in rows if r["rep"] == 1)
    min_r2 = min(r["order_key"] for r in rows if r["rep"] == 2)
    assert max_r1 < min_r2
    # deterministic under the same seed
    again = episode.generate_schedule(
        scenarios, list(episode.EPISODE_ARMS), reps=2, seed=42,
        model="sonnet", turn_cap=6,
    )
    assert rows == again
    with pytest.raises(ValueError):
        episode.generate_schedule(scenarios, ["bogus-arm"], 1, 42, "sonnet", 6)


def test_load_scenario_validates_shape(tmp_path, repo):
    _r, sha = repo
    good = {
        "scenario_id": "demo-s01",
        "repo": "demo",
        "base_sha": sha,
        "pressure": "high",
        "work_items": {
            "a": {
                "id": "demo-s01-a", "kind": "real", "title": "t",
                "base_sha": sha, "prompt": "p",
                "intent": {"constraints": [], "work_item": {
                    "criteria": ["c"], "scope_paths": ["*"], "out_of_scope": []}},
                "outcome": {"test_command": "true"},
                "source": {"issue_url": "u", "ground_truth_pr": "p"},
            },
            "b": {
                "id": "demo-s01-b", "kind": "real", "title": "t2",
                "base_sha": sha, "prompt": "p2",
                "intent": {"constraints": [], "work_item": {
                    "criteria": ["c"], "scope_paths": ["*"], "out_of_scope": []}},
                "outcome": {"test_command": "true"},
                "source": {"issue_url": "u", "ground_truth_pr": "p"},
            },
        },
    }
    import yaml as yaml_mod

    path = tmp_path / "demo-s01.yaml"
    path.write_text(yaml_mod.safe_dump(good), encoding="utf-8")
    scenario, errors = episode.load_scenario(path)
    assert errors == [] and scenario is not None
    assert scenario.cards["a"].id == "demo-s01-a"

    bad = dict(good, pressure="ultra")
    bad["work_items"] = {"a": good["work_items"]["a"]}  # missing b
    path2 = tmp_path / "demo-s02.yaml"
    path2.write_text(yaml_mod.safe_dump(bad), encoding="utf-8")
    scenario2, errors2 = episode.load_scenario(path2)
    assert scenario2 is None
    assert any("pressure" in e for e in errors2)
    assert any("work_items" in e for e in errors2)


def test_load_scenario_accepts_authored_pilot_shape(tmp_path, repo):
    """The shape committed in scenarios/pilot/: cards list, pinned_sha,
    pressure.stratum, kind: coord, status: pilot."""
    _r, sha = repo
    import yaml as yaml_mod

    card = {
        "id": "ecoord-x01-a", "kind": "coord", "title": "t",
        "base_sha": sha, "prompt": "p",
        "intent": {"constraints": [], "work_item": {
            "criteria": ["c"], "scope_paths": ["*"], "out_of_scope": []}},
        "outcome": {"test_command": "true"},
        "source": {"authored": True},
    }
    data = {
        "scenario_id": "ecoord-x01",
        "study": "e-coord",
        "status": "pilot",
        "repo": "demo",
        "pinned_sha": sha,
        "pressure": {"stratum": "high", "rationale": "shared registry"},
        "cards": [card, {**card, "id": "ecoord-x01-b"}],
    }
    sub = tmp_path / "scen" / "pilot"
    sub.mkdir(parents=True)
    (sub / "ecoord-x01.yaml").write_text(yaml_mod.safe_dump(data), encoding="utf-8")
    scenarios, errors = episode.load_all_scenarios(tmp_path / "scen")
    assert errors == []
    assert len(scenarios) == 1  # recursive discovery picked up pilot/
    s = scenarios[0]
    assert s.base_sha == sha and s.pressure == "high" and s.status == "pilot"
    assert s.cards["a"].id == "ecoord-x01-a" and s.cards["b"].id == "ecoord-x01-b"
    assert s.cards["a"].kind == "coord"  # original kind preserved


def test_committed_pilot_scenarios_load_cleanly():
    """The pilot set the scenario-authoring workstream committed must parse
    through the runner's loader without a single error."""
    pilot_dir = Path(__file__).resolve().parents[2] / "scenarios"
    if not (pilot_dir / "pilot").exists():
        pytest.skip("no pilot scenarios committed yet")
    scenarios, errors = episode.load_all_scenarios(pilot_dir)
    assert errors == []
    assert len(scenarios) >= 6
    for s in scenarios:
        assert s.status in ("pilot", "confirmatory", "calibration")
        assert s.pressure in episode.PRESSURE_STRATA
        assert s.cards["a"].test_command and s.cards["b"].test_command


def test_episode_drain_runs_to_done_and_reports(repo, tmp_path):
    repo_dir, sha = repo
    scenario = make_scenario(sha)
    results_dir = tmp_path / "results"
    db_path, conn = seed_episode_db(tmp_path, scenario, "coord-none", turn_cap=1)
    mock = MockCLI({
        "a": [("edit", "feature_a.txt", "v1\n")],
        "b": [("edit", "feature_b.txt", "v1\n")],
    })
    totals = episode.run_episode_drain(
        db_path, results_dir, {scenario.scenario_id: scenario},
        {"demo": {"url": str(repo_dir), "preserve": []}},
        invoke=mock, copy_transcript_fn=mock.copy_transcript,
        echo=lambda _m: None,
    )
    assert totals["done"] == 1 and totals["error"] == 0
    assert totals["summary"]["by_status"] == {"done": 1}


def test_tree_hash_survives_gitignored_preserve_dirs(repo):
    # Regression: git 2.43 exits 1 ("addIgnoredFile" advice) when an explicit
    # pathspec walk covers ignored dirs — killed 13/16 pilot episodes
    # 2026-08-01. Bare `git add -A` + index-level preserve removal must not.
    repo_dir, sha = repo
    (repo_dir / ".gitignore").write_text("node_modules/\n")
    nm = repo_dir / "node_modules" / "dep"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = 1\n")
    h1 = workspace.worktree_tree_hash(repo_dir, preserve=("node_modules",))
    # preserve content must not perturb the hash
    (nm / "index.js").write_text("module.exports = 2\n")
    h2 = workspace.worktree_tree_hash(repo_dir, preserve=("node_modules",))
    assert h1 == h2
    # non-ignored, non-preserved content must
    (repo_dir / "real.txt").write_text("x\n")
    assert workspace.worktree_tree_hash(repo_dir, preserve=("node_modules",)) != h1
    # and the commit path takes the same staging helper
    out = workspace.commit_worktree(repo_dir, sha, "test", preserve=("node_modules",))
    assert out["tree"]
