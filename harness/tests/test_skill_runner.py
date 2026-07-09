"""Turn-artifact hygiene: a requeued run reuses its run_dir, so a previous
attempt's turn files must never leak into a new attempt or into retroactive
rescoring (the live miss: reality-tag validation reruns scored against a
stale final table left by the pre-requeue sweep run)."""

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
