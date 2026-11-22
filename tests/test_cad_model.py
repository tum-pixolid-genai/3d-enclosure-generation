import cadquery as cq
from geometry.cad_model import validate_usb_port

from geometry.cad_model import create_enclosure, verify_enclosure

def test_create_enclosure():
    dimensions = {
        "inner_width_mm": 60,
        "inner_length_mm": 40,
        "inner_height_mm": 12,
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    enclosure = create_enclosure(dimensions, wall_thickness_mm=2.0)

    # Check that the model contains exactly one solid.
    assert enclosure.solids().size() == 1

    # Check that the generated solid is geometrically valid.
    assert enclosure.val().isValid()

    # Check the outer dimensions.
    bounding_box = enclosure.val().BoundingBox()

    assert abs(bounding_box.xlen - 64) < 0.001
    assert abs(bounding_box.ylen - 44) < 0.001
    assert abs(bounding_box.zlen - 14) < 0.001

def test_enclosure_wall_thickness():
    dimensions = {
        "inner_width_mm": 60,
        "inner_length_mm": 40,
        "inner_height_mm": 12,
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    wall_thickness = 2.0

    enclosure = create_enclosure(dimensions, wall_thickness)

    assert enclosure.val().isValid()

    assert (
        dimensions["outer_width_mm"] - dimensions["inner_width_mm"]
    ) / 2 == wall_thickness

    assert (
        dimensions["outer_length_mm"] - dimensions["inner_length_mm"]
    ) / 2 == wall_thickness

    assert (
        dimensions["outer_height_mm"] - dimensions["inner_height_mm"]
    ) == wall_thickness

def test_verify_enclosure():
    dimensions = {
        "inner_width_mm": 60,
        "inner_length_mm": 40,
        "inner_height_mm": 12,
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    enclosure = create_enclosure(dimensions, 2.0)

    errors = verify_enclosure(enclosure, dimensions, 2.0)

    assert errors == []
def test_verify_incorrect_dimensions():
    dimensions = {
        "inner_width_mm": 60,
        "inner_length_mm": 40,
        "inner_height_mm": 12,
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    enclosure = create_enclosure(dimensions, 2.0)

    incorrect_dimensions = dimensions.copy()
    incorrect_dimensions["outer_width_mm"] = 70

    errors = verify_enclosure(
        enclosure,
        incorrect_dimensions,
        2.0,
    )

    assert "Incorrect outer width." in errors

def test_usb_port_cutout():
    dimensions = {
        "inner_width_mm": 60,
        "inner_length_mm": 40,
        "inner_height_mm": 12,
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    usb_port = {
        "width_mm": 10,
        "height_mm": 4,
        "x_mm": 0,
        "z_mm": 0,
    }

    enclosure_without_usb = create_enclosure(
        dimensions,
        wall_thickness_mm=2.0
    )

    enclosure_with_usb = create_enclosure(
        dimensions,
        wall_thickness_mm=2.0,
        usb_port=usb_port
    )

    assert enclosure_with_usb.val().isValid()

    assert (
        enclosure_with_usb.val().Volume()
        < enclosure_without_usb.val().Volume()
    )

def test_valid_usb_port_position():
    dimensions = {
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    usb_port = {
        "width_mm": 10,
        "height_mm": 4,
        "x_mm": 0,
        "z_mm": 0,
    }

    errors = validate_usb_port(dimensions, usb_port, 2.0)

    assert errors == []


def test_invalid_usb_port_position():
    dimensions = {
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    usb_port = {
        "width_mm": 10,
        "height_mm": 4,
        "x_mm": 30,
        "z_mm": 0,
    }

    errors = validate_usb_port(dimensions, usb_port, 2.0)

    assert "USB port exceeds the allowed horizontal boundary." in errors

import pytest


@pytest.mark.parametrize(
    "usb_port",
    [
        None,
        "USB",
        {"width_mm": 10, "height_mm": 4, "x_mm": 0},
        {"width_mm": -10, "height_mm": 4, "x_mm": 0, "z_mm": 0},
        {"width_mm": 10, "height_mm": 4, "x_mm": float("nan"), "z_mm": 0},
        {"width_mm": True, "height_mm": 4, "x_mm": 0, "z_mm": 0},
    ],
)
def test_invalid_usb_port_inputs(usb_port):
    dimensions = {
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    errors = validate_usb_port(dimensions, usb_port, 2.0)

    assert len(errors) > 0

def test_incorrect_wall_thickness():
    dimensions = {
        "inner_width_mm": 60,
        "inner_length_mm": 40,
        "inner_height_mm": 12,
        "outer_width_mm": 64,
        "outer_length_mm": 44,
        "outer_height_mm": 14,
    }

    enclosure = create_enclosure(dimensions, 2.0)

    errors = verify_enclosure(
        enclosure,
        dimensions,
        wall_thickness_mm=3.0,
    )

    assert "Incorrect wall thickness on X axis." in errors
    assert "Incorrect wall thickness on Y axis." in errors
    assert "Incorrect bottom thickness." in errors