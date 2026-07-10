"""Drift-attributed token estimate: turn dedup, write-tool attribution,
scope classification, and extract/runner parity.

Event shapes mirror real Claude Code transcripts: one JSONL assistant event
per content block, all blocks of one API message sharing message.id and an
identical usage dict.
"""

from harness.metrics import drift_tokens

ROOT = "C:\\work\\slot0"

USAGE = {
    "input_tokens": 10,
    "output_tokens": 100,
    "cache_read_input_tokens": 1000,
    "cache_creation_input_tokens": 5,
}


def ev(msg_id, block, usage=USAGE, cwd=ROOT, request_id=None, uuid="u1"):
    message = {"id": msg_id, "usage": dict(usage), "content": [block]}
    if msg_id is None:
        del message["id"]
    return {
        "type": "assistant",
        "message": message,
        "cwd": cwd,
        "requestId": request_id,
        "uuid": uuid,
    }


def tool(name, **input_kwargs):
    return {"type": "tool_use", "name": name, "input": input_kwargs}


def text_block():
    return {"type": "text", "text": "thinking about it"}


def test_usage_deduped_per_message_id(good_task):
    events = [
        ev("m1", text_block()),
        ev("m1", tool("Read", file_path=ROOT + "\\src\\app\\feature.py")),
        ev("m1", tool("Edit", file_path=ROOT + "\\src\\app\\legacy_util.py")),
    ]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["total_turns"] == 1
    assert result["attributed_turns"] == 1
    assert result["attributed_output_tokens"] == 100
    assert result["attributed_input_tokens"] == 10
    assert result["attributed_cache_read_tokens"] == 1000
    assert result["attributed_cache_creation_tokens"] == 5


def test_out_of_scope_edit_attributed(good_task):
    events = [ev("m1", tool("Edit", file_path=ROOT + "\\README.md"))]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 1
    assert result["out_of_scope_write_touches"] == [
        {"tool": "Edit", "path": "README.md", "turn": "m1"}
    ]


def test_all_in_scope_writes_not_attributed(good_task):
    events = [
        ev("m1", tool("Edit", file_path=ROOT + "\\src\\app\\feature.py")),
        ev("m2", tool("Write", file_path=ROOT + "\\src\\app\\helper.py")),
    ]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 0
    assert result["attributed_output_tokens"] == 0
    assert result["in_scope_write_touches"] == 2
    assert result["out_of_scope_write_touches"] == []
    assert result["total_turns"] == 2


def test_bash_never_attributed(good_task):
    events = [ev("m1", tool("Bash", command="rm -rf docs && echo done"))]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 0
    assert result["unattributed_tool_calls"] == {"Bash": 1}


def test_mixed_turn_counted_once(good_task):
    events = [
        ev("m1", tool("Edit", file_path=ROOT + "\\src\\app\\feature.py")),
        ev("m1", tool("Write", file_path=ROOT + "\\src\\app\\legacy_new.py")),
        ev("m1", tool("Write", file_path=ROOT + "\\README.md")),
    ]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 1
    assert result["attributed_output_tokens"] == 100
    assert result["in_scope_write_touches"] == 1
    assert len(result["out_of_scope_write_touches"]) == 2


def test_windows_path_relativized_case_insensitive(good_task):
    events = [ev("m1", tool("Edit", file_path="c:\\WORK\\Slot0/src/app/feature.py"))]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 0
    assert result["in_scope_write_touches"] == 1


def test_write_outside_workspace_attributed(good_task):
    events = [ev("m1", tool("Write", file_path="C:\\elsewhere\\notes.md"))]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 1
    assert result["outside_workspace_touches"] == ["C:/elsewhere/notes.md"]


def test_notebook_edit_uses_notebook_path(good_task):
    events = [ev("m1", tool("NotebookEdit", notebook_path=ROOT + "\\analysis.ipynb"))]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 1
    assert result["out_of_scope_write_touches"][0]["path"] == "analysis.ipynb"


def test_root_derived_from_cwd_matches_explicit(good_task):
    events = [
        ev("m1", tool("Edit", file_path=ROOT + "\\src\\app\\legacy_util.py")),
        ev("m2", tool("Edit", file_path=ROOT + "\\src\\app\\feature.py")),
    ]
    explicit = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    derived = drift_tokens.compute(events, good_task, workspace_root=None)
    assert derived == explicit
    assert derived["attributed_turns"] == 1


def test_missing_message_id_falls_back_to_request_id(good_task):
    events = [
        ev(None, tool("Edit", file_path=ROOT + "\\README.md"), request_id="req1"),
        ev(None, text_block(), request_id="req1"),
    ]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["total_turns"] == 1
    assert result["attributed_turns"] == 1
    assert result["out_of_scope_write_touches"][0]["turn"] == "req1"


def test_empty_events(good_task):
    result = drift_tokens.compute([], good_task, workspace_root=None)
    assert result["basis"] == "write-tools-only"
    assert result["total_turns"] == 0
    assert result["attributed_turns"] == 0
    assert result["attributed_output_tokens"] == 0
    assert "lower-bound" in result["note"]


def test_relative_tool_path_treated_repo_relative(good_task):
    events = [ev("m1", tool("Edit", file_path="src/app/legacy_util.py"))]
    result = drift_tokens.compute(events, good_task, workspace_root=ROOT)
    assert result["attributed_turns"] == 1
    assert result["out_of_scope_write_touches"][0]["path"] == "src/app/legacy_util.py"


def test_relativize():
    assert drift_tokens.relativize("C:\\a\\b\\c.py", "C:/a/b") == ("c.py", True)
    assert drift_tokens.relativize("C:/A/B/x/y.py", "c:\\a\\b") == ("x/y.py", True)
    assert drift_tokens.relativize("C:/other/c.py", "C:/a/b") == (None, False)
    assert drift_tokens.relativize("rel/path.py", "C:/a/b") == ("rel/path.py", True)
    # prefix that is not a path boundary must not match
    assert drift_tokens.relativize("C:/a/bb/c.py", "C:/a/b") == (None, False)
