# Frontend prototype

A small web page for the 3D enclosure pipeline: enter a request, see the status, the design spec, the automatic check results and a 3D preview. Built with Vite, plain JavaScript and three.js.

## Run

Requires Node.js (LTS).

```
npm install
npm run dev
```

- `http://localhost:5173/` runs in **mock mode**: the "Mock result" dropdown picks a fake response in the same shape as the real `POST /design` response.
- `http://localhost:5173/?real` talks to the **real backend**. Start the backend on port 8000 first. `vite.config.js` forwards `/design`, `/health` and `/image` to `http://127.0.0.1:8000`, so no CORS setup is needed.

Without `?real` the page stays in mock mode, whatever backend is configured.

### Using a backend on another computer

`BACKEND_URL` sets the proxy target, so the page can use a backend someone else is running:

```
# same network; the backend must be started with --host 0.0.0.0 and the port must be open
BACKEND_URL=http://192.168.1.23:8001 npm run dev

# Tailscale Serve: the backend stays on 127.0.0.1 and Tailscale publishes it over HTTPS, no port
BACKEND_URL=https://<machine>.<tailnet>.ts.net npm run dev
```

Open `<BACKEND_URL>/health` in a browser first. It has to answer `{"status":"ok"}` before the page can work. `Connection refused` means nothing is listening on that port: the backend is not running, or it is bound to `127.0.0.1` only. A request that hangs and then times out usually means a firewall is blocking the port.

## Files

- `index.html`: page structure
- `src/main.js`: page logic, 3D viewer (three.js), backend call
- `src/mock.js`: mock responses (text request)
- `src/image.js`, `src/mock_image.js`: image request tab and its mock data (four real image agent outputs)
- `src/assembly.js`: Pi 4 assembly tab
- `src/style.css`: styles
- `vite.config.js`: dev proxy to the backend

## What the page uses from the backend

- `POST /design` with `{"prompt": "..."}`
- `status`, `task_id`, `design_spec`, `geometry_result` (`valid`, `dimensions`, `errors`, `warnings`)
- `model_url` and `GET /design/{task_id}/model.stl` for the 3D view and the STL download
- `GET /design/{task_id}/download` for the STEP download
- `GET /health` for the "Real backend: online" label

## Image request tab

Upload a PNG or JPEG (16 to 2048 pixels per side, up to 10 MiB) with an optional text requirement. The page sends `POST /image` and shows a review screen: the image with the detected openings, the first and the checked design spec, what the agent changed and why, the visual evidence, and the reasons why a review is needed. The approve button stays disabled while the request has unsupported features, open questions or unverified features, or while the text requirement, board or wall thickness is missing. The backend makes the final decision (`POST /image/{task_id}/approve`).

The tab uses `POST /image` (base64 image, instructions) and `POST /image/{task_id}/approve`, which takes `approved: true`, a `reviewer` name and the `source_result_sha256` from the first response, echoed unchanged. After approval the response carries `step_url` and `stl_url`; the downloads answer 404 before approval.

**The image routes only exist when the backend is started with the image agent configured** (`PIXOLID_IMAGE_AGENT_PORT`, pointing at the Ollama port that serves the vision model). Without it `POST /image` answers 404 and the page says so. The vision model also has to be installed on the computer that runs the backend.

A real analysis took 177.7 s in our test (3 min 01 s end to end in the page) and the generation after approval about 3 s, so the page waits up to 300 s for an image request. Text requests use 150 s.

In mock mode the tab shows four real outputs of the image agent (`src/mock_image.js`) instead of calling the backend.

## Pi 4 assembly tab

The button calls `POST /design/pi4-assembly` (no request body). The page shows `assembly_validated` as the automatic-check result, the numbers in `verification_metrics` (collision volume before and after the openings, PCB hole alignment, lid screw hole alignment), the full `verification_summary`, a 3D view of case and lid (from `downloads.enclosure_stl` and `downloads.lid_stl`) and download buttons for `enclosure`, `lid` (STEP), both STL files and `report`. When the status is `geometry_blocked` no files are offered.

The backend needs the Raspberry Pi 4 reference STEP file (see the backend README), otherwise it answers 503. This route is currently on the branch `integration/pi4-assembly`. In mock mode the tab shows the numbers of the first local run and a stand-in model.

## Known limits

- The real 3D model is loaded from `model_url` (`GET /design/{task_id}/model.stl`). In mock mode, and if `model_url` is missing, the page draws a stand-in box from `geometry_result.dimensions`.
- "AI says the case works" shows "not reported yet" until the retry loop returns `ai_claim`.
- Check results are shown as the `errors` and `warnings` lists. Per-check results (`checks: [{name, passed, message}]`) would allow a per-check pass/fail view.
- The download buttons give the STEP file (`/design/{task_id}/download`) and the STL file (`model_url`).
