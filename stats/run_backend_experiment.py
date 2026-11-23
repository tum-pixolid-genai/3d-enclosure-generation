#!/usr/bin/env python3
"""Automatic experiment through the team's real Backend (stage 2: "connect the
system"). Sends each benchmark request to  POST /design  and records what the
whole pipeline (Agent -> capability gate -> Geometry -> export) answered.

Start the backend first (needs Ollama + CadQuery; run by Peicen/Qianshun):
    uvicorn backend.main:app --port 8000
then:
    python stats/run_backend_experiment.py --tasks benchmark/tasks.json \
        --base-url http://127.0.0.1:8000 --boards raspberry_pi_4 \
        --out stats/backend_results.csv

Per task it records: HTTP code, backend `status` (generated,
generated_with_warnings, needs_clarification, unsupported, review_required,
geometry_blocked, export_failed), seconds, whether the returned design_spec
equals the expected values, and
  system_says_done = status is generated / generated_with_warnings
  false_done       = system_says_done AND design_spec differs from expected
Only the spec is compared automatically. Whether the CAD really fits is what
the Geometry checks and the physical blind test decide, not this script.
Standard library only (plus the repo's stats helpers).
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from analyze import fmt_rate  # noqa: E402
from run_spec_stage import compare  # noqa: E402

DONE = {"generated", "generated_with_warnings"}


def post(url, payload, timeout):
    req = urllib.request.Request(
        url, json.dumps(payload).encode("utf-8"),
        {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {}
        return e.code, body
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"detail": {"code": "client_error", "message": str(e)}}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--boards", default="raspberry_pi_4")
    ap.add_argument("--limit", type=int, default=0, help="first N tasks only")
    ap.add_argument("--timeout", type=float, default=170,
                    help="seconds per request (frontend uses 150)")
    ap.add_argument("--out", default="backend_results.csv")
    a = ap.parse_args()

    boards = set(a.boards.split(","))
    tasks = [t for t in json.load(open(a.tasks, encoding="utf-8"))["tasks"]
             if t["board_id"] in boards]
    if a.limit:
        tasks = tasks[:a.limit]

    rows = []
    for i, t in enumerate(tasks, 1):
        t0 = time.time()
        code, body = post(a.base_url.rstrip("/") + "/design",
                          {"prompt": t["request"]["request_text"]}, a.timeout)
        secs = round(time.time() - t0, 2)
        status = body.get("status", "") if code == 200 else ""
        detail = body.get("detail") if isinstance(body, dict) else None
        err = detail.get("code", "") if isinstance(detail, dict) else ""
        row = {"task_id": t["task_id"], "board_id": t["board_id"],
               "category": t["category"],
               "expects_clarification": t["expected"]["needs_clarification"],
               "http_status": code, "status": status, "error_code": err,
               "gate_status": (body.get("capability") or {}).get("status", "")
               if code == 200 else "",
               "system_says_done": status in DONE, "spec_match": "",
               "false_done": "", "seconds": secs}
        spec = body.get("design_spec") if code == 200 else None
        if spec:
            row["spec_match"] = compare(spec, t)["spec_match"]
            if not t["expected"]["needs_clarification"]:
                row["false_done"] = bool(row["system_says_done"]
                                         and not row["spec_match"])
        rows.append(row)
        print(f"[{i}/{len(tasks)}] {t['task_id']} http={code} "
              f"status={status or err} {secs}s", flush=True)

    if not rows:
        print("no tasks selected")
        return 1
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    std = [r for r in rows if not r["expects_clarification"]]
    clar = [r for r in rows if r["expects_clarification"]]
    done = [r for r in std if r["system_says_done"]]
    print("\n== Outcome counts (all tasks) ==")
    for s in sorted({r["status"] or r["error_code"] or "no_response"
                     for r in rows}):
        n = sum((r["status"] or r["error_code"] or "no_response") == s
                for r in rows)
        print(f"  {s:26s}{n}")
    print("\n== Standard requests ==")
    print("system said done          :", fmt_rate(len(done), len(std)))
    print("design_spec equals expected:",
          fmt_rate(sum(r["spec_match"] is True for r in std), len(std)))
    print("said done but spec wrong  :",
          fmt_rate(sum(r["false_done"] is True for r in std), len(done)),
          "(of the cases where it said done)")
    print("== Clarification requests ==")
    print("asked a question (needs_clarification):",
          fmt_rate(sum(r["status"] == "needs_clarification" for r in clar),
                   len(clar)))
    print("did not generate anything (asked, blocked or sent to review):",
          fmt_rate(sum(not r["system_says_done"] for r in clar), len(clar)))
    times = sorted(r["seconds"] for r in rows)
    print(f"\nTime per request: median {times[len(times)//2]}s, "
          f"max {times[-1]}s, total {sum(times):.0f}s")
    print(f"Wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
