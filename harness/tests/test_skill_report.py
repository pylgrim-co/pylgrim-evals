"""Report rendering: sections present, non-activated runs segregated,
failures ranked, trigger matrix rendered, numbering monotonic."""

from pathlib import Path

from harness import skill_report


def _record(run_id="map-rich-clean-t01--cooperative--haiku--r1", skill="pylgrim-map",
            model="haiku", activated=True, extra_checks=None, run_dir="results/zoo-runs/x"):
    checks = [{"assertion": "activated",
               "status": "pass" if activated else "fail",
               "evidence": "Skill tool_use" if activated else "no Skill tool_use"}]
    checks += extra_checks or []
    return {
        "run": {"run_id": run_id, "model": model},
        "scenario": {"id": run_id.split("--")[0], "skill": skill,
                     "fixture": "rich-clean", "persona": "cooperative",
                     "invoke": "explicit"},
        "checks": checks,
        "_run_dir": run_dir,
    }


def test_report_sections_and_ranking(tmp_path):
    runs = [
        _record(extra_checks=[
            {"assertion": "spec_valid", "status": "pass", "evidence": "0 errors"},
            {"assertion": "zero_network", "status": "fail",
             "evidence": "Bash: curl https://evil"},
            {"assertion": "within_budgets", "status": "fail",
             "evidence": "wall time 700s > 600s bar"},
        ]),
        _record(run_id="plan-empty-t01--cooperative--haiku--r1",
                skill="pylgrim-plan", activated=False),
    ]
    triggers = [
        {"probe": {"id": "map-should-01", "skill": "pylgrim-map", "expect": "should",
                   "prompt": "pylgrim map"},
         "fired_skills": ["pylgrim-map"], "target_fired": True, "correct": True},
        {"probe": {"id": "map-shouldnot-02", "skill": "pylgrim-map",
                   "expect": "should_not", "prompt": "Generate a sitemap"},
         "fired_skills": ["pylgrim-map"], "target_fired": True, "correct": False},
    ]
    text = skill_report.build_report(runs, triggers, 3, {"by_status": {"done": 2}})

    assert "# Skills stress report 3" in text
    for heading in ("## Reading guide", "## Scoreboard", "## H4 bars",
                    "## Failures, ranked",
                    "## Not activated", "## Worst-output gallery", "## Trigger matrix"):
        assert heading in text
    # Security failures listed before budget failures.
    assert text.index("Security-class") < text.index("Budget-class")
    assert "curl https://evil" in text
    # The non-activated run is segregated, not scored.
    assert "plan-empty-t01--cooperative--haiku--r1" in text.split("## Not activated")[1]
    assert "**FALSE FIRE**" in text
    assert "1 activated, 1 not activated" in text


def test_scoreboard_excludes_na_from_denominator():
    runs = [_record(extra_checks=[
        {"assertion": "spec_valid", "status": "pass", "evidence": "ok"},
        {"assertion": "anti_padding", "status": "na", "evidence": "not barren"},
    ])]
    text = skill_report.build_report(runs, [], 1)
    # spec_valid 1/1 = 100%; anti_padding has no scored runs, shown as 100% of zero.
    assert "| spec_valid | 1 | 0 | 0 | 100% |" in text


def test_below_bar_flagging():
    runs = [_record(extra_checks=[
        {"assertion": "spec_valid", "status": "fail", "evidence": "3 errors"}])]
    text = skill_report.build_report(runs, [], 1)
    assert "**below bar**" in text


def test_h4_bars_per_tier_rates_and_wall_time_median():
    # Two sonnet map runs (one spec_valid fail: 1/2 = 50%, below the 95% bar)
    # and two sonnet plan runs whose wall times give a 500s median (meets).
    runs = [
        _record(run_id="map-a--cooperative--sonnet--r1", model="sonnet",
                extra_checks=[
                    {"assertion": "spec_valid", "status": "pass", "evidence": "ok"},
                    {"assertion": "entry_cap_15", "status": "pass", "evidence": "9"},
                    {"assertion": "evidence_resolves", "status": "pass",
                     "evidence": "10/10"},
                    {"assertion": "zero_network", "status": "pass", "evidence": "ok"},
                ]),
        _record(run_id="map-b--cooperative--sonnet--r1", model="sonnet",
                extra_checks=[
                    {"assertion": "spec_valid", "status": "fail", "evidence": "1 err"},
                ]),
        {**_record(run_id="plan-a--cooperative--sonnet--r1", model="sonnet",
                   skill="pylgrim-plan",
                   extra_checks=[
                       {"assertion": "out_of_scope_present", "status": "pass",
                        "evidence": "ok"}]),
         "wall_time_s": 400.0},
        {**_record(run_id="plan-b--cooperative--sonnet--r1", model="sonnet",
                   skill="pylgrim-plan"),
         "wall_time_s": 600.0},
    ]
    text = skill_report.build_report(runs, [], 1)
    h4 = text.split("## H4 bars")[1].split("## Failures")[0]
    assert "| sonnet | spec-v0 validity | 1/2 (50%) | >= 95% | **below bar** |" in h4
    assert "| sonnet | out_of_scope present on work items | 1/1 (100%) | >= 100% | meets |" in h4
    assert "| sonnet | map charter entries <= 15 | 1/1 (100%) | >= 100% | meets |" in h4
    assert "| sonnet | map evidence >= 90% resolves | 1/1 (100%) | >= 100% | meets |" in h4
    assert "| sonnet | zero network tool calls | 1/1 (100%) | >= 100% | meets |" in h4
    assert "| sonnet | plan session wall-time median | 500s | <= 600s | meets |" in h4


def test_h4_bars_wall_time_median_over_bar_flags():
    runs = [{**_record(run_id="plan-a--cooperative--haiku--r1",
                       skill="pylgrim-plan"), "wall_time_s": 700.0}]
    text = skill_report.build_report(runs, [], 1)
    h4 = text.split("## H4 bars")[1].split("## Failures")[0]
    assert "| haiku | plan session wall-time median | 700s | <= 600s | **below bar** |" in h4
    # Map-only bars have nothing to score on a plan-only tier.
    assert "| haiku | map charter entries <= 15 | no scored runs | >= 100% | n/a |" in h4


def test_next_report_number(tmp_path):
    reports = tmp_path / "reports"
    assert skill_report.next_report_number(reports) == 1
    reports.mkdir()
    (reports / "skills-stress-1.md").write_text("x", encoding="utf-8")
    (reports / "skills-stress-7.md").write_text("x", encoding="utf-8")
    assert skill_report.next_report_number(reports) == 8
