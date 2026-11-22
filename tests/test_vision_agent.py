"""Offline boundary tests, independent of the actual model experiments."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from PIL import Image

from image_agent.vision_agent import VisionAgent, read_image
from agent.llm_agent import AgentError


def envelope():
    return {
        "design": {
            "board_id": None, "case_shape": "rectangular", "lid": {"present": False, "style": "unspecified"},
            "port_requirements": [], "mounting": {"wall_mount_hole_count": None},
            "wall_thickness_mm": None, "needs_clarification": False, "clarification_questions": [],
        },
        "visual_evidence": {
            "case_shape": "Four rectangular enclosure walls", "lid": "Visible open top",
            "port_requirements": "", "mounting": "",
        },
        "image_questions": [], "unrepresented_features": [],
    }


class VisionTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "test.png"
        Image.new("RGB", (64, 64), "white").save(self.path)
        self.fields = envelope()
        self.chat = Mock()
        audit = {
            "scene": "enclosure_3d", "scene_evidence": "Multiple depth edges and an interior floor.",
            "lid_state": "open", "lid_evidence": "Visible cavity.",
            "cover_panel_visible": False, "interior_floor_visible": True,
            "opening_certainty": "none", "openings": [], "other_features": [], "uncertainties": [],
        }
        self.audit_chat = Mock(return_value={"done": True, "done_reason": "stop",
                                            "message": {"content": json.dumps(audit)}})
        self.agent = VisionAgent(chat=self.chat, audit_chat=self.audit_chat)

    def infer(self, instructions="", task_id="IMAGE-TEST"):
        self.chat.return_value = {
            "done": True, "done_reason": "stop",
            "message": {"content": json.dumps(self.fields)}, "eval_count": 42,
        }
        return self.agent.extract(self.path, task_id=task_id, instructions=instructions)

    def test_unknown_board_asks_question_and_preserves_shape(self):
        result = self.infer()
        self.assertEqual(result["design_spec"]["case_shape"], "rectangular")
        self.assertIsNone(result["design_spec"]["board_id"])
        self.assertTrue(result["design_spec"]["needs_clarification"])
        self.assertFalse(result["capability"]["allow_geometry"])
        self.assertEqual(result["usage"]["eval_count"], 42)

    def test_pixels_are_actually_attached_to_structured_inference(self):
        self.infer()
        payload = self.chat.call_args.args[0]
        self.assertTrue(payload["messages"][1]["images"][0].startswith("iVBOR"))
        self.assertEqual(payload["format"]["type"], "object")
        self.assertFalse(payload["stream"])

    def test_text_supplies_board_and_thickness_without_authorizing_cad(self):
        result = self.infer("Make a rectangular case for Raspberry Pi 4 with no lid; 0.3 cm wall thickness.")
        self.assertEqual(result["design_spec"]["board_id"], "raspberry_pi_4")
        self.assertEqual(result["design_spec"]["wall_thickness_mm"], 3)
        self.assertFalse(result["capability"]["allow_geometry"])
        self.assertEqual(result["capability"]["status"], "review_required")

    def test_hallucinated_board_and_visual_dimensions_are_removed(self):
        self.fields["design"].update(board_id="raspberry_pi_4", wall_thickness_mm=2)
        result = self.infer()
        self.assertIsNone(result["design_spec"]["board_id"])
        self.assertIsNone(result["design_spec"]["wall_thickness_mm"])
        self.assertEqual(result["raw_design_spec"]["wall_thickness_mm"], 2)

    def test_visible_lid_is_kept_and_reported_unsupported(self):
        self.fields["design"]["lid"] = {"present": True, "style": "unspecified"}
        self.fields["visual_evidence"]["lid"] = "Separate top cover"
        audit = json.loads(self.audit_chat.return_value["message"]["content"])
        audit.update(lid_state="cover", lid_evidence="Separated visible cover.", cover_panel_visible=True)
        self.audit_chat.return_value["message"]["content"] = json.dumps(audit)
        result = self.infer()
        self.assertTrue(result["design_spec"]["lid"]["present"])
        self.assertTrue(any(item["code"] == "lid" for item in result["capability"]["unsupported"]))

    def test_unlabelled_orientation_is_not_a_physical_axis(self):
        self.fields["design"]["port_requirements"] = [{"port_type": "unknown", "requested_side": "front", "count": 2}]
        self.fields["visual_evidence"]["port_requirements"] = "Two rectangular cutouts"
        result = self.infer()
        self.assertEqual(result["design_spec"]["port_requirements"][0]["requested_side"], "unspecified")
        self.assertTrue(result["design_spec"]["needs_clarification"])
        self.assertEqual(len(result["capability"]["unsupported"]), 1)

    def test_conflicting_image_and_text_requires_clarification(self):
        self.fields["design"]["lid"] = {"present": True, "style": "unspecified"}
        result = self.infer("Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.")
        self.assertTrue(result["design_spec"]["needs_clarification"])
        self.assertTrue(any("disagree" in question for question in result["design_spec"]["clarification_questions"]))

    def test_named_negative_port_is_not_kept_as_positive(self):
        self.fields["design"]["port_requirements"] = [
            {"port_type": "usb", "requested_side": "front", "count": 1},
        ]
        self.fields["visual_evidence"]["port_requirements"] = "A rectangular cutout"
        result = self.infer("Make a rectangular case for Raspberry Pi 4 with no lid; no USB openings.")
        self.assertEqual(result["design_spec"]["port_requirements"], [])
        self.assertTrue(result["design_spec"]["needs_clarification"])

    def test_unrepresented_feature_is_separate_from_contract(self):
        self.fields["unrepresented_features"] = ["hinge"]
        result = self.infer()
        self.assertNotIn("unrepresented_features", result["design_spec"])
        self.assertEqual(result["capability"]["unrepresented_features"], ["hinge"])

    def test_wrong_keys_rejected_and_original_reply_preserved(self):
        self.fields["design"]["port_requirements"] = [{"type": "usb", "side": "front"}]
        with self.assertRaises(AgentError) as caught:
            self.infer()
        self.assertEqual(caught.exception.code, "invalid_model_output")
        self.assertIn('"type"', caught.exception.raw_reply)

    def test_task_id_is_controlled_by_caller(self):
        self.fields["design"]["task_id"] = "HACKED"
        with self.assertRaises(AgentError):
            self.infer()
        with self.assertRaises(AgentError):
            self.infer(task_id="../bad")

    def test_missing_or_fake_image_rejected_before_model_call(self):
        self.path.write_text("not an image", encoding="utf-8")
        with self.assertRaises(AgentError):
            read_image(self.path)
        self.chat.assert_not_called()

    def test_jpeg_accepted(self):
        jpeg = self.path.with_suffix(".jpg")
        Image.new("RGB", (64, 64)).save(jpeg)
        _, metadata = read_image(jpeg)
        self.assertEqual(metadata["format"], "JPEG")

    def test_oversized_image_rejected(self):
        Image.new("RGB", (2100, 16)).save(self.path)
        with self.assertRaises(AgentError):
            read_image(self.path)

    def test_service_error_propagates_without_mock_fallback(self):
        self.chat.side_effect = AgentError("ollama_connection_error", "Test unavailable")
        with self.assertRaisesRegex(AgentError, "Test unavailable"):
            self.infer()
        self.assertEqual(self.chat.call_count, 1)


if __name__ == "__main__":
    unittest.main()
