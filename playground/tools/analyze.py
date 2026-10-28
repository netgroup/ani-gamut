#!/usr/bin/env python3
"""Paired analysis of an ANI-Gamut pilot run (results/pilot.json).

The pilot design is paired: the same seeds are run at every level, so the right
test for "does the abstraction level change success?" is McNemar on the paired
per-seed outcomes, not a comparison of the marginal rates (whose Wilson intervals
overlap even when the paired effect is strong).

Reports, per level: success rate and P(B_frac=0) with Wilson 95% intervals, mean
steps/tokens. Then, for each pair of levels: the 2x2 flip table and an exact
(binomial) two-sided McNemar p-value over the seeds that are valid in both levels.

    python3 tools/analyze.py                       # reads results/pilot.json
    python3 tools/analyze.py --in results/pilot.json

Stdlib only.
"""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact_p(b, c):
    """Two-sided exact (binomial) McNemar p-value for discordant counts b, c."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) * (0.5 ** n)
    return min(1.0, 2.0 * tail)


def valid(r):
    return not (r.get("invalid_baseline") or r.get("redeploy_failed")
                or r.get("agent_failed") or r.get("apply_failed") or r.get("cell_error"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(ROOT / "results" / "pilot.json"))
    a = ap.parse_args()

    data = json.loads(Path(a.inp).read_text())
    rows = [r for r in data["rows"] if valid(r)]
    levels = data["levels"]
    seeds = sorted({r["seed"] for r in rows})

    # solved[(seed, level)] -> bool ; also keep steps/tokens/damage_free
    solved = {}
    dfree = {}
    steps = {lvl: [] for lvl in levels}
    toks = {lvl: [] for lvl in levels}
    for r in rows:
        solved[(r["seed"], r["level"])] = bool(r["solved"])
        dfree[(r["seed"], r["level"])] = bool(r["damage_free"])
        if r.get("steps") is not None:
            steps[r["level"]].append(r["steps"])
        if r.get("tokens") is not None:
            toks[r["level"]].append(r["tokens"])

    print(f"=== ANI-Gamut pilot analysis ({a.inp}) ===")
    print(f"levels={levels}  seeds={len(seeds)}  workers={data.get('workers')}  "
          f"model={data.get('model')}\n")

    print(f"{'level':7} {'n':>3} {'success (Wilson95)':22} {'P(B=0) (Wilson95)':22} "
          f"{'steps':>6} {'tokens':>8}")
    for lvl in levels:
        cells = [s for s in seeds if (s, lvl) in solved]
        n = len(cells)
        succ = sum(solved[(s, lvl)] for s in cells)
        db = sum(dfree[(s, lvl)] for s in cells)
        ps, sl, su = wilson(succ, n)
        pb, bl, bu = wilson(db, n)
        ms = sum(steps[lvl]) / len(steps[lvl]) if steps[lvl] else 0
        mt = sum(toks[lvl]) / len(toks[lvl]) if toks[lvl] else 0
        print(f"{lvl:7} {n:>3} {succ}/{n}={ps:.2f} [{sl:.2f},{su:.2f}]".ljust(7 + 4 + 23)
              + f"{db}/{n}={pb:.2f} [{bl:.2f},{bu:.2f}]".ljust(22)
              + f"{ms:6.1f} {mt:8.0f}")

    print("\npaired McNemar (exact, two-sided) over seeds valid in BOTH levels:")
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            lo, hi = levels[i], levels[j]
            common = [s for s in seeds if (s, lo) in solved and (s, hi) in solved]
            n11 = sum(solved[(s, lo)] and solved[(s, hi)] for s in common)
            n00 = sum((not solved[(s, lo)]) and (not solved[(s, hi)]) for s in common)
            lo_only = sum(solved[(s, lo)] and not solved[(s, hi)] for s in common)
            hi_only = sum(solved[(s, hi)] and not solved[(s, lo)] for s in common)
            p = mcnemar_exact_p(lo_only, hi_only)
            better = hi if hi_only > lo_only else (lo if lo_only > hi_only else "tie")
            sig = "*" if p < 0.05 else " "
            print(f"  {lo:6} vs {hi:7} | paired={len(common):2}  both={n11} neither={n00} "
                  f"{lo}only={lo_only} {hi}only={hi_only}  discordant={lo_only + hi_only}  "
                  f"p={p:.3f}{sig}  -> {better} better")

    # safety
    any_damage = any(not dfree[k] for k in dfree)
    print("\nsafety:", "collateral damage observed (analyze per-level)" if any_damage
          else "no collateral damage at any level -> H2/H3 not testable without fault injection.")

    # cost headline
    mt = {lvl: (sum(toks[lvl]) / len(toks[lvl]) if toks[lvl] else 0) for lvl in levels}
    if "a0" in mt and "a1" in mt and mt["a0"]:
        print(f"cost (H4): tokens a0={mt['a0']:.0f}  a1={mt['a1']:.0f} "
              f"(+{100 * (mt['a1'] - mt['a0']) / mt['a0']:.0f}% vs a0)"
              + (f"  a1plus={mt['a1plus']:.0f}" if "a1plus" in mt else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
