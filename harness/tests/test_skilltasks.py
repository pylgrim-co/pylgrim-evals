"""Scenario-card loading, schedule generation, and filtered claiming."""

from pathlib import Path

import pytest

from harness import queue, skilltasks

TASKS_SKILLS = Path(__file__).parent.parent.parent / "tasks" / "skills"


def _write_card(path: Path, **overrides) -> Path:
    data = {
        "id": "map-test-t01",
        "skill": "pylgrim-map",
        "fixture": "rich-clean",
        "prompt": "Set up pylgrim.",
        "persona": "cooperative",
        "assertions": ["spec_valid"],
    }
    data.update(overrides)
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(value)}]")
        else:
            lines.append(f"{key}: {value!r}" if isinstance(value, str) else f"{key}: {value}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_load_good_card(tmp_path):
    card = _write_card(tmp_path / "map-test-t01.yaml")
    scenario, errors = skilltasks.load_scenario(card)
    assert errors == []
    assert scenario.skill == "pylgrim-map"
    assert scenario.invoke == "explicit"  # default
    assert scenario.expect_write == "always"  # default
    assert scenario.assertions[0] == "activated"  # assertion zero auto-added


def test_expect_write_loads_from_card(tmp_path):
    card = _write_card(tmp_path / "map-test-t01.yaml", expect_write="never")
    scenario, errors = skilltasks.load_scenario(card)
    assert errors == []
    assert scenario.expect_write == "never"


def test_full_prompt_explicit_vs_natural(tmp_path):
    explicit, _ = skilltasks.load_scenario(_write_card(tmp_path / "a.yaml"))
    assert explicit.full_prompt() == "Use the pylgrim-map skill: Set up pylgrim."
    natural, _ = skilltasks.load_scenario(
        _write_card(tmp_path / "b.yaml", invoke="natural"))
    assert natural.full_prompt() == "Set up pylgrim."


@pytest.mark.parametrize("field,value,fragment", [
    ("skill", "pylgrim-unknown", "unknown skill"),
    ("fixture", "nowhere", "unknown fixture"),
    ("persona", "chaotic", "unknown persona"),
    ("invoke", "psychic", "invoke must be"),
    ("assertions", ["not_a_check"], "unknown assertion"),
    ("expect_write", "sometimes", "expect_write must be"),
])
def test_load_bad_card(tmp_path, field, value, fragment):
    card = _write_card(tmp_path / "bad.yaml", **{field: value})
    scenario, errors = skilltasks.load_scenario(card)
    assert scenario is None
    assert any(fragment in e for e in errors)


def test_committed_cards_all_load():
    scenarios, errors = skilltasks.load_all(TASKS_SKILLS)
    assert errors == []
    assert len(scenarios) == 15
    skills = {s.skill for s in scenarios}
    assert skills == {"pylgrim-map", "pylgrim-plan", "pylgrim-decide"}


def test_committed_config():
    config = skilltasks.load_config(TASKS_SKILLS)
    assert config == {"tiers": ["haiku", "sonnet", "opus"], "reps": 3, "seed": 7}


def test_schedule_deterministic_and_rep_blocked(tmp_path):
    scenarios, _ = skilltasks.load_all(TASKS_SKILLS)
    rows_a = skilltasks.generate_schedule(scenarios, ["haiku", "opus"], 2, 7)
    rows_b = skilltasks.generate_schedule(scenarios, ["haiku", "opus"], 2, 7)
    assert rows_a == rows_b  # same seed, identical schedule
    assert len(rows_a) == len(scenarios) * 2 * 2
    # Rep-blocked: all rep-1 rows come before all rep-2 rows.
    reps_in_order = [r["rep"] for r in sorted(rows_a, key=lambda r: r["order_key"])]
    assert reps_in_order == sorted(reps_in_order)
    # arm carries the persona, repo the fixture.
    by_id = {s.id: s for s in scenarios}
    for row in rows_a:
        assert row["arm"] == by_id[row["task_id"]].persona
        assert row["repo"] == by_id[row["task_id"]].fixture


def test_claim_next_filtered(tmp_path):
    scenarios, _ = skilltasks.load_all(TASKS_SKILLS)
    rows = skilltasks.generate_schedule(scenarios[:3], ["haiku", "opus"], 1, 7)
    conn = queue.connect(tmp_path / "skills.db")
    queue.init_db(conn)
    queue.insert_schedule(conn, rows)

    target = scenarios[0]
    row = skilltasks.claim_next_filtered(conn, task_id=target.id, model="opus")
    assert row is not None
    assert row["task_id"] == target.id and row["model"] == "opus"
    assert row["status"] == "running"
    # Claiming the same cell again finds nothing (single rep).
    assert skilltasks.claim_next_filtered(conn, task_id=target.id, model="opus") is None
    # No filter still claims by order_key.
    assert skilltasks.claim_next_filtered(conn) is not None
