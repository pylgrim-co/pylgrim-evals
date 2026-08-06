# E-coord wall-clock memo: the O3 binding projection

**DESIGN MEMO. Not a confirmatory analysis.** This is the §7 O3 freeze gate of `preregistration/design-e-coord-draft-3.md`: the measured-latency projection of the confirmatory drain, as amended by the §3 composition amendment — **432 episodes (48 scenarios × 3 arms × 3 reps) at episode concurrency 2 on the pinned Hetzner VM (CPX32, Ubuntu 24.04)**. Computation code: `analysis/ecoord_wallclock.py` (seed 42). All inputs re-derived from `results-vm/*.db` and `results-vm/episodes/*/episode.json`. Written 2026-08-06.

## Answer in one line

The 432-episode confirmatory drain projects to **~1.1 calendar days of pure drain at concurrency 2 (p10 1.0 / p90 1.2)** on measured Haiku episode walls, plus ~0.2 days of judge drain — call it **2-4 calendar days end-to-end under realistic subscription contention**; the §7 fallback levers are pre-committed but almost certainly unnecessary (ledger-reps=2 saves ~0.1 days, R=4 saves ~0.04).

## Measured inputs

### Per-turn wall (instrumented `wall_s`; Haiku episodes only — the Sonnet pilot predates the instrumentation)

| phase | n turns | mean | median | p10 | p90 | max |
|---|---|---|---|---|---|---|
| haiku re-pilot | 118 | 54s | 31s | 8s | 137s | 283s |
| cal strata | 51 | 72s | 36s | 10s | 194s | 290s |
| confirmatory subset | 80 | 61s | 32s | 8s | 157s | 345s |
| **all haiku** | **249** | **60s** | **33s** | **8s** | **154s** | **345s** |

The distribution is right-skewed: a median turn is half a minute, the p90 is ~2.5 minutes, and the worst observed turn is under 6 minutes. Turn walls trend slightly longer at the harder strata, as expected.

### Turns per episode

Haiku: mean 6.6, median 6, p10 4, p90 10, max 12 (n=38 episodes; cap 2×R=12). Sonnet: mean 9.9, median 10 (n=18 JSON artifacts) — sonnet agents use materially more of the cap. Expected confirmatory volume at the haiku rate: **432 × 6.6 ≈ 2,830 CLI completions**, inside the §7 planning band.

### Per-episode wall (DB `started_at` → `finished_at`, per phase)

| phase | n | mean | median | p10 | p90 | drain span | effective concurrency | pauses |
|---|---|---|---|---|---|---|---|---|
| sonnet pilot | 36 | 2,184s | 1,462s | 234s | 4,507s | 3.23 h | 6.75 (anomalous, see below) | 0 |
| haiku re-pilot | 18 | 365s | 347s | 278s | 454s | 1.83 h | 1.00 (serial) | 0 |
| cal strata | 8 | 467s | 512s | 298s | 588s | 1.04 h | 1.00 (serial) | 0 |

### Install/outcome overhead (episode wall minus sum of instrumented turn walls)

Mean **8s per episode** (n=26 DB-covered haiku episodes; median 6-9s, max 15s). Worktree setup, merge-tree materialization, and the ≤120s-capped outcome commands are collectively negligible against ~6-8 minutes of turn wall — the §3 rule-4 wall-time floor is doing its job.

### Sonnet fallback (pre-instrumentation): DB-timestamp recovery, and an anomaly

Turn stamps are completion checkpoints, so consecutive-stamp diffs recover per-turn wall (validated against `wall_s` in the haiku DBs, where episode start + Σstamps reproduces the walls exactly). Applied to the sonnet pilot DB this yields median 11s / mean 21s per turn and ~3-minute episode active spans — **inconsistent by an order of magnitude with the same DB's episode walls (median ~24 min)**, and the episode intervals overlap up to 18-deep in the 3.23h span, contradicting the 2-way concurrency the §7 O9 amendment records. The sonnet timing rows look like a batched import; they are flagged UNRELIABLE and excluded from the projection. (A file-provenance note for the record: the local `episodes.db` is the sonnet pilot DB per its own meta; the local `episodes-pilot-sonnet.db` copy is empty; the confirmatory-subset episodes have JSON artifacts but no local DB.)

