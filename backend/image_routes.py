"""Local image extraction, explicit review, and approved CAD downloads."""

import base64
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
from os import environ
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from jsonschema import ValidationError
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from agent.agent import load_validator, read_json, save_design
from agent.capability_check import unsupported_features
from agent.llm_agent import AgentError, DESIGN_SCHEMA, parse_json
from backend.geometry_service import OUTPUT_DIR, run_geometry
from image_agent.vision_agent import MAX_BYTES, VisionAgent


router = APIRouter(prefix="/image", tags=["image"])
REVIEW_DIR = OUTPUT_DIR / "image_reviews"
DESIGN_VALIDATOR = load_validator(DESIGN_SCHEMA)
VISUAL_REVIEW_REASON = "Visual requirements need independent review before CAD."


class ImageRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    image_base64: str = Field(min_length=1, max_length=4 * ((MAX_BYTES + 2) // 3))
    instructions: str = Field(default="", max_length=2000)


class Approval(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    approved: StrictBool
    reviewer: str = Field(min_length=1, max_length=100)
    source_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@lru_cache(maxsize=1)
def get_vision_agent():
    return VisionAgent(port=int(environ["PIXOLID_IMAGE_AGENT_PORT"]))


def task_directory(task_id):
    if not re.fullmatch(r"image_[a-f0-9]{32}", task_id):
        raise HTTPException(404, "Unknown image task.")
    return REVIEW_DIR / task_id


@router.post("")
def extract_image(body: ImageRequest, agent=Depends(get_vision_agent)):
    suffix = Path(body.filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(422, "Select PNG or JPEG.")
    try:
        data = base64.b64decode(body.image_base64, validate=True)
    except ValueError as error:
        raise HTTPException(422, "Invalid image encoding.") from error
    if not 0 < len(data) <= MAX_BYTES:
        raise HTTPException(422, "The image must contain at most 10 MiB.")

    task_id = f"image_{uuid4().hex}"
    filename = "input" + suffix
    try:
        with TemporaryDirectory() as staging:
            path = Path(staging) / filename
            path.write_bytes(data)
            result = agent.extract(path, task_id=task_id, instructions=body.instructions)
    except AgentError as error:
        if error.code in {"invalid_image", "invalid_request"}:
            status_code = 422
        elif error.code in {"ollama_connection_error", "ollama_http_error", "ollama_timeout"}:
            status_code = 503
        else:
            status_code = 502
        raise HTTPException(status_code, {"code": error.code, "message": str(error)}) from error
    except ValidationError as error:
        raise HTTPException(502, "The vision model did not produce a valid design.") from error

    if result["design_spec"]["task_id"] != task_id or result["capability"]["allow_geometry"] is not False:
        raise HTTPException(502, "The vision result has invalid task or review metadata.")
    directory = task_directory(task_id)
    directory.mkdir(parents=True)
    (directory / filename).write_bytes(data)
    target = directory / "result.json"
    save_design(target, json.dumps(result, indent=2, allow_nan=False))
    manifest = {
        "source_result_sha256": sha256(target.read_bytes()).hexdigest(),
        "input_file": filename,
        "image_sha256": sha256(data).hexdigest(),
    }
    save_design(directory / "task.json", json.dumps(manifest))
    return {"task_id": task_id, "source_result_sha256": manifest["source_result_sha256"], "result": result}


@router.post("/{task_id}/approve")
def approve_image(task_id: str, body: Approval):
    directory = task_directory(task_id)
    if not (directory / "task.json").is_file():
        raise HTTPException(404, "Unknown image task.")
    manifest = read_json(directory / "task.json")
    result_path = directory / "result.json"
    input_path = directory / manifest["input_file"]
    reviewed_hash = manifest["source_result_sha256"]
    if not body.approved or body.source_result_sha256 != reviewed_hash:
        raise HTTPException(409, "Approval must match the unchanged image and displayed result.")
    try:
        reviewed_bytes = result_path.read_bytes()
        image_hash = sha256(input_path.read_bytes()).hexdigest()
    except FileNotFoundError as error:
        raise HTTPException(409, "The reviewed image or result is missing.") from error
    if sha256(reviewed_bytes).hexdigest() != reviewed_hash or image_hash != manifest["image_sha256"]:
        raise HTTPException(409, "The reviewed image or result changed.")

    result = parse_json(reviewed_bytes)
    draft = result["design_spec"]
    gate = result["capability"]
    try:
        DESIGN_VALIDATOR.validate(draft)
    except ValidationError as error:
        raise HTTPException(422, "The reviewed design is invalid.") from error
    if (draft["task_id"] != task_id or gate["status"] != "review_required"
            or gate["allow_geometry"] is not False or gate["unsupported"] or gate["questions"]
            or gate["review_reasons"] != [VISUAL_REVIEW_REASON]
            or draft["needs_clarification"] or draft["clarification_questions"]
            or draft["board_id"] != "raspberry_pi_4" or draft["case_shape"] != "rectangular"
            or draft["lid"] != {"present": False, "style": "unspecified"}
            or draft["wall_thickness_mm"] is None or not result["instructions"].strip()
            or unsupported_features(draft) or result["evidence"]["unrepresented_features"]
            or result["unverified_features"] or result["visual_audit"]["other_features"]):
        raise HTTPException(422, "Approval cannot override unresolved or unsupported requirements.")

    approval = {**body.model_dump(), "approved_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        save_design(directory / "approval.json", json.dumps(approval))
    except FileExistsError as error:
        raise HTTPException(409, "An approval was already recorded for this task.") from error

    cad_dir = directory / "cad"
    geometry = run_geometry(draft, output_dir=cad_dir)
    if not geometry["valid"] or geometry["errors"]:
        raise HTTPException(422, {"code": "geometry_blocked", "errors": geometry["errors"]})
    artifact_hashes = {}
    for extension in ("step", "stl"):
        artifact = cad_dir / f"{task_id}.{extension}"
        if not artifact.is_file() or not artifact.stat().st_size:
            raise HTTPException(500, "CAD export did not produce both STEP and STL.")
        artifact_hashes[extension] = sha256(artifact.read_bytes()).hexdigest()
    pending = directory / "publication.tmp"
    save_design(pending, json.dumps(artifact_hashes))
    pending.replace(directory / "publication.json")
    return {
        "status": "generated_after_review",
        "task_id": task_id,
        "dimensions": geometry["dimensions"],
        "step_url": f"/image/{task_id}/step",
        "stl_url": f"/image/{task_id}/stl",
    }


@router.get("/{task_id}/{extension}")
def download_image_cad(task_id: str, extension: str):
    directory = task_directory(task_id)
    manifest = directory / "publication.json"
    if extension not in {"step", "stl"} or not manifest.is_file():
        raise HTTPException(404, "No approved artifact for this task.")
    path = directory / "cad" / f"{task_id}.{extension}"
    if not path.is_file() or sha256(path.read_bytes()).hexdigest() != read_json(manifest)[extension]:
        raise HTTPException(404, "The approved artifact is missing or changed.")
    return FileResponse(path, media_type=f"model/{extension}", filename=path.name)
