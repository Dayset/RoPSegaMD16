#!/usr/bin/env python3
"""M7 asset pipeline (issue #024 as scoped in docs/tribute-remake.md):
export the Rings of Power ROM's assets into a form the Esenthel
Titan Engine can load (2D classic mode: smooth flat plane + dot walking).

NOTE ON ISSUE NUMBERING: GitHub issue #024 is the workflow/process
issue ("GitHub issues as the tracker..."), NOT an asset-pipeline
issue — the M7 workstream issues #023-#031 named in
docs/tribute-remake.md were never created on GitHub under those
numbers. The operative scope here is the tribute-remake.md workstream
"#024 asset extraction pipeline (start now, builds on #004-#006)"
plus the parent task: extract maps, terrain, sprites, text, items
and spells into an engine-loadable form. GitHub #019 is the asset
round-trip issue whose exporter is this pipeline's source.

Stages:
  0  verify the ROM (MD5 30c18fdbe2183f64702ae9f1a45d63f9)
  1  DD5C records via the #19 exporter (tools/export_assets.py):
     400 records -> tribute/assets/gfx/ (tilesets/sprites/maps/chunks,
     indexed PNG + JSON), verified against the committed assets/gfx/
  2  engine conversion: true-colour RGB PNGs for every indexed PNG,
     and chunk JSONs re-decoded with the CORRECTED cell-word layout
     (tile_type/height/flags — the #19 export uses misleading VDP
     key names for chunks)
  3  table exports (non-DD5C data, read straight from the ROM):
     terrain, locations, entities, items, spells, figures, text,
     conversations, palettes, event scripts
  4  verification: counts, cross-checks against the committed
     disasm/ dumps, and a summary

The shipped game does NOT need the user to supply a ROM: this
pipeline exports at build time (docs/tribute-remake.md). The
original ROM is read-only here and never modified.

Usage:
  python3 pipeline/m7_export.py [--rom PATH] [--repo PATH] [--out DIR]
  Defaults: --rom <repo>/rop-original.gen, --repo the rings-of-power
  checkout (resolved from this file's location), --out
  <worktree>/tribute/assets.

Exit 0 when every stage passes; exit 1 on any verification failure.
Game rules are NOT built here (later issues). The big-rework
patched-ROM line is untouched by this pipeline.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_WORKTREE = _HERE.parent
# The repo checkout: <worktree>/../../rings-of-power, or --repo.
_REPO_DEFAULT = (_WORKTREE.parent.parent / "rings-of-power").resolve()

ROM_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"
ROM_SIZE = 1048576

# ---------------------------------------------------------------- tables
# (address, record size, count, note)
TABLES = {
    "terrain_props":   (0x05EDC4, 2, 944),    # $5EDC4, 944 words
    "terrain_offsets": (0x05F524, 4, 944),    # $5F524, 944 u32 offsets
    "descriptors":     (0x01AE98, 2, 512),    # $1AE98, 512 words
    "figure_templates": (0x0197B0, 36, 56),   # $197B0, 56 x 36 B
    "locations":       (0x0D1D00, 10, 455),   # $D1D00, 455 x 10 B
    "placement":       (0x0D63E4, 4, 175),    # $D63E4, 175 x 4 B
    "names":           (0x0CD430, 16, 396),  # $CD430, 396 x 16 B
    "entity_templates": (0x0CF1AC, 24, 462),  # $CF1AC, 462 x 24 B
    "spawn_table":     (0x0CECF0, 6, 202),    # $CECF0, 202 x 6 B
    "item_categories": (0x0D66A0, 10, 20),    # $D66A0, 20 x 10 B
    "price_table":     (0x0D6768, 4, 257),    # $D6768, 257 x 4 B
    "rank_tables":     (0x0D6B6C, 6, 126),    # 6 tables x 21 recs x 6 B
    "conversations":   (0x0D3102, 12, 1005),  # $D3102, 1005 x 12 B
    "grants":          (0x0D601E, 6, 161),    # $D601E, 161 x 6 B
    "palettes":        (0x0CC9D8, 32, 31),    # $0CC9D8, 31 x 16 words
}
TERRAIN_STREAM_BASE = 0x603E4
TERRAIN_STREAM_END = 0x96120   # last stream ends at $96120
TEXT_BLOB_START, TEXT_BLOB_END = 0x0D6EBA, 0x0DC0C0
TEXT_OFF_TABLE = 0x0DC0C2
TEXT_N_WORDS = 3466
TEXT_RECORD_TABLE = 0x0DDBD8
TEXT_N_RECORDS = 1184
TEXT_ARRAY_BASE = 0x0E0A18

# Event scripts: case -> (script addr, record count). 8-byte records.
# docs/cutscenes.md (all 10 scripts decoded in full, 198 records).
SCRIPT_CASES = {
    0: (0x19F90, 83), 1: (0x1A228, 46), 2: (0x1A398, 3), 3: (0x1A3B0, 1),
    4: (0x1A3B8, 33), 5: (0x1A4C0, 5), 6: (0x1A4E8, 7), 7: (0x1A520, 14),
    8: (0x1A590, 5), 9: (0x1A5B8, 1),
}
# op -> handler (docs/cutscenes.md dispatch table; target =
# $02DBE8 + word at $02DBB8+2*op). Record byte 0 is a SIGNED op code
# (e.g. -13 = pose, +5 = move, +6 = text, +4 = SFX+mode-6 spawn).
SCRIPT_OPS = {
    0: "0x02D5D4", 1: "0x02D802", 2: "0x02D892", 3: "0x02D852",
    4: "0x02D8F4", 5: "0x02D7D6", 6: "0x02D964", 7: "0x02DA0A",
    8: "0x02DA3E", 9: "0x02DAB4", 10: "0x02DAD4", 11: "0x02DB06",
    12: "0x02DB2A", 13: "0x02DB2E", 14: "0x02DB88", 15: "0x02D67C",
}
SCRIPT_OP_NAMES = {
    0: "grant", 1: "teleport", 2: "spawn", 3: "place",
    4: "sfx_spawn_mode6", 5: "move", 6: "text", 7: "attacker_check",
    8: "kill", 9: "stage", 10: "flush", 11: "event",
    12: "noop", 13: "pose", 14: "step", 15: "text_event_resolve",
}

# $5EDC4 bit layout (docs/maps.md + water-plane REPORT):
# bits 0-4 stream-index offset; bit 5 stream-source select;
# bit 6 tile index -1 when $FF0092 set; bit 7 row count +1;
# bit 8 row count +4; bit 9 tile index +1 when $FF0092 set;
# bits 10-15 6-bit terrain type.
# Walkability is the $02DC0C RULE (pinned live 13/13), not a bit:
# walkable iff type in {5, 9, 18} or tile index == 0x24 (36).
WALKABLE_TYPES = (5, 9, 18)
WALKABLE_TILE = 0x24

# $D6768 price tiers ($2EA92, docs/logic.md §3.4): raw<=20: v=raw;
# 20<raw<=100: v=(raw-16)*5; raw>100: v=(raw-96)*100.
# This is the PURE $2EA92 output (raw 0 -> 0, matching the committed
# disasm/logic/price_table.txt "scaled" column). The shop floor is
# separate: the first spell of each block (raw 0) sells for 2.
def scaled_price(raw):
    if raw <= 20:
        return raw
    if raw <= 100:
        return (raw - 16) * 5
    return (raw - 96) * 100


def shop_price(record, raw):
    """Price the shop charges. The floor clamp (2) is documented for
    spells only (first spell of each block, raw 0); other records pay
    the $2EA92 value. Rec 207 (Flags, raw 0, a trade good) has no
    documented clamp — see the report."""
    v = scaled_price(raw)
    if 1 <= record <= 120:
        return max(v, 2)
    return v


def cram_word_to_rgb(w):
    """CRAM word -> (R, G, B), corrected channel order (#016, live-proven):
    r=(w>>1)&7, g=(w>>5)&7, b=(w>>9)&7; each channel scaled x*255//7."""
    r = (w >> 1) & 7
    g = (w >> 5) & 7
    b = (w >> 9) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=1))


