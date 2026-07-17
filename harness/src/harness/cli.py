"""Command-line interface for the harness.

Commands:
  plan     build the randomized rep-blocked schedule into results/runs.db
  run      execute a batch of claimed runs; exits cleanly on rate limit
  extract  recompute metrics from stored artifacts (no agent invocation)
  status   queue summary table
  smoke    single end-to-end run outside the queue, for pipeline validation

Skills stress suite (separate queue in results/skills.db, isolated from the
coding-task pilot):
  plan-skills     schedule the scenario matrix (tasks/skills/config.yaml)
  run-skills      execute a batch of skill stress runs (multi-turn, personas)
  extract-skills  rescore done skill runs from stored artifacts (no agent calls)
  run-triggers    run the 36 activation probes from tasks/skills/triggers.yaml
  report-skills   regenerate results/reports/skills-stress-<n>.md

Typical subscription-bounded operation: `harness plan` once, then
`harness run --batch N` from a scheduled hourly task until `harness status`
shows everything done.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Optional

import typer
import yaml

from harness import __version__, provenance, queue, runner, schedule, workspace
from harness import taskcards as taskcards_mod
from harness import transcripts as transcripts_mod
from harness.metrics import drift_tokens as drift_tokens_metric
from harness.metrics import honeypots as honeypots_metric
from harness.metrics import scope as scope_metric
from harness.metrics import tokens as tokens_metric
from harness.metrics import violations as violations_metric

app = typer.Typer(help="pylgrim evaluation harness", no_args_is_help=True)

ROOT_OPT = typer.Option(Path("."), "--root", help="Project root (contains tasks/ and results/)")


def _paths(root: Path) -> tuple[Path, Path, Path]:
    root = root.resolve()
    return root / "tasks", root / "results", root / "results" / "runs.db"


def _load_corpus(tasks_dir: Path) -> dict:
    corpus_path = tasks_dir / "corpus.yaml"
    if not corpus_path.exists():
        typer.echo(f"error: {corpus_path} not found", err=True)
        raise typer.Exit(1)
    return yaml.safe_load(corpus_path.read_text(encoding="utf-8")) or {}


def _repo_index(corpus: dict) -> dict[str, dict]:
    return {r["name"]: r for r in corpus.get("repos", []) if isinstance(r, dict)}


def _repo_for_task(task_id: str, repos: dict[str, dict]) -> str | None:
    """Task ids are <repo>-tNN; map by longest matching repo-name prefix."""
    best = None
    for name in repos:
        if task_id.startswith(f"{name}-") and (best is None or len(name) > len(best)):
            best = name
    return best


def _claude_version() -> str:
    return provenance.claude_code_version()


def worker_repos(all_repos: list[str], workers: int, index: int) -> list[str]:
    """Deterministic repo partition for parallel coding drains.

    Sorted repos striped by position (never hash(): Python string hashing is
    randomized per process). Partitions are disjoint and cover every repo;
    workers=1 returns everything, reproducing single-worker behavior.
    """
    return [r for i, r in enumerate(sorted(all_repos)) if i % workers == index]


@app.command()
def plan(
    root: Path = ROOT_OPT,
    force: bool = typer.Option(False, "--force", help="Replace an existing schedule"),
) -> None:
    """Build the full randomized schedule into results/runs.db."""
    tasks_dir, results_dir, db_path = _paths(root)
    corpus = _load_corpus(tasks_dir)
    repos = _repo_index(corpus)

    cards, errors = taskcards_mod.load_all(tasks_dir)
    for err in errors:
        typer.echo(f"task card error: {err}", err=True)
    if errors:
        raise typer.Exit(1)
    if not cards:
        typer.echo("no task cards found in tasks/; nothing to plan", err=True)
        raise typer.Exit(1)

    tasks = []
    control_tasks = []
    for card in cards:
        repo = _repo_for_task(card.id, repos)
        if repo is None:
            typer.echo(f"error: task {card.id} matches no repo name in corpus.yaml", err=True)
            raise typer.Exit(1)
        entry = {"task_id": card.id, "repo": repo}
        (control_tasks if card.control else tasks).append(entry)

    arms_list = corpus.get("arms") or ["vanilla", "claudemd"]
    models = corpus.get("models") or ["sonnet"]
    reps = int(corpus.get("reps") or 1)
    control_reps = int(corpus.get("control_reps") or 1)
    seed = int(corpus.get("schedule_seed") or 0)

    conn = queue.connect(db_path)
    queue.init_db(conn)
    existing = queue.run_count(conn)
    if existing and not force:
        typer.echo(
            f"error: {existing} runs already scheduled in {db_path}; use --force to replace",
            err=True,
        )
        raise typer.Exit(1)
    if existing and force:
        with conn:
            conn.execute("DELETE FROM runs")

    rows = schedule.generate(tasks, arms_list, models, reps, seed)
    if control_tasks:
        # Positive-control runs (instrument validity) are appended after the
        # main block at their own rep count; they never enter confirmatory
        # analysis, so they must never displace confirmatory runs earlier
        # in the drain order.
        rows += schedule.generate(
            control_tasks, arms_list, models, control_reps, seed,
            order_key_start=len(rows),
        )
    queue.insert_schedule(conn, rows)
    queue.init_db(
        conn,
        meta={
            "schedule_seed": str(seed),
            "created_at": queue.now_iso(),
            "harness_version": __version__,
            "claude_version": _claude_version(),
            "platform": platform.platform(),
        },
    )
    typer.echo(f"scheduled {len(rows)} runs into {db_path}")


@app.command()
def run(
    root: Path = ROOT_OPT,
    batch: int = typer.Option(..., "--batch", help="Max runs to execute this invocation"),
    slot_count: int = typer.Option(2, "--slot-count", help="Workspace slot pool size"),
    timeout_min: int = typer.Option(30, "--timeout-min", help="Per-run timeout in minutes"),
    workers: int = typer.Option(
        1, "--workers", help="Total parallel workers (repo-partitioned)"
    ),
    worker_index: int = typer.Option(
        0, "--worker-index", help="This worker's index in [0, workers)"
    ),
    stale_reset: bool = typer.Option(
        True,
        "--stale-reset/--no-stale-reset",
        help="Reset stale running rows first (disable for parallel workers: "
        "a startup reset would return a sibling's in-flight claim to pending)",
    ),
) -> None:
    """Execute up to --batch claimed runs. Exits cleanly on rate limit or batch end."""
    tasks_dir, results_dir, db_path = _paths(root)
    corpus = _load_corpus(tasks_dir)
    repos = _repo_index(corpus)
    cards, errors = taskcards_mod.load_all(tasks_dir)
    if errors:
        for err in errors:
            typer.echo(f"task card error: {err}", err=True)
        raise typer.Exit(1)
    cards_by_id = {c.id: c for c in cards}
    if not 0 <= worker_index < workers:
        typer.echo(f"error: --worker-index must be in [0, {workers})", err=True)
        raise typer.Exit(2)

    conn = queue.connect(db_path)
    queue.init_db(conn)
    if stale_reset:
        stale = queue.reset_stale(conn)
        if stale:
            typer.echo(f"reset {stale} stale running row(s) to pending")

    # Slots are pinned per repo (round-robin over sorted names): a slot that
    # switches repos loses its worktree and with it the preserved dependency
    # caches, so repo-stable assignment is what makes `preserve` effective.
    # Under parallel workers each worker owns a disjoint repo subset and a
    # disjoint slot range (offset by worker_index), so slot directories can
    # never collide across workers. workers=1 reproduces the legacy mapping.
    mine = worker_repos(list(repos), workers, worker_index)
    repo_slots = {
        name: worker_index * slot_count + (i % slot_count)
        for i, name in enumerate(mine)
    }
    claim_repos = mine if workers > 1 else None

    executed = 0
    while executed < batch:
        row = queue.claim_next(conn, repos=claim_repos)
        if row is None:
            typer.echo("no eligible pending runs (done, or gated by resume_after)")
            break
        run_id = row["run_id"]
        task = cards_by_id.get(row["task_id"])
        repo_cfg = repos.get(row["repo"])
        if task is None or repo_cfg is None:
            queue.mark_skipped(conn, run_id, "task card or repo config missing")
            typer.echo(f"{run_id}: skipped (missing task card or repo config)")
            continue

        slot = repo_slots[row["repo"]]
        preserve = tuple(repo_cfg.get("preserve") or ("node_modules", ".venv", "target"))
        typer.echo(f"{run_id}: running in slot {slot}")
        try:
            record = runner.execute_run(
                row,
                task,
                repo_cfg["url"],
                results_dir,
                slot,
                preserve=preserve,
                timeout_s=timeout_min * 60,
            )
        except runner.RateLimited as exc:
            queue.mark_rate_limited(conn, run_id, exc.resume_after)
            typer.echo(f"{run_id}: rate limited, resume after {exc.resume_after}; exiting")
            break
        except Exception as exc:  # keep the loop crash-safe: record and continue
            queue.mark_error(conn, run_id, str(exc))
            typer.echo(f"{run_id}: error: {exc}", err=True)
            executed += 1
            continue

        queue.mark_done(
            conn,
            run_id,
            session_id=record["run"].get("session_id"),
            transcript_path=record["run"].get("transcript_path"),
            workspace_slot=slot,
        )
        typer.echo(f"{run_id}: done")
        executed += 1

    summary = queue.status_summary(conn)
    typer.echo(f"batch finished: {summary['by_status']}")


@app.command()
def extract(
    run_id: Optional[str] = typer.Argument(None, help="Recompute metrics for one run"),
    all_missing: bool = typer.Option(False, "--all-missing", help="All done runs lacking metrics"),
    root: Path = ROOT_OPT,
) -> None:
    """Recompute metrics from stored artifacts (diff, transcript). No agent calls."""
    tasks_dir, results_dir, db_path = _paths(root)
    cards, _ = taskcards_mod.load_all(tasks_dir)
    cards_by_id = {c.id: c for c in cards}
    conn = queue.connect(db_path)

    if run_id:
        targets = [run_id]
    elif all_missing:
        targets = []
        for row in conn.execute("SELECT run_id FROM runs WHERE status = 'done'"):
            result_path = results_dir / "runs" / row["run_id"] / "result.json"
            if not result_path.exists():
                targets.append(row["run_id"])
                continue
            record = json.loads(result_path.read_text(encoding="utf-8"))
            if not record.get("metrics"):
                targets.append(row["run_id"])
    else:
        typer.echo("provide a run_id or --all-missing", err=True)
        raise typer.Exit(1)

    for rid in targets:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (rid,)).fetchone()
        if row is None:
            typer.echo(f"{rid}: not in queue", err=True)
            continue
        task = cards_by_id.get(row["task_id"])
        run_dir = results_dir / "runs" / rid
        diff_path = run_dir / "diff.patch"
        if task is None or not diff_path.exists():
            typer.echo(f"{rid}: missing task card or artifacts, skipping", err=True)
            continue

        diff_text = diff_path.read_text(encoding="utf-8")
        name_only = [
            l for l in (run_dir / "name_only.txt").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        untracked = [
            l for l in (run_dir / "untracked.txt").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        metrics = {
            "scope": scope_metric.compute(diff_text, name_only, untracked, task),
            "honeypots": honeypots_metric.compute(name_only, untracked, task),
            "violations": violations_metric.evaluate(task.rules, diff_text, name_only, untracked),
        }
        transcript = run_dir / "transcript.jsonl"
        cli_result = None
        result_path = run_dir / "result.json"
        record = {}
        if result_path.exists():
            record = json.loads(result_path.read_text(encoding="utf-8"))
            cli_result = record.get("cli_result")
            metrics["outcome"] = (record.get("metrics") or {}).get("outcome")
        if transcript.exists():
            metrics["tokens"] = tokens_metric.compute(
                transcripts_mod.summarize_file(transcript), cli_result
            )
            # workspace_root=None: derived from the transcript's own cwd
            # field, so extraction from a copied transcript matches the
            # live run exactly.
            metrics["drift_tokens"] = drift_tokens_metric.compute(
                transcripts_mod.iter_events(transcript), task, workspace_root=None
            )
        record.setdefault("run", dict(row))
        record["metrics"] = metrics
        record["provenance"] = provenance.backfill(
            record, dict(row), task, transcript if transcript.exists() else None
        )
        result_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
        typer.echo(f"{rid}: metrics extracted")


@app.command()
def status(root: Path = ROOT_OPT) -> None:
    """Print a queue summary."""
    _, _, db_path = _paths(root)
    if not db_path.exists():
        typer.echo("no schedule yet: run `harness plan` first")
        raise typer.Exit(0)
    conn = queue.connect(db_path)
    queue.init_db(conn)
    summary = queue.status_summary(conn)
    typer.echo(f"total runs: {summary['total']}")
    typer.echo("by status:")
    for key in ("pending", "running", "done", "error", "skipped"):
        typer.echo(f"  {key:8} {summary['by_status'].get(key, 0)}")
    if summary["done_by_arm"]:
        typer.echo("done by arm: " + ", ".join(f"{a}={n}" for a, n in summary["done_by_arm"].items()))
    if summary["done_by_rep"]:
        typer.echo("done by rep: " + ", ".join(f"r{r}={n}" for r, n in summary["done_by_rep"].items()))
    if summary["meta"]:
        typer.echo("meta: " + ", ".join(f"{k}={v}" for k, v in summary["meta"].items()))


@app.command()
def smoke(
    repo: str = typer.Option(..., "--repo", help="Repo clone URL"),
    sha: str = typer.Option(..., "--sha", help="Pinned base SHA"),
    task: Path = typer.Option(..., "--task", help="Task card YAML path"),
    model: str = typer.Option("sonnet", "--model"),
    arm: str = typer.Option("vanilla", "--arm"),
    repo_name: Optional[str] = typer.Option(
        None,
        "--repo-name",
        help="Bare-clone cache key; matching corpus.yaml's name reuses the "
        "real repo cache and its warmed slot (default: derived from card id)",
    ),
    slot: int = typer.Option(0, "--slot", help="Workspace slot"),
    rep: int = typer.Option(0, "--rep", help="Rep index (distinguishes run dirs)"),
    root: Path = ROOT_OPT,
    timeout_min: int = typer.Option(30, "--timeout-min"),
) -> None:
    """One end-to-end run outside the queue: validates the whole pipeline."""
    _, results_dir, _ = _paths(root)
    card, errors = taskcards_mod.load_task_card(task)
    for err in errors:
        typer.echo(f"task card warning: {err}", err=True)
    if card is None:
        raise typer.Exit(1)
    card.base_sha = sha or card.base_sha

    name = repo_name or card.id.rsplit("-t", 1)[0] or "smoke"
    run_id = f"smoke--{card.id}--{arm}--{model}"
    if rep:
        run_id += f"--r{rep}"
    row = {
        "run_id": run_id,
        "repo": name,
        "task_id": card.id,
        "arm": arm,
        "model": model,
        "rep": rep,
        "seed": 0,
    }
    try:
        record = runner.execute_run(
            row, card, repo, results_dir, slot=slot, timeout_s=timeout_min * 60
        )
    except runner.RateLimited as exc:
        typer.echo(f"rate limited; resume after {exc.resume_after}", err=True)
        raise typer.Exit(2)
    typer.echo(json.dumps(record["metrics"], indent=2, default=str))
    typer.echo(f"smoke run complete: results/runs/{row['run_id']}/")


@app.command("warm-slots")
def warm_slots(
    root: Path = ROOT_OPT,
    slot_count: int = typer.Option(2, "--slot-count", help="Workspace slot pool size"),
    workers: int = typer.Option(1, "--workers", help="Match the drain's worker count"),
    repos_filter: Optional[str] = typer.Option(
        None, "--repos", help="Comma-separated repo names (default: all in corpus)"
    ),
    install_timeout_min: int = typer.Option(
        20, "--install-timeout-min", help="Per-repo install timeout"
    ),
) -> None:
    """Prepare each repo's slot at its pin and run the corpus install command.

    The harness never installs during runs (corpus `install` is documentation
    for humans and for this command); slots must be warmed before a drain or
    outcome test commands fail on cold dependency caches. Mirrors the drain's
    worker-partitioned slot mapping so the warmed slot is the one each
    worker will actually use.
    """
    import subprocess as sp

    tasks_dir, results_dir, _ = _paths(root)
    corpus = _load_corpus(tasks_dir)
    repos = _repo_index(corpus)
    wanted = (
        [r.strip() for r in repos_filter.split(",") if r.strip()]
        if repos_filter
        else sorted(repos)
    )
    unknown = [r for r in wanted if r not in repos]
    if unknown:
        typer.echo(f"error: not in corpus: {unknown}", err=True)
        raise typer.Exit(1)

    failures = []
    for worker_index in range(workers):
        mine = [r for r in worker_repos(sorted(repos), workers, worker_index) if r in wanted]
        slots = {
            name: worker_index * slot_count + (i % slot_count)
            for i, name in enumerate(worker_repos(sorted(repos), workers, worker_index))
        }
        for name in mine:
            cfg = repos[name]
            pin = cfg.get("pinned_sha")
            install = cfg.get("install")
            if not pin or not install:
                typer.echo(f"{name}: no pinned_sha/install in corpus, skipping")
                continue
            preserve = tuple(cfg.get("preserve") or ("node_modules", ".venv", "target"))
            slot = slots[name]
            typer.echo(f"{name}: preparing slot {slot} at {pin[:12]}")
            slot_dir = workspace.prepare(results_dir, slot, name, cfg["url"], pin, preserve)
            typer.echo(f"{name}: running install: {install}")
            proc = sp.run(
                install,
                shell=True,
                cwd=str(slot_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=install_timeout_min * 60,
            )
            if proc.returncode != 0:
                failures.append(name)
                tail = ((proc.stdout or "") + (proc.stderr or ""))[-500:]
                typer.echo(f"{name}: INSTALL FAILED (exit {proc.returncode}): {tail}", err=True)
            else:
                typer.echo(f"{name}: warmed")
    if failures:
        typer.echo(f"failed: {failures}", err=True)
        raise typer.Exit(1)
    typer.echo("all requested slots warmed")


# ---------------------------------------------------------------------------
# Skills stress suite commands (isolated queue: results/skills.db)
# ---------------------------------------------------------------------------

def _skills_paths(root: Path) -> tuple[Path, Path, Path]:
    root = root.resolve()
    return root / "tasks" / "skills", root / "results", root / "results" / "skills.db"


def _load_scenarios(skills_tasks_dir: Path):
    from harness import skilltasks

    scenarios, errors = skilltasks.load_all(skills_tasks_dir)
    for err in errors:
        typer.echo(f"scenario card error: {err}", err=True)
    if errors:
        raise typer.Exit(1)
    if not scenarios:
        typer.echo("no scenario cards in tasks/skills/; nothing to do", err=True)
        raise typer.Exit(1)
    return scenarios


@app.command("plan-skills")
def plan_skills(
    root: Path = ROOT_OPT,
    force: bool = typer.Option(False, "--force", help="Replace an existing schedule"),
    suite: Optional[str] = typer.Option(
        None, "--suite",
        help="Schedule only cards of this suite (e.g. 'e06' for the real-repo "
             "study, 'stress' for the zoo matrix). Default: all cards."),
) -> None:
    """Schedule the skills stress matrix into results/skills.db."""
    from harness import skill_runner, skilltasks

    skills_tasks_dir, _, db_path = _skills_paths(root)
    scenarios = skilltasks.filter_suite(_load_scenarios(skills_tasks_dir), suite)
    if not scenarios:
        typer.echo(f"no scenario cards in suite {suite!r}; nothing to plan", err=True)
        raise typer.Exit(1)
    config = skilltasks.load_config(skills_tasks_dir)

    conn = queue.connect(db_path)
    queue.init_db(conn)
    existing = queue.run_count(conn)
    if existing and not force:
        typer.echo(
            f"error: {existing} runs already scheduled in {db_path}; use --force",
            err=True,
        )
        raise typer.Exit(1)
    if existing and force:
        with conn:
            conn.execute("DELETE FROM runs")

    rows = skilltasks.generate_schedule(
        scenarios, config["tiers"], config["reps"], config["seed"]
    )
    queue.insert_schedule(conn, rows)
    queue.init_db(
        conn,
        meta={
            "schedule_seed": str(config["seed"]),
            "suite": suite or "all",
            "created_at": queue.now_iso(),
            "harness_version": __version__,
            "claude_version": _claude_version(),
            "pylgrim_repo_sha": skill_runner.pylgrim_repo_sha(),
            "platform": platform.platform(),
        },
    )
    typer.echo(
        f"scheduled {len(rows)} skill runs into {db_path} "
        f"(suite {suite or 'all'}: {len(scenarios)} scenarios x "
        f"{len(config['tiers'])} tiers, default reps {config['reps']})"
    )


@app.command("run-skills")
def run_skills(
    root: Path = ROOT_OPT,
    batch: int = typer.Option(..., "--batch", help="Max runs to execute this invocation"),
    task: Optional[str] = typer.Option(None, "--task", help="Only claim this scenario id"),
    model: Optional[str] = typer.Option(None, "--model", help="Only claim this model tier"),
    timeout_min: int = typer.Option(20, "--timeout-min", help="Per-turn timeout in minutes"),
    stale_reset: bool = typer.Option(
        True, "--stale-reset/--no-stale-reset",
        help="Reset 'running' rows to pending at startup. MUST be disabled for "
             "parallel workers: a worker starting while a sibling is mid-run "
             "would reset the sibling's claim and duplicate it (seen live). "
             "scripts/skills-drain.sh resets once up front instead."),
) -> None:
    """Execute up to --batch skill stress runs. Exits cleanly on rate limit."""
    from harness import skill_runner, skilltasks

    skills_tasks_dir, results_dir, db_path = _skills_paths(root)
    scenarios = {s.id: s for s in _load_scenarios(skills_tasks_dir)}
    # Corpus repos usable as real-repo fixtures (WI-E06); lenient load so the
    # zoo suite still runs without a corpus file.
    corpus_path = skills_tasks_dir.parent / "corpus.yaml"
    corpus_repos: dict[str, dict] = {}
    if corpus_path.exists():
        corpus_repos = _repo_index(
            yaml.safe_load(corpus_path.read_text(encoding="utf-8")) or {})

    conn = queue.connect(db_path)
    queue.init_db(conn)
    if stale_reset:
        stale = queue.reset_stale(conn)
        if stale:
            typer.echo(f"reset {stale} stale running row(s) to pending")

    executed = 0
    while executed < batch:
        if task or model:
            row = skilltasks.claim_next_filtered(conn, task, model)
        else:
            row = queue.claim_next(conn)
        if row is None:
            typer.echo("no eligible pending runs (done, filtered out, or gated)")
            break
        run_id = row["run_id"]
        scenario = scenarios.get(row["task_id"])
        if scenario is None:
            queue.mark_skipped(conn, run_id, "scenario card missing")
            typer.echo(f"{run_id}: skipped (scenario card missing)")
            continue
        typer.echo(f"{run_id}: running ({scenario.skill} on {scenario.fixture}, "
                   f"persona {scenario.persona})")
        try:
            record = skill_runner.execute_skill_run(
                row, scenario, results_dir, timeout_s=timeout_min * 60,
                corpus_repos=corpus_repos,
            )
        except skill_runner.headless.RateLimited as exc:
            queue.mark_rate_limited(conn, run_id, exc.resume_after)
            typer.echo(f"{run_id}: rate limited, resume after {exc.resume_after}; exiting")
            break
        except Exception as exc:  # keep the loop crash-safe: record and continue
            queue.mark_error(conn, run_id, str(exc))
            typer.echo(f"{run_id}: error: {exc}", err=True)
            executed += 1
            continue

        queue.mark_done(conn, run_id, session_id=record["run"].get("session_id"))
        failed = [c["assertion"] for c in record["checks"] if c["status"] == "fail"]
        typer.echo(f"{run_id}: done "
                   f"({'all checks pass' if not failed else 'FAILED: ' + ', '.join(failed)})")
        executed += 1

    summary = queue.status_summary(conn)
    typer.echo(f"batch finished: {summary['by_status']}")


@app.command("extract-skills")
def extract_skills(
    run_id: Optional[str] = typer.Argument(None, help="Rescore one run by id"),
    all_runs: bool = typer.Option(False, "--all", help="Rescore every done run"),
    root: Path = ROOT_OPT,
) -> None:
    """Recompute skill-run assertions from stored artifacts (before/after
    snapshots and transcripts). No agent calls; scenario cards are re-read, so
    new or changed assertions apply retroactively."""
    from harness import skill_runner as skill_runner_mod
    from harness.metrics import skill_checks

    skills_tasks_dir, results_dir, db_path = _skills_paths(root)
    scenarios = {s.id: s for s in _load_scenarios(skills_tasks_dir)}
    conn = queue.connect(db_path)
    queue.init_db(conn)

    if run_id:
        targets = [run_id]
    elif all_runs:
        targets = [row["run_id"] for row in conn.execute(
            "SELECT run_id FROM runs WHERE status = 'done' ORDER BY order_key")]
    else:
        typer.echo("provide a run_id or --all", err=True)
        raise typer.Exit(1)

    rescored = 0
    for rid in targets:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (rid,)).fetchone()
        if row is None:
            typer.echo(f"{rid}: not in queue", err=True)
            continue
        scenario = scenarios.get(row["task_id"])
        run_dir = results_dir / "zoo-runs" / rid
        result_path = run_dir / "result.json"
        if scenario is None or not result_path.exists() or not (run_dir / "before").is_dir():
            typer.echo(f"{rid}: missing scenario card or artifacts, skipping", err=True)
            continue

        record = json.loads(result_path.read_text(encoding="utf-8"))
        # Only this attempt's turn files: a requeued run shares its dir with
        # any previous attempt's higher-numbered leftovers, and globbing
        # turn-* rescores a chimera of the two (skill_runner now purges at
        # run start; this guards dirs written before that fix).
        transcript_paths, turn_result_paths = skill_runner_mod.turn_artifacts(
            run_dir, len(record.get("turns") or []))
        final_texts = []
        for turn_result in turn_result_paths:
            try:
                turn_data = json.loads(turn_result.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            final_texts.append(str(turn_data.get("result") or ""))

        ctx = skill_checks.SkillRunContext(
            skill=scenario.skill,
            fixture=scenario.fixture,
            workspace=run_dir / "workspace",
            before_dir=run_dir / "before",
            transcript_paths=transcript_paths,
            final_texts=final_texts,
            wall_time_s=float(record.get("wall_time_s") or 0.0),
            num_turns=len(record.get("turns") or []) or 1,
            question_rounds=int(record.get("question_rounds") or 0),
            max_turns=scenario.max_turns,
            expect_write=scenario.expect_write,
            persona=scenario.persona,
        )
        record["checks"] = skill_checks.run_checks(ctx, scenario.assertions)
        scenario_meta = record.setdefault("scenario", {})
        scenario_meta["assertions"] = scenario.assertions
        scenario_meta["expect_write"] = scenario.expect_write
        result_path.write_text(json.dumps(record, indent=2, default=str),
                               encoding="utf-8")
        failed = [c["assertion"] for c in record["checks"] if c["status"] == "fail"]
        typer.echo(f"{rid}: rescored "
                   f"({'all pass' if not failed else 'FAILED: ' + ', '.join(failed)})")
        rescored += 1
    typer.echo(f"rescored {rescored} run(s)")


@app.command("run-triggers")
def run_triggers(
    root: Path = ROOT_OPT,
    batch: int = typer.Option(36, "--batch", help="Max probes to run this invocation"),
    model: str = typer.Option("haiku", "--model", help="Model tier for the probes"),
    only: Optional[str] = typer.Option(None, "--only", help="Run a single probe id"),
    skill: Optional[str] = typer.Option(
        None, "--skill",
        help="Run every probe for one skill; like --only, reruns probes "
             "that already have results"),
) -> None:
    """Run activation probes from tasks/skills/triggers.yaml (resumable)."""
    from harness import trigger_check

    skills_tasks_dir, results_dir, _ = _skills_paths(root)
    probes, errors = trigger_check.load_triggers(skills_tasks_dir / "triggers.yaml")
    for err in errors:
        typer.echo(f"trigger error: {err}", err=True)
    if errors:
        raise typer.Exit(1)

    executed = 0
    for probe in probes:
        if executed >= batch:
            break
        if only and probe.id != only:
            continue
        if skill and probe.skill != skill:
            continue
        if not only and not skill and trigger_check.is_done(results_dir, probe.id):
            continue
        typer.echo(f"{probe.id}: probing ({probe.expect}, {probe.skill})")
        try:
            record = trigger_check.run_probe(probe, results_dir, model=model)
        except trigger_check.headless.RateLimited as exc:
            typer.echo(f"{probe.id}: rate limited, resume after {exc.resume_after}; exiting")
            break
        except Exception as exc:
            typer.echo(f"{probe.id}: error: {exc}", err=True)
            executed += 1
            continue
        verdict = "correct" if record["correct"] else "WRONG"
        typer.echo(f"{probe.id}: fired={record['fired_skills'] or 'none'} ({verdict})")
        executed += 1

    results = trigger_check.load_results(results_dir)
    typer.echo(f"trigger probes complete: {len(results)}/{len(probes)}")


@app.command("report-coding")
def report_coding(root: Path = ROOT_OPT) -> None:
    """Regenerate the coding-task drift report + per-run CSV export."""
    from harness import coding_report

    tasks_dir, results_dir, db_path = _paths(root)
    if not db_path.exists():
        typer.echo("no schedule yet: run `harness plan` first", err=True)
        raise typer.Exit(1)
    cards, _ = taskcards_mod.load_all(tasks_dir)
    cards_by_id = {c.id: c for c in cards}

    conn = queue.connect(db_path)
    queue.init_db(conn)
    loaded = coding_report.load_coding_runs(conn, results_dir)
    all_rows = [item["row"] for item in loaded]
    flat_rows = [
        coding_report.flatten_run(
            item["row"], item["record"], cards_by_id.get(item["row"]["task_id"])
        )
        for item in loaded
        if item["record"] is not None
    ]
    meta = {
        row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM meta")
    }

    reports_dir = results_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    number = coding_report.next_report_number(reports_dir)
    text = coding_report.build_report(all_rows, flat_rows, meta, number)
    out = reports_dir / f"coding-report-{number}.md"
    out.write_text(text, encoding="utf-8")
    csv_path = reports_dir / f"coding-report-{number}.csv"
    coding_report.write_csv(flat_rows, csv_path)
    typer.echo(
        f"report written: {out} ({len(flat_rows)} runs with results, "
        f"{len(all_rows)} scheduled); csv: {csv_path}"
    )


@app.command("plan-judge")
def plan_judge(
    root: Path = ROOT_OPT,
    model: str = typer.Option("sonnet", "--model", help="Judge model"),
    reps: int = typer.Option(1, "--reps", help="Judge reps per run"),
    include_control: bool = typer.Option(
        False, "--include-control", help="Also judge positive-control runs"
    ),
) -> None:
    """Enqueue judge work for every done run with a diff artifact."""
    from harness import judge as judge_mod

    tasks_dir, results_dir, db_path = _paths(root)
    cards, _ = taskcards_mod.load_all(tasks_dir)
    conn = queue.connect(db_path)
    queue.init_db(conn)
    inserted = judge_mod.enqueue_judge_runs(
        conn,
        model,
        reps,
        cards_by_id={c.id: c for c in cards},
        results_dir=results_dir,
        include_control=include_control,
    )
    total = conn.execute("SELECT COUNT(*) FROM judge_runs").fetchone()[0]
    typer.echo(f"enqueued {inserted} new judge run(s) ({total} total)")


@app.command("run-judge")
def run_judge(
    root: Path = ROOT_OPT,
    batch: int = typer.Option(..., "--batch", help="Max judge runs this invocation"),
    timeout_min: int = typer.Option(15, "--timeout-min", help="Per-judge timeout (minutes)"),
    stale_reset: bool = typer.Option(
        True,
        "--stale-reset/--no-stale-reset",
        help="Reset stale running judge rows first (disable for parallel workers)",
    ),
) -> None:
    """Drain judge runs. Exits cleanly on rate limit or batch end."""
    from harness import judge as judge_mod

    tasks_dir, results_dir, db_path = _paths(root)
    cards, _ = taskcards_mod.load_all(tasks_dir)
    cards_by_id = {c.id: c for c in cards}
    conn = queue.connect(db_path)
    queue.init_db(conn)
    judge_mod.init_judge_table(conn)
    if stale_reset:
        stale = judge_mod.reset_stale_judge(conn)
        if stale:
            typer.echo(f"reset {stale} stale judge row(s) to pending")

    executed = 0
    while executed < batch:
        row = judge_mod.claim_next_judge(conn)
        if row is None:
            typer.echo("no eligible pending judge runs")
            break
        jid = row["judge_run_id"]
        run_row = conn.execute(
            "SELECT task_id FROM runs WHERE run_id = ?", (row["run_id"],)
        ).fetchone()
        task = cards_by_id.get(run_row["task_id"]) if run_row else None
        if task is None:
            judge_mod.mark_skipped_judge(conn, jid, "task card missing")
            typer.echo(f"{jid}: skipped (task card missing)")
            continue
        typer.echo(f"{jid}: judging")
        try:
            payload = judge_mod.score_run(
                row["run_id"],
                results_dir,
                task,
                model=row["model"],
                rep=row["rep"],
                timeout_s=timeout_min * 60,
            )
        except judge_mod.ArmLeakError as exc:
            judge_mod.mark_skipped_judge(conn, jid, f"arm-leak-unscrubbable: {exc}")
            typer.echo(f"{jid}: skipped (arm leak unscrubbable)")
            executed += 1
            continue
        except runner.RateLimited as exc:
            judge_mod.mark_rate_limited_judge(conn, jid, exc.resume_after)
            typer.echo(f"{jid}: rate limited, resume after {exc.resume_after}; exiting")
            break
        except Exception as exc:
            judge_mod.mark_error_judge(conn, jid, str(exc))
            typer.echo(f"{jid}: error: {exc}", err=True)
            executed += 1
            continue
        judge_mod.mark_done_judge(conn, jid, json.dumps(payload["verdicts"]))
        typer.echo(f"{jid}: done ({len(payload['verdicts'])} verdicts)")
        executed += 1

    counts = {
        row["status"]: row["n"]
        for row in conn.execute(
            "SELECT status, COUNT(*) AS n FROM judge_runs GROUP BY status"
        )
    }
    typer.echo(f"judge batch finished: {counts}")


@app.command("extract-judge")
def extract_judge(
    judge_run_id: Optional[str] = typer.Argument(None, help="Re-parse one judge run"),
    all_runs: bool = typer.Option(False, "--all", help="Re-parse every done judge run"),
    root: Path = ROOT_OPT,
) -> None:
    """Re-parse stored judge artifacts into the verdicts column. No agent calls."""
    from harness import judge as judge_mod

    tasks_dir, results_dir, db_path = _paths(root)
    cards, _ = taskcards_mod.load_all(tasks_dir)
    cards_by_id = {c.id: c for c in cards}
    conn = queue.connect(db_path)
    judge_mod.init_judge_table(conn)

    if judge_run_id:
        rows = conn.execute(
            "SELECT * FROM judge_runs WHERE judge_run_id = ?", (judge_run_id,)
        ).fetchall()
    elif all_runs:
        rows = conn.execute("SELECT * FROM judge_runs WHERE status = 'done'").fetchall()
    else:
        typer.echo("provide a judge_run_id or --all", err=True)
        raise typer.Exit(1)

    for row in rows:
        artifact = (
            results_dir / "runs" / row["run_id"]
            / judge_mod.artifact_name(row["model"], row["rep"])
        )
        if not artifact.exists():
            typer.echo(f"{row['judge_run_id']}: no artifact, skipping", err=True)
            continue
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        run_row = conn.execute(
            "SELECT task_id FROM runs WHERE run_id = ?", (row["run_id"],)
        ).fetchone()
        task = cards_by_id.get(run_row["task_id"]) if run_row else None
        n = len(task.criteria) if task else 0
        verdicts = judge_mod.parse_verdicts(payload.get("raw_result_text", ""), n)
        if verdicts is None:
            verdicts = payload.get("verdicts")
        if verdicts is None:
            typer.echo(f"{row['judge_run_id']}: unparseable, leaving as-is", err=True)
            continue
        judge_mod.mark_done_judge(conn, row["judge_run_id"], json.dumps(verdicts))
        typer.echo(f"{row['judge_run_id']}: verdicts re-parsed")


@app.command("judge-calibration")
def judge_calibration(
    root: Path = ROOT_OPT,
    sample: int = typer.Option(100, "--sample", help="Calibration sample size"),
    seed: int = typer.Option(42, "--seed", help="Sampling seed"),
    graded: Optional[Path] = typer.Option(
        None, "--graded", help="Filled sheet CSV: compute kappa instead of sampling"
    ),
) -> None:
    """Emit the founder-grading sheet, or compute Cohen's kappa from a filled one."""
    from harness import judge as judge_mod

    tasks_dir, results_dir, db_path = _paths(root)
    reports_dir = results_dir / "reports"

    if graded is not None:
        key_csv = reports_dir / "judge-calibration-key.csv"
        if not key_csv.exists():
            typer.echo(f"error: {key_csv} not found", err=True)
            raise typer.Exit(1)
        result = judge_mod.kappa_from_files(graded, key_csv)
        typer.echo(f"graded: {result['n_graded']} (skipped {result['n_skipped']})")
        typer.echo(f"raw agreement: {result['raw_agreement']:.3f}")
        typer.echo(f"Cohen's kappa: {result['kappa']:.3f}")
        typer.echo("confusion (rows=sam, cols=judge):")
        for sam_verdict, cols in result["confusion"].items():
            typer.echo(f"  {sam_verdict:13s} " + " ".join(
                f"{v}={cols[v]}" for v in judge_mod.VERDICTS
            ))
        if result["kappa"] is not None and result["kappa"] < 0.6:
            typer.echo(
                "kappa < 0.6: judged criteria-satisfaction is DEMOTED to "
                "exploratory per the pre-registration."
            )
        return

    cards, _ = taskcards_mod.load_all(tasks_dir)
    conn = queue.connect(db_path)
    judge_mod.init_judge_table(conn)
    units = judge_mod.calibration_pairs(conn, {c.id: c for c in cards})
    if not units:
        typer.echo("no done judge runs to sample from", err=True)
        raise typer.Exit(1)
    sheet_csv, sheet_md, key_csv = judge_mod.write_calibration_sheet(
        units, results_dir, reports_dir, sample_size=sample, seed=seed
    )
    typer.echo(f"sheet: {sheet_md}")
    typer.echo(f"grades go in: {sheet_csv} (sam_verdict column)")
    typer.echo(f"key (do not open while grading): {key_csv}")


@app.command("report-skills")
def report_skills(root: Path = ROOT_OPT) -> None:
    """Regenerate the skills stress findings report."""
    from harness import skill_report, trigger_check

    _, results_dir, db_path = _skills_paths(root)
    runs = skill_report.load_skill_runs(results_dir)
    triggers = trigger_check.load_results(results_dir)

    queue_summary = None
    if db_path.exists():
        conn = queue.connect(db_path)
        queue.init_db(conn)
        queue_summary = queue.status_summary(conn)

    reports_dir = results_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    number = skill_report.next_report_number(reports_dir)
    text = skill_report.build_report(runs, triggers, number, queue_summary)
    out = reports_dir / f"skills-stress-{number}.md"
    out.write_text(text, encoding="utf-8")
    typer.echo(f"report written: {out} ({len(runs)} runs, {len(triggers)} trigger probes)")


if __name__ == "__main__":
    app()
