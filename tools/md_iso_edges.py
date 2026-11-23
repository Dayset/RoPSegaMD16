#!/usr/bin/env python3
"""Render-edge checker for the smooth iso view (#279).

  md_iso_edges.py --rom R --route F [--from A] [--to B] [--json OUT]

Per frame in the iso view: every Plane B tile visible through the
frame's hole must lie in the committed region of the picture that last
wrote its plane row. The commit writes all 32 plane rows of a picture
(23 bitmap rows + 9 void rows), each row void outside the columns
`ti_crow` gives it, so a hole pixel on any other tile shows a render
edge (parchment where the world should be) or another place.

Row owner: while a commit is in progress (TD_IRS = 2) the rows it has
written (bitmap rows < TD_IROW at TD_INX/INY) belong to the new picture,
the rest to the picture on the plane (TD_IOX/IOY). A tile (gx, gy) of a
picture at (ox, oy) is committed if r = gy - oy is in 0..22 and
gx - ox is in ti_crow[r].

Second count, overworld only (mode 1, where the world has no empty
cells): hole pixels on the void tile in the plane after the step. It
also catches committed tiles the render left blank (its 10x10 cells do
not reach them): measured 2026-11-23, those show once the camera is
more than half a cell below the picture's cell on an axis, while +1
cell stays clean, so the safe range is [-0.5, +1] cell, not +-1.

The frame is checked against the state after the previous step: the
scroll and the plane written in a VBlank show in the frame after it.
The hole is tools/td_iso_frame.py's `inside`, at pixel centres. The
scroll is the VDP's (H-scroll table $2000 word 1, VSRAM 1), placed on
the global grid with TD_IGX/IGY (plane B line 0 = global line 6).
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import md_run, md_vram, md_iso_cadence, td_iso_frame


def hole_pixels():
    ys, xs = np.mgrid[0:224, 0:320]
    m = (td_iso_frame.HH * np.abs(xs + 0.5 - td_iso_frame.CX)
         + td_iso_frame.HW * np.abs(ys + 0.5 - td_iso_frame.CY)
         <= td_iso_frame.HW * td_iso_frame.HH) & (ys < td_iso_frame.YCUT)
    return xs[m], ys[m]


def wrap(v, n):
    v %= n
    return v - n if v >= n // 2 else v


def check(ram, vdp, E, crow, hx, hy):
    """-> number of hole pixels on uncommitted tiles (0 = clean), and the
    distinct (gx, gy) tiles involved."""
    w, s = md_run.w, md_iso_cadence.s16
    igx, igy = s(w(ram, E["TD_IGX"])), s(w(ram, E["TD_IGY"]))
    vr = vdp["vram"]
    hs = (vr[0x2002] << 8 | vr[0x2003])
    hs = hs - 0x10000 if hs & 0x8000 else hs
    vs = int(vdp["vsram"][1])
    # global pixel of screen (0,0): x = -hs, y = vs + 6, on the plane's
    # period; take the representative nearest the RAM camera
    gx0 = igx + wrap(-hs - igx, 512)
    gy0 = igy + wrap(vs + 6 - igy, 256)
    gx = (hx + gx0) >> 3
    gy = (hy + gy0 - 6) >> 3
    old = (s(w(ram, E["TD_IOX"])), s(w(ram, E["TD_IOY"])))
    new = (s(w(ram, E["TD_INX"])), s(w(ram, E["TD_INY"])))
    irs, irow = w(ram, E["TD_IRS"]), w(ram, E["TD_IROW"])
    lo = np.array([c[0] for c in crow] + [1] * 9)
    hi = np.array([c[1] for c in crow] + [0] * 9)
    ox = np.full(gx.shape, old[0])
    oy = np.full(gy.shape, old[1])
    if irs == 2 and irow:
        rn = (gy - new[1]) & 31
        mine = rn < min(irow, 32)
        ox[mine], oy[mine] = new
    r = gy - oy
    c = gx - ox
    ok = (r >= 0) & (r < 23)
    rr = np.clip(r, 0, 31)
    ok &= (c >= lo[rr]) & (c <= hi[rr])
    bad = ~ok
    return int(bad.sum()), sorted(set(zip(gx[bad].tolist(), gy[bad].tolist())))[:8]


def void_pixels(ram, vdp, pvdp, E, hx, hy):
    """Hole pixels on the void tile: plane of this state, scroll of the
    previous one (what the frame showed)."""
    void = md_run.w(ram, E["TD_BASE"]) + 256
    pv = pvdp["vram"]
    hs = (pv[0x2002] << 8 | pv[0x2003])
    vs = int(pvdp["vsram"][1])
    px = (hx - hs) & 511
    py = (hy + vs) & 255
    vr = np.frombuffer(vdp["vram"], dtype=np.uint8)
    idx = ((py >> 3) * 64 + (px >> 3)) * 2      # Plane B table at $0000
    nm = ((vr[idx].astype(int) << 8) | vr[idx + 1]) & 0x7FF
    return int((nm == void).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--to", dest="hi", type=int, default=None)
    ap.add_argument("--json")
    a = ap.parse_args()
    E = md_iso_cadence.equs()
    crow = td_iso_frame.commit_rows()
    hx, hy = hole_pixels()
    seq = []
    for n, pad in md_run.parse_route(a.route):
        seq += [pad] * n
    hi = a.hi or len(seq)
    md = md_run.MD(a.rom)
    w = md_run.w
    prev = None
    frames = bad_frames = void_frames = ow_frames = 0
    worst = []
    rows = []
    for i in range(hi):
        md.step(seq[i] if i < len(seq) else "")
        if i < a.lo:
            continue
        ram = md.ram()
        live = (w(ram, E["TD_ISO"]) and w(ram, E["TD_VALID"])
                and w(ram, 0xFF00AE) in (1, 2) and w(ram, E["TD_ICX"]) != 0x8000)
        vdp = md_vram.vdp_from_state(md.em.get_state()) if live else None
        if prev is not None and live:
            pram, pvdp = prev
            n, tiles = check(pram, pvdp, E, crow, hx, hy)
            if w(ram, 0xFF00AE) == 1 and w(pram, 0xFF00AE) == 1:
                ow_frames += 1
                void_frames += void_pixels(ram, vdp, pvdp, E, hx, hy) > 0
            frames += 1
            if n:
                bad_frames += 1
                if len(worst) < 20:
                    worst.append((i, n, tiles))
            rows.append((i, n))
        prev = (ram, vdp) if live else None
    out = {"frames": frames, "bad_frames": bad_frames,
           "bad_pixels_max": max((n for _, n in rows), default=0),
           "overworld_frames": ow_frames, "overworld_void_frames": void_frames,
           "first_bad": worst}
    print(json.dumps(out))
    if a.json:
        json.dump(rows, open(a.json, "w"))


if __name__ == "__main__":
    main()
