"""Record a human's explicit approval of one immutable image result."""

import argparse
import hashlib
import json
from pathlib import Path

from agent.agent import read_json, save_design


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    record = read_json(args.result)
    result = record.get("result", record)
    checksum = hashlib.sha256(args.result.read_bytes()).hexdigest()
    print(json.dumps({
        "design_spec": result["design_spec"], "capability": result["capability"],
        "image_sha256": result["image"]["sha256"], "source_result_sha256": checksum,
    }, indent=2))
    print("Inspect the actual source image, final JSON, evidence, uncertainties, and unsupported features.")
    reviewer = input("Reviewer name: ").strip()
    answer = input("Type APPROVE to authorize CAD for exactly this result, or press Enter to stop: ")
    if not reviewer or answer != "APPROVE":
        raise SystemExit("CAD approval was not granted.")
    save_design(args.output, json.dumps({
        "approved": True, "reviewer": reviewer, "source_result_sha256": checksum,
        "authorization": "Explicit interactive approval of the displayed image result.",
    }, indent=2) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
