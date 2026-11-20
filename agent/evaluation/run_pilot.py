"""Compare the existing Mock and a real, single-attempt local Ollama run."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
from time import perf_counter

from jsonschema import ValidationError

from ..agent import PROJECT_DIR, extract_design, read_json, save_design
from ..capability_check import check_capability
from ..llm_agent import (
    AgentError, DESIGN_SCHEMA, LLMAgent, MODEL, OPTIONS, PORT, PROMPT_PATH, REQUEST_SCHEMA,
    TIMEOUT, ollama_request,
)


MODEL_DIGEST = "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0"
DATA = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def requirement_fields(spec):
    fields = {
        "board_id": spec["board_id"],
        "case_shape": spec["case_shape"],
        "lid.present": spec["lid"]["present"],
        "lid.style": spec["lid"]["style"],
        "wall_mount_hole_count": spec["mounting"]["wall_mount_hole_count"],
        "wall_thickness_mm": spec["wall_thickness_mm"],
    }
    ports = sorted(spec["port_requirements"], key=lambda p: (
        p["port_type"], p["requested_side"], p["count"] or 0,
    ))
    occurrences = Counter()
    for port in ports:
        name = port["port_type"]
        occurrences[name] += 1
        suffix = "" if occurrences[name] == 1 else f".{occurrences[name]}"
        key = f"opening.{name}{suffix}"
        fields[f"{key}.side"] = port["requested_side"]
        fields[f"{key}.count"] = port["count"]
    return fields


def score(reference, design):
    expected = requirement_fields(reference["requirements"])
    observed = requirement_fields(design) if design else {}
    differences = []
    for field in sorted(expected.keys() | observed.keys()):
        if field not in expected or (expected[field] is None and observed.get(field) is not None):
            kind = "extra"
        elif field not in observed or (observed[field] is None and expected[field] is not None):
            kind = "missing"
        elif expected[field] != observed[field]:
            kind = "incorrect"
        else:
            continue
        differences.append({"field": field, "kind": kind,
                            "expected": expected.get(field), "observed": observed.get(field)})

    clarification = False
    missed_topics = list(reference["clarification_topics"])
    if design:
        questions = design["clarification_questions"]
        text = " ".join(questions).lower()
        missed_topics = [topic for topic in missed_topics if topic not in text]
        clarification = (
            design["needs_clarification"] == reference["needs_clarification"]
            and bool(questions) == reference["needs_clarification"]
            and not missed_topics
        )
    return {
        "semantic_exact": not differences and bool(design),
        "expected_fields": len(expected),
        "correct_fields": sum(field in observed and observed[field] == value
                              for field, value in expected.items()),
        "differences": differences,
        "clarification_correct": clarification,
        "missing_clarification_topics": missed_topics,
    }


def run_case(agent, case, variant):
    request = case["request"]
    reference = case["reference"]
    record = {"case_id": case["id"], "category": case["category"], "variant": variant}
    design = None
    started = perf_counter()
    try:
        if variant == "mock":
            draft = extract_design(request)
        else:
            extraction = agent.extract(request)
            draft = extraction.design_spec
            record.update(raw_reply=extraction.raw_reply, usage=extraction.usage)
        agent.design_validator.validate(draft)
        design = draft
    except AgentError as error:
        record.update(error={"code": error.code, "message": str(error)},
                      raw_reply=error.raw_reply, usage=error.usage)
    except ValidationError as error:
        record["error"] = {"code": "invalid_design", "message": error.message}
    record["latency_ms"] = round((perf_counter() - started) * 1000, 3)
    record.update(design_spec=design, schema_valid=design is not None, **score(reference, design))
    gate = check_capability(design, request=request) if design is not None else None
    record["capability"] = gate
    record["capability_correct"] = gate is not None and gate["status"] == reference["capability"]
    record["unsafe_allow"] = bool(gate and gate["allow_geometry"] and reference["capability"] != "allow")
    return record


def summarize(rows):
    return {
        "attempts": len(rows),
        "schema_passes": sum(row["schema_valid"] for row in rows),
        "semantic_exact": sum(row["semantic_exact"] for row in rows),
        "correct_fields": sum(row["correct_fields"] for row in rows),
        "expected_fields": sum(row["expected_fields"] for row in rows),
        "differences": dict(Counter(diff["kind"] for row in rows for diff in row["differences"])),
        "clarification_correct": sum(row["clarification_correct"] for row in rows),
        "capability_correct": sum(row["capability_correct"] for row in rows),
        "unsafe_allow": sum(row["unsafe_allow"] for row in rows),
        "median_latency_ms": round(statistics.median(row["latency_ms"] for row in rows), 3),
    }


def run(cases_file, output_dir):
    cases = read_json(cases_file)
    agent = LLMAgent()
    for case in cases["cases"]:
        request = case["request"]
        reference = case["reference"]
        agent.request_validator.validate(request)
        agent.design_validator.validate({
            "task_id": request["task_id"], "schema_version": "0.1", "assumptions": [],
            **reference["requirements"], "needs_clarification": reference["needs_clarification"],
            "clarification_questions": reference["clarification_topics"],
        })
    version = ollama_request("/api/version")["version"]
    models = ollama_request("/api/tags")["models"]
    model = next((item for item in models if item["name"] == MODEL), None)
    if not model or model["digest"] != MODEL_DIGEST:
        raise SystemExit(f"The verified local model {MODEL} ({MODEL_DIGEST}) is required.")
    before = ollama_request("/api/ps")
    rows = []
    for case in cases["cases"]:
        for variant in ("mock", "llm"):
            row = run_case(agent, case, variant)
            rows.append(row)
            status = row["capability"]["status"] if row["capability"] else row["error"]["code"]
            print(f"{case['id']} {variant}: schema={row['schema_valid']} "
                  f"semantic={row['semantic_exact']} clarify={row['clarification_correct']} "
                  f"gate={status} {row['latency_ms']:.3f} ms", flush=True)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": cases["split"],
        "cases_sha256": digest(cases_file),
        "schema_version": agent.design_validator.schema["properties"]["schema_version"]["const"],
        "design_schema_sha256": digest(DESIGN_SCHEMA),
        "request_schema_sha256": digest(REQUEST_SCHEMA),
        "prompt_version": "llm_v0.2",
        "prompt_sha256": digest(PROMPT_PATH),
        "mock_source_sha256": digest(PROJECT_DIR / "agent.py"),
        "llm_source_sha256": digest(PROJECT_DIR / "llm_agent.py"),
        "gate_source_sha256": digest(PROJECT_DIR / "capability_check.py"),
        "python": platform.python_version(),
        "ollama_version": version,
        "model": model,
        "loopback_port": PORT,
        "options": OPTIONS,
        "socket_timeout_s": TIMEOUT,
        "attempts_per_case": 1,
        "loaded_models_before": before,
        "loaded_models_after": ollama_request("/api/ps"),
        "summary": {variant: summarize([row for row in rows if row["variant"] == variant])
                    for variant in ("mock", "llm")},
        "records": rows,
    }
    output = output_dir / f"{cases['split']}-report.json"
    save_design(output, json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {output}")
    return int(any(row.get("error") for row in rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DATA / "pilot_cases.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.cases, args.output_dir))