def read_rom(rom_path):
    data = Path(rom_path).read_bytes()
    md5 = hashlib.md5(data).hexdigest()
    assert len(data) == ROM_SIZE, "ROM size %d != %d" % (len(data), ROM_SIZE)
    assert md5 == ROM_MD5, "ROM MD5 %s != %s" % (md5, ROM_MD5)
    return data

# ---------------------------------------------------------------- stage 1
def stage1_dd5c(rom, repo, outdir, log):
    """Run the #19 exporter into outdir/gfx/ and verify it against the
    committed assets/gfx/. Returns the export summary."""
    tools = repo / "tools"
    sys.path.insert(0, str(tools))
    import export_assets
    import shutil
    gfx = outdir / "gfx"
    # The four #19 dirs are fully regenerated by the exporter; clear
    # them so a re-run does not leave stale files (the stage-2 dirs
    # tilesets_rgb / sprites_rgb / chunks_corrected are preserved).
    for sub in ("tilesets", "sprites", "maps", "chunks"):
        shutil.rmtree(gfx / sub, ignore_errors=True)
    summary = export_assets.export_all(str(repo / "rop-original.gen"),
                                       str(gfx))
    # Compare the four #19 dirs individually (the stage-2 dirs in
    # gfx/ — tilesets_rgb, sprites_rgb, chunks_corrected — are this
    # pipeline's own output, not part of the #19 export).
    for sub in ("tilesets", "sprites", "maps", "chunks"):
        differing, missing, extra = export_assets.compare_dirs(
            gfx / sub, repo / "assets" / "gfx" / sub)
        assert not differing and not missing and not extra, (
            "stage1 verify failed on %s: %d differing, %d missing, "
            "%d extra" % (sub, len(differing), len(missing), len(extra)))
    log.append("stage1: exported %d records %s (skipped text %s)" % (
        summary["records"], summary["kinds"], summary["skipped_text"]))
    assert summary["records"] == 400, summary
    assert summary["kinds"] == {"tileset": 37, "sprite": 90, "map": 21,
                                "chunk": 252}, summary["kinds"]
    log.append("stage1: output matches committed assets/gfx/ "
               "(PNG by pixels, rest byte-for-byte)")
    return summary


