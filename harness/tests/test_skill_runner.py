"""Turn-artifact hygiene: a requeued run reuses its run_dir, so a previous
attempt's turn files must never leak into a new attempt or into retroactive
rescoring (the live miss: reality-tag validation reruns scored against a
stale final table left by the pre-requeue sweep run).

Plus corpus-repo materialization (WI-E06): a scenario whose fixture names a
corpus repo gets a plain pinned working copy exported from the shared
bare-clone cache, .git included, dependencies never installed."""

import subprocess

import pytest

from harness import skill_runner as sr


def _plant_attempt(run_dir, turns):
    run_dir.mkdir(parents=True, exist_ok=True)
    for turn in range(1, turns + 1):
        (run_dir / f"turn-{turn:02d}.transcript.jsonl").write_text(
            "{}", encoding="utf-8")
        (run_dir / f"turn-{turn:02d}.result.json").write_text(
            '{"result": "turn %d"}' % turn, encoding="utf-8")


def test_purge_turn_artifacts_removes_previous_attempt(tmp_path):
    run_dir = tmp_path / "map-x-t01--cooperative--sonnet--r1"
    _plant_attempt(run_dir, 4)
    (run_dir / "result.json").write_text("{}", encoding="utf-8")
    (run_dir / "before").mkdir()

    removed = sr.purge_turn_artifacts(run_dir)

    assert removed == 8
    assert not list(run_dir.glob("turn-*"))
    # Non-turn artifacts survive: result.json is rewritten, snapshots rebuilt.
    assert (run_dir / "result.json").exists()
    assert (run_dir / "before").is_dir()


def test_purge_turn_artifacts_on_a_fresh_dir_is_a_no_op(tmp_path):
    run_dir = tmp_path / "fresh"
    run_dir.mkdir()
    assert sr.purge_turn_artifacts(run_dir) == 0


def test_turn_artifacts_ignores_stale_higher_numbered_files(tmp_path):
    run_dir = tmp_path / "requeued"
    _plant_attempt(run_dir, 4)  # old attempt reached turn 4
    # New attempt finished in 2 turns; record["turns"] says 2.
    transcripts, results = sr.turn_artifacts(run_dir, 2)
    assert [p.name for p in transcripts] == [
        "turn-01.transcript.jsonl", "turn-02.transcript.jsonl"]
    assert [p.name for p in results] == [
        "turn-01.result.json", "turn-02.result.json"]


def test_turn_artifacts_tolerates_missing_files(tmp_path):
    run_dir = tmp_path / "gappy"
    run_dir.mkdir()
    (run_dir / "turn-02.transcript.jsonl").write_text("{}", encoding="utf-8")
    transcripts, results = sr.turn_artifacts(run_dir, 3)
    assert [p.name for p in transcripts] == ["turn-02.transcript.jsonl"]
    assert results == []


# ---------------------------------------------------------------------------
# Corpus-repo materialization (WI-E06 real-repo fixtures)
# ---------------------------------------------------------------------------

def _git(*args, cwd):
    result = subprocess.run(["git", "-c", "commit.gpgsign=false", *args],
                            cwd=str(cwd), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture()
def fake_corpus_repo(tmp_path):
    """A tiny local 'upstream' repo with two commits; returns (cfg, pinned_sha,
    head_sha) where pinned_sha is the FIRST commit, so a correct
    materialization checks out the pin, not HEAD."""
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git("init", "-q", cwd=upstream)
    _git("config", "user.name", "t", cwd=upstream)
    _git("config", "user.email", "t@t.invalid", cwd=upstream)
    (upstream / "README.md").write_text("# fake corpus repo\n", encoding="utf-8")
    (upstream / "src").mkdir()
    (upstream / "src" / "lib.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git("add", "-A", cwd=upstream)
    _git("commit", "-q", "-m", "initial commit", cwd=upstream)
    pinned = _git("rev-parse", "HEAD", cwd=upstream)
    (upstream / "src" / "lib.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git("add", "-A", cwd=upstream)
    _git("commit", "-q", "-m", "post-pin drift", cwd=upstream)
    head = _git("rev-parse", "HEAD", cwd=upstream)
    cfg = {"name": "fake", "url": str(upstream), "pinned_sha": pinned}
    return cfg, pinned, head


def test_prepare_workspace_materializes_corpus_repo(tmp_path, fake_corpus_repo):
    cfg, pinned, head = fake_corpus_repo
    results_dir = tmp_path / "results"
    workspace = results_dir / "zoo-runs" / "run-x" / "workspace"

    sr.prepare_workspace("fake", results_dir / "zoo", workspace,
                         corpus_repos={"fake": cfg}, results_dir=results_dir)

    # Plain working copy at the pinned SHA, .git INCLUDED for git-facts.
    assert (workspace / "README.md").exists()
    assert (workspace / ".git").exists()
    assert (workspace / "src" / "lib.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert _git("rev-parse", "HEAD", cwd=workspace) == pinned != head
    assert _git("log", "--oneline", cwd=workspace)  # history intact
    # Bare-clone cache shared with workspace.py's layout.
    assert (results_dir / "repos" / "fake.git").is_dir()


def test_prepare_workspace_reuses_bare_clone_cache(tmp_path, fake_corpus_repo):
    cfg, pinned, _ = fake_corpus_repo
    results_dir = tmp_path / "results"
    ws1 = results_dir / "zoo-runs" / "run-1" / "workspace"
    ws2 = results_dir / "zoo-runs" / "run-2" / "workspace"
    sr.prepare_workspace("fake", results_dir / "zoo", ws1,
                         corpus_repos={"fake": cfg}, results_dir=results_dir)
    # Second run must materialize from the existing cache even when the
    # upstream is gone (proves no re-clone from the URL).
    cfg_no_upstream = {**cfg, "url": str(tmp_path / "gone")}
    sr.prepare_workspace("fake", results_dir / "zoo", ws2,
                         corpus_repos={"fake": cfg_no_upstream},
                         results_dir=results_dir)
    assert _git("rev-parse", "HEAD", cwd=ws2) == pinned


def test_prepare_workspace_corpus_replaces_stale_workspace(tmp_path, fake_corpus_repo):
    cfg, pinned, _ = fake_corpus_repo
    results_dir = tmp_path / "results"
    workspace = results_dir / "zoo-runs" / "run-x" / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "stale.txt").write_text("leftover", encoding="utf-8")
    sr.prepare_workspace("fake", results_dir / "zoo", workspace,
                         corpus_repos={"fake": cfg}, results_dir=results_dir)
    assert not (workspace / "stale.txt").exists()
    assert _git("rev-parse", "HEAD", cwd=workspace) == pinned


def test_prepare_workspace_corpus_requires_results_dir(tmp_path, fake_corpus_repo):
    cfg, _, _ = fake_corpus_repo
    with pytest.raises(RuntimeError, match="results_dir"):
        sr.prepare_workspace("fake", tmp_path / "zoo",
                             tmp_path / "ws", corpus_repos={"fake": cfg})


def test_prepare_workspace_zoo_fixture_still_wins_without_corpus(tmp_path):
    # A zoo fixture keeps working unchanged when no corpus mapping is given.
    zoo = tmp_path / "zoo"
    (zoo / "rich-clean").mkdir(parents=True)
    (zoo / "rich-clean" / "CLAUDE.md").write_text("# fixture\n", encoding="utf-8")
    workspace = tmp_path / "ws"
    sr.prepare_workspace("rich-clean", zoo, workspace)
    assert (workspace / "CLAUDE.md").read_text(encoding="utf-8") == "# fixture\n"
