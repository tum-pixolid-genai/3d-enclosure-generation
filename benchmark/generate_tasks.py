#!/usr/bin/env python3
"""Generate the benchmark task set for the Pixolid enclosure project.

50 request "slots" x 4 boards = 200 tasks (catalog, Project 02: "about 200
tasks = around 50 requests and shapes x 4 common boards").

Every task carries a `request` object that follows the Agent's
request.schema.json v0.1 (task_id, request_text, language) so it can be sent
to the Agent / Backend unchanged. Everything else (board, category, expected
outcome) is benchmark metadata kept OUTSIDE the request object, because the
request schema forbids extra fields.

Deterministic: the same script always produces the same tasks.

Usage:  python generate_tasks.py [--out tasks.json]
Port inventories below are from general knowledge of the boards and MUST be
checked against manufacturer drawings before the benchmark is frozen.
"""
import argparse
import json
import random

# --- board palettes ---------------------------------------------------------
# text: how a port is written in a request; kind: normalised port name
BOARDS = {
    "raspberry_pi_4": {
        "label": "Raspberry Pi 4",
        "tag": "PI4",
        "ports": [("USB", "usb"), ("Ethernet", "ethernet"),
                  ("HDMI", "hdmi"), ("power", "power")],
    },
    "raspberry_pi_3b_plus": {
        "label": "Raspberry Pi 3 Model B+",
        "tag": "PI3",
        "ports": [("USB", "usb"), ("Ethernet", "ethernet"),
                  ("HDMI", "hdmi"), ("power", "power")],
    },
    "raspberry_pi_zero_2_w": {
        "label": "Raspberry Pi Zero 2 W",
        "tag": "PZ2",
        "ports": [("USB", "usb"), ("mini HDMI", "hdmi"),
                  ("power", "power"), ("SD card", "sd_card")],
    },
    "arduino_uno_r3": {
        "label": "Arduino Uno R3",
        "tag": "UNO",
        "ports": [("USB", "usb"), ("power", "power")],
    },
}
# Ports that do NOT exist on a board (used for the clarification tests)
MISSING_PORT = {
    "raspberry_pi_4": ("VGA", "vga"),
    "raspberry_pi_3b_plus": ("USB-C", "usb_c"),
    "raspberry_pi_zero_2_w": ("Ethernet", "ethernet"),
    "arduino_uno_r3": ("Ethernet", "ethernet"),
}
SIDES = ["front", "back", "left", "right"]
LIDS = {
    "removable": "a removable lid",
    "snap_fit": "a snap-fit lid",
    "screwed": "a screwed lid",
    "none": "no lid",
}
NUM_WORDS = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def join_ports(texts):
    if len(texts) == 1:
        return texts[0]
    return ", ".join(texts[:-1]) + " and " + texts[-1]


def mount_phrase(n):
    if n == 0:
        return None
    return f"{NUM_WORDS[n]} wall-mount hole" + ("" if n == 1 else "s")


def build_text(label, lid, port_groups, mount, wall):
    """port_groups: list of (side, [port texts]) -> request sentence."""
    parts = []
    if lid:
        parts.append(LIDS[lid])
    for side, texts in port_groups:
        parts.append(f"{join_ports([p[0] for p in texts])} openings on the {side}")
    mp = mount_phrase(mount) if mount is not None else None
    if mp:
        parts.append(mp)
    if wall:
        parts.append(f"{wall} mm wall thickness")
    text = f"Design a rectangular enclosure for {label}"
    if parts:
        text += " with " + join_ports(parts)
    return text + "."


