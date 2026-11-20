"""Create original deterministic engineering sketch fixtures for development."""

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / "examples"


def draw_box(kind):
    image = Image.new("RGB", (640, 480), "white")
    draw = ImageDraw.Draw(image)
    line = "#223348"
    outer = [(80, 180), (390, 100), (550, 205), (240, 295)]
    inner = [(111, 182), (387, 126), (516, 208), (241, 269)]
    draw.polygon(outer, fill="#c1d0dc", outline=line, width=3)
    draw.polygon(inner, fill="#f5f8fa", outline=line, width=3)
    draw.line([(111, 182), (111, 233), (241, 321), (516, 258), (516, 208)],
              fill=line, width=2)
    draw.line([(111, 233), (387, 176), (516, 258)], fill=line, width=2)
    draw.line([(387, 126), (387, 176)], fill=line, width=2)
    draw.polygon([(80, 180), (240, 295), (240, 400), (80, 285)],
                 fill="#b2c8d8", outline=line, width=3)
    draw.polygon([(240, 295), (550, 205), (550, 310), (240, 400)],
                 fill="#cbd9e3", outline=line, width=3)
    if kind == "lid":
        draw.polygon([(100, 84), (402, 24), (554, 103), (252, 169)],
                     fill="#d5dfe5", outline=line, width=4)
        draw.polygon([(100, 84), (252, 169), (252, 180), (100, 95)],
                     fill="#a2b7c7", outline=line, width=3)
        draw.polygon([(252, 169), (554, 103), (554, 114), (252, 180)],
                     fill="#b8c9d5", outline=line, width=3)
    if kind == "ports":
        draw.polygon([(310, 304), (362, 289), (362, 324), (310, 339)],
                     fill="#34495e", outline=line, width=3)
        draw.polygon([(416, 271), (474, 254), (474, 300), (416, 317)],
                     fill="#34495e", outline=line, width=3)
    return image


def main():
    EXAMPLES.mkdir(exist_ok=True)
    images = {
        "open.png": draw_box("open"),
        "lid.png": draw_box("lid"),
        "ports.png": draw_box("ports"),
        "ambiguous.jpg": Image.new("RGB", (640, 480), "white"),
    }
    draw = ImageDraw.Draw(images["ambiguous.jpg"])
    draw.rounded_rectangle((180, 130, 460, 340), radius=45, outline="#2f3e46", width=5)
    draw.line((202, 171, 438, 171), fill="#2f3e46", width=3)
    for name, image in images.items():
        path = EXAMPLES / name
        if path.exists():
            raise SystemExit(f"Fixture exists: {path}")
        image.save(path)
    base = {
        "board_id": None, "case_shape": "rectangular", "lid": {"present": False, "style": "unspecified"},
        "port_requirements": [], "mounting": {"wall_mount_hole_count": None}, "wall_thickness_mm": None,
    }
    cases = [
        {"id": "IMG-01", "image": "open.png", "instructions": "",
         "reference": {**base}, "expected": "needs_clarification",
         "note": "Rectangular open enclosure. No image evidence identifies a board or a wall dimension."},
        {"id": "IMG-02", "image": "lid.png", "instructions": "",
         "reference": {**base, "lid": {"present": True, "style": "unspecified"}},
         "expected": "needs_clarification", "note": "Separate cover above enclosure, attachment unverified."},
        {"id": "IMG-03", "image": "ports.png", "instructions": "",
         "reference": {**base, "port_requirements": [
             {"port_type": "unknown", "requested_side": "unspecified", "count": 2}]},
         "expected": "needs_clarification",
         "note": "Two generic rectangular side cutouts. Connector types and physical axes are absent."},
        {"id": "IMG-04", "image": "ambiguous.jpg", "instructions": "",
         "reference": {**base, "case_shape": "unspecified",
                       "lid": {"present": None, "style": "unspecified"}},
         "expected": "needs_clarification",
         "note": "A rounded outline and one line do not establish enclosure geometry or a lid."},
        {"id": "IMG-05", "image": "open.png",
         "instructions": "Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.",
         "reference": {**base, "board_id": "raspberry_pi_4", "wall_thickness_mm": 2},
         "expected": "review_required",
         "note": "Image supplies the open shape, accompanying text supplies board and wall thickness. Manual visual review precedes optional CAD."},
    ]
    for case in cases:
        case["image_sha256"] = hashlib.sha256((EXAMPLES / case["image"]).read_bytes()).hexdigest()
    doc = {
        "provenance": "Original synthetic engineering diagrams and proposed reference answers prepared for Qianshun Gu with Codex assistance. No external photos or personal data.",
        "review_status": "Author-proposed labels. Independent teammate review is pending.",
        "data_license": "CC BY 4.0 for eligible contributed diagrams and reference annotations to the extent the contributor holds relevant rights.",
        "cases": cases,
    }
    target = EXAMPLES / "cases.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(doc, stream, indent=2)
    print(target)


if __name__ == "__main__":
    main()
