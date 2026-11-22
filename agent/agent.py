import argparse
import json
import math
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator, SchemaError, ValidationError


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_REQUEST = "examples/my_first_request.json"
DEFAULT_OUTPUT_DIR = "outputs"

# Full phrases and explicit boundaries keep isolated keywords from becoming requirements.
ENCLOSURE = re.compile(
    r"(?:please )?(?:design|make|build|create) (?:a |an )?"
    r"(?P<shape>rectangular )?(?:case|enclosure)(?: for (?P<board>.+))?"
)
PORT_TYPE = r"(?:usb|ethernet|hdmi|power)"
PORT_LIST = rf"{PORT_TYPE}(?:(?:, and |, | and ){PORT_TYPE})*"
SIDE = r"front|back|left|right|top|bottom"
WALL_MOUNT = r"wall[- ]mount(?:ing)? holes?"
COUNT_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
COUNT = r"[0-9]+|" + "|".join(COUNT_WORDS)
MM = r"(?:mm|millimeters?|millimetres?)"
NUMBER = r"[0-9]+(?:\.[0-9]+)?"
SEPARATOR = r"(?:, and |[;,] ?| and )"
LID_STYLES = {"removable": "removable", "snap-fit": "snap_fit", "screwed": "screwed"}


def clause(pattern):
    """Match a whole supported requirement before consuming a separator."""
    return re.compile(rf"(?:{pattern})(?=$|{SEPARATOR})")


SEPARATOR_PATTERN = re.compile(SEPARATOR)
LID = clause(r"(?:a |the )?(?:(?P<style>removable|snap-fit|screwed) )?lid")
NO_LID = clause(r"(?:no |without )(?:a |the |any )?lid")
PORTS = clause(
    rf"(?P<negative>no |without )?(?:any )?(?:accessible )?(?P<ports>{PORT_LIST})"
    rf"(?: (?:openings?|ports?|access))?(?: (?:on|at) (?:the )?(?P<side>{SIDE})(?: side)?)?"
)
MOUNT = clause(rf"(?:exactly )?(?P<count>{COUNT}) (?:external )?{WALL_MOUNT}")
THICKNESS = clause(
    rf"(?:(?P<leading>{NUMBER}) {MM} wall thickness|wall thickness (?:of )?(?P<trailing>{NUMBER}) {MM})"
)
REQUIREMENT_START = re.compile(r" with |(?= without )")


def finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"Non-finite JSON number: {text}")
    return value


def reject_json_constant(text):
    raise ValueError(f"Invalid JSON constant: {text}")


def read_json(path):
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file, parse_float=finite_float, parse_constant=reject_json_constant)
    except (OSError, ValueError, RecursionError) as error:
        raise ValueError(f"Cannot read JSON from {path}: {error}") from error


def load_validator(path):
    schema = read_json(path)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as error:
        raise ValueError(f"Invalid JSON Schema at {path}: {error.message}") from error
    return Draft202012Validator(schema)


def parse_requirements(text, questions):
    lid_presence = set()
    lid_styles = set()
    port_sides = {}
    excluded_ports = set()
    mount_counts = set()
    wall_thicknesses = set()
    unresolved_clauses = []
    ambiguous_negation = False

    while text:
        match = NO_LID.match(text)
        if match:
            lid_presence.add(False)
        elif (not ambiguous_negation or False in lid_presence) and (match := LID.match(text)):
            lid_presence.add(True)
            if match["style"]:
                lid_styles.add(LID_STYLES[match["style"]])
        elif (match := PORTS.match(text)) and (match["negative"] or not ambiguous_negation):
            for port in re.findall(PORT_TYPE, match["ports"]):
                if match["negative"]:
                    excluded_ports.add(port)
                else:
                    sides = port_sides.setdefault(port, set())
                    if match["side"]:
                        sides.add(match["side"])
        elif not ambiguous_negation and (match := MOUNT.match(text)):
            count = match["count"]
            try:
                mount_counts.add(COUNT_WORDS[count] if count in COUNT_WORDS else int(count))
            except ValueError:
                questions.append("How many external wall-mount holes should the enclosure have?")
        elif not ambiguous_negation and (match := THICKNESS.match(text)):
            value = float(match["leading"] or match["trailing"])
            if math.isfinite(value) and value > 0:
                wall_thicknesses.add(value)
            else:
                questions.append("What positive wall thickness in millimeters is required?")
        else:
            # An unrecognized "and" may belong to the unknown phrase or carry a negation.
            # Resume only at an explicit punctuation boundary.
            boundary = r"; ?" if ambiguous_negation or text.startswith(("no ", "without ")) else r"[;,] ?"
            unknown, *remainder = re.split(boundary, text, maxsplit=1)
            unresolved_clauses.append(unknown)
            questions.append(f"Could you restate this requirement in a supported form: {unknown!r}?")
            text = re.sub(r"^and ", "", remainder[0]) if remainder else ""
            ambiguous_negation = False
            continue

        rest = text[match.end():]
        ambiguous_negation = rest.startswith(" and ") and text.startswith(("no ", "without "))
        text = SEPARATOR_PATTERN.sub("", rest, count=1)
        if rest and not text:
            questions.append("What additional requirement follows the final separator?")

    unresolved = " ".join(unresolved_clauses)
    if len(lid_presence) > 1 or len(lid_styles) > 1:
        questions.append("Should the enclosure have a lid, and which single lid style is required?")
        lid_presence.clear()
        lid_styles.clear()
    if re.search(r"\blids?\b", unresolved):
        lid = {"present": None, "style": "unspecified"}
    else:
        lid = {"present": next(iter(lid_presence), None), "style": next(iter(lid_styles), "unspecified")}

    ports = []
    unresolved_ports = set(re.findall(rf"\b{PORT_TYPE}\b", unresolved))
    for port, sides in port_sides.items():
        if port in excluded_ports:
            questions.append(f"Should the enclosure include or exclude {port.upper()} openings?")
        elif len(sides) > 1:
            questions.append(f"Which side is required for {port.upper()} openings?")
        elif port not in unresolved_ports:
            ports.append({"port_type": port, "requested_side": next(iter(sides), "unspecified"), "count": None})
    for port in sorted(excluded_ports - port_sides.keys()):
        questions.append(f"Can you confirm that {port.upper()} openings must be excluded? The v0.1 format cannot record port exclusions.")

    if len(mount_counts) > 1:
        questions.append("How many external wall-mount holes should the enclosure have?")
    if len(wall_thicknesses) > 1:
        questions.append("Which single wall thickness in millimeters is required?")

    if re.search(rf"\b{WALL_MOUNT}\b", unresolved):
        mount_counts.clear()
    if "wall thickness" in unresolved:
        wall_thicknesses.clear()

    return {
        "lid": lid,
        "port_requirements": ports,
        "mounting": {"wall_mount_hole_count": next(iter(mount_counts)) if len(mount_counts) == 1 else None},
        "wall_thickness_mm": next(iter(wall_thicknesses)) if len(wall_thicknesses) == 1 else None,
    }


