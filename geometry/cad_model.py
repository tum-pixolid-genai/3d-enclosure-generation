import math
import cadquery as cq


def create_enclosure(
    dimensions,
    wall_thickness_mm=2.0,
    usb_port=None,
    mounting=None,
    lid_fasteners=None,
):
    outer_width = dimensions["outer_width_mm"]
    outer_length = dimensions["outer_length_mm"]
    outer_height = dimensions["outer_height_mm"]

    inner_width = dimensions["inner_width_mm"]
    inner_length = dimensions["inner_length_mm"]
    inner_height = dimensions["inner_height_mm"]

    # 1. Create the outer enclosure.
    outer_box = cq.Workplane("XY").box(
        outer_width,
        outer_length,
        outer_height
    )

    # 2. Create the inner cavity (open-top enclosure).
    inner_box = (
        cq.Workplane("XY")
        .box(inner_width, inner_length, inner_height)
        .translate((0, 0, wall_thickness_mm / 2))
    )

    enclosure = outer_box.cut(inner_box)

    # 3. Create the USB opening.
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

    # 4. Create PCB mounting standoffs.
    if mounting is not None:
        standoff_height = mounting["height_mm"]
        standoff_diameter = mounting["diameter_mm"]
        screw_hole_diameter = mounting["screw_hole_diameter_mm"]

        spacing_x = mounting["spacing_x_mm"]
        spacing_y = mounting["spacing_y_mm"]

        # PCB mounting hole offset from the reference edges.
        edge_offset = mounting.get("edge_offset_mm", 3.5)

        # PCB dimensions, excluding enclosure clearance.
        board_width = mounting.get(
            "board_width_mm",
            inner_width - 2.0
        )

        board_length = mounting.get(
            "board_length_mm",
            inner_length - 2.0
        )

        # Inner bottom surface of the enclosure.
        bottom_z = (
            -outer_height / 2 + wall_thickness_mm
        )

        # Mounting hole coordinates relative to PCB centre.
        #
        # X: first hole is 3.5 mm from the reference edge.
        #    second hole is 58 mm from the first.
        #
        # Y: holes are separated by 49 mm.
        #
        # Assumption: PCB is centred inside the enclosure.
        x1 = -board_width / 2 + edge_offset
        x2 = x1 + spacing_x

        y1 = -board_length / 2 + edge_offset
        y2 = y1 + spacing_y

        positions = [
            (x1, y1),
            (x1, y2),
            (x2, y1),
            (x2, y2),
        ]

        for x, y in positions:

            # Create the cylindrical standoff.
            standoff = (
                cq.Workplane("XY")
                .circle(standoff_diameter / 2)
                .extrude(standoff_height)
                .translate((x, y, bottom_z))
            )

            enclosure = enclosure.union(standoff)

            # Create a blind pilot hole for screw mounting.
            # The hole stops at the enclosure floor.
            screw_hole = (
                cq.Workplane("XY")
                .circle(screw_hole_diameter / 2)
                .extrude(standoff_height)
                .translate((x, y, bottom_z))
            )

            enclosure = enclosure.cut(screw_hole)

    if lid_fasteners is not None:
        enclosure = add_lid_fasteners(enclosure, dimensions, lid_fasteners)

    return enclosure


def lid_fastener_positions(dimensions, config=None):
    config = config or {}
    offset = config.get("side_offset_mm", 2.0)
    inset = config.get("end_inset_mm", 2.0)
    x = dimensions["outer_width_mm"] / 2 + offset
    y = dimensions["outer_length_mm"] / 2 - inset
    return [(-x, -y), (-x, y), (x, -y), (x, y)]


def validate_lid_fasteners(dimensions, config=None):
    config = config or {}
    diameter = config.get("boss_diameter_mm", 5.0)
    hole = config.get("hole_diameter_mm", 2.0)
    height = config.get("boss_height_mm", 5.0)
    overlap = config.get("attachment_overlap_mm", 0.4)
    offset = config.get("side_offset_mm", 2.0)
    lid_thickness = config.get("lid_thickness_mm", 2.0)
    errors = []
    values = (diameter, hole, height, overlap, offset, lid_thickness)
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return ["Lid fastener parameters must be finite numbers."]
    if min(values) <= 0 or hole >= diameter or overlap >= diameter / 2:
        errors.append("Invalid lid fastener dimensions.")
    if offset >= diameter / 2 or diameter / 2 - offset < overlap:
        errors.append("Lid bosses must overlap the enclosure side walls.")
    if height >= dimensions["outer_height_mm"]:
        errors.append("Lid boss height exceeds enclosure height.")
    if config.get("end_inset_mm", 2.0) <= 0:
        errors.append("Lid boss end inset must be positive.")
    return errors


def add_lid_fasteners(enclosure, dimensions, config=None):
    config = config or {}
    errors = validate_lid_fasteners(dimensions, config)
    if errors:
        raise ValueError(" ".join(errors))
    diameter = config.get("boss_diameter_mm", 5.0)
    hole = config.get("hole_diameter_mm", 2.0)
    height = config.get("boss_height_mm", 5.0)
    top = dimensions["outer_height_mm"] / 2
    for x, y in lid_fastener_positions(dimensions, config):
        boss = (cq.Workplane("XY").circle(diameter / 2).extrude(height)
                .translate((x, y, top - height)))
        enclosure = enclosure.union(boss)
        bore = (cq.Workplane("XY").circle(hole / 2).extrude(height)
                .translate((x, y, top - height)))
        enclosure = enclosure.cut(bore)
    return enclosure


