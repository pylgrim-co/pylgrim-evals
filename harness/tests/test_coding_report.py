"""Coding-task report builder: flattening, aggregation, pairing, exclusions."""

import csv

from harness import coding_report
from harness.taskcards import TaskCard


def make_card(kind="real", control=False, honeypots=1):
    return TaskCard(
        id="alpha-t01",
        kind=kind,
        title="t",
        base_sha="a" * 40,
        prompt="p",
        constraints=[],
        criteria=["c1"],
        scope_paths=["src/*"],
        out_of_scope=["docs/*"],
        honeypots=[{"path": f"hp{i}.py"} for i in range(honeypots)],
        control=control,
    )


def make_row(run_id="alpha-t01--vanilla--sonnet--r1", arm="vanilla", status="done"):
    task_id, _, _, rep = run_id.split("--")
    return {
        "run_id": run_id,
        "task_id": task_id,
        "repo": "alpha",
        "arm": arm,
        "model": "sonnet",
        "rep": int(rep[1:]),
        "status": status,
        "attempt": 1,
        "seed": 7,
        "started_at": "2026-07-10T00:00:00",
        "finished_at": "2026-07-10T00:05:00",
    }


def make_record(
    share=0.25,
    touched=True,
    violated=("no-ci-edits",),
    passed=True,
    output_tokens=1000,
    cost=0.5,
    untracked=("CLAUDE.md", "junk.txt"),
):
    return {
        "cli_result": {
            "modelUsage": {
                "claude-sonnet-4-6": {
                    "inputTokens": 100,
                    "outputTokens": output_tokens,
                    "cacheReadInputTokens": 5000,
                    "cacheCreationInputTokens": 200,
                }
            }
        },
        "metrics": {
            "scope": {
                "total_churn_lines": 40,
                "out_of_scope_churn_lines": 10,
                "out_of_scope_churn_share": share,
                "out_of_scope_files_count": 1,
                "out_of_scope_files": ["docs/x.md"],
                "untracked_files": list(untracked),
                "out_of_scope_untracked_files": list(untracked),
            },
            "honeypots": {"honeypot_touched": touched, "touched": []},
            "violations": [
                {"rule": r, "violated": True} for r in violated
            ] + [{"rule": "no-new-deps", "violated": False}],
            "outcome": {
                "passed": passed,
                "deterministic_checks": [{"passed": True}, {"passed": False}],
            },
            "tokens": {
                "totals": {"input_tokens": 400, "output_tokens": 4000},
                "tool_counts": {"Read": 3, "Edit": 2, "Bash": 1},
                "wall_time_s": 120.0,
                "cli": {
                    "total_cost_usd": cost,
                    "num_turns": 10,
                    "duration_ms": 60000,
                    "duration_api_ms": 55000,
                    "model_usage": {
                        "claude-sonnet-4-6": {
                            "inputTokens": 100,
                            "outputTokens": output_tokens,
                            "cacheReadInputTokens": 5000,
                            "cacheCreationInputTokens": 200,
                        }
                    },
                },
            },
            "drift_tokens": {
                "attributed_output_tokens": 50,
                "attributed_turns": 1,
                "total_turns": 10,
                "unattributed_tool_calls": {"Bash": 1},
            },
        },
        "provenance": {
            "claude_code_version": "2.1.175",
            "harness_git_sha": "b" * 40,
            "base_sha": "a" * 40,
        },
    }


def test_flatten_full_record():
    flat = coding_report.flatten_run(make_row(), make_record(), make_card())
    assert flat["run_id"] == "alpha-t01--vanilla--sonnet--r1"
    assert flat["kind"] == "real"
    assert flat["control"] is False
    assert flat["honeypot_touched"] is True
    assert flat["out_of_scope_churn_share"] == 0.25
    assert flat["violations_active"] == 2
    assert flat["violations_violated"] == 1
    assert flat["violated_rules"] == "no-ci-edits"
    assert flat["tests_passed"] is True
    assert flat["det_checks_passed"] == 1
    assert flat["det_checks_total"] == 2
    assert flat["input_tokens"] == 100
    assert flat["output_tokens"] == 1000
    assert flat["cache_read_tokens"] == 5000
    assert flat["transcript_output_tokens"] == 4000
    assert flat["total_cost_usd"] == 0.5
    assert flat["tool_calls_total"] == 6
    assert flat["tool_calls_bash"] == 1
    assert flat["drift_attributed_output_tokens"] == 50
    assert flat["drift_unattributed_tool_calls"] == 1
    assert flat["claude_code_version"] == "2.1.175"


def test_flatten_missing_metrics_yields_empty_not_zero():
    flat = coding_report.flatten_run(make_row(), {"metrics": {}}, make_card())
    assert flat["output_tokens"] == ""
    assert flat["honeypot_touched"] == ""
    assert flat["tests_passed"] == ""
    assert flat["drift_attributed_output_tokens"] == ""
    no_record = coding_report.flatten_run(make_row(), None, None)
    assert no_record["kind"] == ""
    assert no_record["output_tokens"] == ""


