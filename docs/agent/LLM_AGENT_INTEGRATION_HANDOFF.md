# LLM Agent v0.2 integration handoff

Prepared on 2026-11-19 for Peicen Xu and Shanning Xu.

## Python interface

Run from the isolated Text-to-Design project root, with jsonschema 4.26.0
and the local Ollama service available on 127.0.0.1:11439.

```python
from agent.hardened_agent import HardenedAgent
from agent.llm_agent import AgentError, LLMAgent

agent = HardenedAgent(LLMAgent())
request = {
    "task_id": "design_unique_backend_id",
    "request_text": "Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.",
    "language": "en",
}
result = agent.extract(request)
draft = result.design_spec
gate = result.capability
# Call Geometry only when gate["allow_geometry"] is True.
```

The Backend assigns a unique task ID and validates request.schema.json.
HardenedAgent validates the final draft using design_spec.schema.json.
Both files remain v0.1. The returned draft uses the original task_id.
The outer result stores the raw model draft, semantic corrections, issues,
and capability decision separately from the shared contract.

| Result | Backend action |
| --- | --- |
| gate.status = allow | Forward the validated draft to Geometry. Check CAD validity and exports before exposing artifact URLs. |
| clarification_required | Return needs_clarification and questions. Skip Geometry and artifact publication. |
| unsupported | Return unsupported and every item in gate.unsupported. Skip Geometry and artifact publication. |
| review_required | Return review_required and review_reasons. Skip automatic generation. |
| AgentError | Use error.code to distinguish invalid_request, unsupported_language, model transport failures, malformed JSON, and invalid schema. No automatic Mock fallback. |

The current experimental HTTP wrapper maps invalid input to 422, model
HTTP or connection failures to 503, and malformed or invalid model output
to 502. Its business refusals use HTTP 200 with an explicit status.
Confirm these mappings with Peicen before adopting them in production.
The experiment reuses team.create_design and run_geometry by substituting
the Agent and output directory inside a separate process. A production
injection interface should be explicit and owned by Backend.

## Geometry boundary

The Agent extracts requested values. An allow decision does not assert CAD
validity. For example, 0.5 mm remains in the draft and the existing Geometry
minimum of 1.2 mm rejects it. Board dimensions and connector coordinates are
Geometry reference data. The Pi 4 height reference and physical fit require
separate confirmation.

T004 must retain a removable lid, front USB and Ethernet openings, and two
external wall mounting holes. The gate returns unsupported with four
entries. Rejections expose no CAD URLs. The experimental download allowlist
only publishes completed tasks from the current process and rejects seeded
old files even when their filenames match a rejected task.

The gate uses bounded English patterns for independent source checks. It
can require review for free-form requirements. Semantic corrections are
logged beside the model draft and must stay visible in evaluation.

## Reproduction and evidence

From the isolated project root:

```powershell
& '.venv/Scripts/python.exe' -B -m unittest discover -s agent/tests -v
$py = Join-Path $env:LOCALAPPDATA 'PixolidMvp/venv-20261116-141057/Scripts/python.exe'
$run = Join-Path $env:LOCALAPPDATA ('PixolidLLM/hardening/run-' + [guid]::NewGuid())
& $py -B -m experiment.server --run-dir $run --port 8001
# In another PowerShell window, using the same run directory:
& $py -B -m experiment.acceptance --run-dir $run --port 8001
& $py -B -m experiment.acceptance --run-dir $run --port 8001 --holdout
```

The API port must be available. Existing report files are preserved.
Ollama uses qwen3:4b-instruct, Q4_K_M, context 4096, temperature 0,
seed 42, and a 120-second socket timeout. The verified model digest is
0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0.

Historical 2026-11-16 run evidence is under:

- %LOCALAPPDATA%/PixolidLLM/hardening/run-20261116-174522-67e5ef/development-acceptance.json
- %LOCALAPPDATA%/PixolidLLM/hardening/run-20261116-174522-67e5ef/holdout-acceptance.json

That run verified 9 development HTTP cases, 8 new holdout cases, four
controlled model-service failure cases, and seeded stale-file rejection.
IT-01 STEP readback found one valid solid, 91 x 62 x 22 mm, with four PCB
standoffs. The eight-case holdout had raw model exact agreement 3/8 and
grounded agreement 8/8. This is a small local test with synthetic references
and does not establish unrestricted language reliability or physical fit.
The prior 46-test result covers offline regression and controlled mocks.
On 2026-11-19, the 46 offline tests were rerun and passed. Both historical
acceptance reports were read and contained zero recorded assertion errors.
The original Prompt and frozen evaluation file hashes remained intact.
Current HTTP service availability should be checked before the team demo.

## Agreements needed

Peicen should confirm the production Agent selection and dependency injection,
timeouts, concurrency, business statuses, error mapping, and artifact
publication lifecycle. Shanning should confirm the active capability list,
board data revision, coordinate frame, mechanical defaults, and CAD checks.
Qianshun owns the model and Prompt versions, semantic corrections and
traceability. New input types, including images, need a separately agreed
request envelope while retaining the existing Design Spec output.

## Final QA addendum, 2026-11-20

Final QA uses isolated Text API 8022 and Image API 8021, with the verified
local models on 11443. Set LLMAgent(port=11443) for that environment.
Default module port 11439 remains usable when its service is started.

Remote main still contains only LICENSE and README. PRs 1 through 5 are
open Drafts. The isolated Agent gate does not prove that the team Backend
uses it. Peicen must adopt the gate before Geometry in production,
including T004 rejection instead of delivering an incomplete box with warnings.

The proposed Text change is stacked above Agent PR 1. The proposed Image
change depends on it and reuses its agent package and Schema. The local
image shared/ snapshot should be omitted from publication.

The local frozen/holdout data should stay private in this first publication
proposal pending Xiaolong's release decision. Previously inspected sets
cannot become a new final untouched benchmark. The optional native CAD
stack needs team licensing review, including OCCT LGPL-2.1 and its exception.

## Attribution

Code and documentation follow the project Apache-2.0 license. Eligible
contributed evaluation data follows the existing provenance and CC BY 4.0
scope. Qianshun Gu reviews development with ChatGPT and Codex assistance.
