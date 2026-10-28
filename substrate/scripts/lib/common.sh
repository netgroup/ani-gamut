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

declare -A GLOBAL_POLICIES=()

# load_node_config
#
# Loads the node‑specific configuration file based on the
# machine's hostname.
#
# The function aborts (exit 1) if any required variable is
# missing, if POLICIES is empty, or if the per‑host file is
# not readable.
load_host_config()
{
	local required_vars=(POLICIES)
	local hostname
	local k

	# Resolve the short hostname
	if ! hostname="$(hostname -s 2>/dev/null)"; then
		echo "ERROR: Cannot determine hostname." >&2
		exit 1
	fi


	# global
	LOCAL_IPV4_NET="10.0.${NODEID}"
	LOCAL_IPV4_PFX="24"
	readonly LOCAL_IPV4_NET LOCAL_IPV4_PFX

}

load_pe_config()
{
	local required_vars=(POLICIES)
	local conf_file
	local hostname
	local k

	# Resolve the short hostname
	if ! hostname="$(hostname -s 2>/dev/null)"; then
		echo "ERROR: Cannot determine hostname." >&2
		exit 1
	fi

	# Build the expected config file path
	conf_file="${CONFIG_DIR}/${hostname}.conf"
	# Verify that the file exists and is readable
	if [[ ! -r "$conf_file" ]]; then
		echo "ERROR: Configuration file '$conf_file' not found or not readable." >&2
		exit 1
	fi

	# Source the file - it must export the variables it sets
	source "$conf_file"

	# Validate that required variables are present
	for var in "${required_vars[@]}"; do
		case "$var" in
		POLICIES)
			# Ensure the associative array is defined and not empty
			if [[ ${#POLICIES[@]} -eq 0 ]]; then
				echo "ERROR: Required associative array POLICIES is empty in $conf_file." >&2
				exit 1
			fi

			# XXX: POLICIES has been defined with 'declared'
			# meaning that it is sourced *but* became
			# local to this function.  We need to copy the content
			# of POLICIES in GLOBAL_POLICIES.
			for k in "${!POLICIES[@]}"; do
				GLOBAL_POLICIES["$k"]="${POLICIES["$k"]}"
			done
		;;
		*)
			# For scalar values simply check non‑empty
			if [[ -z "${!var:-}" ]]; then
				echo "ERROR: Required variable '$var' is missing in $conf_file." >&2
				exit 1
			fi
			;;
		esac

	# global
	LOCAL_IPV4_NET="10.0.${NODEID}"
	LOCAL_IPV4_PFX="24"
	readonly GLOBAL_POLICIES LOCAL_IPV4_NET LOCAL_IPV4_PFX

	done
}

load_node_config()
{
	# Make sure NODE_TYPE exists before we inspect it
	if [[ -z ${NODE_TYPE+x} ]]; then
		printf 'load_node_config: NODE_TYPE is not set\n' >&2
		exit 1
	fi

	case "$NODE_TYPE" in
		hs)
			load_host_config
			;;
		pe)
			load_pe_config
			;;
		igw|egw)
			# No action required for the "lf" type
			;;
		*)
			printf "load_node_config: unknown NODE_TYPE '%s' (expected 'hs' or 'lf')\n" \
				   "$NODE_TYPE" >&2
			exit 2
			;;
	esac
}
load_node_config

declare -a NEIGH_NODES
# Scan interfaces that match  <string><num>-(<string><num>)
# and store the text inside the parentheses in the global array NEIGH_NODES.
find_neigh_nodes()
{
	local neigh_name

	# for each interface
	for iface_path in /sys/class/net/*; do
		# strip the path
		iface=${iface_path##*/}

		if [[ $iface =~ ^${LINK_REGEXPR}$ ]]; then
			neigh_name="${BASH_REMATCH[3]}${BASH_REMATCH[4]}"
			NEIGH_NODES+=("${neigh_name}")
		fi
	done

	readonly NEIGH_NODES
}
find_neigh_nodes

extract_nodeid()
{
	local name="${1}"

	if [[ -z $name ]]; then
		printf 'extract_id: error – argument is empty\n' >&2
		exit 1
	fi

	if [[ $name =~ ^${NODE_REGEXPR}$ ]]; then
		printf '%s' "${BASH_REMATCH[2]}"
		return 0
	else
		printf 'extract_id: error – "%s" is not a valid node name\n' "$name" >&2
		exit 1
	fi
}

get_ipv6_net_from_iface()
{
	local iface="${1}"
	local id1 id2 tmp

	# Extract the IDs from interface names,
	#   e.g.: hs1-lf5 => id1=1, id2=5
	if [[ "${iface}" =~ ^${LINK_REGEXPR}$ ]]; then
		id1=${BASH_REMATCH[2]}
		id2=${BASH_REMATCH[4]}
	else
		echo "Invalid interface: ${iface}" >&2
		return 1
	fi

	# Ensure numeric comparison - use (( )) which treats the operands as
	# integers.
	if (( id1 > id2 )); then
		tmp=$id1
		id1=$id2
		id2=$tmp
	fi

	printf 'fdf0:0:%s:%s\n' "${id1}" "${id2}"
}

