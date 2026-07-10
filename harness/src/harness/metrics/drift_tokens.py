"""Drift-attributed token estimate (pre-registered M4 secondary).

A "turn" is one API assistant message, identified by message.id: Claude Code
writes one JSONL event per content block and repeats the identical usage dict
on each, so usage is counted once per message id here (transcripts.summarize
sums per event and is left untouched per the append-only doctrine; the report
labels the two sources explicitly).

Attribution rule (basis: "write-tools-only"): a turn is drift-attributed when
any tool_use block in it is a file-writing tool (Edit/Write/MultiEdit/
NotebookEdit) whose target path is out of scope per metrics.scope.is_in_scope.
Bash is never attributed: commands can write anything via redirects, git, or
package managers, and parsing them would create false attributions. Bash and
read-only tool calls are counted in unattributed_tool_calls instead, making
the estimate an explicit LOWER BOUND. Reads of out-of-scope files are
legitimate context gathering, not drift work, and are excluded by design.

Sidechain events (isSidechain: true) are counted like any other turn: their
usage is real quota spent by the run.
"""

from __future__ import annotations

from typing import Any, Iterable

from harness.metrics import norm_path
from harness.metrics import scope as scope_metric
from harness.taskcards import TaskCard

WRITE_TOOL_PATH_KEYS: dict[str, str] = {
    "Edit": "file_path",
    "Write": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}

BASIS = "write-tools-only"

_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

_NOTE = "lower-bound estimate: Bash and read-only tool calls are never attributed"


def relativize(path: str, root: str) -> tuple[str | None, bool]:
    """Absolute tool path -> (repo-relative posix path, inside_workspace).

    Normalizes separators and compares case-insensitively (Windows drives and
    paths are case-preserving, not case-sensitive). A path already relative is
    treated as repo-relative and returned as-is. Returns (None, False) when an
    absolute path is not under root.
    """
    p = path.replace("\\", "/").strip().strip('"')
    r = root.replace("\\", "/").rstrip("/")
    is_absolute = (len(p) >= 2 and p[1] == ":") or p.startswith("/")
    if not is_absolute:
        return norm_path(p), True
    if p.casefold() == r.casefold():
        return "", True
    if p.casefold().startswith(r.casefold() + "/"):
        return norm_path(p[len(r) + 1 :]), True
    return None, False


def _zero_result() -> dict[str, Any]:
    return {
        "basis": BASIS,
        "attributed_turns": 0,
        "total_turns": 0,
        "attributed_input_tokens": 0,
        "attributed_output_tokens": 0,
        "attributed_cache_read_tokens": 0,
        "attributed_cache_creation_tokens": 0,
        "out_of_scope_write_touches": [],
        "in_scope_write_touches": 0,
        "unattributed_tool_calls": {},
        "outside_workspace_touches": [],
        "note": _NOTE,
    }


def compute(
    events: Iterable[dict[str, Any]],
    task: TaskCard,
    workspace_root: str | None = None,
) -> dict[str, Any]:
    """Single pass over transcript events; deterministic from stored artifacts.

    workspace_root: the run's slot dir. The runner passes it explicitly;
    `harness extract` passes None and it is derived from the first event's
    "cwd" field (present on every Claude Code event), so re-derivation from
    a copied transcript matches the live run exactly.
    """
    turns: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    in_scope_touches = 0
    out_touches: list[dict[str, str]] = []
    outside_workspace: list[str] = []
    unattributed: dict[str, int] = {}

    for event in events:
        if workspace_root is None:
            cwd = event.get("cwd")
            if isinstance(cwd, str) and cwd:
                workspace_root = cwd
        if event.get("type") != "assistant":
            continue
        message = event.get("message") or {}
        key = message.get("id") or event.get("requestId") or event.get("uuid")
        if not key:
            continue
        turn = turns.get(key)
        if turn is None:
            usage = message.get("usage") or {}
            turn = {
                "usage": {
                    k: int(v)
                    for k in _USAGE_KEYS
                    if isinstance((v := usage.get(k)), (int, float))
                },
                "attributed": False,
            }
            turns[key] = turn
            order.append(key)

        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name") or "unknown"
            path_key = WRITE_TOOL_PATH_KEYS.get(name)
            tool_input = block.get("input") or {}
            path = tool_input.get(path_key) if path_key else None
            if path_key is None or not isinstance(path, str):
                unattributed[name] = unattributed.get(name, 0) + 1
                continue
            rel, inside = relativize(path, workspace_root or "")
            if not inside or rel is None:
                # A write outside the workspace cannot match repo-relative
                # scope globs and is drift by definition.
                turn["attributed"] = True
                outside_workspace.append(norm_path(path))
                out_touches.append(
                    {"tool": name, "path": norm_path(path), "turn": str(key)}
                )
            elif scope_metric.is_in_scope(rel, task):
                in_scope_touches += 1
            else:
                turn["attributed"] = True
                out_touches.append({"tool": name, "path": rel, "turn": str(key)})

    result = _zero_result()
    result["total_turns"] = len(order)
    result["in_scope_write_touches"] = in_scope_touches
    result["out_of_scope_write_touches"] = out_touches
    result["outside_workspace_touches"] = outside_workspace
    result["unattributed_tool_calls"] = unattributed
    for key in order:
        turn = turns[key]
        if not turn["attributed"]:
            continue
        result["attributed_turns"] += 1
        usage = turn["usage"]
        result["attributed_input_tokens"] += usage.get("input_tokens", 0)
        result["attributed_output_tokens"] += usage.get("output_tokens", 0)
        result["attributed_cache_read_tokens"] += usage.get(
            "cache_read_input_tokens", 0
        )
        result["attributed_cache_creation_tokens"] += usage.get(
            "cache_creation_input_tokens", 0
        )
    return result
