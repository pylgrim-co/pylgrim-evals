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

1. **Grading mode.** The graded CSV was produced by the founder outside the
   interactive session, using five reusable note templates rather than
   per-item prose; provenance affirmed by the founder on direct challenge
   (2026-07-15). Notes are shorthand rationale classes, not per-item
   analysis.
2. **Test-retest subset.** Ten items (cal-001..010) were also graded live
   in an assisted walkthrough (mechanical diff summaries, no verdict
   steering) before the completed sheet arrived. The completed sheet
   diverges from the live grades on 5 of 10: cal-002/005/006/007
   (live cannot_judge → sheet met) and cal-008 (live not_met → sheet met).
   The completed sheet was ruled authoritative by the grader. Implied
   intra-rater agreement on the overlap is 5/10; this is disclosed as a
   limitation on calibration precision, and it clusters on the same
   evidence-sufficiency line as the human-judge disagreements.
3. **Family bias.** Grader is human; judge is Claude-family, agents under
   test are Claude-family. The self-preference limitation stands as written
   in the prereg; this calibration is the mitigation, not a cure.
