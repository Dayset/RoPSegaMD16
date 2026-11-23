"""Shrink the offline $E358 world atlas to fit the 2 MB ROM (#252).

Step 1 is measurement (this module's ``measure``): cross-area tile
sharing, tilemap/tile compression with the game's own $DD5C format
(tools/dd5c.py — the game decodes $DD5C at runtime via routine
$DD5C, so $DD5C blobs are runtime-decodable; zlib is a reference
point only), tile distribution, and the phase-1 cost.

Step 2 is the shrunk representation (``build_shrunk``): the smallest
combination that fits 1,048,576 usable bytes with >= 10% margin
(target <= ~940,000 bytes). The flat atlas output of e358_atlas.py
keeps working -- the compressed form is an addition, not a
replacement of the verified path.

Layout notes (measured, not assumed):
  * Per-area tile sets cannot use u16 indices for the overworld:
    the overworld area has 75,310 distinct tiles > 65,535. The flat
    atlas's u16 tilemap_bytes therefore UNDERSTATE a correct flat
    representation. The shrunk form uses per-canvas tile sets
    (each canvas's own distinct set, u16 indices valid -- see
    ``measure`` for the per-canvas max) remapped through a global
    deduplicated tile table.
  * Load unit is one canvas: tilemaps and tile sets are compressed
    per canvas, so a runtime loader can decompress one canvas at a
    time into RAM instead of staging a whole area.

Usage:
  python3 tools/e358_shrink.py measure [--rom R] [--out JSON]
      [--phase1] [--skip-phase1]
  python3 tools/e358_shrink.py shrink [--rom R] [--out JSON]
      [--measure JSON]   (build the shrunk representation)
"""

import argparse
import json
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from dd5c import dd5c_compress  # noqa: E402  (game's own $DD5C encoder)
from e358_atlas import (AtlasBuilder, overworld_cells,  # noqa: E402
                        room_cells)

REPO = Path(__file__).resolve().parent.parent
ROM_DEFAULT = REPO / "rop-original.gen"
BUDGET = 1_048_576
TARGET = 940_000


def _u16le(arr):
    return np.asarray(arr, dtype="<u2").tobytes()


def index_width(n):
    """Bytes per tilemap index holding values 0..n-1."""
    if n <= 256:
        return 1
    if n <= 65536:
        return 2
    if n <= 16_777_216:
        return 3
    return 4


def pack_indices(arr, width):
    """Pack integer indices little-endian at the given width."""
    a = np.asarray(arr, dtype=np.int64).ravel()
    if width == 1:
        return a.astype(np.uint8).tobytes()
    if width == 2:
        return a.astype("<u2").tobytes()
    if width == 4:
        return a.astype("<u4").tobytes()
    # width == 3: manual pack (no numpy 3-byte dtype)
    out = bytearray(len(a) * 3)
    for i, v in enumerate(a):
        out[3 * i] = v & 0xFF
        out[3 * i + 1] = (v >> 8) & 0xFF
        out[3 * i + 2] = (v >> 16) & 0xFF
    return bytes(out)


def _dd5c(data, method="okumura"):
    t0 = time.time()
    out = dd5c_compress(bytes(data), method=method)
    return len(out), time.time() - t0


def _zlib(data):
    t0 = time.time()
    out = zlib.compress(bytes(data), 9)
    return len(out), time.time() - t0


def build_canvases(ab, phase=0):
    """Rebuild every canvas with per-canvas tile sets kept.

    Returns a list of dicts: {area, label, uniq (n,32) uint8,
    tmap (rows,cols) int64 canvas-local indices, grid, canvas_px}.
    Mirrors e358_atlas.build_area but keeps the per-canvas sets
    instead of joining them into per-area sets.
    """
    specs = [("overworld", [("overworld", overworld_cells(ab))]),
             ("big-rooms",
              [("chunk-%d" % ch, room_cells(ab, ch, 32))
               for ch in range(230, 252)]),
             ("small-rooms",
              [("chunk-%d" % ch, room_cells(ab, ch, 11))
               for ch in range(77, 230)])]
    out = []
    for area, canvases in specs:
        for label, cells in canvases:
            canvas, origin, w_px, h_px = ab.render_canvas(cells, phase)
            uniq, tmap, _w = ab.cut_tiles(canvas, w_px, h_px)
            out.append({"area": area, "label": label, "uniq": uniq,
                        "tmap": tmap, "origin": origin,
                        "canvas_px": (w_px, h_px),
                        "grid": (int(tmap.shape[0]), int(tmap.shape[1]))})
    return out


