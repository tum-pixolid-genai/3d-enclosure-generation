"""Local PNG/JPEG plus optional text to the unchanged Design Spec v0.1."""

import argparse
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from time import perf_counter
import warnings

from PIL import Image, UnidentifiedImageError
from jsonschema import Draft202012Validator, ValidationError

from agent.agent import load_validator, save_design
from agent.capability_check import check_capability, unsupported_features
from agent.llm_agent import AgentError, DESIGN_SCHEMA, LLMAgent, USAGE_FIELDS, ollama_request, parse_json
from agent.semantic_checks import ground_draft
from . import visual_audit


MODEL = "qwen3-vl:4b-instruct-q4_K_M"
MODEL_DIGEST = "84f7ed8042fa7cdbd902f7dcb7d0370e032095047cc3244179f263b77b5bc318"
PORT = 11441
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 1024}
PROMPT = Path(__file__).resolve().parent / "prompts/vision_v0.1.3.md"
MAX_BYTES = 10 * 1024 * 1024


def read_image(path):
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise AgentError("invalid_image", "Use a PNG or JPEG image.")
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise AgentError("invalid_image", "Image exceeds the 10 MiB limit.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as picture:
                size, kind = picture.size, picture.format
                if kind not in {"PNG", "JPEG"} or max(size) > 2048 or min(size) < 16:
                    raise AgentError("invalid_image", "Use a PNG/JPEG between 16 and 2048 pixels per side.")
                picture.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning, ValueError) as error:
        raise AgentError("invalid_image", f"Cannot decode image: {error}") from error
    return data, {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                  "width": size[0], "height": size[1], "format": kind}


def apply_evidence_policy(raw, evidence, instructions, task_id):
    """Retain visual requirements and source restrictions without pretending to verify vision."""
    draft = deepcopy(raw)
    changes = []
    questions = list(draft["clarification_questions"])
    if draft["needs_clarification"] and not questions:
        questions.append("Which image requirements remain uncertain? Please provide the missing details.")
    request = {
        "task_id": task_id,
        "request_text": instructions if instructions else "Image enclosure request without text.",
        "language": "en",
    }
    grounded_text, normalized, _, text_issues = ground_draft(request, draft)

    def replace(field, value, reason):
        if draft[field] != value:
            changes.append({"field": field, "model": draft[field], "corrected": value, "reason": reason})
        draft[field] = value

    replace("board_id", grounded_text["board_id"], "Board identity requires explicit accompanying text.")
    replace("wall_thickness_mm", grounded_text["wall_thickness_mm"],
            "Only explicit accompanying text supplies wall thickness and units.")
    for key in ("board_id", "case_shape", "lid", "mounting", "port_requirements", "wall_thickness_mm"):
        if key in {"board_id", "wall_thickness_mm"}:
            continue
        text_value = grounded_text[key]
        explicit = (
            (key == "case_shape" and text_value != "unspecified")
            or (key == "lid" and text_value["present"] is not None)
            or (key == "mounting" and text_value["wall_mount_hole_count"] is not None)
            or (key == "port_requirements" and bool(text_value))
        )
        if explicit and draft[key] != text_value:
            questions.append(f"The image draft and accompanying text disagree about {key}; please confirm.")

    if draft["board_id"] is None:
        questions.append("Which exact board should this enclosure fit? Its type cannot be determined from appearance.")
    if draft["case_shape"] == "unspecified":
        questions.append("Which enclosure shape is intended by the image?")
    if draft["lid"]["present"] is None:
        questions.append("Does the image require an open top or a lid?")
    for key in ("case_shape", "lid", "port_requirements", "mounting"):
        value = draft[key]
        claimed = ((key == "case_shape" and value != "unspecified")
                   or (key == "lid" and value["present"] is not None)
                   or (key == "port_requirements" and bool(value))
                   or (key == "mounting" and value["wall_mount_hole_count"] is not None))
        if claimed and not evidence["visual_evidence"][key].strip():
            questions.append(f"Please provide visible or textual evidence for {key}.")
    if draft["port_requirements"]:
        corrected_ports = []
        for port in draft["port_requirements"]:
            # Pose-to-physical-axis conversion is intentionally manual for v0.1.
            if (port["requested_side"] != "unspecified"
                    and not re.search(r"\b" + re.escape(port["requested_side"]) + r"\b", instructions.lower())):
                port = {**port, "requested_side": "unspecified"}
            corrected_ports.append(port)
            if port["port_type"] == "unknown" or port["requested_side"] == "unspecified":
                questions.append(f"Please identify the connector type and physical side for {port['port_type']} openings.")
        replace("port_requirements", corrected_ports, "Unlabelled image pose supplies no physical coordinate frame.")
    questions.extend(issue["question"] for issue in text_issues if issue["code"] != "board")
    if any(issue["code"] in {"port_exclusion", "port_scope", "port_conflict"} for issue in text_issues):
        replace("port_requirements", grounded_text["port_requirements"],
                "Conflicting or excluded text requirements need clarification before visual ports can be used.")
    questions.extend(evidence["image_questions"])
    if evidence["unrepresented_features"]:
        questions.append("Please resolve features outside Design Spec v0.1: "
                         + ", ".join(evidence["unrepresented_features"]))
    replace("clarification_questions", list(dict.fromkeys(questions)), "Conservative evidence questions.")
    replace("needs_clarification", bool(questions), "Unresolved image requirements need confirmation.")
    gate = check_capability(draft, request=normalized if instructions else None)
    gate["unsupported"] = unsupported_features(draft)
    gate["unrepresented_features"] = evidence["unrepresented_features"]
    # The image cannot certify that no additional features were overlooked.
    if gate["allow_geometry"]:
        gate.update(status="review_required", allow_geometry=False)
        gate["review_reasons"].append("Visual requirements need independent review before CAD.")
    return draft, gate, changes


