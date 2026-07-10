"""Task card validation: errors are collected, never raised."""

from harness import taskcards


def test_good_card_loads_clean(fixtures_dir):
    card, errors = taskcards.load_task_card(fixtures_dir / "task_good.yaml")
    assert errors == []
    assert card is not None
    assert card.id == "demo-t01"
    assert card.kind == "bait"
    assert card.base_sha == "0123456789abcdef0123456789abcdef01234567"
    assert card.scope_paths == ["src/app/*"]
    assert card.out_of_scope == ["src/app/legacy*"]
    assert card.honeypots[0]["path"] == "config/settings.py"
    assert [r["id"] for r in card.rules] == [
        "protected-paths",
        "no-new-deps",
        "no-ci-edits",
        "no-test-deletion",
    ]
    assert card.test_command == "exit 0"


def test_bad_card_collects_all_errors(fixtures_dir):
    card, errors = taskcards.load_task_card(fixtures_dir / "task_bad.yaml")
    joined = "\n".join(errors)
    assert "id" in joined and "string" in joined            # id is an int
    assert "kind" in joined                                  # unknown kind
    assert "base_sha" in joined                              # not 40-hex
    assert "prompt" in joined                                # missing
    assert "title" in joined                                 # missing
    assert "intent.constraints" in joined                    # not a list
    assert "scope_paths" in joined and "out_of_scope" in joined
    assert "rules[0].id" in joined                           # unknown rule
    # Card object still comes back (usable for tooling), errors flag it.
    assert card is not None


def test_validate_requires_mapping():
    assert taskcards.validate(["not", "a", "mapping"]) == ["task card must be a YAML mapping"]
    assert taskcards.validate(None) == ["task card must be a YAML mapping"]


def test_kind_real_requires_provenance():
    data = {
        "id": "x-t01",
        "kind": "real",
        "title": "t",
        "base_sha": "0" * 40,
        "prompt": "p",
        "intent": {
            "constraints": [],
            "work_item": {"criteria": [], "scope_paths": [], "out_of_scope": []},
        },
    }
    errors = taskcards.validate(data)
    assert any("issue_url" in e for e in errors)
    assert any("ground_truth_pr" in e for e in errors)

    data["source"] = {"issue_url": "https://x", "ground_truth_pr": "https://y"}
    assert taskcards.validate(data) == []


def test_kind_bait_requires_authored():
    data = {
        "id": "x-t01",
        "kind": "bait",
        "title": "t",
        "base_sha": "0" * 40,
        "prompt": "p",
        "intent": {
            "constraints": [],
            "work_item": {"criteria": [], "scope_paths": [], "out_of_scope": []},
        },
        "source": {"authored": False},
    }
    errors = taskcards.validate(data)
    assert any("authored" in e for e in errors)


def test_load_all_flags_duplicate_ids(tmp_path, fixtures_dir):
    good = (fixtures_dir / "task_good.yaml").read_text(encoding="utf-8")
    (tmp_path / "a.yaml").write_text(good, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(good, encoding="utf-8")
    (tmp_path / "corpus.yaml").write_text("repos: []\n", encoding="utf-8")

    cards, errors = taskcards.load_all(tmp_path)
    assert len(cards) == 1
    assert any("duplicate task id" in e for e in errors)


def _minimal_bait(control=None):
    data = {
        "id": "x-c01",
        "kind": "bait",
        "title": "t",
        "base_sha": "0" * 40,
        "prompt": "p",
        "intent": {
            "constraints": [],
            "work_item": {"criteria": [], "scope_paths": [], "out_of_scope": []},
        },
        "source": {"authored": True},
    }
    if control is not None:
        data["control"] = control
    return data


def test_control_true_on_bait_is_valid():
    data = _minimal_bait(control=True)
    assert taskcards.validate(data) == []
    assert taskcards.from_dict(data).control is True


def test_control_true_on_real_is_error():
    data = _minimal_bait(control=True)
    data["kind"] = "real"
    data["source"] = {"issue_url": "https://x", "ground_truth_pr": "https://y"}
    errors = taskcards.validate(data)
    assert any("control: true requires kind: bait" in e for e in errors)


def test_control_non_bool_is_error():
    errors = taskcards.validate(_minimal_bait(control="yes"))
    assert any("control must be a boolean" in e for e in errors)


def test_control_absent_defaults_false():
    data = _minimal_bait()
    assert taskcards.validate(data) == []
    assert taskcards.from_dict(data).control is False
