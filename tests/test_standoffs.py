import math

import cadquery as cq
import pytest

from geometry.board_data import get_board_data
from geometry.checks import (
    check_geometry,
    DEFAULT_WALL_THICKNESS_MM,
)
from geometry.cad_model import create_enclosure, verify_enclosure


def build_pi4_enclosure():
    """Build the Raspberry Pi 4 enclosure with mounting standoffs."""

    board = get_board_data("raspberry_pi_4")

    spec = {
        "board_id": "raspberry_pi_4",
        "case_shape": "rectangular",
        "wall_thickness_mm": DEFAULT_WALL_THICKNESS_MM,
    }

    result = check_geometry(spec)

    assert result["valid"], result["errors"]

    dimensions = result["dimensions"]

    mounting = {
        "height_mm": board["standoff_height_mm"],
        "diameter_mm": 5.0,
        "screw_hole_diameter_mm": 2.0,
        "spacing_x_mm": board["mounting_hole_spacing_x_mm"],
        "spacing_y_mm": board["mounting_hole_spacing_y_mm"],
        "edge_offset_mm": board["mounting_hole_edge_offset_mm"],
        "board_width_mm": board["width_mm"],
        "board_length_mm": board["length_mm"],
    }

    enclosure = create_enclosure(
        dimensions,
        DEFAULT_WALL_THICKNESS_MM,
        mounting=mounting,
    )

    return board, dimensions, mounting, enclosure


def get_standoff_positions(board, mounting):
    """Calculate expected standoff positions relative to PCB centre."""

    x1 = -board["width_mm"] / 2 + mounting["edge_offset_mm"]
    x2 = x1 + mounting["spacing_x_mm"]

    y1 = -board["length_mm"] / 2 + mounting["edge_offset_mm"]
    y2 = y1 + mounting["spacing_y_mm"]

    return [
        (x1, y1),
        (x1, y2),
        (x2, y1),
        (x2, y2),
    ]


def get_bottom_z(dimensions):
    return (
        -dimensions["outer_height_mm"] / 2
        + DEFAULT_WALL_THICKNESS_MM
    )


def test_four_standoffs_exist():
    """Check that all four standoffs are present in the CAD solid."""

    board, dimensions, mounting, enclosure = build_pi4_enclosure()

    bottom_z = get_bottom_z(dimensions)
    positions = get_standoff_positions(board, mounting)

    assert len(positions) == 4

    # Check material exists inside each standoff wall.
    sample_z = bottom_z + mounting["height_mm"] / 2

    sample_radius = (
        mounting["diameter_mm"]
        + mounting["screw_hole_diameter_mm"]
    ) / 4

    solid = enclosure.val()

    for x, y in positions:
        point = cq.Vector(x + sample_radius, y, sample_z)

        assert solid.isInside(point, tolerance=1e-6), (
            f"Missing standoff at ({x}, {y})"
        )


def test_standoff_height_is_three_mm():
    """Check that each standoff extends exactly 3 mm above the floor."""

    board, dimensions, mounting, enclosure = build_pi4_enclosure()

    assert mounting["height_mm"] == pytest.approx(3.0)

    bottom_z = get_bottom_z(dimensions)
    positions = get_standoff_positions(board, mounting)

    solid = enclosure.val()

    sample_radius = (
        mounting["diameter_mm"]
        + mounting["screw_hole_diameter_mm"]
    ) / 4

    for x, y in positions:
        inside_point = cq.Vector(
            x + sample_radius,
            y,
            bottom_z + mounting["height_mm"] - 0.01,
        )

        above_point = cq.Vector(
            x + sample_radius,
            y,
            bottom_z + mounting["height_mm"] + 0.01,
        )

        assert solid.isInside(inside_point, tolerance=1e-6)
        assert not solid.isInside(above_point, tolerance=1e-6)


def test_standoff_spacing():
    """Check the four mounting positions use 58 x 49 mm spacing."""

    board, dimensions, mounting, enclosure = build_pi4_enclosure()

    positions = get_standoff_positions(board, mounting)

    xs = sorted(set(x for x, y in positions))
    ys = sorted(set(y for x, y in positions))

    assert len(xs) == 2
    assert len(ys) == 2

    assert xs[1] - xs[0] == pytest.approx(58.0)
    assert ys[1] - ys[0] == pytest.approx(49.0)

    # Confirm actual standoff material at the expected coordinates.
    solid = enclosure.val()
    sample_z = get_bottom_z(dimensions) + mounting["height_mm"] / 2

    sample_radius = (
        mounting["diameter_mm"]
        + mounting["screw_hole_diameter_mm"]
    ) / 4

    for x, y in positions:
        assert solid.isInside(
            cq.Vector(x + sample_radius, y, sample_z),
            tolerance=1e-6,
        )


def test_standoff_screw_holes_exist():
    """Check each standoff has an empty central pilot hole."""

    board, dimensions, mounting, enclosure = build_pi4_enclosure()

    bottom_z = get_bottom_z(dimensions)
    sample_z = bottom_z + mounting["height_mm"] / 2

    solid = enclosure.val()

    for x, y in get_standoff_positions(board, mounting):
        centre = cq.Vector(x, y, sample_z)

        # The centre must be empty.
        assert not solid.isInside(centre, tolerance=1e-6)

        # The surrounding annular wall must contain material.
        wall_radius = (
            mounting["diameter_mm"]
            + mounting["screw_hole_diameter_mm"]
        ) / 4

        wall_point = cq.Vector(
            x + wall_radius,
            y,
            sample_z,
        )

        assert solid.isInside(wall_point, tolerance=1e-6)


def test_standoffs_fit_inside_enclosure():
    """Check standoffs do not extend beyond the inner cavity."""

    board, dimensions, mounting, enclosure = build_pi4_enclosure()

    radius = mounting["diameter_mm"] / 2

    half_inner_width = dimensions["inner_width_mm"] / 2
    half_inner_length = dimensions["inner_length_mm"] / 2

    for x, y in get_standoff_positions(board, mounting):
        assert abs(x) + radius < half_inner_width
        assert abs(y) + radius < half_inner_length

    bottom_z = get_bottom_z(dimensions)

    assert (
        bottom_z + mounting["height_mm"]
        < dimensions["outer_height_mm"] / 2
    )

    assert enclosure.solids().size() == 1
    assert enclosure.val().isValid()


def test_standoff_enclosure_verification():
    """Check the existing CAD verification accepts the standoffs."""

    board, dimensions, mounting, enclosure = build_pi4_enclosure()

    errors = verify_enclosure(
        enclosure,
        dimensions,
        DEFAULT_WALL_THICKNESS_MM,
        mounting=mounting,
    )

    assert errors == []