# P-compose probe · readout 1 — **PROBE: exploratory, insight-grade, NOT confirmatory**

This is the descriptive readout of the **P-compose probe** (docs/10-evaluation-plan.md §9 in the venture repo): does an LLM-composed context packet behave differently from the free, deterministic export block? One new cell was run — `compose-vague@haiku`, 48 short T-real cards × reps 7-9, where a pre-run Haiku call reads the card's vague prompt plus the full mechanical `.pylgrim` ledger and composes the workspace CLAUDE.md (audit artifacts `composed-claude-md.md`, `compose-result.json`, `compose-transcript.jsonl` persisted per run; compose failure = run error, no fallback). **No preregistration exists for this probe, no hypothesis test is run anywhere in this report, and nothing here is a claim.** Any pattern below is hypothesis-generating only.

**TEMPORAL-GAP DISCLOSURE (read this before the table):** the comparator `export-vague@haiku` (reps 1-3) and the orientation row `vanilla-vague@haiku` were run in the E10 sweep roughly eight days before the probe cell, on the same pinned model snapshot (claude-haiku-4-5-20251001) but not interleaved with it. CLI version, backend behavior, and repo mirror state may have drifted in between. That alone caps this readout at insight grade: this is a probe, not a paired confirmatory study, and no cross-cell difference below should be read as an effect.

Conventions carried verbatim from `analysis/e9_e10_confirmatory.py`: card = unit; M1/M3/any-drift with the R2 junk filter; M5 = majority-of-reps deterministic pass; R4 CLI-modelUsage economy basis; R1-ext scrub for churn on hugo/nushell/zod (compose-vague materializes a workspace CLAUDE.md, so the scrub applies to it like any context arm); bounds are one-sided exact Clopper-Pearson 95%. Database read-only; nothing re-run.

## Regression check (gate, computed before any probe number)

House rule: the published comparator cells are re-derived from the same database and asserted against `results/reports/e9-e10-analysis-1.md` — the full row (drift counts, M5, cost, churn, turns, judged) — before any new number is read: **PASSED**.

- vanilla-vague@haiku (E10, r1-r3): M1 13, M3 14, any-drift 14/48, M5 38/48, cost $0.458, churn 0.234, turns 44.8, judged 51.5% (309/600 verdicts; 140/144 runs) — published: M1 13, M3 14, any-drift 14/48, M5 38/48, $0.458, churn 0.234, turns 44.8, 51.5% (309/600; 140/144)
- export-vague@haiku (E10, r1-r3): M1 0, M3 1, any-drift 1/48, M5 42/48, cost $0.382, churn 0.034, turns 35.0, judged 78.0% (476/610 verdicts; 142/144 runs) — published: M1 0, M3 1, any-drift 1/48, M5 42/48, $0.382, churn 0.034, turns 35.0, 78.0% (476/610; 142/144)

## The cells (48 short T-real cards, vague prompts, Haiku)

| cell | reps | n cards | M1 touched (bound) | M3 violated (bound) | any-drift (bound) | M5 majority-pass | mean main-run cost | churn share | mean turns | judged met |
|---|---|---|---|---|---|---|---|---|---|---|
| compose-vague | 7-9 | 48 | 1 (≤9.5%) | 3 (≤15.4%) | 3 (≤15.4%) | 44/48 | $0.374 | 0.071 | 33.8 | 78.8% (454/576 verdicts; 134/140 runs judged) |
| export-vague (E10 comparator) | 1-3 | 48 | 0 (≤6.1%) | 1 (≤9.5%) | 1 (≤9.5%) | 42/48 | $0.382 | 0.034 | 35.0 | 78.0% (476/610 verdicts; 142/144 runs judged) |
| vanilla-vague (orientation) | 1-3 | 48 | 13 (≤39.6%) | 14 (≤41.8%) | 14 (≤41.8%) | 38/48 | $0.458 | 0.234 | 44.8 | 51.5% (309/600 verdicts; 140/144 runs judged) |

Comparator rows are the published E10 values (asserted above, not recomputed fresh for this table). The compose row's cost column is the MAIN RUN only — the compose call is decomposed below. Turns likewise count the main run only (the compose call is a single-turn text call).

