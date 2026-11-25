
# Backend — FastAPI Integration

## Overview

This module provides the FastAPI backend for the Pixolid
3D Enclosure Generation project.

It connects the Text-to-Design Agent with the Geometry
and Automatic Checks module.

## Features

- REST API implemented using FastAPI
- Automatic task ID generation
- Agent request and output validation
- Geometry validation and CAD generation
- STEP download and STL preview endpoints
- Configurable Mock or local Qwen text extraction
- Automatic Swagger API documentation

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Basic API health check |
| POST | /design | Process a design request |
| GET | /design/{task_id}/download | Download a generated STEP file |
| GET | /design/{task_id}/model.stl | Download the STL preview |
| POST | /design/pi4-assembly | Generate and verify the Raspberry Pi 4 reference assembly |
| GET | /design/pi4-assembly/{task_id}/{artifact} | Download an assembly STEP, STL, or verification report |

## Installation

From the repository root, create and activate a
Python virtual environment.

Install the backend dependencies:

    python -m pip install -r backend/requirements.txt

## Development Setup

The current prototype depends on Agent PR #1 and
Geometry PR #2. This integration checkout also needs Text Agent PR #6
for its text capability checks and Qwen adapter.

Until those modules are merged, they can be checked
out into separate Git worktrees:

    git fetch origin
    git worktree add --detach ../pixolid-text-review origin/feature/text-agent-llm-v02
    git worktree add --detach ../pixolid-geometry-review origin/feature/geometry-checks

On Windows PowerShell, from the repository root:

    $env:PYTHONPATH = (Resolve-Path ..\pixolid-text-review).Path + ";" + (Resolve-Path ..\pixolid-geometry-review).Path

If both source directories are already in the integration checkout,
Python can import them from the repository root.

Start the backend:

    python -m uvicorn backend.main:app --reload

API documentation:

    http://127.0.0.1:8000/docs

The default Agent mode is `mock`. To select Qwen, start a local Ollama
instance with the `qwen3:4b-instruct` model and set its port before
starting Uvicorn. The Text Agent's default port is `11439`.

    $env:PIXOLID_TEXT_AGENT = "llm"
    $env:PIXOLID_OLLAMA_PORT = "11439"

Submit a Pi 4 smoke request to `POST /design`:

    {"prompt":"Design a rectangular enclosure for Raspberry Pi 4 with no lid."}

The open case has an expected exterior size of 91 × 62 × 23.6 mm
with the current 17.6 mm board height and default 2 mm walls.
A clarification, unsupported feature, or review requirement returns a
business status and the capability decision with no CAD links. A local
model transport error returns HTTP 503 and invalid model output returns
HTTP 502.

## Raspberry Pi 4 assembly

Download the [Raspberry Pi 4 Model B layout STEP](https://www.innerscene.com/tools/library/3d-parts/raspberry-pi-4-model-b-layout-821bd96d).
Save it as `../pixolid-demo-outputs/reference-models/raspberry-pi-4.step`,
or set `PIXOLID_PI4_REFERENCE_STEP` to the absolute path of the downloaded file.

Submit this text request to `POST /design` to generate the assembly:

    {"prompt":"Design a rectangular enclosure for Raspberry Pi 4 with a screwed lid, automatic port cutouts, and 2 mm wall thickness."}

This path supports rectangular Pi 4 enclosures with a screwed lid. Wall
thickness can be omitted to use 2 mm or explicitly set to 2 mm. Port cutouts
are derived automatically from the reference STEP. A request for named ports,
specific opening sides, external wall mounting holes, another lid style, or
another wall thickness is outside the supported assembly scope. The assembly
response also carries the extracted `design_spec` and `capability` decision.
The usual text-design download and preview URLs serve the enclosure, and
`downloads` includes the separate lid and verification report.

In Swagger, call `POST /design/pi4-assembly` with no request body. This route
uses the reference STEP to generate automatic port cutouts with 0.5 mm
clearance and a screw-fastened lid. It runs without Ollama.

The response includes `task_id`, `status`, `assembly_validated`,
`verification_summary` and `verification_metrics`. The metrics include the
collision volumes in mm³, PCB hole alignment and maximum deviation in mm,
and lid fastener alignment and count. When the status is `generated`, the
`downloads` object contains relative URLs for both STEP files (`enclosure`,
`lid`), both STL previews (`enclosure_stl`, `lid_stl`), and the JSON
verification `report`. Use those URLs through the same Backend base URL or
frontend proxy that handled the request.

A failed geometry check returns `geometry_blocked` with the verification
summary. A missing reference STEP returns HTTP 503. The verification covers
CAD geometry and collisions. Physical fastener fit, connector access, and
printing tolerances require separate testing.

## Regression tests

With pytest installed, run from the repository root:

    python -m pytest -q backend/tests

The tests call the backend routes with the Mock and a fixed Qwen response,
generate temporary CAD files, and verify unsupported requests stop before
Geometry. They require neither a running backend server nor Ollama.

## Local image review

The optional image routes use Image Agent PR #7. Install
`image_agent/requirements.txt`, then pull the vision model into the local
Ollama service used by the backend.

    ollama pull qwen3-vl:4b-instruct-q4_K_M
    $env:PIXOLID_IMAGE_AGENT_PORT = "11434"
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001

Use your local Ollama port if it differs from 11434. Set the image port
before starting Uvicorn to register the image routes. The service is
intended for loopback use and `reviewer` is a local audit alias.

| Method | Endpoint | Request or result |
|--------|----------|-------------------|
| POST | /image | JSON with `filename`, `image_base64`, and optional `instructions`. Returns the design draft and its `source_result_sha256`. |
| POST | /image/{task_id}/approve | After reviewing the exact image and draft, submit `approved: true`, `reviewer`, and the matching `source_result_sha256`. A successful review returns both CAD URLs. |
| GET | /image/{task_id}/step | Download the reviewed STEP file once both exports exist. |
| GET | /image/{task_id}/stl | Download the reviewed STL file once both exports exist. |

For the positive sample, use `examples/open.png` with
`Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.`
Review the returned draft and visual evidence before approving. Sending the
same image without instructions exercises requests that need clarification.

Each successful extraction creates a separate task under the CAD output
directory's `image_reviews` folder. Approvals are single-use. If generation
fails after recording an approval, submit a new task and review its result.

## Current Limitations

- Agent and Geometry need separate worktrees until the component PRs are merged
  or the sources are included side by side in a local integration checkout.
- Physical fit and printability are not fully verified.
- Live image inference requires the separate Qwen3-VL model in Ollama.

## Status

Draft prototype — not yet ready for production or merge.
