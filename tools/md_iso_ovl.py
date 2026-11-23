#!/usr/bin/env python3
"""Occlusion overlays needed per frame (#278): md_iso_ovl.py --rom R --route F
Counts iso frames, frames with >= 1 figure needing an overlay (TD_OVN),
and the mean figures per frame (TD_NB)."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_run
from md_iso_cadence import equs

ap = argparse.ArgumentParser()
ap.add_argument("--rom", required=True)
ap.add_argument("--route", required=True)
a = ap.parse_args()
E, w = equs(), md_run.w
seq = []
for n, pad in md_run.parse_route(a.route):
    seq += [pad] * n
md = md_run.MD(a.rom)
fr = occ = figs = ovs = 0
for pad in seq:
    md.step(pad)
    r = md.ram()
    if not w(r, E["TD_ISO"]) or w(r, 0xFF00AE) not in (1, 2):
        continue
    fr += 1
    figs += w(r, E["TD_NB"])
    ovs += w(r, E["TD_OVN"])
    occ += w(r, E["TD_OVN"]) > 0
print(f"iso frames {fr}; with overlay {occ} ({100*occ/max(fr,1):.1f}%); "
      f"figures/frame {figs/max(fr,1):.2f}; overlays/frame {ovs/max(fr,1):.2f}")
