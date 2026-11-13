import cadquery as cq


def create_enclosure(dimensions, wall_thickness_mm=2.0, usb_port=None):
    outer_width = dimensions["outer_width_mm"]
    outer_length = dimensions["outer_length_mm"]
    outer_height = dimensions["outer_height_mm"]

    inner_width = dimensions["inner_width_mm"]
    inner_length = dimensions["inner_length_mm"]
    inner_height = dimensions["inner_height_mm"]

    outer_box = cq.Workplane("XY").box(
        outer_width,
        outer_length,
        outer_height
    )

    inner_box = (
        cq.Workplane("XY")
        .box(inner_width, inner_length, inner_height)
        .translate((0, 0, wall_thickness_mm / 2))
    )

    enclosure = outer_box.cut(inner_box)

    if usb_port is not None:
        port_width = usb_port["width_mm"]
        port_height = usb_port["height_mm"]
        port_x = usb_port["x_mm"]
        port_z = usb_port["z_mm"]

        usb_cutout = (
            cq.Workplane("XY")
            .box(
                port_width,
                wall_thickness_mm + 2,
                port_height
            )
            .translate((
                port_x,
                -outer_length / 2 + wall_thickness_mm / 2,
                port_z
            ))
        )

        enclosure = enclosure.cut(usb_cutout)

    return enclosure

def export_enclosure(enclosure, output_path):
    cq.exporters.export(enclosure, str(output_path))

def verify_enclosure(enclosure, dimensions, wall_thickness_mm, usb_port=None):
    errors = []
    tolerance = 0.001

    solids = enclosure.solids()

    if solids.size() != 1:
        errors.append("Enclosure must contain exactly one solid.")
        return errors

    solid = solids.val()

    if not solid.isValid():
        errors.append("Invalid CAD geometry.")
        return errors

    bbox = solid.BoundingBox()

    expected_dimensions = (
        dimensions["outer_width_mm"],
        dimensions["outer_length_mm"],
        dimensions["outer_height_mm"],
    )

    actual_dimensions = (
        bbox.xlen,
        bbox.ylen,
        bbox.zlen,
    )

    for axis, actual, expected in zip(
        ("width", "length", "height"),
        actual_dimensions,
        expected_dimensions,
    ):
        if abs(actual - expected) > tolerance:
            errors.append(f"Incorrect outer {axis}.")

    expected_volume = (
        dimensions["outer_width_mm"]
        * dimensions["outer_length_mm"]
        * dimensions["outer_height_mm"]
        -
        dimensions["inner_width_mm"]
        * dimensions["inner_length_mm"]
        * dimensions["inner_height_mm"]
    )

    if usb_port is not None:
        expected_volume -= (
            usb_port["width_mm"]
            * usb_port["height_mm"]
            * wall_thickness_mm
        )

    if abs(solid.Volume() - expected_volume) > tolerance:
        errors.append("Incorrect enclosure volume.")

    expected_wall_thickness = wall_thickness_mm

    actual_wall_thickness_x = (
        dimensions["outer_width_mm"] - dimensions["inner_width_mm"]
    ) / 2

    actual_wall_thickness_y = (
        dimensions["outer_length_mm"] - dimensions["inner_length_mm"]
    ) / 2

    actual_bottom_thickness = (
        dimensions["outer_height_mm"] - dimensions["inner_height_mm"]
    )

    if abs(actual_wall_thickness_x - expected_wall_thickness) > tolerance:
        errors.append("Incorrect wall thickness on X axis.")

    if abs(actual_wall_thickness_y - expected_wall_thickness) > tolerance:
        errors.append("Incorrect wall thickness on Y axis.")

    if abs(actual_bottom_thickness - expected_wall_thickness) > tolerance:
        errors.append("Incorrect bottom thickness.")

    return errors

import math
def validate_usb_port(dimensions, usb_port, wall_thickness_mm):
    errors = []

    if not isinstance(usb_port, dict):
        return ["USB port must be an object."]

    required_fields = ("width_mm", "height_mm", "x_mm", "z_mm")

    for field in required_fields:
        value = usb_port.get(field)

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            errors.append(f"USB port {field} must be a finite number.")

    if errors:
        return errors

    port_width = usb_port["width_mm"]
    port_height = usb_port["height_mm"]
    port_x = usb_port["x_mm"]
    port_z = usb_port["z_mm"]

    if port_width <= 0 or port_height <= 0:
        errors.append("USB port dimensions must be positive.")
        return errors

    outer_width = dimensions["outer_width_mm"]
    outer_height = dimensions["outer_height_mm"]

    if abs(port_x) + port_width / 2 >= outer_width / 2 - wall_thickness_mm:
        errors.append("USB port exceeds the allowed horizontal boundary.")

    bottom_z = -outer_height / 2 + wall_thickness_mm

    if port_z - port_height / 2 <= bottom_z:
        errors.append("USB port intersects the enclosure bottom.")

    if port_z + port_height / 2 >= outer_height / 2:
        errors.append("USB port exceeds the top boundary.")

    return errors