def slots(rng, board):
    """Return the 50 slot specs for one board."""
    ports = board["ports"]
    out = []

    def pick(k):
        return rng.sample(ports, min(k, len(ports)))

    # A. basic: board + lid only (6)
    for lid, mount in [("removable", 0), ("snap_fit", 0), ("screwed", 0),
                       ("none", 0), ("removable", 2), ("snap_fit", 1)]:
        out.append(dict(cat="basic", diff="easy", lid=lid, groups=[], mount=mount, wall=None))
    # B. single port opening (8)
    for i in range(8):
        p = ports[i % len(ports)]
        out.append(dict(cat="single_port", diff="easy",
                        lid=rng.choice(["removable", "snap_fit"]),
                        groups=[(SIDES[i % 4], [p])], mount=0, wall=None))
    # C. several ports on the same side (8)
    for i in range(8):
        ps = pick(2 if len(ports) <= 2 else rng.choice([2, 3]))
        out.append(dict(cat="multi_port_same_side", diff="medium",
                        lid=rng.choice(["removable", "snap_fit", "screwed"]),
                        groups=[(SIDES[i % 4], ps)], mount=0, wall=None))
    # D. ports on different sides (8)
    for i in range(8):
        ps = pick(2 if len(ports) <= 2 else rng.choice([2, 3]))
        sides = rng.sample(SIDES, 2)
        groups = [(sides[0], ps[:1]), (sides[1], ps[1:])]
        out.append(dict(cat="multi_port_diff_sides", diff="medium",
                        lid=rng.choice(["removable", "screwed"]),
                        groups=groups, mount=0, wall=None))
    # E. lid variants combined with a port (6)
    for lid in ["removable", "snap_fit", "screwed", "none", "snap_fit", "screwed"]:
        p = rng.choice(ports)
        out.append(dict(cat="lid_variant", diff="easy", lid=lid,
                        groups=[(rng.choice(SIDES), [p])], mount=0, wall=None))
    # F. wall mounting (6)
    for n in [1, 2, 2, 3, 4, 4]:
        ps = pick(2)
        out.append(dict(cat="wall_mount", diff="medium",
                        lid=rng.choice(["removable", "screwed"]),
                        groups=[(rng.choice(SIDES), ps)], mount=n, wall=None))
    # G. wall thickness (4)
    for w in ["1.5", "2", "2.5", "3"]:
        p = rng.choice(ports)
        out.append(dict(cat="wall_thickness", diff="easy", lid="removable",
                        groups=[(rng.choice(SIDES), [p])], mount=0, wall=w))
    # H. clarification / conflicting requests (4) -- Agent should ask, not guess
    out.append(dict(cat="clarify_conflict_lid", diff="hard"))
    out.append(dict(cat="clarify_missing_port", diff="hard"))
    out.append(dict(cat="clarify_vague", diff="hard"))
    out.append(dict(cat="clarify_unsupported_unit", diff="hard"))
    return out


def realise(board_id, board, idx, s):
    label = board["label"]
    tid = f"BM-{board['tag']}-{idx:03d}"
    exp = {"board_id": board_id, "needs_clarification": False}
    cat = s["cat"]

    if cat == "clarify_conflict_lid":
        text = f"Design a rectangular enclosure for {label} with a removable lid and no lid."
        exp.update(needs_clarification=True, reason="conflicting lid instructions")
    elif cat == "clarify_missing_port":
        t, k = MISSING_PORT[board_id]
        text = f"Design a rectangular enclosure for {label} with a removable lid and {t} openings on the front."
        exp.update(needs_clarification=True, reason=f"{t} does not exist on this board")
    elif cat == "clarify_vague":
        text = f"Make a nice case for my {label}, something sturdy that looks good on a shelf."
        exp.update(needs_clarification=True, reason="no checkable requirements")
    elif cat == "clarify_unsupported_unit":
        text = f"Design a rectangular enclosure for {label} with a snap-fit lid and 0.08 inch wall thickness."
        exp.update(needs_clarification=True, reason="inch unit / unusual thickness; confirm in mm")
    else:
        text = build_text(label, s["lid"], s["groups"], s["mount"], s["wall"])
        exp.update(
            lid=s["lid"],
            ports=[{"port": p[1], "side": side}
                   for side, ps in s["groups"] for p in ps],
            wall_mount_holes=s["mount"],
            wall_thickness_mm=float(s["wall"]) if s["wall"] else None,
        )

    task = {
        "task_id": tid,
        "board_id": board_id,
        "category": cat,
        "difficulty": s["diff"],
        "request": {"task_id": tid, "request_text": text, "language": "en"},
        "expected": exp,
    }
    if board_id == "raspberry_pi_4" and cat in {"multi_port_same_side", "multi_port_diff_sides"}:
        task["geometry_scope"] = "unsupported_user_selected_opening_sides"
    return task


