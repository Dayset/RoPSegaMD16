#!/usr/bin/env python3
"""tier2_apply.py — apply tier-2 promotions in 40-row shards (#282).

Promotion set (reviewed, see REPORT.md):
  A. Doc citation (163): tier-1 routines whose own start address is cited
     in docs/*.md (152 "strong" from tools/tier2_cite.py), plus 11
     in-body citations adjudicated by hand (ACCEPTED_INBODY below).
  B. Live PC sampling (8): remaining tier-1 routines sampled by the
     VBlank profiler in a scene matching their name (tools/tier2_scenes.py
     + build/tier2/*.json runs). Each note cites the run, scene, sample
     count and frame span.

Notes are appended, never rewritten: "; tier2: <doc>:<line> cites $X"
or "; tier2 live: <scene> scene, N VBlank samples (<run> run fA-fB)".
Names, addresses and tiers of all other rows are untouched. Only the
tier column (1 -> 2) and the note column change, so disasm/src/rop.s
is byte-identical (gen_src.py only reads addr+name).

Shards are the playbook's code shards: shard k = rows 40k+1..40k+40 of
disasm/ghidra/functions.txt (address order). The script applies one
shard, runs tools/lint_symbols.py, and only then moves to the next.

Usage:
  python3 tools/tier2_apply.py            # dry run: print the plan
  python3 tools/tier2_apply.py --apply    # write the CSVs, linting per shard
"""
import argparse
import csv
import glob
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "tier2"

# In-body citations accepted by hand-reading the doc line (routine addr
# -> (doc, line, cited in-body addr)). All other in-body-only proposals
# were rejected: the cited address is a data value, a VDP constant, a
# record/frame number, or a call site that does not confirm the role.
ACCEPTED_INBODY = {
    0x00DC82: ("docs/save.md", 251, 0x00DCB8),
    0x020A88: ("docs/logic.md", 1770, 0x020BBE),
    0x021FE6: ("docs/cutscene-darius-endgame.md", 69, 0x0220AA),
    0x031A9C: ("docs/maps.md", 990, 0x031AF4),
    0x031F66: ("docs/maps.md", 991, 0x031FBE),
    0x03213C: ("docs/maps.md", 992, 0x032194),
    0x038938: ("docs/maps.md", 993, 0x038952),
    0x038DEA: ("docs/logic-audit.md", 439, 0x038F6C),
    0x038FB8: ("docs/logic-audit.md", 439, 0x039104),
    0x039172: ("docs/logic-audit.md", 439, 0x039396),
    0x0393FA: ("docs/cutscene-final-animation.md", 182, 0x0394F6),
}

# Live-sampling promotions: routine addr -> scene. The reviewed set:
# remaining tier-1 routines sampled by the VBlank profiler in a scene
# their name matches (map_/world_/npc_ in room/overworld). Run, sample
# count and frame span are read from the data in load_plan(); the run
# cited is the one with the most samples in that scene.
SAMPLING = {
    0x01E29C: "room",
    0x021194: "room",
    0x023628: "room",
    0x023770: "room",
    0x025E12: "room",
    0x026076: "room",
    0x026B08: "overworld",
    0x032FFA: "room",
}

LOGDOCS = ("docs/log/", "docs/research/", "docs/demos/")


def best_start_cite(prop):
    """Best start-address citation: top-level docs first, then doc, line."""
    starts = [c for c in prop["citations"] if c["at_start"]]
    starts.sort(key=lambda c: (c["doc"].startswith(LOGDOCS), c["doc"], c["line"]))
    return starts[0] if starts else None


