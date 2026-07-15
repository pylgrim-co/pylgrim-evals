"""Wave-1.5 arm tests: the exported channel and the vague prompt row."""

import pytest

from harness import arms
from harness.taskcards import TaskCard


def make_task(task_id="alpha-t01"):
    return TaskCard(
        id=task_id,
        kind="real",
        title="Fix the widget frobnicator",
        base_sha="a" * 40,
        prompt="Fix the frobnicator in src/widget.py. Do not touch CI.",
        constraints=["Never edit .github/workflows", "Keep the public API stable"],
        criteria=["frobnicate() returns 7", "existing tests stay green"],
        scope_paths=["src/widget.py", "tests/test_widget.py"],
        out_of_scope=[".github/**", "docs/**"],
    )


def test_arm_names_registered():
    for arm in ("vanilla", "claudemd", "export", "vanilla-vague",
                "claudemd-vague", "export-vague"):
        assert arm in arms.ARMS


def test_vanilla_renders_nothing(tmp_path):
    prompt = arms.render("vanilla", make_task(), tmp_path)
    assert prompt == make_task().prompt
    assert not (tmp_path / "CLAUDE.md").exists()


def test_claudemd_oracle_block(tmp_path):
    arms.render("claudemd", make_task(), tmp_path)
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "### In scope" in text
    assert "src/widget.py" in text


def test_export_arm_runs_real_exporter(tmp_path):
    """Golden test: the exported block is the product's managed block, with
    the In scope / Out of scope path lists the oracle format proved out."""
    prompt = arms.render("export", make_task(), tmp_path)
    assert prompt == make_task().prompt
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "<!-- pylgrim:begin -->" in text
    assert "<!-- pylgrim:end -->" in text
    assert "In scope:" in text
    assert "src/widget.py" in text
    assert "Out of scope:" in text
    assert ".github/**" in text
    # criteria render as an open checklist
    assert "- [ ]" in text
    assert "frobnicate() returns 7" in text
    # both constraints survive the round trip
    assert "Never edit .github/workflows" in text
    assert "Keep the public API stable" in text


def test_ledger_is_deterministic(tmp_path):
    a = arms.render_exported_claude_md(make_task())
    b = arms.render_exported_claude_md(make_task())
    assert a == b


def test_fake_ulid_shape_and_order():
    u0 = arms._fake_ulid("alpha-t01", 0)
    u1 = arms._fake_ulid("alpha-t01", 1)
    assert len(u0) == len(u1) == 26
    assert all(c in arms._CROCKFORD for c in u0 + u1)
    assert u0 < u1  # ordinal prefix pins export order


def test_vague_prompt_selection(tmp_path, monkeypatch):
    artifact = tmp_path / "vague-prompts-v1.yaml"
    artifact.write_text(
        "# header\n\n"
        "alpha-t01:\n"
        "  issue_url: \"https://github.com/o/r/issues/1\"\n"
        "  fetched: \"2026-07-16\"\n"
        "  sha256: \"x\"\n"
        "  prompt: |-\n"
        "    Frobnicator broken\n"
        "\n"
        "    It returns 6 instead of 7 on my machine.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(arms, "VAGUE_PROMPTS_PATH", artifact)
    arms._vague_prompts.cache_clear()
    ws = tmp_path / "ws"
    ws.mkdir()
    prompt = arms.render("vanilla-vague", make_task(), ws)
    assert prompt == "Frobnicator broken\n\nIt returns 6 instead of 7 on my machine."
    assert not (ws / "CLAUDE.md").exists()
    arms._vague_prompts.cache_clear()


def test_vague_arm_requires_artifact_entry(tmp_path, monkeypatch):
    artifact = tmp_path / "vague-prompts-v1.yaml"
    artifact.write_text("# empty\n", encoding="utf-8")
    monkeypatch.setattr(arms, "VAGUE_PROMPTS_PATH", artifact)
    arms._vague_prompts.cache_clear()
    with pytest.raises(ValueError, match="no entry"):
        arms.render("export-vague", make_task(), tmp_path)
    arms._vague_prompts.cache_clear()


def test_real_artifact_parses_and_covers_treal():
    """The frozen artifact parses and covers every short T-real card."""
    prompts = arms._vague_prompts()
    assert len(prompts) >= 48
    for cid, text in prompts.items():
        assert text.strip(), f"{cid} empty"
