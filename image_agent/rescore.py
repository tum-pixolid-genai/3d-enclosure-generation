"""Correct the initial experiment's status-name comparison without new inference."""

import argparse
import hashlib
import json
from pathlib import Path

from agent.agent import read_json, save_design


def run(source):
    report = read_json(source)
    fixtures = read_json(Path(__file__).resolve().parents[1] / "examples/cases.json")
    expected = {case["id"]: {"needs_clarification": "clarification_required"}.get(
        case["expected"], case["expected"]) for case in fixtures["cases"]}
    outcomes = [{
        "case_id": row["case_id"], "expected_gate": expected[row["case_id"]],
        "actual_gate": row["result"]["capability"]["status"],
        "matches": row["result"]["capability"]["status"] == expected[row["case_id"]],
    } for row in report["records"] if "result" in row]
    correction = {
        "reason": "Map API needs_clarification to capability clarification_required before comparison.",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "new_inference_performed": False,
        "capability_as_expected": sum(row["matches"] for row in outcomes),
        "attempts": report["summary"]["attempts"], "outcomes": outcomes,
    }
    save_design(source.with_name("report-status-correction.json"),
                json.dumps(correction, indent=2) + "\n")
    print(json.dumps(correction, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    run(args.source)
