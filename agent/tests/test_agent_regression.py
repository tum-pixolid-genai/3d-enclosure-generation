import json
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class AgentRegressionTests(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory(prefix="pixolid-agent-test-")
        self.addCleanup(scratch.cleanup)
        self.project = Path(scratch.name)
        # Exercise the real entry points without giving them access to the original outputs.
        for name in ("agent.py", "validate_output.py"):
            shutil.copy2(ROOT / name, self.project / name)
        for name in ("examples", "schemas"):
            shutil.copytree(ROOT / name, self.project / name)

    def run_python(self, *args):
        return subprocess.run(
            [sys.executable, "-B", *map(str, args)],
            cwd=self.project,
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=20,
        )

    def request(self, text, task_id="TEST", language="en"):
        path = self.project / "request.json"
        path.write_text(
            json.dumps({"task_id": task_id, "request_text": text, "language": language}),
            encoding="utf-8",
        )
        return path

    def generate(self, request_path=None, task_id="TEST"):
        output_dir = self.project / "run"
        args = [] if request_path is None else [request_path]
        result = self.run_python("agent.py", *args, "--output-dir", output_dir)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        design = json.loads((output_dir / f"{task_id}_design_spec.json").read_text(encoding="utf-8"))
        schema = json.loads((self.project / "schemas/design_spec.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(design)
        return design

    def test_default_request_with_fresh_output(self):
        design = self.generate(task_id="T001")
        self.assertEqual(design["board_id"], "raspberry_pi_4")
        self.assertEqual(design["case_shape"], "rectangular")
        self.assertEqual(design["lid"], {"present": True, "style": "removable"})
        self.assertEqual(design["port_requirements"], [
            {"port_type": "usb", "requested_side": "unspecified", "count": None},
        ])
        self.assertFalse(design["needs_clarification"])

    def test_existing_default_output_is_preserved(self):
        output_dir = self.project / "outputs"
        output_dir.mkdir()
        target = output_dir / "T001_design_spec.json"
        historical = (FIXTURES / target.name).read_bytes()
        target.write_bytes(historical)
        result = self.run_python("agent.py")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(target.read_bytes(), historical)

    def test_t004_extracts_explicit_requirements(self):
        design = self.generate("examples/complex_request_T004.json", task_id="T004")
        self.assertEqual(design["board_id"], "raspberry_pi_4")
        self.assertEqual(design["case_shape"], "rectangular")
        self.assertEqual(design["lid"], {"present": True, "style": "removable"})
        self.assertEqual(design["port_requirements"], [
            {"port_type": "usb", "requested_side": "front", "count": None},
            {"port_type": "ethernet", "requested_side": "front", "count": None},
        ])
        self.assertEqual(design["mounting"]["wall_mount_hole_count"], 2)
        self.assertFalse(design["needs_clarification"])
        self.assertEqual(design["clarification_questions"], [])

    def test_port_directions_apply_to_each_group(self):
        design = self.generate(self.request(
            "Make a case for Raspberry Pi 4 with Ethernet and USB ports on the left, "
            "HDMI at the back, and exactly three external wall-mount holes.",
        ))
        self.assertEqual(design["task_id"], "TEST")
        self.assertEqual(
            [(port["port_type"], port["requested_side"]) for port in design["port_requirements"]],
            [("ethernet", "left"), ("usb", "left"), ("hdmi", "back")],
        )
        self.assertEqual(design["mounting"]["wall_mount_hole_count"], 3)
        self.assertFalse(design["needs_clarification"])

    def test_no_lid_is_explicitly_false(self):
        design = self.generate(self.request("Make a case for Raspberry Pi 4 without a lid."))
        self.assertEqual(design["lid"], {"present": False, "style": "unspecified"})
        self.assertFalse(design["needs_clarification"])

    def test_negated_ports_are_not_positive(self):
        design = self.generate(self.request(
            "Make a case for Raspberry Pi 4 with no lid and no USB and Ethernet openings.",
        ))
        self.assertIs(design["lid"]["present"], False)
        self.assertEqual(design["port_requirements"], [])
        self.assertTrue(design["needs_clarification"])
        self.assertIn("exclude", " ".join(design["clarification_questions"]).lower())

    def test_explicit_wall_thickness(self):
        design = self.generate(self.request(
            "Make a case for Raspberry Pi 4 with 2 mm wall thickness and a removable lid.",
        ))
        self.assertEqual(design["wall_thickness_mm"], 2)
        self.assertFalse(design["needs_clarification"])

    def test_ambiguous_negation_scope_does_not_add_ports(self):
        design = self.generate(self.request(
            "Make a case for Raspberry Pi 4 without a lid and USB openings."
        ))
        self.assertEqual(design["port_requirements"], [])
        self.assertTrue(design["needs_clarification"])
        self.assertIn("usb", " ".join(design["clarification_questions"]).lower())

    def test_unhandled_and_contradictory_requirements_need_clarification(self):
        prefix = "Make a case for Raspberry Pi 4 with "
        cases = (
            ("no lid and a removable lid", "lid", "lid"),
            ("2 mm wall thickness and 3 mm wall thickness", "thickness", "wall_thickness_mm"),
            ("wall thickness of 2", "thickness", "wall_thickness_mm"),
            ("-2 mm wall thickness", "thickness", "wall_thickness_mm"),
            ("2 mm wall thickness and 3 cm wall thickness", "thickness", "wall_thickness_mm"),
            ("USB openings on the left and USB openings on the right", "USB", "port_requirements"),
            ("two wall-mount holes and three wall-mount holes", "wall-mount", "mounting"),
            ("a removable lid and ventilation slots", "ventilation", None),
        )
        for index, (requirements, question, unresolved) in enumerate(cases):
            with self.subTest(requirements=requirements):
                task = f"AMB{index}"
                design = self.generate(self.request(prefix + requirements, task), task)
                self.assertTrue(design["needs_clarification"])
                self.assertIn(question.lower(), " ".join(design["clarification_questions"]).lower())
                if unresolved == "lid":
                    self.assertIsNone(design["lid"]["present"])
                elif unresolved == "port_requirements":
                    self.assertEqual(design["port_requirements"], [])
                elif unresolved == "mounting":
                    self.assertIsNone(design["mounting"]["wall_mount_hole_count"])
                elif unresolved:
                    self.assertIsNone(design[unresolved])
                else:
                    self.assertEqual(design["lid"], {"present": True, "style": "removable"})

    def test_missing_board_and_unsupported_language(self):
        unknown = self.generate(self.request("Please make a protective case for my electronics board.", "BOARD"), "BOARD")
        self.assertIsNone(unknown["board_id"])
        self.assertTrue(unknown["needs_clarification"])
        self.assertIn("board", " ".join(unknown["clarification_questions"]).lower())
        other = self.generate(self.request("Make a case for Raspberry Pi 4.", "LANG", "de"), "LANG")
        self.assertIsNone(other["board_id"])
        self.assertTrue(other["needs_clarification"])
        self.assertIn("English", " ".join(other["clarification_questions"]))

    def test_import_is_silent_and_does_not_write(self):
        result = self.run_python("-c", "import agent; import validate_output")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout + result.stderr, "")
        self.assertFalse((self.project / "outputs").exists())

    def test_agent_and_validator_control_read_errors(self):
        fixtures = {
            "missing.json": None,
            "bad.json": b'{"task_id":',
            "encoding.json": b'\xff',
            "not-json-number.json": b'{"value": Infinity}',
        }
        for name, data in fixtures.items():
            if data is not None:
                (self.project / name).write_bytes(data)
            for script in ("agent.py", "validate_output.py"):
                with self.subTest(name=name, script=script):
                    result = self.run_python(script, name)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn(name, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.project / "outputs").exists())

    def test_invalid_request_returns_schema_error(self):
        path = self.project / "invalid.json"
        path.write_text('{"task_id": "TEST"}', encoding="utf-8")
        result = self.run_python("agent.py", path)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("request_text", result.stderr)
        self.assertFalse((self.project / "outputs").exists())

    def test_missing_schema_returns_configuration_error(self):
        (self.project / "schemas/design_spec.schema.json").unlink()
        for script in ("agent.py", "validate_output.py"):
            with self.subTest(script=script):
                result = self.run_python(script, "examples/my_first_request.json")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("design_spec.schema.json", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.project / "outputs").exists())

    def test_same_task_can_run_in_two_independent_directories(self):
        first = self.generate("examples/my_first_request.json", "T001")
        result = self.run_python("agent.py", "examples/my_first_request.json", "--output-dir", "other-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        second = json.loads((self.project / "other-run/T001_design_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(first, second)

    def test_concurrent_runs_cannot_both_write_the_same_output(self):
        def execute(_):
            return self.run_python("agent.py", "examples/my_first_request.json", "--output-dir", "parallel")

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(execute, range(2)))
        self.assertEqual(sorted(result.returncode for result in results), [0, 3])
        result = json.loads((self.project / "parallel/T001_design_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(result["task_id"], "T001")

    def test_invalid_output_directory_returns_output_error(self):
        path = self.project / "existing-file"
        path.write_text("keep this", encoding="utf-8")
        result = self.run_python("agent.py", "--output-dir", path)
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("existing-file", result.stderr)
        self.assertEqual(path.read_text(encoding="utf-8"), "keep this")

    def test_historical_prompt_validation(self):
        for version, exit_code, message, error_count in (
            ("0.1", 1, "SCHEMA FAIL", 6),
            ("0.2", 0, "SCHEMA PASS", 0),
        ):
            with self.subTest(version=version):
                source = FIXTURES / f"T004_llm_v{version}.json"
                result = self.run_python("validate_output.py", source)
                self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
                self.assertIn(message, result.stdout)
                self.assertEqual(result.stdout.count("Problem:"), error_count)


if __name__ == "__main__":
    unittest.main()
