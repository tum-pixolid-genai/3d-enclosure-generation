#!/usr/bin/env python3
"""Run the benchmark through the *design step* only (request -> design spec)
for two conditions and compare each spec with the task's expected values.

  mock_agent         Qianshun's rule-based mock (agent/agent.py, PR #1)
  template_baseline  non-AI template (../baseline/template_baseline.py)

This measures structure extraction only. It says nothing about geometry,
printability or physical fit; those need Geometry and the blind prints.

Usage:
  python run_spec_stage.py --tasks ../benchmark/tasks.json \
      --agent-dir /path/to/agent --out spec_stage_results.csv
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "baseline"))

from analyze import fmt_rate, mcnemar_exact  # noqa: E402
import template_baseline  # noqa: E402


def normalise(spec):
    lid = spec.get("lid") or {}
    if lid.get("present") is False:
        lid_v = "none"
    elif lid.get("present") is True:
        lid_v = lid.get("style", "unspecified")
    else:
        lid_v = "unspecified"
    ports = []
    for p in spec.get("port_requirements") or []:
        ports += [(p["port_type"], p["requested_side"])] * (p.get("count") or 1)
    holes = (spec.get("mounting") or {}).get("wall_mount_hole_count")
    return {"board": spec.get("board_id"), "lid": lid_v,
            "ports": sorted(ports), "holes": holes or 0,
            "wall": spec.get("wall_thickness_mm"),
            "clar": bool(spec.get("needs_clarification"))}


def compare(spec, task):
    exp = task["expected"]
    got = normalise(spec)
    if exp["needs_clarification"]:
        ok = got["clar"]
        return {"board_ok": "", "lid_ok": "", "ports_ok": "", "holes_ok": "",
                "wall_ok": "", "clar_ok": ok, "spec_match": ok}
    exp_ports = sorted((p["port"], p["side"]) for p in exp["ports"])
    f = {
        "board_ok": got["board"] == exp["board_id"],
        "lid_ok": got["lid"] == exp["lid"],
        "ports_ok": got["ports"] == exp_ports,
        "holes_ok": got["holes"] == (exp["wall_mount_holes"] or 0),
        "wall_ok": got["wall"] == exp["wall_thickness_mm"],
        "clar_ok": not got["clar"],
    }
    f["spec_match"] = all(f.values())
    return f


def load_agent(agent_dir):
    sys.path.insert(0, agent_dir)
    import agent  # noqa: E402
    return agent


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--agent-dir", required=True)
    ap.add_argument("--out", default="spec_stage_results.csv")
    a = ap.parse_args()

    tasks = json.load(open(a.tasks, encoding="utf-8"))["tasks"]
    agent = load_agent(a.agent_dir)
    rows = []
    for t in tasks:
        base = {"task_id": t["task_id"], "board_id": t["board_id"],
                "category": t["category"], "difficulty": t["difficulty"],
                "expects_clarification": t["expected"]["needs_clarification"]}
        # --- mock agent
        spec = agent.extract_design(t["request"])
        rows.append({**base, "condition": "mock_agent", "applicable": True,
                     "pred_needs_clarification": spec["needs_clarification"],
                     **compare(spec, t)})
        # --- template baseline (standard requests only)
        if t["expected"]["needs_clarification"]:
            rows.append({**base, "condition": "template_baseline",
                         "applicable": False, "pred_needs_clarification": "",
                         **{k: "" for k in ("board_ok", "lid_ok", "ports_ok",
                                            "holes_ok", "wall_ok", "clar_ok",
                                            "spec_match")}})
        else:
            bspec = template_baseline.build_spec(t["task_id"], t["expected"])
            rows.append({**base, "condition": "template_baseline",
                         "applicable": True, "pred_needs_clarification": False,
                         **compare(bspec, t)})

    cols = list(rows[0].keys())
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ------------------------------------------------------------- summary
    std = [r for r in rows if r["applicable"] and not r["expects_clarification"]]
    clar = [r for r in rows if r["applicable"] and r["expects_clarification"]]

    def rate(rs):
        return sum(bool(r["spec_match"]) for r in rs), len(rs)

    print("== Standard requests: design spec equals expected ==")
    for cond in ("mock_agent", "template_baseline"):
        rs = [r for r in std if r["condition"] == cond]
        print(f"{cond:18s} all boards : {fmt_rate(*rate(rs))}")
        for b in sorted({r['board_id'] for r in rs}):
            print(f"{'':18s} {b:22s}: "
                  f"{fmt_rate(*rate([r for r in rs if r['board_id'] == b]))}")

    print("\n== mock_agent, Raspberry Pi 4 only, by category ==")
    pi4 = [r for r in std if r["condition"] == "mock_agent"
           and r["board_id"] == "raspberry_pi_4"]
    for c in sorted({r["category"] for r in pi4}):
        print(f"  {c:22s}: {fmt_rate(*rate([r for r in pi4 if r['category'] == c]))}")

    print("\n== Requests that should trigger a clarification question ==")
    cm = [r for r in clar if r["condition"] == "mock_agent"]
    cm4 = [r for r in cm if r["board_id"] == "raspberry_pi_4"]
    print("mock_agent, Raspberry Pi 4 (informative):",
          fmt_rate(*rate(cm4)))
    for c in sorted({r["category"] for r in cm4}):
        print(f"  {c:26s}: {fmt_rate(*rate([r for r in cm4 if r['category'] == c]))}")
    print(f"mock_agent, other 3 boards: {sum(bool(r['spec_match']) for r in cm if r['board_id'] != 'raspberry_pi_4')}"
          f"/{len([r for r in cm if r['board_id'] != 'raspberry_pi_4'])} asked, "
          "but only because the board is unknown to the mock -> NOT counted as evidence")
    print("template_baseline: not applicable (a form cannot express conflicts)")

    # paired comparison on tasks both conditions handle
    by = defaultdict(dict)
    for r in std:
        by[r["task_id"]][r["condition"]] = bool(r["spec_match"])
    b = sum(v["template_baseline"] and not v["mock_agent"] for v in by.values())
    c = sum(v["mock_agent"] and not v["template_baseline"] for v in by.values())
    print(f"\nPaired (same {len(by)} standard tasks): only baseline correct={b}, "
          f"only mock agent correct={c}, exact McNemar p={mcnemar_exact(b, c):.3g}")
    print("\nNote: the baseline reads the structured 'expected' fields, so a "
          "100% there is by construction (a ceiling), not a result.")
    print(f"Wrote {a.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
