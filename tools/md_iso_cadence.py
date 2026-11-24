#!/usr/bin/env python3
"""Picture cadence of the smooth iso view (#266), from RAM per frame.

  md_iso_cadence.py --rom R --route F [--from A] [--to B]

Per frame in the iso view (TD_ISO set): game camera cell ($FF0E8E/90)
vs the camera cell of the picture on the plane (TD_ICX/ICY), and the
render state (TD_IRS). Reports, over frames where the game camera has
moved in the last 64 frames and the scene (mode, location) has not
changed in the last 64 ("walking"):
  picture lag  share of frames with the picture at the game camera
               cell (0) / at most 1 cell away per axis
  camera trail share with the shown camera (TD_CMX/CMY, 1/TI_CU cell)
               at most 1 cell behind the game camera, and its mean
  renders, ticks, render frames (IRS != 0) per render.
Addresses come from patches/topdown/feature.s (equ chain).
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_run

FEAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                    "patches", "topdown", "feature.s")


def equs(path=FEAT):
    env = {}
    for line in open(path):
        m = re.match(r"^([A-Z_0-9]+)\s+equ\s+([^;]+)", line)
        if not m:
            continue
        expr = m.group(2).strip().replace("$", "0x")
        try:
            env[m.group(1)] = eval(expr, {}, dict(env))
        except Exception:
            pass
    # RAM equs are written sign-extended ($FFFFDC00, abs.w): 24-bit bus
    return {k: v & 0xFFFFFF if isinstance(v, int) and v > 0xFFFFFF else v
            for k, v in env.items()}


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--from", dest="lo", type=int, default=0)
    ap.add_argument("--to", dest="hi", type=int, default=None)
    a = ap.parse_args()
    E = equs()
    seq = []
    for n, pad in md_run.parse_route(a.route):
        seq += [pad] * n
    hi = a.hi or len(seq)
    md = md_run.MD(a.rom)
    w = md_run.w
    walk = n0 = n1 = ntr = trs = 0
    bym = {}
    renders = 0
    rbm = {}
    rframes = 0
    st = {1: [], 2: []}
    run = {1: 0, 2: 0}
    prev_irs = 0
    last_move = -999
    prev_cam = None
    prev_scene = None
    last_scene = -999
    ticks = 0
    prev_tick = None
    for i in range(hi):
        md.step(seq[i] if i < len(seq) else "")
        if i < a.lo:
            continue
        ram = md.ram()
        if not w(ram, E["TD_ISO"]) or w(ram, 0xFF00AE) not in (1, 2):
            prev_cam = None
            continue
        cam = (w(ram, 0xFF0E8E), w(ram, 0xFF0E90))
        scene = (w(ram, 0xFF00AE), w(ram, 0xFF0E98))
        if scene != prev_scene:
            prev_scene = scene
            last_scene = i
        if prev_cam is not None and max(abs(cam[0] - prev_cam[0]),
                                        abs(cam[1] - prev_cam[1])) > 3:
            last_scene = i              # door / teleport: a new scene
        if cam != prev_cam:
            if prev_cam is not None:
                last_move = i
            prev_cam = cam
        tk = w(ram, E["TD_TICKFR"])
        if tk != prev_tick:
            ticks += 1
            prev_tick = tk
        irs = w(ram, E["TD_IRS"])
        if irs:
            rframes += 1
            run[irs] = run.get(irs, 0) + 1
        if prev_irs == 2 and irs != 2:
            renders += 1
            st[1].append(run[1])
            rbm.setdefault(w(ram, 0xFF00AE), []).append(run[1])
            st[2].append(run[2])
            run = {1: 0, 2: 0}
        prev_irs = irs
        if i - last_move > 64 or i - last_scene < 64:
            continue
        pic = (s16(w(ram, E["TD_ICX"])), s16(w(ram, E["TD_ICY"])))
        d = max(abs(pic[0] - cam[0]), abs(pic[1] - cam[1]))
        walk += 1
        n0 += d == 0
        n1 += d <= 1
        cu = E.get("TI_CU", 16)
        tr = max(abs(w(ram, E["TD_CMX"]) - cu * cam[0]),
                 abs(w(ram, E["TD_CMY"]) - cu * cam[1])) * 16 // cu
        ntr += tr <= 16
        trs += tr
        md_ = w(ram, 0xFF00AE)
        bym.setdefault(md_, [0, 0])
        bym[md_][0] += 1
        bym[md_][1] += tr <= 16
    pr = lambda k: "%.1f%%" % (100.0 * k / walk) if walk else "-"
    med = lambda v: sorted(v)[len(v) // 2] if v else 0
    print("walking frames %d  picture lag 0: %s, <=1 cell: %s  camera trail "
          "<=1 cell: %s (mean %.1f/16)  pictures %d  frames per picture: "
          "render %s commit %s (median), render mean %.2f"
          % (walk, pr(n0), pr(n1), pr(ntr), trs / walk if walk else 0,
             renders, med(st[1]), med(st[2]),
             sum(st[1]) / len(st[1]) if st[1] else 0))
    for k, v in sorted(rbm.items()):
        print("  %s: %d pictures, render mean %.2f frames"
              % ({1: "overworld", 2: "rooms"}.get(k, k), len(v), sum(v) / len(v)))
    for k, (n, g) in sorted(bym.items()):
        print("  %s: %d walking frames, camera trail <=1 cell %.1f%%"
              % ({1: "overworld", 2: "rooms"}.get(k, k), n, 100.0 * g / n))


if __name__ == "__main__":
    main()
