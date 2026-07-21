"""Task outcome: does the task's own test command pass in the workspace?

Runs task.outcome.test_command (and optional deterministic_checks) inside
the workspace via the shell. Exit 0 = pass. This is the only metric that
executes anything; it runs before capture_and_reset scrubs the worktree.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TAIL_CHARS = 4000


def _kill_tree(pid: int) -> None:
    """Kill a process and all descendants (grandchildren included)."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            timeout=30,
        )
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def run_command(command: str, workspace_dir: Path | str, timeout_s: int = 600) -> dict[str, Any]:
    """Run one shell command in the workspace. Returns exit_code/passed/output_tail.

    Output goes to a temp file rather than pipes. With shell=True on
    Windows, subprocess.run(capture_output=True, timeout=...) kills only
    the direct cmd.exe on timeout and then blocks forever in a second
    communicate(), because surviving grandchildren of the test suite hold
    the inherited pipe handles (observed live 2026-07-21: rich baseline
    wedged a drain worker for 65+ minutes, attempt 21). A file has no
    pipe-EOF problem, and timeout kills the whole tree via taskkill /T.
    """
    out = tempfile.NamedTemporaryFile(prefix="harness-cmd-", suffix=".out", delete=False)
    out_path = out.name
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(workspace_dir),
            stdout=out,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        try:
            exit_code: int | None = proc.wait(timeout=timeout_s)
            timed_out = False
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass  # no pipes are held, so an unreaped shell cannot block us
            exit_code = None
            timed_out = True
        out.close()
        with open(out_path, "rb") as fh:
            fh.seek(max(0, os.path.getsize(out_path) - TAIL_CHARS * 4))
            output = fh.read().decode("utf-8", errors="replace")
        return {
            "command": command,
            "exit_code": exit_code,
            "passed": exit_code == 0,
            "output_tail": output[-TAIL_CHARS:],
            "timed_out": timed_out,
        }
    finally:
        out.close()
        try:
            os.unlink(out_path)
        except OSError:
            pass  # a surviving grandchild may hold the file handle; leak the temp file rather than hang or raise


def compute(
    test_command: str,
    workspace_dir: Path | str,
    deterministic_checks: list[str] | None = None,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Run the task's test command plus deterministic checks. All must pass."""
    test = run_command(test_command, workspace_dir, timeout_s) if test_command else None
    checks = [run_command(c, workspace_dir, timeout_s) for c in (deterministic_checks or [])]
    passed = (test is None or test["passed"]) and all(c["passed"] for c in checks)
    return {"passed": passed, "test": test, "deterministic_checks": checks}
