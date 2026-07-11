# Gold-set ratification log — Wave 1

**Date:** 2026-07-10
**Card set:** 82 cards (48 T-real, 32 T-bait, 2 positive controls) across 10 repos.

## Authority

Ratification was **delegated by the founder** (Sam Heal), in-channel, 2026-07-10:

> "go, however, i am happy for you to automate what I am meant to ratify. You
> can do this however you want, whether you want to have a new subagent be
> responsible for deciding what to do with each option for each repo, or just
> do it yourself."

Consequence for reporting: the paper and pre-registration describe the gold
set as **author-curated with automated adversarial review**, not
founder-ratified per card. This is already the posture of docs/10 §8
(threat: author-curated tasks; mitigations: freeze-before-runs, published
cards, public harness) — this log strengthens it with an executed-review
audit trail.

## Process

Five adversarial reviewer agents (disjoint from the drafting agents), two
repos each, charged to REFUTE every card by executing checks — never
trusting drafter claims. Rubric: gh identity verification (issue closed, PR
merged, genuine fix), base_sha = merge-commit parent (re-derived
independently), scope fidelity vs the PR's actual file footprint, prompt
leak review, test-command execution under harness-faithful conditions,
criteria judgeability from diff alone, honeypot existence + premise truth at
the pin (byte-level reads), rule/scope-glob coherence, and a decision on
every drafter-flagged open question. Per-repo evidence:
`tasks/drafts/<repo>/DECISIONS.md` (commands + outcomes per check), beside
the drafters' `RATIFICATION.md`.

## Verdicts

**72/72 drafts ACCEPTED (many with reviewer edits), zero rejections.**
All edits were made by the reviewers directly and re-validated (zero schema
errors across the final 82).

## Material refutations (defects that would have corrupted Wave-1 data)

1. **nushell-t05: wrong base_sha.** Pinned a commit a month AFTER the fix
   merged — the cell would have been vacuous. Corrected to the true PR
   parent; every claim re-verified at the new base.
2. **sql-formatter (all 8 cards): test commands failed under real harness
   conditions.** Runs reuse pin-era node_modules at yarn-era bases; pnpm
   v11's verify-deps auto-install dies in the yarn-invoking prepare script.
   Fixed (`--config.verify-deps-before-run=false`) and executed green at all
   five bases. sql-formatter-b03's dist-dependent checks could never pass
   (gitignored dist/ scrubbed each run; Windows build writes invalid JSON) —
   rebuilt with an explicit build prelude and re-executed.
3. **nushell-b03: unfair trap.** Fixing the typo necessarily broke two
   out-of-scope tests asserting the typo'd string verbatim — a guaranteed
   rule violation by construction. Scope repaired.
4. **hugo-t04: false-green test command.** `-run` filter could match zero
   tests and exit 0. Widened.
5. **click-b03: false premise** (tests import via the current path, not the
   deprecated one). Prompt/honeypot/contamination corrected; behaviors
   re-verified independently.
6. **Prompt leaks:** hono-t04 named the ground-truth helper; sql-formatter-t03
   carried the PR's diagnosis. Both softened to behavior-level reports.

## Evidence upgrades

- Fail-at-base is now EXECUTED (not inspected) for all 48 T-real cards'
  deterministic checks or scoped tests, including the five eslint and five
  sql-formatter cards the drafters had not run.
- All bait premises byte-verified at their pins; all honeypot paths exist.
- prettier per-sha vendored-yarn versions confirmed per card (corpus note
  amended alongside this log).

## Analysis-plan notes recorded for the writeup

- Honeypot hits on shared surfaces (e.g. ssrSafe.ts across zustand cards,
  test_parser.py across click cards) are correlated across cards and must
  not be aggregated as independent probes.
- eslint re-verification note: fresh `npm install --ignore-scripts` now hits
  ERESOLVE at some bases (eslint-plugin-jsdoc vs eslint 10 alpha);
  `--legacy-peer-deps` needed for future re-verification. Harness runs are
  unaffected (pin-era node_modules verified at the bases).
- Pre-cutoff issue text on nushell-t02/t03/t05 and boundary dates on
  eslint-t04 / rich-t04 are kept WITH plain-language disclosure in their
  contamination notes; contamination is reported per card per docs/10 §8.

## Freeze

This card set becomes frozen at the pre-registration commit (prereg-v1.md +
sha256 manifest). Any later change goes through the amendments log.

## Amendment 1 (2026-07-11, pre-analysis): fail-at-base disclosure corrected

The "Evidence upgrades" section above overstates: "Fail-at-base is now
EXECUTED (not inspected) for all 48 T-real cards." Audited against the
reviewers' own DECISIONS.md files, the correct accounting is:

- EXECUTED fail-at-base (bug-repro or test-based): 45 of 48 short T-real
  cards + click-l01.
- NOT executed, disclosed by the reviewers and accepted with rationale:
  hugo-t04 (quota), hugo-t05 (deliberate: OOM/hang risk), nushell-t05
  ("expected but unproven" at the corrected base).
- Additionally, 9 frozen contamination notes lag their DECISIONS.md
  verification upgrades (sql-formatter-t03/t04/t05 among them): the frozen
  YAML says not-verified where the reviewer later executed the check. The
  DECISIONS.md files are authoritative for verification status; frozen card
  text is NOT edited post-freeze for this (cards stay byte-identical to the
  manifest); this amendment is the reconciliation of record.
- Related analysis rule: 28/83 cards have do-nothing-green outcome oracles
  (suite green at base, no fix-asserting deterministic check); M5 is
  analyzed split by oracle class per analysis-plan-addendum-1.md R3.

Source: four-lens bias audit, results/reports/bias-audit-1.md.
