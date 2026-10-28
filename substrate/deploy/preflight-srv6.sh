#!/usr/bin/env bash
# Verify the HOST kernel + iproute2 actually support SRv6 seg6 and NEXT-CSID (uN),
# which the testbed micro-SID plan requires. Run as root.  sudo bash deploy/preflight-srv6.sh
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)"; exit 1; }
fail=0
echo "kernel:   $(uname -r)"
echo "iproute2: $(ip -V 2>/dev/null)"

if sysctl net.ipv6.conf.all.seg6_enabled >/dev/null 2>&1; then
  echo "[ok]   seg6 sysctl present"
else
  echo "[FAIL] seg6 not available in this kernel"; fail=1
fi

# Authoritative NEXT-CSID test: actually install a uN (End, next-csid flavor) on a temp dummy.
ip link add usidtest type dummy 2>/dev/null || true
ip link set usidtest up 2>/dev/null || true
if ip -6 route add fcff:9999::/48 encap seg6local action End flavors next-csid lblen 32 nflen 16 dev usidtest 2>/tmp/usid.err; then
  echo "[ok]   NEXT-CSID uN (End flavors next-csid) SUPPORTED"
  ip -6 route del fcff:9999::/48 2>/dev/null || true
else
  echo "[FAIL] NEXT-CSID NOT supported:"; sed 's/^/       /' /tmp/usid.err; fail=1
fi
ip link del usidtest 2>/dev/null || true

# End.DT4 sanity (warn only: vrftable lookup is at packet time)
ip link add dt4test type dummy 2>/dev/null || true; ip link set dt4test up 2>/dev/null || true
if ip -6 route add fcff:9998::1 encap seg6local action End.DT4 vrftable 1 dev dt4test 2>/tmp/dt4.err; then
  echo "[ok]   End.DT4 behavior supported"; ip -6 route del fcff:9998::1 2>/dev/null || true
else
  echo "[warn] End.DT4 add failed (often just needs a real VRF table):"; sed 's/^/       /' /tmp/dt4.err
fi
ip link del dt4test 2>/dev/null || true

echo
if [ "$fail" -eq 0 ]; then echo "PRE-FLIGHT OK -- this kernel can run the testbed SRv6/uSID plane"
else echo "PRE-FLIGHT FAILED -- this kernel cannot run the uSID plane (need a newer kernel / iproute2)"; exit 1; fi
