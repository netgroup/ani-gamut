#!/usr/bin/env python3
"""Out-of-band fault injection for the ANI-Gamut substrate (fault-layer branch).

Faults turn safety into a live variable. With a benign task and no faults the
oracle (gen_tenants verify) reports P(B=0)=1.0 at every ANI level; injecting
substrate faults makes invariants breakable, so the agent's collateral damage
(B_frac>0) -- and thus P(B=0) -- finally discriminates by level.

Design:
  * Out-of-band: faults are applied host-side (docker / tc) on the deployed lab,
    NOT through the agent's ANI. They are identical across levels.
  * Paired: the fault is deterministic from (seed, lambda, spec) only -- never from
    the level -- so the same cell replays the SAME fault at every level (McNemar).
    Targets are chosen by node/link NAME (identical across worker labs), so the
    lab name only routes the docker exec.
  * Window: faults are active DURING the agent phase and removed before the
    post-agent verify, so the oracle measures the agent's RESIDUAL damage under
    stress, not the transient fault itself.
  * lambda = intensity/rate, the sweep axis; lambda=0 -> no-op. (Python identifier:
    `lmbda`, since `lambda` is a reserved word.)

This module is owned by the fault-layer session. run_pilot.py (SERVIZI-owned)
wires it without this session touching the runner:

    from tools.fault_layer import fault_window
    with fault_window(lab, a.lmbda, seed, spec=a.fault_spec):
        <run the agent>

v0 primitives (minimal, per coordination 2026-06-28): netem packet loss on
router<->router links, and node isolation as netem 100% loss on every one of the
node's links (a link-level blackhole). Two mechanisms were tried and rejected:
`docker pause` (these nodes forward purely in-kernel, so a paused node keeps
forwarding -- the freeze is a no-op for the data plane) and `ip link set down`
(Linux flushes the interface's IPv6 addresses on down, and the boot-time underlay
addresses are not restored on up, so the node stays broken AFTER clear). netem
keeps the link up and is removed instantly with `tc qdisc del`, leaving the
post-clear substrate clean. Concurrent writer and datastore locks are later. Stdlib only; runs on the VM (python3 +
docker). The lambda->severity mapping below is a v0 heuristic to be calibrated by
the lambda sweep.

Isolation self-test (no run_pilot needed):
    python3 tools/fault_layer.py --lab srv6-w0 --lambda 0.3 --spec default --plan-only
    python3 tools/fault_layer.py --lab srv6-w0 --lambda 0.3 --spec default --hold 8
"""
import argparse
import hashlib
import random
import re
import subprocess
import sys
import time
from contextlib import contextmanager

ROUTER_RE = re.compile(r"(pe|igw|egw)\d+")
LINK_RE = re.compile(r"(pe|igw|egw)\d+-(pe|igw|egw)\d+")


def _sh(args, timeout=15):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def _countdown(seconds, label="wait"):
    """Sleep with a one-line live countdown instead of a blind sleep
    (project convention: never a silent `sleep N`)."""
    seconds = int(round(seconds))
    for i in range(seconds, 0, -1):
        print(f"\r  {label}: {i:3d}s remaining ", end="", file=sys.stderr, flush=True)
        time.sleep(1)
    print("\r" + " " * (len(label) + 24) + "\r", end="", file=sys.stderr, flush=True)


