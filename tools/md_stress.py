#!/usr/bin/env python3
"""Random-input stress run: N frames of random pad input (seeded), hold
times 4-60 frames, A+B+C (view switch) included. Reports the longest
stretch with no VBlank (frame counter $FF0012 unchanged) and the longest
stretch with an unchanged screen; a crash shows as a VBlank gap that
never ends.

  md_stress.py ROM [--frames 30000] [--seed 1] [--prefix ROUTE:N] [--no-abc]

--prefix ROUTE:N plays the first N frames of a route first (e.g. into
the smooth iso view); --no-abc keeps A+B+C out (stay in that view).
"""
import argparse, json, os, random, sys, warnings, zlib
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_run

PADS = ["", "U", "D", "L", "R", "UL", "UR", "DL", "DR", "A", "B", "C", "S", "ABC"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--frames", type=int, default=30000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--prefix")
    ap.add_argument("--no-abc", action="store_true")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    md = md_run.MD(a.rom)
    pads = [p for p in PADS if p != "ABC"] if a.no_abc else PADS
    if a.prefix:
        route, n = a.prefix.rsplit(":", 1)
        seq = [p for k, p in md_run.parse_route(route) for _ in range(k)]
        for p in seq[:int(n)]:
            md.step(p)
    last_fc, fc_gap, fc_max = None, 0, 0
    last_crc, sc_gap, sc_max = None, 0, 0
    iso_frames = 0
    i = 0
    while i < a.frames:
        pad, n = rng.choice(pads), rng.randint(4, 60)
        for _ in range(min(n, a.frames - i)):
            md.step(pad)
            i += 1
            fc = md_run.w(md.ram(), 0xFF0012)
            fc_gap = fc_gap + 1 if fc == last_fc else 0
            fc_max, last_fc = max(fc_max, fc_gap), fc
            crc = zlib.crc32(md.screen().tobytes())
            sc_gap = sc_gap + 1 if crc == last_crc else 0
            sc_max, last_crc = max(sc_max, sc_gap), crc
            iso_frames += md_run.w(md.ram(), 0xFFDC00 + 0x550) != 0
    r = md.ram()
    print(json.dumps({"frames": a.frames, "seed": a.seed, "vblank_gap_max": fc_max,
                      "vblank_gap_end": fc_gap, "screen_still_max": sc_max,
                      "mode": md_run.w(r, 0xFF00AE), "loc": md_run.w(r, 0xFF0E98),
                      "iso": md_run.w(r, 0xFFDC00 + 0x550),
                      "iso_frames": iso_frames}))


if __name__ == "__main__":
    main()
