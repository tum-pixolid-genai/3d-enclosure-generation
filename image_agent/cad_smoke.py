"""Export a separately reviewed simple image draft using the existing CAD engine."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

from agent.agent import load_validator, read_json, save_design
from agent.capability_check import unsupported_features
from agent.llm_agent import DESIGN_SCHEMA, parse_json


ROOT = Path(__file__).resolve().parents[1]
MVP = Path(os.environ.get(
    "PIXOLID_INTEGRATION_ROOT",
    ROOT if (ROOT / "geometry").is_dir() and (ROOT / "backend").is_dir()
    else ROOT.parent / "pixolid-mvp-windows-2026-11-16" / "checkouts",
))


def run(report_path, output, approval_path):
    source_bytes = report_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    approval = read_json(approval_path)
    if (approval.get("approved") is not True or approval.get("source_result_sha256") != source_hash
            or not isinstance(approval.get("reviewer"), str) or not approval["reviewer"].strip()):
        raise SystemExit("Explicit reviewer approval must match the exact result file SHA-256.")
    report = parse_json(source_bytes)
    result = report.get("result", report)
    draft = result["design_spec"]
    gate = result.get("capability", {})
    allowed_review_reason = "Visual requirements need independent review before CAD."
    if (gate.get("status") != "review_required" or gate.get("unsupported")
            or gate.get("questions")
            or any(reason != allowed_review_reason for reason in gate.get("review_reasons", []))
            or result.get("unverified_features")
            or result.get("visual_audit", {}).get("other_features")):
        raise SystemExit("Approval cannot override unresolved capability or visual-evidence checks.")
    load_validator(DESIGN_SCHEMA).validate(draft)
    if (report.get("corrected_differences") or draft["needs_clarification"] or draft["clarification_questions"]
            or draft["board_id"] != "raspberry_pi_4"
            or draft["case_shape"] != "rectangular"
            or draft["lid"] != {"present": False, "style": "unspecified"}
            or unsupported_features(draft)
            or result["evidence"]["unrepresented_features"]
            or draft["wall_thickness_mm"] is None
            or not result["instructions"]):
        raise SystemExit("This reviewed example is outside the supported simple CAD smoke scope.")
    import cadquery as cq

    output.mkdir(parents=True, exist_ok=False)
    for component in ("geometry", "backend"):
        component_root = MVP / component
        # Accept either isolated worktrees or a future shared repository.
        sys.path.insert(0, str(component_root if (component_root / component).is_dir() else MVP))
    from backend import geometry_service
    geometry_service.OUTPUT_DIR = output
    geometry = geometry_service.run_geometry(draft)
    if not geometry.get("valid") or geometry.get("errors"):
        raise SystemExit(f"Geometry rejected draft: {geometry}")
    files = {}
    for suffix in ("step", "stl"):
        path = output / f"{draft['task_id']}.{suffix}"
        if not path.is_file() or not path.stat().st_size:
            raise SystemExit(f"Export missing: {path}")
        files[suffix] = {"bytes": path.stat().st_size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    step = cq.importers.importStep(str(output / f"{draft['task_id']}.step"))
    solid = step.val()
    box = solid.BoundingBox()
    actual = (box.xlen, box.ylen, box.zlen)
    dims = geometry["dimensions"]
    expected = tuple(dims[key] for key in ("outer_width_mm", "outer_length_mm", "outer_height_mm"))
    assert step.solids().size() == 1 and solid.isValid()
    assert all(abs(a - b) < 0.001 for a, b in zip(actual, expected, strict=True))
    mesh = (output / f"{draft['task_id']}.stl").read_bytes()
    triangle_count = struct.unpack_from("<I", mesh, 80)[0]
    assert triangle_count > 0 and len(mesh) == 84 + 50 * triangle_count
    coordinates = [triangle[start:start + 3]
                   for triangle in struct.iter_unpack("<12fH", mesh[84:]) for start in (3, 6, 9)]
    mesh_bounds = [max(point[axis] for point in coordinates) - min(point[axis] for point in coordinates)
                   for axis in range(3)]
    assert all(abs(a - b) < 0.001 for a, b in zip(mesh_bounds, expected, strict=True))
    files["stl"].update(triangles=triangle_count, dimensions_mm=mesh_bounds)
    floor = -actual[2] / 2 + draft["wall_thickness_mm"]
    mounts = [(x, y) for x in (-39, 19) for y in (-24.5, 24.5)]
    for x, y in mounts:
        assert solid.isInside(cq.Vector(x + 1.75, y, floor + 1.5), tolerance=1e-6)
        assert not solid.isInside(cq.Vector(x, y, floor + 1.5), tolerance=1e-6)
    evidence = {
        "source_result_sha256": source_hash,
        "approval": approval,
        "mode": "Explicit local smoke test after visual and semantic review of this example.",
        "automatic_image_gate": result["capability"],
        "design_spec": draft, "geometry": geometry, "files": files,
        "step_readback": {"valid_solids": 1, "dimensions_mm": actual, "standoff_xy_mm": mounts},
        "physical_fit": "unverified",
    }
    save_design(output / "cad-evidence.json", json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--approval-file", type=Path, required=True)
    args = parser.parse_args()
    run(args.result, args.output_dir, args.approval_file)
