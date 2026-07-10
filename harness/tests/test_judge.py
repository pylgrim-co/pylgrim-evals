"""Judge: diff scrubbing, arm blindness, parsing, queue transactions,
calibration sampling, and Cohen's kappa."""

import json

import pytest

from harness import headless, judge, queue
from harness.taskcards import TaskCard

CLAUDEMD_SECTION = (
    "diff --git a/CLAUDE.md b/CLAUDE.md\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/CLAUDE.md\n"
    "+# Constraints\n"
    "+- do not touch CI\n"
)
CODE_SECTION = (
    "diff --git a/src/app/feature.py b/src/app/feature.py\n"
    "--- a/src/app/feature.py\n"
    "+++ b/src/app/feature.py\n"
    "@@ -1 +1,2 @@\n"
    " x = 1\n"
    "+y = 2\n"
)


def make_task(criteria=("A greet function exists.", "Tests pass.")):
    return TaskCard(
        id="alpha-t01",
        kind="real",
        title="t",
        base_sha="a" * 40,
        prompt="Fix the greeting bug in src/app/feature.py.",
        constraints=[],
        criteria=list(criteria),
        scope_paths=["src/*"],
        out_of_scope=[],
    )


def good_reply(n=2):
    return json.dumps(
        {
            "verdicts": [
                {"criterion": i, "verdict": "met", "rationale": "looks right"}
                for i in range(1, n + 1)
            ]
        }
    )


# --- scrubbing and blindness ------------------------------------------------

def test_scrub_removes_claudemd_sections_only():
    diff = CLAUDEMD_SECTION + CODE_SECTION
    scrubbed, removed = judge.scrub_diff(diff)
    assert removed is True
    assert scrubbed == CODE_SECTION

    nested = CLAUDEMD_SECTION.replace("CLAUDE.md", "docs/CLAUDE.md") + CODE_SECTION
    scrubbed, removed = judge.scrub_diff(nested)
    assert removed is True
    assert scrubbed == CODE_SECTION


def test_scrub_noop_on_clean_diff():
    scrubbed, removed = judge.scrub_diff(CODE_SECTION)
    assert removed is False
    assert scrubbed == CODE_SECTION
    assert judge.scrub_diff("") == ("", False)


def test_assert_arm_blind():
    with pytest.raises(judge.ArmLeakError):
        judge.assert_arm_blind("the file claude.md was changed")
    judge.assert_arm_blind("a clean prompt")


def test_build_prompt_blind_end_to_end():
    prompt, scrubbed, truncated = judge.build_prompt(
        make_task(), CLAUDEMD_SECTION + CODE_SECTION
    )
    assert scrubbed is True and truncated is False
    assert "claude" not in prompt.lower().replace("cannot_judge", "")
    assert "src/app/feature.py" in prompt
    assert "1. A greet function exists." in prompt


def test_build_prompt_unscrubbable_raises():
    diff = CODE_SECTION.replace("+y = 2", "+# see CLAUDE.md for rules")
    with pytest.raises(judge.ArmLeakError):
        judge.build_prompt(make_task(), diff)


def test_build_prompt_truncates_large_diff():
    big = CODE_SECTION + "+" + "x" * (judge.DIFF_CHAR_LIMIT + 100)
    prompt, _, truncated = judge.build_prompt(make_task(), big)
    assert truncated is True
    assert "[diff truncated]" in prompt


# --- parsing ----------------------------------------------------------------

def test_parse_verdicts_clean_and_fenced():
    assert judge.parse_verdicts(good_reply(), 2)[0]["verdict"] == "met"
    fenced = "```json\n" + good_reply() + "\n```"
    assert judge.parse_verdicts(fenced, 2) is not None
    prose = "Here are my verdicts:\n" + good_reply() + "\nHope that helps!"
    assert judge.parse_verdicts(prose, 2) is not None


def test_parse_verdicts_failures():
    assert judge.parse_verdicts(good_reply(1), 2) is None  # wrong count
    bad_value = good_reply().replace("met", "maybe")
    assert judge.parse_verdicts(bad_value, 2) is None
    assert judge.parse_verdicts("no json here", 2) is None
    assert judge.parse_verdicts("", 2) is None
    assert judge.parse_verdicts('{"verdicts": "met"}', 2) is None


# --- score_run ---------------------------------------------------------------

def setup_run_dir(tmp_path, run_id="alpha-t01--claudemd--sonnet--r1",
                  diff=CLAUDEMD_SECTION + CODE_SECTION):
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "diff.patch").write_text(diff, encoding="utf-8")
    return run_id


