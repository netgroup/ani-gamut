#!/usr/bin/env python3
"""A1-adapter smoke test (NO LLM, NO MCP/agent).

Proves that NetAiBench's LinuxDriver can drive the SRv6 substrate: it provisions an
L3VPN tunnel hs1<->hs12 on the *live* containerlab lab using only the public driver
API, then tears it down via the rollback engine.

Exercises, on the real nodes:
  - get_running_config / execute_validation            (read path)
  - the command allowlist                              (seg6 / seg6local pass via the
                                                        generic `ip route add` prefixes)
  - update_config                                      (exec path)
  - capture_rollback_state / restore_rollback_state    (snapshot + delta rollback)

This is the "A1 on the SRv6 domain" claim of the Phase-0 design, validated with zero
LLM dependency. The agentic A0/A1 run (LLM via model_registry) is a separate step.

Run ON THE VM (same host as docker + the clab lab). Stdlib only; needs python3 + docker.
The lab must be up (`sudo make deploy` in 26-agai-srv6). The SRv6 daemons are NOT used:
we provision via the driver, exactly as the A1 agent would.

    python3 tools/srv6_a1_smoketest.py

Addressing (F3216/uSID, see srv6-addressing-plan-F3216.md):
  hs1  = 10.0.1.1  in vrf101 on pe1     End.DT4 uSID of hs1  = 5f00:0:1:f401::
  hs12 = 10.0.12.1 in vrf112 on pe6     End.DT4 uSID of hs12 = 5f00:0:6:f40c::
"""
import re
import sys
from pathlib import Path

# import NetAiBench's real driver (stdlib-only; no pip deps)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ani"))
from drivers.linux_driver import LinuxDriver  # noqa: E402

LAB = "srv6-inest-demo-new"
LOG = Path("/tmp/srv6_a1_smoketest_commands.jsonl")
d = LinuxDriver(lab_name=LAB, log_file=LOG)


def egress_dev(node: str, locator: str) -> str:
    """Read the egress interface toward a /48 locator from the live route plane."""
    out = d.execute_validation(node, f"ip -6 route show {locator}")["output"]
    m = re.search(r"dev (\S+)", out)
    if not m:
        sys.exit(f"FATAL: no route to {locator} on {node}:\n{out}")
    return m.group(1)


def ping_ok(host: str, dst: str) -> tuple[bool, str]:
    out = d.execute_validation(host, f"ping -c3 -W2 {dst}")["output"]
    # NB: "0% packet loss" is also a substring of "100% packet loss"; require a word
    # boundary so only a genuine 0% (full reachability) counts as success.
    return (re.search(r"\b0% packet loss", out) is not None), out


def apply(label: str, steps: list[tuple[str, str]]) -> None:
    print(f"\n== {label} ==")
    for node, cmd in steps:
        res = d.update_config(node, [cmd])["results"][0]
        flag = "  !! ALLOWLIST BLOCK" if res["status"] == "blocked" else ""
        print(f"  [{node}] {res['status']}: {cmd}{flag}")


def main() -> int:
    # egress interfaces, derived from the live route plane (robust to shortest-path)
    pe1_out = egress_dev("pe1", "5f00:0:6::/48")   # pe1 -> pe6 locator
    pe6_out = egress_dev("pe6", "5f00:0:1::/48")   # pe6 -> pe1 locator
    print(f"egress: pe1->{pe1_out}  pe6->{pe6_out}")

    fwd = [  # hs1 -> hs12
        ("pe1", f"ip route add table 101 10.0.12.1/32 encap seg6 mode encap segs 5f00:0:6:f40c:: dev {pe1_out}"),
        ("pe6", "ip -6 route add 5f00:0:6:f40c::/128 encap seg6local action End.DT4 vrftable 112 dev vrf112"),
    ]
    rev = [  # hs12 -> hs1
        ("pe6", f"ip route add table 112 10.0.1.1/32 encap seg6 mode encap segs 5f00:0:1:f401:: dev {pe6_out}"),
        ("pe1", "ip -6 route add 5f00:0:1:f401::/128 encap seg6local action End.DT4 vrftable 101 dev vrf101"),
    ]
    cleanup = [  # best-effort teardown (re-runnable; covers VRF-table routes the snapshot misses)
        ("pe1", "ip route del table 101 10.0.12.1/32"),
        ("pe6", "ip -6 route del 5f00:0:6:f40c::/128"),
        ("pe6", "ip route del table 112 10.0.1.1/32"),
        ("pe1", "ip -6 route del 5f00:0:1:f401::/128"),
    ]

    print("\n== read path: get_running_config(pe6) (first lines) ==")
    print("\n".join(d.get_running_config("pe6")["running_config"].splitlines()[:8]))

    # clean slate so the test is re-runnable regardless of prior provisioning
    for node, cmd in cleanup:
        d.update_config(node, [cmd])

    before_ok, _ = ping_ok("hs1", "10.0.12.1")
    print(f"\nping hs1->10.0.12.1 BEFORE provisioning: {'REACHABLE' if before_ok else 'unreachable (expected)'}")

    # snapshot the two PEs for rollback
    snaps = {n: d.capture_rollback_state(n) for n in ("pe1", "pe6")}

    apply("provision forward (hs1->hs12)", fwd)
    apply("provision reverse (hs12->hs1)", rev)

    after_ok, after_out = ping_ok("hs1", "10.0.12.1")
    print(f"\nping hs1->10.0.12.1 AFTER provisioning: {'REACHABLE' if after_ok else 'UNREACHABLE'}")
    print("  " + "\n  ".join(after_out.splitlines()[-3:]))

    print("\n== rollback via the driver (delta restore of pe1, pe6) ==")
    for n in ("pe1", "pe6"):
        rr = d.restore_rollback_state(n, snaps[n])
        print(f"  {n}: {rr['status']} ({len(rr.get('steps', []))} steps, {len(rr.get('skipped', []))} skipped)")
    # snapshot does not capture VRF-table routes -> explicit teardown of the encap legs
    for node, cmd in cleanup:
        d.update_config(node, [cmd])

    post_ok, _ = ping_ok("hs1", "10.0.12.1")
    print(f"ping hs1->10.0.12.1 AFTER rollback: {'still reachable (!)' if post_ok else 'unreachable (expected)'}")

    ok = after_ok and not post_ok
    print("\n==== VERDICT:", "PASS" if ok else "CHECK OUTPUT", "====")
    print("  provisioned-then-reachable:", after_ok)
    print("  rolled-back-then-unreachable:", not post_ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
