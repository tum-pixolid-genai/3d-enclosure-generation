"""Verify the requested +3 mm USB cutout movement on the X axis."""
import cadquery as cq
from geometry.checks import check_geometry, validate_and_generate


def _spec(x):
    return {
        "task_id": "usb-shift-3mm", "board_id": "raspberry_pi_4",
        "case_shape": "rectangular", "wall_thickness_mm": 2.0,
        "needs_clarification": False,
        "usb_port": {"width_mm": 10.0, "height_mm": 4.0, "x_mm": x, "z_mm": 0.0},
    }


def test_usb_opening_moves_three_mm_right(tmp_path):
    """Compare actual STEP geometry with a centered and shifted cutout."""
    dimensions = check_geometry(_spec(0))["dimensions"]
    outer_width = dimensions["outer_width_mm"]
    outer_length = dimensions["outer_length_mm"]
    outer_height = dimensions["outer_height_mm"]
    wall = 2.0
    # Point lies in the front wall, in the opening for x=3, not x=0.
    # x=7.5: outside the initial [-5, 5] opening, inside shifted [-2, 8].
    x, y, z = 7.5, -outer_length / 2 + wall / 2, 0.0
    states = []
    for label, port_x in (("original", 0.0), ("shifted", 3.0)):
        path = tmp_path / f"{label}.step"
        result = validate_and_generate(_spec(port_x), output_path=path)
        assert result["valid"], result["errors"]
        shape = cq.importers.importStep(str(path))
        assert shape.solids().size() == 1
        assert shape.val().isValid()
        # A tiny solid placed at a probe point checks actual STEP material.
        probe = cq.Workplane("XY").box(0.1, 0.1, 0.1).translate((x, y, z))
        intersection_volume = shape.intersect(probe).val().Volume()
        states.append(intersection_volume)
    assert states[0] > 0.0005, "Original wall should cover probe point"
    assert states[1] < 1e-6, "Shifted opening should remove material at probe point"


def test_shift_too_far_rejected(tmp_path):
    path = tmp_path / "invalid.step"
    result = validate_and_generate(_spec(100), output_path=path)
    assert not result["valid"]
    assert not path.exists()
