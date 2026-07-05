"""Shared headless Claude Code invocation helpers.

Factored out of runner.py so both the coding-task runner (runner.py) and the
skills stress runner (skill_runner.py) drive the CLI through one verified
code path: environment scrubbing, command construction (including session
resume for multi-turn scripted-user runs), rate-limit detection and backoff
parsing, and locating/copying the session transcript out of
~/.claude/projects/<munged-cwd>/ before anything can touch it.

Verified against Claude Code 2.1.175:
  claude -p "<prompt>" --output-format json --model <alias>
         --dangerously-skip-permissions [-r <session_id>]
  Result JSON keys: type, subtype, is_error, duration_ms, duration_api_ms,
  num_turns, result, session_id, total_cost_usd, usage, modelUsage,
  permission_denials, terminal_reason, uuid.
  Transcript: ~/.claude/projects/<munged-cwd>/<session_id>.jsonl where the
  munged dir is the cwd with every non-alphanumeric character replaced by
  a dash (e.g. C:\\Dev\\x -> C--Dev-x).

Only stdout is parsed as JSON; stderr can carry noise (verified live).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_S = 30 * 60
RATE_LIMIT_BACKOFF = timedelta(minutes=60)

# Env vars always kept even though they match the secret-ish drop patterns
# or are needed for claude's subscription auth and basic process operation.
_ENV_KEEP_EXACT = {
    "PATH",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "TEMP",
    "TMP",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "COMSPEC",
    "PATHEXT",
    "USERNAME",
    "PROGRAMFILES",
    "PROGRAMDATA",
}
_ENV_DROP_EXACT = {"ANTHROPIC_API_KEY"}
_ENV_DROP_SUFFIXES = ("_TOKEN", "_SECRET", "_KEY", "_SECRET_KEY", "_API_KEY")


class RateLimited(Exception):
    """The CLI hit the subscription rate/usage limit; resume after `resume_after`."""

    def __init__(self, message: str, resume_after: str) -> None:
        super().__init__(message)
        self.resume_after = resume_after


def scrub_env() -> dict[str, str]:
    """Copy os.environ minus API keys and anything that smells like a secret.

    Keeps PATH and the OS/user vars claude needs, plus all CLAUDE* vars
    (subscription auth lives in ~/.claude, not env, but CLAUDE_CONFIG_DIR
    and friends must survive).
    """
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if upper in _ENV_KEEP_EXACT or upper.startswith("CLAUDE"):
            env[key] = value
            continue
        if upper in _ENV_DROP_EXACT:
            continue
        if any(upper.endswith(suffix) for suffix in _ENV_DROP_SUFFIXES):
            continue
        env[key] = value
    return env


def build_command(prompt: str, model: str, resume_session: str | None = None) -> list[str]:
    """Assemble the headless CLI invocation; `resume_session` continues a session."""
    claude = shutil.which("claude")
    if claude is None:
        raise RuntimeError("claude CLI not found on PATH")
    cmd = [
        claude,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--dangerously-skip-permissions",
    ]
    if resume_session:
        cmd += ["-r", resume_session]
    return cmd


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the CLI and every child it spawned (agents shell out freely)."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
        )
    else:
        proc.kill()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass


def munge_cwd(cwd: Path | str) -> str:
    """Claude Code's project-dir munging: every non-alphanumeric char becomes '-'.

    Verified empirically on 2.1.175 (see module docstring).
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(cwd))


def find_transcript(cwd: Path | str, session_id: str) -> Path | None:
    """Locate the session transcript, with a glob fallback if munging drifts."""
    projects = Path.home() / ".claude" / "projects"
    candidate = projects / munge_cwd(cwd) / f"{session_id}.jsonl"
    if candidate.exists():
        return candidate
    matches = list(projects.glob(f"*/{session_id}.jsonl"))
    return matches[0] if matches else None


def copy_transcript(cwd: Path | str, session_id: str, dest: Path) -> Path | None:
    """Copy the session transcript to `dest` immediately; None when not found."""
    src = find_transcript(cwd, session_id) if session_id else None
    if src is None:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


_RATE_LIMIT_RE = re.compile(r"rate.?limit|usage.?limit|limit (reached|exceeded)", re.IGNORECASE)


def looks_rate_limited(exit_code: int, text: str) -> bool:
    """Nonzero exit + rate/usage-limit wording. Successful runs whose result
    text merely discusses rate limits are handled by the is_error JSON path."""
    return exit_code != 0 and bool(_RATE_LIMIT_RE.search(text))


def parse_resume_after(text: str, now: datetime | None = None) -> str:
    """Best-effort: pull a reset time out of the error text, else now + 60 min.

    Handles ISO-8601 timestamps and unix epoch seconds. Anything else falls
    back to the fixed backoff; the queue re-gates anyway if we come back early.
    """
    now = now or datetime.now(timezone.utc)
    iso = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?", text)
    if iso:
        try:
            ts = datetime.fromisoformat(iso.group(0).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts > now:
                return ts.isoformat(timespec="seconds")
        except ValueError:
            pass
    epoch = re.search(r"\b(1[6-9]\d{8}|2\d{9})\b", text)
    if epoch:
        ts = datetime.fromtimestamp(int(epoch.group(1)), tz=timezone.utc)
        if ts > now:
            return ts.isoformat(timespec="seconds")
    return (now + RATE_LIMIT_BACKOFF).isoformat(timespec="seconds")


def invoke_claude(
    prompt: str,
    model: str,
    workspace_dir: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    resume_session: str | None = None,
) -> dict[str, Any]:
    """Run headless Claude Code. Returns the parsed result JSON (stdout only).

    Raises RateLimited on rate/usage-limit failures, RuntimeError otherwise.
    `resume_session` continues a prior session (`claude -p -r <session_id>`).
    """
    cmd = build_command(prompt, model, resume_session)
    proc = subprocess.Popen(
        cmd,
        cwd=str(workspace_dir),
        env=scrub_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        raise RuntimeError(f"claude run timed out after {timeout_s}s")

    combined = (stdout or "") + "\n" + (stderr or "")
    if looks_rate_limited(proc.returncode, combined):
        raise RateLimited(combined.strip()[:2000], parse_resume_after(combined))
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited {proc.returncode}: {combined.strip()[:2000]}"
        )

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude produced non-JSON output: {stdout[:2000]}")
    if result.get("is_error"):
        text = json.dumps(result)
        if _RATE_LIMIT_RE.search(text):
            raise RateLimited(text[:2000], parse_resume_after(text))
        raise RuntimeError(f"claude reported error: {text[:2000]}")
    return result