def global_dedup(canvases):
    """Deduplicate tile patterns across ALL canvases.

    Returns (global_tiles (n,32) uint8, per-canvas global-index maps).
    """
    joined = np.concatenate([c["uniq"] for c in canvases], axis=0)
    uniq, inverse = np.unique(joined, axis=0, return_inverse=True)
    maps = []
    off = 0
    for c in canvases:
        n = len(c["uniq"])
        local_to_global = inverse[off:off + n]
        off += n
        maps.append(local_to_global[c["tmap"].ravel()].reshape(
            c["tmap"].shape))
    return uniq, maps


def tile_distribution(tiles):
    """Distribution of tile patterns: solid / near-solid / other."""
    n = len(tiles)
    first = tiles[:, 0:1]
    solid = int(np.sum(np.all(tiles == first, axis=1)))
    # distinct byte values per tile
    vals = np.array([len(np.unique(tiles[i])) for i in range(n)])
    le2 = int(np.sum(vals <= 2))
    le4 = int(np.sum(vals <= 4))
    zero = int(np.sum(np.all(tiles == 0, axis=1)))
    return {"n": n, "solid_all_same_byte": solid, "all_zero": zero,
            "distinct_byte_values<=2": le2,
            "distinct_byte_values<=4": le4}


GREEDY_MAX_BYTES = 200_000


def compress_report(name, data):
    """Sizes of data under $DD5C (okumura) and zlib (ref).

    The greedy $DD5C encoder is also tried on small blobs, but it is
    pathologically slow on multi-MB noisy inputs (the 4.34 MB global
    tile set ran > 2 min without finishing, vs 26.8 s for okumura),
    so blobs over GREEDY_MAX_BYTES skip it. Okumura is the canonical
    1992 encoder (byte-identical on all 404 known records) and is
    the one the shrunk form uses.
    """
    d = bytes(data)
    print("  compress %s: %d bytes..." % (name, len(d)), flush=True)
    ok, t_ok = _dd5c(d, "okumura")
    print("    okumura %d in %.1fs" % (ok, t_ok), flush=True)
    if len(d) <= GREEDY_MAX_BYTES:
        gr, t_gr = _dd5c(d, "greedy")
        print("    greedy %d in %.1fs" % (gr, t_gr), flush=True)
    else:
        gr, t_gr = None, 0.0
        print("    greedy skipped (> %d bytes)" % GREEDY_MAX_BYTES,
              flush=True)
    zl, t_zl = _zlib(d)
    best = ok if gr is None else min(ok, gr)
    return {"name": name, "raw": len(d),
            "dd5c_okumura": ok, "dd5c_greedy": gr, "zlib9": zl,
            "dd5c_best": best,
            "dd5c_time_s": round(t_ok + t_gr, 2)}


def delta_encode(arr, width):
    """Row-major first differences (mod 2**(8*width)) packed at width.

    Tilemaps are mostly runs of the same index, so differences are
    usually 0 -- highly compressible by LZSS. Exact: the decoder
    rebuilds indices by cumulative addition mod 2**(8*width), which
    recovers the originals because every index is < 2**(8*width).
    """
    flat = np.asarray(arr, dtype=np.int64).ravel()
    diffs = np.diff(flat, prepend=flat[0]) % (1 << (8 * width))
    return pack_indices(diffs, width)


def _swap_nibbles(b):
    return ((b & 0x0F) << 4) | ((b >> 4) & 0x0F)


