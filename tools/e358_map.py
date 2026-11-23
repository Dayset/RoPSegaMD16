"""Full-view verification for the $E358 port (Track A, issue #252).

Replays the TERRAIN part of map_chunk_pos ($01BA4E) from a live RAM
snapshot of the original ROM and compares the port's $FF1EC0 bytes
against the live buffer, restricted to the bytes the terrain calls
write. Figure / animated-tile calls (hero_track, map_promote_record,
map_tile_at_offset, map_animated_tile) are excluded by construction:
they run after the terrain calls in the real render, so any byte
where live != port inside the terrain-written set is a candidate
figure footprint, reported per frame with its tile location.

Snapshots: full 64 KB RAM dumps produced by
  python3 tools/md_run.py ramdump --rom rop-original.gen \
      --route tools/playtest_route_orig.txt \
      --addr 0xFF0000 --len 65536 --watch 0xFF0098 --out build/e358-map-ram
which dumps on every $FF0098 change; a 1->0 transition means a render
finished (map_chunk_pos ran, buffer complete, DMA issued). Only
1->0 frames are replayed.

Per-cell replay (row-major d4=0..9, d5=0..9), from rop.s $01BA4E:
  tile word  = chunk[(y'%E)*E + (x'%E)] for world cell
               (leaderX + row - 5, leaderY + col - 5), wrapped by the
               gridbase W/H; chunk = (y'//E)*CPR + (x'//E) + base,
               base = 0 overworld, $FF0E98 + 0x4D rooms.
  stream     = tile & 0x1FF; props = $5EDC4[stream] (ROM word);
               $FF0092 != 0: props bit 9 -> stream += 1,
               props bit 6 -> stream -= 1 (props NOT re-read).
  height     = tile bits 13-15; bit7 = tile bit 9 (height-stack flag);
               bit12 = tile bit 12 (top-call d3).
  height loop, only if height > 0 and (row == 9 or col == 9 or bit7):
               props bit 5: a4 = stream, e = height - (props & 0x1F),
                            d3h = bit12
               else:        a4 = 0x22F + (props & 0x1F),
                            props2 = $5EDC4[a4],
                            e = height - (props2 & 0x1F),
                            d3h = (props2 bit 5) * bit12
               for d6 in 0..height-1:
                 d6 < e:  $E358(0x230, d0tab, d1tab - 7*d6, 0)
                 else:    $E358(a4,    d0tab, d1tab - 7*d6, d3h)
  top call (always): $E358(stream, d0tab, d1tab - 7*height, bit12)
  d0tab/d1tab = RAM $FFAE7A/$FFAF42 (100 words each), read from the
  snapshot; they are also checked against the grid_fill formulas
  (196 + 14*(row-col), 8*(row+col) + 18).

Usage:
  python3 tools/e358_map.py --snapdir build/e358-map-ram \
      [--rom rop-original.gen] [--out build/e358-map.json]
"""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from decode_chunks import decode_record, parse_table  # noqa: E402
from e358 import BUF_BASE, BUF_END, E358, RAM_LEN  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
ROM_DEFAULT = REPO / "rop-original.gen"

BUF_LEN = BUF_END - BUF_BASE  # 26,496

# RAM addresses (all $FFxxxx; offsets below are addr - 0xFF0000).
LEADER_X = 0xFF0E8E
LEADER_Y = 0xFF0E90
PHASE = 0xFF0092
CHUNK_BASE = 0xFF0E98
GRIDBASE_PTR = 0xFFA7FC
SPELL_FLAG = 0xFF013C
REDRAW_FLAG = 0xFF0098
D0TAB = 0xFFAE7A
D1TAB = 0xFFAF42
PROPS_TABLE = 0x5EDC4  # ROM address, word per stream id


def w(ram, addr):
    o = addr - 0xFF0000
    return (ram[o] << 8) | ram[o + 1]


def grid_fill_formula(row, col):
    return 196 + 14 * (row - col), 8 * (row + col) + 18


