"""OPTIONAL LOCAL DEMO / TEST HARNESS for Agent acceptance.

Not Peicen's production Backend or Yujia's official Frontend.
Loopback image upload, explicit review, and approved CAD downloads only.
"""

import argparse
import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import Lock
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, StrictBool
import uvicorn

from agent.agent import save_design
from agent.llm_agent import AgentError
from .cad_smoke import run as generate_cad
from .vision_agent import VisionAgent


PAGE = Path(__file__).resolve().parent / "demo.html"


class ImageRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    image_base64: str = Field(min_length=1, max_length=14_000_000)
    instructions: str = Field(default="", max_length=2000)


class Approval(BaseModel):
    approved: StrictBool
    reviewer: str = Field(min_length=1, max_length=100)
    source_result_sha256: str = Field(min_length=64, max_length=64)


def create_app(run_dir, model_port):
    run_dir.mkdir(parents=True, exist_ok=False)
    app = FastAPI(title="Pixolid image review demo")
    agent = VisionAgent(port=model_port)
    tasks = {}
    mutex = Lock()

    @app.get("/", response_class=HTMLResponse)
    def home():
        return PAGE.read_text(encoding="utf-8")

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "image_review_demo", "ollama_port": model_port}

    @app.post("/image")
    def image(body: ImageRequest):
        suffix = Path(body.filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            raise HTTPException(422, "Select PNG or JPEG.")
        try:
            data = base64.b64decode(body.image_base64, validate=True)
        except (ValueError, binascii.Error) as error:
            raise HTTPException(422, "Invalid image encoding.") from error
        task = "image_" + uuid.uuid4().hex
        directory = run_dir / task
        directory.mkdir()
        path = directory / ("input" + suffix)
        path.write_bytes(data)
        try:
            result = agent.extract(path, task_id=task, instructions=body.instructions)
        except AgentError as error:
            failure = {"task_id": task, "error": error.code, "message": str(error),
                       "raw_reply": error.raw_reply, "usage": error.usage}
            save_design(directory / "error.json", json.dumps(failure, indent=2))
            service_codes = {"ollama_connection_error", "ollama_timeout", "ollama_http_error"}
            http = 422 if error.code in {"invalid_image", "invalid_request"} else 503 if error.code in service_codes else 502
            return JSONResponse(failure, status_code=http)
        target = directory / "result.json"
        save_design(target, json.dumps(result, indent=2) + "\n")
        checksum = hashlib.sha256(target.read_bytes()).hexdigest()
        tasks[task] = {"directory": directory, "checksum": checksum, "published": False,
                       "input_path": path, "image_sha256": result["image"]["sha256"]}
        return {"task_id": task, "source_result_sha256": checksum, "result": result}

    @app.post("/image/{task}/approve")
    def approve(task: str, body: Approval):
        if task not in tasks:
            raise HTTPException(404, "Unknown image task.")
        state = tasks[task]
        if not body.approved or not body.reviewer.strip() or body.source_result_sha256 != state["checksum"]:
            raise HTTPException(409, "Explicit approval must match the displayed result.")
        directory = state["directory"]
        with mutex:
            if (hashlib.sha256((directory / "result.json").read_bytes()).hexdigest() != state["checksum"]
                    or hashlib.sha256(state["input_path"].read_bytes()).hexdigest() != state["image_sha256"]):
                raise HTTPException(409, "The reviewed result or source image changed. Extract and review again.")
            if (directory / "approval.json").exists():
                raise HTTPException(409, "This approval has already been processed.")
            record = {**body.model_dump(), "approved_at_utc": datetime.now(timezone.utc).isoformat()}
            save_design(directory / "approval.json", json.dumps(record, indent=2))
            try:
                exported = generate_cad(directory / "result.json", directory / "cad", directory / "approval.json")
            except (SystemExit, OSError, AssertionError) as error:
                return JSONResponse({"status": "blocked", "detail": str(error)}, status_code=422)
            state["published"] = True
            state["artifact_hashes"] = exported["files"]
        return {"status": "generated_after_review",
                "step_url": f"/image/{task}/step", "stl_url": f"/image/{task}/stl"}

    @app.get("/image/{task}/{extension}")
    def download(task: str, extension: str):
        state = tasks.get(task)
        if not state or not state["published"] or extension not in {"step", "stl"}:
            raise HTTPException(404, "No approved artifact for this task.")
        artifact = state["directory"] / "cad" / f"{task}.{extension}"
        if (not artifact.is_file() or hashlib.sha256(artifact.read_bytes()).hexdigest()
                != state["artifact_hashes"][extension]["sha256"]):
            raise HTTPException(404, "The approved artifact is missing or changed.")
        return FileResponse(artifact,
                            media_type=f"model/{extension}", filename=f"{task}.{extension}")

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--port", default=8011, type=int)
    parser.add_argument("--model-port", default=11443, type=int)
    args = parser.parse_args()
    if args.port in {8000, 8001, 5173, args.model_port}:
        parser.error("Choose a separate demo port such as 8011.")
    uvicorn.run(create_app(args.run_dir, args.model_port), host="127.0.0.1", port=args.port)
