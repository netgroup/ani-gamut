#!/usr/bin/env bash
# ANI-Gamut SRv6 testbed -- provision a fresh Ubuntu 24.04 host (local VM) to run the lab.
# Containerlab containers share the HOST kernel, so SRv6/uSID must work on this host.
# Run as root:  sudo bash deploy/provision-vm.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo bash deploy/provision-vm.sh)"; exit 1; }
export DEBIAN_FRONTEND=noninteractive

echo "== apt packages =="
apt-get update
apt-get install -y docker.io git jq curl ca-certificates iproute2

echo "== yq (mikefarah v4 -- used by the Makefile 'deploy' target) =="
if ! yq --version 2>/dev/null | grep -qi mikefarah; then
  ARCH="$(dpkg --print-architecture)"   # amd64 / arm64
  curl -fsSL "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_${ARCH}" -o /usr/local/bin/yq
  chmod +x /usr/local/bin/yq
fi
yq --version

echo "== Containerlab =="
command -v containerlab >/dev/null || bash -c "$(curl -sL https://get.containerlab.dev)"
containerlab version || true

echo "== kernel modules (vrf, dummy) + persistence =="
modprobe vrf   || echo "WARN: modprobe vrf failed"
modprobe dummy || echo "WARN: modprobe dummy failed"
printf 'vrf\ndummy\n' > /etc/modules-load.d/srv6-testbed.conf

echo "== enable SRv6 seg6 on the host (persistent) =="
cat > /etc/sysctl.d/99-srv6-testbed.conf <<EOF
net.ipv6.conf.all.seg6_enabled = 1
net.ipv6.conf.default.seg6_enabled = 1
net.ipv6.conf.all.forwarding = 1
EOF
sysctl --system >/dev/null

echo "== docker: enable + add invoking user to the docker group =="
systemctl enable --now docker || true
[ -n "${SUDO_USER:-}" ] && usermod -aG docker "$SUDO_USER" && echo "added $SUDO_USER to docker group (re-login to apply)" || true

echo
echo "== DONE. Next: sudo bash deploy/preflight-srv6.sh  (must report PRE-FLIGHT OK) =="
