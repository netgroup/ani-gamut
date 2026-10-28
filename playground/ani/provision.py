#!/usr/bin/env python3
"""A3-T service provisioning: a typed intent realized as a transaction.

At level a3t the agent calls ONE tool, provision_service(intent), declaring WHAT
(op + tenant + sites). The layer does the HOW, transactionally: snapshot the
devices it will touch -> apply the tenant's realization (the gen_tenants
--emit-provision recipe, the layer's known-good commands) -> commit, or
AUTO-ROLLBACK every applied device on the first failure. The agent never sees the
per-device commands; that is the abstraction. Under faults this is where A3-T
earns its keep: a failed apply rolls back cleanly (no residual damage), whereas a
raw-shell agent (A0) leaves partial state.

This module holds the datapizza-free, lab-free core (intent validation + the
transaction loop, driven by callbacks) so it is unit-testable; ani/mcp_server.py
wires the real snapshot/apply/restore against the live lab.

Self-test (no lab, no datapizza):  python3 ani/provision.py
"""
import json
from collections import OrderedDict
from pathlib import Path

VALID_OPS = ("onboard", "add_site", "add-site", "change_set", "change-set")


def validate_intent(intent, target_tenant=None):
    """Return None if the intent is well-formed (and matches target_tenant when
    given), else an error string. The intent is the agent's typed request:
    {"op": "onboard", "tenant": <int>, "sites": [<host>, ...]}."""
    if not isinstance(intent, dict):
        return "intent must be a JSON object"
    op = intent.get("op")
    if op not in VALID_OPS:
        return f"intent.op must be one of {VALID_OPS}, got {op!r}"
    if "tenant" not in intent:
        return "intent.tenant is required"
    try:
        tid = int(intent["tenant"])
    except (TypeError, ValueError):
        return f"intent.tenant must be an integer, got {intent.get('tenant')!r}"
    sites = intent.get("sites")
    if sites is not None and not isinstance(sites, list):
        return "intent.sites, if given, must be a list of host names"
    changes = intent.get("changes")
    if changes is not None and not isinstance(changes, list):
        return "intent.changes, if given, must be a list of {op, host, ...} change ops"
    if target_tenant is not None and tid != int(target_tenant):
        return (f"intent.tenant {tid} does not match the held-out target tenant "
                f"{target_tenant} (the agent asked to provision the wrong tenant)")
    return None


def load_recipe(path):
    """Load a gen_tenants --emit-provision recipe: a list of {device, command}."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list) or not all(
            isinstance(x, dict) and "device" in x and "command" in x for x in data):
        raise ValueError("provision recipe must be a list of {device, command} objects")
    return data


def group_by_device(recipe):
    """Group recipe commands by device, preserving order within and across devices."""
    by = OrderedDict()
    for item in recipe:
        by.setdefault(item["device"], []).append(item["command"])
    return by


def run_transaction(recipe, snapshot, apply_cmds, restore):
    """Apply the recipe as an all-or-nothing transaction with auto-rollback.

    Callbacks:
      snapshot(device)         -> capture the device's rollback state
      apply_cmds(device, cmds) -> (ok: bool, detail); ok=False triggers rollback
      restore(device)          -> restore the device to its last snapshot

    On the first device whose apply reports not-ok, every snapshotted device (that
    one included) is restored in reverse order, leaving no partial tenant state.
    Returns a status dict: {"status": "success"|"rollback", ...}.
    """
    by_device = group_by_device(recipe)
    snapped = []
    applied = {}
    for device, cmds in by_device.items():
        snapshot(device)
        snapped.append(device)
        ok, detail = apply_cmds(device, cmds)
        applied[device] = detail
        if not ok:
            for d in reversed(snapped):
                restore(d)
            return {"status": "rollback", "failed_device": device,
                    "rolled_back": list(reversed(snapped)), "applied": applied}
    return {"status": "success", "devices": list(by_device), "applied": applied}


if __name__ == "__main__":
    # Lab-free, datapizza-free self-test of the transaction core + intent validation.
    recipe = [{"device": "pe1", "command": "ip a"}, {"device": "pe1", "command": "ip r"},
              {"device": "pe2", "command": "ip a"}]
    log = []

    def snap(d):
        log.append(("snap", d))

    def restore(d):
        log.append(("restore", d))

    # all succeed -> commit, no restore
    r = run_transaction(recipe, snap, lambda d, c: (True, {"n": len(c)}), restore)
    assert r["status"] == "success" and r["devices"] == ["pe1", "pe2"], r
    assert not [x for x in log if x[0] == "restore"], log

    # pe2 fails -> rollback restores pe2 then pe1 (reverse order)
    log.clear()
    r = run_transaction(recipe, snap, lambda d, c: (d != "pe2", {}), restore)
    assert r["status"] == "rollback" and r["failed_device"] == "pe2", r
    assert [x for x in log if x[0] == "restore"] == [("restore", "pe2"), ("restore", "pe1")], log

    # intent validation
    assert validate_intent({"op": "onboard", "tenant": 1, "sites": ["hs5"]}) is None
    assert validate_intent({"op": "bogus", "tenant": 1}) is not None
    assert validate_intent({"op": "onboard"}) is not None
    assert validate_intent({"op": "onboard", "tenant": 2}, target_tenant=1) is not None
    assert validate_intent({"op": "onboard", "tenant": 1}, target_tenant=1) is None

    print("provision.py self-test: OK")
