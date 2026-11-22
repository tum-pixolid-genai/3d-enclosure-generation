"""Raspberry Pi 4 virtual assembly and geometry verification."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Surface

from geometry.board_data import get_board_data
from geometry.cad_model import (
    create_enclosure, create_screw_lid, add_lid_fasteners,
    lid_fastener_positions, validate_lid_fasteners
)
from geometry.checks import check_geometry, DEFAULT_WALL_THICKNESS_MM


def load_board_step(step_path):
    path = Path(step_path)
    if not path.is_file():
        raise FileNotFoundError(f"STEP file not found: {path}")
    return cq.importers.importStep(str(path))


def align_board_to_enclosure(
    board, dimensions, wall_thickness_mm=2.0,
    standoff_height_mm=3.0, pcb_bottom_z=0.0,
    pcb_origin_x=42.5, pcb_origin_y=28.0
):
    target_z = (
        -dimensions["outer_height_mm"] / 2
        + wall_thickness_mm
        + standoff_height_mm
    )
    return board.translate((
        -pcb_origin_x,
        -pcb_origin_y,
        target_z - pcb_bottom_z
    ))


def _bbox_dict(shape):
    b = shape.BoundingBox()
    return {
        "xmin": round(b.xmin, 4),
        "xmax": round(b.xmax, 4),
        "ymin": round(b.ymin, 4),
        "ymax": round(b.ymax, 4),
        "zmin": round(b.zmin, 4),
        "zmax": round(b.zmax, 4)
    }


def _boxes_overlap(a, b, eps=1e-7):
    return (
        a.xmin < b.xmax - eps and b.xmin < a.xmax - eps
        and a.ymin < b.ymax - eps and b.ymin < a.ymax - eps
        and a.zmin < b.zmax - eps and b.zmin < a.zmax - eps
    )


def _overlap_volume(a, b):
    result = a.intersect(b)
    return sum(s.Volume() for s in result.solids().vals())


def detect_collision(enclosure, aligned_board, volume_tolerance_mm3=0.01):
    if volume_tolerance_mm3 < 0:
        raise ValueError("volume_tolerance_mm3 must be nonnegative")

    volume = _overlap_volume(enclosure, aligned_board)

    return {
        "collision_detected": volume > volume_tolerance_mm3,
        "collision_volume_mm3": round(volume, 6),
        "volume_tolerance_mm3": volume_tolerance_mm3
    }


def _diagnose_components(enclosure, board, dimensions, wall, tolerance, top_n=15):
    bare = create_enclosure(dimensions, wall_thickness_mm=wall)
    mounts = enclosure.cut(bare)

    floor_top = -dimensions["outer_height_mm"] / 2 + wall
    floor_bottom = -dimensions["outer_height_mm"] / 2

    floor_region = (
        cq.Workplane("XY")
        .box(
            dimensions["outer_width_mm"] + 2,
            dimensions["outer_length_mm"] + 2,
            wall
        )
        .translate((0, 0, (floor_top + floor_bottom) / 2))
    )

    floor = bare.intersect(floor_region)
    walls = bare.cut(floor)

    regions = [
        ("floor", floor),
        ("walls", walls),
        ("standoffs", mounts)
    ]

    rows = []
    totals = {name: 0.0 for name, _ in regions}

    for idx, solid in enumerate(board.solids().vals()):
        sb = solid.BoundingBox()
        parts = {}

        for name, region in regions:
            if not region.solids().size():
                continue

            if not _boxes_overlap(sb, region.val().BoundingBox()):
                continue

            volume = _overlap_volume(
                cq.Workplane("XY").newObject([solid]),
                region
            )

            if volume > 1e-8:
                parts[name] = volume
                totals[name] += volume

        volume = sum(parts.values())

        if volume > tolerance:
            rows.append({
                "step_solid_index": idx,
                "overlap_volume_mm3": round(volume, 6),
                "region_volumes_mm3": {
                    k: round(v, 6) for k, v in parts.items()
                },
                "solid_bbox_mm": _bbox_dict(solid)
            })

    rows.sort(key=lambda r: r["overlap_volume_mm3"], reverse=True)

    return {
        "regions_mm3": {
            k: round(v, 6) for k, v in totals.items()
        },
        "interfering_step_solids": len(rows),
        "largest_interferences": rows[:top_n],
        "note": "STEP solid indices are not component names."
    }


def get_assembly_configuration():
    data = get_board_data("raspberry_pi_4")

    spec = {
        "task_id": "pi4-assembly-check",
        "board_id": "raspberry_pi_4",
        "case_shape": "rectangular",
        "wall_thickness_mm": DEFAULT_WALL_THICKNESS_MM
    }

    checked = check_geometry(spec)

    if not checked["valid"]:
        raise ValueError(f"Invalid design: {checked['errors']}")

    dims = checked["dimensions"]

    mounting = {
        "height_mm": data["standoff_height_mm"],
        "diameter_mm": 5.0,
        "screw_hole_diameter_mm": 2.0,
        "spacing_x_mm": data["mounting_hole_spacing_x_mm"],
        "spacing_y_mm": data["mounting_hole_spacing_y_mm"],
        "edge_offset_mm": data["mounting_hole_edge_offset_mm"],
        "board_width_mm": data["width_mm"],
        "board_length_mm": data["length_mm"]
    }

    return data, dims, mounting


def find_pcb_solid(board, board_data, size_tolerance_mm=0.5):
    candidates = []

    for index, solid in enumerate(board.solids().vals()):
        bb = solid.BoundingBox()

        width_matches = abs(bb.xlen - board_data["width_mm"]) <= size_tolerance_mm
        length_matches = abs(bb.ylen - board_data["length_mm"]) <= size_tolerance_mm
        thickness_matches = 0 < bb.zlen <= 3.0

        if width_matches and length_matches and thickness_matches:
            candidates.append((index, solid))

    if len(candidates) != 1:
        return None, None

    return candidates[0]


def extract_step_mounting_holes(
    board, board_data, expected_radius_mm=1.35,
    radius_tolerance_mm=0.1
):
    pcb_index, pcb = find_pcb_solid(board, board_data)

    result = {
        "pcb_solid_index": pcb_index,
        "pcb_identified": pcb is not None,
        "expected_hole_radius_mm": expected_radius_mm,
        "radius_tolerance_mm": radius_tolerance_mm,
        "holes": []
    }

    if pcb is None:
        return result

    holes = []

    for face in pcb.Faces():
        if face.geomType() != "CYLINDER":
            continue

        surface = BRepAdaptor_Surface(face.wrapped)
        cylinder = surface.Cylinder()

        radius = cylinder.Radius()

        if abs(radius - expected_radius_mm) > radius_tolerance_mm:
            continue

        axis = cylinder.Axis()
        direction = axis.Direction()

        if abs(direction.Z()) < 0.999:
            continue

        location = axis.Location()

        x = location.X()
        y = location.Y()

        if not any(
            math.hypot(x - h["x_mm"], y - h["y_mm"]) < 0.01
            for h in holes
        ):
            holes.append({
                "x_mm": round(x, 6),
                "y_mm": round(y, 6),
                "radius_mm": round(radius, 6)
            })

    holes.sort(key=lambda h: (h["x_mm"], h["y_mm"]))
    result["holes"] = holes

    return result


def calculate_mounting_positions(
    board_width_mm, board_length_mm,
    spacing_x_mm, spacing_y_mm, edge_offset_mm
):
    x1 = -board_width_mm / 2 + edge_offset_mm
    x2 = x1 + spacing_x_mm
    y1 = -board_length_mm / 2 + edge_offset_mm
    y2 = y1 + spacing_y_mm

    return [
        (x1, y1),
        (x1, y2),
        (x2, y1),
        (x2, y2)
    ]


def check_mounting_alignment(
    board_data, mounting, board=None,
    tolerance_mm=0.1, expected_hole_radius_mm=1.35
):
    expected = calculate_mounting_positions(
        board_data["width_mm"],
        board_data["length_mm"],
        board_data["mounting_hole_spacing_x_mm"],
        board_data["mounting_hole_spacing_y_mm"],
        board_data["mounting_hole_edge_offset_mm"]
    )

    standoffs = calculate_mounting_positions(
        mounting["board_width_mm"],
        mounting["board_length_mm"],
        mounting["spacing_x_mm"],
        mounting["spacing_y_mm"],
        mounting["edge_offset_mm"]
    )

    parameter_deviations = [
        math.hypot(a[0] - b[0], a[1] - b[1])
        for a, b in zip(expected, standoffs)
    ]

    maximum_parameter_deviation = max(parameter_deviations)
    parameter_alignment = maximum_parameter_deviation <= tolerance_mm

    result = {
        "parameter_alignment_passed": parameter_alignment,
        "step_hole_alignment_verified": False,
        "tolerance_mm": tolerance_mm,
        "maximum_parameter_deviation_mm": round(
            maximum_parameter_deviation, 6
        ),
        "expected_positions_mm": [list(p) for p in expected],
        "standoff_positions_mm": [list(p) for p in standoffs],
        "pcb_identified": False,
        "pcb_solid_index": None,
        "step_hole_count": 0,
        "step_hole_positions_mm": [],
        "maximum_step_deviation_mm": None,
        "hole_matches": []
    }

    if board is None:
        result["note"] = "STEP model was not provided."
        return result

    extraction = extract_step_mounting_holes(
        board, board_data, expected_hole_radius_mm
    )

    result["pcb_identified"] = extraction["pcb_identified"]
    result["pcb_solid_index"] = extraction["pcb_solid_index"]

    holes = extraction["holes"]

    result["step_hole_count"] = len(holes)

    if len(holes) != 4:
        result["note"] = (
            f"Expected 4 mounting holes, but detected {len(holes)}."
        )
        return result

    pcb_width = board_data["width_mm"]
    pcb_length = board_data["length_mm"]

    aligned_holes = [
        (
            hole["x_mm"] - pcb_width / 2,
            hole["y_mm"] - pcb_length / 2
        )
        for hole in holes
    ]

    result["step_hole_positions_mm"] = [
        [round(x, 6), round(y, 6)]
        for x, y in aligned_holes
    ]

    remaining = list(enumerate(aligned_holes))
    matches = []
    deviations = []

    for index, standoff in enumerate(standoffs):
        closest_index, closest_hole = min(
            remaining,
            key=lambda item: math.hypot(
                item[1][0] - standoff[0],
                item[1][1] - standoff[1]
            )
        )

        deviation = math.hypot(
            closest_hole[0] - standoff[0],
            closest_hole[1] - standoff[1]
        )

        deviations.append(deviation)

        matches.append({
            "standoff_index": index,
            "standoff_position_mm": [
                round(standoff[0], 6),
                round(standoff[1], 6)
            ],
            "step_hole_position_mm": [
                round(closest_hole[0], 6),
                round(closest_hole[1], 6)
            ],
            "deviation_mm": round(deviation, 6),
            "aligned": deviation <= tolerance_mm
        })

        remaining = [
            item for item in remaining
            if item[0] != closest_index
        ]

    maximum_step_deviation = max(deviations)

    step_verified = (
        parameter_alignment
        and maximum_step_deviation <= tolerance_mm
        and all(match["aligned"] for match in matches)
    )

    result["maximum_step_deviation_mm"] = round(
        maximum_step_deviation, 6
    )
    result["hole_matches"] = matches
    result["step_hole_alignment_verified"] = step_verified
    result["note"] = (
        "STEP PCB hole centers were extracted from cylindrical "
        "faces and compared with the configured standoff positions. "
        "Fastener fit and manufacturing tolerances are not verified."
    )

    return result


def run_assembly_check(step_path, export_dir=None, volume_tolerance_mm3=0.01):
    data, dims, mounting = get_assembly_configuration()
    wall = DEFAULT_WALL_THICKNESS_MM

    enclosure = create_enclosure(dims, wall, mounting=mounting)
    board = load_board_step(step_path)

    aligned = align_board_to_enclosure(
        board, dims, wall, data["standoff_height_mm"],
        pcb_origin_x=data["width_mm"] / 2,
        pcb_origin_y=data["length_mm"] / 2
    )

    collision = detect_collision(enclosure, aligned, volume_tolerance_mm3)
    diagnostics = _diagnose_components(
        enclosure, aligned, dims, wall, volume_tolerance_mm3
    )

    mounting_validation = check_mounting_alignment(
        data, mounting, board
    )

    translation = [
        -data["width_mm"] / 2,
        -data["length_mm"] / 2,
        -dims["outer_height_mm"] / 2 + wall + data["standoff_height_mm"]
    ]

    result = {
        "board_id": "raspberry_pi_4",
        "dimensions_mm": dims,
        "board_solids": aligned.solids().size(),
        "alignment_translation_mm": [round(v, 6) for v in translation],
        "xy_alignment_verified": mounting_validation[
            "step_hole_alignment_verified"
        ],
        "assembly_validated": False,
        "collision": collision,
        "mounting_alignment": mounting_validation,
        "collision_diagnostics": diagnostics,
        "limitations": [
            "STEP mounting-hole centers are checked against configured standoff positions.",
            "STEP solid indices are not semantic component labels.",
            "Baseline enclosure lacks lid and most port openings.",
            "This is not a physical fit certification."
        ]
    }

    if export_dir is not None:
        output = Path(export_dir)
        output.mkdir(parents=True, exist_ok=True)

        cq.exporters.export(enclosure, str(output / "enclosure.step"))
        cq.exporters.export(aligned, str(output / "raspberry_pi_aligned.step"))

        (output / "assembly_report.json").write_text(
            json.dumps(result, indent=2),
            encoding="utf-8"
        )

    return result


def suggest_port_cutouts(
    board, dimensions, wall_thickness_mm=2.0,
    clearance_mm=0.5, min_overlap_mm3=0.01
):
    if clearance_mm < 0:
        raise ValueError("clearance_mm must be nonnegative")

    hw = dimensions["outer_width_mm"] / 2
    hl = dimensions["outer_length_mm"] / 2
    hh = dimensions["outer_height_mm"] / 2

    faces = {
        "x+": ("x", hw),
        "x-": ("x", -hw),
        "y+": ("y", hl),
        "y-": ("y", -hl)
    }

    candidates = []

    for index, solid in enumerate(board.solids().vals()):
        bb = solid.BoundingBox()

        for face, (axis, outer) in faces.items():
            inner = (
                outer - wall_thickness_mm
                if outer > 0
                else outer + wall_thickness_mm
            )

            bounds = (
                (bb.xmin, bb.xmax)
                if axis == "x"
                else (bb.ymin, bb.ymax)
            )

            if outer > 0 and not (bounds[1] > inner and bounds[0] < outer):
                continue

            if outer < 0 and not (bounds[0] < inner and bounds[1] > outer):
                continue

            if axis == "x":
                u0, u1 = bb.ymin - clearance_mm, bb.ymax + clearance_mm
            else:
                u0, u1 = bb.xmin - clearance_mm, bb.xmax + clearance_mm

            v0 = bb.zmin - clearance_mm
            v1 = bb.zmax + clearance_mm

            if v1 <= -hh or v0 >= hh:
                continue

            candidates.append({
                "face": face,
                "u_min": u0,
                "u_max": u1,
                "z_min": v0,
                "z_max": v1,
                "source_step_solid": index,
                "crosses_top_or_bottom": v0 < -hh or v1 > hh
            })

    merged = []

    for candidate in candidates:
        changed = True

        while changed:
            changed = False

            for existing in merged[:]:
                if existing["face"] != candidate["face"]:
                    continue

                overlaps = (
                    existing["u_min"] <= candidate["u_max"]
                    and candidate["u_min"] <= existing["u_max"]
                    and existing["z_min"] <= candidate["z_max"]
                    and candidate["z_min"] <= existing["z_max"]
                )

                if not overlaps:
                    continue

                merged.remove(existing)

                source_a = candidate["source_step_solid"]
                source_b = existing["source_step_solid"]

                if isinstance(source_a, int):
                    source_a = [source_a]

                if isinstance(source_b, int):
                    source_b = [source_b]

                candidate = {
                    "face": candidate["face"],
                    "u_min": min(candidate["u_min"], existing["u_min"]),
                    "u_max": max(candidate["u_max"], existing["u_max"]),
                    "z_min": min(candidate["z_min"], existing["z_min"]),
                    "z_max": max(candidate["z_max"], existing["z_max"]),
                    "source_step_solid": sorted(set(source_a + source_b)),
                    "crosses_top_or_bottom": (
                        candidate["crosses_top_or_bottom"]
                        or existing["crosses_top_or_bottom"]
                    )
                }

                changed = True

        merged.append(candidate)

    return sorted(
        merged,
        key=lambda x: (x["face"], x["u_min"], x["z_min"])
    )


def apply_port_cutouts(enclosure, cutouts, dimensions, wall_thickness_mm=2.0):
    modified = enclosure
    applied = []
    skipped = []

    for proposed in cutouts:
        c = dict(proposed)
        top = dimensions["outer_height_mm"] / 2
        bridge = top - c["z_max"]
        if 0 < bridge < 1.2:
            c["z_max"] = top + 1.0
            c["opened_to_top"] = True
        if c["crosses_top_or_bottom"]:
            skipped.append({
                **c,
                "reason": "Opening crosses outer top/bottom; manual design required"
            })
            continue

        u_mid = (c["u_min"] + c["u_max"]) / 2
        z_mid = (c["z_min"] + c["z_max"]) / 2
        u_size = c["u_max"] - c["u_min"]
        z_size = c["z_max"] - c["z_min"]

        if c["face"] in ("x+", "x-"):
            sign = 1 if c["face"] == "x+" else -1
            x = sign * (
                dimensions["outer_width_mm"] / 2
                - wall_thickness_mm / 2
            )

            tool = (
                cq.Workplane("XY")
                .box(wall_thickness_mm + 2, u_size, z_size)
                .translate((x, u_mid, z_mid))
            )
        else:
            sign = 1 if c["face"] == "y+" else -1
            y = sign * (
                dimensions["outer_length_mm"] / 2
                - wall_thickness_mm / 2
            )

            tool = (
                cq.Workplane("XY")
                .box(u_size, wall_thickness_mm + 2, z_size)
                .translate((u_mid, y, z_mid))
            )

        modified = modified.cut(tool)
        applied.append(c)

    return modified, applied, skipped


def validate_cad_geometry(model, expected_solids=1):
    solids = model.solids().vals()
    solid_count = len(solids)

    all_solids_valid = all(s.isValid() for s in solids)
    positive_volume = all(s.Volume() > 0 for s in solids)

    geometry_valid = (
        solid_count == expected_solids
        and all_solids_valid
        and positive_volume
    )

    return {
        "geometry_valid": geometry_valid,
        "solid_count": solid_count,
        "expected_solids": expected_solids,
        "all_solids_valid": all_solids_valid,
        "positive_volume": positive_volume,
        "total_volume_mm3": round(
            sum(s.Volume() for s in solids), 6
        )
    }


def generate_lid(dimensions, lid_thickness_mm=2.0):
    return create_screw_lid(dimensions, {"lid_thickness_mm": lid_thickness_mm})


def verify_lid_fasteners(enclosure, lid, dimensions, config=None, tolerance_mm3=0.01):
    config = config or {}
    errors = validate_lid_fasteners(dimensions, config)
    positions = lid_fastener_positions(dimensions, config)
    hole_diameter = config.get("hole_diameter_mm", 2.0)
    boss_height = config.get("boss_height_mm", 5.0)
    lid_thickness = config.get("lid_thickness_mm", 2.0)
    top = dimensions["outer_height_mm"] / 2
    matches = []
    for x, y in positions:
        lid_hole = (cq.Workplane("XY").circle(hole_diameter / 2)
                    .extrude(lid_thickness).translate((x, y, top)))
        boss_hole = (cq.Workplane("XY").circle(hole_diameter / 2)
                     .extrude(boss_height).translate((x, y, top - boss_height)))
        lid_blocked = _overlap_volume(lid, lid_hole) > tolerance_mm3
        boss_blocked = _overlap_volume(enclosure, boss_hole) > tolerance_mm3
        matches.append({
            "position_mm": [x, y],
            "lid_hole_open": not lid_blocked,
            "boss_hole_open": not boss_blocked,
            "aligned": not lid_blocked and not boss_blocked
        })
    return {
        "valid": not errors and len(matches) == 4 and all(m["aligned"] for m in matches),
        "hole_count": len(matches),
        "hole_diameter_mm": hole_diameter,
        "matches": matches,
        "errors": errors,
        "note": "Geometric hole clearance only; screw thread engagement and torque not certified."
    }


def check_cutout_bridges(cutouts, dimensions, min_bridge_mm=1.2):
    top = dimensions["outer_height_mm"] / 2
    bottom = -top
    failures = []
    for cutout in cutouts:
        upper = top - cutout["z_max"]
        lower = cutout["z_min"] - bottom
        if 0 < upper < min_bridge_mm - 1e-6:
            failures.append({"face": cutout["face"], "upper_bridge_mm": round(upper, 4)})
        if 0 < lower < min_bridge_mm - 1e-6:
            failures.append({"face": cutout["face"], "lower_bridge_mm": round(lower, 4)})
    return {
        "passed": not failures,
        "minimum_bridge_mm": min_bridge_mm,
        "thin_bridges": failures,
        "note": "Checks vertical cutout bridges, not global minimum feature thickness."
    }


def check_lid_collision(
    lid, enclosure, aligned_board, volume_tolerance_mm3=0.01
):
    board_collision = detect_collision(
        lid, aligned_board, volume_tolerance_mm3
    )

    enclosure_collision = detect_collision(
        lid, enclosure, volume_tolerance_mm3
    )

    return {
        "collision_free": (
            not board_collision["collision_detected"]
            and not enclosure_collision["collision_detected"]
        ),
        "lid_board_collision": board_collision,
        "lid_enclosure_collision": enclosure_collision,
        "note": (
            "Surface contact is allowed. Lid fastening and "
            "physical assembly clearance are not verified."
        )
    }


def run_port_cutout_experiment(
    step_path, export_dir="assembly_results", clearance_mm=0.5
):
    baseline = run_assembly_check(step_path, export_dir=None)
    data, dims, mounting = get_assembly_configuration()
    wall = DEFAULT_WALL_THICKNESS_MM

    enclosure = create_enclosure(
        dims, wall_thickness_mm=wall, mounting=mounting
    )

    board = load_board_step(step_path)

    aligned = align_board_to_enclosure(
        board,
        dims,
        wall,
        data["standoff_height_mm"],
        pcb_origin_x=data["width_mm"] / 2,
        pcb_origin_y=data["length_mm"] / 2
    )

    proposals = suggest_port_cutouts(
        aligned, dims, wall, clearance_mm
    )

    modified, applied, skipped = apply_port_cutouts(
        enclosure, proposals, dims, wall
    )
    modified = add_lid_fasteners(modified, dims)

    after = detect_collision(modified, aligned)

    baseline_volume = baseline["collision"]["collision_volume_mm3"]
    after_volume = after["collision_volume_mm3"]

    enclosure_validation = validate_cad_geometry(modified)
    mounting_validation = check_mounting_alignment(
        data, mounting, board
    )

    lid = generate_lid(dims)
    lid_validation = validate_cad_geometry(lid)
    lid_collision = check_lid_collision(lid, modified, aligned)
    lid_fastener_validation = verify_lid_fasteners(modified, lid, dims)
    bridge_validation = check_cutout_bridges(applied, dims)

    collision_free = not after["collision_detected"]
    enclosure_valid = enclosure_validation["geometry_valid"]
    lid_valid = lid_validation["geometry_valid"]
    lid_collision_free = lid_collision["collision_free"]

    parameter_alignment = mounting_validation["parameter_alignment_passed"]
    step_alignment_verified = mounting_validation["step_hole_alignment_verified"]

    preliminary_checks_passed = all([
        collision_free,
        enclosure_valid,
        lid_valid,
        lid_collision_free,
        lid_fastener_validation["valid"],
        bridge_validation["passed"],
        parameter_alignment,
        len(skipped) == 0
    ])

    assembly_validated = (
        preliminary_checks_passed
        and step_alignment_verified
    )

    report = {
        "board_id": "raspberry_pi_4",
        "dimensions_mm": dims,
        "baseline_collision_mm3": baseline_volume,
        "candidate_collision": after,
        "reduction_mm3": round(baseline_volume - after_volume, 6),
        "cutout_clearance_mm": clearance_mm,
        "proposed_cutouts": proposals,
        "applied_cutouts": applied,
        "skipped_cutouts": skipped,
        "enclosure_geometry_validation": enclosure_validation,
        "mounting_alignment": mounting_validation,
        "lid_geometry_validation": lid_validation,
        "lid_collision": lid_collision,
        "lid_fastener_validation": lid_fastener_validation,
        "cutout_bridge_validation": bridge_validation,
        "verification_summary": {
            "collision_free": collision_free,
            "enclosure_geometry_valid": enclosure_valid,
            "lid_geometry_valid": lid_valid,
            "lid_collision_free": lid_collision_free,
            "lid_fasteners_valid": lid_fastener_validation["valid"],
            "cutout_bridges_valid": bridge_validation["passed"],
            "mounting_parameters_consistent": parameter_alignment,
            "step_hole_alignment_verified": step_alignment_verified,
            "all_cutouts_applied": len(skipped) == 0,
            "preliminary_checks_passed": preliminary_checks_passed,
            "assembly_validated": assembly_validated
        },
        "assembly_validated": assembly_validated,
        "limitations": [
            "STEP mounting-hole centers are verified against configured standoff positions.",
            "Fastener fit and manufacturing tolerances are not verified.",
            "Port cutouts use STEP bounding boxes, not semantic port recognition.",
            "The lid has four screw mounting tabs; screws and thread engagement are not simulated.",
            "Physical fit and printability have not been verified."
        ]
    }

    output = Path(export_dir)
    output.mkdir(parents=True, exist_ok=True)

    cq.exporters.export(
        enclosure,
        str(output / "enclosure_before_cutouts.step")
    )

    cq.exporters.export(
        modified,
        str(output / "enclosure_candidate_cutouts.step")
    )

    cq.exporters.export(
        aligned,
        str(output / "raspberry_pi_aligned.step")
    )

    cq.exporters.export(
        lid,
        str(output / "enclosure_lid.step")
    )

    (output / "port_cutout_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    (output / "final_verification_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Raspberry Pi 4 virtual assembly and geometry verification"
    )

    parser.add_argument("step_path")
    parser.add_argument("--output", default="assembly_results")
    parser.add_argument("--auto-ports", action="store_true")
    parser.add_argument("--clearance", type=float, default=0.5)

    args = parser.parse_args()

    if args.auto_ports:
        report = run_port_cutout_experiment(
            args.step_path, args.output, args.clearance
        )
    else:
        report = run_assembly_check(
            args.step_path, args.output
        )

    print(json.dumps(report, indent=2))