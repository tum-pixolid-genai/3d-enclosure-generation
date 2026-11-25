import json
from pathlib import Path

import cadquery as cq
import pytest
from fastapi import HTTPException

from agent.agent import PROJECT_DIR, extract_design
from agent.hardened_agent import HardenedAgent
from agent.llm_agent import PROGRAM_FIELDS, AgentError, LLMAgent
from backend import agent_service, geometry_service, main


PI4_PROMPT = "Design a rectangular enclosure for Raspberry Pi 4 with no lid."
SCREWED_LID_PROMPT = "Design a rectangular enclosure for Raspberry Pi 4 with a screwed lid"


def fixture_chat(payload):
    request = json.loads(payload["messages"][-1]["content"])
    draft = extract_design({**request, "task_id": "model-fixture"}, allow_assembly=True)
    model_fields = {
        key: value for key, value in draft.items() if key not in PROGRAM_FIELDS
    }
    return {"done": True, "message": {"content": json.dumps(model_fields)}}


@pytest.fixture(autouse=True)
def isolated_cad_output(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(geometry_service, "OUTPUT_DIR", tmp_path)


@pytest.mark.parametrize("mode", ["mock", "llm_fixture"])
def test_pi4_generates_step_and_stl(mode, monkeypatch):
    text_agent = HardenedAgent(LLMAgent(chat=fixture_chat)) if mode == "llm_fixture" else None
    monkeypatch.setattr(agent_service, "text_agent", text_agent)

    result = main.create_design(main.DesignRequest(prompt=PI4_PROMPT))

    assert result["status"] in {"generated", "generated_with_warnings"}
    assert result["geometry_result"]["dimensions"]["outer_height_mm"] == pytest.approx(23.6)
    task_id = result["task_id"]
    assert result["model_url"] == f"/design/{task_id}/model.stl"
    step = main.download_design(task_id)
    stl = main.get_design_stl(task_id)
    assert step.status_code == stl.status_code == 200
    assert Path(stl.path).stat().st_size > 84
    shape = cq.importers.importStep(str(step.path))
    assert shape.solids().size() == 1
    assert shape.val().BoundingBox().zlen == pytest.approx(23.6, abs=0.001)


@pytest.mark.parametrize("mode", ["mock", "llm_fixture"])
def test_t004_stops_before_geometry(mode, monkeypatch, tmp_path):
    text_agent = HardenedAgent(LLMAgent(chat=fixture_chat)) if mode == "llm_fixture" else None
    monkeypatch.setattr(agent_service, "text_agent", text_agent)

    def unexpected_geometry(_spec):
        pytest.fail("Geometry was invoked for an unsupported request")

    monkeypatch.setattr(main, "run_geometry", unexpected_geometry)
    t004 = json.loads(
        (PROJECT_DIR / "examples/complex_request_T004.json").read_text(encoding="utf-8")
    )

    result = main.create_design(main.DesignRequest(prompt=t004["request_text"]))

    assert result["status"] == "unsupported"
    assert len(result["capability"]["unsupported"]) == 4
    assert "model_url" not in result
    assert not list(tmp_path.iterdir())
    for route in (main.download_design, main.get_design_stl):
        with pytest.raises(HTTPException) as failure:
            route(result["task_id"])
        assert failure.value.status_code == 404


@pytest.mark.parametrize("mode", ["mock", "llm_fixture"])
def test_screwed_lid_routes_through_assembly(mode, monkeypatch):
    text_agent = HardenedAgent(LLMAgent(chat=fixture_chat)) if mode == "llm_fixture" else None
    monkeypatch.setattr(agent_service, "text_agent", text_agent)

    def blocked_assembly(task_id):
        return {"task_id": task_id, "status": "geometry_blocked", "assembly_validated": False}

    monkeypatch.setattr(main, "generate_pi4_assembly", blocked_assembly)
    result = main.create_design(main.DesignRequest(
        prompt=f"{SCREWED_LID_PROMPT}, automatic port cutouts, and 2 mm wall thickness.",
    ))
    assert result["status"] == "geometry_blocked"
    assert result["capability"]["allow_geometry"] is True
    assert result["design_spec"]["wall_thickness_mm"] == 2
    assert result["model_url"] is None
    assert "downloads" not in result


@pytest.mark.parametrize(("requirements", "issue"), [
    (" and 3 mm wall thickness", "assembly_wall_thickness"),
    (" and HDMI openings on the left", "port_opening"),
    (" and two wall-mount holes", "external_wall_mount_holes"),
])
def test_screwed_lid_unsupported_requirements_stop_before_assembly(requirements, issue, monkeypatch):
    monkeypatch.setattr(agent_service, "text_agent", None)
    result = main.create_design(main.DesignRequest(prompt=f"{SCREWED_LID_PROMPT}{requirements}."))
    assert result["status"] == "unsupported"
    assert [item["code"] for item in result["capability"]["unsupported"]] == [issue]
    assert "downloads" not in result


@pytest.mark.parametrize(
    ("failure_code", "http_status"),
    [("ollama_connection_error", 503), ("invalid_model_json", 502)],
)
def test_agent_errors_do_not_generate_cad(failure_code, http_status, monkeypatch, tmp_path):
    def failed_chat(_payload):
        raise AgentError(failure_code, "fixture failure")

    monkeypatch.setattr(agent_service, "text_agent", HardenedAgent(LLMAgent(chat=failed_chat)))

    with pytest.raises(HTTPException) as failure:
        main.create_design(main.DesignRequest(prompt=PI4_PROMPT))

    assert failure.value.status_code == http_status
    assert failure.value.detail["code"] == failure_code
    assert not list(tmp_path.iterdir())