declare -A IF_IPV6_NET
build_if_ipv6_net()
{
	local neigh_node
	local key

	for neigh_node in "${NEIGH_NODES[@]}"; do
		key="${NODE_NAME}-${neigh_node}"

		IF_IPV6_NET["$key"]=$(get_ipv6_net_from_iface "$key")
	done

	readonly IF_IPV6_NET
}
build_if_ipv6_net
readonly IPV6_NET_PREFIX=64

check_ifaces_ready()
{
	local iface

	for iface in "${!IF_IPV6_NET[@]}"; do
		wait_for_iface "$iface" || { echo "host1: $iface missing"; exit 1; }
	done
}

readonly CSID_BLOCK_NET="fcbb"
readonly CSID_BLOCK_LEN="16"
readonly CSID_NODE_LEN="16"
readonly CSID_BLOCK_NODE_LEN="$((CSID_BLOCK_LEN + CSID_NODE_LEN))"
csid_block_node_prefix()
{
	printf "${CSID_BLOCK_NET}:%s::/${CSID_BLOCK_NODE_LEN}" "$1"
}

configure_ifaces()
{
	local iface addr

	for iface in "${!IF_IPV6_NET[@]}"; do
		addr="${IF_IPV6_NET[$iface]}::${NODEID}/${IPV6_NET_PREFIX}"

		ip -6 addr add "$addr" dev "$iface" 2>/dev/null || true
		ip link set dev "$iface" mtu 9000 up
	done
}
configure_ifaces

# hex0nab_from_dec
#   Convert a decimal integer to a 4-digit hexadecimal string that follows the
#   "0NAB" rule.  N must be representable with at most 3 hex digits (decimal
#   value <= 4095).  If it is larger the function prints an error message to
#   stderr and returns a non-zero status.
#   Output format (always 4 hex digits, first nibble = 0):
#	   1-digit N  -> 0N00
#	   2-digit N  -> 0NN0
#	   3-digit N  -> 0NNN
#   The result is printed in uppercase.
hex0nab_from_dec() {
	local hex_n len result
	local dec_input="${1}"

	# Validate argument - it must be a non-negative decimal integer
	if [[ ! "${dec_input}" =~ ^[0-9]+$ ]]; then
		echo "hex0nab_from_dec: argument must be a decimal integer" >&2
		return 1
	fi

	# Convert decimal -> uppercase hex string
	hex_n=$(printf '%X' "${dec_input}")   # e.g. 2748 -> "AB4"

	# If the hex representation needs more than 3 digits -> error
	if (( ${#hex_n} > 3 )); then
		echo "hex0nab_from_dec: value ${dec_input} (0x${hex_n}) exceeds 3 hex digits (max 0xFFF)" >&2
		return 2
	fi

	# Length of the hex representation (1 to 3)
	len=${#hex_n}

	# Build the 4-digit result (MS nibble forced to 0)
	case "${len}" in
		1) result="0${hex_n}00" ;;   # N occupies only the second nibble
		2) result="0${hex_n}0"  ;;   # N occupies nibble 2-3, B = 0
		3) result="0${hex_n}"   ;;   # N occupies nibble 2-4
		*) result="0000"	;;   # should never be reached
	esac

	# Guarantee exactly 4 hex digits (pad with leading zeros if needed)
	result=$(printf '%04X' "$((16#${result}))")

	printf '%s\n' "${result}"
}

# Convert a numeric node/neighbor ID to a 16‑bit USID (4‑digit hex,
# zero‑padded)
build_usid()
{
	hex0nab_from_dec "$1"
}

add_usid_reachability_routes()
{
	local nb key net nxt addr neigh_node

	for neigh_node in "${NEIGH_NODES[@]}"; do
		nb=$(extract_nodeid "${neigh_node}")
		usid=$(build_usid "$nb")
		addr="$(csid_block_node_prefix "${usid}")"

		# build the key, get the network part, then add the host part
		# (the neighbour ID)
		key="${NODE_NAME}-${neigh_node}"
		net=$(get_ipv6_net_from_iface "$key")	  # e.g. fdf0:0:1:3
		nxt="${net}::${nb}"			  # e.g. fdf0:0:1:3::3

		ip -6 route add "$addr" via "$nxt"
	done

	# if we don't know where to go, make the destination unreachable for
	# the whole locator block.
	ip -6 route add unreachable \
		"${CSID_BLOCK_NET}::/${CSID_BLOCK_LEN}" metric 4278198272
}
add_usid_reachability_routes

readonly CSID_NODE="$(build_usid "${NODEID}")"
readonly DECAP_FUNC="00d4"

sysctl_config()
{
	sysctl -wq net.ipv4.conf.all.rp_filter=0
	sysctl -wq net.ipv4.conf.default.rp_filter=0
	sysctl -wq net.ipv4.ip_forward=1
	sysctl -wq net.ipv6.conf.all.forwarding=1

	# from now on, rp_filter will be disabled for new interfaces.
}
sysctl_config

readonly DUMMY_NAME="dum0"
create_dum0()
{
	if lsmod | grep -qw dummy; then
		echo "ERROR: dummy kernel module not loaded.  Try 'modprobe dummy' as root."
		exit 1
	fi

	ip link add name "${DUMMY_NAME}" type dummy
	ip link set dev "${DUMMY_NAME}" up
}
