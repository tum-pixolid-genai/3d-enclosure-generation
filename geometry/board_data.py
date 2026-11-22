"""Board envelopes for preliminary CAD generation, not certified fit data."""

BOARD_DATA = {
    "test_board": {
        "width_mm": 65.0,
        "length_mm": 30.0,
        "height_mm": 12.0,
    },
    "raspberry_pi_4": {
        # PCB dimensions
        "width_mm": 85.0,
        "length_mm": 56.0,

        # Component heights from mechanical reference
        "usb_stack_height_mm": 16.0,
        "ethernet_height_mm": 13.5,
        "gpio_height_mm": 8.5,

        # Mounting holes
        "mounting_hole_diameter_mm": 2.7,
        "mounting_hole_spacing_x_mm": 58.0,
        "mounting_hole_spacing_y_mm": 49.0,
        "mounting_hole_edge_offset_mm": 3.5,

        # Port centre positions
        "usb_ethernet_centres_mm": [9.0, 27.0, 45.75],

        # Preliminary board height reference
        "height_mm": 17.6,

        # Enclosure mounting design
        "standoff_height_mm": 3.0,
    },
}


def get_board_data(board_id):
    return BOARD_DATA.get(board_id)