def test_claudemd_untracked_excluded_root_only():
    record = make_record(untracked=("CLAUDE.md", "docs/CLAUDE.md", "junk.txt"))
    flat = coding_report.flatten_run(make_row(), record, make_card())
    assert flat["out_of_scope_untracked_count"] == 3
    assert flat["out_of_scope_untracked_excl_claudemd"] == 2


def test_csv_round_trip(tmp_path):
    flat = coding_report.flatten_run(make_row(), make_record(), make_card())
    path = tmp_path / "out.csv"
    coding_report.write_csv([flat], path)
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == coding_report.COLUMNS
    assert rows[0]["output_tokens"] == "1000"
    assert rows[0]["violated_rules"] == "no-ci-edits"


def test_percentile_helpers():
    assert coding_report._p90([5.0]) == 5.0
    assert coding_report._p90([1.0, 2.0]) == 2.0
    assert coding_report._p90(list(map(float, range(1, 11)))) == 9.0
    assert coding_report._median([1.0, 2.0, 3.0, 4.0]) == 2.5
    assert coding_report._mean([]) is None
    assert coding_report._p90([]) is None


def _flat(run_id, arm, kind="real", control=False, **record_kwargs):
    card = make_card(kind=kind, control=control)
    card.id = run_id.split("--")[0]
    return coding_report.flatten_run(
        make_row(run_id=run_id, arm=arm), make_record(**record_kwargs), card
    )


def test_paired_deltas_and_unpaired():
    rows = [
        _flat("alpha-t01--vanilla--sonnet--r1", "vanilla", output_tokens=1000, cost=1.0),
        _flat("alpha-t01--claudemd--sonnet--r1", "claudemd", output_tokens=600, cost=0.4),
        _flat("alpha-t02--vanilla--sonnet--r1", "vanilla"),  # unpaired
    ]
    lines = coding_report._paired_deltas(rows)
    text = "\n".join(lines)
    assert "| alpha-t01 |" in text
    assert "-400" in text  # output-token delta B - A
    assert "-0.600" in text  # cost delta
    assert "Unpaired (excluded): alpha-t02" in text


def test_kind_split_never_pooled():
    rows = [
        _flat("alpha-t01--vanilla--sonnet--r1", "vanilla", kind="real"),
        _flat("beta-t01--vanilla--sonnet--r1", "vanilla", kind="bait"),
    ]
    report = coding_report.build_report([make_row()], rows, {}, 1)
    assert "| vanilla | real |" in report
    assert "| vanilla | bait |" in report


def test_controls_excluded_from_scoreboards_present_in_validity():
    control = _flat(
        "alpha-c01--vanilla--sonnet--r1", "vanilla", kind="bait", control=True,
        share=0.9, touched=True,
    )
    report = coding_report.build_report([], [control], {}, 1)
    assert "alpha-c01--vanilla--sonnet--r1" in report
    validity = report.split("## Positive controls")[1]
    assert "| PASS | PASS | PASS |" in validity
    scoreboards = report.split("## Positive controls")[0]
    assert "alpha-c01" not in scoreboards
    # and no confirmatory row exists for its (arm, kind) cell
    assert "| vanilla | bait | 1 |" not in scoreboards


def test_control_fail_cells():
    control = _flat(
        "alpha-c01--vanilla--sonnet--r1", "vanilla", kind="bait", control=True,
        share=0.0, touched=False, violated=(),
    )
    report = coding_report.build_report([], [control], {}, 1)
    validity = report.split("## Positive controls")[1]
    assert "| FAIL | FAIL | FAIL |" in validity


def test_zero_runs_renders_all_sections():
    report = coding_report.build_report([], [], {"schedule_seed": "42"}, 3)
    for header in (
        "# Coding-task drift report #3",
        "## Inventory",
        "## M1: honeypot-touch rate",
        "## M2: out-of-scope churn share",
        "## M3: rule violations",
        "## M5: test-pass rate",
        "## Token economy",
        "## Positive controls",
        "## Provenance",
    ):
        assert header in report
    assert "schedule_seed: 42" in report


def test_next_report_number(tmp_path):
    assert coding_report.next_report_number(tmp_path) == 1
    (tmp_path / "coding-report-1.md").write_text("x", encoding="utf-8")
    (tmp_path / "coding-report-7.md").write_text("x", encoding="utf-8")
    (tmp_path / "skills-stress-9.md").write_text("x", encoding="utf-8")
    assert coding_report.next_report_number(tmp_path) == 8


def test_version_drift_warning():
    a = _flat("alpha-t01--vanilla--sonnet--r1", "vanilla")
    b = _flat("alpha-t01--claudemd--sonnet--r1", "claudemd")
    b["claude_code_version"] = "2.2.0"
    report = coding_report.build_report([], [a, b], {}, 1)
    assert "WARNING: version drift" in report
