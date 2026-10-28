#!/usr/bin/env python3
"""Level-selector smoke test (NO LLM, NO MCP/agent).

Proves the A0 / A1 / A1+ ANI levels behave differently at the driver layer:

  - A0  : run_shell executes ANY command (no allowlist) — runs a command A1 blocks.
  - A1  : update_config enforces the Tier-1 allowlist (blocks non-allowlisted commands)
          and accepts the seg6 / seg6local provisioning commands.
  - A1+ : the Tier-2 anti-damage substrings are additionally in the blocked set.

Side-effect-light: it checks the allowlist predicate (no execution) and only runs the
harmless reads `true` / `ls /etc` via run_shell. Run ON THE VM (lab up); stdlib only.

    python3 tools/levels_smoketest.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ani"))
from drivers.linux_driver import LinuxDriver, TIER1_BLOCKED, TIER2_BLOCKED  # noqa: E402

LAB = "srv6-inest-demo-new"
LOG = Path("/tmp/levels_smoketest.jsonl")
NODE = "pe1"

a1 = LinuxDriver(LAB, LOG, block_tier2=False)   # A1  : Tier-1 only
a1p = LinuxDriver(LAB, LOG, block_tier2=True)   # A1+ : Tier-1 + Tier-2


def main() -> int:
    seg6 = "ip route add table 101 10.0.12.1/32 encap seg6 mode encap segs 5f00:0:6:f40c:: dev pe1-igw8"
    seg6local = "ip -6 route add 5f00:0:6:f40c::/128 encap seg6local action End.DT4 vrftable 112 dev vrf112"
    nonwl = "ls /etc"   # not in the allowlist

    print("== A1 allowlist predicate (no execution) ==")
    print("  seg6 encap allowed     :", a1._is_allowed_command(seg6))
    print("  seg6local decap allowed:", a1._is_allowed_command(seg6local))
    print("  'ls /etc' allowed      :", a1._is_allowed_command(nonwl))

    print("\n== A0 run_shell runs what A1 blocks (no allowlist) ==")
    r_a0 = a1.run_shell(NODE, nonwl)["results"][0]
    print(f"  A0 run_shell('{nonwl}')    -> status={r_a0['status']}  out[:40]={r_a0['output'][:40]!r}")
    r_a1 = a1.update_config(NODE, [nonwl])["results"][0]
    print(f"  A1 update_config('{nonwl}') -> status={r_a1['status']}")

    print("\n== Tier-1 (A1) vs Tier-1+Tier-2 (A1+) ==")
    print(f"  A1  blocks {len(a1._blocked_for_config())} substrings (Tier-1 only)")
    print(f"  A1+ blocks {len(a1p._blocked_for_config())} substrings (Tier-1 + Tier-2)")
    print(f"  Tier-2 (active only in A1+): {TIER2_BLOCKED}")

    ok = (
        a1._is_allowed_command(seg6)
        and a1._is_allowed_command(seg6local)
        and not a1._is_allowed_command(nonwl)
        and a1.run_shell(NODE, "true")["results"][0]["status"] == "success"
        and a1.update_config(NODE, [nonwl])["results"][0]["status"] == "blocked"
        and set(a1._blocked_for_config()) == set(TIER1_BLOCKED)
        and set(a1p._blocked_for_config()) == set(TIER1_BLOCKED) | set(TIER2_BLOCKED)
    )
    print("\n==== VERDICT:", "PASS" if ok else "CHECK OUTPUT", "====")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
