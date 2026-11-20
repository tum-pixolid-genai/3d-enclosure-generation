"""Ground the supported v0.1 fields in independently recognized request text."""

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import math
import re

from .agent import COUNT_WORDS


PI4 = re.compile(r"\braspberry pi 4(?:\s*model\s*b|b)?\b")
BOARD = re.compile(r"\braspberry pi (?:[0-9]+(?:\s*model\s*b|b)?|zero(?: 2)?|pico)\b")
AMOUNT = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
UNIT = r"mm|cm|millimet(?:er|re)s?|centimet(?:er|re)s?|inches|inch|in"
MEASURE = rf"(?P<value>{AMOUNT})[ \t]*(?P<unit>{UNIT})(?!\w)"
WALL = re.compile(
    rf"\bwall(?:s| thickness)?\s+(?:(?:of|is|are|should be|must be)\s+)?{MEASURE}"
    rf"|(?<![\w.])(?P<leading>{AMOUNT})[ \t]*(?P<leading_unit>{UNIT})\s+wall(?:s| thickness)?\b"
)
COUNT = r"(?:[0-9]+|" + "|".join(COUNT_WORDS) + ")"
LID = re.compile(
    r"\b(?:(?P<negative>no|without|omit|exclude|do not (?:add|include)|must not have)\s+)?"
    r"(?:(?:a|the|any)\s+)?(?:(?P<style>removable|snap-fit|screwed)\s+)?lids?\b"
)
PORT = r"(?:usb(?:-c|-a)?|ethernet|hdmi|displayport|audio|power)"
PORT_NOUN = r"(?:openings?|ports?|cutouts?|access)"
SIDE = r"front|back|rear|left|right|top|bottom"
PORT_ITEM = rf"(?:(?:exactly\s+)?{COUNT}\s+)?(?:(?:{SIDE})[- ](?:facing|side)\s+)?{PORT}\b(?:\s+{PORT_NOUN})?"
PORT_LIST = rf"{PORT_ITEM}(?:(?:\s*,\s*|\s+(?:and|or)\s+)(?:(?:and|or)\s+)?{PORT_ITEM})*"
PORT_GROUP = re.compile(
    rf"(?<![\w-])(?:(?P<negative>no|without|omit|exclude|never (?:include|add)|"
    rf"do not (?:include|add|cut)|must not have)\s+(?:any\s+)?)?"
    rf"(?P<items>{PORT_LIST})(?:\s+(?:on|at|in)\s+(?:the\s+)?(?P<side>{SIDE})\b(?:\s+side)?)?"
)
PORT_MEMBER = re.compile(
    rf"(?:(?P<count>{COUNT})\s+)?(?:(?P<side>{SIDE})[- ](?:facing|side)\s+)?(?P<port>{PORT})\b"
)
PORT_DENIAL = re.compile(
    r"\b(?:no|without|omit|exclude|never|not|prohibit(?:ed)?|avoid(?:ed|ing)?|forbidden|unnecessary)\b"
)
NO_PORTS = re.compile(r"\b(?:no|without)\s+(?:any\s+)?(?:ports?|port openings?|connector openings?)(?: at all)?\b")
MOUNT = re.compile(rf"\b(?P<count>no|{COUNT})\s+(?:external\s+)?wall[- ]mount(?:ing)? holes?\b")
SHAPE = re.compile(r"\b(rectangular|round|circular|hexagonal|custom)\b")
SPLIT_SCOPE = re.compile(r";|\.(?=\s|$)|\bbut\b")


def integer(word):
    if word in {"no", "zero"}:
        return 0
    return int(word) if word.isdigit() else COUNT_WORDS[word]


def wall_value(match):
    value = Decimal(match["value"] or match["leading"])
    unit = match["unit"] or match["leading_unit"]
    factor = (Decimal("25.4") if unit.startswith("in") else
              Decimal("10") if unit.startswith(("cm", "centi")) else Decimal("1"))
    result = value * factor
    if not math.isfinite(float(result)) or float(result) <= 0:
        raise ValueError("A wall thickness must be finite and positive.")
    return result


def collect_ports(text, ask):
    """Recognize bounded English groups and withhold ambiguous or denied openings."""
    positive = {}
    excluded = set()
    disputed = set()
    all_excluded = bool(NO_PORTS.search(text))
    for scope in SPLIT_SCOPE.split(text):
        groups = list(PORT_GROUP.finditer(scope))
        if not groups:
            continue
        # Remove fully recognized groups and phrases such as "no lid".
        # A remaining denial may govern a port from either direction.
        residue = PORT_GROUP.sub(" ", NO_PORTS.sub(" ", scope))
        residue = LID.sub(" ", residue)
        uncertain = bool(PORT_DENIAL.search(residue)) or any(group["negative"] for group in groups)
        for group in groups:
            members = list(PORT_MEMBER.finditer(group["items"]))
            side = group["side"] or "unspecified"
            side = "back" if side == "rear" else side
            tail = scope[group.end():]
            multiple_sides = bool(re.match(rf"\s+(?:and|or|/)\s+(?:the\s+)?(?:{SIDE})\b", tail))
            shared_count = (len(members) > 1 and members[0]["count"]
                            and any(item["count"] is None for item in members[1:]))
            alternatives = bool(re.search(r"\bor\b", group["items"]))
            for item in members:
                name = item["port"]
                count = integer(item["count"]) if item["count"] else None
                item_side = "back" if item["side"] == "rear" else item["side"]
                if group["negative"] or count == 0 or all_excluded:
                    excluded.add(name)
                    if all_excluded and not group["negative"] and count != 0:
                        disputed.add(name)
                    continue
                conflicting_side = item_side and side not in ("unspecified", item_side)
                if uncertain or multiple_sides or shared_count or alternatives or conflicting_side:
                    disputed.add(name)
                    continue
                positive.setdefault(name, set()).add((item_side or side, count))

    ports = []
    for name in sorted(positive.keys() | excluded | disputed):
        entries = positive.get(name, set())
        if name in disputed or (name in excluded and entries):
            ask("port_scope", f"Please clarify whether {name.upper()} openings are required, excluded, or optional, and specify their side and count.")
        elif name in excluded:
            ask("port_exclusion", f"Please confirm that {name.upper()} must be excluded. Design Spec v0.1 cannot represent a named port exclusion.")
        elif len(entries) != 1:
            ask("port_conflict", f"Which side and count are required for {name.upper()} openings?")
        else:
            side, count = next(iter(entries))
            ports.append({"port_type": name, "requested_side": side, "count": count})
    return ports


