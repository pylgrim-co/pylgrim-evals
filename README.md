# pylgrim-evals

> **Private until pre-registration freeze.** This repo becomes public when the
> pre-registration in `preregistration/` is frozen. Until then: no issues, no
> external sharing, no result peeking beyond pipeline validation.

Evaluation harness for **pylgrim**: controlled experiments on AI coding agents.

One run is one `(repo, task, arm, model, rep)` cell: a headless Claude Code
(`claude -p`) invocation on a pinned checkout of a public repo. Drift, rule
violations, and token waste are measured deterministically from the resulting
git diff and session transcript.

**Arms:**

- `vanilla`: the task prompt only.
- `claudemd`: the same intent rendered into a `CLAUDE.md` in the workspace.
- `pylgrim`: the enforcement layer (Wave 2, stubbed for now).

The prompt text is identical across arms; only the context channel differs.

All runs are **subscription-bounded** (founder's Claude Max plan, zero API
budget). The core design consequence is a crash-safe resumable SQLite queue:
batches trickle over weeks, and any process death or rate limit resumes with
zero lost state.

## Layout

```
preregistration/        frozen hypotheses, power analysis, analysis plan
paper/                  writeup
analysis/notebooks/     post-hoc analysis (pandas/scipy/statsmodels, later)
tasks/                  corpus.yaml + one task card YAML per task
results/                gitignored: runs.db, repo clones, worktree slots,
                        per-run artifacts under results/runs/<run_id>/
harness/                the Python package (src layout) + tests
```

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/) (uv 0.11 verified).

```powershell
cd harness
uv sync                      # creates .venv, installs typer + pyyaml + pytest
uv run pytest                # all tests are offline: no network, no claude

# From the repo root (or pass --root):
uv run harness plan --root ..            # freeze the randomized schedule into results/runs.db
uv run harness run --root .. --batch 5   # execute up to 5 runs; exits cleanly on rate limit
uv run harness status --root ..          # queue summary
uv run harness extract --root .. --all-missing   # recompute metrics from stored artifacts
uv run harness smoke --root .. --repo <URL> --sha <SHA> --task ../tasks/<f>.yaml
```

`plan` refuses to overwrite an existing schedule without `--force`. `run`
resets stale `running` rows on startup (a previous process died), claims runs
one at a time in the frozen order, and stops the batch on the first rate
limit, leaving the run pending with a `resume_after` gate.

## Verified Claude Code CLI facts (2.1.175, 2026-07)

Discovered by running `claude --help` and a real smoke run, not from memory.
Re-verify these when the CLI updates (`claude --version` is recorded in the
queue's `meta` table at plan time).

- Headless invocation: `claude -p "<prompt>" --output-format json --model <alias>`.
  There is no separate `claude -p --help`; `-p/--print` is a flag on the main
  command.
- Model selection: `--model` takes an alias (`sonnet`, `haiku`, `opus`,
  `fable`) or a full model name.
- Permission bypass: `--dangerously-skip-permissions` (full bypass). A
  `--permission-mode bypassPermissions` choice also exists, as does
  `--allow-dangerously-skip-permissions`. The harness uses
  `--dangerously-skip-permissions`.
- Result JSON (single object on stdout) keys observed: `type`, `subtype`,
  `is_error`, `duration_ms`, `duration_api_ms`, `num_turns`, `result`,
  `stop_reason`, `session_id`, `total_cost_usd`, `usage` (input/output/cache
  token counts), `modelUsage` (per-model accounting incl. `costUSD`),
  `permission_denials`, `terminal_reason`, `uuid`.
- Transcript location: `~/.claude/projects/<munged-cwd>/<session_id>.jsonl`.
  **Munging rule (verified empirically):** every character of the absolute
  cwd that is not `[A-Za-z0-9]` is replaced with `-`. Example observed:
  `C:\Users\samue\AppData\Local\Temp\pylgrim-smoke` becomes
  `C--Users-samue-AppData-Local-Temp-pylgrim-smoke` (colon and backslashes
  each become one dash; existing dashes pass through). The runner also has a
  glob fallback (`projects/*/<session_id>.jsonl`) in case the rule drifts.
- The runner copies the transcript into `results/runs/<run_id>/` immediately
  after the run, before anything can rotate or touch it.

## Subscription-bounded operating notes

- Weekly/5-hour usage limits are the normal operating condition, not an
  error. On a rate limit the run goes back to `pending` with `resume_after`
  set (parsed from the error if possible, else now + 60 min) and the attempt
  counter is not consumed.
- Suggested cadence on Windows: a Task Scheduler job running hourly, e.g.
  `uv run harness run --root C:\Dev\pylgrim-master\pylgrim-evals --batch 3`. Idle invocations
  are free: if everything is gated or done, the command exits immediately.
- The schedule is blocked by rep: all rep-1 runs (shuffled across cells) come
  before any rep-2 run, so a truncated study is still balanced across cells.
- The run environment is scrubbed: `ANTHROPIC_API_KEY` and `*_TOKEN`,
  `*_SECRET`, `*_KEY` variables are dropped (PATH, user dirs, and `CLAUDE*`
  vars are kept; subscription auth lives in `~/.claude`, not in env vars).

## Tooling notes

- `uv` was available at build time (0.11.21), so the standard flow is
  `uv sync` / `uv run`. Without uv: `py -3.12 -m venv .venv`, activate,
  `pip install -e .[analysis] pytest` from `harness/`.
- Runtime deps are deliberately minimal: typer + pyyaml. sqlite3, hashlib,
  subprocess, fnmatch are stdlib. scipy/pandas/statsmodels are declared as
  the `analysis` optional extra for later; nothing in the harness imports them.
