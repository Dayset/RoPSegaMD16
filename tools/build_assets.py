#!/usr/bin/env python3
"""Build the $DD5C asset records from assets/gfx/ sources (issue #19).

`make assets` runs this script. For every record in
assets/gfx/manifest.json it:

  1. imports the source (indexed PNG + palette JSON, or map/chunk
     JSON) via tools/assets_import.py — the importer is imported,
     never reimplemented;
  2. compresses the raw record bytes with tools/dd5c.py (Okumura
     encoder, #17) — the compressor is imported, never reimplemented;
  3. compares the compressed bytes against the original record in
     rop-original.gen (byte-identical check);
  4. splices the compressed record into a copy of the ROM at its
     table offset (data base + per-record offset).

Output:
  build/assets.gen — the ROM with the rebuilt records spliced in.
    Byte-identical to rop-original.gen when every record round-trips
    (the proof). Verified with cmp before the script exits 0. If any
    record differs, the script exits 1 and does NOT write build/
    assets.gen (and removes a stale one) — a partial rebuild must not
    look like a success.
  build/assets/*.dd5c — the per-record compressed bytes (inspection;
    written for the records that round-tripped, even on failure).

Splice rule: a rebuilt record must be exactly the same compressed
length as the original (it is, when byte-identical). If a record's
compressed length ever differs — e.g. an edited asset that compresses
longer — the script FAILS with the record id and both lengths instead
of silently overwriting the next record. Growing a record past its
original size needs M9 (#16, shiftable build); until then the asset
pipeline rebuilds byte-identically (or smaller, which still splices
cleanly only if the table offsets are rebuilt — not attempted here).

The 4 $96120 text records (32, 55, 59, 61) are NOT assets: they are
#18's text pipeline and are copied through untouched from the ROM.

Usage:
  python3 tools/build_assets.py [--rom PATH] [--gfx DIR] [--out FILE]
      [--no-verify] [--keep] [--quiet]
  --rom:    original ROM to compare against (default rop-original.gen)
  --gfx:    asset sources dir (default assets/gfx)
  --out:    output ROM path (default build/assets.gen)
  --no-verify: skip the final whole-ROM byte-compare (still reports
      per-record rates; exit 0 requires all records byte-identical)
  --quiet:  only the summary lines
Exit 0 only when every record is byte-identical AND (unless
--no-verify) the output ROM is byte-identical to the original.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
from assets_import import (  # noqa: E402
    import_tileset, import_sprite, import_map_json,
    load_palette_json, palette_words_to_rgb)
from dd5c import dd5c_compress  # noqa: E402  (Okumura encoder, #17)
from extract_text import dd5c_decompress  # noqa: E402

ROOT = _here.parent
ROM_DEFAULT = ROOT / "rop-original.gen"
GFX_DEFAULT = ROOT / "assets" / "gfx"
OUT_DEFAULT = ROOT / "build" / "assets.gen"

TABLES = {
    "96120": (0x96120, 0x9638C, 62),
    "B86AE": (0xB86AE, 0xB8A32, 90),
    "43850": (0x43850, 0x44228, 252),
}


def read_table(rom, table, base, n):
    """Return {index: (off, declen, used)} for a $DD5C table.

    `used` is the consumed compressed length, from the decompressor
    (== next record's offset - this offset; the #17 corpus verified
    consumed == implicit length on all 404 records).
    """
    out = {}
    for i in range(n):
        off, ln, typ = struct.unpack_from(">IIH", rom, table + i * 10)
        assert typ == 1, "table 0x%X rec %d type %d" % (table, i, typ)
        _data, used = dd5c_decompress(rom, base + off, max_out=200000)
        out[i] = (off, ln, used)
    return out


def import_record(gfx, rec):
    """Manifest record -> raw (decompressed) record bytes."""
    kind = rec["kind"]
    src = gfx / rec["src"]
    if kind == "tileset":
        _w, pal_rgb = load_palette_json(gfx / rec["palette"])
        data, rep = import_tileset(src, pal_rgb, rec["cols"],
                                   rec["scale"], rec["gap"], rec["tiles"])
        if rep["ambiguous_px"]:
            print("WARNING %s: %d ambiguous RGB pixels"
                  % (src, rep["ambiguous_px"]), file=sys.stderr)
        return data
    if kind == "sprite":
        words, _rgb = load_palette_json(gfx / rec["palette"])
        data, rep = import_sprite(src, words, rec["cols"],
                                  rec["scale"], rec["gap"], rec["tiles"])
        if rep["ambiguous_px"]:
            print("WARNING %s: %d ambiguous RGB pixels"
                  % (src, rep["ambiguous_px"]), file=sys.stderr)
        return data
    if kind in ("map", "chunk"):
        return import_map_json(src)
    raise ValueError("unknown kind %r" % kind)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=str(ROM_DEFAULT))
    ap.add_argument("--gfx", default=str(GFX_DEFAULT))
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    rom_path = Path(args.rom)
    gfx = Path(args.gfx)
    out_path = Path(args.out)
    if not rom_path.exists():
        print("error: ROM not found: %s" % rom_path, file=sys.stderr)
        return 2
    manifest_path = gfx / "manifest.json"
    if not manifest_path.exists():
        print("error: asset sources not found: %s\n"
              "generate them first (see assets/gfx/README.md)"
              % manifest_path, file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text())
    rom = rom_path.read_bytes()

    tables = {name: read_table(rom, *spec)
              for name, spec in TABLES.items()}

    out_rom = bytearray(rom)
    results = {}   # (table, kind) -> [ok, total]
    failures = []
    per_record = {}
    for rec in manifest["records"]:
        table = rec["table"]
        idx = rec["index"]
        kind = rec["kind"]
        off, declen, used = tables[table][idx]
        orig = bytes(rom[TABLES[table][1] + off:
                         TABLES[table][1] + off + used])
        try:
            raw = import_record(gfx, rec)
        except Exception as e:  # noqa: BLE001 — report and continue
            failures.append((table, idx, kind, "import: %s" % e))
            results.setdefault((table, kind), [0, 0])
            results[(table, kind)][1] += 1
            continue
        if len(raw) != declen:
            failures.append((table, idx, kind,
                             "raw len %d != table declen %d"
                             % (len(raw), declen)))
            results.setdefault((table, kind), [0, 0])
            results[(table, kind)][1] += 1
            continue
        comp = dd5c_compress(raw)
        ok = comp == orig
        key = (table, kind)
        results.setdefault(key, [0, 0])
        results[key][1] += 1
        if ok:
            results[key][0] += 1
        else:
            failures.append((table, idx, kind,
                             "compressed %d bytes != original %d bytes"
                             % (len(comp), len(orig))))
            continue
        # comp == orig implies len(comp) == used (orig was sliced to
        # `used` bytes), so the splice below cannot overwrite the
        # next record.
        base = TABLES[table][1]
        out_rom[base + off: base + off + used] = comp
        per_record[(table, idx)] = comp

    # write the per-record files (successful records only). Clear the
    # dir first so a failed record's stale file from an earlier run
    # cannot masquerade as a fresh one.
    import shutil
    rec_dir = out_path.parent / "assets"
    if rec_dir.exists():
        shutil.rmtree(rec_dir)
    rec_dir.mkdir(parents=True, exist_ok=True)
    for (table, idx), comp in per_record.items():
        (rec_dir / ("%s_rec%03d.dd5c" % (table, idx))).write_bytes(comp)

    # report
    total_ok = total = 0
    for (table, kind), (ok, n) in sorted(results.items()):
        total_ok += ok
        total += n
        if not args.quiet:
            print("  $%s %-8s %d/%d byte-identical" % (table, kind, ok, n))
    for table, idx, kind, why in failures:
        print("FAIL $%s rec %d (%s): %s" % (table, idx, kind, why),
              file=sys.stderr)
    if not args.quiet:
        print("records: %d/%d byte-identical" % (total_ok, total))
    if total_ok != total:
        # Failed records were NOT spliced in, so do not write an
        # output ROM: a partial rebuild that silently matches the
        # original would look like a success. Remove any stale output
        # from an earlier run, too. The per-record .dd5c files above
        # are still there for inspection.
        if out_path.exists():
            out_path.unlink()
        print("error: %d record(s) differ; %s NOT written"
              % (total - total_ok, out_path), file=sys.stderr)
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(out_rom))
    rom_ok = bytes(out_rom) == rom
    if not args.quiet:
        print("output ROM %s: %d bytes, %s"
              % (out_path, len(out_rom),
                 "byte-identical to the original"
                 if rom_ok else "DIFFERS from the original"))
    if not args.no_verify and not rom_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