def ground_draft(request, draft):
    """Return an auditable spec plus the normalized source for the capability check."""
    text = " ".join(request["request_text"].lower().split())
    text = text.replace("’", "'").replace("don't", "do not")
    spec = deepcopy(draft)
    issues = []
    changes = []

    def ask(code, question):
        issues.append({"code": code, "question": question})

    def replace(key, value):
        original = spec[key]
        if key == "port_requirements":
            original = sorted(original, key=lambda port: (
                port["port_type"], port["requested_side"], port["count"] or 0,
            ))
        if original != value:
            changes.append({"field": key, "model": spec[key], "grounded": value})
        spec[key] = value

    board_tokens = list(BOARD.finditer(text))
    known = bool(PI4.search(text))
    ambiguous_board = (any(not PI4.fullmatch(token[0]) for token in board_tokens)
                       or bool(re.search(r"\bpi 4(?:b)?\s*(?:/|\bor\b|\band\b)\s*(?:\d|an? (?:unknown|other)|another)", text)))
    replace("board_id", "raspberry_pi_4" if known and not ambiguous_board else None)
    if spec["board_id"] is None:
        ask("board", "Which exact supported board should this enclosure fit?")

    shapes = set(SHAPE.findall(text))
    negated_shape = re.search(r"\b(?:not|non-)\s*(?:a\s+)?(?:rectangular|round|circular|hexagonal|custom)\b", text)
    shape = next(iter(shapes)) if len(shapes) == 1 and not negated_shape else "unspecified"
    replace("case_shape", shape if shape in ("rectangular", "unspecified") else "custom")
    if len(shapes) > 1 or negated_shape:
        ask("shape_conflict", "Which single enclosure shape is required?")

    lids = {(not match["negative"], (match["style"] or "unspecified").replace("-", "_"))
            for match in LID.finditer(text)}
    lids = {(present, style if present else "unspecified") for present, style in lids}
    if re.search(r"\b(?:leave|keep) (?:the )?top open\b|\bopen[- ]top\b", text):
        lids.add((False, "unspecified"))
    present, style = next(iter(lids)) if len(lids) == 1 else (None, "unspecified")
    if len(lids) > 1:
        ask("lid_conflict", "Should the enclosure have a lid, and which single style is required?")
    replace("lid", {"present": present, "style": style})

    mount_counts = {integer(match["count"]) for match in MOUNT.finditer(text)}
    if len(mount_counts) > 1:
        ask("wall_mount_conflict", "How many external wall mounting holes are required?")
    count = next(iter(mount_counts)) if len(mount_counts) == 1 else None
    replace("mounting", {"wall_mount_hole_count": count})
    replace("port_requirements", collect_ports(text, ask))

    walls = list(WALL.finditer(text))
    try:
        thicknesses = {wall_value(match) for match in walls}
    except (InvalidOperation, OverflowError, ValueError):
        thicknesses = set()
        ask("wall_units", "Please specify a finite positive wall thickness in mm.")
    alternative_wall = any(
        re.search(rf"{AMOUNT}(?:\s*(?:{UNIT}))?\s*(?:or|to|–)\s*$", text[:match.start()])
        for match in walls
    )
    if len(thicknesses) > 1 or alternative_wall:
        thicknesses.clear()
        ask("wall_conflict", "Which single wall thickness is required?")
    elif not walls and "wall thickness" in text:
        ask("wall_units", "What single wall thickness and unit should be used?")
    replace("wall_thickness_mm", float(next(iter(thicknesses))) if len(thicknesses) == 1 else None)

    questions = list(dict.fromkeys(
        [issue["question"] for issue in issues] + draft["clarification_questions"]
    ))
    if draft["needs_clarification"] and not questions:
        questions.append("Could you clarify which enclosure requirements are unresolved?")
    replace("clarification_questions", questions)
    replace("needs_clarification", bool(questions))

    normalized = PI4.sub("raspberry pi 4", text)
    if walls and len(thicknesses) == 1 and not any(issue["code"].startswith("wall_") for issue in issues):
        normalized = WALL.sub(lambda match: f"{format(wall_value(match), 'f')} mm wall thickness", normalized)
    return spec, {**request, "request_text": normalized}, changes, issues
