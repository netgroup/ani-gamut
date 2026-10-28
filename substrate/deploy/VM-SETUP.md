# Running the ANI-Gamut SRv6 testbed on a local Ubuntu 24.04 VM

## 0. Create the VM
- Hypervisor: Hyper-V / VirtualBox / VMware on Windows.
- Image: **Ubuntu Server 24.04 LTS** (kernel 6.8 -> SRv6 + NEXT-CSID; matches the
  `ubuntu:24.04` node image).
- Resources: **4 vCPU, 16 GB RAM** (8 GB minimum), **40 GB disk**. Network: NAT or
  bridged (needs Internet for apt/Docker/Containerlab and the Google API for the agent).

## 1. Get the code
```bash
git clone <repo-url> 26-agai-srv6 && cd 26-agai-srv6 && git checkout cnsm-paper
# (or copy the folder from the Windows host: C:\GITs\26-agai-srv6)
```

## 2. Provision + PRE-FLIGHT (the critical gate)
```bash
sudo bash deploy/provision-vm.sh
sudo bash deploy/preflight-srv6.sh     # MUST print "PRE-FLIGHT OK" (NEXT-CSID supported)
# log out/in so the docker group applies, or keep using sudo for docker
```
If the pre-flight FAILS, the uSID plane will not work on this kernel -- stop and use a
newer kernel before deploying.

## 3. Build the image + deploy the lab
```bash
echo "API_TOKEN=<YOUR_GOOGLE_AI_TOKEN>" > .env     # the agent uses Google
make docker
sudo make deploy
```

## 4. Dynamic verification (the reason for the VM)
### 4a. boot-time uSID setup on a router
```bash
make connect NODE=pe6
  ip -6 addr show dev lo | grep 5f00        # expect loopback 5f00:0:6::1/128
  ip -6 route show | grep '5f00:0:6::/48'   # expect the uN: ... seg6local action End ... next-csid
  ip -6 route show | grep 5f00              # static route plane to other locators 5f00:0:N::/48 via fcf0:...
  exit
```
### 4b. create a tunnel via the agent
```bash
make connect NODE=master
  # at "SRv6 Planner Ready": ask to create a tunnel between hs1 and hs12
  exit
```
### 4c. End.DT4 uSID on the egress PE
```bash
make connect NODE=pe6
  ip -6 route show | grep f40c              # expect 5f00:0:6:f40c:: ... End.DT4 vrftable 112
  exit
```
### 4d. data-plane end-to-end (out-of-band -- authoritative)
```bash
make connect NODE=hs1
  ping -c3 10.0.12.1                         # hs12; succeeds AFTER the tunnel (failed before)
  exit
```

## 5. Teardown
```bash
sudo make destroy
```

## Known caveats to watch (expected, not regressions)
- **The agent's active validation is stale after re-addressing.**
  `scripts/lib/demone_router/validator_handler.py` has hardcoded old IPs/SIDs
  (`h1=10.0.1.1`, `h2=10.0.5.1`, `fcf0:2::5`, ...). With the new `5f00` plan its
  validation will not match and the agent may report failure/rollback even when the
  tunnel works. **Trust the out-of-band ping (4d), not the agent validator.**
  Parametrizing the validator is a known hardening item.
- **PE boot / POLICIES.** `scripts/lib/common.sh::load_pe_config` expects a `POLICIES`
  array in `<pe>.conf`, but the conf files are route CSVs. If a PE fails to boot:
  `make connect NODE=pe1` then `cat /var/log/output_router.log`. Clarify with Andrea
  (pre-existing, not introduced by the re-addressing).
- **uN warnings.** `router.sh` logs `WARN: uN install ... failed` if NEXT-CSID is
  unsupported -- exactly what the pre-flight (step 2) guards against.
