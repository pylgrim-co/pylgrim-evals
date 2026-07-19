# Pre-registration v3-stale — E8, the staleness study

Dated: 2026-07-18 (UTC). Status at signing: NO E8 confirmatory run has
been executed. Wave-1 (prereg-v1, e8ae27a) and Wave-1.5 (prereg-v2-ext,
99a4f16) artifacts are untouched and remain binding for their waves. E8
was pre-declared in the extension ledger (bias-audit-1.md) and tests the
claim the Wave-1.5 writeup could only argue: pylgrim's value is measured
against the stale file users actually have, not against no file.

## 1. Design

Two new cells on the vague-prompt row, same 48 short T-real cards, same
frozen vague-prompt artifact (sha 2e41d3aa…), 3 reps, Sonnet:

| cell | the file in the workspace |
|---|---|
| `stale-generic-vague` | charter-only exported block: the card's constraints, NO work item — a file with some still-relevant rules and no current work contract |
| `stale-wrong-vague` | the ENTIRE exported block of the PREVIOUS task — the file nobody updated since the last piece of work |

- **The staleness rule (frozen):** "previous task" = the next T-real card
  in sorted id order within the repo, cyclically (`wrong_card_for` in
  harness/src/harness/arms.py). Deterministic; no selection freedom. The
  corpus cards' constraints are task-scoped, so the faithful stale file is
  stale wholesale (constraints + work item both from the previous card).
- Baselines reuse the already-run Wave-1.5 cells `vanilla-vague` and
  `export-vague` (run 0-2 days earlier, same model snapshot and CLI;
  the temporal gap is disclosed rather than re-run).
- 2 × 48 × 3 = 288 new runs, appended past the current max order key,
  seed 42, rep-blocked.

## 2. Hypotheses (stated for honesty; the tests decide)

- H-E8a: staleness forfeits the drift protection — `stale-wrong-vague`
  drifts more than `export-vague`.
- H-E8b (the misleading-file hypothesis): a wholly stale file is WORSE
  than no file — `stale-wrong-vague` under-performs `vanilla-vague` on
  drift and/or outcomes, because confident wrong scope steers the agent.
- H-E8c: `stale-generic-vague` sits between fresh and nothing (rules
  retain some protective value without a work contract).
- Awkward-direction results publish with the same prominence.

## 3. Confirmatory family (Holm as one family; card = unit; §7 pairing carried over)

| # | endpoint | comparison | test |
|---|---|---|---|
| 1 | drift: M1∪M3 any-drift | `stale-wrong-vague` vs `export-vague` | exact McNemar, two-sided |
| 2 | drift: M1∪M3 any-drift | `stale-wrong-vague` vs `vanilla-vague` | exact McNemar, two-sided |
| 3 | M5 test-pass (majority-of-reps) | `stale-wrong-vague` vs `vanilla-vague` | exact McNemar, two-sided |
| 4 | economy: total_cost_usd | `stale-wrong-vague` − `vanilla-vague` | repo-level sign-flip, two-sided |

`stale-generic-vague` is descriptive only (bounds + factorial row): the
family stays at four for power discipline, and the generic cell's role is
the gradient picture, not a headline claim.

Degenerate-case rule, R1-ext scrub (hugo/nushell/zod), R2 junk patterns,
R4 economy basis, truncation rule: all carried over verbatim from
prereg-v2-ext. Injection-mass decomposition accompanies endpoint 4
(the stale block still carries mass; its overhead is computed from the
actual rendered stale artifact).

## 4. Claim scoping (binding)

Results are statements about "a wholly out-of-date managed block under
issue-text prompts, single-session" — the staleness MODEL is one specific,
frozen rule (previous-task file), not a measurement of real-world aging
distributions. The Custodian/freshness product mechanism is motivated by,
not tested by, this study.

## 5. Smoke disclosure

Pipeline validation before this freeze: unit tests (12, incl. the
cyclic-next rule and block-identity checks), a dry CONTENT render of
`stale-generic-vague` on zustand-l01 (excluded card) and of
`stale-wrong-vague` on click-t01 (content generation only; no agent run,
no outcome observed). The live agent/capture path is unchanged from
Wave 1.5 (same render-then-run machinery, live-proven there).

## 6. Provenance

Harness at this freeze commit; vendored exporter unchanged (pylgrim-repo
00ff5a1); vague artifact unchanged (tasks/vague/vague-prompts-v1.yaml).
This freeze: the commit carrying this file, tagged `prereg-v3-stale`.
