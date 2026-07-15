# Judge calibration record

Date graded: 2026-07-15. Grader: Sam (founder), per prereg §judging.
Sheet: `judge-calibration-sheet.md` / graded CSV
`judge-calibration-sheet-completed.csv` (100 items, sample seed 42, drawn
from pilot judge runs; blind: run ids hashed, judge verdicts withheld at
grading time).

## Result

- Graded items: 100/100 (0 skipped)
- Raw agreement: **0.850**
- Cohen's kappa: **0.626** — clears the pre-registered 0.6 bar, narrowly.
- Consequence: the judged criteria-satisfaction metric (M5 secondary)
  reports as **human-calibrated secondary**, not demoted to exploratory.

Confusion (rows = human, cols = judge):

| | judge met | judge not_met | judge cannot_judge |
|---|---|---|---|
| human met (77) | 73 | 0 | 4 |
| human not_met (0) | 0 | 0 | 0 |
| human cannot_judge (23) | 0 | 11 | 12 |

## Disagreement pattern

Every disagreement (15/100) lies on the evidence-sufficiency line. The
human grader used cannot_judge for criteria asserting runtime facts a diff
cannot exhibit (suite-wide passes, exact runtime output); on 11 of those 23
items the judge committed to not_met instead. The judge is therefore
stricter than the human on thin evidence. For claims built on judged-met
rates this is the conservative direction; judged not_met rates over
runtime-fact criteria should be read with this asymmetry in mind.

## Disclosures

1. **Grading mode.** The founder graded the blind sheet solo, per the
   pre-registered protocol (grade from the sheet's criterion + diff alone).
   Notes use five shorthand rationale classes rather than per-item prose;
   they record the rationale category, not per-item analysis.
2. **Family bias.** Grader is human; judge is Claude-family, agents under
   test are Claude-family. The self-preference limitation stands as written
   in the prereg; this calibration is the mitigation, not a cure.
