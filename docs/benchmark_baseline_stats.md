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
- Geometry spec-level check, measured on 16 Nov against the earlier Geometry PR #2 (cadquery
  stubbed, no STEP files): accepted 46/46 Pi 4 specs and rejected all 138 for other boards
  (no board data). Geometry has changed since (22 Nov: screw lid, port cutouts, assembly
  verification), so this number is **outdated and should be re-measured**.
  In the current `geometry/checks.py` the spec check still warns "Port alignment has not been
  verified" and "Wall mounting holes are not implemented yet"; the cutouts are computed from the
  STEP file in the separate Pi 4 assembly route, not from the request. "Valid" is not "works".

## Running the benchmark on the real LLM agent (stage 2)

`stats/run_llm_stage.py` sends the Pi 4 tasks through the local Qwen agent
(Agent PR #6: `HardenedAgent(LLMAgent())`) and records, per task:

- whether the design spec equals the expected values (`spec_match`),
- whether the agent "claimed done", meaning it asked no question and did not
  crash (`claims_done`), and whether it was wrong anyway (`false_done`,
  research question 2),
- the capability gate decision (`gate_status`) and any error code.

```
python stats/run_llm_stage.py --tasks benchmark/tasks.json \
       --repo <repo root with agent/llm_agent.py> \
       --boards raspberry_pi_4 --out stats/llm_stage_results.csv
```

It needs a local Ollama server with `qwen3:4b-instruct` (the script uses port 11439 by default;
if Ollama runs on its default port 11434, pass `--port 11434`). `--stub` replaces Qwen with the rule-based
mock to test the script only; stub numbers are not LLM results.
Only Pi 4 is run by default because the Geometry module has board data for
Pi 4 only. Scope: design step only (no CAD, no print).

## Running the benchmark through the real Backend (stage 2)

`stats/run_backend_experiment.py` posts each request to the Backend's `POST /design`
and records the pipeline's own answer (`generated`, `generated_with_warnings`,
`needs_clarification`, `unsupported`, `review_required`, `geometry_blocked`,
`export_failed`), the time per request, and whether the returned design spec equals the
expected values. "System said done" = `generated*`; "false done" = said done while the spec
differs from the expected answer. It starts from the Backend's `/design` endpoint as of
22 Nov (`integration/pi4-assembly`). Only the spec is compared automatically; whether the
CAD really fits is for the Geometry checks and the physical blind test.
Tested only against a stand-in server that used the mock agent, never against the real
Backend, so try it on a few tasks first (`--limit 3`).

Setup (from `backend/README.md` on `integration/pi4-assembly`): `pip install -r
backend/requirements.txt` (fastapi, uvicorn, jsonschema, cadquery), then
`python -m uvicorn backend.main:app`. The Backend's default text agent is the **mock**
(`PIXOLID_TEXT_AGENT=mock`), so this runs without Ollama. For the real model start Ollama
with `qwen3:4b-instruct` and set `PIXOLID_TEXT_AGENT=llm` and `PIXOLID_OLLAMA_PORT=11439`.
The result file must say which of the two was used.

```
python stats/run_backend_experiment.py --tasks benchmark/tasks.json \
       --base-url http://127.0.0.1:8000 --boards raspberry_pi_4 --out stats/backend_results.csv
```

## First end-to-end run through the Backend (23 Nov 2026, mock text agent)

`stats/run_backend_experiment.py` on the 50 Raspberry Pi 4 tasks against the Backend of branch
`integration/pi4-assembly` with its default **mock** text agent (not Qwen). Raw rows:
`stats/backend_mock_results.csv`. Python 3.12, local machine; one run, no repetitions.

| Backend status | Tasks |
| --- | --- |
| unsupported (stopped by the capability gate) | 44 |
| needs_clarification | 5 (the 4 clarification tests + BM-PI4-034) |
| generated_with_warnings | 1 (BM-PI4-004, "...with no lid.") |

- Standard requests (n=46): the Backend said "done" for 1 (2.2%, 95% CI 0.4-11.3%); the returned
  design spec equals the expected one for 45 (97.8%, CI 88.7-99.6%); "said done but spec wrong" 0/1.
