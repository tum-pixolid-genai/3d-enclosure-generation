"""Offline contract, parser, and gate tests. This suite does not call Ollama."""

import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from agent.agent import extract_design
from agent.capability_check import check_capability
from agent.evaluation.run_pilot import score
from agent.llm_agent import AgentError, LLMAgent, MODEL, PORT, PROGRAM_FIELDS, TIMEOUT, ollama_request


SMOKE = json.loads((Path(__file__).resolve().parents[1] / "evaluation/pilot_cases.json").read_text(
    encoding="utf-8"
))["cases"]


def model_fields(case):
    reference = case["reference"]
    return {
        **reference["requirements"], "needs_clarification": reference["needs_clarification"],
        "clarification_questions": [f"Which {topic}?" for topic in reference["clarification_topics"]],
    }


def response(content, *, reason="stop"):
    return {
        "done": True, "done_reason": reason, "message": {"content": content},
        "prompt_eval_count": 17, "eval_count": 5,
    }


class LLMExtractionTests(unittest.TestCase):
    def setUp(self):
        self.request = SMOKE[0]["request"]
        self.fields = model_fields(SMOKE[0])
        self.chat = Mock(return_value=response(json.dumps(self.fields)))
        self.agent = LLMAgent(chat=self.chat)

    def extract_error(self, code):
        with self.assertRaises(AgentError) as caught:
            self.agent.extract(self.request)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_contract_generated_with_structured_output_and_backend_id(self):
        result = self.agent.extract(self.request)
        self.assertEqual(result.design_spec["task_id"], self.request["task_id"])
        self.assertEqual(result.design_spec["schema_version"], "0.1")
        self.assertEqual(result.usage["eval_count"], 5)
        self.assertEqual(result.design_spec["lid"]["present"], False)
        self.assertEqual(result.design_spec["port_requirements"], [])
        payload = self.chat.call_args.args[0]
        self.assertEqual(payload["model"], MODEL)
        self.assertFalse(payload["stream"])
        self.assertFalse(payload["format"]["additionalProperties"])
        self.assertTrue(set(PROGRAM_FIELDS).isdisjoint(payload["format"]["required"]))
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertEqual(json.loads(payload["messages"][1]["content"])["request_text"],
                         self.request["request_text"])

    def test_invalid_request_does_not_call_model(self):
        self.request = {**self.request, "task_id": "../untrusted"}
        self.extract_error("invalid_request")
        self.chat.assert_not_called()

    def test_model_cannot_supply_program_fields(self):
        for field in PROGRAM_FIELDS:
            with self.subTest(field=field):
                self.chat.return_value = response(json.dumps({**self.fields, field: "invented"}))
                self.extract_error("invalid_design")

    def test_unexpected_engineering_field_rejected(self):
        self.chat.return_value = response(json.dumps({**self.fields, "board_width_mm": 85}))
        self.extract_error("invalid_design")

    def test_wrong_port_keys_fail_full_schema(self):
        self.chat.return_value = response(json.dumps({
            **self.fields, "port_requirements": [{"type": "usb", "side": "front", "count": None}],
        }))
        self.extract_error("invalid_design")

    def test_invalid_model_json_is_retained_and_rejected(self):
        for bad_json in ("{", 'null trailing', '{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'):
            with self.subTest(bad_json=bad_json):
                self.chat.return_value = response(bad_json)
                error = self.extract_error("invalid_model_json")
                self.assertEqual(error.raw_reply, bad_json)
                self.assertEqual(error.usage["eval_count"], 5)

    def test_truncated_output_and_provider_error_are_not_successes(self):
        self.chat.return_value = response(json.dumps(self.fields), reason="length")
        self.extract_error("incomplete_generation")
        self.chat.side_effect = AgentError("ollama_timeout", "test timeout")
        self.extract_error("ollama_timeout")
        self.assertEqual(self.chat.call_count, 2)

    def test_api_opened_only_on_loopback_and_timeout_mapped(self):
        with patch("agent.llm_agent.http.client.HTTPConnection") as constructor:
            constructor.return_value.getresponse.side_effect = TimeoutError
            with self.assertRaisesRegex(AgentError, "socket timeout"):
                ollama_request("/api/chat", {"example": True})
            constructor.assert_called_once_with("127.0.0.1", PORT, timeout=TIMEOUT)
            constructor.return_value.close.assert_called_once()

    def test_model_clarification_survives_validation(self):
        self.chat.return_value = response(json.dumps(model_fields(SMOKE[1])))
        design = self.agent.extract(SMOKE[1]["request"]).design_spec
        self.assertIsNone(design["board_id"])
        self.assertTrue(design["needs_clarification"])
        self.assertEqual(design["clarification_questions"], ["Which board?"])

    def test_valid_structure_does_not_hide_omitted_feature(self):
        case = SMOKE[3]
        fields = model_fields(case)
        ports = [port for port in fields["port_requirements"] if port["port_type"] != "ethernet"]
        self.chat.return_value = response(json.dumps({**fields, "port_requirements": ports}))
        design = self.agent.extract(case["request"]).design_spec
        outcome = score(case["reference"], design)
        self.assertFalse(outcome["semantic_exact"])
        self.assertIn("opening.ethernet.side", [diff["field"] for diff in outcome["differences"]])
        gate = check_capability(design, request=case["request"])
        self.assertFalse(gate["allow_geometry"])
        self.assertTrue(any(issue.get("port_type") == "ethernet" and
                            issue.get("source") == "request_cross_check" for issue in gate["unsupported"]))


