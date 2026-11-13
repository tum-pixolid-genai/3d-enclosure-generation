from geometry.cad_model import (
    create_enclosure,
    export_enclosure,
    verify_enclosure,
    validate_usb_port,
)
from geometry.board_data import get_board_data


DEFAULT_WALL_THICKNESS_MM = 2.0
DEFAULT_CLEARANCE_MM = 1.0
MIN_WALL_THICKNESS_MM = 1.2


def check_geometry(design_spec):
    errors = []
    warnings = []

    # 1. Check whether clarification is required.
    if design_spec.get("needs_clarification", False):
        errors.append("Design requires clarification.")

    # 2. Check whether the board is supported.
    board_id = design_spec.get("board_id")
    board = get_board_data(board_id)

    if board is None:
        errors.append(f"Unknown or unsupported board: {board_id}")

    # 3. Check case shape.
    case_shape = design_spec.get("case_shape")

    if case_shape != "rectangular":
        errors.append(f"Unsupported case shape: {case_shape}")

    # 4. Check wall thickness.
    wall_thickness = design_spec.get("wall_thickness_mm")

    if wall_thickness is None:
        wall_thickness = DEFAULT_WALL_THICKNESS_MM
        warnings.append("Using default wall thickness of 2.0 mm.")

    if not isinstance(wall_thickness, (int, float)) or isinstance(wall_thickness, bool):
        errors.append("Wall thickness must be a number.")
    elif wall_thickness < MIN_WALL_THICKNESS_MM:
        errors.append("Wall thickness is below the minimum requirement.")

    # 5. Check unsupported features.
    lid = design_spec.get("lid", {})
    if lid.get("present") is True:
        warnings.append("Lid geometry is not implemented yet.")

    if design_spec.get("port_requirements"):
        warnings.append("Port alignment has not been verified.")

    mounting = design_spec.get("mounting", {})
    if mounting.get("wall_mount_hole_count") not in (None, 0):
        warnings.append("Wall mounting holes are not implemented yet.")

    # 6. Calculate enclosure dimensions.
    dimensions = None

    if board is not None and isinstance(wall_thickness, (int, float)) \
            and not isinstance(wall_thickness, bool) and wall_thickness > 0:

        dimensions = {
            "inner_width_mm": board["width_mm"] + 2 * DEFAULT_CLEARANCE_MM,
            "inner_length_mm": board["length_mm"] + 2 * DEFAULT_CLEARANCE_MM,
            "inner_height_mm": board["height_mm"] + DEFAULT_CLEARANCE_MM,
        }

        dimensions["outer_width_mm"] = (
            dimensions["inner_width_mm"] + 2 * wall_thickness
        )
        dimensions["outer_length_mm"] = (
            dimensions["inner_length_mm"] + 2 * wall_thickness
        )
        dimensions["outer_height_mm"] = (
            dimensions["inner_height_mm"] + wall_thickness
        )

    # 7. Return structured result.
    return {
        "task_id": design_spec.get("task_id"),
        "valid": len(errors) == 0,
        "dimensions": dimensions,
        "errors": errors,
        "warnings": warnings,
    }

def validate_and_generate(design_spec, output_path=None):
    result = check_geometry(design_spec)

    if not result["valid"]:
        return result

    dimensions = result["dimensions"]

    wall_thickness = design_spec.get("wall_thickness_mm")
    if wall_thickness is None:
        wall_thickness = DEFAULT_WALL_THICKNESS_MM

    usb_port = design_spec.get("usb_port")

    if usb_port is not None:
        port_errors = validate_usb_port(
            dimensions,
            usb_port,
            wall_thickness,
        )

        result["errors"].extend(port_errors)

        if port_errors:
            result["valid"] = False
            return result

    try:
        enclosure = create_enclosure(
            dimensions,
            wall_thickness,
            usb_port=usb_port,
        )

        geometry_errors = verify_enclosure(
            enclosure,
            dimensions,
            wall_thickness,
            usb_port=usb_port,
        )

        result["errors"].extend(geometry_errors)

        if not geometry_errors and output_path is not None:
            export_enclosure(enclosure, output_path)
            result["output_path"] = str(output_path)

    except Exception as error:
        result["errors"].append(
            f"CAD generation or export failed: {error}"
        )

    result["valid"] = len(result["errors"]) == 0

    return result