#!/usr/bin/env python3
"""Pre-drawn world for the big-ROM build (full-screen iso view, #307).

Renders the overworld and every room once with the $E358 port (both
terrain phases, tools/e358_atlas.py), cuts them into 8x8 tiles on the
iso view's global 8-px grid and writes one payload for $210000 (bank 4,
past the save RAM window):

  $210000  'OWA4', u16 areas (1 + 175)
  $210006  u32 per area: its header (bank 5), 0 = none. Area 0 is the
           overworld, area 1 + n is location n (chunk 77 + n).
  header   u16 tile rows R, cols C, block rows BR, block cols BC,
           s16 dy, dx (canvas tile = plane row + dy, global column +
           dx), u32 tile base, u32 blank tile id, then u32 per block
           (BR x BC, row-major): its record, 0 = all blank
  record   16x16 u8 pair index (row-major), then per pair two u24 tile
           ids (phase 0, phase 1); never crosses a 512 KB bank
  tiles    32 bytes per id at the tile base + 32 * id (one store)
  HUD      records 16-17 (pad picture, gauges) at the end of the ROM

Records and tiles are read at run time through the Sega mapper (slots
6 and 7). Cached in build/ per ROM md5 (a full render takes minutes).
"""
import hashlib
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e358_atlas import AtlasBuilder, overworld_cells, room_cells  # noqa: E402

OFFSET = 0x210000            # past the save RAM window
BS = 16                     # block edge, tiles
BANK = 0x80000
NLOC = 175                  # locations 0-174: chunks 77-251
SIZE = 0xA00000             # 10 MB ROM (Genesis Plus GX: 10 MB max)
HUD = SIZE - 0x10000        # records 16-17: VRAM 1834-2037, lent to the
                            # tile slots and restored from here
# measured on the live iso picture (overworld, origin (-2992, 88)):
# canvas x = global x + 3124, y = plane line; i.e. 132 - ox0, 88 - oy0
KX0, KY0 = 132, 88


