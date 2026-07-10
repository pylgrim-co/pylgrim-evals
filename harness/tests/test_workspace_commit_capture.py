"""Committed-drift capture: agents that git-commit their changes must not
blind the diff-based instruments (observed live on a haiku positive control)."""

import subprocess
from pathlib import Path

import pytest

from harness import workspace


def _git(*args, cwd):
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path):
    """A tiny worktree-like repo with one base commit."""
    r = tmp_path / "repo"
    r.mkdir()
    _git("init", cwd=r)
    _git("config", "user.email", "t@t", cwd=r)
    _git("config", "user.name", "t", cwd=r)
    (r / "a.txt").write_text("base\n", encoding="utf-8")
    _git("add", ".", cwd=r)
    _git("commit", "-m", "base", cwd=r)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(r), capture_output=True, text=True
    ).stdout.strip()
    return r, sha


def test_committed_changes_visible_with_base_sha(repo, tmp_path):
    r, base = repo
    (r / "a.txt").write_text("drift\n", encoding="utf-8")
    (r / "sneaky.txt").write_text("new\n", encoding="utf-8")
    _git("add", ".", cwd=r)
    _git("commit", "-m", "agent commits its drift", cwd=r)

    out = tmp_path / "run"
    artifacts = workspace.capture_and_reset(r, out, preserve=(), base_sha=base)
    assert artifacts["agent_committed"] == "true"
    assert "drift" in artifacts["diff"]
    assert "sneaky.txt" in artifacts["name_only"]
    # worktree is back at base
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(r), capture_output=True, text=True
    ).stdout.strip()
    assert head == base
    assert (r / "a.txt").read_text(encoding="utf-8") == "base\n"
    assert not (r / "sneaky.txt").exists()


def test_uncommitted_changes_with_base_sha(repo, tmp_path):
    r, base = repo
    (r / "a.txt").write_text("uncommitted\n", encoding="utf-8")
    out = tmp_path / "run"
    artifacts = workspace.capture_and_reset(r, out, preserve=(), base_sha=base)
    assert artifacts["agent_committed"] == "false"
    assert "uncommitted" in artifacts["diff"]


def test_legacy_no_base_sha_unchanged(repo, tmp_path):
    r, _ = repo
    (r / "a.txt").write_text("wt-change\n", encoding="utf-8")
    out = tmp_path / "run"
    artifacts = workspace.capture_and_reset(r, out, preserve=())
    assert artifacts["agent_committed"] == "false"
    assert "wt-change" in artifacts["diff"]
