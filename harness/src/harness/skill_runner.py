"""Execute one skill stress run: scripted multi-turn session over a zoo fixture.

Pipeline per run: copy the materialized zoo fixture (or make an empty repo)
into results/zoo-runs/<run_id>/workspace, install the pylgrim skills into
<workspace>/.claude/skills/ (pinned by the pylgrim-repo HEAD SHA), snapshot
the ledger surface (.pylgrim/, .pylgrimignore, CLAUDE.md) into before/, then
drive the turn loop: invoke headless Claude, copy the transcript out
immediately, detect whether the assistant is waiting on the user, answer with
the deterministic persona, resume the session. Afterwards snapshot after/,
run the skill_checks assertions, and write result.json.

Rate limits propagate as headless.RateLimited; the batch loop returns the run
to pending and a re-claim rebuilds the workspace from scratch.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from harness import headless, personas
from harness import transcripts as transcripts_mod
from harness.metrics import skill_checks
from harness.skilltasks import SkillScenario

DEFAULT_SKILLS_SOURCE = Path(r"C:\Dev\pylgrim-master\pylgrim-repo\skills")
DEFAULT_TURN_TIMEOUT_S = 20 * 60

# Snapshot surface: everything the tighten-only / never-touch-ratified /
# managed-block / consolidation contracts are stated over.
_SNAPSHOT_ITEMS = (".pylgrim", ".pylgrimignore", "redaction.toml",
                   "CLAUDE.md", "AGENTS.md")


def _rmtree(path: Path) -> None:
    """rmtree that survives Windows read-only .git objects."""

    def on_error(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onerror=on_error)


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-c", "core.excludesFile=", "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def pylgrim_repo_sha(skills_source: Path = DEFAULT_SKILLS_SOURCE) -> str:
    """HEAD SHA of the repo the skills are vendored from (per-run provenance)."""
    try:
        return _git("rev-parse", "HEAD", cwd=Path(skills_source).parent).strip()
    except (RuntimeError, OSError):
        return "unknown"


def materialize_corpus_repo(
    repo_cfg: dict[str, Any], results_dir: Path, workspace: Path
) -> None:
    """Export a plain working copy of a pinned corpus repo into `workspace`.

    Reuses workspace.py's bare-clone cache in results/repos/ (so the
    zustand/click caches from the coding-task pilot are shared), then clones
    locally and checks out the pinned SHA detached. The working copy keeps
    its .git so map's git-facts (history, CODEOWNERS-adjacent archaeology)
    work. Dependencies are never installed: map and plan read the repo, they
    do not run test suites.
    """
    from harness import workspace as workspace_mod

    name = str(repo_cfg["name"])
    url = str(repo_cfg["url"])
    sha = str(repo_cfg["pinned_sha"])
    clone = workspace_mod.ensure_bare_clone(Path(results_dir).resolve(), name, url, sha)
    _git("clone", "--no-checkout", str(clone), str(workspace), cwd=clone.parent)
    _git("checkout", "--detach", "--force", sha, cwd=workspace)
    # Local identity so any harness-side git plumbing works; the skills
    # themselves never commit (write_surface forbids it).
    _git("config", "user.name", "zoo-runner", cwd=workspace)
    _git("config", "user.email", "zoo@pylgrim-evals.invalid", cwd=workspace)


def prepare_workspace(
    fixture: str,
    zoo_dir: Path,
    workspace: Path,
    corpus_repos: dict[str, dict[str, Any]] | None = None,
    results_dir: Path | None = None,
) -> None:
    """Materialize the run workspace: zoo fixture copy, empty repo, self copy,
    or a pinned corpus-repo checkout (when `fixture` names a repo in
    tasks/corpus.yaml and corpus_repos/results_dir are provided)."""
    _rmtree(workspace)
    if corpus_repos and fixture in corpus_repos:
        if results_dir is None:
            raise RuntimeError(
                f"corpus fixture {fixture!r} needs results_dir for the bare-clone cache"
            )
        materialize_corpus_repo(corpus_repos[fixture], results_dir, workspace)
        return
    if fixture == "empty":
        workspace.mkdir(parents=True)
        _git("init", "-q", cwd=workspace)
        _git("config", "user.name", "zoo-runner", cwd=workspace)
        _git("config", "user.email", "zoo@pylgrim-evals.invalid", cwd=workspace)
        # Neutral message: never leak fixture provenance into harvestable history.
        _git("commit", "-q", "--allow-empty", "-m", "initial commit", cwd=workspace)
        return
    if fixture == "self":
        source = DEFAULT_SKILLS_SOURCE.parent
        shutil.copytree(source, workspace, ignore=shutil.ignore_patterns(".git"))
        _git("init", "-q", cwd=workspace)
        _git("config", "user.name", "zoo-runner", cwd=workspace)
        _git("config", "user.email", "zoo@pylgrim-evals.invalid", cwd=workspace)
        _git("add", "-A", cwd=workspace)
        _git("commit", "-q", "-m", "initial commit", cwd=workspace)
        return
    source = zoo_dir / fixture
    if not source.is_dir():
        raise RuntimeError(
            f"zoo fixture {fixture!r} not built at {source}; run build_zoo.py first"
        )
    shutil.copytree(source, workspace)


def install_skills(workspace: Path, skills_source: Path = DEFAULT_SKILLS_SOURCE) -> list[str]:
    """Copy the pylgrim skills into the workspace's project skill dir."""
    dest = workspace / ".claude" / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    installed = []
    for skill_dir in sorted(Path(skills_source).iterdir()):
        if skill_dir.is_dir():
            shutil.copytree(skill_dir, dest / skill_dir.name, dirs_exist_ok=True)
            installed.append(skill_dir.name)
    return installed