def flip_h_tile(t):
    """Horizontal flip of one 32-byte 4bpp tile (VDP flip-H)."""
    out = bytearray(32)
    for r in range(8):
        row = t[4 * r:4 * r + 4]
        for j in range(4):
            out[4 * r + j] = _swap_nibbles(row[3 - j])
    return bytes(out)


def flip_v_tile(t):
    """Vertical flip of one 32-byte 4bpp tile (VDP flip-V)."""
    out = bytearray(32)
    for r in range(8):
        out[4 * r:4 * r + 4] = t[4 * (7 - r):4 * (7 - r) + 4]
    return bytes(out)


def shift_h_tile(t, nbytes, wrap):
    """Shift a tile horizontally by nbytes*2 pixels (nbytes bytes/row).

    vacated bytes are 0 (wrap=False) or wrap around (wrap=True).
    A shifted tile that equals another tile in the set can be stored
    as (other tile + shift) instead of as its own 32 bytes.
    """
    out = bytearray(32)
    for r in range(8):
        row = t[4 * r:4 * r + 4]
        for j in range(4):
            src = j - nbytes
            if 0 <= src < 4:
                out[4 * r + j] = row[src]
            elif wrap:
                out[4 * r + j] = row[src % 4]
            else:
                out[4 * r + j] = 0
    return bytes(out)


def bitplane_split(tiles):
    """Reorder tile bytes into 4 bitplanes (8 bytes each per tile).

    4bpp pixels: plane p holds bit p of every pixel. Planar data
    lets LZSS match within a plane's stream instead of across mixed
    nibbles.
    """
    out = bytearray()
    for t in tiles:
        px = []
        for b in t:
            px.append((b >> 4) & 0xF)
            px.append(b & 0xF)
        for p in range(4):
            for r in range(8):
                byte = 0
                for k in range(8):
                    byte |= ((px[r * 8 + k] >> p) & 1) << (7 - k)
                out.append(byte)
    return bytes(out)


def front_coded(tiles):
    """Sort tiles lexicographically; store (prefix-len, suffix) pairs.

    Adjacent sorted tiles share long prefixes, so the suffix stream
    is mostly short -- and $DD5C then sees the remaining bytes.
    Returns (stream_bytes, total_suffix_bytes).
    """
    srt = sorted(tiles)
    out = bytearray()
    total_suffix = 0
    prev = b""
    for t in srt:
        n = 0
        while n < 32 and n < len(prev) and prev[n] == t[n]:
            n += 1
        out.append(n)
        out += t[n:]
        total_suffix += 32 - n
        prev = t
    return bytes(out), total_suffix


def measure_tile_transforms(gtiles):
    """How much do flip/shift/front-coding/bitplanes shrink the
    global tile set? All counts are exact (hash-based)."""
    tiles = [bytes(t) for t in gtiles.tolist()]
    tile_set = set(tiles)
    # Flip canonicalization: the VDP tilemap carries flip-H/flip-V
    # bits for free, so a tile equal to another tile's flip needs no
    # own 32 bytes -- the map entry references the stored tile with
    # the flip bit set.
    canon = set()
    for t in tiles:
        variants = [t, flip_h_tile(t), flip_v_tile(t),
                    flip_v_tile(flip_h_tile(t))]
        canon.add(min(variants))
    # 2px (1-byte) horizontal shifts, zero-fill and wraparound.
    shift_zero = set()
    shift_wrap = set()
    for t in tiles:
        if (shift_h_tile(t, 1, False) in tile_set
                or shift_h_tile(t, -1, False) in tile_set):
            shift_zero.add(t)
        if (shift_h_tile(t, 1, True) in tile_set
                or shift_h_tile(t, -1, True) in tile_set):
            shift_wrap.add(t)
    # Front-coding (sorted delta).
    fc_stream, suffix_total = front_coded(tiles)
    fc = compress_report("front-coded global tiles", fc_stream)
    # Bitplane split.
    bp = bitplane_split(tiles)
    bp_rep = compress_report("bitplane-split global tiles", bp)
    # Per-canvas tile $DD5C is measured by the caller (needs canvases).
    return {
        "flip_canonical_tiles": len(canon),
        "flip_canonical_tile_bytes": len(canon) * 32,
        "tiles_matching_a_shifted_sibling_zero_fill": len(shift_zero),
        "tiles_matching_a_shifted_sibling_wrap": len(shift_wrap),
        "front_coded_stream_bytes": len(fc_stream),
        "front_coded_suffix_bytes": suffix_total,
        "front_coded_dd5c": fc,
        "bitplane_split_dd5c": bp_rep,
    }


