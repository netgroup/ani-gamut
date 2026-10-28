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
# -------------------------------------------------
# wait_iface.sh – reusable "wait for interface" helper
# -------------------------------------------------
# Usage:  wait_for_iface <iface> [<max_seconds>]
#   <iface>        - name of the interface to watch (e.g. eth1)
#   <max_seconds>  - optional timeout, default = 30 seconds
# -------------------------------------------------
wait_for_iface() {
    local iface=$1
    local timeout=${2:-30}   # default 30s if not supplied
    local elapsed=0

    while ! ip link show "$iface" >/dev/null 2>&1; do
        ((elapsed++))
        if (( elapsed > timeout )); then
            echo "ERROR: interface $iface never appeared after $timeout seconds"
            return 1
        fi
        sleep 1
    done

    # Interface is now present – return success
    return 0
}
