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

# --------------------------------------------------------------
# Fail fast, fail loudly – abort on any error or undefined variable
# --------------------------------------------------------------
set -euox pipefail

# ------------------------------------------------------------
# Guard - abort if the file is executed directly or sourced
# without the startup sentinel.
# ------------------------------------------------------------
#
# The single line below does all the work:
#
#   : "${__STARTUP_GUARD:?Error: This file must be sourced via startup.sh}"
#
# * `:` is the POSIX no‑op builtin - it does nothing except evaluate
#   its arguments.
#
# * `${var:?msg}` is a parameter‑expansion form that expands to the value
#   of *var* **only if** the variable is set and not null.
#   If the variable is unset or null the shell prints *msg* to
#   standard error and exits with status 1.
#
# * `__STARTUP_GUARD` is a readonly variable that **startup.sh** creates
#   *just before* it sources this file.  Because it is readonly the
#   profile cannot unset or change it.
#
# Result:
#   - When the file is sourced via startup.sh the guard variable exists,
#     the expansion succeeds and the script continues.
#   - When the file is run directly (e.g. `./host.sh`) or sourced
#     without startup.sh, the variable is missing, Bash prints the error
#     message and aborts.
#
# ------------------------------------------------------------
: "${__STARTUP_GUARD:?Error: This file must be sourced via startup.sh}"

readonly COMMON_LIB="${SCRIPT_DIR}/common.sh"
readonly CONFIG_DIR="${SCRIPT_DIR}/configs"

# source common library. It takes care of setting up global variables used by
# the script as well as configuring the backbone networking, addresses, etc.
source "${COMMON_LIB}" || { echo "Cannot source common library"; exit 1; }

# Verify that the VRF kernel module is available
if [ ! -d "/sys/module/vrf" ];  then
	echo "ERROR: VRF kernel module not loaded.  Try 'modprobe vrf' as root."
	exit 1
fi

readonly VRF_TABLE=100
readonly VRF_NAME="vrf${VRF_TABLE}"

sysctl -wq net.vrf.strict_mode=1

# VRF used for SRv6 End.DT4 (decap)
ip link add name "${VRF_NAME}" type vrf table "${VRF_TABLE}"
ip link set dev "${VRF_NAME}" up

# Bridge br0 local to this host. VMs/Containers can be attached to this bridge
# in order to communicate with remote VMs/Containers using SRv6 (remote machine
# belong to another IPv4 network).
ip link add name br0 type bridge
ip link set dev br0 up

# ATM, NOT USED IN FAVOR OF VRF IPV6 LOOPBACK ADDRESS
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Create dummy interface for the SRv6 H.Encap Reduced; we need just a device as
# placeholder :-) and we can't use the VRF unless we assign it an IPv6 address
# (used by the tunnel as src tunnel address).
#
# create_dum0

# VRF‑bridge veth pair
#  *) veth-"${VRF_NAME}"  -> attached to VRF, e.g., 10.0.1.2/24
#  *) veth-br0		  -> attached to br0, no IP
# -------------------------------------------------
readonly LOCAL_IPV4_NH_ENCAP="${LOCAL_IPV4_NET}.2"

ip link add veth-br0 type veth peer name veth-"${VRF_NAME}"
ip link set veth-br0 master br0
ip link set veth-"${VRF_NAME}" master "${VRF_NAME}"

ip addr add "${LOCAL_IPV4_NH_ENCAP}/${LOCAL_IPV4_PFX}" dev veth-"${VRF_NAME}"

ip link set dev veth-br0 up
ip link set dev veth-"${VRF_NAME}" up

# IPv6 "loopback address" for the VRF. This is needed if we don't want to use a
# random? dev in the SRv6 encap rule and don't want to use a dummy interface
# (in the default VRF).
# The address is needed otherwise the SRv6 tunnel won't have a good IPv6
# address to use in the tunnel 'src'.
#
# Note that you can use the 'ip sr' command to assign a tunnel src address for
# the whole netns (used for any SRv6 encap).
# ip addr add "fdf0:${NODEID}::2/128" dev "${VRF_NAME}"

# Assign IPv4 address to the local bridge. This bridge enables connectivity
# between VMs/Containers running locally on this machine. Using this bridge we
# can also reach different IPv4 networks on remote hosts through SRv6 tunnels.

#ip addr add "${LOCAL_IPV4_NET}.1/${LOCAL_IPV4_PFX}" dev br0
find_interface_pe(){
	for iface in $(ip -o link show | awk -F': ' '{print $2}'); do
	    if [[ $iface =~ ^hs[0-9]+-pe[0-9]+@if[0-9]+$ ]]; then
		IFS='@'
		read -ra iface <<< "$iface"
		NET_IFACE="$iface"
		break
	    fi
	done
}

#Trovo l'interfaccia su cui sta il mio router
find_interface_pe 
#su quell'interfaccia io mi prendo il .1 e lui si deve prendere il .254
ip addr	add "${LOCAL_IPV4_NET}.1/${LOCAL_IPV4_PFX}" dev ${NET_IFACE}
ip link set ${NET_IFACE} up

#tutto  il traffico passa per la {pericolo}
ip route del default
ip route add default via "${LOCAL_IPV4_NET}.254"

#ip route add "10.0.0.0/16" via "${LOCAL_IPV4_NET}.2" dev $NET_IFACE

# SRv6 uSID encapsulation (inside the VRF)
# add_policy_seg6_routes

# SRv6 tunnel termination (using the VRF). Note that we could have put decap
# routes on a separate table, but we leave them on the main for the sake of
# simplicity.
# seg6_decap_route

# Change priority of l3mdev-table lookup rule in the Policy-Routing.
# This is a way to "leak" (through the veth-pairs) routes from the specific VRF
# to the default VRF and vice-versa.
#fixup_policy_routing
