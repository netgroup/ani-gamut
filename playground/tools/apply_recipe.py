#!/usr/bin/env python3
"""Apply a [{device, command}] recipe to a deployed lab via docker exec, netns-aware for the
host-aggregator (device hs<N> -> `ip netns exec h<N>` inside clab-<lab>-<agg>). Committed so the
A3-T / change-set ground-truth recipe tests have a robust applier (no fragile heredoc).

    .venv/bin/python tools/apply_recipe.py --lab srv6-w0 --agg hosts --recipe /tmp/cs.json
"""
import argparse
import json
import re
import subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--lab", default="srv6-w0")
ap.add_argument("--agg", default="hosts", help="aggregator node name (empty = one container per host)")
ap.add_argument("--recipe", required=True, help="path to the [{device, command}] recipe JSON")
a = ap.parse_args()

recipe = json.load(open(a.recipe))
fail = 0
for x in recipe:
    d, c = x["device"], x["command"]
    m = re.fullmatch(r"hs(\d+)", d)
    if m and a.agg:
        argv = ["docker", "exec", "-u", "0", f"clab-{a.lab}-{a.agg}",
                "ip", "netns", "exec", f"h{m.group(1)}", "sh", "-c", c]
    else:
        argv = ["docker", "exec", "-u", "0", f"clab-{a.lab}-{d}", "sh", "-c", c]
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode and "File exists" not in r.stderr and "No such" not in r.stderr:
        fail += 1
        print(f"FAIL [{d}] rc={r.returncode}: {c[:55]} :: {r.stderr.strip()[:70]}")
print(f"apply_recipe: {len(recipe) - fail}/{len(recipe)} ok ({fail} fail)")
