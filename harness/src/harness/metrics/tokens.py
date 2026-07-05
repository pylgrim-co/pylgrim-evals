"""Token and cost accounting per run.

Combines two sources:
  1. The session transcript (via transcripts.summarize): per-model token
     totals and tool-call counts. This is the ground truth for token waste.
  2. The `claude -p --output-format json` result record captured by the
     runner: total_cost_usd, num_turns, duration_ms, and modelUsage (the
     CLI's own per-model accounting, kept for cross-checking).
"""

from __future__ import annotations

from typing import Any


def compute(
    transcript_summary: dict[str, Any],
    runner_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge transcript token totals with the runner's captured result JSON."""
    tokens_by_model = transcript_summary.get("tokens_by_model", {})
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    for usage in tokens_by_model.values():
        for key in totals:
            totals[key] += int(usage.get(key, 0))

    result: dict[str, Any] = {
        "totals": totals,
        "tokens_by_model": tokens_by_model,
        "tool_counts": transcript_summary.get("tool_counts", {}),
        "num_assistant_messages": transcript_summary.get("num_assistant_messages", 0),
        "wall_time_s": transcript_summary.get("wall_time_s", 0.0),
    }

    if runner_result:
        result["cli"] = {
            "total_cost_usd": runner_result.get("total_cost_usd"),
            "num_turns": runner_result.get("num_turns"),
            "duration_ms": runner_result.get("duration_ms"),
            "duration_api_ms": runner_result.get("duration_api_ms"),
            "model_usage": runner_result.get("modelUsage"),
        }
    return result
