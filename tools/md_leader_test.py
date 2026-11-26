#!/usr/bin/env python3
"""Leader controller + pre-drawn view checks (#307), frame by frame.

  md_leader_test.py [ROM] [--route tools/playtest_route_leader.txt]
                    [--from 3700] [--to N]

Runs the route on the big-ROM build (topdown, --size 10m) and checks, on
every frame the pre-drawn view and the leader controller are on:

  fontblank  the font blank tile (every blank window cell) stays blank
  hud        no gold / time / food-water words in the HUD rows (td_hsrc
             cells) while no message shows
  jump       the leader figure moves <= 1/16 cell a frame (no teleport)
  lift       the figure's lift is the lift of the cell nearest its drawn
             place, one frame late at most (it turns at half a step)
  plane      every 30th frame: every screen tile matches the atlas
  late       leader images shown late (TA_MISS), reported, not failed

Exit status 1 if any of the failing checks has a hit.
"""
import argparse
import glob
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_iso_cadence import equs  # noqa: E402
from md_run import MD, parse_route  # noqa: E402
from md_vram import vdp_from_state  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
# controller variables (DECBUF tail, after TD_ARTOK $FF7D4C; forward
# references, so not in equs())
TA_ON, TA_L, TA_T = 0x7D4E, 0x7D50, 0x7D52
TA_AR, TA_PH, TA_CTL = 0x7D62, 0x7D6A, 0x7D7A
TA_MISS, TA_LT = 0x7D94, 0x7D96
HSRC = [(6, 9), (7, 13), (10, 13), (11, 16), (14, 16), (15, 18)]  # rows 20-25


def s16(v):
    return v - 65536 if v > 32767 else v


class Atlas:
    def __init__(self):
        f = sorted(glob.glob(str(REPO / "build" / "ow-atlas4-*.bin")))
        self.d = open(f[-1], "rb").read() if f else None

    def tile(self, area, row, col, ph):
        d, o = self.d, 0x210000
        h = struct.unpack_from(">I", d, 6 + 4 * area)[0] - o
        R, C, BR, BC, dy, dx, TB, BL = struct.unpack_from(">HHHHhhII", d, h)
        r, c = row + dy, col + dx
        if not (0 <= r < R and 0 <= c < C):
            return None
        p = struct.unpack_from(">I", d, h + 20 + 4 * ((r // 16) * BC + c // 16))[0]
        if not p:
            return None
        rec = p - o
        i = d[rec + (r % 16) * 16 + c % 16]
        t = int.from_bytes(d[rec + 256 + 6 * i + 3 * ph:rec + 259 + 6 * i + 3 * ph], "big")
        return None if t == BL else d[TB - o + 32 * t:TB - o + 32 * t + 32]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", default=str(REPO / "build" / "rop-topdown-10m.rom"))
    ap.add_argument("--route", default=str(REPO / "tools" / "playtest_route_leader.txt"))
    ap.add_argument("--from", dest="lo", type=int, default=3700)
    ap.add_argument("--to", dest="hi", type=int, default=0)
    a = ap.parse_args()
    E = equs()
    seq = []
    for n, p in parse_route(a.route):
        seq += [p] * n
    hi = a.hi or len(seq)
    atlas = Atlas()
    md = MD(a.rom)
    hits = {k: [] for k in ("fontblank", "hud", "jump", "lift", "plane")}
    prev = None
    miss0 = None
    frames = 0
    for i in range(hi):
        md.step("" if seq[i] == "." else seq[i])
        if i < a.lo:
            continue
        r = bytes(md.ram())
        W = lambda x: (r[x & 0xFFFF] << 8) | r[(x & 0xFFFF) + 1]  # noqa: E731
        if W(TA_ON) != 0x5A71 or not W(TA_CTL):
            prev = None
            continue
        frames += 1
        if miss0 is None:
            miss0 = W(TA_MISS)
        vdp = vdp_from_state(md.em.get_state())
        vr = vdp["vram"]
        fb = W(0xFF8640)
        if any(vr[fb * 32:fb * 32 + 32]):
            hits["fontblank"].append(i)
        if not W(E["TD_MSG"]):
            for k, (c0, c1) in enumerate(HSRC):
                row = 20 + k
                if any(((vr[0x1000 + (row * 64 + c) * 2] << 8 | vr[0x1001 + (row * 64 + c) * 2]) & 0x7FF) != fb
                       for c in range(c0, c1 + 1)):
                    hits["hud"].append(i)
                    break
        ld = W(0xFF02B2)
        g = (W(0xFF02B4 + ld * 0x34 + 0xC), W(0xFF02B4 + ld * 0x34 + 0xE))
        pos = (s16(W(E["TD_LEADX"])), s16(W(E["TD_LEADY"])))
        area = W(TA_AR)
        if prev and prev[2] == area and max(abs(pos[0] - prev[0][0]), abs(pos[1] - prev[0][1])) > 1 \
                and max(abs(g[0] - prev[1][0]), abs(g[1] - prev[1][1])) <= 1:
            hits["jump"].append((i, pos, prev[0]))
        lt = {(W(TA_LT + 6 * k), W(TA_LT + 6 * k + 2)): W(TA_LT + 6 * k + 4) for k in range(5)}
        lfd = W(E["TD_LFD"] + 2 * ld)
        near = ((pos[0] + 8) >> 4, (pos[1] + 8) >> 4)  # lift turns at half a step
        pnear = prev and ((prev[0][0] + 8) >> 4, (prev[0][1] + 8) >> 4)
        if near in lt and lt[near] != lfd and prev and prev[2] == area \
                and lt.get(pnear, lfd) != lfd:          # (one frame late is fine)
            hits["lift"].append((i, near, lfd, lt[near]))
        if atlas.d and i % 30 == 0:
            gx, gy = s16(W(E["TD_IGX"])), s16(W(E["TD_IGY"]))
            bad = 0
            for sy in range(0, 224, 8):
                for sx in range(0, 320, 8):
                    px, py = gx + sx, gy - 6 + sy
                    pc, pr = (px // 8) & 63, (py // 8) & 31
                    t = ((vr[(pr * 64 + pc) * 2] << 8) | vr[(pr * 64 + pc) * 2 + 1]) & 0x7FF
                    want = [atlas.tile(area - 1, py // 8, px // 8, ph) for ph in (0, 1)]
                    if want[0] is None and want[1] is None:
                        continue
                    if bytes(vr[t * 32:t * 32 + 32]) not in want:
                        bad += 1
            if bad:
                hits["plane"].append((i, bad))
        prev = (pos, g, area)
    late = (W(TA_MISS) - miss0) & 0xFFFF if miss0 is not None else 0
    print("frames checked %d (controller on)" % frames)
    fail = False
    for k, v in hits.items():
        print("%-10s %s" % (k, "ok" if not v else "%d hits, first %s" % (len(v), v[:3])))
        fail |= bool(v)
    print("%-10s %d leader images shown late" % ("late", late))
    return 1 if fail or not frames else 0


if __name__ == "__main__":
    sys.exit(main())