# ---------------------------------------------------------------- stage 2
def stage2_rgb_and_chunks(rom, outdir, log):
    """True-colour RGB PNGs + corrected chunk JSONs."""
    from PIL import Image
    import export_assets

    gfx = outdir / "gfx"
    # -- RGB PNGs: PIL converts mode-P via the embedded PLTE, which the
    # #19 exporter wrote from cram_word_to_rgb (corrected #016 order).
    rgb_tiles = gfx / "tilesets_rgb"
    rgb_sprites = gfx / "sprites_rgb"
    rgb_tiles.mkdir(parents=True, exist_ok=True)
    rgb_sprites.mkdir(parents=True, exist_ok=True)
    n_rgb = 0
    for src_dir, dst_dir in ((gfx / "tilesets", rgb_tiles),
                             (gfx / "sprites", rgb_sprites)):
        for png in sorted(src_dir.glob("*.png")):
            with Image.open(png) as im:
                assert im.mode == "P", (png, im.mode)
                rgb = im.convert("RGB")
                rgb.save(dst_dir / png.name)
                n_rgb += 1
    # Spot-check: a converted pixel must equal the CRAM-derived RGB
    # for the pixel's own palette index (read from the tileset's
    # pal.json, not hardcoded).
    from assets_import import load_palette_words  # noqa: F401  (repo tools)
    pal_meta = json.loads(
        (gfx / "tilesets" / "tileset_rec06_pal.json").read_text())
    words = load_palette_words(rom, pal_meta["palette_index"])
    with Image.open(gfx / "tilesets" / "tileset_rec06.png") as im:
        idx = im.getpixel((0, 0))
    expect = cram_word_to_rgb(words[idx])
    with Image.open(rgb_tiles / "tileset_rec06.png") as im:
        got = im.getpixel((0, 0))
    assert got == expect, (got, expect, idx)
    log.append("stage2: %d RGB PNGs written (tilesets_rgb + sprites_rgb); "
               "pixel spot-check tileset_rec06 (0,0) index %d == CRAM "
               "palette %d word %d -> %s"
               % (n_rgb, idx, pal_meta["palette_index"], idx, expect))

    # -- Corrected chunk JSONs. The #19 export reads chunk words as VDP
    # tilemap words (tile/flipH/flipV/palette/priority). The corrected
    # layout (docs/maps.md, 2026-11-11) is: bits 0-8 tile-type index,
    # bit 9 height-stack flag, bit 10 step-tile flag, bit 11 hazard
    # floor, bit 12 variant flag, bits 13-15 height (0-7).
    tables = export_assets.read_records(
        rom, 0x43850, 0x44228, 252)
    corr_dir = gfx / "chunks_corrected"
    corr_dir.mkdir(parents=True, exist_ok=True)
    n_cells = 0
    heights = set()
    for idx, data in enumerate(tables):
        rows, cols = {2048: (32, 32), 242: (11, 11)}[len(data)]
        words = struct.unpack(">%dH" % (len(data) // 2), data)
        assert len(words) == rows * cols
        entries = []
        for w in words:
            entries.append({
                "tile_type": w & 0x1FF,
                "height": (w >> 13) & 7,
                "height_stack": bool(w & 0x0200),
                "step_tile": bool(w & 0x0400),
                "hazard": bool(w & 0x0800),
                "variant": bool(w & 0x1000),
            })
            heights.add((w >> 13) & 7)
        n_cells += len(entries)
        write_json(corr_dir / ("chunk_rec%03d.json" % idx),
                   {"record": idx, "rows": rows, "cols": cols,
                    "entries": entries})
    # Cross-check the correction against the #19 chunk JSON: the VDP
    # reading must be a pure relabelling of the same word.
    sample = json.loads((gfx / "chunks" / "chunk_rec233.json").read_text())
    corr = json.loads((corr_dir / "chunk_rec233.json").read_text())
    for e19, ec in zip(sample["entries"], corr["entries"]):
        w19 = (e19["tile"]
               | (0x0800 if e19["flipH"] else 0)
               | (0x1000 if e19["flipV"] else 0)
               | ((e19.get("palette") or 0) << 13)
               | (0x8000 if e19.get("priority") else 0))
        wc = (ec["tile_type"]
              | (0x0200 if ec["height_stack"] else 0)
              | (0x0400 if ec["step_tile"] else 0)
              | (0x0800 if ec["hazard"] else 0)
              | (0x1000 if ec["variant"] else 0)
              | (ec["height"] << 13))
        assert w19 == wc, (e19, ec)
    log.append("stage2: 252 corrected chunk JSONs (%d cells; heights "
               "seen %s); cross-checked rec233 word-for-word against "
               "the #19 export (pure relabelling, no data lost)"
               % (n_cells, sorted(heights)))
    return {"rgb_pngs": n_rgb, "corrected_chunks": 252, "cells": n_cells}

# ---------------------------------------------------------------- stage 3
def _u16s(rom, addr, n):
    return list(struct.unpack_from(">%dH" % n, rom, addr))


def _u32s(rom, addr, n):
    return list(struct.unpack_from(">%dI" % n, rom, addr))


def stage3_terrain(rom, outdir, log):
    """$5EDC4 + $1AE98 + $5F524 index + raw terrain-stream blob."""
    props = _u16s(rom, 0x05EDC4, 944)
    entries = []
    walkable = 0
    for tile, v in enumerate(props):
        ttype = (v >> 10) & 0x3F
        is_walk = ttype in WALKABLE_TYPES or tile == WALKABLE_TILE
        walkable += is_walk
        entries.append({
            "tile": tile, "word": v,
            "stream_offset": v & 0x1F,
            "stream_source": (v >> 5) & 1,
            "tile_minus1": bool((v >> 6) & 1),
            "row_plus1": bool((v >> 7) & 1),
            "row_plus4": bool((v >> 8) & 1),
            "tile_plus1": bool((v >> 9) & 1),
            "terrain_type": ttype,
            # $02DC0C rule (pinned live 13/13), NOT a flag bit.
            "walkable": is_walk,
        })
    descs = []
    for i in range(512):
        v = struct.unpack_from(">H", rom, 0x01AE98 + i * 2)[0]
        descs.append({
            "tile_type": i,
            "low": {"flipH": bool(v & 1), "flipV": bool((v >> 1) & 1),
                    "tile": (v >> 2) & 0x3F},
            "high": {"flipH": bool((v >> 8) & 1),
                     "flipV": bool((v >> 9) & 1),
                     "tile": (v >> 10) & 0x3F},
        })
    offs = _u32s(rom, 0x05F524, 944)
    assert all(offs[i] < offs[i + 1] for i in range(943)), "offsets not monotonic"
    assert offs[0] == 0 and 0x603E4 + offs[-1] < 0x96120
    # Raw stream bytes tile $603E4-$9611F exactly (sim_terrain.py).
    blob = rom[TERRAIN_STREAM_BASE:TERRAIN_STREAM_END]
    (outdir / "terrain_streams.bin").write_bytes(blob)
    write_json(outdir / "terrain.json", {
        "props_table": "0x05EDC4", "props_words": 944,
        "props": entries,
        "walkable_rule": "type in {5, 9, 18} or tile == 0x24 ($02DC0C, "
                         "pinned live 13/13); there is NO single "
                         "walkable flag bit in $5EDC4",
        "walkable_tiles": walkable,
        "descriptor_table": "0x01AE98", "descriptors": descs,
        "descriptor_note": "cell bit 12 selects low/high variant; "
                           "tile is 0-63 within the tileset loaded at "
                           "$FF8678; palette/priority always 0",
        "stream_table": "0x05F524", "stream_offsets": offs,
        "stream_base": "0x0603E4", "stream_blob": "terrain_streams.bin",
        "stream_blob_bytes": len(blob),
        "stream_note": "$E358 bytecode streams, NOT $DD5C; simulated "
                       "by tools/sim_terrain.py (3776 decode combos "
                       "land exactly on the terminator)",
    })
    log.append("stage3 terrain: 944 props (%d walkable by the $02DC0C "
               "rule), 512 descriptors, 944 stream offsets, blob %d B"
               % (walkable, len(blob)))
    return {"props": 944, "walkable": walkable, "streams": 944}


def stage3_locations(rom, outdir, log):
    """$D1D00 (455 x 10 B) + $D63E4 (175 x 4 B)."""
    locs = []
    for i in range(455):
        a = 0x0D1D00 + i * 10
        kx, ky = struct.unpack_from(">HH", rom, a)
        dest, b5, b6, b7 = rom[a + 4], rom[a + 5], rom[a + 6], rom[a + 7]
        tail = struct.unpack_from(">H", rom, a + 8)[0]
        locs.append({
            "record": i, "key_x": kx, "key_y": ky,
            "dest": dest, "chunk": 77 + dest,
            "grid": "11x11" if dest < 153 else "32x32",
            "raw_b5": b5, "raw_b6": b6, "raw_b7": b7, "tail": tail,
        })
    place = []
    for i in range(175):
        a = 0x0D63E4 + i * 4
        place.append({"location": i, "x": rom[a], "y": rom[a + 1],
                      "byte2": rom[a + 2], "song_byte": rom[a + 3]})
    write_json(outdir / "locations.json", {
        "location_table": "0x0D1D00", "locations": locs,
        "location_note": "key (x, y) is the world-map lookup key; dest "
                         "is the location number (10-174); chunk = "
                         "77 + dest; +5/+6/+7 bytes are undecoded, "
                         "preserved raw; tail is 0x1066 except rec 454 "
                         "(0x0000)",
        "placement_table": "0x0D63E4", "placement": place,
        "placement_note": "x, y = party placement in the room; song_byte "
                          "resolves to a song via the $32D0E picker "
                          "(docs/sound.md §7.3; e.g. loc 15 byte 34 -> "
                          "song 2 Enchanters, the picker default) — the "
                          "byte->song mapping is owned by #030 audio",
        "hazard_dispatch": "dest 158->lava(1), 160->toggle(2), "
                           "170->6, 172->traps(3), 174->sensors(5), "
                           "else 0; $FF0126==3 overrides to 4 "
                           "($01DD1A)",
    })
    log.append("stage3 locations: 455 records + 175 placement records")
    return {"locations": 455, "placement": 175}


def stage3_entities(rom, outdir, log):
    """$CD430 names + $CF1AC templates + $CECF0 spawn table."""
    names = []
    for i in range(396):
        a = 0x0CD430 + i * 16
        names.append({"index": i, "category": rom[a],
                      "name": rom[a + 1:a + 16].split(b"\x00")[0]
                      .decode("ascii", "replace")})
    spawns = []
    for i in range(202):
        a = 0x0CECF0 + i * 6
        w0, w1, w2 = struct.unpack_from(">HHH", rom, a)
        spawns.append({"index": i, "name_idx": w0,
                       "name": names[w0]["name"] if w0 < 396 else None,
                       "w1": w1, "w2": w2, "raw": rom[a:a + 6].hex()})
    templates = []
    for i in range(462):
        a = 0x0CF1AC + i * 24
        w = list(struct.unpack_from(">12H", rom, a))
        templates.append({
            "index": i,
            "name_idx": w[0],
            "name": names[w[0]]["name"] if w[0] < 396 else None,
            # w0 doubles as a spawn-table index in npc_place_group
            # (sys_struct52_scan reads +0x14 as a spawn index) — the
            # coincidence that makes the Buc scene work.
            "spawn_idx": w[0],
            "spawn_name": (spawns[w[0]]["name"]
                           if w[0] < 202 else None),
            "spawn_list": w[0:6],
            "w6": w[6], "w7": w[7], "w8": w[8], "w9": w[9],
            "w10": w[10], "w11": w[11],
            "byte_0x13": rom[a + 0x13],
            "raw": rom[a:a + 24].hex(),
        })
    write_json(outdir / "entities.json", {
        "name_table": "0x0CD430", "names": names,
        "name_note": "396 entries x 16 B: [1-byte category][15-byte "
                     "name, NUL-padded]",
        "template_table": "0x0CF1AC", "templates": templates,
        "template_note": "462 x 24 B (12 words). Copy loop writes "
                         "words 0-5 to char struct +0x14..+0x1E; word "
                         "+0x0C (w6) -> +0x20; byte +0x13 selects the "
                         "+0x18 level bits for type-1 entities; "
                         "w8/w9/w10/w11 feed the stat computation at "
                         "$23DE0. w0 is BOTH the name index and (in "
                         "npc_place_group) a spawn-table index.",
        "spawn_table": "0x0CECF0", "spawns": spawns,
        "spawn_note": "202 x 6 B: +0 word name_idx; +2/+4 words are "
                      "stat fields (level/HP/Power encoding — the "
                      "per-record decode lives in docs/logic.md; raw "
                      "bytes preserved)",
    })
    log.append("stage3 entities: 396 names, 462 templates, 202 spawns")
    return {"names": 396, "entity_templates": 462, "spawns": 202}


def stage3_items(rom, outdir, log):
    """$D66A0 categories + $D6768 price table."""
    cats = []
    for i in range(20):
        a = 0x0D66A0 + i * 10
        E, A, B, cnt = rom[a], rom[a + 1], rom[a + 2], rom[a + 3]
        w1, name_idx, w = struct.unpack_from(">HHH", rom, a + 4)
        cats.append({"category": i, "E": E, "A_sprite": A, "B_key": B,
                     "count": cnt, "cap_w1": w1,
                     "name_idx": name_idx, "base_w": w})
    prices = []
    for i in range(257):
        a = 0x0D6768 + i * 4
        name_idx, raw = struct.unpack_from(">HH", rom, a)
        prices.append({"record": i, "name_idx": name_idx,
                       "name": None, "raw": raw,
                       "scaled": scaled_price(raw),
                       "shop_price": shop_price(i, raw)})
    # Resolve names from the name table (read fresh, not from entities).
    for p in prices:
        ni = p["name_idx"]
        a = 0x0CD430 + ni * 16
        p["name"] = rom[a + 1:a + 16].split(b"\x00")[0].decode(
            "ascii", "replace") if ni < 396 else None
    write_json(outdir / "items.json", {
        "category_table": "0x0D66A0", "categories": cats,
        "category_note": "E = vessel mode-5 sub-value; A = $B86AE "
                         "sprite shown with the item message; B = "
                         "merchant-kind key (char +0x17); count = "
                         "records in the category; w1 = cap (1, 99 "
                         "goods, 9999 healing); w = base index into "
                         "the price table",
        "price_table": "0x0D6768", "prices": prices,
        "price_note": "257 records x 4 B: +0 word name_idx, +2 word "
                      "raw value; scaled = the $2EA92 output "
                      "(raw<=20: v=raw; 20<raw<=100: v=(raw-16)*5; "
                      "raw>100: v=(raw-96)*100; raw 0 -> 0, matching "
                      "price_table.txt). shop_price = what the shop "
                      "charges: for spells (1-120) the documented "
                      "floor of 2 applies (first spell of each block, "
                      "raw 0, sells for 2); otherwise shop_price == "
                      "scaled. Rec 207 (Flags, raw 0, a trade good) "
                      "has no documented clamp — open question. "
                      "Ranges: 1-120 spells, 121-135 rings/quest "
                      "words, 136-137 Sleep/Meal, 138-152 keys, "
                      "153-158 guild symbols, 159-185 quest items, "
                      "186-216 trade goods + food/water + transports, "
                      "217-218 Heal/Pow Up, 219-256 notes/tomes/"
                      "scraps/maps",
    })
    log.append("stage3 items: 20 categories, 257 price records")
    return {"categories": 20, "prices": 257}


def stage3_spells(rom, outdir, log):
    """120 spells (price recs 1-120) + 6 rank tables (21 x 6 B)."""
    disciplines = ["Sorc", "Knight", "Archer", "Necro", "Enchnt",
                   "Conjur"]
    characters = ["Buc", "Slash", "Feather", "Mortimer", "Obliky",
                  "Alexi"]
    spells = []
    for i in range(1, 121):
        a = 0x0D6768 + i * 4
        name_idx, raw = struct.unpack_from(">HH", rom, a)
        an = 0x0CD430 + name_idx * 16
        name = rom[an + 1:an + 16].split(b"\x00")[0].decode(
            "ascii", "replace")
        block = (i - 1) // 20
        spells.append({
            "id": i, "block": block + 1,
            "discipline": disciplines[block],
            "character": characters[block],
            "name_idx": name_idx, "name": name, "raw": raw,
            "scaled": scaled_price(raw),
            "shop_price": shop_price(i, raw),
        })
    rank_bases = [0x0D6B6C, 0x0D6BEA, 0x0D6C68,
                  0x0D6CE6, 0x0D6D64, 0x0D6DE2]
    rank_tables = []
    for r, base in enumerate(rank_bases, start=1):
        recs = []
        for j in range(21):
            w0, w1, w4 = struct.unpack_from(">HHH", rom, base + j * 6)
            recs.append({
                "record": j, "w0": w0, "w1": w1, "w4": w4,
                "damage_base": (w0 & 0x7F) // 3,
                "effect_class": (w0 >> 8) & 7,
                "heal_target": bool((w0 >> 11) & 1),
                "effect_param": w1 & 0xF,
                "action_code": w1 >> 4,
                "power_cost_base": w4,
            })
        rank_tables.append({"rank": r, "table": "0x%05X" % base,
                            "records": recs})
    write_json(outdir / "spells.json", {
        "spell_list": "price records 1-120 ($D6768)", "spells": spells,
        "spell_note": "block N = discipline N (1 Sorc/Buc, 2 Knight/"
                      "Slash, 3 Archer/Feather, 4 Necro/Mortimer, 5 "
                      "Enchnt/Obliky, 6 Conjur/Alexi) — pinned from "
                      "code + guide. The spell bought (price record) "
                      "and the spell cast (rank-table record) are "
                      "different objects, joined by the caster's "
                      "+0x25 byte and rank.",
        "rank_tables": rank_tables,
        "rank_note": "6 distinct effect tables (ranks 7-10 reuse rank "
                     "2's table), 21 records x 6 B each, indexed by "
                     "the caster's +0x25 byte. Cost = w4 * (modifier+1) "
                     "* 3, modifier = (caster.+0x2C >> 8) & 3 ($3C2C0). "
                     "Records 19 and 20 are identical in every table "
                     "(rec 19 is the top spell). Cast/resist/hit "
                     "poses are figure templates 16-19 / 20-23 / 24-27.",
        "discipline_note": "'Arrow' vs 'Feather': the fan guide calls "
                           "the archer Arrow, the ROM name is Feather "
                           "(name 61); also a spell named Arrow (block "
                           "3, rec 44). Unresolved until a live "
                           "new-game character-creation trace (#020). "
                           "Do not rename either in the remake.",
    })
    log.append("stage3 spells: 120 spells, 6 rank tables x 21 records")
    return {"spells": 120, "rank_tables": 6}


def stage3_figures(rom, outdir, log):
    """$197B0 figure templates (56 x 36 B)."""
    templates = []
    for i in range(56):
        a = 0x0197B0 + i * 36
        groups = []
        for g in range(4):
            s, p, dx, dy = struct.unpack_from(">hhhh", rom, a + g * 8)
            groups.append({"stream_offset": s, "param": p,
                           "dx": dx, "dy": dy})
        stepcode, stepphase = struct.unpack_from(">HH", rom, a + 0x20)
        templates.append({"template": i, "groups": groups,
                          "stepcode": stepcode,
                          "stepphase": stepphase})
    write_json(outdir / "figures.json", {
        "table": "0x0197B0", "templates": templates,
        "note": "56 x 36 B: 4 phase groups x 8 B + 4-byte tail. Group "
                "= (E358 stream-index offset, E358 4th-arg param, "
                "x-offset, y-offset). Groups 0-3 are the 4 animation "
                "frames, selected one per frame by geom+$A (cycles "
                "0-3 every frame). Tail: stepcode (+0x20) is the "
                "dispatch case for $0226BC (0-5), stepphase (+0x22) "
                "the frame it belongs to. Templates 16-19 cast, "
                "20-23 resist, 24-27 hit, 36-55 walk (36+facing dir).",
    })
    log.append("stage3 figures: 56 templates")
    return {"figure_templates": 56}

def stage3_text(rom, outdir, log):
    """Dictionary (3,466 words) + dialogue records ($DDBD8, 1,184)."""
    # extract_text.py binds ROM/OUT from sys.argv at import time.
    _argv = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        import extract_text
    finally:
        sys.argv = _argv
    offs = struct.unpack_from(">%dH" % (TEXT_N_WORDS + 1), rom,
                              TEXT_OFF_TABLE)
    assert offs[0] == 0 and offs[TEXT_N_WORDS] == TEXT_BLOB_END - TEXT_BLOB_START
    blob = rom[TEXT_BLOB_START:TEXT_BLOB_END]
    words = [blob[offs[i - 1]:offs[i]].decode("ascii")
             for i in range(1, TEXT_N_WORDS + 1)]
    records = []
    for r in range(TEXT_N_RECORDS):
        ptr, ln, typ = struct.unpack_from(">IIH", rom,
                                         TEXT_RECORD_TABLE + r * 10)
        rec = {"record": r, "ptr": ptr, "len": ln, "type": typ}
        if typ == 5 and r < 1181:
            count = (ln >> 1) + 1
            arr = struct.unpack_from(">%dH" % (count + 1), rom,
                                     TEXT_ARRAY_BASE + ptr)
            text = extract_text.expand_record_words(rom, arr, count)
            rec["rendered"] = text
            rec["entries"] = [
                {"word_idx": e & 0x3FFF,
                 "sep": [" ", ",", ".", "?"][(e >> 14) & 3]}
                for e in arr[:ln // 2]]
        elif r in (1181, 1182):
            rec["note"] = "literal <NA> placeholder"
        elif r == 1183:
            rec["note"] = ("malformed: array overruns into $EB772 code; "
                           "not rendered")
        records.append(rec)
    write_json(outdir / "text.json", {
        "dictionary_blob": "0x0D6EBA-0x0DC0C0",
        "dictionary_offset_table": "0x0DC0C2",
        "dictionary": words,
        "dictionary_note": "3,466 words, 1-based indices; word i = "
                           "blob[offs[i-1]:offs[i]]. The 2 bytes at "
                           "0x0DC0C0-0x0DC0C1 (FF 6F) sit between the "
                           "blob and the offset table and are not text.",
        "record_table": "0x0DDBD8",
        "records": records,
        "record_note": "1,184 records x 10 B (u32 ptr, u32 len, u16 "
                       "type; all type 5). Rendered by $136FC: word "
                       "indices are 1-based, each u16 entry is low 14 "
                       "bits word index + top 2 bits separator "
                       "(space/,/./?); the loop starts at array[1] "
                       "and reads one entry past the record (the next "
                       "record's first entry). Rec 0 drops its 'An' "
                       "(array[0] is skipped) — the game renders "
                       "'unknown building.', not 'An unknown...'. "
                       "Ground truth: 647/649 fan-transcribed "
                       "sentences appear verbatim.",
    })
    log.append("stage3 text: %d dictionary words, %d dialogue records "
               "(%d rendered)"
               % (len(words), len(records),
                  sum(1 for r in records if "rendered" in r)))
    return {"dictionary_words": len(words),
            "dialogue_records": len(records)}


def stage3_conversations(rom, outdir, log):
    """$D3102 conversation table (1,005 x 12 B) + $D601E grants."""
    conv = []
    for i in range(1005):
        a = 0x0D3102 + i * 12
        w = list(struct.unpack_from(">6H", rom, a))
        ev1, ev2 = w[5], w[4]
        conv.append({
            "record": i, "kind": w[0],
            "raw_w1": w[1], "raw_w2": w[2], "raw_w3": w[3],
            "event_first": {"type": (ev1 >> 12) & 0xF,
                            "delta": ev1 & 0xFFF, "word": ev1},
            "event_second": {"type": (ev2 >> 12) & 0xF,
                             "delta": ev2 & 0xFFF, "word": ev2},
        })
    grants = []
    for i in range(161):
        a = 0x0D601E + i * 6
        w0, w1 = struct.unpack_from(">HH", rom, a)
        grants.append({
            "record": i, "code": w0 & 0x7FF, "type": (w0 >> 11) & 0x1F,
            "word0": w0, "location_word": w1,
            "b4": rom[a + 4], "b5": rom[a + 5],
        })
    write_json(outdir / "conversations.json", {
        "conversation_table": "0x0D3102", "records": conv,
        "conversation_note": "1,005 x 12 B. +0 word = kind (the "
                             "argument to npc_attitude_positive); +8 "
                             "word = second event word, +10 word = "
                             "first event word, both packed as "
                             "(type << 12) | delta; the first is "
                             "dispatched first, the second only if "
                             "the first leaves no effect. +2/+4/+6 "
                             "words are undecoded, preserved raw. "
                             "11 records have kind == 8 (Bribe).",
        "grant_table": "0x0D601E", "grants": grants,
        "grant_note": "161 x 6 B: +0 word = code (low 11 bits) + "
                      "type (high 5 bits); +2 word = location word; "
                      "+4/+5 bytes = grant conditions (not decoded). "
                      "Grant categories present (code//64): {0:54, "
                      "1:37, 5:1, 10:7, 12:11, 13:20, 14:6, 17:23, "
                      "18:2}; no grants for cats 2,3,4,6,7,8,9,11,15,"
                      "16,19.",
    })
    log.append("stage3 conversations: 1,005 records, 161 grants")
    return {"conversations": 1005, "grants": 161}


def stage3_palettes(rom, outdir, log):
    """Master palette table $0CC9D8 (31 x 16 CRAM words)."""
    pals = []
    for i in range(31):
        words = _u16s(rom, 0x0CC9D8 + i * 32, 16)
        pals.append({"palette": i, "words": words,
                     "rgb": [list(cram_word_to_rgb(w)) for w in words]})
    write_json(outdir / "palettes.json", {
        "table": "0x0CC9D8", "palettes": pals,
        "note": "31 palettes x 16 CRAM words. CRAM order (corrected "
                "#016, live-proven): r=(w>>1)&7, g=(w>>5)&7, "
                "b=(w>>9)&7; each channel scaled x*255//7.",
    })
    log.append("stage3 palettes: 31 palettes")
    return {"palettes": 31}


def stage3_scripts(rom, outdir, log):
    """Event scripts (10 cases, 198 records x 8 B, raw bytes)."""
    cases = []
    total = 0
    for case in sorted(SCRIPT_CASES):
        addr, count = SCRIPT_CASES[case]
        recs = [rom[addr + i * 8: addr + i * 8 + 8].hex()
                for i in range(count)]
        cases.append({"case": case, "script_addr": "0x%05X" % addr,
                      "records": count, "bytes": recs})
        total += count
    write_json(outdir / "scripts.json", {
        "dispatch": "menu_select_screen ($02D3DC) has exactly 10 cases; "
                    "case -> script address above. sys_event_run "
                    "($02D56A) runs them, ~1 engine call per 4 ticks.",
        "op_table": {str(op): {"handler": h,
                                "name": SCRIPT_OP_NAMES[op]}
                     for op, h in sorted(SCRIPT_OPS.items())},
        "op_note": "Record byte 0 is a SIGNED op code (-13 = pose, "
                   "+5 = move, +6 = text, +4 = SFX+mode-6 spawn, "
                   "+0 = grant, +15 = text-event resolve). The "
                   "record arg layout per op is in docs/cutscenes.md "
                   "and the per-scene docs. The script INTERPRETER "
                   "is game logic (a later issue); this file is the "
                   "script DATA only. Op-6 displays text record "
                   "w4 + 96 (the +96 rule). No scene casts a spell "
                   "record (cases 0/1 fire mode-6 projectiles via "
                   "op-13 pose + op-4 spawn).",
        "cases": cases,
    })
    log.append("stage3 scripts: %d records across 10 cases" % total)
    return {"script_records": total}


# ---------------------------------------------------------------- stage 4
def stage4_verify(rom, repo, outdir, log):
    """Cross-checks against the committed disasm/ dumps + counts."""
    fails = []

    def check(name, cond, detail=""):
        log.append("verify %-28s %s %s" % (
            name, "OK" if cond else "FAIL", detail))
        if not cond:
            fails.append(name)

    # 1. Committed dump spot-checks (full-file where machine-readable).
    # items.txt / price_table.txt are human-formatted; verify the tables
    # by re-reading the ROM values they quote instead.
    def price_rec(i):
        return struct.unpack_from(">HH", rom, 0x0D6768 + i * 4)
    check("price rec 1 Stun", price_rec(1) == (157, 0))
    check("price rec 2 Clue", price_rec(2) == (164, 36))
    check("price rec 186 Food", price_rec(186) == (300, 12))
    check("price rec 187 Water", price_rec(187) == (301, 8))
    check("price rec 253 Corpse", price_rec(253) == (156, 1))
    check("price rec 120 raw 125", price_rec(120) == (279, 125))
    # spell rank tables: recs 19 and 20 identical in every table.
    rank_bases = [0x0D6B6C, 0x0D6BEA, 0x0D6C68,
                  0x0D6CE6, 0x0D6D64, 0x0D6DE2]
    for r, base in enumerate(rank_bases, start=1):
        a19 = rom[base + 19 * 6: base + 20 * 6]
        a20 = rom[base + 20 * 6: base + 21 * 6]
        check("rank %d recs 19==20" % r, a19 == a20)
    # names: first/last + the student names.
    def name(i):
        a = 0x0CD430 + i * 16
        return rom[a + 1:a + 16].split(b"\x00")[0].decode()
    check("names 57/141-145", (name(57), name(141), name(142),
          name(143), name(144), name(145)) ==
          ("Buc", "Roakus", "Imino", "Yoppa", "Fezzik", "Darius"))
    check("names 0/395", (name(0), name(395)) == ("Nobody", "memo"))
    # $D1D00 rec 30 key/dest + rec 454 tail.
    r30 = rom[0x0D1D00 + 30 * 10: 0x0D1D00 + 30 * 10 + 10]
    check("loc rec 30", (struct.unpack_from(">HH", r30, 0) == (116, 113)
          and r30[4] == 156 and r30[8:] == b"\x10\x66"), r30.hex())
    r454 = rom[0x0D1D00 + 454 * 10: 0x0D1D00 + 454 * 10 + 10]
    check("loc rec 454 tail 0", r454[8:] == b"\x00\x00", r454.hex())
    # $D63E4 spot values.
    check("placement 15/53/156/170",
          [(rom[0x0D63E4 + l * 4 + k]) for l in (15, 53, 156, 170)
           for k in range(4)] ==
          [5, 8, 0, 34, 8, 5, 3, 10, 29, 16, 3, 141, 15, 30, 0, 7])
    # $5EDC4 walkability rule on the known cells.
    def ttype(t):
        return (struct.unpack_from(">H", rom, 0x05EDC4 + t * 2)[0] >> 10) & 0x3F
    check("terrain types 28/29 sea=0", (ttype(28), ttype(29)) == (0, 0))
    check("terrain type 279 road=9", ttype(279) == 9)
    check("terrain tile 36 type 6", ttype(36) == 6)
    # Descriptor: tile 28 -> tile 13, no flips.
    d28 = struct.unpack_from(">H", rom, 0x01AE98 + 28 * 2)[0]
    check("descriptor 28", d28 == 0x3434, hex(d28))
    # Terrain-stream table: 944 offsets, monotonic, in range.
    offs = _u32s(rom, 0x05F524, 944)
    check("stream offsets", offs[0] == 0
          and all(offs[i] < offs[i + 1] for i in range(943))
          and 0x603E4 + offs[-1] < 0x96120,
          "last 0x%05X" % offs[-1])
    # Text: dictionary sentinel + record 0 quirk.
    offs_t = struct.unpack_from(">3467H", rom, TEXT_OFF_TABLE)
    check("dictionary sentinels", offs_t[0] == 0
          and offs_t[3466] == TEXT_BLOB_END - TEXT_BLOB_START)
    # Output counts.
    manifest = json.loads((outdir / "manifest.json").read_text())
    check("manifest counts",
          manifest["counts"]["records"] == 400
          and manifest["counts"]["dictionary_words"] == 3466
          and manifest["counts"]["dialogue_records"] == 1184
          and manifest["counts"]["locations"] == 455
          and manifest["counts"]["names"] == 396
          and manifest["counts"]["entity_templates"] == 462
          and manifest["counts"]["figure_templates"] == 56
          and manifest["counts"]["spawns"] == 202
          and manifest["counts"]["spells"] == 120)
    return fails


def write_manifest(outdir, counts, log):
    manifest = {
        "pipeline": "m7_export.py (M7 asset pipeline, "
                    "docs/tribute-remake.md #024 workstream)",
        "source_rom_md5": ROM_MD5,
        "source_rom": "Rings of Power (USA, Europe).gen, 1,048,576 B",
        "format_version": 1,
        "counts": counts,
        "layout": {
            "gfx/tilesets": "indexed PNGs + pal.json (#19 export, archival)",
            "gfx/sprites": "indexed PNGs + pal.json (#19 export, archival)",
            "gfx/maps": "map JSONs (#19 export)",
            "gfx/chunks": "chunk JSONs, VDP-keyed (#19 export, archival)",
            "gfx/tilesets_rgb": "true-colour RGB PNGs (engine-loadable)",
            "gfx/sprites_rgb": "true-colour RGB PNGs (engine-loadable)",
            "gfx/chunks_corrected": "chunk JSONs, corrected cell-word "
                                    "layout (engine-loadable)",
            "terrain.json": "$5EDC4 props + $1AE98 descriptors + "
                            "$5F524 stream index",
            "terrain_streams.bin": "raw $E358 stream bytes ($603E4-$9611F)",
            "locations.json": "$D1D00 + $D63E4",
            "entities.json": "$CD430 names + $CF1AC templates + $CECF0 spawns",
            "items.json": "$D66A0 categories + $D6768 price table",
            "spells.json": "120 spells + 6 rank tables",
            "figures.json": "$197B0 figure templates",
            "text.json": "dictionary + $DDBD8 dialogue records",
            "conversations.json": "$D3102 + $D601E grants",
            "palettes.json": "$0CC9D8 master palette table (31)",
            "scripts.json": "event scripts, 10 cases, 198 records (raw)",
        },
        "known_gaps": [
            "walkable flag bit in $5EDC4: RESOLVED as 'no such bit "
            "exists' — walkability is the $02DC0C rule (type in "
            "{5, 9, 18} or tile == 0x24), pinned live 13/13 "
            "(docs/maps.md). Remaining open item: the mode-$17 "
            "live re-run with $FF00A4=1.",
            "food/water routine: RESOLVED since the brief — "
            "docs/logic.md §3.7 locates and live-verifies it "
            "($02C0EE goods adjust, $024F44/$024F78 per-step cost, "
            "$FFC364/$FFC366 food/water, CAMP $03019A).",
            "$D1D00 +5/+6/+7 bytes: undecoded, preserved raw.",
            "$D3102 +2/+4/+6 words: undecoded, preserved raw.",
            "$D63E4 song_byte -> song mapping: owned by #030 audio "
            "(via the $32D0E picker; e.g. loc 15 byte 34 -> song 2 "
            "Enchanters).",
            "names_cd431.txt needs regenerating at 396 entries "
            "(entries past 396 are binary data misread as names) — "
            "this pipeline exports exactly 396.",
            "'Arrow' vs 'Feather': unresolved until a live new-game "
            "character-creation trace (#020). Do not rename either.",
            "Price record 207 (Flags, a trade good) has raw value 0, "
            "so its scaled price is 0; the shop floor of 2 is "
            "documented for spells only, so no clamp is applied to "
            "it here — open question whether the shop clamps all "
            "prices or only spells.",
            "Rendered dialogue text may carry a trailing separator "
            "(e.g. rec 0 renders 'unknown building. ' with a trailing "
            "space) — a faithful artifact of the $136FC renderer, "
            "which appends each entry's separator after the word. "
            "Engines should strip trailing whitespace on display; "
            "the raw word-index arrays are in each record's "
            "'entries' field.",
            "The $96120 map dims/tileset/palette table (KNOWN, "
            "tools/decode_map.py) covers 21 of 62 records; the "
            "remaining 41 are tilesets (37) + text (4), not maps.",
        ],
        "not_built_here": [
            "game rules (movement, combat, script engine, shop, "
            "spells-as-cast) — later issues",
            "audio (songs/SFX) — #030",
            "save system — #031",
            "the Esenthel project itself — #023",
        ],
    }
    write_json(outdir / "manifest.json", manifest)
    log.append("manifest written (%d counts)" % len(counts))
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=None)
    ap.add_argument("--repo", default=str(_REPO_DEFAULT))
    ap.add_argument("--out", default=str(_WORKTREE / "tribute" / "assets"))
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    rom_path = args.rom or str(repo / "rop-original.gen")
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    log = []

    rom = read_rom(rom_path)
    log.append("stage0: ROM MD5 %s verified (%d B)" % (ROM_MD5, ROM_SIZE))

    s1 = stage1_dd5c(rom, repo, outdir, log)
    s2 = stage2_rgb_and_chunks(rom, outdir, log)
    counts = {"records": s1["records"]}
    counts.update({k: v for k, v in s1["kinds"].items()})
    counts["rgb_pngs"] = s2["rgb_pngs"]
    counts["corrected_chunks"] = s2["corrected_chunks"]
    counts["chunk_cells"] = s2["cells"]
    for fn in (stage3_terrain, stage3_locations, stage3_entities,
               stage3_items, stage3_spells, stage3_figures,
               stage3_text, stage3_conversations, stage3_palettes,
               stage3_scripts):
        counts.update(fn(rom, outdir, log))
    write_manifest(outdir, counts, log)
    fails = stage4_verify(rom, repo, outdir, log)
    print("\n".join(log))
    if fails:
        print("FAILED: %s" % ", ".join(fails))
        return 1
    print("ALL STAGES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