class MapReplayer:
    def __init__(self, rom):
        self.e = E358(rom)
        self.rom = rom
        self.recs = parse_table(rom)
        self._chunks = {}

    def props(self, stream):
        return struct.unpack_from(">H", self.rom, PROPS_TABLE + 2 * stream)[0]

    def chunk_words(self, chunk_id):
        if chunk_id not in self._chunks:
            if not 0 <= chunk_id < len(self.recs):
                raise ValueError("chunk id out of range: %d" % chunk_id)
            data, _used = decode_record(self.rom, self.recs[chunk_id])
            n = len(data) // 2
            self._chunks[chunk_id] = struct.unpack(">%dH" % n, data[: n * 2])
        return self._chunks[chunk_id]

    def tile_word(self, wx, wy, gridbase, base):
        """Tile word for world cell (wx, wy); gridbase = (W, H, E, CPR)."""
        W, H, E, CPR = gridbase
        x = (W + wx) % W
        y = (H + wy) % H
        chunk = (y // E) * CPR + (x // E) + base
        words = self.chunk_words(chunk)
        off = (y % E) * E + (x % E)
        return words[off]

    def replay(self, ram, complete=False):
        """Replay the terrain calls of one render from a RAM snapshot.

        Returns (port_buf, written_mask, info). port_buf is the 26,496
        buffer bytes; written_mask is a bytearray of the same length
        with 1s at offsets any terrain call wrote; info has the
        inputs, per-frame stats and any anomaly.

        With complete=True the height loop runs whenever height > 0
        (a cell's full drawing); with complete=False (default) it
        follows the game's gate (only at row/col 9 or tile bit 9).
        """
        leader_x = w(ram, LEADER_X)
        leader_y = w(ram, LEADER_Y)
        phase = w(ram, PHASE)
        base_raw = w(ram, CHUNK_BASE)
        base = 0 if base_raw == 0xFFFF else base_raw + 0x4D
        spell = w(ram, SPELL_FLAG)
        gb_ptr = (w(ram, GRIDBASE_PTR) << 16) | w(ram, GRIDBASE_PTR + 2)
        gb_off = gb_ptr - 0xFF0000
        gridbase = tuple((ram[gb_off + 2 * i] << 8) | ram[gb_off + 2 * i + 1]
                         for i in range(4))
        d0tab = [w(ram, D0TAB + 2 * i) for i in range(100)]
        d1tab = [w(ram, D1TAB + 2 * i) for i in range(100)]
        formula_bad = []
        for row in range(10):
            for col in range(10):
                f0, f1 = grid_fill_formula(row, col)
                if (d0tab[row * 10 + col], d1tab[row * 10 + col]) != (f0, f1):
                    formula_bad.append((row, col))
        info = {"leader": [leader_x, leader_y], "phase": phase,
                "chunk_base_raw": base_raw, "chunk_base": base,
                "gridbase": list(gridbase), "gridbase_ptr": hex(gb_ptr),
                "spell_flag": spell, "formula_bad": formula_bad}
        sim = bytearray(RAM_LEN)
        written = bytearray(BUF_LEN)
        buf_off = BUF_BASE - 0xFF0000
        ncalls = 0
        oor = []
        for row in range(10):
            for col in range(10):
                wx = leader_x + row - 5
                wy = leader_y + col - 5
                tile = self.tile_word(wx, wy, gridbase, base)
                stream = tile & 0x1FF
                props = self.props(stream)
                if phase:
                    if (props >> 9) & 1:
                        stream += 1
                    if (props >> 6) & 1:
                        stream -= 1
                if not 0 <= stream < 944:
                    raise ValueError(
                        "phase-adjusted stream out of range: %d "
                        "(cell %d,%d tile %04x)" % (stream, row, col, tile))
                height = (tile >> 13) & 7
                bit7 = (tile >> 9) & 1
                bit12 = (tile >> 12) & 1
                d0 = d0tab[row * 10 + col]
                d1b = d1tab[row * 10 + col]

                def docall(s, d0v, d1v, d3v):
                    nonlocal ncalls
                    before = np.frombuffer(
                        sim[buf_off:buf_off + BUF_LEN], dtype=np.uint8).copy()
                    st = self.e.call(s, d0v, d1v, d3v, sim)
                    after = np.frombuffer(
                        sim[buf_off:buf_off + BUF_LEN], dtype=np.uint8)
                    for o in np.nonzero(before != after)[0]:
                        written[int(o)] = 1
                    ncalls += 1
                    oor.extend(st["out_of_range"])

                if height > 0 and (complete or row == 9 or col == 9 or bit7):
                    if (props >> 5) & 1:
                        a4 = stream
                        e = height - (props & 0x1F)
                        d3h = bit12
                    else:
                        a4 = 0x22F + (props & 0x1F)
                        props2 = self.props(a4)
                        e = height - (props2 & 0x1F)
                        d3h = ((props2 >> 5) & 1) * bit12
                    for d6 in range(height):
                        if d6 < e:
                            docall(0x230, d0, d1b - 7 * d6, 0)
                        else:
                            docall(a4, d0, d1b - 7 * d6, d3h)
                docall(stream, d0, d1b - 7 * height, bit12)
        info["ncalls"] = ncalls
        info["out_of_range_writes"] = oor
        info["written_bytes"] = sum(written)
        return bytes(sim[buf_off:buf_off + BUF_LEN]), written, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapdir", required=True)
    ap.add_argument("--rom", default=str(ROM_DEFAULT))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rom = Path(a.rom).read_bytes()
    snapdir = Path(a.snapdir)
    manifest = json.loads((snapdir / "manifest.json").read_text())
    # Replay only 0xFFFF->0 transitions of $FF0098 (render finished;
    # redraw_flag_set writes $FFFF, the render clears it).
    frames = []
    prev = None
    for m in manifest:
        if prev == 0xFFFF and m["watch"] == 0:
            frames.append(m["frame"])
        prev = m["watch"]
    print("render-complete frames: %d of %d dumps"
          % (len(frames), len(manifest)))
    rp = MapReplayer(rom)
    results = []
    tot_written = 0
    tot_match = 0
    for f in frames:
        ram = (snapdir / ("ram_f%05d.bin" % f)).read_bytes()
        assert len(ram) == RAM_LEN, (f, len(ram))
        rec = {"frame": f}
        try:
            port, written, info = rp.replay(ram)
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            rec["replay_error"] = "%s: %s" % (type(exc).__name__, exc)
            results.append(rec)
            print("frame %d: REPLAY ERROR %s" % (f, rec["replay_error"]))
            continue
        live = ram[BUF_BASE - 0xFF0000:BUF_END - 0xFF0000]
        diffs = [o for o in range(BUF_LEN)
                 if written[o] and live[o] != port[o]]
        # Cluster diffs by 8x8 tile (tile row = off // 1152).
        tiles = {}
        for o in diffs:
            t = (o // 1152, (o % 1152) // 32)
            tiles[t] = tiles.get(t, 0) + 1
        rec.update(info)
        rec["written"] = info["written_bytes"]
        rec["diffs"] = len(diffs)
        rec["diff_rate"] = (len(diffs) / info["written_bytes"]
                            if info["written_bytes"] else 0)
        rec["diff_tiles"] = ["%d,%d:%d" % (r, c, n)
                             for (r, c), n in sorted(tiles.items())]
        rec["diff_offsets"] = diffs[:50]
        if diffs:
            rec["diff_values"] = [[o, live[o], port[o]] for o in diffs[:20]]
        tot_written += info["written_bytes"]
        tot_match += info["written_bytes"] - len(diffs)
        results.append(rec)
        print("frame %5d leader %s gridbase %s phase %d spell %d: "
              "calls %3d written %5d diffs %3d (tiles %s)"
              % (f, info["leader"], info["gridbase"], info["phase"],
                 info["spell_flag"], info["ncalls"], info["written_bytes"],
                 len(diffs),
                 ",".join(rec["diff_tiles"][:8]) or "-"))
    ok = [r for r in results if "replay_error" not in r]
    summary = {"mode": "full-view", "frames": len(frames),
               "frames_ok": len(ok),
               "frames_replay_error": len(results) - len(ok),
               "terrain_written_bytes": tot_written,
               "terrain_matched_bytes": tot_match,
               "terrain_match_rate": (tot_match / tot_written
                                      if tot_written else 0),
               "results": results}
    out = a.out or str(REPO / "build" / "e358-map.json")
    Path(out).write_text(json.dumps(summary, indent=1))
    print("full-view: %d/%d frames ok, terrain bytes %d, matched %d, "
          "rate %.6f" % (len(ok), len(frames), tot_written, tot_match,
                         summary["terrain_match_rate"]))
    print("wrote %s" % out)
    # Exit 0 iff every frame replayed: diffs are expected figure
    # footprints, reported in the JSON, not a failure.
    return 0 if len(ok) == len(frames) else 1


if __name__ == "__main__":
    sys.exit(main())
