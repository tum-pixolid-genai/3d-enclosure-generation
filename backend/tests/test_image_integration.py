import base64
import json
from pathlib import Path

import cadquery as cq
from fastapi import HTTPException
import pytest

from backend import image_routes
from image_agent.vision_agent import VisionAgent


EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
INSTRUCTIONS = "Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness."


@pytest.fixture
def review_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(image_routes, "REVIEW_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def vision_agent():
    primary = {
        "design": {
            "board_id": None, "case_shape": "rectangular",
            "lid": {"present": False, "style": "unspecified"}, "port_requirements": [],
            "mounting": {"wall_mount_hole_count": None}, "wall_thickness_mm": None,
            "needs_clarification": False, "clarification_questions": [],
        },
        "visual_evidence": {
            "case_shape": "Rectangular enclosure walls", "lid": "Visible open top",
            "port_requirements": "", "mounting": "",
        },
        "unrepresented_features": [], "image_questions": [],
    }
    audit = {
        "scene": "enclosure_3d", "scene_evidence": "Visible depth and floor",
        "lid_state": "open", "lid_evidence": "Visible cavity",
        "cover_panel_visible": False, "interior_floor_visible": True,
        "opening_certainty": "none", "openings": [], "other_features": [], "uncertainties": [],
    }
    return VisionAgent(
        chat=lambda _: {"done": True, "message": {"content": json.dumps(primary)}},
        audit_chat=lambda _: {"done": True, "message": {"content": json.dumps(audit)}},
    )


def extract(agent, instructions=INSTRUCTIONS):
    image = (EXAMPLES / "open.png").read_bytes()
    request = image_routes.ImageRequest(
        filename="open.png", image_base64=base64.b64encode(image).decode("ascii"),
        instructions=instructions,
    )
    return image_routes.extract_image(request, agent)


def approval(result, **overrides):
    return image_routes.Approval(**{
        "approved": True, "reviewer": "test-reviewer",
        "source_result_sha256": result["source_result_sha256"],
        **overrides,
    })


def test_review_publishes_both_exports(vision_agent, review_dir):
    result = extract(vision_agent)
    task_id = result["task_id"]
    assert result["result"]["capability"]["status"] == "review_required"
    assert result["result"]["capability"]["allow_geometry"] is False
    for extension in ("step", "stl"):
        with pytest.raises(HTTPException) as failure:
            image_routes.download_image_cad(task_id, extension)
        assert failure.value.status_code == 404

    generated = image_routes.approve_image(task_id, approval(result))
    assert generated["status"] == "generated_after_review"
    assert generated["dimensions"]["outer_height_mm"] == pytest.approx(23.6)
    step = Path(image_routes.download_image_cad(task_id, "step").path)
    stl = Path(image_routes.download_image_cad(task_id, "stl").path)
    assert cq.importers.importStep(str(step)).val().BoundingBox().zlen == pytest.approx(23.6)
    assert stl.stat().st_size > 84

    with pytest.raises(HTTPException) as failure:
        image_routes.approve_image(task_id, approval(result))
    assert failure.value.status_code == 409
    stl.write_bytes(b"changed")
    with pytest.raises(HTTPException) as failure:
        image_routes.download_image_cad(task_id, "stl")
    assert failure.value.status_code == 404


@pytest.mark.parametrize("rejection", ["declined", "wrong_hash", "changed_image", "changed_result", "missing_details"])
def test_rejected_review_never_calls_geometry(rejection, vision_agent, review_dir, monkeypatch):
    result = extract(vision_agent, "" if rejection == "missing_details" else INSTRUCTIONS)
    task_id = result["task_id"]
    directory = review_dir / task_id
    overrides = {}
    if rejection == "declined":
        overrides["approved"] = False
    if rejection == "wrong_hash":
        overrides["source_result_sha256"] = "0" * 64
    if rejection == "changed_image":
        (directory / "input.png").write_bytes(b"new image")
    if rejection == "changed_result":
        (directory / "result.json").write_bytes(b"new result")

    def unexpected_geometry(*args, **kwargs):
        pytest.fail("Rejected image review reached Geometry")

    monkeypatch.setattr(image_routes, "run_geometry", unexpected_geometry)
    with pytest.raises(HTTPException) as failure:
        image_routes.approve_image(task_id, approval(result, **overrides))
    assert failure.value.status_code == (422 if rejection == "missing_details" else 409)
    assert not (directory / "approval.json").exists()
    assert not (directory / "cad").exists()
