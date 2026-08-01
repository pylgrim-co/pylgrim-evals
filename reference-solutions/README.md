# Reference solutions (E-coord existence proofs)

Per-scenario reference-solution pairs required by design-e-coord-draft-3.md
§3 rule 1: for every pilot scenario, `card-a.diff` and `card-b.diff` are
unified diffs against the scenario's pinned SHA such that (a) the two diffs
produce a clean `git merge-tree` from the common base and (b) each card's
outcome command passes on its own branch and both pass on the merged tree.
They prove collision is EVITABLE — a control-arm collision is a behavioral
outcome, never forced by construction — and they validate the outcome
commands, exactly as merged PRs ground T-real.

## Authoring order (M5 audit trail)

The task cards (scenarios/pilot/*.yaml, including every `scope_paths` and
`out_of_scope` list) were committed BEFORE any file in this directory
existed; this directory lands in a strictly later commit. Verify with:

    git log --oneline --follow scenarios/pilot/ reference-solutions/

This blocks the leak where knowledge of the reference pair's known-disjoint
split flows backward into `scope_paths`, pre-partitioning the repo for the
agents.

## Location: outside every agent-reachable root (M5)

Episode agents work in worktrees that are slot checkouts of the CORPUS
repositories (zustand, click, ...), materialized under the slots roots from
the bare mirrors in `results/repos/`. No agent worktree is ever a checkout
of pylgrim-evals itself, so nothing under this repository root — including
this directory — is inside any agent-reachable root. `reference-solutions/`
must additionally be listed in the harness's worktree/transcript audit
exclusions (the §2 audit asserts no tool call reaches the reference-solution
store), so that any path escape toward this store is detected and the
episode excluded-and-counted.

Do NOT copy these diffs into any slot, worktree, corpus mirror, or prompt.

## Verification

`scripts/scenario-check.sh <mirrors-dir>` mechanically re-checks all four
§3 rules (clean merge, outcome commands pass with k=3 determinism and the
<=120 s wall-time floor, churn symmetry within 3x, measured overlap-pressure
score). The wall-time floor is defined on the pinned VM host
(docs/ops/vm-setup.md); run the check there before freeze.
