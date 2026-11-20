"""A second pixel observation supplies an auditable, fallible consistency check."""

from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from agent.llm_agent import AgentError, parse_json


PROMPT = Path(__file__).resolve().parent / "prompts/visual_audit_v0.1.1.md"
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "scene": {"type": "string", "enum": ["enclosure_3d", "outline_2d", "uncertain"]},
        "scene_evidence": {"type": "string"},
        "lid_state": {"type": "string", "enum": ["open", "cover", "uncertain"]},
        "lid_evidence": {"type": "string"},
        "cover_panel_visible": {"type": "boolean"},
        "interior_floor_visible": {"type": "boolean"},
        "opening_certainty": {"type": "string", "enum": ["clear", "uncertain", "none"]},
        "openings": {
            "type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "description": {"type": "string", "minLength": 1},
                    "surface": {"type": "string", "enum": ["exterior_wall", "top_cavity", "uncertain"]},
                    "bbox": {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 1000},
                             "minItems": 4, "maxItems": 4},
                }, "required": ["description", "surface", "bbox"],
            },
        },
        "other_features": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["scene", "scene_evidence", "lid_state", "lid_evidence", "cover_panel_visible", "interior_floor_visible",
                 "opening_certainty", "openings", "other_features", "uncertainties"],
}


def decode(response):
    message = response.get("message") if isinstance(response, dict) else None
    raw = message.get("content") if isinstance(message, dict) else None
    try:
        if response.get("done") is not True or response.get("done_reason") not in (None, "stop"):
            raise ValueError("Incomplete visual inventory.")
        audit = parse_json(raw)
        Draft202012Validator(SCHEMA).validate(audit)
        boxes = []
        for item in audit["openings"]:
            x1, y1, x2, y2 = item["bbox"]
            if x2 <= x1 or y2 <= y1:
                raise ValueError("Opening bounding box has no positive area.")
            for left, top, right, bottom in boxes:
                if min(x2, right) > max(x1, left) and min(y2, bottom) > max(y1, top):
                    raise ValueError("Opening boxes overlap and may double-count.")
            boxes.append(item["bbox"])
        return audit, raw
    except (ValueError, TypeError, ValidationError, AttributeError) as error:
        raise AgentError("invalid_visual_audit", str(error), raw_reply=raw) from error


def reconcile(raw, audit, evidence, explicit_text):
    draft = deepcopy(raw)
    questions = []
    changes = []

    def replace(field, value, reason):
        if draft[field] != value:
            changes.append({"field": field, "model": draft[field], "corrected": value, "reason": reason})
            draft[field] = value

    if audit["scene"] != "enclosure_3d" or not audit["scene_evidence"].strip():
        if explicit_text["case_shape"] == "unspecified":
            replace("case_shape", "unspecified", "Independent observation does not establish spatial geometry.")
        if explicit_text["lid"]["present"] is None:
            replace("lid", {"present": None, "style": "unspecified"},
                    "A flat outline cannot establish a cavity or lid.")
        questions.append("Please clarify the three-dimensional shape and whether the image shows a lid or open cavity.")
    elif audit["cover_panel_visible"]:
        if draft["lid"]["present"] is False:
            questions.append("The two pixel observations disagree about the lid; please review the image.")
        replace("lid", {"present": True, "style": explicit_text["lid"]["style"] if explicit_text["lid"]["present"] else "unspecified"},
                "A separately reported cover panel establishes a lid, not its attachment mechanism.")
    elif audit["interior_floor_visible"]:
        if draft["lid"]["present"] is True:
            questions.append("The two pixel observations disagree about the lid; please review the image.")
        replace("lid", {"present": False, "style": "unspecified"}, "A visible cavity floor without a cover supports an open top.")
    elif audit["lid_state"] == "uncertain":
        if explicit_text["lid"]["present"] is None:
            replace("lid", {"present": None, "style": "unspecified"}, "The lid observation is uncertain.")
        questions.append("Please confirm whether a lid or open top is intended.")
    elif (draft["lid"]["present"] is not None
          and draft["lid"]["present"] != (audit["lid_state"] == "cover")):
        questions.append("The two pixel observations disagree about the lid; please review the image.")
        if explicit_text["lid"]["present"] is None:
            replace("lid", {"present": None, "style": "unspecified"}, "Conflicting visual observations.")

    count = sum(item["surface"] == "exterior_wall" for item in audit["openings"])
    if count and audit["opening_certainty"] == "clear" and not draft["port_requirements"]:
        replace("port_requirements", [{"port_type": "unknown", "requested_side": "unspecified", "count": count}],
                "A separate pixel inventory identified distinct generic openings.")
        questions.append("Please identify the observed openings and confirm their count and physical side.")
    elif audit["opening_certainty"] == "uncertain":
        questions.append("Possible openings are visually uncertain; please review them before design generation.")
    elif draft["port_requirements"] and not count:
        questions.append("Opening detection differs between observations; please confirm the visible cutouts.")
    elif count:
        model_counts = [port["count"] for port in draft["port_requirements"]]
        if all(value is not None for value in model_counts) and sum(model_counts) != count:
            questions.append("The opening counts differ between observations; please confirm the intended count.")

    unverified = []
    if evidence["unrepresented_features"] and not audit["other_features"]:
        unverified = list(evidence["unrepresented_features"])
        questions.append("Extra features reported by one observation lack corroboration; please review: "
                         + ", ".join(unverified))
    if audit["other_features"]:
        questions.append("Please review visible features outside the current CAD capability: "
                         + ", ".join(audit["other_features"]))
    questions.extend(audit["uncertainties"])
    draft["clarification_questions"] = list(dict.fromkeys(draft["clarification_questions"] + questions))
    draft["needs_clarification"] = bool(draft["clarification_questions"])
    return draft, changes, unverified
