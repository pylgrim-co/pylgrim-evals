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


def test_stale_generic_renders_charter_only(tmp_path, monkeypatch):
    task = make_task()
    text = arms.render_stale_claude_md(task, "generic")
    assert "<!-- pylgrim:begin -->" in text
    assert "Never edit .github/workflows" in text
    assert "frobnicate() returns 7" not in text  # no work item at all
    assert "In scope:" not in text


def test_stale_wrong_uses_next_cards_work_item():
    """E8 rule: deterministic cyclic-next mapping within the repo."""
    by_repo = arms._all_treal_cards()
    repo, siblings = sorted(by_repo.items())[0]
    ordered = sorted(siblings, key=lambda c: c.id)
    w = arms.wrong_card_for(ordered[0], siblings)
    assert w.id == ordered[1].id
    w_last = arms.wrong_card_for(ordered[-1], siblings)
    assert w_last.id == ordered[0].id  # cyclic


def test_stale_wrong_renders_other_work_item():
    by_repo = arms._all_treal_cards()
    repo, siblings = sorted(by_repo.items())[0]
    ordered = sorted(siblings, key=lambda c: c.id)
    task, wrong = ordered[0], arms.wrong_card_for(ordered[0], siblings)
    text = arms.render_stale_claude_md(task, "wrong")
    assert "<!-- pylgrim:begin -->" in text
    # the whole block is the wrong card's: its block equals a fresh export
    # of the wrong card, and differs from the running card's own export
    assert text == arms.render_exported_claude_md(wrong)
    assert text != arms.render_exported_claude_md(task)


def test_e9_enforce_mode_renders_enforce_tag():
    task = make_task()
    text = arms.render_exported_claude_md(task, mode="enforce")
    assert "[enforce]" in text
    assert "[observe]" not in text


def test_e9_bare_strips_mode_tags_only():
    task = make_task()
    tagged = arms.render_exported_claude_md(task)
    bare = arms.render_exported_claude_md(task, strip_mode_tags=True)
    assert "[observe]" in tagged
    assert "[observe]" not in bare
    assert "[enforce]" not in bare
    # constraint text and work item survive untouched
    assert "Never edit .github/workflows" in bare
    assert "In scope:" in bare
    # the strip is the ONLY difference
    import re
    assert re.sub(r"^- \[observe\] ", "- ", tagged, flags=re.M) == bare


def _patch_vague(tmp_path, monkeypatch):
    artifact = tmp_path / "vague-prompts-v1.yaml"
    artifact.write_text(
        "alpha-t01:\n"
        "  prompt: |-\n"
        "    Frobnicator broken\n"
        "\n"
        "    It returns 6 instead of 7 on my machine.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(arms, "VAGUE_PROMPTS_PATH", artifact)
    arms._vague_prompts.cache_clear()


def test_compose_arm_registered():
    assert "compose-vague" in arms.ARMS


def test_compose_render_rejected(tmp_path):
    """The runner owns compose (model call + persistence); render must refuse."""
    with pytest.raises(ValueError, match="compose_claude_md"):
        arms.render("compose-vague", make_task(), tmp_path)


def test_ledger_artifacts_carry_full_ledger():
    text = arms.render_ledger_artifacts(make_task())
    assert "=== .pylgrim/charter/" in text
    assert "=== .pylgrim/work/" in text
    assert "Never edit .github/workflows" in text
    assert "Keep the public API stable" in text
    assert "frobnicate() returns 7" in text
    assert "src/widget.py" in text
    assert ".github/**" in text


def test_compose_prompt_carries_vague_prompt_and_ledger(tmp_path, monkeypatch):
    _patch_vague(tmp_path, monkeypatch)
    try:
        prompt = arms.compose_prompt_for(make_task())
    finally:
        arms._vague_prompts.cache_clear()
    assert "Frobnicator broken" in prompt  # the VAGUE prompt, not task.prompt
    assert "Fix the frobnicator in src/widget.py" not in prompt
    assert "=== .pylgrim/charter/" in prompt
    assert "no code fences" in prompt


def test_compose_claude_md_returns_block_and_result(tmp_path, monkeypatch):
    _patch_vague(tmp_path, monkeypatch)
    seen = {}

    def fake_invoke(prompt, model, cwd, timeout_s):
        seen.update(prompt=prompt, model=model, cwd=cwd, timeout_s=timeout_s)
        return {"result": "# Project instructions\n\n- keep API stable",
                "session_id": "sess-1", "total_cost_usd": 0.001}

    try:
        composed, cli = arms.compose_claude_md(make_task(), invoke=fake_invoke)
    finally:
        arms._vague_prompts.cache_clear()
    assert seen["model"] == arms.COMPOSE_MODEL == "haiku"
    assert seen["timeout_s"] == arms.COMPOSE_TIMEOUT_S
    assert "Frobnicator broken" in seen["prompt"]
    assert composed == "# Project instructions\n\n- keep API stable\n"
    assert cli["session_id"] == "sess-1"


def test_compose_strips_one_wrapping_fence(tmp_path, monkeypatch):
    _patch_vague(tmp_path, monkeypatch)

    def fake_invoke(prompt, model, cwd, timeout_s):
        return {"result": "```markdown\n# Block\n```", "session_id": "s"}

    try:
        composed, _ = arms.compose_claude_md(make_task(), invoke=fake_invoke)
    finally:
        arms._vague_prompts.cache_clear()
    assert composed == "# Block\n"


def test_compose_empty_result_raises(tmp_path, monkeypatch):
    """No silent fallback: an empty composition fails the run."""
    _patch_vague(tmp_path, monkeypatch)

    def fake_invoke(prompt, model, cwd, timeout_s):
        return {"result": "   \n", "session_id": "s"}

    try:
        with pytest.raises(RuntimeError, match="empty context block"):
            arms.compose_claude_md(make_task(), invoke=fake_invoke)
    finally:
        arms._vague_prompts.cache_clear()


def test_compose_requires_vague_artifact_entry(tmp_path, monkeypatch):
    """Compose is a vague-row arm: cards outside the frozen artifact refuse."""
    artifact = tmp_path / "vague-prompts-v1.yaml"
    artifact.write_text("# empty\n", encoding="utf-8")
    monkeypatch.setattr(arms, "VAGUE_PROMPTS_PATH", artifact)
    arms._vague_prompts.cache_clear()
    try:
        with pytest.raises(ValueError, match="no entry"):
            arms.compose_prompt_for(make_task())
    finally:
        arms._vague_prompts.cache_clear()


def test_e9_arm_dispatch(tmp_path):
    for arm, marker in (("export-bare-vague", None), ("export-enforce-vague", "[enforce]")):
        ws = tmp_path / arm
        ws.mkdir()
        try:
            arms.render(arm, make_task(), ws)
        except ValueError:
            pass  # vague artifact has no alpha-t01; context file written first
        text = (ws / "CLAUDE.md").read_text(encoding="utf-8")
        if marker:
            assert marker in text
        else:
            assert "[observe]" not in text and "[enforce]" not in text
