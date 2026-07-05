"""Execute one claimed run end to end.

Pipeline: prepare workspace at the pinned SHA, render the arm, invoke
headless Claude Code (`claude -p`) with a scrubbed environment, parse the
result JSON, copy the session transcript out of ~/.claude/projects/ before
anything can touch it, run the outcome test command, capture the diff
artifacts, compute metrics, and write results/runs/<run_id>/result.json.

Verified against Claude Code 2.1.175:
  claude -p "<prompt>" --output-format json --model <alias>
         --dangerously-skip-permissions
  Result JSON keys: type, subtype, is_error, duration_ms, duration_api_ms,
  num_turns, result, session_id, total_cost_usd, usage, modelUsage,
  permission_denials, terminal_reason, uuid.
  Transcript: ~/.claude/projects/<munged-cwd>/<session_id>.jsonl where the
  munged dir is the cwd with every non-alphanumeric character replaced by
  a dash (e.g. C:\\Dev\\x -> C--Dev-x).

Rate limits are the normal operating condition on a subscription: a nonzero
exit or an error mentioning rate/usage limits sends the run back to pending
with resume_after set, and the batch loop exits cleanly.
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

from harness import arms, workspace
from harness import transcripts as transcripts_mod
from harness.metrics import honeypots as honeypots_metric
from harness.metrics import scope as scope_metric
from harness.metrics import tests_outcome as tests_metric
from harness.metrics import tokens as tokens_metric
from harness.metrics import violations as violations_metric
from harness.taskcards import TaskCard

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


def build_command(prompt: str, model: str) -> list[str]:
    claude = shutil.which("claude")
    if claude is None:
        raise RuntimeError("claude CLI not found on PATH")
    return [
        claude,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--dangerously-skip-permissions",
    ]


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
) -> dict[str, Any]:
    """Run headless Claude Code. Returns the parsed result JSON.

    Raises RateLimited on rate/usage-limit failures, RuntimeError otherwise.
    """
    cmd = build_command(prompt, model)
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


def execute_run(
    run_row: dict[str, Any],
    task: TaskCard,
    repo_url: str,
    results_dir: Path | str,
    slot: int,
    preserve: tuple[str, ...] = ("node_modules", ".venv", "target"),
    timeout_s: int = DEFAULT_TIMEOUT_S,
    outcome_timeout_s: int = 600,
) -> dict[str, Any]:
    """Execute one claimed run. Returns the result record written to disk.

    Raises RateLimited (caller returns the run to pending) or RuntimeError
    (caller marks it error). Workspace capture/reset happens even when the
    outcome test fails, never when the CLI invocation itself failed.
    """
    results_dir = Path(results_dir)
    run_dir = results_dir / "runs" / run_row["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)

    slot_dir = workspace.prepare(
        results_dir, slot, run_row["repo"], repo_url, task.base_sha, preserve
    )
    prompt = arms.render(run_row["arm"], task, slot_dir)

    cli_result = invoke_claude(prompt, run_row["model"], slot_dir, timeout_s)
    session_id = cli_result.get("session_id", "")

    transcript_dest = None
    transcript_src = find_transcript(slot_dir, session_id) if session_id else None
    if transcript_src is not None:
        transcript_dest = run_dir / "transcript.jsonl"
        shutil.copy2(transcript_src, transcript_dest)

    outcome = None
    if task.test_command or task.deterministic_checks:
        outcome = tests_metric.compute(
            task.test_command, slot_dir, task.deterministic_checks, outcome_timeout_s
        )

    artifacts = workspace.capture_and_reset(slot_dir, run_dir, preserve)
    name_only = [l for l in artifacts["name_only"].splitlines() if l.strip()]
    untracked = [l for l in artifacts["untracked"].splitlines() if l.strip()]

    metrics: dict[str, Any] = {
        "scope": scope_metric.compute(artifacts["diff"], name_only, untracked, task),
        "honeypots": honeypots_metric.compute(name_only, untracked, task),
        "violations": violations_metric.evaluate(
            task.rules, artifacts["diff"], name_only, untracked
        ),
        "outcome": outcome,
    }
    if transcript_dest is not None:
        metrics["tokens"] = tokens_metric.compute(
            transcripts_mod.summarize_file(transcript_dest), cli_result
        )

    record = {
        "run": {**run_row, "session_id": session_id,
                "transcript_path": str(transcript_dest) if transcript_dest else None},
        "cli_result": cli_result,
        "metrics": metrics,
    }
    (run_dir / "result.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    return record
