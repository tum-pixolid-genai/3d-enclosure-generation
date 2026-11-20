"""Approval regressions with synthetic responses and a CAD-call sentinel."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from image_agent.cad_smoke import run as run_cad
from image_agent.demo_server import Approval


ROOT = Path(__file__).resolve().parents[1]


def result():
    return {
        "design_spec": {
            "schema_version": "0.1", "task_id": "QA-REVIEW",
            "board_id": "raspberry_pi_4", "case_shape": "rectangular",
            "lid": {"present": False, "style": "unspecified"}, "port_requirements": [],
            "mounting": {"wall_mount_hole_count": None}, "wall_thickness_mm": 2,
            "needs_clarification": False, "clarification_questions": [], "assumptions": [],
        },
        "instructions": "Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.",
        "evidence": {"unrepresented_features": []}, "unverified_features": [],
        "visual_audit": {"other_features": []},
        "capability": {
            "status": "review_required", "allow_geometry": False, "unsupported": [],
            "questions": [], "review_reasons": ["Visual requirements need independent review before CAD."],
        },
    }


class ApprovalSafetyTests(unittest.TestCase):
    def assert_rejected_before_geometry(self, data):
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            source = directory / "result.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            approval = directory / "approval.json"
            approval.write_text(json.dumps({
                "approved": True, "reviewer": "QA synthetic reviewer",
                "source_result_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }), encoding="utf-8")
            fake = ModuleType("backend")

            def sentinel(_):
                raise RuntimeError("QA_SENTINEL_GEOMETRY_CALLED")

            fake.geometry_service = SimpleNamespace(run_geometry=sentinel)
            with patch.dict(sys.modules, {"backend": fake}):
                with self.assertRaises(SystemExit):
                    run_cad(source, directory / "cad", approval)
            self.assertFalse((directory / "cad").exists())

    def test_human_approval_cannot_override_other_review_reasons(self):
        data = result()
        data["capability"]["review_reasons"].append(
            "The original request is outside the verified simple patterns.")
        self.assert_rejected_before_geometry(data)

    def test_human_approval_cannot_override_reported_audit_features(self):
        data = result()
        data["visual_audit"]["other_features"] = ["unverified hinge"]
        self.assert_rejected_before_geometry(data)

    def test_non_boolean_approval_is_rejected(self):
        for supplied in (1, "true", "yes"):
            with self.subTest(supplied=supplied), self.assertRaises(ValidationError):
                Approval.model_validate({
                    "approved": supplied, "reviewer": "QA reviewer",
                    "source_result_sha256": "a" * 64,
                })

    def test_input_change_clears_obsolete_completion_status(self):
        script = r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes={};
for(const id of ['image','preview','instructions','extract','status','results','spec','gate','raw',
                 'reviewer','reviewed','approve','downloads']) {
 nodes[id]={value:'',checked:false,disabled:false,hidden:false,textContent:'',
            replaceChildren(){},appendChild(){}};
}
const context={document:{getElementById:id=>nodes[id]}};
vm.createContext(context);vm.runInContext(source,context);
nodes.status.textContent='Extraction completed for a previous input.';
nodes.instructions.oninput();
assert.notEqual(nodes.status.textContent,'Extraction completed for a previous input.');
assert.equal(nodes.results.hidden,true);
assert.equal(nodes.approve.disabled,true);
"""
        done = subprocess.run(["node", "-e", script, str(ROOT / "image_agent/demo.html")],
                              text=True, capture_output=True, timeout=15)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_changed_input_cannot_display_older_approval_downloads(self):
        script = r"""
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const source=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes={};
for(const id of ['image','preview','instructions','extract','status','results','spec','gate','raw',
                 'reviewer','reviewed','approve','downloads']) {
 nodes[id]={value:'',checked:false,disabled:false,hidden:false,textContent:'',children:[],
            replaceChildren(){this.children=[]},appendChild(v){this.children.push(v)}};
}
nodes.image.files=[{name:'qa.png'}];
nodes.instructions.value='QA request';
let finish;
const context={document:{getElementById:id=>nodes[id],createElement:()=>({})},
 URL:{createObjectURL:()=>''},
 FileReader:class{readAsDataURL(){this.result='data:image/png;base64,AAAA';this.onload();}},
 fetch:async(url)=> {
   if(url==='/image')return {ok:true,json:async()=>({
    task_id:'qa_task',source_result_sha256:'a'.repeat(64),
    result:{design_spec:{},capability:{status:'review_required'}}})};
   return await new Promise(resolve=>{finish=()=>resolve({ok:true,json:async()=>({
    step_url:'/image/qa_task/step',stl_url:'/image/qa_task/stl'})})});
 }};
vm.createContext(context);vm.runInContext(source,context);
(async()=>{
 await nodes.extract.onclick();
 nodes.reviewed.checked=true;nodes.reviewer.value='QA reviewer';
 const pending=nodes.approve.onclick();
 await Promise.resolve();
 nodes.instructions.value='A different request';
 nodes.instructions.oninput();
 finish();await pending;
 assert.equal(nodes.downloads.children.length,0,'Old approval populated a different input view');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
        done = subprocess.run(["node", "-e", script, str(ROOT / "image_agent/demo.html")],
                              text=True, capture_output=True, timeout=15)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
