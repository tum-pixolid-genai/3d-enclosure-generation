"""Decide whether a validated draft can reach the current enclosure generator."""

if __package__:
    from .agent import extract_design
else:
    from agent import extract_design


def unsupported_features(design, *, assembly_wall_thickness_mm=None):
    issues = []
    if design["board_id"] not in (None, "raspberry_pi_4"):
        issues.append({"code": "unsupported_board", "board_id": design["board_id"]})
    if design["case_shape"] not in ("rectangular", "unspecified"):
        issues.append({"code": "unsupported_shape", "shape": design["case_shape"]})
    if design["lid"]["present"] is True:
        if assembly_wall_thickness_mm is None or design["lid"]["style"] != "screwed":
            issues.append({"code": "lid", "style": design["lid"]["style"]})
        elif design["wall_thickness_mm"] not in (None, assembly_wall_thickness_mm):
            issues.append({
                "code": "assembly_wall_thickness",
                "requested_mm": design["wall_thickness_mm"],
                "supported_mm": assembly_wall_thickness_mm,
            })
    for port in design["port_requirements"]:
        issues.append({"code": "port_opening", **port})
    count = design["mounting"]["wall_mount_hole_count"]
    if count:
        issues.append({"code": "external_wall_mount_holes", "count": count})
    return issues


def feature_key(issue):
    return issue["code"], issue.get("port_type"), issue.get("requested_side")


def check_capability(design, *, request=None, assembly_wall_thickness_mm=None):
    """Keep unsupported CAD features, user questions, and review reasons distinct.

    Both arguments should already have passed the v0.1 validators. Without
    the original request the gate can identify unsupported spec features, but
    it cannot authorize generation. The Mock is the source cross-check for the
    narrow automatic path and never replaces the LLM's extracted fields.
    """
    allow_assembly = assembly_wall_thickness_mm is not None
    source_draft = (
        extract_design(request, allow_assembly=allow_assembly)
        if request is not None else None
    )
    issues = unsupported_features(design, assembly_wall_thickness_mm=assembly_wall_thickness_mm)
    if source_draft is not None:
        detected = {feature_key(issue) for issue in issues}
        for issue in unsupported_features(source_draft, assembly_wall_thickness_mm=assembly_wall_thickness_mm):
            if feature_key(issue) not in detected:
                issues.append({**issue, "source": "request_cross_check"})
                detected.add(feature_key(issue))

    questions = design["clarification_questions"]
    review = []
    if design["board_id"] is None or design["case_shape"] == "unspecified":
        review.append("Board and enclosure shape must be known.")
    supported_lids = [{"present": False, "style": "unspecified"}]
    if allow_assembly:
        supported_lids.append({"present": True, "style": "screwed"})
    if design["lid"] not in supported_lids:
        review.append(
            "Specify either no lid or a screwed lid." if allow_assembly
            else "The automatic path requires an explicit no-lid request."
        )
    if source_draft is None:
        review.append("The original request is required for automatic generation.")
    elif source_draft["needs_clarification"]:
        review.append("The original request is outside the verified simple patterns.")
    elif any(design[key] != source_draft[key] for key in (
        "board_id", "case_shape", "lid", "mounting", "wall_thickness_mm",
    )):
        review.append("The draft disagrees with independently extracted request fields.")

    if design["needs_clarification"]:
        status = "clarification_required"
    elif issues:
        status = "unsupported"
    elif review or questions:
        status = "review_required"
    else:
        status = "allow"
    return {
        "status": status,
        "allow_geometry": status == "allow",
        "unsupported": issues,
        "questions": questions,
        "review_reasons": review,
    }
