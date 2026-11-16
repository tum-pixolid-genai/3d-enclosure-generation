# Non-AI Baseline, Benchmark and Statistics (draft, 16 Nov 2026)

```
benchmark/   tasks.json (200 tasks), generate_tasks.py, README.md
baseline/    template_baseline.py        non-AI template: structured form -> design spec
stats/       analyze.py                  Wilson CI, exact McNemar, blind-test agreement, "false done"
             run_spec_stage.py           runs mock agent + baseline over all tasks
             spec_stage_results.csv      400 rows (200 tasks x 2 conditions)
protocol/    blind_test_protocol.md + CSV templates (blind log, cost log, shape register)
```

Run (needs `jsonschema` only if you also run the Agent; Python 3.10+):

```
python stats/analyze.py --selftest
python stats/run_spec_stage.py --tasks benchmark/tasks.json \
       --agent-dir <path to repo>/agent --out stats/spec_stage_results.csv
python stats/analyze.py blind --log protocol/blind_test_log.csv --pred protocol/predictions.csv
```

## First measured results (design step only, mock agent from PR #1)

Scope: request text -> design spec. No geometry, no prints. 184 standard tasks.

| Condition | Spec equals expected |
| --- | --- |
| Mock agent, Raspberry Pi 4 | 45/46 = 97.8% (95% CI 88.7-99.6%) |
| Mock agent, Pi 3B+ / Pi Zero 2 W / Arduino Uno | 0/138: mock only recognises Pi 4 |
| Template baseline, all 4 boards | 184/184, **by construction** (it reads the structured fields); a ceiling, not a result |

- Clarification tests, Pi 4 only: 4/4 asked instead of guessing (n is tiny; CI 51-100%).
  For the other boards the mock "asks" only because the board is unknown, so those 12 are not counted.
- The one Pi 4 miss is **BM-PI4-034**: "...with no lid and power openings on the left."
  The parser loses the power opening after "no lid". Report to the Agent owner.
- Geometry spec-level check (cadquery stubbed, no STEP files): accepts 46/46 Pi 4 specs and
  rejects all 138 for other boards (no board data). Warnings on the accepted specs say lid,
  port alignment and wall-mount holes are not implemented, so "valid" is not "works".

## Not done / not measured yet

- No STEP/STL generation was run here (CadQuery not installed in my environment).
- No real LLM was called; "AI" above is the rule-based mock. No retry loop, so no "claims done" data yet.
- No physical prints. Blind-test tooling is ready but untested on real data.
- Pi 4 data checked against the official mechanical drawing; port lists for the other three boards are from general knowledge and still need checking.
- Open question for Geometry: Pi 4 USB/Ethernet sit on the short edge and power/HDMI on the long edge, so some "same wall" requests may be physically impossible; board orientation to be confirmed.
- Comparison to a *geometric search* baseline (for irregular shapes) is not started.

## Licence and provenance

Code in `baseline/`, `stats/` and `benchmark/generate_tasks.py` follows the repository's
Apache-2.0 licence. `benchmark/tasks.json`, `stats/spec_stage_results.csv` and the CSV
templates are data and follow the repository's CC BY 4.0 data licence. The benchmark requests
are synthetic and adapted from the example scenario in the TUM GenAI Project Catalog, Project 02.
The scripts use only the Python standard library (running the Agent also needs `jsonschema`).

## GenAI assistance

Claude (Anthropic) assisted with drafting the benchmark generator, baseline, statistics scripts
and protocol text. Xiaolong Wen reviewed the output and is responsible for it.
