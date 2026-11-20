# Text-to-Design Agent

This isolated development copy includes the original Mock and an opt-in
local LLM prototype. See [Local LLM Agent v0.2](#local-llm-agent-v02) for
runtime and experiment instructions.

The original Mock extracts enclosure requirements from a small set of English request patterns. It validates inputs and outputs against the proposed v0.1 JSON Schemas. The contract is open for review by Agent, Backend, and Geometry.

## Run on Windows

The supported target is Python 3.14.x. Verification used Python 3.14.8 and jsonschema 4.26.0.

From the repository root, install the module's pinned direct dependency in your Python environment:

```powershell
python -m pip install -r agent/requirements.txt
```

Run the tests and generate new examples in a fresh temporary directory:

```powershell
python -B -m unittest discover -s agent/tests -v
$pixolidRun = Join-Path ([IO.Path]::GetTempPath()) ("pixolid-agent-" + [guid]::NewGuid())
python -B agent/agent.py --output-dir $pixolidRun
python -B agent/agent.py examples/complex_request_T004.json --output-dir $pixolidRun
python -B agent/validate_output.py (Join-Path $pixolidRun "T004_design_spec.json")
```

Relative input and output paths resolve from the module directory. From inside agent/, use python -B agent.py, python -B validate_output.py and python -B -m unittest discover -s tests -v with the corresponding arguments.

With no input argument, the CLI uses the T001 request. It writes to agent/outputs/ by default. The first run in a fresh checkout succeeds. A repeat with the same destination exits with code 3 and leaves the saved result intact. Use a fresh --output-dir for a separate run. The module ignores its generated outputs and Python caches.

| Exit code | Meaning |
| --- | --- |
| 0 | A structurally valid design was saved or the validator accepted a saved design |
| 1 | Input or design failed validation |
| 2 | CLI usage, file read, UTF-8 decoding, JSON parsing, or Schema configuration error |
| 3 | The output already exists or could not be written |

## Supported patterns

Start with a simple instruction such as “Make a rectangular case for Raspberry Pi 4 with a removable lid, USB and Ethernet openings on the front, and two wall-mount holes.” Use with to introduce features. A semicolon can separate a negative clause from a subsequent positive clause.

| Feature | Supported examples |
| --- | --- |
| Board and enclosure | Raspberry Pi 4 with optional rectangular before case or enclosure |
| Lid | a lid, removable lid, snap-fit lid, screwed lid, no lid, without a lid |
| Connector openings | USB, Ethernet, HDMI, and power. A list can share an explicit front, back, left, right, top, or bottom side. |
| External wall mounting | A nonnegative integer or zero through ten before wall-mount hole(s) or wall-mounting hole(s) |
| Wall thickness | 2 mm wall thickness or wall thickness of 2.5 mm |

The Mock asks for clarification on recognized conflicts and unrecognized clauses. Port exclusions trigger clarification because the draft schema lacks an exclusion field. The parser can miss nuance in free-form requests, alternative requirements, or nested negation. Port counts and unit conversions are outside its supported patterns.

## Integration boundary

The CLI validates requests and designs. For a future Python integration, extract_design(request) takes a validated request and returns a draft without file I/O. Backend should check needs_clarification and review the semantic requirements before forwarding a draft to Geometry. A successful CLI exit or SCHEMA PASS verifies structure only. T004's board, lid, ports, directions, and wall-mount count are separately asserted in the regression suite.

The team still needs to confirm board data ownership, coordinate frames, port exclusions, error handling, and how the Backend will use task IDs. Requested sides describe user intent. Verified connector dimensions, placement, fit, and printability are Geometry concerns.

## Historical validation fixtures

The archived T001 output is used to test overwrite protection. The T004 fixtures are preserved responses from manual ChatGPT UI sessions. No automated LLM API experiment produced these fixtures.

From the repository root:

```powershell
python -B agent/validate_output.py tests/fixtures/T004_llm_v0.1.json
$LASTEXITCODE
python -B agent/validate_output.py tests/fixtures/T004_llm_v0.2.json
$LASTEXITCODE
```

The saved Prompt v0.1 output gives **SCHEMA FAIL** with six validation errors and exit code 1. The saved Prompt v0.2 output gives **SCHEMA PASS** and exit code 0. The v0.2 output was obtained after an additional display-formatting instruction.

These saved samples do not establish one-shot reliability or a statistically significant improvement. Schema validation checks structure and leaves semantic completeness, geometric feasibility, printability, and physical success unverified. The Mock's 18 passing regression tests cover the documented cases. Free-form natural-language understanding remains outside that evidence.

The old prototype ZIP labels the heading inside `system_prompt_v0.2.md` as v0.1. The active prototype and the copy in this repository use v0.2 in that heading. The heading is the sole line-level difference between the archived and current copies.

## License and provenance

The [repository Apache-2.0 license](../LICENSE) covers the contributed implementation, draft schemas, prompt templates, and module documentation. [CC BY 4.0](DATA-LICENSE) covers eligible contributed test data as described below and only grants rights the contributors can license.

| File | Provenance and attribution | Data license scope |
| --- | --- | --- |
| `examples/my_first_request.json` | Synthetic request prepared by Qianshun Gu (@qianshungu440-droid) for local Agent testing. | CC BY 4.0 for the contributed example. |
| `examples/complex_request_T004.json` | Synthetic request adapted and extended by Qianshun Gu from the example scenario in the TUM GenAI Project Catalog, Project 02, p. 6. | CC BY 4.0 covers eligible original contributions to the adaptation. The grant excludes the catalog's material and any third-party rights. |
| `tests/fixtures/T001_design_spec.json` | Historical output from the local rule-based Mock, preserved in Qianshun Gu's prototype archive. The archived file matches this copy. The exact invocation and source-code revision are unverified. | CC BY 4.0 applies to any rights the contributor holds in this test snapshot. |
| `tests/fixtures/T004_llm_v0.1.json` | Preserved AI-generated response from a historical manual ChatGPT UI session for T004. Qianshun Gu preserved the fixture. | Qianshun Gu authorizes public distribution under CC BY 4.0 to the extent he holds the relevant rights. Third-party rights are outside this grant. |
| `tests/fixtures/T004_llm_v0.2.json` | Preserved AI-generated response from a historical manual ChatGPT UI session for T004, obtained after an additional display-formatting instruction. Qianshun Gu preserved the fixture. | Qianshun Gu authorizes public distribution under CC BY 4.0 to the extent he holds the relevant rights. Third-party rights are outside this grant. |

When reusing data covered by CC BY 4.0, credit the contributor listed above and link to the source and license. Preserve the TUM catalog citation for the adapted request.

The pinned Python dependency jsonschema is MIT licensed. The installed versions of its runtime dependencies attrs, jsonschema-specifications, referencing, and rpds-py also declare MIT.

## GenAI assistance

ChatGPT assisted with planning, prompt engineering, and technical review. OpenAI Codex assisted with implementation, debugging, automated testing, and documentation. Qianshun Gu supervised and reviewed the development process. The current Mock Agent applies deterministic rules to requests. It makes no live model calls.

## Local LLM Agent v0.2

The explicit LLM entry point uses Ollama structured output and validates the
assembled Design Spec against the same v0.1 schema. The application supplies
the task ID, schema version, and mechanical-data caveat. The LLM extracts
requirements from English text. Capability decisions are stored alongside
the extraction, outside the schema. The live MVP still uses the Mock.

### Runtime

Use the official Windows x64 standalone Ollama release v0.40.16 and
`qwen3:4b-instruct` Q4_K_M. The model manifest digest is
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
The [release asset](https://github.com/ollama/ollama/releases/tag/v0.40.16)
`ollama-windows-amd64.zip` has SHA-256
`50fcf5ad54277f2fa5d173ebfc93bcb017adbc0c9ef2314daabc96ca9e6aa64e`.
Weights are Apache-2.0 and the Ollama source is MIT. The repository code
and prompts follow Apache-2.0. Eligible original evaluation data follows
CC BY 4.0 to the extent contributors hold the relevant rights. The new
synthetic requests and reference labels were prepared for Qianshun Gu with
Codex assistance. The IT-04 request retains the TUM Catalog attribution
listed above. Model weights and runtime binaries are external downloads.

For a fresh PowerShell session, start the extracted executable with these
process-scoped settings. Run `serve` only if the isolated server is down.

```powershell
$runtime = Join-Path $env:LOCALAPPDATA 'PixolidLLM'
$env:OLLAMA_HOST = '127.0.0.1:11439'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_MODELS = Join-Path $runtime 'models'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
& (Join-Path $runtime 'bin/ollama.exe') serve
```

If the model is missing, in a second PowerShell window set
`$env:OLLAMA_HOST = '127.0.0.1:11439'` and use
`& (Join-Path $env:LOCALAPPDATA 'PixolidLLM/bin/ollama.exe') pull qwen3:4b-instruct`.
Project requests are sent through the loopback HTTP connection. The Agent
does not use a proxy, follow redirects, or invoke model tools.

### Tests and reproducible runs

From the isolated project root with its `.venv` and pinned dependencies:

```powershell
$py = '.venv/Scripts/python.exe'
$results = Join-Path $env:LOCALAPPDATA ("PixolidLLM/runs/" + [guid]::NewGuid())
& $py -B -m unittest discover -s agent/tests -v
& $py -B -m agent.llm_agent agent/examples/complex_request_T004.json --output-dir $results
& $py -B -m agent.evaluation.run_pilot --output-dir $results
& $py -B -m agent.evaluation.run_pilot --cases agent/evaluation/frozen_cases.json --output-dir $results
```

The CLI takes paths relative to the current directory. Its saved file
contains the Design Spec. Its console result shows the gate. Exit codes
are 0 for an allowed draft, 1 for an invalid request or failed extraction,
2 for input or setup errors, 3 for output errors including overwrite
protection, 4 for clarification, 5 for unsupported features, and 6 when
review is required. T004 should save a draft and exit 5 after successful
extraction. A gate status of allow delegates mechanical validation. A
0.5 mm draft can reach Geometry, which enforces the minimum thickness.

The gate accepts the specified simple open-top design when the original
request matches the independently checked patterns. For other requests
it can list capabilities it recognizes from the draft and request. An
unsupported or unrecognized original request cannot become an approved
design solely because features are missing from model output.

The smoke report covers four known integration prompts. The frozen
report covers 12 synthetic prompts with prewritten reference answers.
Scores count expected structured fields, extra fields, errors, and
case-level exact agreement separately. Clarification scoring checks the
flag and approximate topics by keyword. It can require manual adjudication.
Both methods use the same reference answers. Each LLM item is attempted
once with the fixed settings and 120-second socket timeout in
`llm_agent.py`. Preserve cold-start failures alongside warm measurements.
The JSON reports contain
the raw model answer, measured timing, token counts, loaded model data,
and SHA-256 hashes. Unit tests substitute responses when testing parsing
and transport failures. Pilot runs invoke the actual local model and
stop at the capability gate. Geometry and physical validation are later
steps.

## Isolated LLM-to-CAD experiment

The experimental entry point uses the same local Qwen model and v0.2 Prompt.
Before forwarding a Design Spec, a deterministic check grounds explicit
requirements in recognized English phrases and validates the result against
v0.1. The response includes the raw model draft, grounded draft, differences,
and capability decision. Named exclusions require clarification because
v0.1 has no field for them. Port direction and counts, including omitted
values, are checked against recognized source phrases. Wall measurements
use explicit metric or inch units. Conflicts require clarification.

The automatic route is limited to independently verified simple English
requests. Unrecognized syntax or additional requirements can require review.
CAD capability refusal, clarification, model failure, and Geometry rejection
have distinct statuses. Download routes expose both artifacts only after a
successful export for a request from the current experimental process.

From this isolated project root, with standalone Ollama running on port
11439 and the existing short-path Windows CAD environment available:

```powershell
$py = Join-Path $env:LOCALAPPDATA 'PixolidMvp/venv-20261116-141057/Scripts/python.exe'
$run = Join-Path $env:LOCALAPPDATA ('PixolidLLM/hardening/run-' + [guid]::NewGuid())
& $py -B -m experiment.server --run-dir $run --port 8001
```

The API documentation is at http://127.0.0.1:8001/docs. Send
`{"prompt":"Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness."}`
to `POST /design`. Use the returned task's STEP and STL URLs. This is a
dedicated loopback listener. The server reuses the team's Backend and
Geometry from the adjacent read-only MVP checkouts and injects the hardened
Agent inside its own process.

In a second PowerShell window, use the same absolute `$py` and `$run` values:

```powershell
& '.venv/Scripts/python.exe' -B -m unittest discover -s agent/tests -v
& $py -B -m experiment.acceptance --run-dir $run --port 8001
& $py -B -m experiment.acceptance --run-dir $run --port 8001 --holdout
```

The development suite exercises real Qwen inference and CAD over HTTP.
Controlled invalid replies and upstream HTTP/connection failures are
tested separately on port 8002 with a loopback fault provider. The
fault-only CAD directory includes deliberate stale artifact copies to
test download rejection. The new synthetic holdout is separate from the
previous frozen set. The runner records both raw and grounded scores.
The work evaluates software and geometry only. Physical fit and printing
require independent tests.

## Proposed publication scope, 2026-11-20

The proposed Text Agent v0.2 PR is stacked above Agent PR 1 and retains
the Mock, shared v0.1 schemas and historical fixtures unchanged. Core
extraction, semantic checks, capability gating, unit tests and the four-case
pilot runner are included. Frozen/holdout datasets and the machine-specific
experiment/ HTTP harness remain local pending evaluation release and Backend
integration decisions. Earlier commands mentioning those excluded files
describe this complete local workspace, not the minimal public PR.
The final local 46-test suite passed; seven new real-model HTTP cases are
recorded separately. No production Backend adoption is implied.