def extract_design(request):
    """Extract a draft from a Schema-validated request without reading or writing files."""
    questions = []
    board_id = None
    shape = "unspecified"
    requirements = ""
    text = " ".join(request["request_text"].lower().split()).removesuffix(".")

    if request.get("language", "en") != "en":
        questions.append("Could you provide the enclosure request in English?")
    else:
        head, *tail = REQUIREMENT_START.split(text, maxsplit=1)
        requirements = tail[0].strip() if tail else ""
        if match := ENCLOSURE.fullmatch(head):
            if match["shape"]:
                shape = "rectangular"
            if match["board"] in {"raspberry pi 4", "a raspberry pi 4", "the raspberry pi 4"}:
                board_id = "raspberry_pi_4"
        else:
            questions.append("Could you specify the enclosure and board using 'Make a case for Raspberry Pi 4'?")
        if board_id is None:
            questions.append("Which supported board should the enclosure fit? The Mock currently recognizes Raspberry Pi 4.")
        if tail and not requirements:
            questions.append("What features should the enclosure include?")

    design = parse_requirements(requirements, questions)
    return {
        "schema_version": "0.1",
        "task_id": request["task_id"],
        "board_id": board_id,
        "case_shape": shape,
        **design,
        "needs_clarification": bool(questions),
        "clarification_questions": list(dict.fromkeys(questions)),
        "assumptions": ["Board dimensions and connector positions require verified reference data."],
    }


def save_design(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("x", encoding="utf-8")
    try:
        with stream:
            stream.write(content)
    except OSError:
        # Only remove a partial file that this process opened successfully.
        path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a v0.1 enclosure draft with the rule-based Mock.")
    parser.add_argument("input_file", nargs="?", default=DEFAULT_REQUEST, type=Path)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, type=Path,
                        help="Output directory, relative to the Agent folder unless absolute.")
    args = parser.parse_args(argv)
    request_path = PROJECT_DIR / args.input_file
    try:
        request = read_json(request_path)
        request_validator = load_validator(PROJECT_DIR / "schemas/request.schema.json")
        request_validator.validate(request)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", request["task_id"]):
            raise ValidationError("task_id must contain only the supported identifier characters")
        output_validator = load_validator(PROJECT_DIR / "schemas/design_spec.schema.json")
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except ValidationError as error:
        print(f"INVALID: {request_path}: {error.message}", file=sys.stderr)
        return 1

    design = extract_design(request)
    try:
        output_validator.validate(design)
    except ValidationError as error:
        print(f"INVALID: Generated design for {request_path}: {error.message}", file=sys.stderr)
        return 1

    output_path = PROJECT_DIR / args.output_dir / f"{request['task_id']}_design_spec.json"
    content = json.dumps(design, indent=2, allow_nan=False)
    try:
        save_design(output_path, content)
    except FileExistsError as error:
        if error.filename == str(output_path):
            print(f"ERROR: Output already exists: {output_path}. Use a fresh --output-dir.", file=sys.stderr)
        else:
            print(f"ERROR: Cannot save {output_path}: {error}", file=sys.stderr)
        return 3
    except OSError as error:
        print(f"ERROR: Cannot save {output_path}: {error}", file=sys.stderr)
        return 3

    print("VALID: Input matches the JSON Schema.")
    print(f"Task ID: {request['task_id']}")
    print(f"Language: {request.get('language', 'en')}")
    print("\nMOCK DESIGN OUTPUT:")
    print(content)
    print(f"\nDesign specification saved successfully!\nFile: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
