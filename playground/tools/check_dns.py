#!/usr/bin/env python3
"""Preflight DNS check -- abort a simulation early if the VM can't resolve the LLM API.

Network bouncing (train / hotspot WiFi that filters public :53) repeatedly leaves
the VM unable to resolve api.anthropic.com, which then kills every agent cell with
APIConnectionError after wasting minutes. Run this BEFORE any LLM-API simulation
(e.g. run_pilot); it exits non-zero with the exact fix steps if DNS is down, so the
campaign never starts blind.

    python3 tools/check_dns.py            # exit 0 if OK, 2 (with instructions) if not
    python3 tools/check_dns.py --host api.anthropic.com

Note: the oracle-only potency test and the fault-layer self-test do NOT need this
(no API), only runs that call the model do.
"""
import argparse
import socket
import subprocess
import sys


def resolves(host: str) -> bool:
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


def _current_resolver() -> str:
    try:
        out = subprocess.run(["resolvectl", "status", "eth0"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        if "Current DNS Server" in line:
            return line.split(":", 1)[-1].strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Preflight DNS check before an LLM-API run")
    ap.add_argument("--host", default="api.anthropic.com")
    a = ap.parse_args()

    if resolves(a.host):
        print(f"DNS OK: {a.host} resolves")
        return 0

    res = _current_resolver()
    print(f"DNS FAIL: cannot resolve {a.host} "
          f"(VM resolver: {res or 'unknown'}). Aborting before the run wastes API time.",
          file=sys.stderr)
    print("\nLikely the network bounced (train/hotspot WiFi filters public :53). Fix:",
          file=sys.stderr)
    print("  1) On Windows (PowerShell) find the resolver this network allows:", file=sys.stderr)
    print("       Get-DnsClientServerAddress -AddressFamily IPv4 | "
          "? ServerAddresses | ft InterfaceAlias,ServerAddresses", file=sys.stderr)
    print("     -> take the IP on the active adapter (usually the Wi-Fi row).", file=sys.stderr)
    print("  2) On the VM point eth0 at it and retry:", file=sys.stderr)
    print("       sudo resolvectl dns eth0 <THAT_IP> && sudo resolvectl flush-caches", file=sys.stderr)
    print("       getent hosts api.anthropic.com && echo 'DNS OK'", file=sys.stderr)
    print("  (back on the department network / tethering: 'sudo resolvectl revert eth0')",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