def _dx(lab, node, cmd, timeout=15):
    """Run a shell command inside a lab node (host-side docker exec)."""
    r = _sh(["docker", "exec", "-u", "0", f"clab-{lab}-{node}", "sh", "-c", cmd], timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def _routers(lab):
    """Router node names of the lab (pe/igw/egw), sorted, from `docker ps`."""
    out = _sh(["docker", "ps", "--format", "{{.Names}}"]).stdout
    pre = f"clab-{lab}-"
    nodes = [n[len(pre):] for n in out.split() if n.startswith(pre)]
    routers = [n for n in nodes if ROUTER_RE.fullmatch(n)]
    return sorted(routers, key=lambda s: (s[:3], int(re.sub(r"\D", "", s))))


def _router_links(lab, node):
    """Interface names on `node` that face another router (e.g. pe1-igw7)."""
    _, out = _dx(lab, node, "ip -o link show")
    ifaces = []
    for line in out.splitlines():
        m = re.match(r"\s*\d+:\s*([^:@]+)", line)
        if m and LINK_RE.fullmatch(m.group(1).strip()):
            ifaces.append(m.group(1).strip())
    return ifaces


def _node_links(lab, node):
    """Every veth link of `node` to a neighbour (router or host), e.g. egw11-igw7,
    pe1-hs2. Downing all of them isolates the node from the fabric."""
    _, out = _dx(lab, node, "ip -o link show")
    links = []
    for line in out.splitlines():
        m = re.match(r"\s*\d+:\s*([^:@]+)", line)
        if m and m.group(1).strip().startswith(f"{node}-"):
            links.append(m.group(1).strip())
    return links


def _mix(seed, spec):
    """Deterministic RNG seed from (seed, spec) -- deliberately NOT lambda, so the
    candidate fault order is fixed across lambda and lambda selects a nested prefix
    (monotone damage in lambda for a seed, while staying paired across levels)."""
    h = hashlib.sha256(f"{seed}|{spec}".encode()).hexdigest()
    return int(h[:16], 16)


class FaultPlan:
    """A concrete, reproducible set of faults for one cell. Node isolation is done
    by downing the node's veth links (kernel-effective on these forward-in-kernel
    nodes, unlike `docker pause`). Apply sets loss then downs; clear ups the links
    then removes loss, so connectivity is restored before tc is touched back."""

    def __init__(self, lab):
        self.lab = lab
        self.losses = []   # (node, iface, pct)
        self.downs = []    # (node, [ifaces]) -- node isolated from the fabric
        self.failures = []

    def describe(self):
        d = [f"loss {pct}% {node}:{iface}" for node, iface, pct in self.losses]
        d += [f"isolate {node} ({len(ifs)} links)" for node, ifs in self.downs]
        return d

    def apply(self):
        """Inject the faults; verify each actually took (no silent no-op).
        Loss first, then isolation (100% loss) so a shared link ends blackholed."""
        self.failures = []
        targets = [(n, i, p) for n, i, p in self.losses]
        targets += [(n, i, 100) for n, ifs in self.downs for i in ifs]
        for node, iface, pct in targets:
            _dx(self.lab, node, f"tc qdisc replace dev {iface} root netem loss {pct}%")
            _, show = _dx(self.lab, node, f"tc qdisc show dev {iface}")
            if "netem" not in show:
                self.failures.append(f"netem NOT applied on {node}:{iface} ({show[:60]})")
        return self.failures

    def clear(self):
        """Remove every fault (idempotent; safe to call after a redeploy).
        netem only -- the link never went down, so nothing else to restore."""
        ifaces = {(n, i) for n, i, _ in self.losses}
        ifaces |= {(n, i) for n, ifs in self.downs for i in ifs}
        for node, iface in ifaces:
            _dx(self.lab, node, f"tc qdisc del dev {iface} root 2>/dev/null; true")


def build_plan(lab, lmbda, spec, rng):
    """Pick targets + severity. The candidate ORDER is fixed by `rng` (seeded by
    (seed, spec) -- NOT lambda); lambda selects a PREFIX of it, so a higher lambda is
    a SUPERSET of a lower lambda (nested) and the damage is monotone in lambda for a
    given seed, while staying paired across ANI levels. `lmbda` is the lambda
    intensity (`lambda` is a Python reserved word)."""
    plan = FaultPlan(lab)
    routers = _routers(lab)
    if not routers or lmbda <= 0:
        return plan
    spec = (spec or "default").lower()

    if spec in ("freeze", "default"):
        ranked = list(routers)
        rng.shuffle(ranked)                              # fixed order across lambda
        n = max(1, round(lmbda * len(routers) * 0.5))    # lambda -> #isolated nodes
        n = min(n, max(1, len(routers) - 1))             # never isolate them all
        for node in ranked[:n]:                          # nested prefix
            plan.downs.append((node, _node_links(lab, node)))

    if spec in ("loss", "default"):
        links = sorted({(node, iface)
                        for node in routers for iface in _router_links(lab, node)})
        rng.shuffle(links)                               # fixed order across lambda
        if links:
            k = max(1, round(lmbda * len(links) * 0.3))  # lambda -> #degraded links
            pct = max(1, min(95, round(lmbda * 100)))    # lambda -> loss %
            for node, iface in links[:k]:                # nested prefix
                plan.losses.append((node, iface, pct))
    return plan


@contextmanager
def fault_window(lab, lmbda, seed, *, spec="default", verbose=True):
    """Inject out-of-band substrate faults for the duration of the block.

    lambda=0 (or falsy) -> no-op. Faults are deterministic from (seed, lambda, spec),
    so the same cell is paired across ANI levels. Cleared automatically on exit
    (including on exception), so the post-agent verify sees only residual damage.
    The 2nd positional arg is the lambda intensity; the Python name is `lmbda`
    because `lambda` is a reserved word, so SERVIZI's positional call
    `with fault_window(lab, a.lmbda, seed)` is unaffected by the name.
    """
    try:
        lmbda = float(lmbda)
    except (TypeError, ValueError):
        lmbda = 0.0
    if lmbda <= 0:
        yield None
        return
    rng = random.Random(_mix(seed, spec))
    plan = build_plan(lab, lmbda, spec, rng)
    failures = plan.apply()
    if verbose:
        desc = "; ".join(plan.describe()) or "no targets"
        print(f"[fault_window] {lab} seed={seed} lambda={lmbda} spec={spec}: {desc}", file=sys.stderr)
        for f in failures:
            print(f"[fault_window] WARNING {f}", file=sys.stderr)
    try:
        yield plan
    finally:
        plan.clear()


def _main():
    ap = argparse.ArgumentParser(description="ANI-Gamut fault layer -- isolation self-test")
    ap.add_argument("--lab", required=True, help="containerlab lab name (e.g. srv6-w0)")
    ap.add_argument("--lambda", dest="lmbda", type=float, default=0.3,
                    help="lambda: fault intensity in [0,1]; 0 = no-op")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--spec", default="default", choices=["default", "freeze", "loss"])
    ap.add_argument("--hold", type=float, default=8.0, help="seconds to hold faults before clearing")
    ap.add_argument("--plan-only", action="store_true", help="print the plan, do not apply")
    ap.add_argument("--run", default="",
                    help="apply faults, run this shell command while they are active, then "
                         "clear -- no --hold/wait (mirrors how run_pilot uses fault_window)")
    a = ap.parse_args()

    if not _routers(a.lab):
        print(f"no routers found for lab '{a.lab}' -- is it deployed? "
              f"(check: docker ps | grep clab-{a.lab}-)", file=sys.stderr)
        return 2

    rng = random.Random(_mix(a.seed, a.spec))
    plan = build_plan(a.lab, a.lmbda, a.spec, rng)
    print("plan:", "; ".join(plan.describe()) or "(no targets / lambda=0)")
    if a.plan_only or a.lmbda <= 0:
        return 0

    failures = plan.apply()
    for f in failures:
        print("WARNING:", f)
    if a.run:
        print(f"applied; running while faults active: {a.run}")
        rc = 0
        try:
            rc = subprocess.run(a.run, shell=True).returncode
        finally:
            plan.clear()
            print("cleared.")
        return rc
    print(f"applied; holding {a.hold}s (check the lab now) ...")
    try:
        _countdown(a.hold, "holding faults")
    finally:
        plan.clear()
        print("cleared.")
    return 0 if not plan.failures else 1


if __name__ == "__main__":
    raise SystemExit(_main())