def load_plan():
    cite = json.load(open(ROOT / "build" / "tier2_cite.json"))
    scenes = json.load(open(BUILD / "tier2_scenes.json"))
    funcs = []
    for line in (ROOT / "disasm" / "ghidra" / "functions.txt").read_text().splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == "FUNC":
            funcs.append(int(p[1], 16))
    starts = sorted(funcs)
    ends = {}
    for line in (ROOT / "disasm" / "ghidra" / "functions.txt").read_text().splitlines():
        p = line.split()
        if len(p) >= 2 and p[0] == "FUNC":
            ends[int(p[1], 16)] = int(p[2], 16) + 1
    import bisect

    def routine_of(pc):
        i = bisect.bisect_right(starts, pc) - 1
        if i < 0:
            return None
        s = starts[i]
        return s if pc < ends[s] else None

    # Per (routine, scene, run): count, first frame, last frame.
    import collections
    obs = collections.defaultdict(lambda: [0, None, None])
    for run, windows in scenes["windows"].items():
        d = json.load(open(BUILD / f"{run}.json"))
        s = d["samples"]
        for scene, lo, hi in windows:
            for r in s[lo:hi + 1]:
                if r["count"] != r["frame"] or not r["pc"]:
                    continue
                rt = routine_of(r["pc"])
                if rt is None:
                    continue
                k = (rt, scene, run)
                o = obs[k]
                o[0] += 1
                o[1] = r["i"] if o[1] is None else min(o[1], r["i"])
                o[2] = r["i"] if o[2] is None else max(o[2], r["i"])
    sampling = {}
    for addr, scene in SAMPLING.items():
        cands = [(v, run) for (a, sc, run), v in obs.items()
                 if a == addr and sc == scene]
        assert cands, f"no sampling observation for {addr:#x} in {scene}"
        (n, f0, f1), run = max(cands)
        sampling[addr] = (scene, run, n, f0, f1)

    plan = {}  # addr -> (kind, suffix)
    for p in cite["proposals"]:
        a = int(p["addr"], 16)
        if p["strong"]:
            c = best_start_cite(p)
            plan[a] = ("cite", f"; tier2: {c['doc']}:{c['line']} cites {c['addr']}")
        elif a in ACCEPTED_INBODY:
            doc, line, inaddr = ACCEPTED_INBODY[a]
            plan[a] = ("cite", f"; tier2: {doc}:{line} cites in-body ${inaddr:05X}")
    for a, (scene, run, n, f0, f1) in sampling.items():
        if a not in plan:
            plan[a] = ("live", f"; tier2 live: {scene} scene, {n} VBlank "
                               f"sample{'s' if n != 1 else ''} "
                               f"({run} run f{f0}-f{f1})")
    return plan, funcs


def load_csvs():
    files, rows = {}, {}
    for pat in ("code_*.csv", "extra.csv", "auto.csv"):
        for fp in sorted(glob.glob(str(ROOT / "disasm" / "symbols" / pat))):
            with open(fp, newline="") as fh:
                rd = list(csv.DictReader(fh))
            files[fp] = rd
            for r in rd:
                rows[int(r["addr"], 16)] = (fp, r)
    return files, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    plan, funcs = load_plan()
    files, rows = load_csvs()
    # Only tier-1 routines in the 446 can be promoted; anything else in
    # the plan is a bug.
    bad = [a for a in plan if rows.get(a, (None, {}))[1].get("tier") != "1"
           or a not in funcs]
    if bad:
        sys.exit(f"plan has non-tier-1 / non-func addrs: {[hex(a) for a in bad]}")
    shards = {}
    for i, a in enumerate(funcs):
        if a in plan:
            shards.setdefault(i // 40, []).append(a)
    n_cite = sum(1 for a in plan if plan[a][0] == "cite")
    n_live = sum(1 for a in plan if plan[a][0] == "live")
    print(f"plan: {len(plan)} promotions ({n_cite} citation, {n_live} live) "
          f"in {len(shards)} shards")
    for k in sorted(shards):
        print(f"  shard {k:2d} (funcs {40 * k + 1}-{40 * k + 40}): "
              f"{len(shards[k])} rows")
    if not args.apply:
        print("dry run; re-run with --apply to write")
        for a in sorted(plan):
            print(f"  0x{a:06X} {rows[a][1]['name']:32s} {plan[a][1]}")
        return 0
    for k in sorted(shards):
        for a in shards[k]:
            fp, r = rows[a]
            r["tier"] = "2"
            r["note"] = r["note"] + plan[a][1]
        # Write back every touched file, then lint before the next shard.
        touched = {rows[a][0] for a in shards[k]}
        for fp in touched:
            with open(fp, "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["addr", "name", "tier", "note"],
                                   lineterminator="\n")
                w.writeheader()
                w.writerows(files[fp])
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "lint_symbols.py")],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            print(r.stdout, r.stderr)
            sys.exit(f"lint failed after shard {k}")
        print(f"shard {k}: applied {len(shards[k])} rows, lint OK")
    print(f"applied {len(plan)} promotions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
