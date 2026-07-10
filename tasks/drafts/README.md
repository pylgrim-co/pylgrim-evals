# Gold-set drafts — RATIFIED 2026-07-10 (see tasks/RATIFICATION-LOG.md)

All 72 drafts were accepted (with reviewer edits) under founder-delegated
adversarial review and moved to tasks/. The per-repo RATIFICATION.md and
DECISIONS.md files below are the audit trail; the YAMLs now live in tasks/.

72 cards across 10 repos (each: T-real from closed issue + merged PR with
base = PR parent; T-bait authored on pre-existing temptations at the corpus
pin). All validate with zero errors; ids unique. Per-repo evidence and open
questions live in each repo's RATIFICATION.md. Nothing here enters tasks/
(the frozen card set) without explicit per-card ratification.

| repo | cards | fail-at-base verified | flagged for the sitting |
|---|---|---|---|
| zustand | t05 + b01-b03 | t05 both directions; b01 both directions | t05/t03 both devtools type fixes; tests/** protection breadth |
| click | t05 + b01-b03 | t05 on host | src-touching bait (b01) wanted?; b03/t04 shared surface |
| sql-formatter | t01-t05 + b01-b03 | 2 of 5 | see RATIFICATION.md |
| hono | t01-t05 + b01-b03 | t03, t04 | pre-projects-split bases use plain vitest invocations |
| zod | t01-t05 + b01-b03 | t02, t03, t04 | packages/mini mirror scoping |
| rich | t01-t05 + b01-b03 | 2 of 5 | see RATIFICATION.md |
| prettier | t01-t05 + b01-b03 | ALL FIVE + 2 flip-to-pass | t03-t05 vendor yarn 4.17.1 (corpus pin 4.17.0) — corpus note needed |
| eslint | t01-t05 + b01-b03 | t01 (20 fail), t05 (5 fail) | t04 contamination-weakest (Jan-2026 dates), swap candidates listed |
| hugo | t01-t05 + b01-b03 | t01-t03 | see RATIFICATION.md |
| nushell | t01-t05 + b01-b03 | t01 (5-min compile budget) | t02/t03/t05 pre-cutoff issue text; t04 issue-filed-after-PR provenance |

Contamination doctrine reminder: pre-cutoff dates are recorded honestly per
card and reported per docs/10 §8 (threat 3); they are disclosure items, not
automatic rejections.
