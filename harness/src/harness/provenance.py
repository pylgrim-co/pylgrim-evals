"""Per-run provenance: what produced this result, recorded at run time.

The pre-registration requires every run to record the model snapshot served,
the Claude Code version, the harness version, the schedule seed, and the
pinned repo SHA. These are facts about the RUN-TIME environment: the extract
backfill for old runs therefore records only what stored artifacts prove
(the transcript's own version field) and leaves the rest None, never
substituting the current environment for the one that ran.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from harness import __version__, queue
from harness import transcripts as transcripts_mod
from harness.taskcards import TaskCard

_HARNESS_REPO_ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def claude_code_version() -> str:
    """`claude --version`, cached: once per drain process, not per run."""
    import shutil

    exe = shutil.which("claude")
    if not exe:
        return "not-found"
    try:
        out = subprocess.run(
            [exe, "--version"], capture_output=True, text=True, timeout=60
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@lru_cache(maxsize=1)
def harness_git_sha() -> str:
    """HEAD of the harness repo itself; "unknown" on any failure (results
    directories may be exported and analyzed away from the checkout)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(_HARNESS_REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        sha = out.stdout.strip()
        return sha if out.returncode == 0 and len(sha) == 40 else "unknown"
    except Exception:
        return "unknown"


def version_from_transcript(transcript_path: Path | str) -> str | None:
    """The `version` field Claude Code stamps on every transcript event —
    run-time truth usable for backfilling runs that predate this module."""
    try:
        for event in transcripts_mod.iter_events(transcript_path):
            version = event.get("version")
            if isinstance(version, str) and version:
                return version
    except OSError:
        return None
    return None


def build(
    run_row: dict[str, Any], task: TaskCard, cli_result: dict[str, Any]
) -> dict[str, Any]:
    """Provenance block written as a top-level result.json key at run time."""
    return {
        "claude_code_version": claude_code_version(),
        "harness_git_sha": harness_git_sha(),
        "harness_version": __version__,
        "model_snapshots": sorted((cli_result.get("modelUsage") or {}).keys()),
        "schedule_seed": run_row.get("seed"),
        "base_sha": task.base_sha,
        "captured_at": queue.now_iso(),
    }


def backfill(
    record: dict[str, Any],
    run_row: dict[str, Any],
    task: TaskCard,
    transcript_path: Path | None,
) -> dict[str, Any]:
    """Provenance for a run extracted after the fact.

    A live (run-time) block is never overwritten. Otherwise only run-time
    truths are recorded: the transcript's version field and the stored
    cli_result's modelUsage; the current binary and checkout say nothing
    about the run-time state, so those fields are None, never fabricated.
    """
    existing = record.get("provenance")
    if isinstance(existing, dict) and not existing.get("backfilled"):
        return existing
    cli_result = record.get("cli_result") or {}
    version = None
    if transcript_path is not None and Path(transcript_path).exists():
        version = version_from_transcript(transcript_path)
    return {
        "backfilled": True,
        "claude_code_version": version,
        "harness_git_sha": None,
        "harness_version": None,
        "model_snapshots": sorted((cli_result.get("modelUsage") or {}).keys()),
        "schedule_seed": run_row.get("seed"),
        "base_sha": task.base_sha,
        "captured_at": queue.now_iso(),
    }
