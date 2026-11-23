#!/usr/bin/env python3
"""tier2_sample.py — per-scene VBlank PC sampling (issue #282).

Runs one route on the tier2-profiler ROM (plain ROM + VBlank sampler
hook; see patches/tier2-profiler/) under GPGX via tools/md_run.py and
records, per frame, the sampled interrupted PC ($FFDC00), the sample
count ($FFDC04), the frame counter, MODE ($FF00AE), LOC ($FF0E98),
UI mode ($FF00AC) and combat flags ($FF010E).

A sample is valid only when count == frame (the sampler ticks once per
VBlank in lockstep with the frame counter; during boot $FFDC00 holds
transient scratch, where count != frame) and the PC falls inside a
Ghidra routine range from disasm/ghidra/functions.txt.

Scene classification is done afterwards by tools/tier2_scenes.py from
the recorded RAM words + the route's known phase boundaries, so this
script stays a dumb recorder.

Usage:
  PYTHONNOUSERSITE=0 python3 tools/tier2_sample.py --rom build/tier2/profiled.rom \
      --route tools/playtest_route_orig.txt --out build/tier2/orig.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import md_run as m

FIELDS = {
    "frame": 0xFF0012, "mode": 0xFF00AE, "loc": 0xFF0E98,
    "ui": 0xFF00AC, "cflags": 0xFF010E,
    "pc_hi": 0xFFDC00, "pc_lo": 0xFFDC02, "count": 0xFFDC04,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=0)
    args = ap.parse_args()
    md = m.MD(args.rom)
    seq = []
    for n, pad in m.parse_route(args.route):
        seq += [pad] * n
    total = args.frames or len(seq)
    rec = []
    for i in range(total):
        md.step(seq[i] if i < len(seq) else "")
        ram = md.ram()
        row = {"i": i, "pad": seq[i] if i < len(seq) else ""}
        row.update({k: m.w(ram, a) for k, a in FIELDS.items()})
        row["pc"] = (row.pop("pc_hi") << 16) | row.pop("pc_lo")
        rec.append(row)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"rom": args.rom, "route": args.route, "frames": total,
               "samples": rec}, open(out, "w"))
    valid = sum(1 for r in rec if r["count"] == r["frame"] and r["pc"] != 0)
    print(f"{args.route}: {total} frames, {valid} valid samples -> {out}")


if __name__ == "__main__":
    main()
