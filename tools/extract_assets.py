#!/usr/bin/env python3
"""Asset extraction pipeline (issue #024): ROM -> tribute/assets/.

Implements the export contract in docs/tribute/024-asset-pipeline.md
by WRAPPING the repo's proven decoders (never re-implementing them):
  palettes : master table 0x0CC9D8, 31 x 16 words, 9-bit BGR
  tiles    : $96120 tile-class records via tools/render_tiles.py
             ($DD5C decompress + packed 2px/byte decode, palette 1)
  sprites  : $B86AE 90 records via tools/render_tiles.py sprite path
             ([32B embedded palette][36 tiles] -> 48x48 PNG)
  maps     : the 21 $1194A-proven tilemap records via
             tools/decode_map.py (KNOWN dims/tileset/palette)
  text     : $DDBD8 dialogue via tools/extract_text.py expansion
             (dialogue.json) + the four $DD5C text streams
             (books.json) + the 3,466-word dictionary
             (dictionary.json)
Outputs land in tribute/assets/ (git-ignored: ROM-derived build
products) with a manifest.json recording every export's source
record and parameters. The shipped tribute does NOT read the ROM
at runtime; export happens at build time from the user's own dump.

Run with the system python3 (needs PIL, which tools/render_tiles.py
already requires):  python3 tools/extract_assets.py
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
ROM = ROOT / "rop-original.gen"
OUT = ROOT / "tribute" / "assets"
sys.path.insert(0, str(TOOLS))

PALETTE_TABLE, N_PALETTES = 0x0CC9D8, 31
# $96120 records that are text streams (graphics inventory, #005):
# their sources are exactly the four $DD5C text streams of #004.
TEXT_RECORDS = {32: "Book of Nexus", 55: "Book of Buc",
                59: "Title credits", 61: "Bestiary / classes"}
TILESET_PALETTE = 1     # render_tiles.py default table palette
TILE_SCALE = 2          # build choice; sizes recorded in manifest


def md_word_to_rgb(w):
    return tuple(((w >> s) & 7) * 255 // 7 for s in (9, 5, 1))


def export_palettes(data):
    pals = []
    for n in range(N_PALETTES):
        words = struct.unpack_from(">16H", data, PALETTE_TABLE + n * 32)
        pals.append([list(md_word_to_rgb(w)) for w in words])
    (OUT / "palettes.json").write_text(json.dumps(pals, indent=1))
    return {"count": N_PALETTES, "file": "palettes.json"}


def export_tiles(data, map_records):
    import render_tiles
    entries = []
    pal = render_tiles.get_palette(data, TILESET_PALETTE)
    for n in range(62):
        if n in map_records or n in TEXT_RECORDS:
            continue
        blob, src, declen = render_tiles.record_bytes(data, n)
        img = render_tiles.render_tiles(blob, pal, cols=16,
                                        scale=TILE_SCALE, gap=0)
        name = f"tileset_rec{n:02d}.png"
        img.save(OUT / "tiles" / name)
        entries.append({"record": n, "src": f"0x{src:06X}",
                        "declen": declen, "tiles": declen // 32,
                        "palette": TILESET_PALETTE, "file": name,
                        "png_size": list(img.size)})
    return {"count": len(entries), "records": entries}


def export_sprites(data):
    import render_tiles
    entries = []
    for n in range(90):
        blob, src, declen = render_tiles.sprite_bytes(data, n)
        words = struct.unpack_from(">16H", blob, 0)
        pal = [render_tiles.md_word_to_rgb(w) for w in words]
        img = render_tiles.render_tiles(blob[32:], pal, cols=6,
                                        scale=1, gap=0)
        name = f"sprite_rec{n:02d}.png"
        img.save(OUT / "sprites" / name)
        entries.append({"record": n, "src": f"0x{src:06X}",
                        "declen": declen, "file": name,
                        "png_size": list(img.size)})
    return {"count": len(entries), "records": entries}


def export_maps(data):
    import decode_map
    pairs = {22: 48, 48: 22, 23: 49, 49: 23, 24: 50, 50: 24,
             25: 51, 51: 25, 26: 52, 52: 26}
    entries = []
    for n in sorted(decode_map.KNOWN):
        rows, cols, tileset, pal, loader, note = decode_map.KNOWN[n]
        words = decode_map.map_words(data, n)
        rec = {"record": n, "rows": rows, "cols": cols,
               "tileset_record": tileset, "palette": pal,
               "loader": f"0x{loader:05X}", "note": note,
               "entries_expected": rows * cols,
               "entries_found": len(words),
               "entries": [{"tile": w & 0x07FF,
                            "flipH": bool(w & 0x0800),
                            "flipV": bool(w & 0x1000)} for w in words]}
        if n in pairs:
            rec["layer_alt"] = pairs[n]
        name = f"map_rec{n:02d}.json"
        (OUT / "maps" / name).write_text(json.dumps(rec, indent=1))
        entries.append({"record": n, "file": name,
                        "dims": [rows, cols],
                        "entries": len(words),
                        "rectangular": len(words) == rows * cols})
    return {"count": len(entries), "records": entries}


def export_text(data):
    import extract_text as et
    # dictionary (1-based indices, $136FC)
    offs = struct.unpack_from(">%dH" % (et.N_WORDS + 1), data,
                              et.OFF_TABLE)
    blob = data[et.BLOB_START:et.BLOB_END]
    words = [blob[offs[i - 1]:offs[i]].decode("ascii")
             for i in range(1, et.N_WORDS + 1)]
    (OUT / "text" / "dictionary.json").write_text(
        json.dumps({"count": len(words), "words": words}, indent=1))
    # dialogue records ($DDBD8): verbatim expansion, record 0's
    # dropped "An" included exactly as shipped (#004 caveat)
    records, skipped = [], []
    for r in range(et.N_RECORDS):
        ptr, ln, typ = struct.unpack_from(
            ">IIH", data, et.RECORD_TABLE + r * 10)
        if typ != 5 or r >= et.N_REAL_RECORDS + 2:
            skipped.append(r)
            continue
        count = (ln >> 1) + 1
        arr = struct.unpack_from(">%dH" % (count + 1), data,
                                 et.ARRAY_BASE + ptr)
        records.append({"index": r,
                        "text": et.expand_record_words(
                            data, arr, count).strip()})
    (OUT / "text" / "dialogue.json").write_text(json.dumps(
        {"records": records, "skipped": skipped,
         "note": "records 1181/1182 are placeholders whose "
                 "expansion is the literal string '<NA>'; 1183 is "
                 "the malformed dummy, not exported (see "
                 "extract_text.py)"},
        indent=1, ensure_ascii=False))
    # books: the four $DD5C text streams (= $96120 TEXT_RECORDS)
    books = []
    for rec_n, title in sorted(TEXT_RECORDS.items()):
        ptr, ln, typ = struct.unpack_from(
            ">IIH", data, 0x96120 + rec_n * 10)
        out, used = et.dd5c_decompress(data, 0x9638C + ptr)
        books.append({"title": title, "table_record": rec_n,
                      "src": f"0x{0x9638C + ptr:06X}",
                      "text": out.decode("ascii", "replace")})
    (OUT / "text" / "books.json").write_text(
        json.dumps({"books": books}, indent=1, ensure_ascii=False))
    return {"dialogue_records": len(records), "skipped": skipped,
            "dictionary_words": len(words), "books": len(books)}


def main():
    if not ROM.exists():
        print("extract_assets: BLOCKED — rop-original.gen not present. "
              "Place your own verified dump (MD5 "
              "30c18fdbe2183f64702ae9f1a45d63f9) in the repo root and "
              "re-run. Nothing exported.")
        return 1
    data = ROM.read_bytes()
    if len(data) != 1_048_576:
        print(f"extract_assets: FAIL — ROM is {len(data)} bytes, "
              "expected 1048576")
        return 1
    for sub in ("tiles", "sprites", "maps", "text"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    import decode_map
    manifest = {"rom_md5": hashlib.md5(data).hexdigest(),
                "contract": "docs/tribute/024-asset-pipeline.md"}
    manifest["palettes"] = export_palettes(data)
    print("extract_assets:", manifest["palettes"])
    manifest["tiles"] = export_tiles(data, set(decode_map.KNOWN))
    print("extract_assets: tiles:", manifest["tiles"]["count"],
          "tilesets")
    manifest["sprites"] = export_sprites(data)
    print("extract_assets: sprites:", manifest["sprites"]["count"])
    manifest["maps"] = export_maps(data)
    print("extract_assets: maps:", manifest["maps"]["count"])
    manifest["text"] = export_text(data)
    print("extract_assets: text:", manifest["text"])
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print("extract_assets: manifest -> tribute/assets/manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
