#!/usr/bin/env python3
"""Pre-drawn overworld for the 8 MB build (full-screen iso view).

Renders the whole overworld once with the $E358 port (both terrain
phases, tools/e358_atlas.py), cuts it into 8x8 tiles and writes one
payload for $280000 (bank 5; bank 4 stays free for the save RAM):

  $280000  'OWAT', u16 tile rows R, cols C, block rows BR, block cols BC,
           s16 canvas tile = global tile + (dx, dy) (global = TD_IGX px),
           u32 tile base (physical), u32 blank tile id
  $280018  u32 per block (BR x BC, row-major): physical address of the
           block record, 0 = all blank
  record   32x32 u16 pair index (row-major), then per pair two u32 tile
           ids (phase 0, phase 1); never crosses a 512 KB bank
  tiles    32 bytes per id at tile base + 32 * id

Read at run time through the Sega mapper window (slot 7, $380000).
The result is cached in build/ per ROM md5 (a render takes ~25 s).
"""
import hashlib
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e358_atlas import AtlasBuilder, overworld_cells  # noqa: E402

OFFSET = 0x280000
BS = 32                     # block edge, tiles
BANK = 0x80000
KX = 3124 + 4


def tiles_and_maps(rom):
    ab = AtlasBuilder(rom)
    cells = overworld_cells(ab)
    ph = []
    for p in (0, 1):
        canvas, origin, w, h = ab.render_canvas(cells, p)
        # measured on a live iso picture (#307): canvas x = global x +
        # 3124, y = global y; pad 4 px left so tiles sit on the global
        # 8-px grid (canvas tile = global tile + (KX / 8, 0))
        assert origin == (-2992, 88), origin
        rows = np.frombuffer(canvas, np.uint8).reshape(h, w // 2)
        rows = np.pad(rows, ((0, 0), (2, 2)))
        w += 8
        uniq, tmap, _ = ab.cut_tiles(bytearray(rows.tobytes()), w, h)
        ph.append((uniq, tmap, origin))
    (u0, t0, o0), (u1, t1, o1) = ph
    assert o0 == o1 and t0.shape == t1.shape
    allu, inv = np.unique(np.concatenate([u0, u1]), axis=0,
                          return_inverse=True)
    inv = inv.ravel()
    return allu, inv[:len(u0)][t0], inv[len(u0):][t1], (KX // 8, 0)


def layout(allu, g0, g1, origin):
    blank = int(np.where(~allu.any(axis=1))[0][0])
    R, C = g0.shape
    BR, BC = (R + BS - 1) // BS, (C + BS - 1) // BS
    pad = lambda g: np.pad(g, ((0, BR * BS - R), (0, BC * BS - C)),
                           constant_values=blank)
    g0, g1 = pad(g0), pad(g1)
    out = bytearray()
    head = struct.pack(">4sHHHHhhII", b"OWAT", R, C, BR, BC,
                       origin[0], origin[1], 0, blank)
    out += head + bytes(4 * BR * BC)
    table = len(head)
    for br in range(BR):
        for bc in range(BC):
            a = g0[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            b = g1[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            if (a == blank).all() and (b == blank).all():
                continue
            key = a.astype(np.int64) << 20 | b
            pairs, idx = np.unique(key, return_inverse=True)
            rec = idx.astype(">u2").tobytes() + b"".join(
                struct.pack(">II", int(p >> 20), int(p & 0xFFFFF))
                for p in pairs)
            pos = OFFSET + len(out)
            if pos // BANK != (pos + len(rec) - 1) // BANK:
                out += bytes(BANK - pos % BANK)
                pos = OFFSET + len(out)
            struct.pack_into(">I", out, table + 4 * (br * BC + bc), pos)
            out += rec
    out += bytes(-len(out) % 32)
    struct.pack_into(">I", out, 16, OFFSET + len(out))
    out += allu.astype(np.uint8).tobytes()
    return bytes(out)


def build(rom: bytes) -> bytes:
    cache = (Path(__file__).resolve().parent.parent / "build" /
             ("ow-atlas-%s.bin" % hashlib.md5(rom).hexdigest()[:12]))
    if cache.is_file():
        return cache.read_bytes()
    data = layout(*tiles_and_maps(rom))
    cache.parent.mkdir(exist_ok=True)
    cache.write_bytes(data)
    return data


if __name__ == "__main__":
    rom = Path(sys.argv[1] if len(sys.argv) > 1 else "rop-original.gen")
    d = build(rom.read_bytes())
    print("%d bytes, $%06X-$%06X" % (len(d), OFFSET, OFFSET + len(d) - 1))
