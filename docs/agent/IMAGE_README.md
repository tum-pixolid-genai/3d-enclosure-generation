# Image-to-Design v0.1

An isolated local vision prototype for Pixolid Group 08. PNG or JPEG pixels
and optional English instructions are sent to a local vision model and
converted into the existing Design Spec v0.1 JSON. The result contains the
original model reply, draft, corrections, evidence, questions, and capability
decision. CAD generation requires independent review.

image_agent/demo.html and image_agent/demo_server.py are OPTIONAL LOCAL
DEMO / TEST HARNESS files for Agent acceptance only. They do not replace
Yujia's official Frontend or Peicen's production Backend. Authentication,
persistence and production approval lifecycle remain Backend responsibilities.

The current November 20 demo uses primary Prompt v0.1.3 and a second visual
inventory with its own Prompt. See READINESS_DEMO.md for the combined
Text/Image demonstration and IMAGE_AGENT_INTEGRATION_HANDOFF.md for team
integration. Every image CAD action requires an explicit reviewer approval
bound to the exact result hash.

## Environment

The tested target is Windows x64 with an RTX 3070 Ti Laptop GPU (8 GiB),
Python 3.14.8, and the existing short-path CadQuery environment. This project
reuses that environment's jsonschema 4.26.0 and Pillow 13.0.0.
The shared validation snapshot and its hashes are in shared/ and
shared-source-hashes.json. The original Text-to-Design directory is separate.

The approved local model is qwen3-vl:4b-instruct-q4_K_M, sourced from the
official Ollama registry. It includes 2,497,888,288 bytes of quantized language
weights and an 839,325,760-byte visual projector, with 3,337,225,445 total
layer bytes. Its manifest SHA-256 is
84f7ed8042fa7cdbd902f7dcb7d0370e032095047cc3244179f263b77b5bc318.
The verified model license is Apache-2.0. Ollama's source license is MIT.
Runtime version 0.40.16 is reused from the existing standalone installation.
Runtime and weights reside outside the project directory.

Official references:

- https://ollama.com/library/qwen3-vl:4b-instruct-q4_K_M
- https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct
- https://docs.ollama.com/capabilities/vision

## Run locally

Start the vision-only runtime in a new PowerShell terminal if it is down.
These settings are process scoped.

```powershell
$base = Join-Path $env:LOCALAPPDATA 'PixolidVision'
$env:OLLAMA_HOST = '127.0.0.1:11441'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_MODELS = Join-Path $base 'models'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
& (Join-Path $env:LOCALAPPDATA 'PixolidLLM/bin/ollama.exe') serve
```

From this project's root, run tests and fresh model experiments:

```powershell
$py = Join-Path $env:LOCALAPPDATA 'PixolidMvp/venv-20261116-141057/Scripts/python.exe'
$results = Join-Path $env:LOCALAPPDATA ('PixolidVision/runs/' + [guid]::NewGuid())
& $py -B -m unittest discover -s tests -v
& $py -B -m image_agent.run_examples --output-dir $results
& $py -B -m image_agent.vision_agent examples/open.png --task-id MY-IMAGE --instructions 'Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.' --output-dir $results
```

Every CLI task uses a new subdirectory and preserves previous files.
The experimental JSON envelope is local to this module. design_spec
conforms to the unchanged shared v0.1 output Schema. The input image limit
is 10 MiB and 16 to 2048 pixels per side. Images are transmitted as base64
to 127.0.0.1:11441 only. Requests have a 120-second socket timeout and no
automatic fallback or retry. A failed attempt remains part of the report.

## Evidence boundaries

Board identity and wall thickness require accompanying text in this version.
Image-only requests cannot supply engineering scale or physical fit.
Generic visual cutouts use port_type unknown and require identification.
Unlabelled camera pose does not establish the physical coordinate frame.
Visual evidence is model-reported and needs independent review. Text/image
conflicts and unrepresented features require clarification.

The capability check reuses the existing module to list unsupported lids,
openings, and external wall mounting. A positive automatic CAD decision is
converted to review_required for image-based drafts. The optional CAD smoke
test is a separate, explicitly reviewed operation.

## Development fixtures and provenance

examples/ contains four original synthetic technical diagrams and five
development cases, including one shared image with accompanying board and
wall instructions. make_sketches.py created the diagrams deterministically.
The cases contain image hashes and proposed reference answers. Independent
teammate review is pending. No original course PDFs, photographs, personal
images, private notes, or downloaded third-party artwork are included.

Contributed code and documentation follow LICENSE (Apache-2.0). Eligible
contributed diagrams and reference annotations follow CC BY 4.0 to the extent
contributors hold the relevant rights. Credit Qianshun Gu and preserve the
provenance statement. Codex assisted with implementation, testing,
documentation, and synthetic fixture preparation under contributor review.
Runtime, model, and other third-party content retain their original licenses.
The development examples do not establish general vision reliability.

See DEVELOPMENT_RESULTS.md for the observed model runs, status-score
correction, current errors, GPU use, and reviewed CAD smoke result.
To reproduce the supported single-case CAD smoke after reviewing its
image and result:

```powershell
& $py -B -m image_agent.approve_result (Join-Path $results 'IMG-05-result.json') --output (Join-Path $results 'approval.json')
& $py -B -m image_agent.cad_smoke (Join-Path $results 'IMG-05-result.json') --output-dir (Join-Path $results 'cad-smoke') --approval-file (Join-Path $results 'approval.json')
```

## Final QA and proposed repository layout

The final local suite has 33 tests. Full review/API tests additionally use
requirements-qa.txt and Node.js; the core extraction requirements remain
jsonschema and Pillow. The fixed QA review instance is on 8021. An older
8011 Python process must be deliberately restarted before reuse.

Subsequent real headless Chrome acceptance verified groups A through E:
unapproved generation, input invalidation, unresolved images, controlled
provider failures, refresh, separate tabs and delayed responses. The positive
CAD regression reused the exact previously approved result via CLI; it was
not a new browser approval. A one-line reset fix clears obsolete completion
status after input changes, with a failing-before/passing-after regression.

Publication is a proposal only. In the proposed stacked repository, reuse
the root agent/ package from the Text Agent branch instead of publishing
the local shared/ snapshot. Place these image documents in docs/agent/,
the requirements under image_agent/, and the development data license at
examples/DATA-LICENSE. Run tests and image_agent commands from repository
root. Install image_agent/requirements-qa.txt for full offline QA.

The earlier start_readiness_demo.ps1, verify_* scripts, DEVELOPMENT_RESULTS.md,
frozen evaluation cases, and Text experiment/ server are local evidence or
orchestration, excluded from this minimal publication proposal. Commands
referring to those files describe this local workspace, not a fresh public
checkout. Portable extraction and the optional image review API remain the
reviewable module; production integration belongs to the team Backend.

For optional approved CAD, PIXOLID_INTEGRATION_ROOT can select a source root
containing backend/ and geometry/. The loader supports either team component
worktrees or packages in a shared repository. Without that variable it uses
packages in the current repository, or the existing sibling MVP worktrees.
Native CAD needs separate CadQuery/OCP/OCCT dependency and license review;
underlying OCCT and CasADi include LGPL terms. They are not extraction
requirements and their binaries are not proposed for publication here.
