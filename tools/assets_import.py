#!/usr/bin/env python3
"""Asset import pipeline (issue #19): PNG/JSON -> $DD5C records.

The inverse of tools/extract_assets.py (issue #024, on the
agent/all-open-issues branch — not on main; this module implements
against its documented output format, read from that branch's
tools/extract_assets.py at commit 9681cb3):

  extract (export)                        import (this module)
  ----------------                        ---------------------
  $96120 tileset -> tileset_recNN.png     PNG + palette -> 4bpp tiles
  $B86AE sprite   -> sprite_recNN.png     PNG + palette -> [32B pal][tiles]
  $96120 map     -> map_recNN.json        map JSON -> tilemap words
  $43850 chunk   -> (not exported)        chunk JSON -> tilemap words

Tile format (verified #005/#016): 4bpp PACKED, 2 pixels/byte, high
nibble first. A tile is 8x8 pixels = 32 bytes. Tilemap words are
big-endian u16 in VDP format: bits 0-10 tile index, 0x0800 flip-H,
0x1000 flip-V, bits 13-14 palette, bit 15 priority.

CRAM order (corrected #016, live-proven): r=(w>>1)&7, g=(w>>5)&7,
b=(w>>9)&7; each channel scaled x*255//7. The inverse (RGB -> word)
is exact only for the 8 scaled values per channel (0, 36, 72, 109,
145, 182, 218, 255); any other RGB value is an off-palette colour
and is rejected.

PNG input — two modes:
  * Indexed (mode 'P'): each pixel IS the palette index (0-15).
    Exact and unambiguous. This is the recommended build input.
  * RGB (mode 'RGB'): each pixel is mapped back to a palette index
    via the palette. This is what extract_assets.py produces — but
    it is LOSSY when the palette has duplicate RGB values: palette 1
    has entries 0 and 1 both black (0,0,0), and both are heavily used
    in the tilesets (107,104 px index 0 vs 90,036 px index 1), so a
    black RGB pixel cannot be told apart. 75/90 sprite palettes also
    have duplicate RGBs. RGB import therefore reports every ambiguous
    pixel (count + first locations) and resolves ties to the LOWEST
    index; it cannot round-trip byte-identically where the original
    used the higher duplicate. Use indexed PNGs for byte-identical
    builds (see the round-trip report in .scratch-dd5c/).

Sprite palettes: a sprite PNG cannot carry its 16-word palette — the
PNG only shows colours the tiles actually use, so unreferenced
palette entries are unrecoverable from the PNG alone. The palette is
therefore a separate input: a JSON file {"palette_words": [16 ints]}
(CRAM words, big-endian u16 as stored) or {"palette": [[r,g,b], ...]}
(RGB triples, converted with the corrected order). extract_assets.py
does not export sprite palettes; the round-trip harness saves them
from the original records.

Map JSON (extractor format): {"record", "rows", "cols", "entries":
[{"tile", "flipH", "flipV"}, ...]}. Chunk JSON uses the same schema
plus "palette" (0-3) and "priority" (bool) per entry — REQUIRED for
$43850 chunks, whose words use palette bits 13-14 (25,223 words) and
priority bit 15 (3,835 words); the $96120 maps never set bits 13-15,
so the plain extractor schema is lossless for them.

Compression is tools/dd5c.py (Okumura encoder, method="okumura") —
imported, never reimplemented. It is byte-identical on all 404 known
records, so any round-trip failure is in the import path, not the
compressor.

Usage:
  assets_import.py tileset <png> --palette N|--palette-json F [--cols 16 --scale 2 --gap 0]
  assets_import.py sprite <png> --palette-json F [--cols 6 --scale 1 --gap 0]
  assets_import.py map <json>            (writes tilemap words to stdout as hex, or --out)
  assets_import.py chunk <json>
  assets_import.py compress <in.bin> <out.dd5c> [--greedy]
"""
import argparse
import json
import struct
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
from dd5c import dd5c_compress  # noqa: E402  (Okumura encoder, #17)

from PIL import Image  # noqa: E402

ROM_PATH = _here.parent / "rop-original.gen"
PALETTE_TABLE = 0x0CC9D8
N_PALETTES = 31

