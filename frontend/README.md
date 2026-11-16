# Frontend prototype

A small web page for the 3D enclosure pipeline: enter a request, see the status, the design spec, the automatic check results and a 3D preview. Built with Vite, plain JavaScript and three.js.

## Run

Requires Node.js (LTS).

```
npm install
npm run dev
```

- `http://localhost:5173/` runs in **mock mode**: the "Mock result" dropdown picks a fake response in the same shape as the real `POST /design` response.
- `http://localhost:5173/?real` talks to the **real backend**. Start the backend on port 8000 first. `vite.config.js` forwards `/design` and `/health` to `http://127.0.0.1:8000`, so no CORS setup is needed.

## Files

- `index.html`: page structure
- `src/main.js`: page logic, 3D viewer (three.js), backend call
- `src/mock.js`: mock responses
- `src/style.css`: styles
- `vite.config.js`: dev proxy to the backend

## What the page uses from the backend

- `POST /design` with `{"prompt": "..."}`
- `status`, `task_id`, `design_spec`, `geometry_result` (`valid`, `dimensions`, `errors`, `warnings`)
- `model_url` and `GET /design/{task_id}/model.stl` for the 3D view and the STL download
- `GET /design/{task_id}/download` for the STEP download
- `GET /health` for the "Real backend: online" label

## Known limits

- The real 3D model is loaded from `model_url` (`GET /design/{task_id}/model.stl`). In mock mode, and if `model_url` is missing, the page draws a stand-in box from `geometry_result.dimensions`.
- "AI says the case works" shows "not reported yet" until the retry loop returns `ai_claim`.
- Check results are shown as the `errors` and `warnings` lists. Per-check results (`checks: [{name, passed, message}]`) would allow a per-check pass/fail view.
- The download buttons give the STEP file (`/design/{task_id}/download`) and the STL file (`model_url`).
