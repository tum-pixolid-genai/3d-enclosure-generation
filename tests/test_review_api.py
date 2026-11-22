"""Real loopback HTTP lifecycle tests with explicitly synthetic model/CAD providers."""

import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
import unittest
from unittest.mock import patch

import uvicorn

from image_agent.demo_server import create_app
from image_agent.vision_agent import read_image
from agent.llm_agent import AgentError
from test_approval_safety import result as synthetic_result


ROOT = Path(__file__).resolve().parents[1]


class SyntheticAgent:
    def __init__(self, **kwargs):
        pass

    def extract(self, path, *, task_id, instructions):
        if instructions == "QA_MODEL_FAILURE":
            raise AgentError("ollama_connection_error", "Controlled unavailable model")
        _, meta = read_image(path)
        value = synthetic_result()
        value["design_spec"]["task_id"] = task_id
        value.update(task_id=task_id, image=meta, instructions=instructions)
        return value


def synthetic_export(source, directory, approval):
    # These markers are not CAD exports. Actual STEP/STL are tested separately.
    payload = json.loads(source.read_text(encoding="utf-8"))
    task = payload["task_id"]
    directory.mkdir()
    files = {}
    for extension in ("step", "stl"):
        path = directory / f"{task}.{extension}"
        path.write_bytes(f"QA_SYNTHETIC_{task}_{extension}".encode())
        files[extension] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return {"files": files}


class ReviewHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(prefix="pixolid-review-api-")
        cls.directory = Path(cls.temp.name) / "run"
        cls.model_patch = patch("image_agent.demo_server.VisionAgent", SyntheticAgent)
        cls.model_patch.start()
        cls.cad_patch = patch("image_agent.demo_server.generate_cad", side_effect=synthetic_export)
        cls.exporter = cls.cad_patch.start()
        cls.app = create_app(cls.directory, 11443)
        cls.sock = socket.socket()
        cls.sock.bind(("127.0.0.1", 0))
        cls.port = cls.sock.getsockname()[1]
        cls.server = uvicorn.Server(uvicorn.Config(cls.app, log_level="critical"))
        cls.worker = Thread(target=cls.server.run, kwargs={"sockets": [cls.sock]}, daemon=True)
        cls.worker.start()
        deadline = monotonic() + 8
        while not cls.server.started and cls.worker.is_alive() and monotonic() < deadline:
            sleep(0.02)
        if not cls.server.started:
            raise RuntimeError("QA loopback HTTP listener did not start")

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.worker.join(8)
        cls.sock.close()
        cls.cad_patch.stop()
        cls.model_patch.stop()
        cls.temp.cleanup()

    def call(self, route, payload=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            body = json.dumps(payload).encode() if payload is not None else None
            conn.request("POST" if body else "GET", route, body, {"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def upload(self, instructions="QA supported image"):
        import base64
        status, raw = self.call("/image", {
            "filename": "open.png",
            "image_base64": base64.b64encode((ROOT / "examples/open.png").read_bytes()).decode(),
            "instructions": instructions,
        })
        return status, json.loads(raw)

    def approve(self, value, **overrides):
        return self.call(f"/image/{value['task_id']}/approve", {
            "approved": True, "reviewer": "QA synthetic reviewer",
            "source_result_sha256": value["source_result_sha256"], **overrides,
        })

    def assert_no_downloads(self, task):
        for extension in ("step", "stl"):
            self.assertEqual(self.call(f"/image/{task}/{extension}")[0], 404)

    def test_new_extraction_has_review_state_without_artifacts(self):
        status, data = self.upload()
        self.assertEqual(status, 200)
        self.assertEqual(data["result"]["capability"]["status"], "review_required")
        self.assert_no_downloads(data["task_id"])
        self.assertFalse((self.directory / data["task_id"] / "cad").exists())

    def test_missing_false_or_non_boolean_approval_blocks_generation(self):
        _, data = self.upload()
        route = f"/image/{data['task_id']}/approve"
        self.assertEqual(self.call(route, {})[0], 422)
        self.assertEqual(self.approve(data, approved=False)[0], 409)
        self.assertEqual(self.approve(data, approved="true")[0], 422)
        self.assert_no_downloads(data["task_id"])

    def test_approval_for_other_image_or_text_cannot_be_reused(self):
        _, old = self.upload("QA original instructions")
        _, new = self.upload("QA changed instructions")
        self.assertNotEqual(old["task_id"], new["task_id"])
        self.assertEqual(self.approve(new, source_result_sha256=old["source_result_sha256"])[0], 409)
        self.assert_no_downloads(new["task_id"])

    def test_modified_result_invalidates_approval(self):
        _, data = self.upload()
        path = self.directory / data["task_id"] / "result.json"
        payload = json.loads(path.read_text())
        payload["design_spec"]["wall_thickness_mm"] = 3
        path.write_text(json.dumps(payload))
        self.assertEqual(self.approve(data)[0], 409)
        self.assert_no_downloads(data["task_id"])

    def test_modified_image_invalidates_approval(self):
        _, data = self.upload()
        path = self.directory / data["task_id"] / "input.png"
        path.write_bytes(path.read_bytes() + b"QA_CHANGED")
        self.assertEqual(self.approve(data)[0], 409)
        self.assert_no_downloads(data["task_id"])

    def test_approved_artifacts_are_task_bound_and_tamper_detected(self):
        _, data = self.upload()
        code, raw = self.approve(data)
        self.assertEqual(code, 200, raw)
        task = data["task_id"]
        self.assertIn(task, json.loads(raw)["step_url"])
        status, body = self.call(f"/image/{task}/step")
        self.assertEqual(status, 200)
        self.assertIn(task.encode(), body)
        (self.directory / task / "cad" / f"{task}.step").write_bytes(b"QA_STALE_ARTIFACT")
        self.assertEqual(self.call(f"/image/{task}/step")[0], 404)
        self.assertEqual(self.approve(data)[0], 409)

    def test_failed_generation_does_not_publish_seeded_old_artifacts(self):
        _, data = self.upload()
        with patch("image_agent.demo_server.generate_cad", side_effect=SystemExit("QA blocked")):
            self.assertEqual(self.approve(data)[0], 422)
        cad = self.directory / data["task_id"] / "cad"
        cad.mkdir()
        for ext in ("step", "stl"):
            (cad / f"{data['task_id']}.{ext}").write_bytes(b"QA_STALE")
        self.assert_no_downloads(data["task_id"])

    def test_invalid_image_and_model_failure_are_safe(self):
        status, _ = self.call("/image", {"filename": "bad.png", "image_base64": "dGVzdA=="})
        self.assertEqual(status, 422)
        status, failure = self.upload("QA_MODEL_FAILURE")
        self.assertEqual(status, 503)
        self.assert_no_downloads(failure["task_id"])


if __name__ == "__main__":
    unittest.main()
