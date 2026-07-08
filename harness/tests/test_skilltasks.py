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
    assert len(scenarios) == 25
    skills = {s.skill for s in scenarios}
    assert skills == {"pylgrim-map", "pylgrim-plan", "pylgrim-decide"}


def test_committed_config():
    config = skilltasks.load_config(TASKS_SKILLS)
    assert config == {"tiers": ["haiku", "sonnet", "opus"], "reps": 1, "seed": 7}


def test_security_cards_pin_reps_three():
    # Poisoned, poisoned-v2, refuser, and delegated variants keep statistical
    # weight even in a 1-rep sweep by pinning reps: 3 on the card.
    by_id = {s.id: s for s in skilltasks.load_all(TASKS_SKILLS)[0]}
    for cid in ("map-poisoned2-t01", "plan-poisoned2-t01", "decide-poisoned2-t01",
                "map-refuser-t01", "plan-refuser-t01", "decide-refuser-t01",
                "map-delegated-t01", "plan-delegated-t01", "decide-refuser-t02"):
        assert by_id[cid].reps == 3, cid


def test_refuser_cards_assert_the_delegation_offer():
    # WI-014: the refuser's delegation phrases must be met with the offer of
    # a standing delegation entry; delegated cards assert the sanctioned path.
    by_id = {s.id: s for s in skilltasks.load_all(TASKS_SKILLS)[0]}
    for cid in ("map-refuser-t01", "plan-refuser-t01", "decide-refuser-t01"):
        assert "delegation_offered" in by_id[cid].assertions, cid
    for cid in ("plan-delegated-t01", "decide-refuser-t02"):
        assert "delegation_honored" in by_id[cid].assertions, cid
    for cid in ("map-delegated-t01", "plan-delegated-t01", "decide-refuser-t02"):
        assert by_id[cid].fixture == "rich-clean-delegated", cid
        assert "no_self_ratification" in by_id[cid].assertions, cid


def test_subdir_card_carries_cwd():
    by_id = {s.id: s for s in skilltasks.load_all(TASKS_SKILLS)[0]}
    assert by_id["decide-subdir-t01"].cwd == "src"


def test_schedule_deterministic_and_rep_blocked(tmp_path):
    scenarios, _ = skilltasks.load_all(TASKS_SKILLS)
    rows_a = skilltasks.generate_schedule(scenarios, ["haiku", "opus"], 2, 7)
    rows_b = skilltasks.generate_schedule(scenarios, ["haiku", "opus"], 2, 7)
    assert rows_a == rows_b  # same seed, identical schedule
    # Per-card reps: each scenario contributes effective_reps * len(models)
    # rows (its own reps override, else the config default of 2 here).
    expected = sum((s.reps or 2) for s in scenarios) * 2
    assert len(rows_a) == expected
    # Rep-blocked: all rep-1 rows come before all rep-2 rows.
    reps_in_order = [r["rep"] for r in sorted(rows_a, key=lambda r: r["order_key"])]
    assert reps_in_order == sorted(reps_in_order)
    # arm carries the persona, repo the fixture.
    by_id = {s.id: s for s in scenarios}
    for row in rows_a:
        assert row["arm"] == by_id[row["task_id"]].persona
        assert row["repo"] == by_id[row["task_id"]].fixture


def test_per_card_reps_override_extends_blocks(tmp_path):
    # A card with reps: 3 appears in rep-3 blocks; a default (reps None) card
    # under a 1-rep config appears only in rep 1. Cells absent from later
    # blocks, order_keys still contiguous per block.
    hot, _ = skilltasks.load_scenario(_write_card(tmp_path / "hot.yaml",
                                                  id="hot-t01", reps=3))
    cold, _ = skilltasks.load_scenario(_write_card(tmp_path / "cold.yaml",
                                                   id="cold-t01"))
    rows = skilltasks.generate_schedule([hot, cold], ["haiku"], 1, 7)
    by_rep: dict[int, set[str]] = {}
    for r in rows:
        by_rep.setdefault(r["rep"], set()).add(r["task_id"])
    assert by_rep[1] == {"hot-t01", "cold-t01"}
    assert by_rep[2] == {"hot-t01"}
    assert by_rep[3] == {"hot-t01"}
    assert len(rows) == 3 + 1  # hot x3 + cold x1, one model
    order_keys = sorted(r["order_key"] for r in rows)
    assert order_keys == list(range(len(rows)))


@pytest.mark.parametrize("value,fragment", [
    (0, "reps must be a positive integer"),
    (-2, "reps must be a positive integer"),
])
def test_bad_reps_rejected(tmp_path, value, fragment):
    card = _write_card(tmp_path / "bad.yaml", reps=value)
    scenario, errors = skilltasks.load_scenario(card)
    assert scenario is None
    assert any(fragment in e for e in errors)


@pytest.mark.parametrize("value", ["/abs/path", "../escape", "/etc"])
def test_bad_cwd_rejected(tmp_path, value):
    card = _write_card(tmp_path / "bad.yaml", cwd=value)
    scenario, errors = skilltasks.load_scenario(card)
    assert scenario is None
    assert any("cwd must be a relative subdirectory" in e for e in errors)


def test_good_cwd_loads(tmp_path):
    scenario, errors = skilltasks.load_scenario(
        _write_card(tmp_path / "ok.yaml", cwd="src/inner"))
    assert errors == []
    assert scenario.cwd == "src/inner"


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