## Projection: 432 episodes at concurrency 2

Model: per-stratum episode-wall pools from the hardest available on-VM haiku data — high from the 4 certified confirmatory-subset high episodes (Σturn wall + overhead; mean 394s), very-high and extreme from the calibration DB walls (means 420s and 514s) — composed 108/162/162 per the amendment, arms treated as exchangeable (pilot arm means 344-370s, within noise of control). Double bootstrap (resample each 4-episode pool, then draw the composition; 4,000 reps, seed 42) for the band; serial seconds ÷ 2 for concurrency 2, which the sonnet pilot's amendment evidence (36/36, zero lock failures at 2-way) licenses and the projection assumes holds at 432.

| design | episodes | calendar days at concurrency 2 | p10 / p90 | serial equivalent |
|---|---|---|---|---|
| **base (48 × 3 arms × 3 reps)** | 432 | **1.12** | **1.01 / 1.22** | 2.24 |
| lever: ledger-arm reps = 2 | 384 | 1.00 | 0.91 / 1.09 | 2.00 |
| lever: R = 4 (measured −3.4% turn wall) | 432 | 1.08 | — | 2.17 |
| both levers | 384 | 0.97 | — | 1.94 |

**Judge drain add-on:** ≤ 2 × 432 = **864 verdicts at the observed ~3.5 verdicts/min from prior drains ≈ 4.1 h (0.17 days)**, additive (the judge runs after episode capture).

**Fallback levers, restated verbatim from §7 (pre-committed, in order, and only these):** (1) R = 4; (2) ledger-arm reps = 2. Their measured calendar value is small — R=4 removes only the 3.4% of haiku turn wall spent in turns 9-12 (haiku episodes mostly finish early; the lever's real value is capping sonnet-class blowup, not saving haiku time), and ledger-reps=2 saves ~0.11 days (11% of episodes) — so **neither lever should fire on this projection**; they stay in the prereg as insurance.

**Sensitivity — the model pin.** This projection is Haiku-based, consistent with the calibration data the composition amendment is fitted on; draft-3 §5 still names sonnet as the model, and the freeze must resolve that pin (same flag as the power memo). If the drain ran sonnet: taking the sonnet pilot's episode walls at face value despite the timing anomaly (mean 2,184s) gives 432 × 2,184 / 2 ≈ **5.5 calendar days** of pure drain, plus longer episodes (10 turns) pushing the completion count toward ~4,300; the honest sonnet number would need re-measurement with `wall_s` instrumentation on a few certified scenarios before freeze.

## Caveats

- **Subscription contention (the binding one).** The drain shares Max-subscription capacity with Sam's interactive use; every measured drain above ran in a quiet 1-3h window with **zero rate-limit pauses**, and a 1-day continuous drain will not get that. Pause-not-abort gate semantics (§2 O2) make contention a calendar tax, not a validity threat, but the honest expectation is **2-4 calendar days end-to-end** (drain + judge + contention), not 1.1. The §7 "6-10+ week" fear was priced for sonnet-class turns pre-pilot; measured haiku reality is two orders gentler.
- Pool thinness: the very-high/extreme wall pools are 4 control-arm episodes each; the bootstrap band reflects that but cannot see effects it never sampled (e.g. treatment-arm slice composition at hard strata lengthening turns — pilot evidence at low pressure says it doesn't).
- Concurrency-2 speedup is taken as exactly 2× on API-bound turns; CPU contention on the 4-vCPU host during simultaneous outcome commands could shave this, bounded by the 8s/episode overhead measurement.
- Zero-pause, zero-defect extrapolation from 62 episodes to 432; the §5 rerun-not-drop rule absorbs defects at a calendar (not validity) cost.
