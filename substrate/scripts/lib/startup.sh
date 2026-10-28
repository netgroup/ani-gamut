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
# ------------------------------------------------------------
#  startup.sh – Detect the node type and source the appropriate
#			   configuration file.
#
#  Expected files (in the same directory as this script or in $LIBDIR):
#	  host.sh   – for nodes whose name starts with "hs"
#	  pe.sh   – for nodes whose name starts with "pe"
#	  igw.sh  – for nodes whose name starts with "igw"
#	  egw.sh  – for nodes whose name starts with "egw"
#
#  The script aborts with a clear message if:
#	 * hostname cannot be obtained,
#	 * the hostname does not match one of the allowed patterns,
#	 * the selected file does not exist or is not readable.
# ------------------------------------------------------------

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

readonly HS_PFX="hs"
readonly PE_PFX="pe"
readonly IGW_PFX="igw"
readonly EGW_PFX="egw"

# node := (hs|pe|igw|egw)<digits>
readonly NODE_REGEXPR="(${HS_PFX}|${PE_PFX}|${IGW_PFX}|${EGW_PFX})([0-9]+)"
# <node>-<node>
readonly LINK_REGEXPR="${NODE_REGEXPR}-${NODE_REGEXPR}"

# Variables that will be filled by extract_node_info()
NODE_TYPE=
NODE_NAME=
NODEID=

extract_node_info()
{
	local host

	# Get short hostname - silence any error messages.
	host=$(hostname -s 2>/dev/null) || :
	if [ -z "$host" ]; then
		printf 'extract_node_info: unable to obtain hostname\n' >&2
		return 1
	fi

	if [ $host == "master" ]; then
		echo "export NO_PROXY=\$(echo \$NO_PROXY | tr ',' '\n' | grep -v ':' | paste -sd \",\" -)" >> /root/.bashrc
		echo "export \"no_proxy=\$NO_PROXY\"">> /root/.bashrc
		echo "source /.venv/bin/activate" >> /root/.bashrc
		echo "cd /opt/clab/lib/agent_ai" >> /root/.bashrc
		echo "python3 planner_agent.py" >> /root/.bashrc
		return 1
	fi
	# Validate and capture the three groups.
	if [[ $host =~ ^${NODE_REGEXPR}$ ]]; then
		NODE_TYPE=${BASH_REMATCH[1]}
		NODEID=${BASH_REMATCH[2]}
		NODE_NAME="${host}"
		# Make them read‑only for the rest of the script.
		readonly NODE_TYPE NODEID NODE_NAME
		return 0
	else
		printf "extract_node_info: hostname '%s' is not of form hs<ID>, lf<ID> or sp<ID>\n" \
			   "$host" >&2
		return 1
	fi
}

# Main; call the function and source the right file
main()
{
	local path_profile_file
	local profile_file

	# Run the detection routine
	if ! extract_node_info; then
		# extract_node_info already printed a diagnostic, just exit.
		exit 0
	fi

	# Decide which profile file to source
	case "${NODE_NAME}" in
		${HS_PFX}*)   profile_file="host.sh"   ;;   # hsX
		${PE_PFX}*)   profile_file="pe.sh"   ;;   # peX
		${IGW_PFX}*)   profile_file="igw.sh"  ;;   # igwX
		${EGW_PFX}*)   profile_file="egw.sh"  ;;   # egwX
		*) printf "startup.sh: unknown node prefix in '%s'\n" "${NODE_NAME}" >&2
		   exit 1
	esac

	# Set the guard variable **before** sourcing files
	readonly __STARTUP_GUARD=1

	path_profile_file="${SCRIPT_DIR}/$profile_file"
	if [ -r "${path_profile_file}" ]; then
		source "${path_profile_file}"
	else
		printf "startup.sh: cannot find readable '%s'\n" \
			"$profile_file" >&2
		exit 1
	fi
}

# Entry point
main
