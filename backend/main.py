
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from os import getenv
import uuid
from agent.llm_agent import AgentError
from backend.agent_service import run_agent
from pathlib import Path
from backend.geometry_service import run_geometry, OUTPUT_DIR
from backend.pi4_assembly_routes import router as pi4_assembly_router
import re

from fastapi.responses import FileResponse

app = FastAPI()
app.include_router(pi4_assembly_router)

if getenv("PIXOLID_IMAGE_AGENT_PORT"):
    from backend.image_routes import router as image_router

    app.include_router(image_router)


# Define the structure of a design request
class DesignRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(min_length=10, max_length=4096)


# Health check API
@app.get("/health")
def health_check():
    return {"status": "ok"}


# Design request API
@app.post("/design")
def create_design(request: DesignRequest):
    # Step 1: Generate a unique task ID
    task_id = f"design_{uuid.uuid4().hex}"

    # Step 2: Prepare the Agent request
    agent_request = {
        "task_id": task_id,
        "request_text": request.prompt,
        "language": "en"
    }

    # Step 3: Extract the spec and check the Agent's capability decision
    try:
        design_spec, capability = run_agent(agent_request)
    except AgentError as error:
        if error.code in {"invalid_request", "unsupported_language"}:
            status_code = 422
            message = str(error)
        elif error.code in {"ollama_http_error", "ollama_connection_error", "ollama_timeout"}:
            status_code = 503
            message = "The text model service is unavailable or did not respond in time."
        else:
            status_code = 502
            message = "The text model did not produce a valid design."
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "message": message},
        ) from error

    # Step 4: Stop before Geometry when the Agent has not approved generation
    if capability["allow_geometry"] is not True:
        status = capability["status"]
        response = {
            "status": "needs_clarification" if status == "clarification_required" else status,
            "task_id": task_id,
            "design_spec": design_spec,
            "capability": capability,
        }
        if status == "clarification_required":
            response["questions"] = capability["questions"]
        return response

    # Step 5: Call Geometry
    geometry_result = run_geometry(design_spec)

    # Step 6: Handle geometry validation failures
    if not geometry_result["valid"]:
        return {
            "status": "geometry_blocked",
            "task_id": task_id,
            "design_spec": design_spec,
            "geometry_result": geometry_result
        }

    # Step 7: Confirm that STEP export succeeded
    output_path = geometry_result.get("output_path")

    if not output_path or not Path(output_path).is_file():
        return {
            "status": "export_failed",
            "task_id": task_id,
            "geometry_result": geometry_result
        }

    
    # Step 8: Return the generated model information
    stl_path = geometry_result.get("stl_path")

    model_url = (
        f"/design/{task_id}/model.stl"
        if stl_path and Path(stl_path).is_file()
        else None
    )

    return {
        "status": (
            "generated_with_warnings"
            if geometry_result["warnings"]
            else "generated"
        ),
        "task_id": task_id,
        "design_spec": design_spec,
        "geometry_result": geometry_result,
        "model_url": model_url
    }



@app.get("/design/{task_id}/download")
def download_design(task_id: str):
    # Validate the task ID to prevent unsafe file paths
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID"
        )

    # Find the generated STEP file
    file_path = OUTPUT_DIR / f"{task_id}.step"

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="STEP file not found"
        )

    # Send the STEP file to the user
    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="model/step"
    )


@app.get("/design/{task_id}/model.stl")
def get_design_stl(task_id: str):

    # Validate task ID
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", task_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid task ID"
        )

    # Find STL file
    file_path = OUTPUT_DIR / f"{task_id}.stl"

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="STL file not found"
        )

    # Return STL file to frontend
    return FileResponse(
        path=file_path,
        media_type="model/stl"
    )