class VisionAgent:
    def __init__(self, *, port=PORT, chat=None, audit_chat=None):
        self.port = port
        self.chat = chat
        self.audit_chat = audit_chat
        self.validator = load_validator(DESIGN_SCHEMA)
        extraction_schema = LLMAgent().generation_schema
        fields = ("case_shape", "lid", "port_requirements", "mounting")
        self.schema = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "design": extraction_schema,
                "visual_evidence": {
                    "type": "object", "additionalProperties": False,
                    "properties": {field: {"type": "string"} for field in fields},
                    "required": list(fields),
                },
                "unrepresented_features": {"type": "array", "items": {"type": "string"}},
                "image_questions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["design", "visual_evidence", "unrepresented_features", "image_questions"],
        }
        self.response_validator = Draft202012Validator(self.schema)
        self.prompt = PROMPT.read_text(encoding="utf-8")

    def extract(self, image_path, *, task_id, instructions=""):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", task_id):
            raise AgentError("invalid_request", "Invalid task ID.")
        if not isinstance(instructions, str) or len(instructions) > 2000:
            raise AgentError("invalid_request", "Instructions must be a string of at most 2000 characters.")
        data, metadata = read_image(Path(image_path))
        payload = {
            "model": MODEL, "format": self.schema, "stream": False,
            "options": OPTIONS, "keep_alive": "10m",
            "messages": [
                {"role": "system", "content": self.prompt},
                {"role": "user", "content": json.dumps({"instructions": instructions}),
                 "images": [base64.b64encode(data).decode("ascii")]},
            ],
        }
        start = perf_counter()
        response = self.chat(payload) if self.chat else ollama_request("/api/chat", payload, port=self.port)
        if not isinstance(response, dict):
            raise AgentError("invalid_model_output", "Ollama returned a non-object response.")
        message = response.get("message")
        raw = message.get("content") if isinstance(message, dict) else None
        usage = {key: response[key] for key in USAGE_FIELDS if key in response}
        if not isinstance(raw, str) or response.get("done") is not True or response.get("done_reason") not in (None, "stop"):
            raise AgentError("invalid_model_output", "Incomplete vision response.", raw_reply=raw, usage=usage)
        try:
            parsed = parse_json(raw)
            self.response_validator.validate(parsed)
        except (ValueError, ValidationError, RecursionError) as error:
            raise AgentError("invalid_model_output", str(error), raw_reply=raw, usage=usage) from error
        raw_design = {
            "schema_version": "0.1", "task_id": task_id, **parsed["design"],
            "assumptions": ["Image interpretation does not verify dimensions, physical fit, or printability."],
        }
        self.validator.validate(raw_design)
        audit_payload = {
            "model": MODEL, "format": visual_audit.SCHEMA, "stream": False,
            "options": {**OPTIONS, "num_predict": 768}, "keep_alive": "10m",
            "messages": [
                {"role": "system", "content": visual_audit.PROMPT.read_text(encoding="utf-8")},
                {"role": "user", "content": "Inspect the actual image for spatial structure and visible openings.",
                 "images": [base64.b64encode(data).decode("ascii")]},
            ],
        }
        audit_response = (self.audit_chat(audit_payload) if self.audit_chat
                          else ollama_request("/api/chat", audit_payload, port=self.port))
        try:
            audit, audit_raw = visual_audit.decode(audit_response)
        except AgentError as error:
            error.usage = {"primary": usage, "primary_raw_reply": raw}
            raise
        explicit, _, _, _ = ground_draft({
            "task_id": task_id, "request_text": instructions or "Image without accompanying text.",
            "language": "en",
        }, raw_design)
        reconciled, audit_changes, unverified = visual_audit.reconcile(raw_design, audit, parsed, explicit)
        draft, gate, changes = apply_evidence_policy(reconciled, parsed, instructions, task_id)
        self.validator.validate(draft)
        return {
            "task_id": task_id, "design_spec": draft, "raw_design_spec": raw_design,
            "raw_reply": raw, "evidence": {key: parsed[key] for key in parsed if key != "design"},
            "changes": audit_changes + changes, "capability": gate, "image": metadata,
            "visual_audit": audit, "audit_raw_reply": audit_raw,
            "unverified_features": unverified,
            "input_mode": "image_plus_text" if instructions.strip() else "image_only",
            "audit_usage": {key: audit_response[key] for key in USAGE_FIELDS if key in audit_response},
            "instructions": instructions, "usage": usage,
            "latency_ms": round((perf_counter() - start) * 1000, 3),
            "schema_valid": True,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--instructions", default="")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    try:
        result = VisionAgent(port=args.port).extract(args.image, task_id=args.task_id, instructions=args.instructions)
    except AgentError as error:
        print(json.dumps({"error": error.code, "message": str(error), "raw_reply": error.raw_reply}))
        return 1
    folder = args.output_dir / args.task_id
    folder.mkdir(parents=True, exist_ok=False)
    save_design(folder / "result.json", json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    save_design(folder / "design_spec.json", json.dumps(result["design_spec"], indent=2) + "\n")
    print(json.dumps({"folder": str(folder), "capability": result["capability"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
