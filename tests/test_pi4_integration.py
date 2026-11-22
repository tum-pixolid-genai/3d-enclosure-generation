"""Real CadQuery STEP smoke tests using Agent v0.1-shaped input."""
import cadquery as cq
from geometry.checks import validate_and_generate


def agent_spec(**overrides):
    spec = {
        "schema_version": "0.1", "task_id": "pi4-e2e-smoke",
        "board_id": "raspberry_pi_4", "case_shape": "rectangular",
        "lid": {"present": False, "style": "unspecified"},
        "port_requirements": [], "mounting": {"wall_mount_hole_count": None},
        "wall_thickness_mm": None, "needs_clarification": False,
        "clarification_questions": [], "assumptions": [],
    }
    spec.update(overrides)
    return spec


def test_pi4_agent_input_exports_readable_step(tmp_path):
    path = tmp_path / "pi4.step"
    result = validate_and_generate(agent_spec(), output_path=path)
    assert result["valid"], result["errors"]
    assert result["output_path"] == str(path)
    assert path.stat().st_size > 1000
    shape = cq.importers.importStep(str(path))
    assert shape.solids().size() == 1
    assert shape.val().isValid()


def test_pi4_port_requirements_are_not_silently_modeled(tmp_path):
    path = tmp_path / "pi4_ports_unverified.step"
    spec = agent_spec(port_requirements=[
        {"port_type": "usb", "requested_side": "front", "count": 2}
    ])
    result = validate_and_generate(spec, output_path=path)
    assert result["valid"], result["errors"]
    assert any("Port alignment has not been verified" in w for w in result["warnings"])
    assert path.exists()


def test_pi4_clarification_blocks_export(tmp_path):
    path = tmp_path / "should_not_exist.step"
    result = validate_and_generate(agent_spec(needs_clarification=True), output_path=path)
    assert not result["valid"]
    assert not path.exists()


def test_null_optional_objects_do_not_crash():
    from geometry.checks import check_geometry
    result = check_geometry(agent_spec(lid=None, mounting=None))
    assert result["valid"]


def test_nonfinite_wall_thickness_rejected():
    from geometry.checks import check_geometry
    result = check_geometry(agent_spec(wall_thickness_mm=float("nan")))
    assert not result["valid"]
    assert result["dimensions"] is None
