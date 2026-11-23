"""Offline world-atlas renderer for the $E358 port (Track A, #252).

Renders every map cell once with the port, stamps the footprints
onto per-area isometric canvases, cuts them into 8x8 tiles,
deduplicates, and reports exact tile/tilemap/atlas byte counts plus
the 2 MB fit verdict.

Key fact (verified empirically in the probe below, not assumed):
a cell's footprint -- the (mask, value) write triples of its
$E358 calls -- is EXACTLY translation-invariant. The same tile word
rendered at window (4,4), (5,4) and (4,5) gives identical triples
after shifting by the isometric steps East (+14,+8) and South
(-14,+8). The (row-col) dispatch "variants" do not change the
drawing, only which handler writes each byte. So the atlas IS the
game's world image: any live window buffer is a crop of it (up to
figure bytes).

Method:
  * tile word -> footprint: the cell's $E358 calls at canonical
    window position (4,4) (d0=196, d1=82), traced with E358.call
    (trace=...), composited per byte into one net (mask, value)
    triple. The per-byte sequence (m1,v1),(m2,v2),... is exactly
    equivalent to a single (M=m1&m2&..., V=(v1&m2&...)|(v2&...)...)
    applied to any starting byte, so net triples stamp correctly.
    Cached by tile word (phase 0 and phase 1 separately).
    The footprint is the cell's COMPLETE drawing: top call + height
    stack whenever height > 0. The game itself draws an interior
    bit-9-clear cell's stack only at the window's last row/column
    (map_chunk_pos gate), so a live window omits those stack bytes;
    the atlas shows every cell whole. Complete footprints are
    exactly translation-invariant across all 100 window positions
    (verified per tile; only buffer-edge clipping at (0,0) breaks
    it, and the atlas renders at interior (4,4)).
  * stamp: cells painted in game order (world-X outer, world-Y
    inner) at canvas offset origin + wx*East + wy*South, applying
    (canvas & M) | V per byte. All offsets are even, so 2-pixel
    bytes stay byte-aligned.
  * areas: overworld = chunks 0-76 as one 352x224 canvas; big rooms
    = chunks 230-251 (22 x 32x32, one canvas each); small rooms =
    chunks 77-229 (153 x 11x11, one canvas each). One tile set per
    area (union over its canvases); one tilemap per canvas.
  * tiles: 8x8 pixels = 32 bytes (4 bits/pixel, 2 pixels/byte).
    Tilemap entries are u8 when the area has <= 256 distinct tiles,
    else u16; reported per area.

Verification (in --verify mode): for each live RAM snapshot, a
WINDOW-ONLY canvas (the frame's 100 cells, stamped with the atlas
machinery) is compared against (a) a COMPLETE port replay of the
same window (must be 0 mismatches) and (b) the live $FF1EC0 buffer
(must differ only by figure bytes + the height-stack bytes the live
window omits). The full atlas is NOT compared directly: neighbouring
cells outside the window legitimately paint over the edge cells'
footprints there, so only the window-only comparison is exact.

Usage:
  python3 tools/e358_atlas.py [--rom rop-original.gen]
      [--out build/e358-atlas.json] [--verify build/e358-map-ram]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from decode_chunks import decode_record, parse_table  # noqa: E402
from e358 import BUF_BASE, BUF_LEN, E358, RAM_LEN  # noqa: E402
from e358_map import w as ram_w  # noqa: E402  (RAM word reader)

REPO = Path(__file__).resolve().parent.parent
ROM_DEFAULT = REPO / "rop-original.gen"

EAST = (14, 8)
SOUTH = (-14, 8)


def buf_offset_to_px(o):
    """Buffer byte offset -> (pixel x, pixel y) of its left pixel."""
    tile_row, b = divmod(o, 1152)
    tile_col, r = divmod(b, 32)
    row_in_tile, byte_in_row = divmod(r, 4)
    return tile_col * 8 + byte_in_row * 2, tile_row * 8 + row_in_tile


class AtlasBuilder:
    def __init__(self, rom):
        self.e = E358(rom)
        self.rom = rom
        self.recs = parse_table(rom)
        self._chunks = {}
        self._footprints = {}  # (tile_word, phase) -> {(px,py): (M,V)}

    def props(self, stream):
        return struct.unpack_from(">H", self.rom, 0x5EDC4 + 2 * stream)[0]

    def chunk_words(self, chunk_id):
        if chunk_id not in self._chunks:
            data, _used = decode_record(self.rom, self.recs[chunk_id])
            n = len(data) // 2
            self._chunks[chunk_id] = struct.unpack(">%dH" % n, data[: n * 2])
        return self._chunks[chunk_id]

    def cell_calls(self, tile, row=4, col=4, phase=0, complete=False):
        """$E358 call list for one cell at window (row, col).

        Same logic as e358_map.MapReplayer.replay, factored per cell.
        With complete=False (default) this is exactly what the game
        draws at that window position: the height loop runs only when
        height > 0 and (row == 9 or col == 9 or the tile's bit 9).
        With complete=True the height loop runs whenever height > 0,
        giving the cell's full drawing (top + stack) -- what the
        atlas stamps. The two differ only for interior bit-9-clear
        cells with height > 0, whose stack the game draws solely at
        the window's last row/column.
        """
        stream = tile & 0x1FF
        pr = self.props(stream)
        if phase:
            if (pr >> 9) & 1:
                stream += 1
            if (pr >> 6) & 1:
                stream -= 1
        height = (tile >> 13) & 7
        bit7 = (tile >> 9) & 1
        bit12 = (tile >> 12) & 1
        d0 = 196 + 14 * (row - col)
        d1b = 8 * (row + col) + 18
        calls = []
        if height > 0 and (complete or row == 9 or col == 9 or bit7):
            if (pr >> 5) & 1:
                a4 = stream
                ee = height - (pr & 0x1F)
                d3h = bit12
            else:
                a4 = 0x22F + (pr & 0x1F)
                pr2 = self.props(a4)
                ee = height - (pr2 & 0x1F)
                d3h = ((pr2 >> 5) & 1) * bit12
            for d6 in range(height):
                if d6 < ee:
                    calls.append((0x230, d0, d1b - 7 * d6, 0))
                else:
                    calls.append((a4, d0, d1b - 7 * d6, d3h))
        calls.append((stream, d0, d1b - 7 * height, bit12))
        return calls

    def footprint(self, tile, phase=0):
        """Net {(px, py): (mask, value)} for one tile word at (4,4).

        Complete drawing (top + height stack whenever height > 0):
        the atlas shows each cell whole, unlike a live window, where
        the game draws an interior bit-9-clear cell's stack only at
        the window's last row/column (see cell_calls)."""
        key = (tile, phase)
        if key in self._footprints:
            return self._footprints[key]
        ram = bytearray(RAM_LEN)
        net = {}
        for s, d0, d1, d3 in self.cell_calls(tile, 4, 4, phase, complete=True):
            tr = []
            st = self.e.call(s, d0, d1, d3, ram, trace=tr)
            if st["out_of_range"]:
                raise ValueError("out-of-range write for tile %04x phase %d"
                                 % (tile, phase))
            for addr, mask, val in tr:
                o = addr - BUF_BASE
                px, py = buf_offset_to_px(o)
                m0, v0 = net.get((px, py), (0xFF, 0))
                net[(px, py)] = (m0 & mask, (v0 & mask) | val)
        self._footprints[key] = net
        return net

    def render_canvas(self, cells, phase=0):
        """cells: iterable of (wx, wy, tile_word). Returns (canvas, origin,
        width_px, height_px) where canvas is a bytearray of 4bpp pixels
        (2 pixels/byte, width_px/2 bytes per row)."""
        # First pass: footprint pixel bounds in canvas coordinates.
        min_x = min_y = None
        max_x = max_y = None
        per_cell = []
        # Paint in game order: world-X outer, world-Y inner (the
        # window loop's d4/d5 order). Overlap resolution depends on it.
        for wx, wy, tile in sorted(cells):
            fp = self.footprint(tile, phase)
            ox = wx * EAST[0] + wy * SOUTH[0]
            oy = wx * EAST[1] + wy * SOUTH[1]
            per_cell.append((ox, oy, fp))
            for (px, py) in fp:
                cx, cy = px + ox, py + oy
                if min_x is None or cx < min_x:
                    min_x = cx
                if max_x is None or cx > max_x:
                    max_x = cx
                if min_y is None or cy < min_y:
                    min_y = cy
                if max_y is None or cy > max_y:
                    max_y = cy
        # Footprint pixels come in byte pairs (even px); pad the canvas
        # to a multiple of 8 px so it cuts into whole 8x8 tiles.
        ox0 = (min_x // 8) * 8
        oy0 = (min_y // 8) * 8
        w_px = ((max_x - ox0 + 8) // 8) * 8 + 8
        h_px = ((max_y - oy0 + 8) // 8) * 8 + 8
        row_bytes = w_px // 2
        canvas = bytearray(h_px * row_bytes)
        for ox, oy, fp in per_cell:
            dx = ox - ox0
            dy = oy - oy0
            idx = []
            msk = []
            val = []
            for (px, py), (m, v) in fp.items():
                idx.append((py + dy) * row_bytes + (px + dx) // 2)
                msk.append(m)
                val.append(v)
            ia = np.array(idx, dtype=np.int64)
            ma = np.array(msk, dtype=np.uint8)
            va = np.array(val, dtype=np.uint8)
            ca = np.frombuffer(canvas, dtype=np.uint8)
            ca[ia] = (ca[ia] & ma) | va
        return canvas, (ox0, oy0), w_px, h_px

    def cut_tiles(self, canvas, w_px, h_px):
        """Cut a canvas into 8x8 tiles; returns (tiles, tilemap, width).
        tiles: (n_distinct, 32) uint8 array; tilemap: flat index array
        (row-major over tile positions); width: tilemap entry bytes
        (1 if <= 256 distinct tiles, else 2)."""
        row_bytes = w_px // 2
        a = np.frombuffer(canvas, dtype=np.uint8).reshape(h_px, row_bytes)
        ntr, ntc = h_px // 8, w_px // 8
        t = a.reshape(ntr, 8, ntc, 4).transpose(0, 2, 1, 3)
        flat = t.reshape(ntr * ntc, 32)
        uniq, inverse = np.unique(flat, axis=0, return_inverse=True)
        width = 1 if len(uniq) <= 256 else 2
        return uniq, inverse.reshape(ntr, ntc), width


def overworld_cells(ab):
    cells = []
    for wy in range(224):
        for wx in range(352):
            ch = (wy // 32) * 11 + (wx // 32)
            words = ab.chunk_words(ch)
            cells.append((wx, wy, words[(wy % 32) * 32 + (wx % 32)]))
    return cells


def room_cells(ab, chunk_id, edge):
    words = ab.chunk_words(chunk_id)
    assert len(words) == edge * edge, (chunk_id, len(words), edge)
    return [(wx, wy, words[wy * edge + wx])
            for wy in range(edge) for wx in range(edge)]


def build_area(ab, name, canvases, phase=0):
    """canvases: list of (label, cells). Returns area report dict.

    Tilemaps index the AREA tile set (union over the area's canvases),
    not the canvas-local sets: the per-canvas uniques are joined,
    deduplicated once, and each canvas's tilemap is remapped to the
    area indices.
    """
    per_canvas = []
    for label, cells in canvases:
        canvas, origin, w_px, h_px = ab.render_canvas(cells, phase)
        uniq, tmap, _w = ab.cut_tiles(canvas, w_px, h_px)
        per_canvas.append({"label": label, "origin": origin,
                           "canvas_px": [w_px, h_px],
                           "tile_grid": [int(tmap.shape[0]),
                                         int(tmap.shape[1])],
                           "uniq": uniq, "tmap_local": tmap,
                           "canvas": canvas})
    if per_canvas:
        joined = np.concatenate([c["uniq"] for c in per_canvas], axis=0)
        uniq_all, joined_inv = np.unique(joined, axis=0, return_inverse=True)
    else:
        uniq_all = np.zeros((0, 32), dtype=np.uint8)
        joined_inv = np.zeros(0, dtype=int)
    width = 1 if len(uniq_all) <= 256 else 2
    total_map_bytes = 0
    off = 0
    tilemaps = []
    for c in per_canvas:
        n = len(c["uniq"])
        area_map = joined_inv[off:off + n][c["tmap_local"].ravel()]
        off += n
        area_map = area_map.reshape(c["tmap_local"].shape)
        total_map_bytes += int(area_map.size * width)
        tilemaps.append({"label": c["label"], "origin": c["origin"],
                         "canvas_px": c["canvas_px"],
                         "tile_grid": c["tile_grid"],
                         "tilemap_width": width,
                         "tilemap_bytes": int(area_map.size * width),
                         "tiles_here": int(len(c["uniq"])),
                         "tilemap": area_map.tolist(),
                         "canvas": c["canvas"]})
    return {"area": name, "canvases": len(canvases),
            "distinct_tiles": int(len(uniq_all)),
            "tile_bytes": int(len(uniq_all) * 32),
            "tilemap_bytes": int(total_map_bytes),
            "total_bytes": int(len(uniq_all) * 32 + total_map_bytes),
            "tilemap_width": width, "tilemaps": tilemaps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(ROM_DEFAULT))
    ap.add_argument("--out", default="")
    ap.add_argument("--verify", default="",
                    help="snapshot dir (build/e358-map-ram) to check live "
                         "window buffers against the overworld atlas crop")
    a = ap.parse_args()
    rom = Path(a.rom).read_bytes()
    ab = AtlasBuilder(rom)
    # Distinct tile words per group (drives the footprint cache).
    ow_words = set()
    for ch in range(77):
        ow_words.update(ab.chunk_words(ch))
    big_words = set()
    for ch in range(230, 252):
        big_words.update(ab.chunk_words(ch))
    small_words = set()
    for ch in range(77, 230):
        small_words.update(ab.chunk_words(ch))
    print("distinct tile words: overworld %d, big rooms %d, small rooms %d"
          % (len(ow_words), len(big_words), len(small_words)))
    all_words = ow_words | big_words | small_words
    phase_diff = sum(1 for tile in all_words
                     if ab.footprint(tile, 0) != ab.footprint(tile, 1))
    print("phase 0 vs 1 footprints differ for %d/%d tile words"
          % (phase_diff, len(all_words)))
    areas = []
    areas.append(build_area(
        ab, "overworld", [("overworld", overworld_cells(ab))]))
    areas.append(build_area(
        ab, "big-rooms",
        [("chunk-%d" % ch, room_cells(ab, ch, 32)) for ch in range(230, 252)]))
    areas.append(build_area(
        ab, "small-rooms",
        [("chunk-%d" % ch, room_cells(ab, ch, 11)) for ch in range(77, 230)]))
    total = sum(x["total_bytes"] for x in areas)
    total_tiles = sum(x["distinct_tiles"] for x in areas)
    for x in areas:
        print("%s: canvases %d, distinct tiles %d, tile bytes %d, "
              "tilemap bytes %d (u%d), total %d"
              % (x["area"], x["canvases"], x["distinct_tiles"],
                 x["tile_bytes"], x["tilemap_bytes"], x["tilemap_width"],
                 x["total_bytes"]))
    print("TOTAL distinct tiles (sum over areas): %d" % total_tiles)
    print("TOTAL atlas bytes: %d (2 MiB = 2097152) -> %s"
          % (total, "FITS" if total <= 2097152 else "EXCEEDS by %d"
             % (total - 2097152)))
    summary = {"mode": "atlas", "areas": areas,
               "total_distinct_tiles": total_tiles,
               "total_bytes": total, "limit_bytes": 2097152,
               "fits_2mb": total <= 2097152,
               "phase_diff_tile_words": phase_diff,
               "phase_diff_total": len(all_words)}
    if a.verify:
        summary["verify"] = verify_overworld(ab, a.verify)
    out = a.out or str(REPO / "build" / "e358-atlas.json")
    # The JSON summary carries counts only: drop tilemap arrays and
    # raw canvases (kept in memory for --verify above).
    for x in summary["areas"]:
        for tm in x["tilemaps"]:
            tm.pop("tilemap", None)
            tm.pop("canvas", None)
    Path(out).write_text(json.dumps(summary, indent=1))
    print("wrote %s" % out)
    return 0


def verify_overworld(ab, snapdir):
    """Check the atlas against port replays and live buffers, per frame.

    Each frame gets a WINDOW-ONLY canvas: the same 100 cells the
    game's window render draws, stamped with the atlas machinery.
    (The full atlas legitimately differs from a window render at the
    edges: neighbouring cells outside the window paint over the edge
    cells' footprints there -- the interior matches exactly, which
    the window-only comparison isolates.)

    Mapping (through pixels, not byte rows -- the $FF1EC0 buffer is
    tiled 36x23, so buffer byte offset o is NOT row o//144): a buffer
    byte at offset o covers pixels buf_offset_to_px(o); those pixels
    sit on the window canvas at +S(leader), S = (leaderX-1)*East +
    (leaderY-1)*South - origin (the (row, col) terms cancel: the
    whole window is one rigid shift of the atlas). The canvas byte
    for canvas pixel (cx, cy) is canvas[cy*row_bytes + cx//2].

    The window canvas uses the frame's own $FF0092 phase (which
    toggles every tick and selects stream +/-1 variants for 520/2614
    tile words); the stored atlas itself is phase 0.

    Two checks per frame:
    (a) synthetic: the window canvas crop vs a COMPLETE port replay
        of the same window (height loop forced on) -- must be 0
        mismatches; this validates the stamping, lattice and paint
        order.
    (b) live: the window canvas crop vs the live buffer -- mismatches
        must be exactly the figure bytes (live vs gated replay) plus
        the height-stack bytes the live window omits for interior
        bit-9-clear cells (complete replay vs gated replay).
    """
    from e358_map import MapReplayer
    snapdir = Path(snapdir)
    manifest = json.loads((snapdir / "manifest.json").read_text())
    frames = []
    prev = None
    for m in manifest:
        if prev == 0xFFFF and m["watch"] == 0:
            frames.append(m["frame"])
        prev = m["watch"]
    rp = MapReplayer(ab.rom)
    results = []
    for f in frames:
        ram = (snapdir / ("ram_f%05d.bin" % f)).read_bytes()
        gb_ptr = (ram_w(ram, 0xFFA7FC) << 16) | ram_w(ram, 0xFFA7FC + 2)
        gb_off = gb_ptr - 0xFF0000
        gridbase = tuple((ram[gb_off + 2 * i] << 8) | ram[gb_off + 2 * i + 1]
                         for i in range(4))
        lx = ram_w(ram, 0xFF0E8E)
        ly = ram_w(ram, 0xFF0E90)
        base_raw = ram_w(ram, 0xFF0E98)
        base = 0 if base_raw == 0xFFFF else base_raw + 0x4D
        # $FF0092 phase (toggles every tick): the game draws stream
        # +/-1 variants for tiles whose props have bit 9/6 set when
        # it is nonzero. The window canvas must use the frame's own
        # phase, as MapReplayer does -- the atlas itself is phase 0.
        phase = ram_w(ram, 0xFF0092)
        # Window-only canvas: the frame's 100 cells, atlas machinery.
        cells = []
        for row in range(10):
            for col in range(10):
                wx, wy = lx + row - 5, ly + col - 5
                cells.append((wx, wy,
                              rp.tile_word(wx, wy, gridbase, base)))
        canvas, (ox0, oy0), w_px, h_px = ab.render_canvas(cells, phase)
        row_bytes = w_px // 2
        sx = (lx - 1) * EAST[0] + (ly - 1) * SOUTH[0] - ox0
        sy = (lx - 1) * EAST[1] + (ly - 1) * SOUTH[1] - oy0
        live = ram[BUF_BASE - 0xFF0000:BUF_BASE - 0xFF0000 + BUF_LEN]
        gated, _w1, _i1 = rp.replay(ram)
        complete, _w2, _i2 = rp.replay(ram, complete=True)
        # Atlas crop, mapped buffer-byte by buffer-byte through pixels.
        crop = bytearray(BUF_LEN)
        for o in range(BUF_LEN):
            px, py = buf_offset_to_px(o)
            cx, cy = px + sx, py + sy
            cxb = cx // 2
            crop[o] = (canvas[cy * row_bytes + cxb]
                       if 0 <= cxb < row_bytes and 0 <= cy < h_px else 0)
        # (a) synthetic: crop vs complete replay.
        syn = {o for o in range(BUF_LEN) if crop[o] != complete[o]}
        # (b) live: crop vs live; expected = figure bytes (live vs
        # gated) + stack bytes the gated replay omits (complete vs
        # gated).
        figure = {o for o in range(BUF_LEN) if live[o] != gated[o]}
        stack = {o for o in range(BUF_LEN) if complete[o] != gated[o]}
        live_mism = {o for o in range(BUF_LEN) if crop[o] != live[o]}
        expect = figure | stack
        extra = live_mism - expect
        missing = expect - live_mism
        results.append({"frame": f, "leader": [lx, ly],
                        "gridbase": list(gridbase), "phase": phase,
                        "synthetic_mismatches": len(syn),
                        "live_mismatches": len(live_mism),
                        "figure_bytes": len(figure),
                        "stack_bytes": len(stack),
                        "live_extra": len(extra),
                        "live_missing": len(missing)})
        print("verify frame %5d leader [%d,%d] gridbase %s phase %d: "
              "synthetic %d, live %d (figure %d + stack %d, extra %d, "
              "missing %d)"
              % (f, lx, ly, gridbase, phase, len(syn), len(live_mism),
                 len(figure), len(stack), len(extra), len(missing)))
    tot_syn = sum(r["synthetic_mismatches"] for r in results)
    tot_extra = sum(r["live_extra"] for r in results)
    tot_missing = sum(r["live_missing"] for r in results)
    print("verify: %d frames, synthetic mismatches %d, "
          "live extra %d, live missing %d"
          % (len(results), tot_syn, tot_extra, tot_missing))
    return {"frames": len(results), "synthetic_mismatches": tot_syn,
            "live_extra": tot_extra, "live_missing": tot_missing,
            "results": results}


if __name__ == "__main__":
    sys.exit(main())
