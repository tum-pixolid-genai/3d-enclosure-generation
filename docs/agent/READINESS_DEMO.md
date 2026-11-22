# November 26 readiness demonstration

Run these commands from the isolated Image-to-Design project directory.
The existing short-path Windows CAD Python environment and two verified
local models are reused. The preparation created a dedicated model store
using hardlinks to the already-downloaded blobs. No new weights are needed.

## Start

    ./start_readiness_demo.ps1

This prints its fresh run directory. Dedicated ports are 11443 (Ollama,
local-only, one loaded model), 8012 (Text API), and 8011 (image review UI).
If a demo is already running, use it instead of starting a second instance.
The original team MVP ports are 8000/5173. A non-listening original port
means the service is not currently started; it does not diagnose a failure.

## A and D: Text-to-CAD and T004 refusal

Open http://127.0.0.1:8012/docs, POST /design, and use:

    {"prompt":"Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness."}

Expect generated and current task STEP/STL URLs. For T004 use:

    {"prompt":"Design a rectangular enclosure for Raspberry Pi 4 with a removable lid, USB and Ethernet openings on the front, and two wall-mount holes."}

Expect unsupported, four unsupported feature entries, no Geometry call,
and 404 at both task artifact routes.

CLI verification, with a fresh output directory:

    $py = Join-Path $env:LOCALAPPDATA 'PixolidMvp/venv-20261116-141057/Scripts/python.exe'
    $out = Join-Path $env:LOCALAPPDATA ('PixolidVision/readiness/check-' + [guid]::NewGuid())
    & $py -B verify_text_demo.py --output-dir (Join-Path $out 'text')

## B: Image-to-JSON

Open http://127.0.0.1:8011/. Upload examples/open.png or examples/ports.png.
Inspect the image, Design Spec, two observations, and review state.
No CAD action occurs during upload or extraction.

CLI:

    & $py -B -m image_agent.vision_agent examples/open.png --task-id DEMO-IMAGE --instructions 'Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.' --port 11443 --output-dir $out

## C: Explicitly reviewed Image-to-CAD

In the browser, inspect the displayed image and all JSON/evidence. Enter
the reviewer's name, check the approval box, and press the CAD button.
Only a supported, sufficiently specified draft can generate after approval.
The STEP and STL download links belong to that approved task.

For CLI approval, inspect the original image and the result first:

    & $py -B -m image_agent.approve_result (Join-Path $out 'DEMO-IMAGE/result.json') --output (Join-Path $out 'approval.json')

The reviewer must enter a name and type APPROVE. Then:

    & $py -B -m image_agent.cad_smoke (Join-Path $out 'DEMO-IMAGE/result.json') --output-dir (Join-Path $out 'image-cad') --approval-file (Join-Path $out 'approval.json')

No approval is inferred from earlier requests or from merely running the
image extraction. Each approval binds the exact result hash.

## Tests and evidence

    & $py -B -m unittest discover -s tests -v
    & $py -B -m image_agent.run_examples --port 11443 --output-dir (Join-Path $out 'development')
    & $py -B -m image_agent.run_examples --port 11443 --cases evaluation/readiness_holdout/cases.json --output-dir (Join-Path $out 'evaluation')

The six-case evaluation contains five new original images, with one reused
across image-only and image-plus-text inputs. It was frozen before inference.
Its results did not guide further model or evidence-policy adjustments.
The earlier five cases remain development cases.

The 2026-11-20 evidence root is:
%LOCALAPPDATA%/PixolidVision/readiness/run-20261120-094545-7fab35

It contains development (an unsuccessful first audit policy), development-final,
evaluation, text-demo, approved-image-cad, and HTTP demo evidence.
Approved image CAD includes Qianshun's explicit approval and exact source hash.
The historical-hashes.json manifest is used to verify older raw experiments.

Browser automation did not connect successfully in this session. HTTP page
serving, actual upload/inference, and approval rejection were tested separately.
The human browser click-through and independent reference review remain tasks
for the team before the internal meeting.

## Final QA instance

The corrected Image API is running separately at http://127.0.0.1:8021/.
Text QA uses http://127.0.0.1:8022/docs. Both use the verified local models
on 11443. Older Python services do not reload patched code automatically.
Use the fixed QA instance or restart an old demo deliberately before reuse.

For a new controlled run, start from the relevant workspace and supply
a fresh output directory:

    # From Text workspace
    & $py -B -m experiment.server --run-dir <fresh-text-directory> --port 8022 --ollama-port 11443
    # From Image workspace, in another terminal
    & $py -B -m image_agent.demo_server --run-dir <fresh-image-directory> --port 8021 --model-port 11443

The full Image QA suite uses FastAPI, Uvicorn, Pydantic and Node.js in
addition to the core requirements. requirements-qa.txt pins the Python
test/API dependencies. Native CAD is optional and uses the team's verified
CadQuery environment, subject to its licensing decision.

The manual positive browser result reported by Qianshun is retained
separately from automated negative HTTP/page-handler tests. No new manual
negative browser-click claim is made by final QA.

Subsequent browser acceptance completed A through E using existing
Playwright and real headless Chrome on 8021. The earlier connection failure
above records the old automation attempt, not a current browser blocker.
The suite is now 33 tests, including a stale-status reset regression.
Controlled model faults/delayed replies and the exact-approved native CLI
replay are separate evidence categories. No production module is replaced.
