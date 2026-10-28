#!/usr/bin/env bash

# SRv6 Data Center Network Simulation -- ANI-Gamut host aggregator
# Copyright (C) 2026 -- GPL v3 <https://www.gnu.org/licenses/gpl-3.0.html>
#
# hosts_aggregator.sh -- boot one container that holds ALL host endpoints.
#
# RAM-footprint optimization (branch host-aggregator): the 12 per-host
# containers are replaced by a single "hosts" container that owns every
# PE<->host veth. Each leg, named hs<N>-pe<M>, is moved into its own network
# namespace h<N>. Per-leg namespaces recreate the exact L3 isolation of the
# separate-container hosts:
#   * traffic between two hosts must traverse the SRv6 fabric (the leg is the
#     only interface in its namespace, with a default route to its PE), instead
#     of being short-circuited by local delivery inside one shared namespace;
#   * overlapping tenant addresses (e.g. 10.99.x reused across tenants) live in
#     different namespaces and never collide.
# Routing is left disabled in each namespace: a host is a pure stub (one uplink,
# one default route). The base IPv4 below is the bare-substrate default; the
# tenant generator (gen_tenants.py) overrides it per tenant at runtime via
# `docker exec <hosts> ip netns exec h<N> ...`.
#
# This script is referenced only by the aggregated worker topologies produced by
# deploy/gen-worker-topos.py --aggregate-hosts. It does not touch startup.sh or
# any canonical node boot path.

set -uo pipefail

# Host leg interface pattern: hs<N>-pe<M>  (N = host id, M = PE id).
readonly IFACE_RE='^hs([0-9]+)-pe([0-9]+)$'
readonly WAIT_TRIES=30      # ~30 s max wait for containerlab to wire the legs
readonly WAIT_QUIET=3       # consider wiring complete once the count is stable
readonly LEG_MTU=9000       # match the fabric MTU used on the router links

# List host legs currently present in the container's default namespace.
list_legs() {
    ip -o link show \
        | awk -F': ' '{print $2}' \
        | sed 's/@.*//' \
        | grep -E "$IFACE_RE" || true
}

# Wait until containerlab has attached the legs and their count is stable.
wait_for_legs() {
    local prev=-1 cur stable=0 i=0
    while (( i < WAIT_TRIES )); do
        cur=$(list_legs | wc -l)
        if (( cur > 0 && cur == prev )); then
            (( stable++ ))
            (( stable >= WAIT_QUIET )) && return 0
        else
            stable=0
        fi
        prev=$cur
        sleep 1
        (( i++ ))
    done
    return 0   # proceed with whatever is present; per-leg setup is idempotent
}

# Move one leg into its own namespace and apply the bare-substrate config.
setup_leg() {
    local iface="$1" id="$2" ns="h$2"

    ip netns add "$ns" 2>/dev/null || true
    if ! ip link set "$iface" netns "$ns" 2>/dev/null; then
        echo "hosts_aggregator: cannot move $iface into $ns " \
             "(needs CAP_SYS_ADMIN; is the node privileged?)" >&2
        return 1
    fi
    ip -n "$ns" link set lo up
    ip -n "$ns" link set "$iface" mtu "$LEG_MTU" up 2>/dev/null \
        || ip -n "$ns" link set "$iface" up
    ip -n "$ns" addr add "10.0.${id}.1/24" dev "$iface" 2>/dev/null || true
    ip -n "$ns" route replace default via "10.0.${id}.254" 2>/dev/null || true
    return 0
}

main() {
    command -v ip >/dev/null 2>&1 || { echo "hosts_aggregator: 'ip' not found" >&2; exit 1; }

    wait_for_legs

    local legs iface id n=0 ok=0
    legs="$(list_legs)"        # snapshot before we start moving interfaces out
    while IFS= read -r iface; do
        [[ -z "$iface" ]] && continue
        [[ "$iface" =~ $IFACE_RE ]] || continue
        id="${BASH_REMATCH[1]}"
        n=$((n + 1))
        setup_leg "$iface" "$id" && ok=$((ok + 1))
    done <<< "$legs"

    echo "hosts_aggregator: configured ${ok}/${n} host legs " \
         "($(ip netns list 2>/dev/null | wc -l) namespaces)"
    [[ "$n" -eq 0 ]] && echo "hosts_aggregator: WARNING no hs<N>-pe<M> legs found" >&2
    return 0
}

main
