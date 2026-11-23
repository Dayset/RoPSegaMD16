#!/usr/bin/env python3
"""tier2_scenes.py — routine -> scenes table from PC-sample runs (#282).

Reads the per-frame sample JSONs written by tools/tier2_sample.py and
maps each valid sampled PC to its Ghidra routine (disasm/ghidra/
functions.txt). Scene windows per run are fixed from the RAM transitions
observed in the traces (see build/tier2_scenes.json for the windows):

  attract.json : attract  351-1799  (post-boot, no input; MODE 1, LOC 0)
  orig.json    : attract  351-3294
                 overworld 3295-3926 (LOC $FFFF, MODE 1)
                 room     3927-5275  (MODE 2, LOC $0D Academy)
  menu.json    : attract  351-3294
                 overworld 3295-3391
                 menu     3392-3919  ($FF00AC 0 -> 1 after START)
  explore.json : attract  351-3294
                 overworld 3295-6825
                 room     6826-16409 (MODE 2, LOC $15; $FF00AC $FFFF
                           from 6858: a verb menu open, main_loop idle;
                           shop_record_score / shop_merchant_setup
                           sampled f6858-6877 — merchant interaction,
                           not a confirmed shop visit)

A sample is valid only when count == frame and pc != 0 (boot scratch
filtered). Output: build/tier2_scenes.csv (routine, name, scenes,
counts) and build/tier2_scenes.json (windows + per-scene routine lists).

Usage: python3 tools/tier2_scenes.py
"""
import bisect
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "tier2"

WINDOWS = {
    "attract": [("attract", 351, 1799)],
    "orig": [("attract", 351, 3294), ("overworld", 3295, 3926),
             ("room", 3927, 5275)],
    "menu": [("attract", 351, 3294), ("overworld", 3295, 3391),
             ("menu", 3392, 3919)],
    "explore": [("attract", 351, 3294), ("overworld", 3295, 6825),
                ("room", 6826, 16409)],
    # buc.json: route_buc.txt (md_buc_route.py on the profiled ROM):
    # overworld 3295-3934, room 156 (Buc interior) 3935-9014; brief
    # $FF00AC $FFFF at 5318-5338 is the cutscene dialog beat.
    "buc": [("attract", 351, 3294), ("overworld", 3295, 3934),
            ("room", 3935, 9014)],
}


def load_routines():
    funcs = []
    for line in (ROOT / "disasm" / "ghidra" / "functions.txt").read_text().splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == "FUNC":
            funcs.append((int(p[1], 16), int(p[2], 16) + 1))
    funcs.sort()
    names = {}
    for pat in ("code_*.csv", "extra.csv", "auto.csv"):
        for fp in (ROOT / "disasm" / "symbols").glob(pat):
            for r in csv.DictReader(open(fp)):
                names[int(r["addr"], 16)] = r["name"]
    return funcs, names


def main():
    funcs, names = load_routines()
    starts = [s for s, _ in funcs]

    def routine(pc):
        i = bisect.bisect_right(starts, pc) - 1
        if i < 0:
            return None
        s, e = funcs[i]
        return (s, names.get(s, "?")) if pc < e else None

    per_routine = defaultdict(Counter)   # addr -> Counter(scene -> n)
    per_scene = defaultdict(Counter)     # scene -> Counter(addr -> n)
    totals = Counter()
    for run, windows in WINDOWS.items():
        d = json.load(open(BUILD / f"{run}.json"))
        s = d["samples"]
        for scene, lo, hi in windows:
            n = 0
            for r in s[lo:hi + 1]:
                if r["count"] != r["frame"] or not r["pc"]:
                    continue
                rt = routine(r["pc"])
                if rt is None:
                    continue
                per_routine[rt[0]][scene] += 1
                per_scene[scene][rt[0]] += 1
                n += 1
            totals[scene] += n
    rows = []
    for addr in sorted(per_routine):
        c = per_routine[addr]
        rows.append({"addr": f"0x{addr:06X}", "name": names.get(addr, "?"),
                     "scenes": ";".join(sorted(c)),
                     **{sc: c.get(sc, 0) for sc in
                        ("attract", "overworld", "room", "menu", "combat", "shop")},
                     "total": sum(c.values())})
    csvp = BUILD / "tier2_scenes.csv"
    with open(csvp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["addr", "name", "scenes", "attract",
                                           "overworld", "room", "menu", "combat",
                                           "shop", "total"])
        w.writeheader()
        w.writerows(rows)
    json.dump({"windows": WINDOWS,
               "scene_sample_totals": dict(totals),
               "routines_seen": len(rows),
               "per_scene_routines": {sc: len(c) for sc, c in per_scene.items()},
               "rows": rows}, open(BUILD / "tier2_scenes.json", "w"), indent=1)
    print(f"routines seen in sampling: {len(rows)}")
    for sc in ("attract", "overworld", "room", "menu"):
        print(f"  {sc}: {totals[sc]} valid routine samples, "
              f"{len(per_scene[sc])} routines")
    print(f"wrote {csvp}")


if __name__ == "__main__":
    main()
