#!/usr/bin/env python3
"""Generate the SRv6 underlay static-route plane (configs/<router>.conf) from the
Containerlab topo.yaml, by shortest path over the router graph.

The boot script scripts/lib/router.sh reads ${CONFIG_DIR}/<node>.conf and installs
each line as `ip -6 route add <prefix> via <next_hop> dev <dev>`. This generator
produces those files from the topology, so the route plane always matches topo.yaml.

Output line format:
    <dst_locator_prefix>,<next_hop_ipv6>,<egress_iface>
e.g.  5f00:0:2::/48,fcf0:0:1:7::7,pe1-igw7

Conventions (see srv6-addressing-plan-F3216.md; in sync with state.py + common.sh):
  router id  = integer digits in the node name (pe1->1, igw7->7, egw10->10)
  locator    = F3216 uSID locator 5f00:0:<hex id>::/48  (Block 5f00:0000, Set 0x00, Node)
  link net   = fcf0:0:{min}:{max}   (global link addressing kept as legacy infra)
  next hop   = <link_net>::{neigh_id}   (neighbour address on that link)
  egress dev = local interface on the link toward the next hop ({R}-{nb})

Usage: python3 gen_underlay_routes.py <topo.yaml> <out_dir>
"""
import sys, os, yaml, networkx as nx

ROUTER_PREFIXES = ("pe", "igw", "egw")

def is_router(name): return any(name.startswith(p) for p in ROUTER_PREFIXES)
def node_id(name):   return int("".join(c for c in name if c.isdigit()))
def link_net(a, b):
    x, y = sorted((node_id(a), node_id(b)))
    return f"fcf0:0:{x}:{y}"

def load_topo(path):
    with open(path) as f:
        t = yaml.safe_load(f)
    return list(t["topology"]["nodes"].keys()), t["topology"]["links"]

def build_graph(nodes, links):
    routers = [n for n in nodes if is_router(n)]
    G = nx.Graph(); G.add_nodes_from(routers)
    iface = {}                                   # (a, b) -> a's egress iface toward b
    for link in links:
        (n1, i1), (n2, i2) = (ep.split(":") for ep in link["endpoints"])
        if is_router(n1) and is_router(n2):
            G.add_edge(n1, n2)
            iface[(n1, n2)] = i1
            iface[(n2, n1)] = i2
    return routers, G, iface

def gen(topo_path, out_dir):
    nodes, links = load_topo(topo_path)
    routers, G, iface = build_graph(nodes, links)
    os.makedirs(out_dir, exist_ok=True)
    for R in sorted(routers, key=node_id):
        lines = []
        for D in sorted(routers, key=node_id):
            if D == R:
                continue
            nb = nx.shortest_path(G, R, D)[1]    # first hop toward D
            # dst = F3216 uSID locator 5f00:0:<hex>::/48; next hop = global link addr (legacy infra)
            lines.append(f"5f00:0:{node_id(D):x}::/48,{link_net(R, nb)}::{node_id(nb)},{iface[(R, nb)]}")
        with open(os.path.join(out_dir, f"{R}.conf"), "w") as f:
            f.write("\n".join(lines) + "\n")
    return routers

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <topo.yaml> <out_dir>")
    rs = gen(sys.argv[1], sys.argv[2])
    print(f"generated {len(rs)} route files in {sys.argv[2]}: "
          + ", ".join(sorted(rs, key=node_id)))