def test_score_run_writes_artifact(tmp_path):
    run_id = setup_run_dir(tmp_path)
    calls = []

    def fake_invoke(prompt, model, cwd, timeout_s):
        calls.append(prompt)
        return {"result": good_reply(), "total_cost_usd": 0.01, "session_id": "s1"}

    payload = judge.score_run(run_id, tmp_path, make_task(), invoke=fake_invoke)
    assert len(calls) == 1
    assert "claude" not in calls[0].lower().replace("cannot_judge", "")
    assert run_id not in calls[0]
    assert payload["diff_scrubbed"] is True
    assert [v["verdict"] for v in payload["verdicts"]] == ["met", "met"]
    artifact = tmp_path / "runs" / run_id / "judge--sonnet--r1.json"
    assert artifact.exists()
    stored = json.loads(artifact.read_text(encoding="utf-8"))
    assert stored["raw_result_text"] == good_reply()


def test_score_run_retries_once_then_succeeds(tmp_path):
    run_id = setup_run_dir(tmp_path)
    replies = iter(["not json at all", good_reply()])
    calls = []

    def fake_invoke(prompt, model, cwd, timeout_s):
        calls.append(prompt)
        return {"result": next(replies)}

    payload = judge.score_run(run_id, tmp_path, make_task(), invoke=fake_invoke)
    assert len(calls) == 2
    assert calls[1].startswith(judge.RETRY_PREFIX)
    assert payload["verdicts"][0]["verdict"] == "met"


def test_score_run_double_failure_raises(tmp_path):
    run_id = setup_run_dir(tmp_path)

    def fake_invoke(prompt, model, cwd, timeout_s):
        return {"result": "nope"}

    with pytest.raises(RuntimeError, match="unparseable"):
        judge.score_run(run_id, tmp_path, make_task(), invoke=fake_invoke)


def test_score_run_rate_limit_propagates(tmp_path):
    run_id = setup_run_dir(tmp_path)

    def fake_invoke(prompt, model, cwd, timeout_s):
        raise headless.RateLimited("limit", resume_after="2026-07-10T12:00:00")

    with pytest.raises(headless.RateLimited):
        judge.score_run(run_id, tmp_path, make_task(), invoke=fake_invoke)


# --- judge queue --------------------------------------------------------------

def make_db(tmp_path, statuses=("done",), task_id="alpha-t01", with_diff=True):
    db = tmp_path / "runs.db"
    conn = queue.connect(db)
    queue.init_db(conn)
    judge.init_judge_table(conn)
    rows = []
    for i, status in enumerate(statuses):
        run_id = f"{task_id}--{'claudemd' if i % 2 else 'vanilla'}--sonnet--r{i + 1}"
        rows.append(
            {
                "run_id": run_id,
                "repo": "alpha",
                "task_id": task_id,
                "arm": "vanilla",
                "model": "sonnet",
                "rep": i + 1,
                "seed": 1,
                "order_key": i,
            }
        )
    queue.insert_schedule(conn, rows)
    for i, status in enumerate(statuses):
        conn.execute(
            "UPDATE runs SET status = ? WHERE run_id = ?", (status, rows[i]["run_id"])
        )
    conn.commit()
    if with_diff:
        for row in rows:
            run_dir = tmp_path / "runs" / row["run_id"]
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "diff.patch").write_text(CODE_SECTION, encoding="utf-8")
    return conn, db, rows


def test_enqueue_idempotent_and_filtered(tmp_path):
    conn, _, rows = make_db(tmp_path, statuses=("done", "done", "pending"))
    cards = {"alpha-t01": make_task()}
    n1 = judge.enqueue_judge_runs(
        conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path
    )
    assert n1 == 2  # only done rows
    n2 = judge.enqueue_judge_runs(
        conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path
    )
    assert n2 == 0  # idempotent


def test_enqueue_skips_controls_unless_included(tmp_path):
    conn, _, _ = make_db(tmp_path, statuses=("done",))
    control = make_task()
    control.control = True
    cards = {"alpha-t01": control}
    assert judge.enqueue_judge_runs(
        conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path
    ) == 0
    assert judge.enqueue_judge_runs(
        conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path,
        include_control=True,
    ) == 1


def test_enqueue_skips_missing_diff(tmp_path):
    conn, _, _ = make_db(tmp_path, statuses=("done",), with_diff=False)
    cards = {"alpha-t01": make_task()}
    assert judge.enqueue_judge_runs(
        conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path
    ) == 0


