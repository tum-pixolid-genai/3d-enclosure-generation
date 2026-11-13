# Text-to-Design Mock Agent

This prototype extracts enclosure requirements from a small set of English request patterns. It validates inputs and outputs against the proposed v0.1 JSON Schemas. The contract is open for review by Agent, Backend, and Geometry.

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