def purge_turn_artifacts(run_dir: Path) -> int:
    """Delete turn-* artifacts left by a previous attempt at this run_id.

    A requeued or re-claimed run reuses its run_dir; without this purge the
    old attempt's higher-numbered turn files survive alongside the new
    attempt's, and any consumer that globs turn-* scores a chimera of two
    attempts (seen live: the reality-tag validation reruns rescored against
    a stale final table). Returns the number of files removed."""
    removed = 0
    for stale in sorted(run_dir.glob("turn-*")):
        if stale.is_file():
            stale.unlink()
            removed += 1
    return removed


def turn_artifacts(run_dir: Path, num_turns: int) -> tuple[list[Path], list[Path]]:
    """(transcript_paths, result_paths) belonging to THIS attempt: turn files
    are keyed by turn number, so only turns 1..num_turns are trusted; never
    glob blindly, higher numbers may be a previous attempt's leftovers."""
    transcripts: list[Path] = []
    results: list[Path] = []
    for turn in range(1, num_turns + 1):
        transcript = run_dir / f"turn-{turn:02d}.transcript.jsonl"
        if transcript.exists():
            transcripts.append(transcript)
        result = run_dir / f"turn-{turn:02d}.result.json"
        if result.exists():
            results.append(result)
    return transcripts, results


def snapshot(workspace: Path, dest: Path) -> None:
    """Copy the ledger surface (full file copies) preserving relative layout."""
    _rmtree(dest)
    dest.mkdir(parents=True)
    for item in _SNAPSHOT_ITEMS:
        source = workspace / item
        if source.is_dir():
            shutil.copytree(source, dest / item)
        elif source.is_file():
            shutil.copy2(source, dest / item)


