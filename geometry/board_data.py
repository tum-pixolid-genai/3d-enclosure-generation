# Placeholder board data for MVP testing only.
# Replace with verified mechanical specifications before physical validation.

BOARD_DATA = {
    "test_board": {
        "width_mm": 65.0,
        "length_mm": 30.0,
        "height_mm": 12.0,
    }
}


def get_board_data(board_id):
    return BOARD_DATA.get(board_id)