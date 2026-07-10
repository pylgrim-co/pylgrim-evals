"""Provenance block: run-time capture, caching, and honest backfill."""

import subprocess

import pytest

from harness import provenance


@pytest.fixture(autouse=True)
def clear_caches():
    provenance.claude_code_version.cache_clear()
    provenance.harness_git_sha.cache_clear()
    yield
    provenance.claude_code_version.cache_clear()
    provenance.harness_git_sha.cache_clear()


def test_build_shape(good_task):
    run_row = {"run_id": "demo-t01--vanilla--sonnet--r1", "seed": 4242}
    cli_result = {"modelUsage": {"claude-sonnet-4-6": {}, "claude-haiku-4-5": {}}}
    block = provenance.build(run_row, good_task, cli_result)
    assert set(block) == {
        "claude_code_version",
        "harness_git_sha",
        "harness_version",
        "model_snapshots",
        "schedule_seed",
        "base_sha",
        "captured_at",
    }
    assert block["model_snapshots"] == ["claude-haiku-4-5", "claude-sonnet-4-6"]
    assert block["schedule_seed"] == 4242
    assert block["base_sha"] == good_task.base_sha
    assert "backfilled" not in block


def test_claude_code_version_cached(monkeypatch):
    calls = {"n": 0}

    def fake_run(*args, **kwargs):
        calls["n"] += 1

        class R:
            stdout = "2.1.175 (Claude Code)\n"
            returncode = 0

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("shutil.which", lambda name: "C:/fake/claude.exe")
    assert provenance.claude_code_version() == "2.1.175 (Claude Code)"
    assert provenance.claude_code_version() == "2.1.175 (Claude Code)"
    assert calls["n"] == 1


def test_harness_git_sha_real_repo():
    sha = provenance.harness_git_sha()
    assert sha == "unknown" or (len(sha) == 40 and all(c in "0123456789abcdef" for c in sha))


def test_harness_git_sha_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no git")

    monkeypatch.setattr(subprocess, "run", boom)
    assert provenance.harness_git_sha() == "unknown"


def test_version_from_transcript(tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        '{"type":"user","timestamp":"2026-07-05T00:00:00Z"}\n'
        '{"type":"assistant","version":"2.1.175","message":{}}\n',
        encoding="utf-8",
    )
    assert provenance.version_from_transcript(transcript) == "2.1.175"
    assert provenance.version_from_transcript(tmp_path / "missing.jsonl") is None


def test_backfill_records_only_run_time_truths(good_task, tmp_path):
    transcript = tmp_path / "t.jsonl"
    transcript.write_text('{"type":"assistant","version":"2.0.9","message":{}}\n', encoding="utf-8")
    record = {"cli_result": {"modelUsage": {"claude-sonnet-4-6": {}}}}
    row = {"seed": 7}
    block = provenance.backfill(record, row, good_task, transcript)
    assert block["backfilled"] is True
    assert block["claude_code_version"] == "2.0.9"
    assert block["harness_git_sha"] is None
    assert block["harness_version"] is None
    assert block["model_snapshots"] == ["claude-sonnet-4-6"]
    assert block["schedule_seed"] == 7
    assert block["base_sha"] == good_task.base_sha


def test_backfill_never_overwrites_live_block(good_task):
    live = {"claude_code_version": "2.1.0", "harness_git_sha": "abc"}
    record = {"provenance": dict(live)}
    block = provenance.backfill(record, {"seed": 1}, good_task, None)
    assert block == live


def test_backfill_replaces_older_backfill(good_task):
    record = {"provenance": {"backfilled": True, "claude_code_version": None}}
    block = provenance.backfill(record, {"seed": 1}, good_task, None)
    assert block["backfilled"] is True
    assert block["claude_code_version"] is None
    assert block["base_sha"] == good_task.base_sha