def create_screw_lid(dimensions, config=None):
    config = config or {}
    errors = validate_lid_fasteners(dimensions, config)
    if errors:
        raise ValueError(" ".join(errors))
    thickness = config.get("lid_thickness_mm", 2.0)
    diameter = config.get("boss_diameter_mm", 5.0)
    hole = config.get("hole_diameter_mm", 2.0)
    top = dimensions["outer_height_mm"] / 2
    lid = (cq.Workplane("XY")
           .box(dimensions["outer_width_mm"], dimensions["outer_length_mm"], thickness)
           .translate((0, 0, top + thickness / 2)))
    for x, y in lid_fastener_positions(dimensions, config):
        tab = (cq.Workplane("XY").circle(diameter / 2).extrude(thickness)
               .translate((x, y, top)))
        lid = lid.union(tab)
        bore = (cq.Workplane("XY").circle(hole / 2).extrude(thickness)
                .translate((x, y, top)))
        lid = lid.cut(bore)
    return lid


def export_enclosure(enclosure, output_path):
    cq.exporters.export(enclosure, str(output_path))


def verify_enclosure(
    enclosure,
    dimensions,
    wall_thickness_mm,
    usb_port=None,
    mounting=None,
    lid_fasteners=None,
):
    errors = []
    tolerance = 0.001

    # 1. Check number of solids.
    solids = enclosure.solids()

    if solids.size() != 1:
        errors.append("Enclosure must contain exactly one solid.")
        return errors

    solid = solids.val()

    # 2. Check CAD validity.
    if not solid.isValid():
        errors.append("Invalid CAD geometry.")
        return errors

    # 3. Check outer dimensions.
    bbox = solid.BoundingBox()

    expected_width = dimensions["outer_width_mm"]
    expected_length = dimensions["outer_length_mm"]
    if lid_fasteners is not None:
        diameter = lid_fasteners.get("boss_diameter_mm", 5.0)
        offset = lid_fasteners.get("side_offset_mm", 2.0)
        inset = lid_fasteners.get("end_inset_mm", 2.0)
        expected_width = max(expected_width, expected_width + 2 * offset + diameter)
        expected_length = max(expected_length, expected_length - 2 * inset + diameter)
    expected_dimensions = (
        expected_width,
        expected_length,
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

    # 4. Calculate expected enclosure volume.
    expected_volume = (
        dimensions["outer_width_mm"]
        * dimensions["outer_length_mm"]
        * dimensions["outer_height_mm"]
        -
        dimensions["inner_width_mm"]
        * dimensions["inner_length_mm"]
        * dimensions["inner_height_mm"]
    )

    # Subtract USB opening volume.
    if usb_port is not None:
        expected_volume -= (
            usb_port["width_mm"]
            * usb_port["height_mm"]
            * wall_thickness_mm
        )

    # Add the volume of four hollow standoffs.
    if mounting is not None:
        outer_radius = mounting["diameter_mm"] / 2
        inner_radius = mounting["screw_hole_diameter_mm"] / 2
        height = mounting["height_mm"]

        single_standoff_volume = (
            math.pi
            * (outer_radius ** 2 - inner_radius ** 2)
            * height
        )

        expected_volume += 4 * single_standoff_volume

    if lid_fasteners is None and abs(solid.Volume() - expected_volume) > tolerance:
        errors.append("Incorrect enclosure volume.")

    # 5. Check wall thickness.
    expected_wall_thickness = wall_thickness_mm

    actual_wall_thickness_x = (
        dimensions["outer_width_mm"]
        - dimensions["inner_width_mm"]
    ) / 2

    actual_wall_thickness_y = (
        dimensions["outer_length_mm"]
        - dimensions["inner_length_mm"]
    ) / 2

    actual_bottom_thickness = (
        dimensions["outer_height_mm"]
        - dimensions["inner_height_mm"]
    )

    if abs(
        actual_wall_thickness_x - expected_wall_thickness
    ) > tolerance:
        errors.append("Incorrect wall thickness on X axis.")

    if abs(
        actual_wall_thickness_y - expected_wall_thickness
    ) > tolerance:
        errors.append("Incorrect wall thickness on Y axis.")

    if abs(
        actual_bottom_thickness - expected_wall_thickness
    ) > tolerance:
        errors.append("Incorrect bottom thickness.")

    return errors


def validate_usb_port(dimensions, usb_port, wall_thickness_mm):
    errors = []

    if not isinstance(usb_port, dict):
        return ["USB port must be an object."]

    required_fields = (
        "width_mm",
        "height_mm",
        "x_mm",
        "z_mm",
    )

    for field in required_fields:
        value = usb_port.get(field)

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            errors.append(
                f"USB port {field} must be a finite number."
            )

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

    if (
        abs(port_x) + port_width / 2
        >= outer_width / 2 - wall_thickness_mm
    ):
        errors.append(
            "USB port exceeds the allowed horizontal boundary."
        )

    bottom_z = (
        -outer_height / 2 + wall_thickness_mm
    )

    if port_z - port_height / 2 <= bottom_z:
        errors.append(
            "USB port intersects the enclosure bottom."
        )

    if port_z + port_height / 2 >= outer_height / 2:
        errors.append(
            "USB port exceeds the top boundary."
        )

    return errors