#!/usr/bin/env python3
"""Pre-drawn world for the big-ROM build (full-screen iso view, #307).

Renders the overworld and every room once with the $E358 port (both
terrain phases, tools/e358_atlas.py), cuts them into 8x8 tiles on the
iso view's global 8-px grid and writes one payload for $210000 (bank 4,
past the save RAM window):

  $210000  'OWA8', u16 areas (1 + 175)
  $210006  u32 per area: its header (bank 5), 0 = none. Area 0 is the
           overworld, area 1 + n is location n (chunk 77 + n).
  header   u16 tile rows R, cols C, block rows BR, block cols BC,
           s16 dy, dx (canvas tile = plane row + dy, global column +
           dx), u32 tile base, u32 blank tile id, then u32 per block
           (BR x BC, row-major): its record, 0 = all blank
  header   +16: the area's filler pattern, 2 x 14 u32 ids (phase 0, 1;
           index (row % 2) 7 + column % 7): drawn past the canvas and in
           blocks not stored; then u16 rows, columns of the period an
           11x11 zone repeats with past its canvas (0 = the pattern)
  record   16x16 u8 pair index (row-major), u16 m, then m u24 phase-1
           ids, then a u24 phase-0 id per pair. Pairs 0..m-1 differ
           between the phases; pair k >= m shows its phase-0 tile in
           both. Even address, never crosses a 512 KB bank; identical
           records are stored once.
  tiles    32 bytes per id at the tile base + 32 * id (one store).
           Near twins (<= 3 pixels apart) are one tile: the one used
           most stands for the rest.
  HUD      records 16-17 (pad picture, gauges) and 6 (frame art) at
           the end of the ROM (put back when the view goes off)

Records and tiles are read at run time through the Sega mapper (slots
6 and 7). Cached in build/ per ROM md5 (a full render takes minutes).
"""
import hashlib
import struct
import sys
from pathlib import Path

import collections
import os

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
        k = k[(k[:, 0] >= 0) & (k[:, 0] < w - 1) & (k[:, 1] >= 0)
              & (k[:, 1] < h)]
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


def filler(ab, cells):
    """the cell repeated past the area's edge (no pink void): the one
    most common within 2 cells of the painted area's border"""
    paint = {(x, y): t for x, y, t in cells if ab.footprint(t, 0)}
    near = set()
    for (x, y) in paint:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in paint:
                near.update((x + i, y + j) for i in range(-2, 3)
                            for j in range(-2, 3))
                break
    cnt = collections.Counter(paint[p] for p in near if p in paint)
    return cnt.most_common(1)[0][0] if cnt else None


