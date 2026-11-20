"""Regression tests using deliberately incorrect, schema-valid model drafts."""

import unittest

from agent.agent import extract_design, load_validator
from agent.capability_check import check_capability
from agent.llm_agent import DESIGN_SCHEMA
from agent.semantic_checks import ground_draft


def request(tail):
    return {"task_id": "unrelated-id", "request_text":
            "Make a rectangular case for Raspberry Pi 4 with " + tail, "language": "en"}


def port(name, side="unspecified", count=None):
    return {"port_type": name, "requested_side": side, "count": count}


class GroundingTests(unittest.TestCase):
    def checked(self, tail, **model_overrides):
        incoming = request(tail)
        draft = extract_design(request("no lid; 2 mm wall thickness."))
        draft.update(model_overrides)
        design, normalized, changes, issues = ground_draft(incoming, draft)
        load_validator(DESIGN_SCHEMA).validate(design)
        return design, check_capability(design, request=normalized), changes, issues

    def test_negated_ports_cannot_become_positive(self):
        for phrase in ("no USB or Ethernet openings", "USB and Ethernet must not be exposed",
                       "do not include USB or Ethernet cutouts", "without cutouts for USB and Ethernet"):
            with self.subTest(phrase=phrase):
                design, gate, changes, issues = self.checked(
                    f"no lid; {phrase}; 2 mm wall thickness.",
                    port_requirements=[port("usb"), port("ethernet")],
                )
                self.assertEqual(design["port_requirements"], [])
                self.assertTrue(design["needs_clarification"])
                self.assertFalse(gate["allow_geometry"])
                self.assertTrue(any(change["field"] == "port_requirements" for change in changes))
                self.assertTrue(issues)

    def test_explicit_positive_port_after_separate_negative_clause(self):
        design, gate, _, _ = self.checked(
            "no lid; omit USB openings; exactly two HDMI openings on the left.",
        )
        self.assertEqual(design["port_requirements"], [port("hdmi", "left", 2)])
        self.assertFalse(gate["allow_geometry"])

    def test_explicit_count_and_direction_even_if_model_omits_them(self):
        design, gate, _, _ = self.checked(
            "no lid; two front-facing USB openings and one Ethernet opening on the front.",
        )
        self.assertEqual(design["port_requirements"], [
            port("ethernet", "front", 1), port("usb", "front", 2),
        ])
        self.assertEqual(gate["status"], "unsupported")

    def test_unqualified_plural_has_no_count(self):
        design, _, _, _ = self.checked(
            "no lid; USB and Ethernet openings on the back.",
            port_requirements=[port("usb", "front", 1)],
        )
        self.assertEqual(design["port_requirements"], [port("ethernet", "back"), port("usb", "back")])

    def test_shared_count_or_alternative_sides_need_clarification(self):
        for phrase in ("two USB and Ethernet openings", "USB openings on the front or back"):
            with self.subTest(phrase=phrase):
                design, gate, _, _ = self.checked(f"no lid; {phrase}.")
                self.assertEqual(design["port_requirements"], [])
                self.assertEqual(gate["status"], "clarification_required")

    def test_metric_and_inch_conversion_grounded_in_original_text(self):
        for phrase, expected in (
            ("0.3 cm wall thickness", 3), ("wall thickness of 0.25 centimetres", 2.5),
            ("0.1 inches wall thickness", 2.54), ("wall thickness of 2mm", 2),
        ):
            with self.subTest(phrase=phrase):
                design, gate, _, _ = self.checked(f"no lid; {phrase}.", wall_thickness_mm=0.3)
                self.assertEqual(design["wall_thickness_mm"], expected)
                self.assertEqual(gate["status"], "allow")

    def test_conflicting_wall_values_are_not_selected(self):
        design, gate, _, _ = self.checked("no lid; 0.3 cm wall thickness; wall thickness of 4 mm.")
        self.assertIsNone(design["wall_thickness_mm"])
        self.assertEqual(gate["status"], "clarification_required")
        self.assertTrue(design["clarification_questions"])

    def test_wall_range_is_ambiguous(self):
        design, gate, _, _ = self.checked("no lid; 0.3 cm or 4 mm wall thickness.")
        self.assertIsNone(design["wall_thickness_mm"])
        self.assertEqual(gate["status"], "clarification_required")

    def test_missing_values_are_not_invented(self):
        design, _, _, _ = self.checked(
            "no lid.", wall_thickness_mm=3, mounting={"wall_mount_hole_count": 2},
            port_requirements=[port("usb")],
        )
        self.assertIsNone(design["wall_thickness_mm"])
        self.assertIsNone(design["mounting"]["wall_mount_hole_count"])
        self.assertEqual(design["port_requirements"], [])

    def test_unknown_board_hallucination_blocked(self):
        incoming = {"task_id": "T", "language": "en", "request_text":
                    "Make a rectangular case for an unidentified board with no lid."}
        hallucination = extract_design(request("no lid."))
        hallucination["task_id"] = "T"
        design, normalized, _, _ = ground_draft(incoming, hallucination)
        self.assertIsNone(design["board_id"])
        self.assertTrue(design["needs_clarification"])
        self.assertFalse(check_capability(design, request=normalized)["allow_geometry"])

    def test_requirement_outside_spec_cannot_become_generated(self):
        _, gate, _, _ = self.checked("no lid; 2 mm wall thickness; an integrated hinge.")
        self.assertEqual(gate["status"], "review_required")


if __name__ == "__main__":
    unittest.main()
