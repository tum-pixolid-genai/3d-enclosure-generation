"""Run one actual local vision inference per declared development image."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

from agent.agent import read_json, save_design
from agent.llm_agent import AgentError, DESIGN_SCHEMA, ollama_request
from .vision_agent import MODEL, MODEL_DIGEST, OPTIONS, PORT, PROMPT, VisionAgent
from .visual_audit import PROMPT as AUDIT_PROMPT


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(reference, spec):
    differences = []
    for key, expected in reference.items():
        observed = spec[key]
        if key == "port_requirements":
            expected = sorted(expected, key=lambda p: json.dumps(p, sort_keys=True))
            observed = sorted(observed, key=lambda p: json.dumps(p, sort_keys=True))
        if expected != observed:
            differences.append({"field": key, "expected": expected, "observed": observed})
    return differences


def field_scores(reference, actual):
    def flatten(value, prefix=""):
        result = {}
        if isinstance(value, dict):
            for key, item in value.items():
                result.update(flatten(item, f"{prefix}.{key}"))
        elif isinstance(value, list) and value:
            for index, item in enumerate(sorted(value, key=lambda entry: json.dumps(entry, sort_keys=True))):
                result.update(flatten(item, f"{prefix}.{index}"))
        else:
            result[prefix] = value
        return result
    expected = flatten(reference)
    observed = flatten({key: actual[key] for key in reference})
    missing = object()
    return {
        "correct": sum(observed.get(key, missing) == value for key, value in expected.items()),
        "total": len(expected),
        "extra": sum(key not in expected or (expected[key] is None and value is not None)
                     for key, value in observed.items()),
        "omitted": sum(key not in observed or (observed[key] is None and value is not None)
                       for key, value in expected.items()),
    }


def run(output, cases_path=None, port=PORT):
    output.mkdir(parents=True, exist_ok=False)
    cases_path = cases_path or ROOT / "examples/cases.json"
    fixtures = read_json(cases_path)
    version = ollama_request("/api/version", port=port)
    model = next((m for m in ollama_request("/api/tags", port=port)["models"] if m["name"] == MODEL), None)
    if not model or model["digest"] != MODEL_DIGEST:
        raise SystemExit("Install the verified vision model before running this experiment.")
    agent = VisionAgent(port=port)
    report = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": model, "ollama_version": version["version"], "options": OPTIONS,
        "prompt_sha256": sha(PROMPT), "schema_sha256": sha(DESIGN_SCHEMA),
        "audit_prompt_sha256": sha(AUDIT_PROMPT),
        "fixtures_sha256": sha(cases_path),
        "split": fixtures.get("split", "development"), "runtime_port": port,
        "review_status": fixtures["review_status"], "records": [],
    }
    save_design(output / "system-prompt.md", PROMPT.read_text(encoding="utf-8"))
    save_design(output / "audit-prompt.md", AUDIT_PROMPT.read_text(encoding="utf-8"))
    for case in fixtures["cases"]:
        path = cases_path.parent / case["image"]
        if sha(path) != case["image_sha256"]:
            raise SystemExit(f"Fixture hash changed: {case['image']}")
        row = {"case_id": case["id"], "expected": case["reference"]}
        try:
            result = agent.extract(path, task_id=case["id"], instructions=case["instructions"])
            row.update(
                result=result,
                raw_differences=compare(case["reference"], result["raw_design_spec"]),
                corrected_differences=compare(case["reference"], result["design_spec"]),
                raw_fields=field_scores(case["reference"], result["raw_design_spec"]),
                corrected_fields=field_scores(case["reference"], result["design_spec"]),
                capability_as_expected=result["capability"]["status"] == {
                    "needs_clarification": "clarification_required",
                }.get(case["expected"], case["expected"]),
            )
            save_design(output / f"{case['id']}-design_spec.json",
                        json.dumps(result["design_spec"], indent=2) + "\n")
            print(f"{case['id']}: schema PASS, gate={result['capability']['status']}, "
                  f"raw differences={len(row['raw_differences'])}, "
                  f"corrected differences={len(row['corrected_differences'])}, "
                  f"{result['latency_ms']:.1f} ms", flush=True)
        except AgentError as error:
            row["error"] = {"code": error.code, "message": str(error), "raw_reply": error.raw_reply,
                            "usage": error.usage}
            print(f"{case['id']}: {error.code}: {error}", flush=True)
        report["records"].append(row)
        save_design(output / f"{case['id']}-result.json", json.dumps(row, indent=2) + "\n")
    report["loaded_models"] = ollama_request("/api/ps", port=port)
    good = [row for row in report["records"] if "result" in row]
    report["summary"] = {
        "attempts": len(fixtures["cases"]), "schema_pass": len(good),
        "raw_exact": sum(not row["raw_differences"] for row in good),
        "corrected_exact": sum(not row["corrected_differences"] for row in good),
        "capability_as_expected": sum(row["capability_as_expected"] for row in good),
        "median_latency_ms": statistics.median(row["result"]["latency_ms"] for row in good) if good else None,
        "raw_fields_correct": sum(row["raw_fields"]["correct"] for row in good),
        "corrected_fields_correct": sum(row["corrected_fields"]["correct"] for row in good),
        "reference_fields": sum(row["raw_fields"]["total"] for row in good),
        "raw_extra": sum(row["raw_fields"]["extra"] for row in good),
        "raw_omitted": sum(row["raw_fields"]["omitted"] for row in good),
    }
    save_design(output / "report.json", json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))
    return int(len(good) != len(fixtures["cases"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    raise SystemExit(run(args.output_dir, args.cases, args.port))
