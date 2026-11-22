"""Agent-schema-shaped Raspberry Pi 4 smoke tests."""
from geometry.board_data import get_board_data
from geometry.checks import check_geometry


def test_raspberry_pi_4_is_registered():
    assert get_board_data("raspberry_pi_4") is not None


def test_agent_schema_shape_is_accepted():
    spec = {
        "schema_version": "0.1",
        "task_id": "pi4-demo",
        "board_id": "raspberry_pi_4",
        "case_shape": "rectangular",
        "lid": {"present": False, "style": "unspecified"},
        "port_requirements": [],
        "mounting": {"wall_mount_hole_count": 0},
        "wall_thickness_mm": None,
        "needs_clarification": False,
        "clarification_questions": [],
        "assumptions": [],
    }
    result = check_geometry(spec)
    assert result["valid"], result["errors"]
    assert result["dimensions"]["inner_width_mm"] == 87.0
    assert result["dimensions"]["inner_length_mm"] == 58.0