def execute_skill_run(
    run_row: dict[str, Any],
    scenario: SkillScenario,
    results_dir: Path | str,
    zoo_dir: Path | str | None = None,
    skills_source: Path = DEFAULT_SKILLS_SOURCE,
    timeout_s: int = DEFAULT_TURN_TIMEOUT_S,
    corpus_repos: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one scenario end to end. Returns the result record written to disk.

    Raises headless.RateLimited (caller returns the run to pending) or
    RuntimeError (caller marks it error).
    """
    results_dir = Path(results_dir)
    zoo_dir = Path(zoo_dir) if zoo_dir else results_dir / "zoo"
    run_dir = results_dir / "zoo-runs" / run_row["run_id"]
    run_dir.mkdir(parents=True, exist_ok=True)
    purge_turn_artifacts(run_dir)
    workspace = run_dir / "workspace"

    prepare_workspace(scenario.fixture, zoo_dir, workspace,
                      corpus_repos=corpus_repos, results_dir=results_dir)
    installed = install_skills(workspace, skills_source)
    repo_sha = pylgrim_repo_sha(skills_source)
    snapshot(workspace, run_dir / "before")

    # The session may run from a workspace-relative subdirectory (fix 1
    # coverage): headless Claude's cwd moves, but skills stay installed at the
    # WORKSPACE root's .claude/skills/, and every snapshot/assertion is still
    # taken over the workspace root.
    session_cwd = workspace
    if scenario.cwd:
        session_cwd = (workspace / scenario.cwd).resolve()
        session_cwd.mkdir(parents=True, exist_ok=True)

    turns: list[dict[str, Any]] = []
    transcript_paths: list[Path] = []
    final_texts: list[str] = []
    wall_time_s = 0.0
    question_rounds = 0
    session_id: str | None = None
    prompt = scenario.full_prompt()
    # Per-session persona state (the cooperative walk cycle advances here).
    persona_state: dict[str, Any] = {}

    for turn in range(1, scenario.max_turns + 1):
        cli_result = headless.invoke_claude(
            prompt, run_row["model"], session_cwd, timeout_s, resume_session=session_id
        )
        session_id = cli_result.get("session_id") or session_id
        wall_time_s += float(cli_result.get("duration_ms") or 0) / 1000.0
        text = str(cli_result.get("result") or "")
        final_texts.append(text)

        transcript_dest = headless.copy_transcript(
            session_cwd, session_id or "", run_dir / f"turn-{turn:02d}.transcript.jsonl"
        )
        if transcript_dest is not None:
            transcript_paths.append(transcript_dest)
        (run_dir / f"turn-{turn:02d}.result.json").write_text(
            json.dumps(cli_result, indent=2, default=str), encoding="utf-8"
        )

        events = (list(transcripts_mod.iter_events(transcript_dest))
                  if transcript_dest else [])
        question = personas.detect_question(text, events)
        turn_meta: dict[str, Any] = {
            "turn": turn,
            "session_id": session_id,
            "prompt": prompt[:500],
            "transcript": str(transcript_dest) if transcript_dest else None,
            "question_heuristic": question.heuristic,
        }
        turns.append(turn_meta)

        if not question.asked or turn == scenario.max_turns:
            break
        reply = personas.persona_reply(scenario.persona, question, persona_state)
        if reply is None:
            turn_meta["persona_reply"] = None
            break
        turn_meta["persona_reply"] = reply[:500]
        question_rounds += 1
        prompt = reply

    snapshot(workspace, run_dir / "after")

    ctx = skill_checks.SkillRunContext(
        skill=scenario.skill,
        fixture=scenario.fixture,
        workspace=workspace,
        before_dir=run_dir / "before",
        transcript_paths=transcript_paths,
        final_texts=final_texts,
        wall_time_s=wall_time_s,
        num_turns=len(turns),
        question_rounds=question_rounds,
        max_turns=scenario.max_turns,
        expect_write=scenario.expect_write,
        persona=scenario.persona,
        cwd=scenario.cwd,
    )
    checks = skill_checks.run_checks(ctx, scenario.assertions)

    record = {
        "run": {**run_row, "session_id": session_id},
        "scenario": {
            "id": scenario.id, "skill": scenario.skill, "fixture": scenario.fixture,
            "persona": scenario.persona, "invoke": scenario.invoke,
            "max_turns": scenario.max_turns, "assertions": scenario.assertions,
            "expect_write": scenario.expect_write, "notes": scenario.notes,
        },
        "pylgrim_repo_sha": repo_sha,
        "skills_installed": installed,
        "turns": turns,
        "wall_time_s": wall_time_s,
        "question_rounds": question_rounds,
        "checks": checks,
    }
    (run_dir / "result.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    return record
