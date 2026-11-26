#!/usr/bin/env python3
"""Pre-drawn world for the big-ROM build (full-screen iso view, #307).

Renders the overworld and every room once with the $E358 port (both
terrain phases, tools/e358_atlas.py), cuts them into 8x8 tiles on the
iso view's global 8-px grid and writes one payload for $210000 (bank 4,
past the save RAM window):

  $210000  'OWA5', u16 areas (1 + 175)
  $210006  u32 per area: its header (bank 5), 0 = none. Area 0 is the
           overworld, area 1 + n is location n (chunk 77 + n).
  header   u16 tile rows R, cols C, block rows BR, block cols BC,
           s16 dy, dx (canvas tile = plane row + dy, global column +
           dx), u32 tile base, u32 blank tile id, then u32 per block
           (BR x BC, row-major): its record, 0 = all blank
  record   16x16 u8 pair index (row-major), u16 m, then m u24 phase-1
           ids, then a u24 phase-0 id per pair. Pairs 0..m-1 differ
           between the phases; pair k >= m shows its phase-0 tile in
           both. Even address, never crosses a 512 KB bank; identical
           records are stored once.
  tiles    32 bytes per id at the tile base + 32 * id (one store).
           Near twins (<= 2 pixels apart) are one tile: the one used
           most stands for the rest.
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
from e358_atlas import (AtlasBuilder, overworld_cells, room_cells,  # noqa: E402
                        EAST, SOUTH)

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


def owners(ab, cells, ox0, oy0, w, h):
    """-> per pixel: depth (wx + wy) of the cell that painted it last
    (the game's paint order), -1 where none did"""
    own = np.full((h, w), -1, np.int16)
    for wx, wy, tile in sorted(cells):
        fp = ab.footprint(tile, 0)
        if not fp:
            continue
        ox = wx * EAST[0] + wy * SOUTH[0] - ox0
        oy = wx * EAST[1] + wy * SOUTH[1] - oy0
        k = np.array([(px + ox, py + oy, m) for (px, py), (m, v)
                      in fp.items()], np.int64)
        hi = (k[:, 2] & 0xF0) == 0
        lo = (k[:, 2] & 0x0F) == 0
        own[k[hi, 1], k[hi, 0]] = wx + wy
        own[k[lo, 1], k[lo, 0] + 1] = wx + wy
    return own


def depths(own):
    """per 8x8 tile of an owner grid -> (smin, sup, 8-byte mask of the
    pixels deeper than smin); smin -1 = nothing painted"""
    h, w = own.shape
    t = own.reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3)
    t = t.reshape(h // 8, w // 8, 64).astype(np.int32)
    big = np.where(t < 0, 1 << 20, t)
    smin = big.min(axis=2)
    up = np.where(t > smin[..., None], t, 1 << 20).min(axis=2)
    none = smin >= 1 << 20
    smin = np.where(none, -1, smin)
    sup = np.where(up >= 1 << 20, smin, up)
    bits = (t > smin[..., None]) & ~none[..., None]
    msk = np.packbits(bits.reshape(h // 8, w // 8, 8, 8), axis=3)[..., 0]
    return smin, sup, msk


def render(ab, cells):
    """-> (u0, t0, u1, t1, (dx, dy) in tiles, (smin, sup, mask))"""
    ph = []
    dep = None
    for p in (0, 1):
        canvas, (ox, oy), w, h = ab.render_canvas(cells, p)
        kx, ky = KX0 - ox, KY0 - oy
        pad = -kx % 8               # left pad: tiles on the global grid
        rows = np.frombuffer(canvas, np.uint8).reshape(h, w // 2)
        rows = np.pad(rows, ((0, 0), (pad // 2, (8 - pad) // 2)))
        uniq, tmap, _ = ab.cut_tiles(bytearray(rows.tobytes()), w + 8, h)
        assert ky % 8 == 0
        if p == 0:
            own = np.pad(owners(ab, cells, ox, oy, w, h),
                         ((0, 0), (pad, 8 - pad)), constant_values=-1)
            dep = depths(own)
        ph.append((uniq, tmap, ((kx + pad) // 8, ky // 8)))
    (u0, t0, k0), (u1, t1, k1) = ph
    assert k0 == k1 and t0.shape == t1.shape
    return u0, t0, u1, t1, k0, dep


CLAMP = [0, 0]


def depth_bytes(smin, sup):
    """per position: (smin - atlas row + 16) << 3 | min(sup - smin, 7)"""
    R, C = smin.shape
    rel = smin - np.arange(R)[:, None] + 16
    up = np.minimum(sup - smin, 7)
    bad = (smin >= 0) & ((rel < 0) | (rel > 31))
    CLAMP[0] += int(bad.sum())
    CLAMP[1] += int((smin >= 0).sum())
    rel = np.clip(rel, 0, 31)
    return np.where(smin >= 0, rel << 3 | up, 0).astype(np.uint8)


def pairs_blocks(g0, g1, blank, dep):
    R, C = g0.shape
    BR, BC = (R + BS - 1) // BS, (C + BS - 1) // BS
    pad = lambda g: np.pad(g, ((0, BR * BS - R), (0, BC * BS - C)),
                           constant_values=blank)
    g0, g1 = pad(g0), pad(g1)
    db = np.pad(depth_bytes(*dep[:2]), ((0, BR * BS - R), (0, BC * BS - C)))
    blocks = []
    for br in range(BR):
        for bc in range(BC):
            a = g0[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            b = g1[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            if (a == blank).all() and (b == blank).all():
                blocks.append(None)
                continue
            key = a.astype(np.int64) << 20 | b
            pairs = np.unique(key)
            same = (pairs >> 20) == (pairs & 0xFFFFF)
            pairs = np.concatenate([pairs[~same], pairs[same]])
            m = int((~same).sum())
            assert len(pairs) <= 256
            at = {int(k): i for i, k in enumerate(pairs)}
            idx = np.array([at[int(k)] for k in key])
            u24 = lambda v: struct.pack(">I", int(v))[1:]
            blocks.append(idx.astype(np.uint8).tobytes()
                          + db[br * BS:(br + 1) * BS,
                               bc * BS:(bc + 1) * BS].tobytes()
                          + struct.pack(">H", m)
                          + b"".join(u24(p & 0xFFFFF) for p in pairs[:m])
                          + b"".join(u24(p >> 20) for p in pairs))
    return R, C, BR, BC, blocks


def twins(allu, uses, blank, maxd=2):
    """-> id map: each tile to the most used tile <= maxd pixels from it
    (any two such tiles agree on one of 3 pixel groups: bucket on each)"""
    n = len(allu)
    pix = np.stack([allu >> 4, allu & 15], axis=2).reshape(n, 64)
    cand = [[] for _ in range(n)]
    for g in range(3):
        cols = pix[:, g::3]
        key = np.unique(cols, axis=0, return_inverse=True)[1].ravel()
        order = np.argsort(key, kind="stable")
        ks = key[order]
        cut = np.flatnonzero(np.diff(ks)) + 1
        for grp in np.split(order, cut):
            if len(grp) < 2 or len(grp) > 4000:
                continue
            p = pix[grp]
            for i in range(len(grp) - 1):
                d = (p[i + 1:] != p[i]).sum(axis=1)
                for j in np.flatnonzero(d <= maxd):
                    a, b = int(grp[i]), int(grp[i + 1 + j])
                    cand[a].append(b)
                    cand[b].append(a)
    to = np.arange(n)
    done = np.zeros(n, bool)
    for t in np.argsort(-uses, kind="stable"):
        if done[t]:
            continue
        done[t] = True
        for o in cand[t]:
            if not done[o] and o != blank:
                done[o] = True
                to[o] = t
    return to


def id_masks(n, maps, deps):
    """-> (n, 8) per tile id: the pixel mask its positions have most"""
    ids = np.concatenate([g.ravel() for (g0, g1) in maps for g in (g0, g1)])
    mk = np.concatenate([d[2].reshape(-1, 8) for d in deps for _ in (0, 1)])
    mk = mk.view(">u8").ravel()
    order = np.lexsort((mk, ids))
    ids, mk = ids[order], mk[order]
    cut = np.flatnonzero((np.diff(ids) != 0) | (np.diff(mk) != 0)) + 1
    st = np.concatenate([[0], cut])
    cnt = np.diff(np.concatenate([st, [len(ids)]]))
    out = np.zeros(n, ">u8")
    best = np.zeros(n, np.int64)
    for a, c in zip(st, cnt):
        if c > best[ids[a]]:
            best[ids[a]] = c
            out[ids[a]] = mk[a]
    return out.view(np.uint8).reshape(n, 8)


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
    blank = int(np.where(~allu.any(axis=1))[0][0])
    uses = np.zeros(len(allu), np.int64)
    for g0, g1 in maps:
        np.add.at(uses, g0.ravel(), 1)
        np.add.at(uses, g1.ravel(), 1)
    to = twins(allu, uses, blank)
    keep = np.unique(to)
    new = np.zeros(len(allu), np.int64)
    new[keep] = np.arange(len(keep))
    to = new[to]
    return allu[keep], [(to[g0], to[g1]) for g0, g1 in maps], int(to[blank])


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
    out = bytearray(b"OWA6" + struct.pack(">H", 1 + NLOC)
                    + bytes(4 * (1 + NLOC)) + bytes(4))
    MBASE = 6 + 4 * (1 + NLOC)  # u32: the tile masks (8 bytes per id)
    groups = [([ow] + list(rooms.values()), [0] + [1 + n for n in rooms])]
    pending = []                # (header offset, area blocks, store index)
    stores = []
    for gi, (rs, ids) in enumerate(groups):
        allu, maps, blank = store([r[:4] for r in rs])
        stores.append((allu, id_masks(len(allu), maps, [r[5] for r in rs])))
        for r, (g0, g1), aid in zip(rs, maps, ids):
            R, C, BR, BC, blocks = pairs_blocks(g0, g1, blank, r[5])
            dx, dy = r[4]
            hdr = len(out)
            struct.pack_into(">I", out, 6 + 4 * aid, OFFSET + hdr)
            out += struct.pack(">HHHHhhII", R, C, BR, BC, dy, dx, 0, blank)
            out += bytes(4 * BR * BC)
            pending.append((hdr, blocks, gi))
    assert len(out) <= BANK - (OFFSET % BANK), "headers past the first bank"
    seen = {}
    for hdr, blocks, gi in pending:
        for i, rec in enumerate(blocks):
            if rec is None:
                continue
            if rec in seen:
                struct.pack_into(">I", out, hdr + 20 + 4 * i, seen[rec])
                continue
            out += bytes(len(out) & 1)
            pos = OFFSET + len(out)
            if pos // BANK != (pos + len(rec) - 1) // BANK:
                out += bytes(BANK - pos % BANK)
                pos = OFFSET + len(out)
            struct.pack_into(">I", out, hdr + 20 + 4 * i, pos)
            seen[rec] = pos
            out += rec
    bases = []
    for allu, masks in stores:
        out += bytes(-len(out) % 32)
        bases.append(OFFSET + len(out))
        out += allu.astype(np.uint8).tobytes()
        struct.pack_into(">I", out, MBASE, OFFSET + len(out))
        out += masks.tobytes()
    print("depth clamped: %d of %d" % tuple(CLAMP))
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
             ("ow-atlas6-%s.bin" % hashlib.md5(rom).hexdigest()[:12]))
    if cache.is_file():
        return cache.read_bytes()
    acache = cache.with_name("ow-areas6-%s.npz" % hashlib.md5(rom).hexdigest()[:12])
    import pickle
    if acache.is_file():
        ar = pickle.loads(acache.read_bytes())
    else:
        ar = areas(rom)
        acache.write_bytes(pickle.dumps(ar))
    data = layout(*ar)
    assert OFFSET + len(data) <= HUD, "%X" % (OFFSET + len(data))
    data += bytes(HUD - OFFSET - len(data)) + hud_copy(rom)
    cache.parent.mkdir(exist_ok=True)
    cache.write_bytes(data)
    return data


if __name__ == "__main__":
    rom = Path(sys.argv[1] if len(sys.argv) > 1 else "rop-original.gen")
    d = build(rom.read_bytes())
    print("%d bytes, $%06X-$%06X" % (len(d), OFFSET, OFFSET + len(d) - 1))
