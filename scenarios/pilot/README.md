# E-coord PILOT scenario set

Six scenarios for the E-coord pilot (design-e-coord-draft-3.md §6):
36 pilot episodes / 3 arms / 2 reps = **6 scenarios**, drawn from the two
ratified pilot repos (corpus.yaml `pilot: true`: zustand, click), three per
repo spanning the low/medium/high overlap-pressure strata. **Pilot scenarios
are permanently excluded from confirmatory analysis** — they exist to
calibrate instruments (turn cap R, C2 shingle threshold, judge κ, control-arm
C1 base rates for the §5a power memo, per-turn latency for the §7 wall-clock
memo), so the set spans the difficulty range honestly rather than clustering
where an effect is likeliest.

## Stratum table (as authored)

Pressure score = files in the intersection of the two reference solutions'
read-plus-write neighborhoods (touched files plus direct importers/importees
at the pinned SHA, §3 rule 2), computed mechanically by
`scripts/scenario-check.sh`. Churn = added+deleted lines per reference diff;
rule 3 requires the ratio within 3x.

| scenario | repo | stratum | pressure score | co-written files | churn a/b | ratio |
|---|---|---|---|---|---|---|
| ecoord-pilot-zu01 | zustand | low | 2 | none | 48/50 | 1.04 |
| ecoord-pilot-zu02 | zustand | medium | 12 | src/middleware.ts | 71/77 | 1.08 |
| ecoord-pilot-zu03 | zustand | high | 14 | src/vanilla.ts | 63/65 | 1.03 |
| ecoord-pilot-cl01 | click | low | 3 | none | 39/49 | 1.26 |
| ecoord-pilot-cl02 | click | medium | 9 | none | 69/48 | 1.44 |
| ecoord-pilot-cl03 | click | high | 42 | src/click/types.py, src/click/__init__.py | 64/69 | 1.08 |

Stratum semantics, within each repo:

- **low** — disjoint write surfaces in sibling modules; the neighborhoods
  intersect only in shared read-side files (the §3 rule-2 floor).
- **medium** — a materially larger shared neighborhood; in zu02 both cards
  must co-write the 17-line middleware registry (shared registry/index
  pressure); in cl02 card B's `prompt` calls the exact function card A
  modifies (`echo`).
- **high** — both cards write the same central file(s): zu03 puts both edit
  regions a handful of lines apart inside src/vanilla.ts; cl03 co-writes
  the type catalog AND the package's alphabetical export registry
  (src/click/__init__.py), whose importer fan-in (every `import click`)
  drives the measured score.

Scores are comparable within a repo, not across repos (import-graph density
differs); strata were authored per repo and the measured scores are monotone
low < medium < high in both repos. Threshold pinning for the confirmatory
set happens at freeze, informed by these measurements.

## Pinned SHAs

Repo-level corpus pins from tasks/corpus.yaml (the same SHAs the harness
mirrors carry): zustand `a1f685ca744e56a982b1c5029620e0925c3ee996`, click
`16fc00e2f4a2717a521084f193709a6058afc693`.

## Outcome commands and the 120 s rule

Every outcome command is a scoped single-file test invocation
(`pnpm vitest run tests/coord/<x>.test.ts`, `uv run pytest -q
tests/test_coord_<x>.py`), sized well under the §3 rule-4 <=120 s/tree
floor — no card needed a compromise or a whole-suite run, because the pilot
pair was chosen from light repos precisely so the wall-time floor binds
loosely (the rule is what excludes nushell/hugo-class suites from scenario
sourcing). Definitive timings are measured on the pinned VM host by
`scripts/scenario-check.sh` (which also enforces the k=3 determinism rule,
M6); timings on any other host are advisory.

## Authoring order

Cards (with scope_paths/out_of_scope) were committed before any reference
solution was attempted; reference pairs live at the repo root in
`reference-solutions/`, outside all agent-reachable roots. See
reference-solutions/README.md for the M5 reasoning and the audit command.