def measure(ab, phase1=False):
    """Measure every shrink lever on the phase-0 atlas (and phase 1
    if requested). Returns a JSON-able report dict."""
    t0 = time.time()
    print("step: build phase-0 canvases", flush=True)
    canvases = build_canvases(ab, phase=0)
    print("step: phase-0 canvases built in %.1fs" % (time.time() - t0),
          flush=True)
    per_area_sum = sum(len(c["uniq"]) for c in canvases)
    per_canvas_max = max(len(c["uniq"]) for c in canvases)
    per_canvas_mean = per_area_sum / len(canvases)
    print("canvases: %d, per-area distinct sum: %d, per-canvas "
          "distinct max/mean: %d/%.1f"
          % (len(canvases), per_area_sum, per_canvas_max,
             per_canvas_mean))
    gtiles, gmaps = global_dedup(canvases)
    print("GLOBAL distinct tiles: %d (vs per-area sum %d, sharing "
          "saves %d tiles / %d bytes)"
          % (len(gtiles), per_area_sum,
             per_area_sum - len(gtiles),
             (per_area_sum - len(gtiles)) * 32))
    dist = tile_distribution(gtiles)
    print("tile distribution: %s" % dist)
    rep = {"canvases": len(canvases),
           "per_area_distinct_sum": per_area_sum,
           "per_canvas_distinct_max": int(per_canvas_max),
           "per_canvas_distinct_mean": round(per_canvas_mean, 1),
           "global_distinct_tiles": int(len(gtiles)),
           "global_tile_bytes": int(len(gtiles) * 32),
           "tile_distribution": dist,
           "areas": {}, "tilemaps": {}, "tiles": {}}
    # --- tile bytes: global dedup set, compressed ---
    rep["tiles"]["global_raw"] = int(len(gtiles) * 32)
    rep["tiles"]["global_compressed"] = compress_report(
        "global tile bytes", gtiles.tobytes())
    print("global tile bytes %d -> $DD5C %d / zlib %d"
          % (len(gtiles) * 32,
             rep["tiles"]["global_compressed"]["dd5c_best"],
             rep["tiles"]["global_compressed"]["zlib9"]))
    # --- tile transforms: flips (free via VDP flip bits), shifts,
    # front-coding, bitplanes ---
    print("step: tile transforms", flush=True)
    rep["tile_transforms"] = measure_tile_transforms(gtiles)
    tt = rep["tile_transforms"]
    print("flip-canonical tiles: %d (%d bytes); shifted siblings "
          "(zero-fill/wrap): %d/%d; front-coded stream %d bytes "
          "(suffix %d) -> $DD5C %d; bitplane split -> $DD5C %d"
          % (tt["flip_canonical_tiles"],
             tt["flip_canonical_tile_bytes"],
             tt["tiles_matching_a_shifted_sibling_zero_fill"],
             tt["tiles_matching_a_shifted_sibling_wrap"],
             tt["front_coded_stream_bytes"],
             tt["front_coded_suffix_bytes"],
             tt["front_coded_dd5c"]["dd5c_best"],
             tt["bitplane_split_dd5c"]["dd5c_best"]))
    # --- tiles compressed per canvas (small blobs, 4 KB window) ---
    pc_tiles = 0
    pc_tiles_z = 0
    for c in canvases:
        data = c["uniq"].tobytes()
        pc_tiles += compress_report(
            "tiles " + c["label"], data)["dd5c_best"]
        pc_tiles_z += _zlib(data)[0]
    rep["tiles"]["per_canvas_dd5c_total"] = pc_tiles
    rep["tiles"]["per_canvas_zlib_total"] = pc_tiles_z
    print("tiles per-canvas $DD5C total %d / zlib total %d"
          % (pc_tiles, pc_tiles_z))
    # --- tilemaps: per-area (area-local indices) and global remap ---
    # Index widths are width-aware: the overworld area (75,310
    # distinct) and the global set both exceed u16, so a correct
    # flat tilemap needs 3-byte indices there. Widths are reported
    # per area / globally.
    for area in ("overworld", "big-rooms", "small-rooms"):
        idxs = [i for i, c in enumerate(canvases)
                if c["area"] == area]
        # area-local index width: distinct tiles in this area's
        # canvases (per-canvas sets joined, as in e358_atlas).
        area_n = sum(len(canvases[i]["uniq"]) for i in idxs)
        # (union, not sum, drives the true width; recompute below)
        w_local = index_width(
            len(set().union(*[set(map(bytes, canvases[i]["uniq"]))
                               for i in idxs])) if idxs else 1)
        raw_local = b"".join(pack_indices(canvases[i]["tmap"], w_local)
                             for i in idxs)
        w_global = index_width(len(gtiles))
        raw_global = b"".join(pack_indices(gmaps[i], w_global)
                              for i in idxs)
        rep["tilemaps"][area] = {
            "canvases": len(idxs),
            "index_width_local": w_local,
            "index_width_global": w_global,
            "raw_local_bytes": len(raw_local),
            "compressed_local": compress_report(
                area + " tilemap (area-local)", raw_local),
            "compressed_local_delta": compress_report(
                area + " tilemap (area-local, delta)",
                b"".join(delta_encode(canvases[i]["tmap"], w_local)
                         for i in idxs)),
            "raw_global_bytes": len(raw_global),
            "compressed_global": compress_report(
                area + " tilemap (global)", raw_global),
        }
        print("%s tilemap: raw local %d (u%d) -> $DD5C %d "
              "(delta %d, zlib %d); raw global %d (u%d) -> $DD5C %d"
              % (area, len(raw_local), w_local,
                 rep["tilemaps"][area]["compressed_local"]["dd5c_best"],
                 rep["tilemaps"][area]["compressed_local_delta"][
                     "dd5c_best"],
                 rep["tilemaps"][area]["compressed_local"]["zlib9"],
                 len(raw_global), w_global,
                 rep["tilemaps"][area]["compressed_global"][
                     "dd5c_best"]))
    # per-canvas tilemap compression (the runtime load unit)
    pc = []
    for i, c in enumerate(canvases):
        w = index_width(len(c["uniq"]))
        raw = pack_indices(c["tmap"], w)
        comp = compress_report(c["label"] + " tilemap", raw)
        pc.append({"label": c["label"], "area": c["area"],
                   "entries": int(c["tmap"].size),
                   "distinct": int(len(c["uniq"])),
                   "index_width": w,
                   "raw": len(raw), "dd5c_best": comp["dd5c_best"]})
    rep["tilemaps"]["per_canvas_total_dd5c"] = sum(
        x["dd5c_best"] for x in pc)
    rep["tilemaps"]["per_canvas_total_raw"] = sum(
        x["raw"] for x in pc)
    rep["tilemaps"]["per_canvas_max_dd5c"] = max(
        x["dd5c_best"] for x in pc)
    print("tilemaps per-canvas: raw total %d -> $DD5C total %d "
          "(max single canvas %d)"
          % (rep["tilemaps"]["per_canvas_total_raw"],
             rep["tilemaps"]["per_canvas_total_dd5c"],
             rep["tilemaps"]["per_canvas_max_dd5c"]))
    # --- phase 1 ---
    if phase1:
        canvases1 = build_canvases(ab, phase=1)
        gtiles1, _maps1 = global_dedup(canvases1)
        # tiles in the phase-1 set that are NOT in the phase-0 set
        g0 = set(map(bytes, gtiles.tolist()))
        extra = [t for t in gtiles1.tolist() if bytes(t) not in g0]
        extra_bytes = b"".join(bytes(t) for t in extra)
        rep["phase1"] = {
            "global_distinct_tiles": int(len(gtiles1)),
            "tiles_not_in_phase0": len(extra),
            "extra_tile_bytes": len(extra) * 32,
            "extra_tile_bytes_dd5c": compress_report(
                "phase-1-only tiles", extra_bytes)["dd5c_best"]
            if extra else 0,
        }
        print("phase 1: global distinct %d, tiles not in phase 0: "
              "%d (%d bytes raw, $DD5C %d)"
              % (len(gtiles1), len(extra), len(extra) * 32,
                 rep["phase1"]["extra_tile_bytes_dd5c"]))
    rep["build_s"] = round(time.time() - t0, 1)
    return rep


