"""Success/failure tally per checkpoint.

The live demo is 5 consecutive attempts worth 6 points each, and the jury asks how you
iterated. Logging every evaluation attempt gives you (a) an objective way to pick the
checkpoint for the demo and (b) the numbers to quote in the presentation.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import OrderedDict
from math import comb

from .config import JOURNAL_DIR

EVAL_CSV = JOURNAL_DIR / "eval.csv"
FIELDS = ["timestamp", "policy", "result", "note"]


def _read() -> list[dict]:
    if not EVAL_CSV.exists():
        return []
    with open(EVAL_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def add(policy: str, result: str, note: str = "") -> None:
    JOURNAL_DIR.mkdir(exist_ok=True)
    new = not EVAL_CSV.exists()
    with open(EVAL_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(
            {
                "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "policy": policy,
                "result": "success" if result == "s" else "fail",
                "note": note,
            }
        )


def prob_at_least(k: int, n: int, p: float) -> float:
    return sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k, n + 1))


def summary() -> None:
    rows = _read()
    if not rows:
        print("No evaluation attempts logged yet.  Log some with:  so eval <policy-label>")
        return
    groups: "OrderedDict[str, list[dict]]" = OrderedDict()
    for r in rows:
        groups.setdefault(r["policy"], []).append(r)
    print(f"\n{'policy / checkpoint':<44} {'tries':>5} {'ok':>4} {'rate':>6}   {'demo pts (exp.)':>15}   P(>=3 of 5)")
    print("-" * 100)
    best = None
    for policy, rs in groups.items():
        n = len(rs)
        ok = sum(r["result"] == "success" for r in rs)
        # Laplace-smoothed rate so 2/2 does not look better than 9/10.
        p = (ok + 1) / (n + 2)
        expected = 30 * p
        print(f"{policy:<44} {n:>5} {ok:>4} {ok / n:>6.0%}   {expected:>12.1f}/30   {prob_at_least(3, 5, p):>10.0%}")
        if n >= 5 and (best is None or p > best[1]):
            best = (policy, p)
    print("-" * 100)
    print("rate = raw successes/tries; demo points use a smoothed rate ((ok+1)/(tries+2)).")
    if best:
        print(f"Best checkpoint with >= 5 tries so far: {best[0]}")
    fails = [r for r in rows if r["result"] == "fail" and r["note"]]
    if fails:
        print("\nRecent failure notes (record more episodes of these cases):")
        for r in fails[-8:]:
            print(f"  {r['timestamp']}  {r['policy']}: {r['note']}")
    print(f"\nRaw log: {EVAL_CSV}")


def interactive(policy: str, attempts: int) -> None:
    print(f"\nLogging attempts for: {policy}")
    print("After each attempt type:  s = success   f = fail   q = stop   (optionally add a note: `f missed grasp`)")
    done = 0
    while attempts <= 0 or done < attempts:
        try:
            raw = input(f"  attempt {done + 1}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        key, _, note = raw.partition(" ")
        key = key.lower()
        if key in ("q", "quit"):
            break
        if key not in ("s", "f"):
            print("    s / f / q please")
            continue
        add(policy, key, note.strip())
        done += 1
    summary()
