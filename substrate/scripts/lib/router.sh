#!/usr/bin/env bash

# SRv6 Data Center Network Simulation
# Copyright (C) 2026 Andrea Mayer
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# See <https://www.gnu.org/licenses/gpl-3.0.html>

# Fail fast, fail loudly -- abort on any error or undefined variable
set -euox pipefail

# Guard: abort if executed directly or sourced without the startup sentinel.
: "${__STARTUP_GUARD:?Error: This file must be sourced via startup.sh}"

readonly COMMON_LIB="${SCRIPT_DIR}/common.sh"
readonly CONFIG_DIR="${SCRIPT_DIR}/configs"

# source common library: sets global variables and configures backbone/addresses.
source "${COMMON_LIB}" || { echo "Cannot source common library"; exit 1; }

add_ipv6_routes() {
    local file="${CONFIG_DIR}/${NODE_NAME}.conf"

    if [[ ! -f "$file" ]]; then
        echo "File non trovato: $file"
        return 1
    fi

    while IFS=',' read -r prefix nexthop dev; do
        # Salta righe vuote o commenti
        [[ -z "$prefix" || "$prefix" =~ ^# ]] && continue
        ip -6 route add "$prefix" via "$nexthop" dev "$dev"
    done < "$file"
}

# Verify that the VRF kernel module is available
if [ ! -d "/sys/module/vrf" ]; then
    echo "ERROR: VRF kernel module not loaded.  Try 'modprobe vrf' as root."
    exit 1
fi

readonly VRF_TABLE=100
readonly VRF_NAME="vrf${VRF_TABLE}"

config_interface_to_host(){
    ip addr add "10.0.${HS_ID}.254/24" dev $NET_IFACE
    ip link set ${NET_IFACE} up
}

PRF_ADDR_IPV6="fcf0:0"
config_interface_to_router(){
    if [ "$NODEID" -lt "$R_ID" ]; then
        MIN_ID=$NODEID
        MAX_ID=$R_ID
    else
        MIN_ID=$R_ID
        MAX_ID=$NODEID
    fi
    address_node="${PRF_ADDR_IPV6}:${MIN_ID}:${MAX_ID}::${NODEID}"
    address_nb="${PRF_ADDR_IPV6}:${MIN_ID}:${MAX_ID}::${R_ID}"
    ip -6 addr add "${address_node}/64" dev ${NET_IFACE}
    ip link set ${NET_IFACE} up
}

create_vrf() {
    local num="$1"
    local iface="$2"

    if [[ -z "$num" || -z "$iface" ]]; then
        echo "Uso: create_vrf <numero> <interfaccia>"
        return 1
    fi

    local vrf_name="vrf$((100 + num))"
    local table_id="$((100 + num))"

    ip link add "$vrf_name" type vrf table "$table_id"
    ip link set dev "$vrf_name" up
    ip link set dev "$iface" master "$vrf_name"
    sysctl -q -w net.vrf.strict_mode=1   # abilito la strict mode
}

ip -6 route del default
ip route del default

find_interface_pe(){
    # per ogni interfaccia vedo se e' la mia con quella di un host o di un altro router
    for iface in $(ip -o link show | awk -F': ' '{print $2}'); do
        if [[ $iface =~ ^${NODE_NAME}-hs[0-9]+@if[0-9]+$ ]]; then
            IFS='@'
            read -ra iface <<< "$iface"
            NET_IFACE="$iface"
            HS_ID=$(echo "$NET_IFACE" | sed -E 's/.*-hs([0-9]+).*/\1/')
            config_interface_to_host
            if="${iface%@*}"
            create_vrf ${HS_ID} ${if}
        fi
        if [[ $iface =~ ^${NODE_NAME}-pe[0-9]+@if[0-9]+$ ]]; then
            IFS='@'
            read -ra iface <<< "$iface"
            NET_IFACE="$iface"
            R_ID=$(echo "$NET_IFACE" | sed -E 's/.*-pe([0-9]+).*/\1/')
            config_interface_to_router
        fi
        if [[ $iface =~ ^${NODE_NAME}-igw[0-9]+@if[0-9]+$ ]]; then
            IFS='@'
            read -ra iface <<< "$iface"
            NET_IFACE="$iface"
            R_ID=$(echo "$NET_IFACE" | sed -E 's/.*-igw([0-9]+).*/\1/')
            config_interface_to_router
        fi
        if [[ $iface =~ ^${NODE_NAME}-egw[0-9]+@if[0-9]+$ ]]; then
            IFS='@'
            read -ra iface <<< "$iface"
            NET_IFACE="$iface"
            R_ID=$(echo "$NET_IFACE" | sed -E 's/.*-egw([0-9]+).*/\1/')
            config_interface_to_router
        fi
    done
}
find_interface_pe
add_ipv6_routes

# --- F3216 / NEXT-CSID micro-SID node setup (see srv6-addressing-plan-F3216.md) ---
# Each router is a uSID node: it owns the locator 5f00:0:<hex id>::/48 and installs a
# uN behaviour (End, next-csid flavor, F3216 lblen 32 / nflen 16). Locator and uN live
# on a dedicated dummy device, NOT on lo: on lo the kernel accepts the route (rc=0) but
# silently drops the seg6local lwtunnel, so the uN never attaches (verified on
# kernel 6.8 / iproute2 6.1.0). Per-VPN End.DT4 SIDs (5f00:0:<id>:f4<host>::) are
# installed per-tunnel by the daemon on the VRF device.
HEXID="$(printf '%x' "$NODEID")"
readonly USID_DEV="usid0"
sysctl -wq net.ipv6.conf.all.seg6_enabled=1 || echo "WARN: seg6_enabled failed" >&2
ip link add "${USID_DEV}" type dummy 2>/dev/null || true
ip link set "${USID_DEV}" up
ip -6 addr add "5f00:0:${HEXID}::1/128" dev "${USID_DEV}" 2>/dev/null \
    || echo "WARN: locator 5f00:0:${HEXID}::1 add failed" >&2
ip -6 route replace "5f00:0:${HEXID}::/48" \
    encap seg6local action End flavors next-csid lblen 32 nflen 16 dev "${USID_DEV}" \
    || echo "WARN: uN install for 5f00:0:${HEXID}::/48 failed" >&2

source /.venv/bin/activate
nohup python3 -u /opt/clab/lib/demone_router/main.py > /var/log/output_router.log 2>&1 &
