"""Trigger detection, triggers.yaml integrity, and scoring."""

from pathlib import Path

from harness import trigger_check

TRIGGERS_YAML = Path(__file__).parent.parent.parent / "tasks" / "skills" / "triggers.yaml"


def _skill_event(skill):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": skill, "args": ""}}]}}


def test_detect_activation_positive_and_negative():
    events = [_skill_event("pylgrim-map")]
    assert trigger_check.detect_activation(events, "pylgrim-map")
    assert not trigger_check.detect_activation(events, "pylgrim-plan")
    assert not trigger_check.detect_activation([], "pylgrim-map")


def test_non_skill_tools_do_not_count():
    events = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "SKILL.md"}}]}}]
    assert trigger_check.activated_skills(events) == []


def test_activated_skills_collects_unique_in_order():
    events = [_skill_event("pylgrim-plan"), _skill_event("pylgrim-decide"),
              _skill_event("pylgrim-plan")]
    assert trigger_check.activated_skills(events) == ["pylgrim-plan", "pylgrim-decide"]


def test_committed_triggers_load_36_balanced():
    probes, errors = trigger_check.load_triggers(TRIGGERS_YAML)
    assert errors == []
    assert len(probes) == 36
    for skill in trigger_check.PYLGRIM_SKILLS:
        should = [p for p in probes if p.skill == skill and p.expect == "should"]
        should_not = [p for p in probes if p.skill == skill and p.expect == "should_not"]
        assert len(should) == 6 and len(should_not) == 6
    # A couple of verbatim spot checks.
    by_id = {p.id: p.prompt for p in probes}
    assert by_id["plan-should-01"] == "pylgrim plan: add rate limiting to the API"
    assert by_id["map-shouldnot-02"] == "Generate a sitemap"
    assert by_id["decide-should-06"] == \
        "Note the why on dropping the queue idea, then keep going"


def test_load_triggers_flags_bad_entries(tmp_path):
    bad = tmp_path / "triggers.yaml"
    bad.write_text(
        "prompts:\n"
        "  - { id: x-01, skill: pylgrim-nope, expect: should, prompt: hi }\n"
        "  - { id: x-02, skill: pylgrim-map, expect: maybe, prompt: hi }\n",
        encoding="utf-8",
    )
    probes, errors = trigger_check.load_triggers(bad)
    assert probes == []
    assert len(errors) == 2


def test_score_hit_and_false_fire():
    results = [
        {"probe": {"skill": "pylgrim-map", "expect": "should"}, "target_fired": True},
        {"probe": {"skill": "pylgrim-map", "expect": "should"}, "target_fired": False},
        {"probe": {"skill": "pylgrim-map", "expect": "should_not"}, "target_fired": True},
        {"probe": {"skill": "pylgrim-map", "expect": "should_not"}, "target_fired": False},
    ]
    stats = trigger_check.score(results)["pylgrim-map"]
    assert stats == {"should_total": 2, "should_hit": 1,
                     "should_not_total": 2, "false_fires": 1}