def measure_cellmaps(ab):
    """Tilemaps as CELL-word maps instead of tile-index maps.

    The atlas tilemaps have one entry per 8x8 tile (582,770 entries
    overworld). A cell map has one u16 entry per map CELL (78,848
    overworld cells) holding the cell's tile word (2,614 distinct).
    A loader would expand cells to tiles through the footprint
    library -- NOT built here, and not trivial -- so this is a
    bound on what the map side could ever save, not a proposal.
    """
    ow = b"".join(struct.pack(">H", w)
                  for ch in range(77)
                  for w in ab.chunk_words(ch))
    big = b"".join(struct.pack(">H", w)
                   for ch in range(230, 252)
                   for w in ab.chunk_words(ch))
    small = b"".join(struct.pack(">H", w)
                     for ch in range(77, 230)
                     for w in ab.chunk_words(ch))
    rep = {}
    for name, data in (("overworld", ow), ("big-rooms", big),
                       ("small-rooms", small)):
        rep[name] = {"cells": len(data) // 2, "raw_bytes": len(data),
                     "compressed": compress_report(
                         name + " cell map", data)}
        print("%s cell map: %d cells, raw %d -> $DD5C %d (zlib %d)"
              % (name, len(data) // 2, len(data),
                 rep[name]["compressed"]["dd5c_best"],
                 rep[name]["compressed"]["zlib9"]))
    rep["total_dd5c"] = sum(rep[k]["compressed"]["dd5c_best"]
                            for k in ("overworld", "big-rooms",
                                      "small-rooms"))
    rep["total_raw"] = sum(rep[k]["raw_bytes"]
                           for k in ("overworld", "big-rooms",
                                     "small-rooms"))
    print("cell maps total: raw %d -> $DD5C %d"
          % (rep["total_raw"], rep["total_dd5c"]))
    return rep


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--rom", default=str(ROM_DEFAULT))
    m.add_argument("--out", default="")
    m.add_argument("--phase1", action="store_true",
                   help="also build the phase-1 atlas and measure its "
                        "extra tiles vs phase 0")
    c = sub.add_parser("cellmaps")
    c.add_argument("--rom", default=str(ROM_DEFAULT))
    c.add_argument("--out", default="")
    a = ap.parse_args()
    if a.cmd == "measure":
        rom = Path(a.rom).read_bytes()
        ab = AtlasBuilder(rom)
        rep = measure(ab, phase1=a.phase1)
        out = a.out or str(REPO / "build" / "e358-shrink-measure.json")
        Path(out).write_text(json.dumps(rep, indent=1))
        print("wrote %s" % out)
        return 0
    if a.cmd == "cellmaps":
        rom = Path(a.rom).read_bytes()
        ab = AtlasBuilder(rom)
        rep = measure_cellmaps(ab)
        out = a.out or str(REPO / "build" / "e358-cellmaps.json")
        Path(out).write_text(json.dumps(rep, indent=1))
        print("wrote %s" % out)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