- Clarification tests: the mock asked 4/4 (n is tiny; CI 51-100%); the Qwen run below asked 1/4.
- Reading the request is mostly right; the pipeline stops afterwards. The gate currently lets only
  requests with an explicit "no lid" and no ports, no wall-mount holes through (read from
  `agent/capability_check.py` in PR #6): BM-PI4-004 is the only such task in the benchmark.
  Lid, port and wall-mount requests are all answered `unsupported`.
- Time per request: median 0.0 s, max 0.4 s (mock agent, no model call). These are not Qwen times.
- The generated model carries warnings and was neither checked physically nor printed.
  The single "done" says nothing yet about real-world fit.
- Not measured in this mock run: Qwen (see the Qwen section below), retries, other boards, prints.

## Qwen run (23 Nov 2026, real LLM agent, Pi 4 tasks only)

Model `qwen3:4b-instruct` via Ollama on a MacBook (Apple silicon), `PIXOLID_TEXT_AGENT=llm`.
Two runs over the 50 Pi 4 tasks: `stats/run_llm_stage.py` (agent only, with raw model draft
before the rule-based corrections) and `stats/run_backend_experiment.py` (full Backend `/design`).
Files: `stats/llm_stage_results.csv`, `stats/backend_qwen_results.csv`.

Standard requests (46):
- Raw model draft matches the expected spec: 46/46 (100%, Wilson CI 92.3-100%).
  The rule-based corrections changed 0 of 46, so the result is not produced by the corrections.
- Through the Backend: generated 1/46 (2%, CI 0.4-11.3%), the same single task as with the mock
  agent (BM-PI4-004, "no lid"; status `generated_with_warnings`). The other 45 were answered
  `unsupported` by the capability gate. False "done": 0.
- Reason for 1/46: the gate does not pass lid, port or wall-mount requests to `/design` yet.
  So the benchmark is currently limited by the pipeline, not by reading the request.

Clarification requests (4; n is tiny, CI 4.6-69.9% for 1/4):
- Only BM-PI4-047 (conflicting "removable lid and no lid") was actually asked back.
- BM-PI4-048 (VGA port, which does not exist on this board), 049 (vague "nice case") and
  050 (0.08 inch wall thickness) were not asked back by the model. Nothing was generated for
  any of the four, because the gate answered `unsupported` (048, 050) or `review_required` (049).
  So no false "done", but the stop came from the gate, not from the model noticing the problem.

Time per request: median 7.6 s, max 12.6 s through the Backend (total 406 s for 50);
3-17 s per request in the agent-only run.

Limits: one board, one model, one run each (temperature 0, seed 42), tasks written by one person
and not yet reviewed by teammates; the benchmark looks too easy for this model (ceiling) and needs
harder items (paraphrases, vague or conflicting requests, other units). No physical check or print.

## Not done / not measured yet

- No STEP/STL generation was run here (CadQuery not installed in my environment).
- The mock sections above use the rule-based mock; Qwen results are in their own section. No retry loop, so no retry data yet.
- No physical prints. Blind-test tooling is ready but untested on real data.
- Pi 4 data checked against the official mechanical drawing; port lists for the other three boards are from general knowledge and still need checking.
- Open question for Geometry: Pi 4 USB/Ethernet sit on the short edge and power/HDMI on the long edge, so some "same wall" requests may be physically impossible; board orientation to be confirmed.
- Comparison to a *geometric search* baseline (for irregular shapes) is not started.

## Licence and provenance

Code in `baseline/`, `stats/` and `benchmark/generate_tasks.py` follows the repository's
Apache-2.0 licence. `benchmark/tasks.json`, `stats/spec_stage_results.csv` and the CSV
templates are data and follow the repository's CC BY 4.0 data licence. The benchmark requests
are synthetic. Size and example scenario follow the TUM GenAI Project Catalog, Project 02; the task categories are the benchmark author's own design, based on the fields of the Agent's design spec v0.1 (see `benchmark/README.md`, "Design basis").
The scripts use only the Python standard library (running the Agent also needs `jsonschema`).

## GenAI assistance

Claude (Anthropic) assisted with drafting the benchmark generator, baseline, statistics scripts
and protocol text. Xiaolong Wen reviewed the output and is responsible for it.
