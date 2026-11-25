#!/usr/bin/env python3
"""Non-AI baseline for the request -> design step.

Catalog, Project 02: each AI step is compared with a non-AI baseline
("a template for standard requests, a geometric search for unusual shapes").

This file is the *template* baseline. It takes a structured form (board, lid,
ports + sides, mounting holes, wall thickness) and fills a fixed template that
produces a design spec in the Agent's output format (design_spec.schema.json
v0.1). There is no language model and no free-text parsing, so it can only
serve requests that fit the form ("standard requests"). It cannot notice
conflicting or vague wishes; those tasks are reported as not applicable.

The geometry stage is shared with the AI pipeline (Shanning's module), so
differences between conditions come from the design step only.

Library use:   spec = build_spec(task_id, form)
CLI:           python template_baseline.py tasks.json BM-PI4-025
"""
import json
import sys

SCHEMA_VERSION = "0.1"
LID_STYLES = {"removable", "snap_fit", "screwed"}


class FormError(ValueError):
    """The form cannot be expressed in the template (-> not applicable)."""


def build_spec(task_id, form):
    """form keys: board_id, lid ('removable'|'snap_fit'|'screwed'|'none'),
    ports [{'port','side'}], wall_mount_holes (int), wall_thickness_mm (num|None)
    """
    if not form.get("board_id"):
        raise FormError("board_id is required")
    lid = form.get("lid")
    if lid == "none":
        lid_obj = {"present": False, "style": "unspecified"}
    elif lid in LID_STYLES:
        lid_obj = {"present": True, "style": lid}
    else:
        raise FormError(f"unknown lid option: {lid!r}")

    # merge duplicate (port, side) pairs into one entry with a count
    merged = {}
    for p in form.get("ports", []):
        key = (p["port"], p["side"])
        merged[key] = merged.get(key, 0) + 1
    ports = [{"port_type": k[0], "requested_side": k[1],
              "count": (n if n > 1 else None)}
             for k, n in merged.items()]

    holes = form.get("wall_mount_holes", 0)
    if not isinstance(holes, int) or holes < 0:
        raise FormError("wall_mount_holes must be a non-negative integer")
    wall = form.get("wall_thickness_mm")
    if wall is not None and wall <= 0:
        raise FormError("wall thickness must be positive")

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "board_id": form["board_id"],
        "case_shape": "rectangular",
        "lid": lid_obj,
        "port_requirements": ports,
        "mounting": {"wall_mount_hole_count": holes},
        "wall_thickness_mm": wall,
        "needs_clarification": False,
        "clarification_questions": [],
        "assumptions": [
            "Template baseline: filled from a structured form, no language model.",
            "Board dimensions come from the geometry module's board data.",
        ],
    }


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    tasks = json.load(open(argv[1], encoding="utf-8"))["tasks"]
    task = next(t for t in tasks if t["task_id"] == argv[2])
    try:
        spec = build_spec(task["task_id"], task["expected"])
    except FormError as e:
        print(f"not applicable: {e}")
        return 1
    print(json.dumps(spec, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
