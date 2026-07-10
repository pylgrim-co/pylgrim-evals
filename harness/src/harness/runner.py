"""Execute one claimed run end to end.

Pipeline: prepare workspace at the pinned SHA, render the arm, invoke
headless Claude Code (`claude -p`) with a scrubbed environment, parse the
result JSON, copy the session transcript out of ~/.claude/projects/ before
anything can touch it, run the outcome test command, capture the diff
artifacts, compute metrics, and write results/runs/<run_id>/result.json.

The CLI-invocation mechanics (env scrubbing, rate-limit detection, transcript
munging/copying, session resume) live in headless.py, shared with the skills
stress runner (skill_runner.py); the names below are re-exported so existing
callers of runner.* keep working unchanged.

Rate limits are the normal operating condition on a subscription: a nonzero
exit or an error mentioning rate/usage limits sends the run back to pending
with resume_after set, and the batch loop exits cleanly.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from harness import arms, provenance, workspace
from harness import transcripts as transcripts_mod
from harness.headless import (  # noqa: F401  (re-exported public surface)
    DEFAULT_TIMEOUT_S,
    RATE_LIMIT_BACKOFF,
    RateLimited,
    build_command,
    find_transcript,
    invoke_claude,
    looks_rate_limited,
    munge_cwd,
    parse_resume_after,
    scrub_env,
)
from harness.metrics import drift_tokens as drift_tokens_metric
from harness.metrics import honeypots as honeypots_metric
from harness.metrics import scope as scope_metric
from harness.metrics import tests_outcome as tests_metric
from harness.metrics import tokens as tokens_metric
from harness.metrics import violations as violations_metric
from harness.taskcards import TaskCard


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
        metrics["drift_tokens"] = drift_tokens_metric.compute(
            transcripts_mod.iter_events(transcript_dest),
            task,
            workspace_root=str(slot_dir),
        )

    record = {
        "run": {**run_row, "session_id": session_id,
                "transcript_path": str(transcript_dest) if transcript_dest else None},
        "cli_result": cli_result,
        "metrics": metrics,
        "provenance": provenance.build(run_row, task, cli_result),
    }
    (run_dir / "result.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    return record