def test_judge_queue_lifecycle(tmp_path):
    conn, db, _ = make_db(tmp_path, statuses=("done",))
    cards = {"alpha-t01": make_task()}
    judge.enqueue_judge_runs(conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path)

    row = judge.claim_next_judge(conn)
    assert row is not None and row["status"] == "running" and row["attempt"] == 1
    # a second claim finds nothing (single pending row now running)
    assert judge.claim_next_judge(conn) is None

    judge.mark_rate_limited_judge(conn, row["judge_run_id"], "2999-01-01T00:00:00")
    back = conn.execute(
        "SELECT * FROM judge_runs WHERE judge_run_id = ?", (row["judge_run_id"],)
    ).fetchone()
    assert back["status"] == "pending" and back["attempt"] == 0
    assert judge.claim_next_judge(conn) is None  # gated by resume_after

    conn.execute(
        "UPDATE judge_runs SET resume_after = NULL WHERE judge_run_id = ?",
        (row["judge_run_id"],),
    )
    conn.commit()
    row = judge.claim_next_judge(conn)
    judge.mark_done_judge(conn, row["judge_run_id"], good_reply())
    done = conn.execute(
        "SELECT * FROM judge_runs WHERE judge_run_id = ?", (row["judge_run_id"],)
    ).fetchone()
    assert done["status"] == "done"
    assert json.loads(done["verdicts"])["verdicts"][0]["verdict"] == "met"


def test_reset_stale_judge(tmp_path):
    conn, _, _ = make_db(tmp_path, statuses=("done",))
    cards = {"alpha-t01": make_task()}
    judge.enqueue_judge_runs(conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path)
    judge.claim_next_judge(conn)
    assert judge.reset_stale_judge(conn) == 1
    assert judge.claim_next_judge(conn) is not None


# --- calibration ---------------------------------------------------------------

def seed_done_judges(conn, tmp_path, n_runs=5):
    cards = {"alpha-t01": make_task()}
    judge.enqueue_judge_runs(conn, "sonnet", 1, cards_by_id=cards, results_dir=tmp_path)
    for row in conn.execute("SELECT judge_run_id FROM judge_runs").fetchall():
        judge.mark_done_judge(
            conn,
            row["judge_run_id"],
            json.dumps(
                [
                    {"criterion": 1, "verdict": "met", "rationale": ""},
                    {"criterion": 2, "verdict": "not_met", "rationale": ""},
                ]
            ),
        )
    return cards


def test_calibration_sheet_blind_and_deterministic(tmp_path):
    conn, _, rows = make_db(tmp_path, statuses=("done", "done", "done"))
    cards = seed_done_judges(conn, tmp_path)
    units = judge.calibration_pairs(conn, cards)
    assert len(units) == 6  # 3 runs x 2 criteria
    reports = tmp_path / "reports"
    sheet_csv, sheet_md, key_csv = judge.write_calibration_sheet(
        units, tmp_path, reports, sample_size=4, seed=7
    )
    sheet_text = sheet_csv.read_text(encoding="utf-8")
    md_text = sheet_md.read_text(encoding="utf-8")
    for forbidden in ("met,", "not_met", "vanilla", "claudemd"):
        assert forbidden not in sheet_text
    for row in rows:
        assert row["run_id"] not in sheet_text
        assert row["run_id"] not in md_text
    key_text = key_csv.read_text(encoding="utf-8")
    assert "not_met" in key_text  # judge verdicts live only in the key

    again_csv, _, _ = judge.write_calibration_sheet(
        units, tmp_path, reports, sample_size=4, seed=7
    )
    assert again_csv.read_text(encoding="utf-8") == sheet_text  # seeded determinism


def test_cohens_kappa_values():
    perfect = [("met", "met")] * 10 + [("not_met", "not_met")] * 10
    assert judge.cohens_kappa(perfect) == pytest.approx(1.0)

    # Textbook 2-category example: po=0.7, pe=0.5 -> kappa=0.4
    pairs = (
        [("met", "met")] * 35
        + [("met", "not_met")] * 15
        + [("not_met", "met")] * 15
        + [("not_met", "not_met")] * 35
    )
    assert judge.cohens_kappa(pairs) == pytest.approx(0.4)

    assert judge.cohens_kappa([("met", "met")] * 5) == 1.0  # degenerate
    disagree = [("met", "not_met")] * 10 + [("not_met", "met")] * 10
    assert judge.cohens_kappa(disagree) <= 0


def test_kappa_from_files(tmp_path):
    import csv

    key = tmp_path / "key.csv"
    graded = tmp_path / "graded.csv"
    with open(key, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["sample_id", "run_id", "criterion_index", "judge_verdict"])
        writer.writerow(["cal-001", "r1", 1, "met"])
        writer.writerow(["cal-002", "r1", 2, "not_met"])
        writer.writerow(["cal-003", "r2", 1, "met"])
    with open(graded, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["sample_id", "run_ref", "criterion", "sam_verdict", "notes"])
        writer.writerow(["cal-001", "x", "c", "met", ""])
        writer.writerow(["cal-002", "x", "c", "Not Met", ""])  # normalized
        writer.writerow(["cal-003", "x", "c", "", ""])  # ungraded -> skipped
    result = judge.kappa_from_files(graded, key)
    assert result["n_graded"] == 2
    assert result["n_skipped"] == 1
    assert result["raw_agreement"] == 1.0
    assert result["confusion"]["not_met"]["not_met"] == 1
