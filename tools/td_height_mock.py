#!/usr/bin/env python3
"""Mock-up: height in the oblique top-down view (#255).

Renders a piece of the overworld from the ROM's own data (chunk cell
words, `$1AE98` descriptors, map tileset record 10, palette `$CCB18`)
the way the top-down patch draws it, then the same piece with cell
height (cell bits 13-15) as raised blocks: the top drawn 8 px (one
tile row) higher per level, the south face below it as the same tiles
at half brightness (what the VDP's shadow mode gives a priority-0
tile). Both sheared like the patch (floor(row/2) px per pixel row).

  td_height_mock.py ROM OUT.png [CX CY W H]
"""
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from decode_chunks import parse_table, decode_record  # noqa: E402
from export_assets import read_records  # noqa: E402


def overworld(rom):
    tab = parse_table(rom)
    grid = np.zeros((224, 352), np.uint16)
    for rec in range(77):
        data = bytes(decode_record(rom, tab[rec])[0])
        cy, cx = divmod(rec, 11)
        grid[cy * 32:cy * 32 + 32, cx * 32:cx * 32 + 32] = \
            np.frombuffer(data, ">u2").reshape(32, 32)
    return grid


def cell_tiles(rom):
    desc = struct.unpack_from(">512H", rom, 0x1AE98)
    tiles = np.frombuffer(read_records(rom, 0x96120, 0x9638C, 62)[10],
                          np.uint8).reshape(-1, 32)
    pal = struct.unpack_from(">16H", rom, 0xCCB18)
    rgb = np.array([((c >> 1 & 7) * 36, (c >> 5 & 7) * 36, (c >> 9 & 7) * 36)
                    for c in pal], np.uint8)

    def img(word):
        d = desc[word & 0x1FF]
        if word & 0x1000:
            d >>= 8
        t = tiles[(d >> 2) & 63]
        px = np.stack([t >> 4, t & 15], 1).reshape(8, 8)
        if d & 1:
            px = px[:, ::-1]
        if d & 2:
            px = px[::-1, :]
        return np.kron(rgb[px], np.ones((2, 2, 1), np.uint8))
    return img


def render(grid, img, x0, y0, w, h, raised):
    pad = 8 if raised else 0                 # rows of cells below for tall tops
    out = np.zeros((h * 16, w * 16, 3), np.uint8)
    for cy in range(y0, y0 + h + pad):       # north to south: painter order
        for cx in range(x0, x0 + w):
            word = int(grid[cy % 224, cx % 352])
            lift = ((word >> 13) & 7) * 8 if raised else 0
            top = img(word)
            sy = (cy - y0) * 16 - lift
            sx = (cx - x0) * 16
            for y in range(16 + lift):       # top, then the south face
                oy = sy + y
                if 0 <= oy < h * 16:
                    row = top[y] if y < 16 else top[15 - (y - 16) % 16] // 2
                    out[oy, sx:sx + 16] = row
    # shear: pixel row r moves floor(r/2) px left (pivot at the middle)
    sh = np.zeros_like(out)
    W = out.shape[1]
    for r in range(out.shape[0]):
        s = r // 2 - out.shape[0] // 4
        sh[r] = np.roll(out[r], -s, axis=0)
        if s > 0:
            sh[r, W - s:] = 0
        elif s < 0:
            sh[r, :-s] = 0
    return sh


def main():
    rom = open(sys.argv[1], "rb").read()
    out = sys.argv[2]
    cx, cy, w, h = (int(v) for v in sys.argv[3:7]) if len(sys.argv) > 6 else (96, 100, 22, 14)
    grid = overworld(rom)
    img = cell_tiles(rom)
    a = render(grid, img, cx, cy, w, h, False)
    b = render(grid, img, cx, cy, w, h, True)
    pic = Image.fromarray(np.concatenate([a, np.zeros((a.shape[0], 8, 3), np.uint8), b], 1))
    d = ImageDraw.Draw(pic)
    for x, t in ((4, "now: flat"), (a.shape[1] + 12, "height: +8 px per level, shadowed south face")):
        d.rectangle([x - 2, 2, x + 6 * len(t) + 2, 14], fill=(0, 0, 0))
        d.text((x, 3), t, fill=(255, 255, 255))
    pic.save(out)
    hs = (grid >> 13) & 7
    print("overworld cells by height:", np.bincount(hs.ravel(), minlength=8).tolist())


if __name__ == "__main__":
    main()