class CapabilityTests(unittest.TestCase):
    def test_simple_supported_request_allowed_with_no_llm(self):
        request = SMOKE[0]["request"]
        gate = check_capability(extract_design(request), request=request)
        self.assertEqual(gate["status"], "allow")
        self.assertTrue(gate["allow_geometry"])

    def test_all_t004_features_rejected_from_spec_without_model_or_task_id(self):
        draft = extract_design({**SMOKE[3]["request"], "task_id": "ANOTHER-CASE"})
        gate = check_capability(draft)
        self.assertFalse(gate["allow_geometry"])
        self.assertEqual(gate["status"], "unsupported")
        self.assertEqual(gate["unsupported"], [
            {"code": "lid", "style": "removable"},
            {"code": "port_opening", "port_type": "usb", "requested_side": "front", "count": None},
            {"code": "port_opening", "port_type": "ethernet", "requested_side": "front", "count": None},
            {"code": "external_wall_mount_holes", "count": 2},
        ])

    def test_concealed_unsupported_features_do_not_pass_gate(self):
        draft = extract_design(SMOKE[0]["request"])
        gate = check_capability(draft, request=SMOKE[3]["request"])
        self.assertFalse(gate["allow_geometry"])
        self.assertEqual(len(gate["unsupported"]), 4)

    def test_unknown_board_needs_user_clarification(self):
        request = SMOKE[1]["request"]
        gate = check_capability(extract_design(request), request=request)
        self.assertEqual(gate["status"], "clarification_required")
        self.assertTrue(gate["questions"])
        self.assertEqual(gate["unsupported"], [])

    def test_wall_thickness_threshold_remains_a_geometry_check(self):
        request = SMOKE[2]["request"]
        design = extract_design(request)
        self.assertEqual(design["wall_thickness_mm"], 0.5)
        self.assertTrue(check_capability(design, request=request)["allow_geometry"])

    def test_ambiguous_or_unverified_sources_do_not_pass_gate(self):
        draft = extract_design(SMOKE[0]["request"])
        request = {**SMOKE[0]["request"], "request_text": "Please make it work."}
        for source in (request, None):
            with self.subTest(source=source):
                self.assertEqual(check_capability(draft, request=source)["status"], "review_required")

    def test_disagreement_with_explicit_wall_thickness_needs_review(self):
        request = SMOKE[0]["request"]
        draft = {**extract_design(request), "wall_thickness_mm": 3.0}
        self.assertEqual(check_capability(draft, request=request)["status"], "review_required")


if __name__ == "__main__":
    unittest.main()