def render(ab, cells):
    """-> (u0, t0, u1, t1, (dx, dy) in tiles)"""
    ph = []
    for p in (0, 1):
        canvas, (ox, oy), w, h = ab.render_canvas(cells, p)
        kx, ky = KX0 - ox, KY0 - oy
        pad = -kx % 8               # left pad: tiles on the global grid
        rows = np.frombuffer(canvas, np.uint8).reshape(h, w // 2)
        rows = np.pad(rows, ((0, 0), (pad // 2, (8 - pad) // 2)))
        uniq, tmap, _ = ab.cut_tiles(bytearray(rows.tobytes()), w + 8, h)
        assert ky % 8 == 0
        ph.append((uniq, tmap, ((kx + pad) // 8, ky // 8)))
    (u0, t0, k0), (u1, t1, k1) = ph
    assert k0 == k1 and t0.shape == t1.shape
    return u0, t0, u1, t1, k0


def pairs_blocks(g0, g1, blank):
    R, C = g0.shape
    BR, BC = (R + BS - 1) // BS, (C + BS - 1) // BS
    pad = lambda g: np.pad(g, ((0, BR * BS - R), (0, BC * BS - C)),
                           constant_values=blank)
    g0, g1 = pad(g0), pad(g1)
    blocks = []
    for br in range(BR):
        for bc in range(BC):
            a = g0[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            b = g1[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            if (a == blank).all() and (b == blank).all():
                blocks.append(None)
                continue
            key = a.astype(np.int64) << 20 | b
            pairs, idx = np.unique(key, return_inverse=True)
            assert len(pairs) <= 256
            blocks.append(idx.astype(np.uint8).tobytes() + b"".join(
                struct.pack(">I", int(p >> 20))[1:]
                + struct.pack(">I", int(p & 0xFFFFF))[1:] for p in pairs))
    return R, C, BR, BC, blocks


def store(tile_sets):
    """[(u0, t0, u1, t1)] -> (tiles, [(g0, g1)], blank id)"""
    allu, inv = np.unique(np.concatenate(
        [u for s in tile_sets for u in (s[0], s[2])]), axis=0,
        return_inverse=True)
    inv = inv.ravel()
    maps, off = [], 0
    for u0, t0, u1, t1 in tile_sets:
        g0 = inv[off:off + len(u0)][t0]
        off += len(u0)
        g1 = inv[off:off + len(u1)][t1]
        off += len(u1)
        maps.append((g0, g1))
    return allu, maps, int(np.where(~allu.any(axis=1))[0][0])


def areas(rom):
    ab = AtlasBuilder(rom)
    ow = render(ab, overworld_cells(ab))
    rooms = {}
    for n in range(NLOC):
        ch = 77 + n
        try:
            words = ab.chunk_words(ch)
        except Exception:
            continue
        edge = {121: 11, 1024: 32}.get(len(words))
        if edge:
            rooms[n] = render(ab, room_cells(ab, ch, edge))
    return ow, rooms


def layout(ow, rooms):
    out = bytearray(b"OWA4" + struct.pack(">H", 1 + NLOC)
                    + bytes(4 * (1 + NLOC)))
    groups = [([ow] + list(rooms.values()), [0] + [1 + n for n in rooms])]
    pending = []                # (header offset, area blocks, store index)
    stores = []
    for gi, (rs, ids) in enumerate(groups):
        allu, maps, blank = store([r[:4] for r in rs])
        stores.append(allu)
        for r, (g0, g1), aid in zip(rs, maps, ids):
            R, C, BR, BC, blocks = pairs_blocks(g0, g1, blank)
            dx, dy = r[4]
            hdr = len(out)
            struct.pack_into(">I", out, 6 + 4 * aid, OFFSET + hdr)
            out += struct.pack(">HHHHhhII", R, C, BR, BC, dy, dx, 0, blank)
            out += bytes(4 * BR * BC)
            pending.append((hdr, blocks, gi))
    assert len(out) <= BANK - (OFFSET % BANK), "headers past the first bank"
    for hdr, blocks, gi in pending:
        for i, rec in enumerate(blocks):
            if rec is None:
                continue
            pos = OFFSET + len(out)
            if pos // BANK != (pos + len(rec) - 1) // BANK:
                out += bytes(BANK - pos % BANK)
                pos = OFFSET + len(out)
            struct.pack_into(">I", out, hdr + 20 + 4 * i, pos)
            out += rec
    bases = []
    for allu in stores:
        out += bytes(-len(out) % 32)
        bases.append(OFFSET + len(out))
        out += allu.astype(np.uint8).tobytes()
    for hdr, _blocks, gi in pending:
        struct.pack_into(">I", out, hdr + 12, bases[gi])
    return bytes(out)


def hud_copy(rom):
    import decode_map
    b = decode_map.record_bytes(rom, 16) + decode_map.record_bytes(rom, 17)
    assert len(b) == 204 * 32, len(b)
    return b


def build(rom: bytes) -> bytes:
    cache = (Path(__file__).resolve().parent.parent / "build" /
             ("ow-atlas4-%s.bin" % hashlib.md5(rom).hexdigest()[:12]))
    if cache.is_file():
        return cache.read_bytes()
    data = layout(*areas(rom))
    assert OFFSET + len(data) <= HUD, "%X" % (OFFSET + len(data))
    data += bytes(HUD - OFFSET - len(data)) + hud_copy(rom)
    cache.parent.mkdir(exist_ok=True)
    cache.write_bytes(data)
    return data


if __name__ == "__main__":
    rom = Path(sys.argv[1] if len(sys.argv) > 1 else "rop-original.gen")
    d = build(rom.read_bytes())
    print("%d bytes, $%06X-$%06X" % (len(d), OFFSET, OFFSET + len(d) - 1))
