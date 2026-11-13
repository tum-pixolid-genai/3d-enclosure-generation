from geometry.checks import check_geometry
from geometry.checks import validate_and_generate


def test_valid_design():
    design = {
        "task_id": "test_001",
        "board_id": "test_board",
        "case_shape": "rectangular",
        "wall_thickness_mm": 2.0,
        "needs_clarification": False,
        "lid": {"present": False, "style": "unspecified"},
        "port_requirements": [],
        "mounting": {"wall_mount_hole_count": 0},
    }

    result = check_geometry(design)

    assert result["valid"] is True
    assert result["dimensions"]["outer_width_mm"] == 71.0
    assert result["dimensions"]["outer_length_mm"] == 36.0
    assert result["dimensions"]["outer_height_mm"] == 15.0


def test_unknown_board():
    design = {
        "task_id": "test_002",
        "board_id": "unknown_board",
        "case_shape": "rectangular",
        "wall_thickness_mm": 2.0,
        "needs_clarification": False,
    }

    result = check_geometry(design)

    assert result["valid"] is False
    assert result["dimensions"] is None


def test_wall_too_thin():
    design = {
        "task_id": "test_003",
        "board_id": "test_board",
        "case_shape": "rectangular",
        "wall_thickness_mm": 0.5,
        "needs_clarification": False,
    }

    result = check_geometry(design)

    assert result["valid"] is False

def test_validate_and_generate():
    design_spec = {
        "task_id": "cad_test_001",
        "board_id": "test_board",
        "case_shape": "rectangular",
        "wall_thickness_mm": 2.0,
        "needs_clarification": False,
    }

    result = validate_and_generate(design_spec)

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["dimensions"] is not None
def test_export_enclosure(tmp_path):
    design_spec = {
        "task_id": "export_test_001",
        "board_id": "test_board",
        "case_shape": "rectangular",
        "wall_thickness_mm": 2.0,
        "needs_clarification": False,
    }

    output_file = tmp_path / "enclosure.step"

    result = validate_and_generate(design_spec, output_file)
    
    assert result["valid"] is True
    assert output_file.exists()
    assert output_file.stat().st_size > 0

def test_usb_port_generation(tmp_path):
    design_spec = {
        "task_id": "usb_test_001",
        "board_id": "test_board",
        "case_shape": "rectangular",
        "wall_thickness_mm": 2.0,
        "needs_clarification": False,
        "usb_port": {
            "width_mm": 10,
            "height_mm": 4,
            "x_mm": 3,
            "z_mm": 0,
        },
    }

    output_file = tmp_path / "usb_enclosure.step"

    result = validate_and_generate(design_spec, output_file)

    assert result["valid"] is True
    assert output_file.exists()
    assert output_file.stat().st_size > 0


def test_invalid_usb_port_generation(tmp_path):
    design_spec = {
        "task_id": "usb_test_002",
        "board_id": "test_board",
        "case_shape": "rectangular",
        "wall_thickness_mm": 2.0,
        "needs_clarification": False,
        "usb_port": {
            "width_mm": 10,
            "height_mm": 4,
            "x_mm": 40,
            "z_mm": 0,
        },
    }

    output_file = tmp_path / "invalid_usb.step"

    result = validate_and_generate(design_spec, output_file)

    assert result["valid"] is False
    assert not output_file.exists()