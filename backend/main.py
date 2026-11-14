
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict
import uuid
from backend.agent_service import run_agent
from pathlib import Path
from backend.geometry_service import run_geometry, OUTPUT_DIR
import re

from fastapi.responses import FileResponse

app = FastAPI()


# Define the structure of a design request
class DesignRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    prompt: str = Field(min_length=10)


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

    # Step 3: Call the Agent
    design_spec = run_agent(agent_request)

    # Step 4: Check whether clarification is needed
    if design_spec["needs_clarification"]:
        return {
            "status": "needs_clarification",
            "task_id": task_id,
            "design_spec": design_spec,
            "questions": design_spec["clarification_questions"]
        }

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
    return {
        "status": (
            "generated_with_warnings"
            if geometry_result["warnings"]
            else "generated"
        ),
        "task_id": task_id,
        "design_spec": design_spec,
        "geometry_result": geometry_result
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