# The 8 RGB values a CRAM channel (0-7) scales to via x*255//7.
_SCALED = tuple(c * 255 // 7 for c in range(8))
_UNSCALE = {v: c for c, v in enumerate(_SCALED)}


def cram_word_to_rgb(w):
    """CRAM word -> (R, G, B) 0-255. Corrected order (#016)."""
    r = (w >> 1) & 7
    g = (w >> 5) & 7
    b = (w >> 9) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def rgb_to_cram_word(rgb):
    """(R, G, B) -> CRAM word. Exact inverse of cram_word_to_rgb.

    Raises ValueError on any channel that is not one of the 8 scaled
    values (off-palette colour). Word layout 0BBB0GGG0RRR0.
    """
    try:
        r = _UNSCALE[rgb[0]]
        g = _UNSCALE[rgb[1]]
        b = _UNSCALE[rgb[2]]
    except KeyError as e:
        raise ValueError("RGB %r is not a CRAM colour (channel %s "
                         "not in %s)" % (rgb, e.args[0], _SCALED))
    return (b << 9) | (g << 5) | (r << 1)


def load_palette_words(rom, n):
    """Master palette n (0-30) as 16 CRAM words from the ROM table."""
    if n < 0 or n >= N_PALETTES:
        raise ValueError("palette %d out of range 0-%d"
                         % (n, N_PALETTES - 1))
    return struct.unpack_from(">16H", rom, PALETTE_TABLE + n * 32)


def palette_words_to_rgb(words):
    return [cram_word_to_rgb(w) for w in words]


def load_palette_json(path):
    """Palette JSON -> (words, rgb). Accepts {"palette_words": [16 ints]}
    or {"palette": [[r,g,b], ...]}. Returns (words tuple, rgb list)."""
    d = json.loads(Path(path).read_text())
    if "palette_words" in d:
        words = tuple(int(w) for w in d["palette_words"])
        if len(words) != 16:
            raise ValueError("%s: need 16 palette_words, got %d"
                             % (path, len(words)))
        return words, palette_words_to_rgb(words)
    if "palette" in d:
        rgb = [tuple(int(c) for c in t) for t in d["palette"]]
        if len(rgb) != 16:
            raise ValueError("%s: need 16 palette entries, got %d"
                             % (path, len(rgb)))
        return tuple(rgb_to_cram_word(t) for t in rgb), rgb
    raise ValueError("%s: need 'palette_words' or 'palette'" % path)


def build_reverse_palette(palette_rgb):
    """RGB -> palette index (lowest index wins on duplicates).

    Returns (revmap, ambiguous) where ambiguous is {rgb: [indices]}
    for every RGB value shared by more than one index.
    """
    rev = {}
    amb = {}
    for i, rgb in enumerate(palette_rgb):
        if rgb in rev:
            amb.setdefault(rgb, [rev[rgb]]).append(i)
        else:
            rev[rgb] = i
    return rev, amb


def png_to_tiles(path, palette_rgb, cols, scale, gap=0, ntiles=None):
    """PNG -> list of tiles, each a list of 64 palette indices.

    PNG geometry: a grid of 8x8-pixel tiles, each pixel scaled by
    `scale`, tiles laid out `cols` across with `gap` pixels between
    (and around) them — the render_tiles.render_tiles geometry.
    Indexed PNGs (mode 'P') give indices directly; RGB PNGs are
    mapped through the palette (see module docstring for the
    duplicate-RGB caveat). Every scale block must be uniform (all
    pixels in the block equal) or the PNG was interpolated/edited.
    `ntiles`: tiles to read — the grid may have padding slots past
    them (render_tiles fills them with its (32,32,40) background);
    padding slots are ignored but must be a single uniform colour,
    which catches a wrong `ntiles`.

    Returns (tiles, report) where report has keys: mode, ambiguous_px
    (RGB pixels whose colour maps to >1 index), ambiguous_rgb (the
    colours), ntiles.
    """
    im = Image.open(path)
    mode = im.mode
    if mode not in ("P", "RGB", "RGBA"):
        raise ValueError("%s: unsupported PNG mode %s" % (path, mode))
    if mode == "RGBA":
        im = im.convert("RGB")
        mode = "RGB"
    w, h = im.size
    cell = 8 * scale + gap
    ncols = (w - gap) // cell
    nrows = (h - gap) // cell
    if ncols != cols:
        raise ValueError("%s: width %d implies %d cols, expected %d "
                         "(scale %d gap %d)" % (path, w, ncols, cols,
                                                scale, gap))
    if (w - gap) % cell or (h - gap) % cell:
        raise ValueError("%s: size %dx%d is not a clean %d-col grid "
                         "(scale %d gap %d)" % (path, w, h, cols,
                                                scale, gap))
    grid_tiles = ncols * nrows
    if ntiles is None:
        ntiles = grid_tiles
    if ntiles > grid_tiles:
        raise ValueError("%s: asked for %d tiles but the grid holds %d"
                         % (path, ntiles, grid_tiles))
    px = im.load()
    rev, amb = build_reverse_palette(palette_rgb) if mode == "RGB" else ({}, {})
    amb_px = 0
    amb_seen = set()
    tiles = []
    for ti in range(grid_tiles):
        cx, cy = ti % ncols, ti // ncols
        ox = gap + cx * cell
        oy = gap + cy * cell
        if ti >= ntiles:
            # padding slot: must be one uniform colour (the render
            # background); anything else means ntiles is wrong.
            colours = set()
            for y in range(8 * scale):
                for x in range(8 * scale):
                    colours.add(px[ox + x, oy + y])
            if len(colours) != 1:
                raise ValueError(
                    "%s: padding slot %d is not uniform (%d colours) "
                    "— ntiles=%d is probably wrong"
                    % (path, ti, len(colours), ntiles))
            continue
        tile = []
        for y in range(8):
            for x in range(8):
                bx = ox + x * scale
                by = oy + y * scale
                v = px[bx, by]
                # scale block must be uniform
                for sy in range(scale):
                    for sx in range(scale):
                        if px[bx + sx, by + sy] != v:
                            raise ValueError(
                                "%s: tile %d pixel (%d,%d) is not a "
                                "uniform %dx%d block (interpolated or "
                                "edited PNG)" % (path, ti, x, y, scale, scale))
                if mode == "P":
                    if v > 15:
                        raise ValueError("%s: tile %d pixel (%d,%d) has "
                                         "palette index %d > 15"
                                         % (path, ti, x, y, v))
                    tile.append(v)
                else:
                    if v not in rev:
                        raise ValueError(
                            "%s: tile %d pixel (%d,%d) RGB %r is not in "
                            "the palette" % (path, ti, x, y, v))
                    if v in amb:
                        amb_px += 1
                        amb_seen.add(v)
                    tile.append(rev[v])
        tiles.append(tile)
    report = {"mode": mode, "ntiles": ntiles, "ambiguous_px": amb_px,
              "ambiguous_rgb": sorted(amb_seen)}
    return tiles, report


def pack_tiles(tiles):
    """List of 64-index tiles -> packed bytes (2 px/byte, hi first)."""
    out = bytearray()
    for t in tiles:
        if len(t) != 64:
            raise ValueError("tile has %d pixels, expected 64" % len(t))
        for i in range(0, 64, 2):
            out.append(((t[i] & 15) << 4) | (t[i + 1] & 15))
    return bytes(out)


def unpack_tiles(data):
    """Packed tile bytes -> list of 64-index tiles (inverse of pack)."""
    if len(data) % 32:
        raise ValueError("tile data %d bytes is not a multiple of 32"
                         % len(data))
    tiles = []
    for off in range(0, len(data), 32):
        tile = []
        for b in data[off:off + 32]:
            tile.append(b >> 4)
            tile.append(b & 15)
        tiles.append(tile)
    return tiles


def import_tileset(png_path, palette_rgb, cols=16, scale=2, gap=0,
                   ntiles=None):
    """Tileset PNG -> packed tile bytes. Returns (bytes, report)."""
    tiles, report = png_to_tiles(png_path, palette_rgb, cols, scale, gap,
                                ntiles)
    return pack_tiles(tiles), report


def import_sprite(png_path, palette_words, cols=6, scale=1, gap=0,
                  ntiles=36):
    """Sprite PNG + 16 CRAM words -> [32-byte palette][tile bytes].

    The palette words are stored big-endian, exactly as in the
    $B86AE record (first 32 bytes). Returns (bytes, report).
    """
    palette_rgb = palette_words_to_rgb(palette_words)
    tiles, report = png_to_tiles(png_path, palette_rgb, cols, scale, gap,
                                ntiles)
    out = bytearray(struct.pack(">16H", *palette_words))
    out += pack_tiles(tiles)
    return bytes(out), report


def map_entries_to_words(entries):
    """Map/chunk JSON entries -> big-endian u16 tilemap words.

    Each entry: {"tile", "flipH", "flipV"} plus optional "palette"
    (0-3) and "priority" (bool) — the $43850 chunk words use both;
    the $96120 maps never set them. Missing palette/priority default
    to 0/False.
    """
    words = []
    for e in entries:
        w = int(e["tile"]) & 0x07FF
        if e.get("flipH"):
            w |= 0x0800
        if e.get("flipV"):
            w |= 0x1000
        pal = int(e.get("palette", 0))
        if not 0 <= pal <= 3:
            raise ValueError("palette %r out of range 0-3" % pal)
        w |= pal << 13
        if e.get("priority"):
            w |= 0x8000
        words.append(w)
    return struct.pack(">%dH" % len(words), *words)


def import_map_json(path):
    """Map/chunk JSON (extractor schema) -> tilemap words (bytes)."""
    d = json.loads(Path(path).read_text())
    return map_entries_to_words(d["entries"])


def compress_record(data, method="okumura"):
    """Compress decompressed record bytes with the $DD5C compressor."""
    return dd5c_compress(data, method=method)


def _load_rom(path):
    return Path(path).read_bytes()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=str(ROM_PATH))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tileset", help="PNG + palette -> packed tiles")
    p.add_argument("png")
    p.add_argument("--palette", type=int, default=1,
                   help="master palette table index (default 1)")
    p.add_argument("--palette-json", default=None)
    p.add_argument("--cols", type=int, default=16)
    p.add_argument("--scale", type=int, default=2)
    p.add_argument("--gap", type=int, default=0)
    p.add_argument("--tiles", type=int, default=None,
                   help="tiles to read (default: whole grid; needed "
                        "when the last row has background padding)")
    p.add_argument("--out", default=None)
    p.add_argument("--compress", action="store_true",
                   help="also emit the $DD5C-compressed record")

    p = sub.add_parser("sprite", help="PNG + palette words -> sprite record")
    p.add_argument("png")
    p.add_argument("--palette-json", required=True,
                   help='JSON with "palette_words" (16 CRAM words)')
    p.add_argument("--cols", type=int, default=6)
    p.add_argument("--scale", type=int, default=1)
    p.add_argument("--gap", type=int, default=0)
    p.add_argument("--out", default=None)
    p.add_argument("--compress", action="store_true")

    p = sub.add_parser("map", help="map JSON -> tilemap words")
    p.add_argument("json")
    p.add_argument("--out", default=None)
    p.add_argument("--compress", action="store_true")

    p = sub.add_parser("chunk", help="chunk JSON -> tilemap words")
    p.add_argument("json")
    p.add_argument("--out", default=None)
    p.add_argument("--compress", action="store_true")

    p = sub.add_parser("compress", help="compress raw record bytes")
    p.add_argument("inp")
    p.add_argument("outp")
    p.add_argument("--greedy", action="store_true")

    args = ap.parse_args(argv)
    rom = _load_rom(args.rom) if args.cmd in ("tileset",) else None

    if args.cmd == "tileset":
        if args.palette_json:
            _w, pal_rgb = load_palette_json(args.palette_json)
        else:
            pal_rgb = palette_words_to_rgb(load_palette_words(rom, args.palette))
        data, rep = import_tileset(args.png, pal_rgb, args.cols,
                                   args.scale, args.gap, args.tiles)
        print("tileset %s: %d tiles, %d bytes, mode %s"
              % (args.png, rep["ntiles"], len(data), rep["mode"]))
        if rep["ambiguous_px"]:
            print("WARNING: %d pixels ambiguous (RGB %s maps to >1 "
                  "index; resolved to lowest)"
                  % (rep["ambiguous_px"], rep["ambiguous_rgb"]))
    elif args.cmd == "sprite":
        words, _rgb = load_palette_json(args.palette_json)
        data, rep = import_sprite(args.png, words, args.cols,
                                  args.scale, args.gap)
        print("sprite %s: %d tiles, %d bytes, mode %s"
              % (args.png, rep["ntiles"], len(data), rep["mode"]))
        if rep["ambiguous_px"]:
            print("WARNING: %d pixels ambiguous (RGB %s maps to >1 "
                  "index; resolved to lowest)"
                  % (rep["ambiguous_px"], rep["ambiguous_rgb"]))
    elif args.cmd in ("map", "chunk"):
        data = import_map_json(args.json)
        print("%s %s: %d words, %d bytes"
              % (args.cmd, args.json, len(data) // 2, len(data)))
    elif args.cmd == "compress":
        data = Path(args.inp).read_bytes()
        out = dd5c_compress(data, method="greedy" if args.greedy else "okumura")
        Path(args.outp).write_bytes(out)
        print("compressed %d -> %d bytes" % (len(data), len(out)))
        return 0

    if getattr(args, "out", None):
        Path(args.out).write_bytes(data)
        print("wrote", args.out)
    if getattr(args, "compress", False):
        out = dd5c_compress(data)
        cpath = (args.out + ".dd5c") if getattr(args, "out", None) else None
        if cpath:
            Path(cpath).write_bytes(out)
            print("compressed -> %s (%d bytes)" % (cpath, len(out)))
        else:
            print("compressed %d -> %d bytes (no --out, not saved)"
                  % (len(data), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
