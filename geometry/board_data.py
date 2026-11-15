"""Board envelopes for preliminary CAD generation, not certified fit data."""

BOARD_DATA = {
    "test_board": {
        "width_mm": 65.0,
        "length_mm": 30.0,
        "height_mm": 12.0,
    },
    "raspberry_pi_4": {
        # Raspberry Pi 4 Model B PCB nominal footprint: approximately 85 x 56 mm.
        # The 18 mm height is a PROVISIONAL component-envelope allowance,
        # NOT a verified mechanical specification or connector clearance.
        "width_mm": 85.0,
        "length_mm": 56.0,
        "height_mm": 18.0,
    },
}


def get_board_data(board_id):
    return BOARD_DATA.get(board_id)
