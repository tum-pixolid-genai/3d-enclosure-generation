"""Regressions for visual evidence conflicts and mandatory CAD approval."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from image_agent.visual_audit import decode, reconcile
from image_agent.cad_smoke import run as run_cad
from agent.llm_agent import AgentError


def draft():
    return {
        "case_shape": "rectangular", "lid": {"present": False, "style": "unspecified"},
        "port_requirements": [], "clarification_questions": [], "needs_clarification": False,
    }


def inventory():
    return {
        "scene": "enclosure_3d", "scene_evidence": "Cavity, rim and several depth edges.",
        "lid_state": "open", "lid_evidence": "Visible interior.",
        "cover_panel_visible": False, "interior_floor_visible": True,
        "opening_certainty": "clear",
        "openings": [
            {"description": "First dark exterior rectangular cutout", "surface": "exterior_wall", "bbox": [250, 500, 350, 650]},
            {"description": "Second dark exterior rectangular cutout", "surface": "exterior_wall", "bbox": [450, 500, 550, 650]},
        ],
        "other_features": [], "uncertainties": [],
    }


class ReadinessTests(unittest.TestCase):
    def test_missed_distinct_openings_are_preserved_for_review(self):
        result, changes, _ = reconcile(draft(), inventory(), {"unrepresented_features": []}, draft())
        self.assertEqual(result["port_requirements"], [
            {"port_type": "unknown", "requested_side": "unspecified", "count": 2},
        ])
        self.assertTrue(result["needs_clarification"])
        self.assertTrue(changes)

    def test_flat_outline_does_not_establish_shape_or_lid(self):
        audit = {**inventory(), "scene": "outline_2d", "openings": [], "lid_state": "uncertain"}
        explicit = {**draft(), "case_shape": "unspecified", "lid": {"present": None, "style": "unspecified"}}
        result, _, _ = reconcile(draft(), audit, {"unrepresented_features": []}, explicit)
        self.assertEqual(result["case_shape"], "unspecified")
        self.assertIsNone(result["lid"]["present"])
        self.assertTrue(result["needs_clarification"])

    def test_unsupported_hinge_requires_corroboration_and_review(self):
        result, _, unverified = reconcile(draft(), inventory(), {"unrepresented_features": ["hinge"]}, draft())
        self.assertEqual(unverified, ["hinge"])
        self.assertTrue(result["needs_clarification"])
        self.assertTrue(any("lack corroboration" in item for item in result["clarification_questions"]))

    def test_overlapping_boxes_cannot_double_count_openings(self):
        audit = inventory()
        audit["openings"][1]["bbox"] = audit["openings"][0]["bbox"]
        with self.assertRaises(AgentError):
            decode({"done": True, "done_reason": "stop", "message": {"content": json.dumps(audit)}})

    def test_unconfirmed_or_stale_approval_cannot_reach_geometry(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "result.json"
            source.write_text("{}", encoding="utf-8")
            approval = base / "approval.json"
            for permitted in (False, True):
                approval.write_text(json.dumps({
                    "approved": permitted, "source_result_sha256": "wrong",
                    "reviewer": "Test reviewer",
                }), encoding="utf-8")
                with self.assertRaises(SystemExit):
                    run_cad(source, base / "cad", approval)
                self.assertFalse((base / "cad").exists())


if __name__ == "__main__":
    unittest.main()
