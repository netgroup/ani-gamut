#!/usr/bin/env python3
"""Lightweight real-time resource monitor for the ANI-Gamut VM.

Samples load average / memory / disk / running clab containers every --interval
seconds and prints one line per tick (optionally appending a CSV). Use it to
size the worker pool: if load1 stays well below nproc while a run is active, the
box is latency-bound (waiting on the LLM API and on pings) and has headroom for
more parallel labs; if load1 approaches or exceeds nproc, you are CPU-bound and
should not add workers.

    python3 tools/resmon.py                    # every 5s to stdout
    python3 tools/resmon.py -i 10 --csv ~/resmon.csv
    python3 tools/resmon.py --once             # a single sample, then exit

Stdlib only, so it runs under any interpreter (no venv needed).
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime


def meminfo():
    """Return (total_bytes, used_bytes) from /proc/meminfo (used = total - available)."""
    d = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, _, v = line.partition(":")
            d[k] = int(v.split()[0]) * 1024
    total = d.get("MemTotal", 0)
    avail = d.get("MemAvailable", total)
    return total, total - avail


def clab_count():
    """Number of running containers whose name starts with clab- (the lab nodes)."""
    try:
        out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return -1
    return sum(1 for n in out.splitlines() if n.startswith("clab-"))


def gb(x):
    return x / 1024 ** 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--interval", type=float, default=5.0, help="seconds between samples")
    ap.add_argument("--csv", default="", help="append samples to this CSV file")
    ap.add_argument("--once", action="store_true", help="take one sample and exit")
    a = ap.parse_args()

    ncpu = os.cpu_count() or 1
    csv = open(a.csv, "a") if a.csv else None
    if csv and csv.tell() == 0:
        csv.write("iso_ts,load1,load5,ncpu,mem_used_gb,mem_total_gb,"
                  "disk_used_gb,disk_total_gb,clab_containers\n")

    print(f"resmon: interval={a.interval}s ncpu={ncpu}"
          + (f" csv={a.csv}" if a.csv else "") + "   (Ctrl-C to stop)", flush=True)
    try:
        while True:
            l1, l5, _ = os.getloadavg()
            mtot, mused = meminfo()
            du = shutil.disk_usage("/")
            nc = clab_count()
            now = datetime.now()
            print(f"{now:%H:%M:%S}  load {l1:5.1f}/{ncpu} ({100 * l1 / ncpu:3.0f}%)  "
                  f"mem {gb(mused):5.1f}/{gb(mtot):4.1f}G ({100 * mused / mtot:3.0f}%)  "
                  f"disk {gb(du.used):5.1f}/{gb(du.total):4.1f}G ({100 * du.used / du.total:3.0f}%)  "
                  f"clab {nc}", flush=True)
            if csv:
                csv.write(f"{now.isoformat()},{l1:.2f},{l5:.2f},{ncpu},"
                          f"{gb(mused):.2f},{gb(mtot):.2f},{gb(du.used):.2f},{gb(du.total):.2f},{nc}\n")
                csv.flush()
            if a.once:
                break
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print(file=sys.stderr)
    finally:
        if csv:
            csv.close()


if __name__ == "__main__":
    raise SystemExit(main())
