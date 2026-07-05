"""Command-line interface for the harness.

Commands:
  plan     build the randomized rep-blocked schedule into results/runs.db
  run      execute a batch of claimed runs; exits cleanly on rate limit
  extract  recompute metrics from stored artifacts (no agent invocation)
  status   queue summary table
  smoke    single end-to-end run outside the queue, for pipeline validation

Typical subscription-bounded operation: `harness plan` once, then
`harness run --batch N` from a scheduled hourly task until `harness status`
shows everything done.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
import yaml

from harness import __version__, queue, runner, schedule
from harness import taskcards as taskcards_mod
from harness import transcripts as transcripts_mod
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
    exe = shutil.which("claude")
    if not exe:
        return "not-found"
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=60)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


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
    for card in cards:
        repo = _repo_for_task(card.id, repos)
        if repo is None:
            typer.echo(f"error: task {card.id} matches no repo name in corpus.yaml", err=True)
            raise typer.Exit(1)
        tasks.append({"task_id": card.id, "repo": repo})

    arms_list = corpus.get("arms") or ["vanilla", "claudemd"]
    models = corpus.get("models") or ["sonnet"]
    reps = int(corpus.get("reps") or 1)
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

    conn = queue.connect(db_path)
    queue.init_db(conn)
    stale = queue.reset_stale(conn)
    if stale:
        typer.echo(f"reset {stale} stale running row(s) to pending")

    # Slots are pinned per repo (round-robin over sorted names): a slot that
    # switches repos loses its worktree and with it the preserved dependency
    # caches, so repo-stable assignment is what makes `preserve` effective.
    repo_slots = {name: i % slot_count for i, name in enumerate(sorted(repos))}

    executed = 0
    while executed < batch:
        row = queue.claim_next(conn)
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
        record.setdefault("run", dict(row))
        record["metrics"] = metrics
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

    repo_name = card.id.rsplit("-t", 1)[0] or "smoke"
    row = {
        "run_id": f"smoke--{card.id}--{arm}--{model}",
        "repo": repo_name,
        "task_id": card.id,
        "arm": arm,
        "model": model,
        "rep": 0,
        "seed": 0,
    }
    try:
        record = runner.execute_run(
            row, card, repo, results_dir, slot=0, timeout_s=timeout_min * 60
        )
    except runner.RateLimited as exc:
        typer.echo(f"rate limited; resume after {exc.resume_after}", err=True)
        raise typer.Exit(2)
    typer.echo(json.dumps(record["metrics"], indent=2, default=str))
    typer.echo(f"smoke run complete: results/runs/{row['run_id']}/")


if __name__ == "__main__":
    app()
