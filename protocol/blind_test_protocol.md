# Physical blind test protocol (draft v0.1)

Goal (Research question 3): do the automatic checks agree with what happens
with a real print? Target from the project description: **at least 100 blind
physical tests, checks and prints agreeing in at least 90% of cases, with
uncertainty reported.** Desktop 3D printing only; no user studies, no personal data.

## Roles

| Role | Does | Must not know |
| --- | --- | --- |
| Test selector | Picks which cases to print (see sampling) | n/a |
| Printer | Slices and prints, records print problems | n/a |
| Blind checker | Assembles the case and fills in the log | What the automatic checks or the AI predicted |
| Analyst | Joins log with predictions after all rows are locked | n/a |

The selector and analyst may not be the blind checker.

## Procedure

1. **Freeze predictions.** Export, for every selected case, the automatic check
   result and the AI's "done / not done" claim into `predictions.csv`. Commit
   it before any print is judged.
2. **Sampling.** At least 100 cases. Include passing and failing cases (do not
   print only cases the checks like), spread over all 4 boards and categories.
   Suggested: ~50% predicted pass, ~50% predicted fail.
3. **Print.** Same printer, material and slicer profile for all cases; write
   them in `blind_test_log.csv`. Label parts with a random ID, not the task ID.
4. **Blind check** each printed case, recording pass/fail for each item:
   - board inserted (fits in cavity without force)
   - every requested port usable (a real plug can be inserted)
   - lid closes
   - shaken upside down: board stays inside, lid stays on
   - printed OK at all (if not: note why; "print failed" is its own outcome)
5. **Lock** the log, then the analyst joins it with `predictions.csv`.

## Analysis

- Agreement = share of cases where predicted overall pass/fail equals measured.
  Report a 95% confidence interval (e.g. Wilson), not only the point value.
- Report separately: false "pass" (checks said OK, print failed) and false
  "fail". A false pass is the dangerous one.
- Also report AI "done" while measured fail (Research question 2).
- Cost and time per working case from `cost_log.csv`.

## Files

| File | Use |
| --- | --- |
| `blind_test_log.csv` | One row per printed case, filled by the blind checker |
| `predictions.csv` | Written by the pipeline, committed before judging (columns below) |
| `cost_log.csv` | Time and API/print cost per case |
| `shape_register.csv` | Third-party and student shapes, with licence and consent |

`predictions.csv` columns: `test_id, task_id, checks_overall_pass, ai_claims_done, retries_used`.

## Licence and compliance checklist

- [ ] Repository code: Apache-2.0 from day one
- [ ] Data (benchmark, logs): CC-BY-4.0
- [ ] Only AI models whose licences permit use in the EU
- [ ] Downloaded 3D models only under CC0 or CC-BY (recorded in `shape_register.csv`)
- [ ] Student-made shapes published only with written consent
- [ ] Only permissively licensed dependencies (check on each new `requirements.txt` entry)
- [ ] No personal data, no user studies
- [ ] Pixolid credited as industry mentor; no Pixolid code or confidential data used
- [ ] Catalog text only cited, not copied into the open data