- Compose drift cards: `hono-t01`, `sql-formatter-t04`, `zustand-t05` (vs the comparator's single drift card `hono-t01`). Compose M5 misses: `eslint-t02`, `hono-t01`, `nushell-t04`, `zustand-t05`.
- Reading, probe-grade: drift 3/48 vs 1/48 and M5 44/48 vs 42/48 are both within what the temporal gap plus rep-to-rep noise could produce; judged-met is a wash (78.8% vs 78.0%). Nothing here suggests composition helps or hurts agent behavior by more than noise on this corpus.

## Compose-cost decomposition (does composition pay for itself?)

Economy basis: R4 CLI-reported `total_cost_usd` for the main run; the compose call's own `total_cost_usd` from its persisted `compose-result.json`. Card-unit means (mean over cards of the per-card rep mean).

| component | mean USD/run |
|---|---|
| compose-vague main run | $0.3740 |
| compose call (pre-run) | $0.0332 |
| **compose-vague total** | **$0.4072** |
| export-vague comparator (block is free) | $0.3819 |

- The compose call adds $0.0332/run (8.9% of the main-run cost). Total, composition costs $+0.0253/run vs the deterministic block — i.e. the composed packet is ~+6.6% on total spend, while the export block costs $0 to produce (a deterministic render of the ledger).
- For composition to "pay for itself" it would have to buy back its own mass in behavior (drift, M5, or judged-met). On this corpus it does not: drift is nominally worse, M5 nominally better, judged-met flat — all within probe noise — and the main-run cost saving vs the comparator ($-0.0080) is smaller than the compose call itself.

## Coverage and missing data

- Runs: 140/144 done. 4 permanent run errors (post-retry):
  - `click-t02--compose-vague--haiku--r9`: attempt 2 — [WinError 32] The process cannot access the file because it is being used by another proce
  - `eslint-t02--compose-vague--haiku--r9`: attempt 2 — git clean -fdx -e node_modules failed (exit 1): warning: failed to remove coverage/tmp: Di
  - `nushell-t04--compose-vague--haiku--r8`: attempt 3 — claude run timed out after 1800s
  - `nushell-t04--compose-vague--haiku--r9`: attempt 2 — claude run timed out after 1800s
- Judge: 134/140 done runs judged; 6 excluded as judge errors (judge reply unparseable after one retry, the recorded exclusion class):
  - `hono-t01--compose-vague--haiku--r9`
  - `hono-t04--compose-vague--haiku--r9`
  - `hugo-t03--compose-vague--haiku--r7`
  - `nushell-t05--compose-vague--haiku--r9`
  - `rich-t02--compose-vague--haiku--r9`
  - `sql-formatter-t04--compose-vague--haiku--r9`
- Judge rows pending: 0 (drain complete for this cell).
- Card-unit aggregation absorbs the run errors (affected cards aggregate over their remaining reps): `nushell-t04` counts from 1 rep, `eslint-t02` and `click-t02` from 2. Comparator exclusions are as published in e9-e10-analysis-1.md (none; 144/144).

## What the composer actually writes (qualitative pass)

Eleven composed artifacts read across 8 repos — `click-t01 r7`, `hugo-t02 r7`, `nushell-t01 r7/r9`, `zod-t04 r7`, `prettier-t03 r7`, `eslint-t04 r7`, `hono-t02 r7/r8/r9`, `rich-t01 r7` — each against the card's deterministic export block, its raw ledger, and its vague prompt.

- **Shape and length.** Composed blocks average 1763 chars (median 1740, range 1177-2611, n=140 done runs) vs the export block's 1576 (median 1534) — composition does not compress; it re-narrates. The composer reliably restructures the ledger into a task-shaped document: a problem statement lifted from the vague prompt (which the deterministic block never contains), then scope/constraints/acceptance criteria that map 1:1 onto ledger entries, usually with imperative phrasing ("Do not touch", "Work in these files").
- **What it keeps.** Scope boundaries and acceptance criteria survive essentially intact in all eleven reads; a crude literal-string scan over all done runs finds the card's out-of-scope path literals verbatim in the composed text for 805/958 (card, path) occurrences (84.0%; heuristic — paraphrases like "docs, CI, examples" count as misses). Notably the composer reads the RAW ledger, not the exported rendering, so it is not subject to the exporter's 8-path cap: `nushell-t01 r7` lists `crates/nu-protocol/**` explicitly — an entry the export block hides behind "(+3 more)".
- **What it drops.** Uniformly: the `pylgrim:begin/end` markers, the managed-block notice, the `[observe]` mode tags, the Skills footer, and the full-ledger pointer. The E9 result (mode tags inert on drift) suggests the tag loss is behaviorally neutral, but the dropped markers mean a repo-hygiene layer (managed-block detection, staleness tooling) would not recognize a composed block.
- **Key risk finding — content not traceable to the ledger.** Three of the eleven artifacts contain material traceable to NEITHER the ledger NOR the prompt: (1) `click-t01 r7` invents the technical detail "when `echo_via_pager=False` and `color=False`" — `echo_via_pager` appears nowhere in the ledger, prompt, or repo instructions; (2) `nushell-t01 r7` and `r9` invent a test command (`cargo test -p nu-command --lib http`) never stated anywhere; (3) worst, `hono-t02 r7` CORRUPTS an exact oracle literal: the acceptance criterion's expected Location header `%E3%81%93%E3%82%93%E3%81%AB%E3%81%A1%E3%81%AF` (こんにちは) is reproduced with a duplicated `%E3%81%AB` (こんににちは) — a wrong expected value handed to the agent as ground truth. The same card's r7/r8 also append "Implementation Guidance" pseudo-logic ("if url contains non-ASCII characters, encode") that contradicts its own invalid-percent criterion (`%hello` is pure ASCII yet must become `%25hello`). All three hono-t02 reps still passed the deterministic oracle — the agent implemented correct encoding despite the corrupted literal — so the fidelity failures did not convert to outcome failures HERE, but a composed packet that silently mutates ratified acceptance criteria is exactly the failure mode the ledger exists to prevent, and nothing in the compose path would catch it.

## Is the smart-compose dial worth a registered study?

On this evidence, no — not as a replacement for the deterministic export block. Behaviorally the two packets are indistinguishable at probe grade (drift 3/48 vs 1/48, M5 44/48 vs 42/48, judged-met 78.8% vs 78.0% — every delta within temporal-gap-plus-noise range), so there is no effect worth the cost of confirming. Economically composition is strictly worse: +$0.0253/run (~7%) against a free deterministic render, plus a per-run LLM dependency in the context path. And on fidelity — the one axis where composition could not merely match but corrupt — it is not clean: a corrupted oracle literal and two invented technical details in eleven audited artifacts is a real, recurring hallucination rate in the exact artifact whose job is to carry ratified intent verbatim. If composition is ever revisited, the registered question should not be "composed vs export on a clean ledger" (this probe suggests that answer is "no difference, at a cost") but whether composition earns its keep where the deterministic exporter cannot go — messy, unratified, or oversized ledgers — and any such study needs a fidelity gate (composed content mechanically checked against ledger literals) as a primary endpoint, because the failure mode observed here is silent. Until then, the free block wins by default.

