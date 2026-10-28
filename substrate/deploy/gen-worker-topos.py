#!/usr/bin/env python3
"""Generate per-worker containerlab topologies for parallel ANI-Gamut runs.

Each worker gets an isolated lab: a distinct name (hence distinct container
names clab-<name>-<node>) and a distinct management network/subnet, so K copies
of the fabric coexist on one host. The data plane lives in each node's network
namespace, so SRv6 locators and 10.x addresses can stay identical across workers
without colliding; only the lab name and the mgmt network are host-shared.

Two independent, decoupled control-plane axes (both OFF by default = lean lab):
  --with-datapizza : include the `master` node (the datapizza orchestrator).
  --with-rabbit    : include the `rabbit` node (the RabbitMQ pub/sub bus).
RabbitMQ is only a message bus and is independent of datapizza; the per-node daemon
(pika + pyroute2, datapizza-free) uses it to apply encap/decap. So "rabbit without
datapizza" is a valid, datapizza-free actuation channel. The reverse, datapizza
without rabbit, is rejected (the orchestrator would have no bus to talk on). Neither
node carries a data-plane link, so dropping them removes no topology.

    python3 deploy/gen-worker-topos.py --workers 4                # lean (docker-exec only)
    python3 deploy/gen-worker-topos.py --workers 4 --with-rabbit  # + pub/sub bus + node daemons
    python3 deploy/gen-worker-topos.py --workers 1 --with-datapizza --with-rabbit  # full lab

Run with an interpreter that has PyYAML, e.g. the net-ai-bench venv:
    ~/26-net-ai-bench/.venv/bin/python deploy/gen-worker-topos.py --workers 2
"""
import argparse
import random
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    raise SystemExit(
        "PyYAML required. Run with the net-ai-bench venv, e.g.\n"
        "  ~/26-net-ai-bench/.venv/bin/python deploy/gen-worker-topos.py --workers 2"
    )

BASE = Path(__file__).resolve().parent.parent / "topo.yaml"
DATAPIZZA_NODE = "master"   # the datapizza orchestrator
RABBIT_NODE = "rabbit"      # the RabbitMQ pub/sub bus (datapizza-independent)


def aggregate_hosts(topo: dict, hosts_node: str) -> int:
    """Collapse every hs<N> node into one aggregator container that owns all host legs.

    RAM-footprint optimization (branch host-aggregator): instead of 12 host
    containers, one container holds all PE<->host legs, each in its own network
    namespace (see scripts/lib/hosts_aggregator.sh). The routers are NOT merged
    (each is a distinct SRv6 node and the agent acts on it individually). Each link
    endpoint hs<N>:hs<N>-pe<M> is rewritten to <hosts_node>:hs<N>-pe<M>; the PE side
    interface name (pe<M>-hs<N>) is left untouched, so the PE boot and the tenant
    generator keep working unchanged. Returns the number of hosts collapsed.
    """
    topology = topo.setdefault("topology", {})
    nodes = topology.setdefault("nodes", {})
    hs = [n for n in list(nodes) if re.fullmatch(r"hs\d+", n)]
    for n in hs:
        nodes.pop(n, None)
    # the aggregator runs its own boot script (bypasses the startup.sh dispatch,
    # which only matches hs/pe/igw/egw<digits>); image + binds inherit from defaults.
    # Invoke via `bash` so it does not depend on the file's +x bit (commits from
    # Windows drop the executable bit, which silently breaks a bare-path exec).
    nodes[hosts_node] = {"exec": ["bash", "/opt/clab/lib/hosts_aggregator.sh"]}
    for link in topology.get("links", []):
        new = []
        for ep in link.get("endpoints", []):
            node, _, iface = ep.partition(":")
            new.append(f"{hosts_node}:{iface}" if re.fullmatch(r"hs\d+", node) else ep)
        link["endpoints"] = new
    return len(hs)


