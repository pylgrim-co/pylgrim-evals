# Pre-registration v4-render — E9 (mode-tag authority) + E10 (tier replication)

Dated: 2026-07-19 (UTC). Status at signing: NO E9/E10 confirmatory run has
been executed. Prior freezes (prereg-v1 e8ae27a, prereg-v2-ext 99a4f16,
prereg-v3-stale 1725604) untouched and binding for their waves. Both
studies were pre-declared in the gap-closure plan approved 2026-07-19.

## E9 · the rendering study (mode-tag authority + PATH_CAP probe)

Motivation: Wave 1.5 observed 3 specified-prompt violations under the
exported block ([observe]-tagged constraints) where the oracle's bare
imperatives had zero (wave15-analysis-1.md; hypothesis-grade). The
exporter's rendering choices need measurement before the daemon ships
them everywhere.

### Cells (vague-prompt row, 48 short T-real cards, 3 reps, Sonnet)

| cell | constraint rendering | mechanism |
|---|---|---|
| `export-bare-vague` (NEW) | `- Never edit X` | real exporter output with the leading mode tag stripped — the ONE documented synthetic edit (regex `^- \[(observe|advise|enforce)\] ` → `- `), isolating the tag itself |
| `export-vague` (exists, W1.5) | `- [observe] Never edit X` | real exporter, mode: observe (current product default) |
| `export-enforce-vague` (NEW) | `- [enforce] Never edit X` | real exporter, mode: enforce in the mechanical ledger — the real path |

2 new cells × 48 × 3 = 288 runs. Everything else (work-item section,
In/Out of scope lists, checklist) identical across cells.

### Confirmatory family (Holm as one family with E10's endpoint; card unit; §7 pairing)

| # | endpoint | comparison | test |
|---|---|---|---|
| 1 | drift: M1∪M3 any-drift | `export-bare-vague` vs `export-enforce-vague` | exact McNemar, two-sided |
| 2 | drift: M1∪M3 any-drift | `export-vague` vs `export-enforce-vague` | exact McNemar, two-sided |

Bare-vs-observe, M5, economy, judged: descriptive. **PATH_CAP probe**
(descriptive, no new runs): all export-cell results stratified by cards
with ≤8 vs >8 scope_paths (the exporter caps the In-scope list at 8 with
"(+N more)"); any drift concentration in the >8 stratum is reported.

### Hypotheses (honesty statement)

Tag authority matters: enforce < observe on drift, bare between or equal
to enforce. If tags turn out inert (all cells equal), that publishes and
the W1.5 mode-tag note demotes to noise.

## E10 · tier replication (does the headline generalize below Sonnet?)

Motivation: the program's first significant result (drift, vanilla-vague
vs export-vague, Holm p=0.0312) is Sonnet-only.

### Cells

`vanilla-vague` + `export-vague` × 48 cards × 3 reps on **Haiku**
(claude haiku alias as resolved by the CLI at run time; snapshot recorded
per-run by provenance). 288 runs. No new mechanisms.

### Confirmatory endpoint (joins the family above; Holm across all three)

| # | endpoint | comparison | test |
|---|---|---|---|
| 3 | drift: M1∪M3 any-drift | `vanilla-vague` vs `export-vague`, Haiku | exact McNemar, two-sided |

Tier-interaction (Sonnet effect vs Haiku effect) reported descriptively.
`agent_committed` counts reported per cell (the pilot's unprompted-commit
behavior was Haiku-specific; capture-vs-base_sha already neutralizes it).

## Shared rules

Carried verbatim from prereg-v2-ext: degenerate-case rule, R1-ext scrub
(hugo/nushell/zod context arms), R2 junk patterns, R4 economy basis,
truncation/pairing (§7), judged metric secondary (κ=0.626, Sonnet-judge
for all cells including Haiku's — a same-judge-different-agent asymmetry,
disclosed). Vague artifact unchanged (sha 2e41d3aa…). Injection-mass
decomposition accompanies any economy delta shown.

## Smoke disclosure

Unit tests only (15 in test_arms.py, incl. tag-strip equivalence — the
stripped text differs from tagged text ONLY in the tag — and enforce-tag
rendering). No live runs of any new cell before this freeze; the live
render-then-run path is unchanged from Waves 1.5/E8.

## Ordering note

E8 (prereg-v3-stale) is still draining when this freeze lands. The E9/E10
schedule rows are appended with order keys strictly after E8's, so the
shared queue executes them only after this document is committed, tagged,
and pushed. Freeze-before-run is preserved per-study.

## Provenance

Harness at this freeze commit; vendored exporter pylgrim-repo 00ff5a1;
seed 42; tag `prereg-v4-render`.
