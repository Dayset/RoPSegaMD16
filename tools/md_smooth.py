#!/usr/bin/env python3
"""Smoothness of a route segment, measured on the rendered frames only
(no RAM probes, so it judges the picture the player sees).

For every pair of consecutive frames the background shift (dx, dy) is
the integer translation in [-R, R]^2 that best maps frame t onto t+1 in
the play area (rows 8..150, cols 8..300, the pad icon box masked out).
A frame whose best translation still leaves many pixels changed is a
"redraw" (the picture was replaced, not moved) — the original game's
world update — and its changed-pixel count is reported.

  md_smooth.py --rom R --route F --from A --to B [--radius 4] [--hole]

--hole: smooth iso view (#252): judge only the pixels inside the fixed
parchment frame's hole (the frame never moves, the picture under it
does), shrunk by 8 px so figures crossing the edge do not count.
"""
import argparse, json, os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import md_run
import md_vram


def best_shift(a, b, R):
    # a, b: HxW int arrays (luma). Find (dx,dy) minimising mismatches of
    # b[y,x] vs a[y-dy, x-dx] on the interior.
    H, W = a.shape
    best = None
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            A = a[R - dy:H - R - dy, R - dx:W - R - dx]
            B = b[R:H - R, R:W - R]
            n = int((A != B).sum())
            if best is None or n < best[0]:
                best = (n, dx, dy)
    return best


def hole_mask(R):
    # screen pixels of the play crop (rows 8..150, cols 8..300) inside the
    # iso hole |x-162|*64 + |y-98|*112 <= 7168, shrunk by ~8 px
    ys, xs = np.mgrid[8:150, 8:300]
    m = 64 * np.abs(xs + 0.5 - 162) + 112 * np.abs(ys + 0.5 - 98) <= 7168 - 8 * 128
    return m[R:-R, R:-R]


def best_shift_masked(a, b, R, m):
    H, W = a.shape
    B = b[R:H - R, R:W - R]
    best = None
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            A = a[R - dy:H - R - dy, R - dx:W - R - dx]
            n = int(((A != B) & m).sum())
            if best is None or n < best[0]:
                best = (n, dx, dy)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--from", dest="lo", type=int, required=True)
    ap.add_argument("--to", dest="hi", type=int, required=True)
    ap.add_argument("--radius", type=int, default=4)
    ap.add_argument("--json")
    ap.add_argument("--hole", action="store_true")
    ap.add_argument("--fold", action="append", default=[],
                    help="R,G,B=R,G,B: count the first colour as the second "
                         "(ignore a deliberate colour animation, e.g. water)")
    a = ap.parse_args()
    seq = []
    for n, pad in md_run.parse_route(a.route):
        seq += [pad] * n
    md = md_run.MD(a.rom)
    prev = None
    hmask = hole_mask(a.radius) if a.hole else None
    prev_cram = None
    rows = []
    blobs = []
    for i in range(a.hi):
        md.step(seq[i] if i < len(seq) else "")
        if i < a.lo:
            continue
        vdp = md_vram.vdp_from_state(md.em.get_state())
        cram = vdp["cram"].copy()
        palchg = prev_cram is not None and bool((cram != prev_cram).any())
        prev_cram = cram
        # sprite slot 68 (topdown leader blob) if it is in the link chain
        vr, k, seen = vdp["vram"], 0, []
        while k not in seen and len(seen) < 80:
            seen.append(k)
            o = 0x2400 + k * 8
            k = ((vr[o + 2] << 8) | vr[o + 3]) & 0x7F
            if k == 0:
                break
        if 68 in seen:
            o = 0x2400 + 68 * 8
            blobs.append((i, (vr[o + 6] << 8 | vr[o + 7]) & 0x1FF, (vr[o] << 8 | vr[o + 1]) & 0x1FF))
        s = md.screen()[8:150, 8:300].astype(np.int32)
        s[0:60, 160:292] = 0          # pad icon (sprites)
        for f in a.fold:
            src, dst = (np.array([int(v) for v in c.split(",")]) for c in f.split("="))
            s[(s == src).all(2)] = dst
        luma = s[:, :, 0] * 3 + s[:, :, 1] * 5 + s[:, :, 2] * 2
        if prev is not None:
            d = luma != prev
            R = a.radius
            chg = int((d[R:-R, R:-R] & hmask).sum()) if a.hole else int(d.sum())
            if chg == 0:
                rows.append((i, 0, 0, 0, 0, palchg))
            else:
                n, dx, dy = (best_shift_masked(prev, luma, a.radius, hmask) if a.hole
                             else best_shift(prev, luma, a.radius))
                rows.append((i, chg, dx, dy, n, palchg))
        prev = luma
    area = rows and (int(hmask.sum()) if a.hole else (142 - 2 * a.radius) * (292 - 2 * a.radius))
    moves = [r for r in rows if (r[2] or r[3]) and r[4] < 0.05 * area]
    redraws = [r for r in rows if r[1] > 0.10 * area and r[4] >= 0.05 * area and not r[5]]
    still = [r for r in rows if r[1] == 0]
    out = {
        "frames": len(rows),
        "scroll_frames": len(moves),
        "scroll_step_px": sorted({abs(r[2]) + abs(r[3]) for r in moves}),
        "scroll_step_hist": {str(k): sum(1 for r in moves
                                         if abs(r[2]) + abs(r[3]) == k)
                             for k in sorted({abs(r[2]) + abs(r[3])
                                              for r in moves})},
        # hitch: a one-frame stop with the picture moving on both sides
        "hitch_frames": sum(1 for p_, c, n_ in zip(rows, rows[1:], rows[2:])
                            if not (c[2] or c[3]) and (p_[2] or p_[3]) and (n_[2] or n_[3])),
        "redraw_frames": len(redraws),
        "unchanged_frames": len(still),
        "palette_frames": sum(1 for r in rows if r[5]),
    }
    if blobs:
        steps = [abs(b[1] - a_[1]) + abs(b[2] - a_[2]) for a_, b in zip(blobs, blobs[1:])
                 if b[0] == a_[0] + 1]
        out["blob_frames"] = len(blobs)
        out["blob_step_hist"] = {k: steps.count(k) for k in sorted(set(steps))}
    if redraws:
        gaps = [b[0] - a_[0] for a_, b in zip(redraws, redraws[1:])]
        out["redraw_gap_mean"] = round(sum(gaps) / max(1, len(gaps)), 1)
    print(json.dumps(out))
    if a.json:
        json.dump(rows, open(a.json, "w"))


if __name__ == "__main__":
    main()