def make_unique(board_id, board, idx, s, seen):
    """Re-draw side / lid until the request text is new for this board."""
    s = dict(s)
    if s["cat"].startswith("clarify"):
        return realise(board_id, board, idx, s)
    lid_order = ["removable", "snap_fit", "screwed", "none"]
    for attempt in range(16):
        t = realise(board_id, board, idx, s)
        if t["request"]["request_text"] not in seen:
            return t
        if s["groups"] and attempt % 2 == 0:
            side, ps = s["groups"][0]
            s["groups"] = [(SIDES[(SIDES.index(side) + 1) % 4], ps)] + s["groups"][1:]
        elif s["lid"] and s["lid"] in lid_order:
            s["lid"] = lid_order[(lid_order.index(s["lid"]) + 1) % 3]  # never flips to "none"
    raise RuntimeError(f"cannot make {board_id} slot {idx} unique")


def pi4_assembly_tasks():
    """Keep the new assembly cohort outside the historical 50 Pi 4 tasks."""
    board_id = "raspberry_pi_4"
    requests = [
        ("Design a rectangular enclosure for Raspberry Pi 4 with a screwed lid and automatic port openings.", None),
        ("Make a rectangular case for Raspberry Pi 4 with automatic port cutouts and a screwed lid.", None),
        ("Create a rectangular case for Raspberry Pi 4 with a screwed lid, STEP-based port cutouts, and 2 mm wall thickness.", 2.0),
    ]
    tasks = []
    for index, (prompt, wall) in enumerate(requests, start=1):
        task_id = f"BM-PI4-ASM-{index:03d}"
        tasks.append({
            "task_id": task_id,
            "board_id": board_id,
            "category": "screwed_lid_automatic_cutouts",
            "difficulty": "easy",
            "request": {"task_id": task_id, "request_text": prompt, "language": "en"},
            "expected": {
                "board_id": board_id, "lid": "screwed", "ports": [],
                "wall_mount_holes": 0, "wall_thickness_mm": wall,
                "needs_clarification": False, "assembly_validated": True,
                "all_cutouts_applied": True,
            },
        })
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tasks.json")
    ap.add_argument("--assembly-out", help="write a separate Pi 4 assembly cohort")
    args = ap.parse_args()

    tasks = []
    for b_i, (board_id, board) in enumerate(BOARDS.items()):
        rng = random.Random(2026 * 10 + b_i)  # fixed seed per board
        seen = set()
        for i, s in enumerate(slots(rng, board), start=1):
            t = make_unique(board_id, board, i, s, seen)
            seen.add(t["request"]["request_text"])
            tasks.append(t)

    doc = {
        "benchmark_version": "0.1-draft",
        "note": ("Draft for team review. Port inventories per board are "
                 "unverified against manufacturer drawings. 'expected' is what "
                 "the user asked for, not a statement about physical fit."),
        "n_tasks": len(tasks),
        "tasks": tasks,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
    print(f"wrote {len(tasks)} tasks to {args.out}")
    if args.assembly_out:
        assembly_tasks = pi4_assembly_tasks()
        with open(args.assembly_out, "w", encoding="utf-8") as f:
            json.dump({"benchmark_version": "pi4-assembly-0.1", "n_tasks": len(assembly_tasks),
                       "tasks": assembly_tasks}, f, indent=2)
            f.write("\n")
        print(f"wrote {len(assembly_tasks)} tasks to {args.assembly_out}")


if __name__ == "__main__":
    main()
