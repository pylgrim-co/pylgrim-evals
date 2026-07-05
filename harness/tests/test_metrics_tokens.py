"""Transcript parsing and token accounting against the synthetic JSONL fixture."""

from harness import transcripts
from harness.metrics import tokens


def _summary(fixtures_dir):
    return transcripts.summarize_file(fixtures_dir / "sample_transcript.jsonl")


def test_iter_events_skips_malformed_lines(fixtures_dir):
    events = list(transcripts.iter_events(fixtures_dir / "sample_transcript.jsonl"))
    # 8 lines in the file, 1 is invalid JSON.
    assert len(events) == 7


def test_token_totals_per_model(fixtures_dir):
    summary = _summary(fixtures_dir)
    usage = summary["tokens_by_model"]["claude-sonnet-4-5"]
    assert usage["input_tokens"] == 150
    assert usage["output_tokens"] == 130
    assert usage["cache_read_input_tokens"] == 1400
    assert usage["cache_creation_input_tokens"] == 300


def test_tool_counts_and_paths(fixtures_dir):
    summary = _summary(fixtures_dir)
    assert summary["tool_counts"] == {"Read": 1, "Edit": 1}
    paths = [p["path"] for p in summary["tool_file_paths"]]
    assert paths == ["src/app/feature.py", "src/app/feature.py"]
    assert summary["num_assistant_messages"] == 3


def test_wall_time(fixtures_dir):
    summary = _summary(fixtures_dir)
    assert summary["wall_time_s"] == 90.0


def test_tokens_compute_merges_cli_result(fixtures_dir):
    summary = _summary(fixtures_dir)
    cli_result = {
        "total_cost_usd": 0.0219695,
        "num_turns": 3,
        "duration_ms": 1582,
        "duration_api_ms": 1510,
        "modelUsage": {"claude-sonnet-4-5": {"inputTokens": 150}},
    }
    merged = tokens.compute(summary, cli_result)
    assert merged["totals"]["input_tokens"] == 150
    assert merged["totals"]["cache_read_input_tokens"] == 1400
    assert merged["cli"]["total_cost_usd"] == 0.0219695
    assert merged["cli"]["num_turns"] == 3
    assert merged["tool_counts"]["Edit"] == 1


def test_tokens_compute_without_cli_result(fixtures_dir):
    merged = tokens.compute(_summary(fixtures_dir))
    assert "cli" not in merged
    assert merged["totals"]["output_tokens"] == 130
