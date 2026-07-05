"""Task outcome: does the task's own test command pass in the workspace?

Runs task.outcome.test_command (and optional deterministic_checks) inside
the workspace via the shell. Exit 0 = pass. This is the only metric that
executes anything; it runs before capture_and_reset scrubs the worktree.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

TAIL_CHARS = 4000


def run_command(command: str, workspace_dir: Path | str, timeout_s: int = 600) -> dict[str, Any]:
    """Run one shell command in the workspace. Returns exit_code/passed/output_tail."""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(workspace_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "command": command,
            "exit_code": proc.returncode,
            "passed": proc.returncode == 0,
            "output_tail": output[-TAIL_CHARS:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        output = ""
        for stream in (exc.stdout, exc.stderr):
            if isinstance(stream, bytes):
                output += stream.decode("utf-8", errors="replace")
            elif isinstance(stream, str):
                output += stream
        return {
            "command": command,
            "exit_code": None,
            "passed": False,
            "output_tail": output[-TAIL_CHARS:],
            "timed_out": True,
        }


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