def regenerate_hosts(topo: dict, n_hosts: int, homing: int, seed: int) -> tuple[int, int]:
    """Replace the static host set with N hosts, each MULTI-HOMED to `homing` distinct
    random PEs (seeded). The fabric (PE/IGW/EGW + their links) is left untouched; the
    underlay route plane does not depend on stub hosts, so host count/wiring is free to
    grow. Host hs<N> gets `homing` legs hs<N>-pe<M>; which leg is the active attachment in
    the brownfield is decided later by the tenant generator (gen_tenants), seeded. Returns
    (n_hosts, total_legs). Same seed across workers -> identical wiring per lab."""
    topology = topo.setdefault("topology", {})
    nodes = topology.setdefault("nodes", {})
    links = topology.setdefault("links", [])
    pes = sorted((n for n in nodes if re.fullmatch(r"pe\d+", n)), key=lambda s: int(s[2:]))
    if homing > len(pes):
        raise SystemExit(f"--homing {homing} exceeds the {len(pes)} PEs available ({pes})")
    # drop the static hosts and every host<->PE link (host-side endpoint matches hs<N>)
    for n in [n for n in list(nodes) if re.fullmatch(r"hs\d+", n)]:
        nodes.pop(n, None)
    kept = [lk for lk in links
            if not any(re.fullmatch(r"hs\d+", ep.partition(":")[0]) for ep in lk.get("endpoints", []))]
    rng = random.Random(seed)
    total = 0
    for h in range(1, n_hosts + 1):
        nodes[f"hs{h}"] = {}
        for pe in rng.sample(pes, homing):
            m = int(pe[2:])
            kept.append({"endpoints": [f"hs{h}:hs{h}-pe{m}", f"pe{m}:pe{m}-hs{h}"]})
            total += 1
    topology["links"] = kept
    return n_hosts, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, required=True, help="number of isolated labs to generate")
    ap.add_argument("--prefix", default="srv6", help="lab name prefix -> <prefix>-w<N>")
    ap.add_argument("--mgmt-base", type=int, default=30,
                    help="mgmt subnet third octet base: 172.20.<base+w>.0/24 (avoid 20 = clab default)")
    ap.add_argument("--with-datapizza", action="store_true",
                    help="include the datapizza orchestrator node (master); off by default")
    ap.add_argument("--with-rabbit", action="store_true",
                    help="include the RabbitMQ pub/sub bus node (rabbit); off by default. "
                         "Independent of datapizza: 'rabbit without datapizza' is a valid "
                         "datapizza-free actuation channel")
    ap.add_argument("--aggregate-hosts", action="store_true",
                    help="collapse the 12 host nodes into one aggregator container (host legs in "
                         "per-host network namespaces); off by default. Cuts ~11 container "
                         "overheads per lab. Routers are not merged. Pair with gen_tenants.py / "
                         "run_pilot.py --hosts-aggregator <name> so the oracle and agent reach "
                         "hosts via 'ip netns exec h<N>'")
    ap.add_argument("--hosts-node", default="hosts",
                    help="name of the aggregator node when --aggregate-hosts is set (default: hosts)")
    ap.add_argument("--hosts", type=int, default=0,
                    help="regenerate the host set with N multi-homed hosts (0 = keep the static "
                         "hosts from topo.yaml). Use for the change-set scale (e.g. --hosts 75)")
    ap.add_argument("--homing", type=int, default=3,
                    help="when --hosts is set, wire each host to this many distinct random PEs "
                         "(multi-homed CE; the active attachment is chosen by gen_tenants)")
    ap.add_argument("--wiring-seed", type=int, default=1234,
                    help="seed for the host->PE multi-homing; same across workers -> identical wiring")
    a = ap.parse_args()

    if not BASE.exists():
        raise SystemExit(f"base topology not found: {BASE}")
    # consistency: the datapizza orchestrator needs a bus to talk on
    if a.with_datapizza and not a.with_rabbit:
        raise SystemExit("inconsistent flags: --with-datapizza requires --with-rabbit "
                         "(datapizza communicates over RabbitMQ; rabbit-without-datapizza is fine, "
                         "datapizza-without-rabbit is not)")
    drop = []
    if not a.with_datapizza:
        drop.append(DATAPIZZA_NODE)
    if not a.with_rabbit:
        drop.append(RABBIT_NODE)

    written = []
    for w in range(a.workers):
        topo = yaml.safe_load(BASE.read_text())          # fresh copy per worker
        topo["name"] = f"{a.prefix}-w{w}"
        topo["mgmt"] = {"network": f"clab-w{w}",
                        "ipv4-subnet": f"172.20.{a.mgmt_base + w}.0/24",
                        # IPv6 mgmt too: the node boot runs `ip -6 route del default` under
                        # `set -e`; with an IPv4-only mgmt there is no IPv6 default to delete,
                        # so the boot aborts before installing the SRv6 underlay. The default
                        # clab network has both families; mirror that here.
                        "ipv6-subnet": f"3fff:172:20:{a.mgmt_base + w}::/64"}
        nodes = topo.get("topology", {}).get("nodes", {})
        for n in drop:
            nodes.pop(n, None)
        n_legs = 0
        if a.hosts > 0:
            _, n_legs = regenerate_hosts(topo, a.hosts, a.homing, a.wiring_seed)
        n_agg = aggregate_hosts(topo, a.hosts_node) if a.aggregate_hosts else 0
        nodes = topo.get("topology", {}).get("nodes", {})   # refresh after aggregation
        out = BASE.parent / f"topo-w{w}.yaml"
        out.write_text(
            "# GENERATED by deploy/gen-worker-topos.py -- do not edit, do not commit.\n"
            + yaml.safe_dump(topo, sort_keys=False)
        )
        written.append(out.name)
        agg_note = f" aggregated={n_agg}->{a.hosts_node}" if a.aggregate_hosts else ""
        hosts_note = f" hosts={a.hosts}x{a.homing}-homed legs={n_legs}" if a.hosts > 0 else ""
        print(f"  {out.name}: name={topo['name']} mgmt={topo['mgmt']['ipv4-subnet']} "
              f"nodes={len(nodes)} dropped={drop or 'none'}{agg_note}{hosts_note}")
    print(f"wrote {len(written)} topo file(s) in {BASE.parent}")


if __name__ == "__main__":
    raise SystemExit(main())
