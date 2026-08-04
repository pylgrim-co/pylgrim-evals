# E-coord GATE-CALIBRATION scenario set

8 scenarios in two overlap-pressure strata ABOVE the confirmatory set's
low/medium/high ladder. They exist for one purpose: measuring the
CONTROL-ARM COLLISION BASE RATE at pressure levels the current corpus
lacks (pilot + confirmatory produced 0-17% control collisions, below the
design's 20% gate floor). They are calibration instruments and are
PERMANENTLY EXCLUDED from confirmatory analysis (`status: calibration`;
confirmatory analysis selects `status: confirmatory` only).

The §3 authoring rules of `preregistration/design-e-coord-draft-3.md`
remain binding — in particular rule 1: every scenario ships a committed
region-disjoint reference pair whose `git merge-tree` is clean. Collision
is always EVITABLE; these strata only raise how tempting it is.

The M5 cards-before-solutions audit trail applies: the scenario YAMLs in
this directory were committed before any `reference-solutions/ecoord-cal-*`
directory existed; the reference pairs land in a strictly later commit.

Run the mechanical checks with the confirmatory-style override:

```
SCENARIO_DIR=scenarios/calibration scripts/scenario-check.sh <mirrors-dir>
```

NOTE (freeze input): `harness/src/harness/episode.py` currently pins
`PRESSURE_STRATA = ("low", "medium", "high")`. Ingesting this set through
`plan-episodes` requires the freeze to extend that tuple with
`"very-high"` and `"extreme"`; scripts/scenario-check.sh itself does not
gate on the stratum label.

## Stratum definitions (freeze input)

These definitions are the ones the calibration strata were authored
against and are recorded here for the freeze:

- **very-high** — both cards' natural implementations gravitate to the
  SAME function or contiguous code region (not merely the same file):
  e.g. both add cases to one switch/dispatch table, or both modify the
  same exported config object — while a region-disjoint solution pair
  STILL exists (e.g. one card can be satisfied via a separate helper or
  module the file already imports, or by appending in a distinct region
  of the same structure). The temptation to collide is the default path;
  the escape requires care.
- **extreme** — maximum honest pressure: both cards explicitly require
  edits to the same small file (under ~100 lines) or the same
  registry/index structure, with acceptance criteria that reference
  overlapping behavior, while the committed reference pair proves
  disjointness is achievable (e.g. careful line placement, one card's
  refactoring-free append vs the other's targeted in-place edit in a
  different region of the same file). Collision is NOT unavoidable —
  rule 1 (region-disjoint reference pair with clean merge-tree) is still
  binding.

## Stratum table

| Stratum | Expected | Actual | Scenarios |
|---|---|---|---|
| very-high | 4 | 4 | ho01, sf01, zo01, zu01 |
| extreme | 4 | 4 | ho02, sf02, zo02, zu02 |

## Per-repo spread (pinned SHAs identical to the confirmatory set)

| Repo | Pinned SHA | Scenarios |
|---|---|---|
| hono | `d6b1d32a697ef9ba9f5036753fe9bde1121c0ff9` | ho01, ho02 |
| sql-formatter | `b2ce5459c1861eac394a20ac69c7f222a5cebd95` | sf01, sf02 |
| zod | `912f0f51b0ced654d0069741e7160834dca742ee` | zo01, zo02 |
| zustand | `a1f685ca744e56a982b1c5029620e0925c3ee996` | zu01, zu02 |

## Why the default path collides (one line per scenario)

Churn = added + deleted lines per reference diff (`git apply --numstat`
sums against the pin). All 8 pairs sit within the §3 3x bound; the
measured ratio range across the set is **1.00 - 1.10**.

| Scenario | Stratum | Churn a/b (ratio) | Why the default path collides |
|---|---|---|---|
| ecoord-cal-ho01 | very-high | 33/30 (1.10) | Both cards add entries to the one alphabetized `_baseMimes` object in src/utils/mime.ts, and strict alphabetical placement interleaves their keys in the same 'm' block (m4a/mkv beside md) while the lazy path appends both at the object tail. |
| ecoord-cal-ho02 | extreme | 51/53 (1.04) | Both cards rework the same three tiny regions of the 78-line src/http-exception.ts (options type, constructor, getResponse's no-res branch) with criteria that overlap on the very Response getResponse() builds. |
| ecoord-cal-sf01 | very-high | 31/34 (1.10) | Both cards add an identically-shaped enum guard whose natural home is the same insertion point inside the single validateConfig() body, inviting one shared allowed-values loop or back-to-back if-blocks on the same lines. |
| ecoord-cal-sf02 | extreme | 37/39 (1.05) | Both cards add a dialect alias whose registry route co-writes the one dialectNameMap Record type-annotation line (the key union) plus neighboring alphabetical map slots, with near-verbatim overlapping acceptance criteria. |
| ecoord-cal-zo01 | very-high | 38/38 (1.00) | Both cards follow the identical two-file format recipe whose default insertion point is the same tail of the classic/schemas.ts format-factory block and the same tail of core/regexes.ts (adjacent-line appends in two shared regions). |
| ecoord-cal-zo02 | extreme | 37/36 (1.03) | Both cards register a case-insensitive twin beside its sibling in the 32-line classic/checks.ts registry, where `startsWith` and `endsWith` sit on directly adjacent lines, and add mirror factories twelve lines apart in core/api.ts. |
| ecoord-cal-zu01 | very-high | 72/74 (1.03) | Both cards extend the selector form inside the SAME ~20-line wrapped-subscribe closure of subscribeWithSelectorImpl and must widen the SAME four-line options type literal. |
| ecoord-cal-zu02 | extreme | 76/73 (1.04) | Both cards add a near-twin state-change observer middleware and must both write the 17-line src/middleware.ts registry, whose lazy insertion point (append at end) is identical for both. |

All 8 pairs were verified with git-only checks from the committed diffs:
both diffs `git apply --index` cleanly at the pin,
`git merge-tree --write-tree` of the two branches is conflict-free, both
cards' features are present in the merged tree, every path touched by
either diff exists in the merged tree, and every diff touches only its
card's `scope_paths`. The full §3 re-check (outcome commands with k=3
determinism, wall-time floor, measured overlap-pressure score) is
`scripts/scenario-check.sh` on the pinned VM host
(`SCENARIO_DIR=scenarios/calibration`).
