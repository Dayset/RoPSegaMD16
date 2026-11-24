#!/usr/bin/env python3
"""Exact check of the top-down plane against the map (#297, raised cells).

Runs ROM on ROUTE in Genesis Plus GX and, at the given frames (top-down
view, overworld), rebuilds every plane tile the view draws (the ring
rows cy0..cy0+15, columns cx0-3..cx0+28) from the ROM's own map data
with the painter rule in patches/topdown (cell y of height h covers
tile rows 2y-h..2y+1: top, then h face rows upside down) and compares
it with VRAM, priority bit masked in the HUD band rows.

  td_plane_check.py ROM ROUTE FRAMES     (FRAMES = 4500,5900)
"""
import struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_run import MD, w, parse_route  # noqa: E402
from md_vram import vdp_from_state  # noqa: E402
import td_height_mock as M  # noqa: E402

TD = 0xFFDC00


def tile_words(desc, word, base):
    d = desc[word & 0x1FF]
    if word & 0x1000:
        d >>= 8
    q = (((d >> 2) & 63) << 2) + base | (d & 3) << 11
    f = d & 3
    return [q + (p ^ f) for p in range(4)]          # TL TR BL BR


def expected(grid, desc, base, x, t, W, H):
    def cell(cx, cy):
        return int(grid[cy, cx]) if 0 <= cx < W and 0 <= cy < H else None
    y = (t + 7) >> 1
    while y > t >> 1:
        c = cell(x, y)
        if c is not None and (c >> 13) >= 2 * y - t:
            break
        y -= 1
    c = cell(x, y)
    if c is None:
        v = (base + 256 + 0x2000) | 0x8000
        return v, v, True
    p = t - 2 * y + (c >> 13)
    q = tile_words(desc, c, base)
    if p == 0:
        return q[0] | 0x8000, q[1] | 0x8000, True
    if p == 1:
        return q[2] | 0x8000, q[3] | 0x8000, True
    a, b = (q[2], q[3]) if (p - 2) % 2 == 0 else (q[0], q[1])
    return a ^ 0x1000, b ^ 0x1000, False


def main():
    rom = Path("rop-original.gen").read_bytes()
    grid = M.overworld(rom)
    desc = struct.unpack_from(">512H", rom, 0x1AE98)
    md = MD(sys.argv[1])
    seq = []
    for n, pad in parse_route(sys.argv[2]):
        seq += [pad] * n
    frames = sorted(int(f) for f in sys.argv[3].split(","))
    bad_total = 0
    for i in range(frames[-1] + 1):
        md.step(seq[i] if i < len(seq) else "")
        if i not in frames:
            continue
        r = md.ram()
        s = lambda a: (lambda v: v - 65536 * (v > 32767))(w(r, a))
        base, cx0, cy0 = s(TD + 0x18), s(TD + 0x12), s(TD + 0x14)
        vram = vdp_from_state(md.em.get_state())["vram"]
        W, H = s(TD + 0x1A), s(TD + 0x1C)
        if (W, H) != (352, 224) or s(TD + 0x32):
            print(f"frame {i}: not the overworld top-down view ({W}x{H})")
            continue
        camy = s(TD + 0x10)
        band = ((camy + 152) >> 3) & 31
        bad = n = 0
        for t in range(2 * cy0, 2 * cy0 + 32):
            rr = t & 31
            inband = ((rr - band) & 31) < 13
            for x in range(cx0 - 3, cx0 + 28):
                a, b, _ = expected(grid, desc, base, x, t, W, H)
                if inband:
                    a, b = a & 0x7FFF, b & 0x7FFF
                o = (rr * 64 + (2 * x & 63)) * 2
                ga, gb = struct.unpack_from(">HH", vram, o)
                n += 1
                if (ga, gb) != (a, b):
                    bad += 1
                    if bad <= 5:
                        print(f"  t={t} x={x}: vram {ga:04X} {gb:04X} want {a:04X} {b:04X}")
        print(f"frame {i}: cam ({s(TD + 0x0E)},{camy}) ring ({cx0},{cy0}): "
              f"{n - bad}/{n} tile pairs match")
        bad_total += bad
    return 1 if bad_total else 0


if __name__ == "__main__":
    sys.exit(main())