def lattice(ab, tile, p):
    """-> period image F (16 x 28 px) of the cell repeated everywhere, and
    its global origin: pixel (gx, gy) = F[(gy - y0) % 16, (gx - x0) % 28]"""
    cv, (ox, oy), w, h = ab.render_canvas(
        [(x, y, tile) for x in range(9) for y in range(9)], p)
    b = np.frombuffer(bytes(cv), np.uint8).reshape(h, w // 2)
    px = np.stack([b >> 4, b & 15], axis=2).reshape(h, w)
    x0, y0 = ox + w // 2 - 14, oy + h // 2 - 8   # mid-lattice: covered
    return px[y0 - oy:y0 - oy + 16, x0 - ox:x0 - ox + 28], x0, y0


TP = 12                     # torus period (cells): an 11x11 zone + a
TH, TW = 24, 42             # filler row and column; in tiles (0,192 px
                            # and 336,0 px: tile-aligned)


def torus(ab, cells, fill, p):
    """the zone repeated on a 12-cell lattice (its 12th row and column
    the filler cell), rendered and cut to a window around the zone of at
    least TH x TW tiles: the picture past it repeats with that period"""
    zone = dict(((x, y), t) for x, y, t in cells)
    _, (oxa, oya), wa, ha = ab.render_canvas(cells, p)
    assert wa <= TW * 8, wa
    ww, hh = TW * 8, max(ha, TH * 8)        # exactly one period across,
    xs = oxa - ((ww - wa) // 2) // 8 * 8 - 4  # on the global tile grid
    ys = oya - ((hh - ha) // 2) // 8 * 8    # (no pad columns: they would
    #                                         show a seam where it repeats)
    tc = []
    for i in range(-2, 3):
        for j in range(-2, 3):
            cx = (i - j) * TP * 14
            cy = (i + j) * TP * 8
            if abs(cx) > 600 or abs(cy) > 420:
                continue
            for y in range(TP):
                for x in range(TP):
                    tc.append((x + TP * i, y + TP * j, zone.get((x, y), fill)))
    cv, (ox, oy), w, h = ab.render_canvas(tc, p)
    b = np.frombuffer(bytes(cv), np.uint8).reshape(h, w // 2)
    x0, y0 = xs - ox, ys - oy
    assert x0 % 2 == 0 and y0 % 8 == 0 and x0 >= 0 and y0 >= 0
    b = b[y0:y0 + hh, x0 // 2:(x0 + ww) // 2]
    assert b.shape == (hh, ww // 2), (b.shape, hh, ww)
    return bytearray(b.tobytes()), (xs, ys), ww, hh, tc


def render(ab, cells, tor=False):
    """-> (u0, t0, u1, t1, (dx, dy) in tiles, (smin, sup, mask),
    (pattern tiles phase 0, phase 1): 2 x 7 tiles, row r % 2, col c % 7,
    (rows, cols) of the picture's period past the canvas, 0 = pattern)
    Pixels no cell paints show the filler cell's lattice, as does all
    past the canvas (the runtime repeats the pattern tiles there).
    tor: an 11x11 zone repeated all around instead (#308)"""
    ph = []
    dep = None
    fill = filler(ab, cells)
    tor = tor and fill is not None
    for p in (0, 1):
        if tor:
            canvas, (ox, oy), w, h, ocells = torus(ab, cells, fill, p)
        else:
            canvas, (ox, oy), w, h = ab.render_canvas(cells, p)
            ocells = cells
        kx, ky = KX0 - ox, KY0 - oy
        pad = -kx % 8               # left pad: tiles on the global grid
        rpad = 8 - pad              # (a torus window is cut on the grid)
        if tor:
            assert pad == 0, pad
            rpad = 0
        if p == 0:
            own = np.pad(owners(ab, ocells, ox, oy, w, h),
                         ((0, 0), (pad, rpad)), constant_values=-1)
            dep = depths(own)
        b = np.frombuffer(bytes(canvas), np.uint8).reshape(h, w // 2)
        px = np.stack([b >> 4, b & 15], axis=2).reshape(h, w)
        px = np.pad(px, ((0, 0), (pad, rpad)))
        H, Wp = px.shape
        if fill is not None:
            F, x0, y0 = lattice(ab, fill, p)
            gy = (np.arange(H)[:, None] + oy - y0) % 16
            gx = (np.arange(Wp)[None, :] - pad + ox - x0) % 28
            px = np.where(own < 0, F[gy, gx], px)
            ys = (np.arange(16)[:, None] + oy - y0) % 16
            xs = (np.arange(56)[None, :] - pad + ox - x0) % 28
            pat = F[ys, xs].reshape(2, 8, 7, 8).transpose(0, 2, 1, 3)
        else:
            pat = np.zeros((2, 7, 8, 8), np.uint8)
        pat = (pat[..., 0::2] << 4 | pat[..., 1::2]).reshape(14, 32)
        rows = (px[:, 0::2] << 4 | px[:, 1::2]).astype(np.uint8)
        uniq, tmap, _ = ab.cut_tiles(bytearray(rows.tobytes()), w + pad + rpad, h)
        assert ky % 8 == 0
        ph.append((uniq, tmap, ((kx + pad) // 8, ky // 8), pat.astype(np.uint8)))
    (u0, t0, k0, p0), (u1, t1, k1, p1) = ph
    assert k0 == k1 and t0.shape == t1.shape
    return u0, t0, u1, t1, k0, dep, (p0, p1), ((TH, TW) if tor else (0, 0))


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
    return np.where(smin >= 0, rel << 3 | up, 0xFF).astype(np.uint8)


def pairs_blocks(g0, g1, blank, dep, pid):
    """pid: (2, 2, 7) pattern ids (phase, row % 2, col % 7); a block all
    pattern is not stored (the runtime draws the pattern there)"""
    R, C = g0.shape
    BR, BC = (R + BS - 1) // BS, (C + BS - 1) // BS
    pad = lambda g: np.pad(g, ((0, BR * BS - R), (0, BC * BS - C)),
                           constant_values=blank)
    g0, g1 = pad(g0), pad(g1)
    rr = np.arange(BR * BS)[:, None] % 2      # past R / C: the pattern
    cc = np.arange(BC * BS)[None, :] % 7      # (never read there)
    out_ = np.ones_like(g0, bool)
    out_[:R, :C] = False
    g0 = np.where(out_, pid[0][rr, cc], g0)
    g1 = np.where(out_, pid[1][rr, cc], g1)
    db = np.pad(depth_bytes(*dep[:2]), ((0, BR * BS - R), (0, BC * BS - C)))
    blocks = []
    for br in range(BR):
        for bc in range(BC):
            a = g0[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            b = g1[br * BS:(br + 1) * BS, bc * BS:(bc + 1) * BS].ravel()
            rr = (br * BS + np.arange(BS))[:, None] % 2
            cc = (bc * BS + np.arange(BS))[None, :] % 7
            if (a == pid[0][rr, cc].ravel()).all() and \
                    (b == pid[1][rr, cc].ravel()).all():
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


TWIN = int(os.environ.get("ROP_TWIN", "3"))     # near-twin merge (px)
HALF = int(os.environ.get("ROP_HALF", "-1"))    # half-width tiles: those
# whose pixel pairs differ in at most HALF places (32 = all, -1 = none)


def halfx(t):
    """32-byte tiles -> as the runtime shows them stored half-width: the
    left pixel of each pair kept (pixels 0, 2, 4, 6), shown p p q q on
    even rows and p q p q on odd ones (a dither where they change)"""
    px = np.stack([t >> 4, t & 15], axis=2).reshape(-1, 8, 8)
    h = px[:, :, 0::2]                            # p0 q0 p1 q1
    out = np.repeat(h, 2, axis=2)                 # p p q q per byte
    odd = out[:, 1::2]
    odd[:, :, 0::4], odd[:, :, 1::4] = h[:, 1::2, 0::2], h[:, 1::2, 1::2]
    odd[:, :, 2::4], odd[:, :, 3::4] = h[:, 1::2, 0::2], h[:, 1::2, 1::2]
    out[:, 1::2] = odd
    out = out.reshape(-1, 64)
    return (out[:, 0::2] << 4 | out[:, 1::2]).astype(t.dtype)


def twins(allu, uses, blank, maxd=TWIN):
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


def store(tile_sets, gen=None):
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
    z = np.where(~allu.any(axis=1))[0]
    blank = int(z[0]) if len(z) else -1
    uses = np.zeros(len(allu), np.int64)
    for g0, g1 in maps:
        np.add.at(uses, g0.ravel(), 1)
        np.add.at(uses, g1.ravel(), 1)
    to = twins(allu, uses, blank)
    keep = np.unique(to)
    new = np.zeros(len(allu), np.int64)
    new[keep] = np.arange(len(keep))
    to = new[to]
    allu, maps = allu[keep], [(to[g0], to[g1]) for g0, g1 in maps]
    blank = int(to[blank]) if blank >= 0 else -1
    # half-width tiles next (stored as 16 bytes, pixels doubled at load),
    # material noise last (made at load from the shared field, not stored)
    err = ((allu >> 4) != (allu & 15)).sum(axis=1)
    gid = np.array([gen.get(x.tobytes(), -1) if gen else -1 for x in allu],
                   np.int64)
    isg = gid >= 0
    half = (err <= HALF) & ~isg
    full = ~half & ~isg
    nf, nh = int(full.sum()), int(half.sum())
    ng = NVAR * (max(gen.values()) // NVAR + 1) if gen else 0
    new = np.empty(len(allu), np.int64)
    new[full] = np.arange(nf)
    new[half] = nf + np.arange(nh)
    new[isg] = nf + nh + gid[isg]
    out = np.zeros((nf + nh + ng, 32), allu.dtype)
    out[new] = allu
    if gen:
        for b, k in gen.items():
            out[nf + nh + k] = np.frombuffer(b, np.uint8)
    out[nf:nf + nh] = halfx(out[nf:nf + nh])
    return (out, [(new[g0], new[g1]) for g0, g1 in maps],
            int(new[blank]) if blank >= 0 else -1, (nf, nh))


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
            rooms[n] = render(ab, room_cells(ab, ch, edge), edge == 11)
    return ow, rooms


NVAR = 8                    # noise variants per material and phase
SOLID = os.environ.get("ROP_SOLID", "1") == "1"  # materials one colour
NMIN = 24                   # uses before a tile counts as a texture


def textures(sets):
    """-> {tile bytes: material key}: tiles that are a material's dither
    (sand, grass, water, carpet...): used often, 2-4 colours, none 0, the
    minority colours only in specks (runs <= 2 across and down: brick
    and plank lines stay), one colour at least 45 %. Key: the colours
    and the dominant colour's share in eighths."""
    cnt = collections.Counter()
    for u0, t0, u1, t1 in sets:
        for u, t in ((u0, t0), (u1, t1)):
            n = np.bincount(t.ravel(), minlength=len(u))
            for k in np.flatnonzero(n):
                cnt[u[k].tobytes()] += int(n[k])
    out = {}
    for b, n in cnt.items():
        k = tex_key(b, n)
        if k is not None:
            out[b] = k
    return out


def tex_key(b, n=NMIN):
    """a tile's material key, or None: 2-4 colours (0 too: carpets),
    one at least 45 %, the others only in specks (runs <= 2 across and
    down: brick and plank lines stay); used seldom (< n) it counts only
    when nearly one colour (the dotted carpets and floors)"""
    a = np.frombuffer(b, np.uint8)
    px = np.stack([a >> 4, a & 15], axis=1).reshape(8, 8)
    cols, num = np.unique(px, return_counts=True)
    if not 2 <= len(cols) <= 4:
        return None
    dom = cols[num.argmax()]
    if num.max() < 29 or (n < NMIN and num.max() < (36 if SOLID else 56)):
        return None
    for c in cols:
        if c == dom:
            continue
        m = px == c
        if SOLID:                   # runs of 4 or more: a line, keep it
            if (m[:, :-3] & m[:, 1:-2] & m[:, 2:-1] & m[:, 3:]).any() or \
                    (m[:-3] & m[1:-2] & m[2:-1] & m[3:]).any():
                return None
        elif (m[:, :-2] & m[:, 1:-1] & m[:, 2:]).any() or \
                (m[:-2] & m[1:-1] & m[2:]).any():
            return None
    return (tuple(int(c) for c in cols),
            tuple(int(round(8 * k / 64)) for k in num))


SOLIDC = {}                 # colour set -> the colour all its tiles get


def solidc(key):
    """a solid material's colour: the colour its colour set has most of
    over all its tiles (one colour for all of a sea's tiles, whichever
    of its two colours each tile has more of: no patchwork)"""
    cols, share = key
    return SOLIDC.get(cols, cols[int(np.argmax(share))])


NFIELD = np.random.default_rng(308).integers(0, 256, (NVAR, 64)).astype(np.uint8)


def thresholds(key):
    """a material's 3 thresholds on the shared noise (255 = unused)"""
    cols, share = key
    cum = np.cumsum(share)[:-1] / sum(share)
    t = [min(255, int(round(256 * c))) for c in cum] + [255] * (4 - len(cols))
    return t[:3]


def variants(key, seed):
    """NVAR noise tiles of a material: ONE noise field shared by every
    material (#308), cut at its shares into its colours; seed 1 (water's
    other phase) takes the variants shifted by half"""
    cols, share = key
    if SOLID:                       # one colour: the material's main one
        c = np.full(4, solidc(key), np.uint8)
    else:
        c = np.array(list(cols) + [cols[-1]] * (4 - len(cols)), np.uint8)
    t = np.array(thresholds(key))
    f = np.roll(NFIELD, NVAR // 2 * seed, axis=0)
    v = c[(f[..., None] >= t).sum(axis=2)]
    return (v[:, 0::2] << 4 | v[:, 1::2]).astype(np.uint8)


def noise(r, tex, bank):
    """textures drawn as noise (#308): a texture tile becomes one of its
    material's NVAR variants, picked by a hash of the tile's place in
    its 16x16 block; the same variant in both phases where the tile does not
    animate (water's phases get their own)"""
    u0, t0, u1, t1, (kx, ky) = r[:5]
    R, C = t0.shape
    gr = np.arange(R)[:, None] % BS      # by the place in its block:
    gc = np.arange(C)[None, :] % BS      # alike blocks stay one record
    h = ((gr * 73856093) ^ (gc * 19349663)) & 0x7FFFFFFF
    h = (h * 2654435761 >> 13) % NVAR
    k0 = [tex.get(x.tobytes()) for x in u0]
    k1 = [tex.get(x.tobytes()) for x in u1]
    add0, add1 = {}, {}
    n0, n1 = t0.copy(), t1.copy()
    nu0, nu1 = [u0], [u1]

    def vid(add, nu, base, key, seed):
        if (key, seed) not in add:
            if (key, seed) not in bank:
                bank[key, seed] = variants(key, seed)
            add[key, seed] = base + sum(len(x) for x in nu[1:])
            nu.append(bank[key, seed])
        return add[key, seed]
    for y in range(R):
        for x in range(C):
            a, b = t0[y, x], t1[y, x]
            ka, kb = k0[a], k1[b]
            if ka is None or kb is None:
                continue
            same = u0[a].tobytes() == u1[b].tobytes()
            n0[y, x] = vid(add0, nu0, len(u0), ka, 0) + h[y, x]
            n1[y, x] = vid(add1, nu1, len(u1), kb, 0 if same else 1) + h[y, x]
    pats = []                           # the filler pattern too (#308)
    for ph, pt in enumerate(r[6]):
        pt = np.array(pt).copy()
        for k in range(len(pt)):
            key = tex.get(pt[k].tobytes()) or tex_key(pt[k].tobytes())
            if key is not None:
                if (key, 0) not in bank:
                    bank[key, 0] = variants(key, 0)
                pt[k] = bank[key, 0][k % NVAR]
        pats.append(pt)
    return ((np.concatenate(nu0), n0, np.concatenate(nu1), n1) + tuple(r[4:6])
            + (tuple(pats),) + tuple(r[7:]))


NCM = 128                   # materials a composite tile can stand on
COMPOSE = os.environ.get("ROP_COMPOSE", "0") == "1"   # off: see claude/tile-composition-plan.md


def compose(allu, nf, masks, mats, tex):
    """whole tiles -> ground material + object overlay (#308): where a
    tile's pixels equal a material texture tile (the lattice dither it
    was drawn on), those pixels are that material's ground, made at load
    from its noise; the other pixels (the object) are the overlay. Only
    pixels that were the texture itself become noise. Overlays dedupe
    across grounds and lattice phases and are stored sparse.
    -> (keep ids, old id -> new id or -(1 + composite), overlays, masks)"""
    px = np.stack([allu[:nf] >> 4, allu[:nf] & 15], axis=2).reshape(nf, 64)
    mi = {}
    for m, (key, seed) in enumerate(mats[:NCM]):
        if seed == 0:
            mi.setdefault(key, m)
    tb = [(np.frombuffer(b, np.uint8), mi[k]) for b, k in tex.items() if k in mi]
    tp = np.array([np.stack([t >> 4, t & 15], axis=1).reshape(64) for t, _ in tb])
    tm = np.array([m for _, m in tb])
    best = np.full(nf, -1)
    bcnt = np.zeros(nf, np.int64)
    for a in range(0, nf, 2048):                 # equal pixels per texture
        eq = (px[a:a + 2048, None, :] == tp[None, :, :]).sum(axis=2)
        k = eq.argmax(axis=1)
        best[a:a + 2048] = k
        bcnt[a:a + 2048] = eq[np.arange(len(k)), k]
    ok = (bcnt >= 24) & (px == 0).sum(axis=1).__eq__(0)
    keep = np.flatnonzero(~ok)
    new = np.empty(nf, np.int64)
    new[keep] = np.arange(len(keep))
    ov, omask = {}, []
    for t in np.flatnonzero(ok):
        k = best[t]
        o = np.where(px[t] == tp[k], 0, px[t]).astype(np.uint8)
        b = o.tobytes()
        if b not in ov:
            ov[b] = len(ov)
            omask.append(masks[t])
        new[t] = -(1 + (ov[b] * NCM + int(tm[k])))
    olist = [np.frombuffer(b, np.uint8) for b in ov]
    return keep, new, olist, np.array(omask, np.uint8).reshape(-1, 8)


def sparse(olist):
    """overlays -> (u32 offset per 8 overlays, bytes): each a 64-bit
    mask of its pixels (bit 63 = pixel 0), then those pixels, 2 a byte"""
    offs, out = [], bytearray()
    for i, o in enumerate(olist):
        if i % 8 == 0:
            offs.append(len(out))
        bits = 0
        for k in range(64):
            if o[k]:
                bits |= 1 << (63 - k)
        out += bits.to_bytes(8, "big")
        v = [int(x) for x in o if x]
        if len(v) % 2:
            v.append(0)
        out += bytes(v[i] << 4 | v[i + 1] for i in range(0, len(v), 2))
    return offs, bytes(out)


STATIC = os.environ.get("ROP_STATIC", "1") == "1"   # no tile animation:


def still(r):                       # phase 1 drawn as phase 0 (#308)
    return (r[0], r[1], r[0], r[1]) + tuple(r[4:6]) + ((r[6][0], r[6][0]),) + tuple(r[7:])


def layout(ow, rooms):
    if STATIC:
        ow = still(ow)
        rooms = {n: still(r) for n, r in rooms.items()}
    tex = textures([r[:4] for r in [ow] + list(rooms.values())])
    tot = collections.defaultdict(collections.Counter)
    for cols, share in tex.values():
        for c, sh in zip(cols, share):
            tot[cols][c] += sh
    SOLIDC.clear()
    SOLIDC.update({cols: cn.most_common(1)[0][0] for cols, cn in tot.items()})
    bank = {}
    print("textures: %d tiles drawn as noise" % len(tex))
    ow = noise(ow, tex, bank)
    rooms = {n: noise(r, tex, bank) for n, r in rooms.items()}
    mats = list(bank)                       # (material, seed) -> index
    gen = {}
    for m, ks in enumerate(mats):
        for v, t in enumerate(bank[ks]):
            gen.setdefault(t.tobytes(), m * NVAR + v)
    print("materials: %d (noise made at load, one shared field)" % len(mats))
    out = bytearray(b"OWA8" + struct.pack(">H", 1 + NLOC)
                    + bytes(4 * (1 + NLOC)) + bytes(36))
    MBASE = 6 + 4 * (1 + NLOC)  # u32: the tile masks (8 bytes per id)
    groups = [([ow] + list(rooms.values()), [0] + [1 + n for n in rooms])]
    pending = []                # (header offset, area blocks, store index)
    stores = []
    for gi, (rs, ids) in enumerate(groups):
        k7 = np.arange(14).reshape(2, 7)
        sets = [r[:4] for r in rs] + [(r[6][0], k7, r[6][1], k7) for r in rs]
        allu, maps, blank, nf = store(sets, gen)
        masks = id_masks(len(allu), maps[:len(rs)], [r[5] for r in rs])
        cinfo = None
        if COMPOSE:
            nfu, nh = nf
            keep, new, olist, omask = compose(allu, nfu, masks, mats, tex)
            nk = len(keep)
            ng = len(allu) - nfu - nh
            cb = nk + nh + ng
            to = np.empty(len(allu), np.int64)
            to[:nfu] = np.where(new >= 0, new, cb + (-new - 1))
            to[nfu:] = nk + np.arange(nh + ng)
            maps = [(to[g0], to[g1]) for g0, g1 in maps]
            blank = int(to[blank]) if blank >= 0 else -1
            allu = np.concatenate([allu[keep], allu[nfu:]])
            masks = np.concatenate([masks[keep], masks[nfu:]])
            nf = (nk, nh)
            cinfo = (cb, olist, omask)
            print("composed: %d tiles kept, %d overlays (from %d tiles)"
                  % (nk, len(olist), nfu - nk))
        pats, maps = maps[len(rs):], maps[:len(rs)]
        stores.append((allu, masks, nf, cinfo))
        for r, (g0, g1), pid, aid in zip(rs, maps, pats, ids):
            R, C, BR, BC, blocks = pairs_blocks(g0, g1, blank, r[5], pid)
            dx, dy = r[4]
            hdr = len(out)
            struct.pack_into(">I", out, 6 + 4 * aid, OFFSET + hdr)
            ptab = OFFSET + hdr + 20 + 4 * BR * BC
            out += struct.pack(">HHHHhhII", R, C, BR, BC, dy, dx, 0, ptab)
            out += bytes(4 * BR * BC)
            out += b"".join(struct.pack(">I", int(v))
                            for v in np.concatenate([pid[0].ravel(), pid[1].ravel()]))
            out += struct.pack(">HH", *r[7])
            pending.append((hdr, blocks, gi))
    out += bytes(-len(out) % 2)     # materials (first bank, read direct):
    struct.pack_into(">I", out, MBASE + 16, OFFSET + len(out))
    for (cols, share), seed in mats:    # 4 colours, 3 thresholds, shift
        c = list(cols) + [cols[-1]] * (4 - len(cols))
        if SOLID:                       # solid, not animated
            c = [solidc((cols, share))] * 4
        out += bytes(c + thresholds((cols, share)) + [NVAR // 2 * seed])
    struct.pack_into(">I", out, MBASE + 20, OFFSET + len(out))
    out += NFIELD.tobytes()             # the noise field all of them share
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
    for allu, masks, (nf, nh), cinfo in stores:
        out += bytes(-len(out) % 32)
        bases.append(OFFSET + len(out))
        out += allu[:nf].astype(np.uint8).tobytes()
        struct.pack_into(">III", out, MBASE + 4, nf, OFFSET + len(out),
                         nf + nh)
        h = allu[nf:nf + nh].reshape(-1, 8, 4)   # 2 bytes a row: pixels
        h = (h[..., 0::2] & 0xF0) | (h[..., 1::2] >> 4)  # 0, 2, 4, 6
        out += h.astype(np.uint8).tobytes()
        struct.pack_into(">I", out, MBASE, OFFSET + len(out))
        out += masks.tobytes()
        if cinfo:                       # composites: their base id, the
            cb, olist, omask = cinfo    # overlays' masks, offsets, data
            struct.pack_into(">I", out, MBASE + 24, cb)
            struct.pack_into(">I", out, MBASE + 32, OFFSET + len(out))
            out += omask.tobytes()
            offs, data = sparse(olist)
            out += bytes(-len(out) % 4)
            otab = len(out)
            struct.pack_into(">I", out, MBASE + 28, OFFSET + otab)
            out += bytes(4 * len(offs))
            # groups of 8 never cross a 512 KB bank (read via one slot)
            ends = offs[1:] + [len(data)]
            for i, (a, b) in enumerate(zip(offs, ends)):
                pos = OFFSET + len(out)
                if pos // BANK != (pos + (b - a) - 1) // BANK:
                    out += bytes(BANK - pos % BANK)
                    pos = OFFSET + len(out)
                struct.pack_into(">I", out, otab + 4 * i, pos)
                out += data[a:b]
        else:
            struct.pack_into(">I", out, MBASE + 24, 0xFFFFFF)
    print("depth clamped: %d of %d" % tuple(CLAMP))
    for hdr, _blocks, gi in pending:
        struct.pack_into(">I", out, hdr + 12, bases[gi])
    return bytes(out)


def hud_copy(rom):
    import decode_map
    b = decode_map.record_bytes(rom, 16) + decode_map.record_bytes(rom, 17)
    assert len(b) == 204 * 32, len(b)
    r6 = decode_map.record_bytes(rom, 6)  # frame art, VRAM 436-873
    assert len(r6) == 438 * 32, len(r6)
    return b + r6


def build(rom: bytes) -> bytes:
    cache = (Path(__file__).resolve().parent.parent / "build" /
             ("ow-atlas26-%s-t%d-h%d-c%d-s%d-a%d.bin" % (hashlib.md5(rom).hexdigest()[:12], TWIN, HALF, COMPOSE, SOLID, STATIC)))
    if cache.is_file():
        return cache.read_bytes()
    acache = cache.with_name("ow-areas10-%s.npz" % hashlib.md5(rom).hexdigest()[:12])
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
