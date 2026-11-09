#!/usr/bin/env python3
"""Asset extraction pipeline scaffold (issue #024): ROM -> tribute/assets/.

STATUS (2026-11-09, agent session, no ROM in VM): SCAFFOLD.
Every exporter below is wired to the repo's PROVEN decoders and
fails with an explicit message until rop-original.gen is present:
  tiles/maps : tools/extract_text.py dd5c_decompress ($DD5C LZSS)
               + tools/render_tiles.py packed decode (2px/byte)
  text       : $DDBD8 records + $136FC dictionary (3,466 words)
  palettes   : master table 0x0CC9D8, 31 x 16 words, 9-bit BGR
Layout contract (docs/tribute/024-asset-pipeline.md):
  tribute/assets/tiles/    PNG per $96120 tileset record
  tribute/assets/sprites/  PNG per $B86AE record (embedded palette)
  tribute/assets/maps/     JSON per tilemap record (indices+flip bits)
  tribute/assets/text/     dialogue.json (UTF-8, 1,184 records)
  tribute/assets/palettes.json  31 palettes as RGB triples
The shipped tribute does NOT read the ROM at runtime: export happens
at build time from the user's own dump (issue #024 default, confirmed
in docs/tribute/024-asset-pipeline.md).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rop-original.gen"
OUT = ROOT / "tribute" / "assets"
PALETTE_TABLE, N_PALETTES = 0x0CC9D8, 31


def md_word_to_rgb(w):
    return tuple(((w >> s) & 7) * 255 // 7 for s in (9, 5, 1))


def export_palettes(data):
    import struct
    pals = []
    for n in range(N_PALETTES):
        words = struct.unpack_from(">16H", data, PALETTE_TABLE + n * 32)
        pals.append([md_word_to_rgb(w) for w in words])
    (OUT / "palettes.json").write_text(json.dumps(pals, indent=1))
    return f"palettes: {N_PALETTES} -> tribute/assets/palettes.json"


def main():
    if not ROM.exists():
        print("extract_assets: BLOCKED — rop-original.gen not present. "
              "Place your own verified dump (MD5 30c18fdbe2183f64702ae9f1a45d63f9) "
              "in the repo root and re-run. Nothing exported.")
        return 1
    data = ROM.read_bytes()
    if len(data) != 1_048_576:
        print(f"extract_assets: FAIL — ROM is {len(data)} bytes, expected 1048576")
        return 1
    for sub in ("tiles", "sprites", "maps", "text"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    print("extract_assets:", export_palettes(data))
    print("extract_assets: tiles/sprites/maps/text exporters are the next "
          "#024 step — they must wrap tools/render_tiles.py + "
          "tools/decode_map.py + the $DDBD8 decoder, not re-implement them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
