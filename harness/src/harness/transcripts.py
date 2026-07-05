"""Claude Code session transcript (JSONL) parsing.

Transcripts are the token-accounting ground truth for the experiment. Claude
Code writes one JSONL file per session under ~/.claude/projects/<munged-cwd>/,
where the munged dir name is the workspace cwd with every non-alphanumeric
character replaced by a dash (verified empirically against Claude Code 2.1.175:
C:\\Users\\samue\\AppData\\Local\\Temp\\pylgrim-smoke became
C--Users-samue-AppData-Local-Temp-pylgrim-smoke).

Event lines carry a top-level "type". The ones we consume:
  assistant  message.usage has input/output/cache token counts, message.model
             names the model, message.content holds tool_use blocks.
  user       message.content may hold tool_result blocks.
Both carry an ISO "timestamp" used for wall-time.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


def iter_events(path: Path | str) -> Iterator[dict[str, Any]]:
    """Yield parsed JSONL events, skipping malformed lines."""
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


_PATH_INPUT_KEYS = ("file_path", "path", "notebook_path")


def summarize(events: Iterator[dict[str, Any]] | list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a transcript into token totals, tool-call counts, and wall time.

    Returns:
      tokens_by_model: {model: {input_tokens, output_tokens,
                                cache_read_input_tokens, cache_creation_input_tokens}}
      tool_counts:     {tool_name: count}
      tool_file_paths: [{"tool": name, "path": p, "uuid": event uuid}]
                       (raw material for drift-attributed token estimates later)
      num_assistant_messages, wall_time_s
    """
    tokens_by_model: dict[str, dict[str, int]] = {}
    tool_counts: dict[str, int] = {}
    tool_file_paths: list[dict[str, str]] = []
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    num_assistant = 0

    for event in events:
        ts = _parse_ts(event.get("timestamp"))
        if ts is not None:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        num_assistant += 1

        model = message.get("model") or "unknown"
        usage = message.get("usage") or {}
        bucket = tokens_by_model.setdefault(
            model,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        )
        for key in bucket:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                bucket[key] += int(value)

        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name") or "unknown"
            tool_counts[name] = tool_counts.get(name, 0) + 1
            tool_input = block.get("input") or {}
            for key in _PATH_INPUT_KEYS:
                path = tool_input.get(key)
                if isinstance(path, str):
                    tool_file_paths.append(
                        {"tool": name, "path": path, "uuid": event.get("uuid", "")}
                    )
                    break

    wall_time_s = 0.0
    if first_ts is not None and last_ts is not None:
        wall_time_s = max(0.0, (last_ts - first_ts).total_seconds())

    return {
        "tokens_by_model": tokens_by_model,
        "tool_counts": tool_counts,
        "tool_file_paths": tool_file_paths,
        "num_assistant_messages": num_assistant,
        "wall_time_s": wall_time_s,
    }


def summarize_file(path: Path | str) -> dict[str, Any]:
    return summarize(iter_events(path))
