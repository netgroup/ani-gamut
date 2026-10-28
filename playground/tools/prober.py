#!/usr/bin/env python3
"""In-container batch ICMP reachability prober for the ANI-Gamut oracle.

Runs as ONE process inside the host-aggregator container. For each source host it switches
into that host's network namespace (setns, via ctypes -> no extra deps), opens a raw ICMP
socket, fires an echo to every target of that source, and collects replies with a bounded
deadline. Replaces the per-check `docker exec ... ping` storm: no process-per-check, no ARP
hang (we never block on send; the recv has a deadline we control), no orphan pings, no CPU
meltdown, and FULL O(k^2) coverage (no sampling needed).

  input  : argv[1] = JSON list of checks  [{"i": <int>, "src": "h<N>", "dst": "<ip>"}]
  output : stdout  = JSON map  {"<i>": <reachable bool>}

Run as root (docker exec -u 0) so SOCK_RAW is allowed. Source netns must exist as
/var/run/netns/h<N> (created by scripts/lib/hosts_aggregator.sh)."""
import ctypes
import json
import os
import select
import socket
import struct
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

CLONE_NEWNET = 0x40000000
_libc = ctypes.CDLL("libc.so.6", use_errno=True)


def _setns(netns: str) -> None:
    fd = os.open(f"/var/run/netns/{netns}", os.O_RDONLY)
    try:
        if _libc.setns(fd, CLONE_NEWNET) != 0:
            e = ctypes.get_errno()
            raise OSError(e, os.strerror(e), netns)
    finally:
        os.close(fd)


def _checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return (~s) & 0xFFFF


def _echo(ident: int, seq: int) -> bytes:
    payload = b"ani-gamut-probe!"
    head = struct.pack("!BBHHH", 8, 0, 0, ident, seq)
    chk = _checksum(head + payload)
    return struct.pack("!BBHHH", 8, 0, chk, ident, seq) + payload


def _probe_one(src: str, targets: list, deadline: float = 2.5) -> dict:
    """targets = [(i, dst_ip), ...] -> {i: reachable bool}. setns is per-thread on Linux.
    Sends TWO echoes per target (different seq, same i) so a single lost packet does not
    produce a false 'unreachable'."""
    res = {i: False for i, _ in targets}
    try:
        _setns(src)
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except OSError:
        return res
    s.setblocking(False)
    ident = (os.getpid() ^ (hash(src) & 0xFFFF)) & 0xFFFF
    seq2i = {}
    n = len(targets)
    for rep in range(2):
        for k, (i, dst) in enumerate(targets):
            seq = (rep * n + k) & 0xFFFF
            seq2i[seq] = i
            try:
                s.sendto(_echo(ident, seq), (dst, 0))
            except OSError:
                pass
    end = time.time() + deadline
    while time.time() < end and not all(res.values()):
        r, _, _ = select.select([s], [], [], max(0.0, end - time.time()))
        if not r:
            break
        try:
            pkt, _ = s.recvfrom(4096)
        except OSError:
            continue
        if len(pkt) < 28:
            continue
        ihl = (pkt[0] & 0x0F) * 4
        icmp = pkt[ihl:]
        if len(icmp) < 8:
            continue
        typ, _code, _chk, rid, rseq = struct.unpack("!BBHHH", icmp[:8])
        if typ == 0 and rid == ident and rseq in seq2i:
            res[seq2i[rseq]] = True
    s.close()
    return res


def main() -> int:
    checks = json.load(open(sys.argv[1]))
    by_src = defaultdict(list)
    for c in checks:
        by_src[c["src"]].append((c["i"], c["dst"]))
    out = {}
    with ThreadPoolExecutor(max_workers=min(48, max(1, len(by_src)))) as ex:
        for d in ex.map(lambda kv: _probe_one(kv[0], kv[1]), by_src.items()):
            out.update(d)
    print(json.dumps({str(k): v for k, v in out.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
