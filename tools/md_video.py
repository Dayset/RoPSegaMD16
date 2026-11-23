#!/usr/bin/env python3
"""Side-by-side 60 fps video of ROMs on an input route
(GPGX via stable-retro + ffmpeg).

  md_video.py --route F --from N --to M --out video.mp4 ROM [ROM ...]

A ROM may be given as ROM@ROUTE@FROM to use its own route and start
frame (same length --to minus --from for every panel).
"""
import argparse, os, subprocess, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import md_run


def dump(rom, route, lo, hi, out):
    """Child process: one emulator per process (stable-retro limit)."""
    seq = []
    for n, pad in md_run.parse_route(route):
        seq += [pad] * n
    md = md_run.MD(rom)
    with open(out, "wb") as fh:
        for i in range(hi):
            md.step(seq[i] if i < len(seq) else "")
            if i >= lo:
                fh.write(md.screen().tobytes())


def frames(path, n):
    with open(path, "rb") as fh:
        for _ in range(n):
            b = fh.read(320 * 224 * 3)
            if len(b) < 320 * 224 * 3:
                return
            yield np.frombuffer(b, np.uint8).reshape(224, 320, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", required=True)
    ap.add_argument("--from", dest="lo", type=int, required=True)
    ap.add_argument("--to", dest="hi", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--dump", help=argparse.SUPPRESS)
    ap.add_argument("roms", nargs="+")
    a = ap.parse_args()
    if a.dump:
        dump(a.roms[0], a.route, a.lo, a.hi, a.dump)
        return
    raws = []
    for k, spec in enumerate(a.roms):
        rom, route, lo = (spec.split("@") + [a.route, str(a.lo)])[:3]
        lo = int(lo)
        raw = f"{a.out}.{k}.raw"
        subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--route", route,
                        "--from", str(lo), "--to", str(lo + a.hi - a.lo), "--out", a.out,
                        "--dump", raw, rom], check=True)
        raws.append(raw)
    gens = [frames(r, a.hi - a.lo) for r in raws]
    w, h = 320 * len(a.roms) + 8 * (len(a.roms) - 1), 224
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", "60", "-i", "-",
         "-vf", f"scale={w*a.scale}:{h*a.scale}:flags=neighbor",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", a.out],
        stdin=subprocess.PIPE)
    for imgs in zip(*gens):
        row = np.zeros((h, w, 3), np.uint8)
        for k, im in enumerate(imgs):
            row[:, k * 328:k * 328 + 320] = im
        ff.stdin.write(row.tobytes())
    ff.stdin.close()
    ff.wait()
    for r in raws:
        os.remove(r)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
