#!/usr/bin/env python3
"""Statistics helpers for the Pixolid benchmark (standard library only).

Functions
  wilson(k, n)            95% Wilson interval for a proportion
  mcnemar_exact(b, c)     exact two-sided McNemar p for paired pass/fail
  blind_agreement(...)    checks-vs-print agreement from the blind test logs
  false_done_rates(...)   how often the AI says "done" when the case fails

CLI
  python analyze.py --selftest
  python analyze.py blind --log blind_test_log.csv --pred predictions.csv
"""
import argparse
import csv
import math
import sys

TRUE = {"1", "true", "t", "yes", "y", "pass", "passed"}
FALSE = {"0", "false", "f", "no", "n", "fail", "failed"}


def as_bool(v):
    s = str(v).strip().lower()
    if s in TRUE:
        return True
    if s in FALSE:
        return False
    raise ValueError(f"cannot read {v!r} as pass/fail")


def wilson(k, n, z=1.96):
    """Wilson score interval (lo, hi). n == 0 -> (nan, nan)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant pair counts.
    b = only A passes, c = only B passes."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def fmt_rate(k, n):
    if n == 0:
        return "n/a (n=0)"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.1%}  (95% CI {lo:.1%}-{hi:.1%})"


def cohen_kappa(pairs):
    """pairs: list of (a, b) booleans."""
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    pa = sum(a for a, _ in pairs) / n
    pb = sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def false_done_rates(rows):
    """rows: dicts with ai_claims_done and checks_pass (or overall_pass).
    Returns (claims_done, of_which_failed, total_failed)."""
    done = failed_done = failed = 0
    for r in rows:
        ok = as_bool(r["measured_pass"])
        claim = as_bool(r["ai_claims_done"])
        failed += (not ok)
        if claim:
            done += 1
            failed_done += (not ok)
    return done, failed_done, failed


def blind_agreement(log_rows, pred_rows, min_n=100, target=0.90):
    pred = {r["test_id"]: r for r in pred_rows}
    pairs, claims = [], []
    skipped = 0
    for r in log_rows:
        p = pred.get(r["test_id"])
        if p is None or not str(r.get("overall_pass", "")).strip():
            skipped += 1
            continue
        measured = as_bool(r["overall_pass"])
        predicted = as_bool(p["checks_overall_pass"])
        pairs.append((predicted, measured))
        if "ai_claims_done" in p and str(p["ai_claims_done"]).strip():
            claims.append({"measured_pass": measured,
                           "ai_claims_done": p["ai_claims_done"]})
    n = len(pairs)
    agree = sum(a == b for a, b in pairs)
    false_pass = sum(a and not b for a, b in pairs)
    false_fail = sum((not a) and b for a, b in pairs)
    lo, hi = wilson(agree, n)
    out = {
        "n": n, "skipped_unjoined_or_unfilled": skipped,
        "agree": agree, "agreement": agree / n if n else float("nan"),
        "ci95": (lo, hi), "false_pass": false_pass, "false_fail": false_fail,
        "kappa": cohen_kappa(pairs),
        "enough_tests": n >= min_n,
        "point_estimate_meets_target": (agree / n >= target) if n else False,
        "ci_lower_meets_target": lo >= target if n else False,
        "claims": claims,
    }
    return out


def print_blind(res):
    print(f"Blind tests joined: {res['n']}"
          f"  (rows skipped: {res['skipped_unjoined_or_unfilled']})")
    print("Agreement checks vs print:", fmt_rate(res["agree"], res["n"]))
    print(f"False pass (checks OK, print failed): {res['false_pass']}"
          f"   False fail: {res['false_fail']}   kappa: {res['kappa']:.2f}")
    print(f">=100 tests: {res['enough_tests']}   "
          f"point estimate >=90%: {res['point_estimate_meets_target']}   "
          f"CI lower bound >=90%: {res['ci_lower_meets_target']}")
    if res["claims"]:
        d, fd, f = false_done_rates(res["claims"])
        print("AI said 'done' but case failed:", fmt_rate(fd, d),
              f"| of all {f} failed cases, AI had claimed done in {fd}")


def selftest():
    lo, hi = wilson(5, 10)
    assert abs(lo - 0.2366) < 1e-3 and abs(hi - 0.7634) < 1e-3, (lo, hi)
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and abs(hi - 0.2775) < 1e-3, (lo, hi)
    assert abs(mcnemar_exact(0, 8) - 2 / 256) < 1e-12
    assert mcnemar_exact(3, 3) == 1.0 and mcnemar_exact(0, 0) == 1.0
    assert abs(cohen_kappa([(True, True), (False, False)] * 5) - 1.0) < 1e-12
    log = [{"test_id": "a", "overall_pass": "true"},
           {"test_id": "b", "overall_pass": "false"},
           {"test_id": "c", "overall_pass": "true"}]
    pred = [{"test_id": "a", "checks_overall_pass": "true", "ai_claims_done": "true"},
            {"test_id": "b", "checks_overall_pass": "true", "ai_claims_done": "true"},
            {"test_id": "c", "checks_overall_pass": "true", "ai_claims_done": "true"}]
    r = blind_agreement(log, pred)
    assert r["n"] == 3 and r["agree"] == 2 and r["false_pass"] == 1
    d, fd, f = false_done_rates(r["claims"])
    assert (d, fd, f) == (3, 1, 1)
    print("selftest ok")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("cmd", nargs="?", choices=["blind"])
    ap.add_argument("--log")
    ap.add_argument("--pred")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        selftest()
        return 0
    if a.cmd == "blind":
        if not (a.log and a.pred):
            ap.error("blind needs --log and --pred")
        print_blind(blind_agreement(read_csv(a.log), read_csv(a.pred)))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
