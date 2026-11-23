#!/usr/bin/env python3
"""Run the benchmark through Qianshun's real LLM agent (PR #6) and record,
per task, whether the design spec is right AND whether the agent "claimed done".

Needs: the repo with PR #6 checked out, `pip install jsonschema`, and a local
Ollama server with the Qwen model (port 11439) -- unless you use --stub.

  python stats/run_llm_stage.py --tasks benchmark/tasks.json \
      --repo <path to repo root that has agent/ with llm_agent.py> \
      --boards raspberry_pi_4 --out stats/llm_stage_results.csv

  --stub  replaces Qwen by the rule-based mock (only to test this script
          without Ollama; the numbers are then NOT LLM results).

Definitions (used for research question 2, "how often does AI say done when
it failed"):
  claims_done  = the agent did not ask a question and did not crash
  false_done   = claims_done AND the spec differs from the expected answer
  gate_status  = Qianshun's capability gate (allow / unsupported / ...)
Note: this is the design-spec step only; no CAD, no print.
"""
import argparse
import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze import fmt_rate  # noqa: E402
from run_spec_stage import compare  # noqa: E402


def load(repo, stub):
    sys.path.insert(0, repo)
    from agent.hardened_agent import HardenedAgent
    from agent.llm_agent import AgentError, Extraction, LLMAgent
    if stub:
        from agent.agent import extract_design

        class Stub(LLMAgent):
            def extract(self, request):
                self.request_validator.validate(request)
                return Extraction(extract_design(request), "", {})
        return HardenedAgent(Stub()), AgentError
    return HardenedAgent(LLMAgent()), AgentError


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--boards", default="raspberry_pi_4",
                    help="comma list; the geometry module only has Pi 4 so far")
    ap.add_argument("--out", default="llm_stage_results.csv")
    ap.add_argument("--stub", action="store_true")
    a = ap.parse_args()

    boards = set(a.boards.split(","))
    tasks = [t for t in json.load(open(a.tasks, encoding="utf-8"))["tasks"]
             if t["board_id"] in boards]
    agent, AgentError = load(os.path.abspath(a.repo), a.stub)

    rows = []
    for i, t in enumerate(tasks, 1):
        row = {"task_id": t["task_id"], "board_id": t["board_id"],
               "category": t["category"],
               "expects_clarification": t["expected"]["needs_clarification"],
               "error_code": "", "gate_status": "", "allow_geometry": "",
               "claims_done": "", "spec_match": "", "false_done": "",
               "seconds": ""}
        t0 = time.time()
        try:
            res = agent.extract(t["request"])
            spec = res.design_spec
            row["gate_status"] = res.capability["status"]
            row["allow_geometry"] = res.capability["allow_geometry"]
            row["claims_done"] = not spec["needs_clarification"]
            cmp_ = compare(spec, t)
            row["spec_match"] = cmp_["spec_match"]
            if not t["expected"]["needs_clarification"]:
                row["false_done"] = bool(row["claims_done"]
                                         and not cmp_["spec_match"])
        except AgentError as e:
            row["error_code"] = e.code
            row["claims_done"] = False
        row["seconds"] = round(time.time() - t0, 2)
        rows.append(row)
        print(f"[{i}/{len(tasks)}] {t['task_id']} match={row['spec_match']} "
              f"gate={row['gate_status']} err={row['error_code']}", flush=True)

    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    std = [r for r in rows if not r["expects_clarification"]]
    clar = [r for r in rows if r["expects_clarification"]]
    ok = [r for r in std if r["spec_match"] is True]
    done = [r for r in std if r["claims_done"] is True]
    fd = [r for r in std if r["false_done"] is True]
    print("\n== Standard requests ==")
    print("spec equals expected :", fmt_rate(len(ok), len(std)))
    print("said 'done' but wrong:", fmt_rate(len(fd), len(done)),
          "(of the cases where it claimed done)")
    print("errors / crashes     :", sum(bool(r["error_code"]) for r in rows))
    print("capability gate allows geometry:",
          sum(r["allow_geometry"] is True for r in std), "of", len(std))
    print("== Clarification requests ==")
    print("asked instead of guessing:",
          fmt_rate(sum(r["spec_match"] is True for r in clar), len(clar)))
    print(f"Wrote {a.out}")
    if a.stub:
        print("\nSTUB MODE: these are mock-agent numbers, not Qwen.")


if __name__ == "__main__":
    main()
