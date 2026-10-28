#!/usr/bin/env python3
"""Direct A3-T provision_service probe, bypassing the agent.

Calls mcp_server.provision_service() against a live lab that is already in the
held-out baseline (target tenant not provisioned) with its recipe emitted by
gen_tenants --emit-provision. Confirms the trusted layer applies the recipe with
NO agent allowlist (apply_raw) and reports the transaction status. Pair it with a
gen_tenants --mode verify afterwards to check the target became reachable.

This isolates "is the A3-T tool/recipe sound?" from "does the agent form the
intent?"; it does not deploy or verify (the caller does), so it has no heredoc and
pastes cleanly.

    .venv/bin/python tools/diag_a3t.py --lab srv6-w0 --recipe /tmp/r.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--lab", default="srv6-w0")
ap.add_argument("--recipe", default="/tmp/r.json")
ap.add_argument("--agg", default="hosts", help="host-aggregator node name (ANI_HOSTS_AGG)")
ap.add_argument("--tenant", type=int, default=1)
a = ap.parse_args()

os.environ["ANI_HOSTS_AGG"] = a.agg
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ani"))
sys.path.insert(0, str(ROOT / "ani" / "drivers"))

import mcp_server as M  # noqa: E402

M._lab_name = a.lab
M._level = "a3t"
M._provision_recipe = a.recipe
M._log_file = Path("/tmp/diag_a3t.jsonl")

seen: list[str] = []
for x in json.load(open(a.recipe)):
    if x["device"] not in seen:
        seen.append(x["device"])
M._node_kinds = {d: "linux" for d in seen}
M._rollback_stacks = {d: [] for d in seen}

res = M.provision_service({"op": "onboard", "tenant": a.tenant, "sites": []})
print("STATUS:", res.get("status"))
if res.get("status") != "success":
    print(json.dumps(res, indent=1)[:2000])
