#!/usr/bin/env python3
"""Tests for the asset exporter (tools/export_assets.py, issue #19).

The main test regenerates all 400 asset records from the ROM itself
— no fixtures — and asserts the output matches the committed
`assets/gfx/` byte-for-byte (every PNG and JSON; README.md is
hand-written documentation, not a generated file, and is excluded).
That is the proof the committed sources are regenerable: the exporter
is the canonical regeneration path the README promises.

Record tables (10-byte entries: u32 offset, u32 decompressed length,
u16 type=1; offsets relative to the data base):

  $96120  62 records, data base 0x09638C (37 tilesets + 21 tilemaps
          + 4 text records, which the exporter skips)
  $B86AE  90 records, data base 0x0B8A32 (sprites)
  $43850 252 records, data base 0x044228 (map chunks)

The ROM (rop-original.gen, never committed) is found in the repo root
or via $ROP_ROM; the tests skip gracefully if it is absent.

pytest-style (test_* functions, plain asserts). pytest is not
installed in this repo, so the file also runs standalone:
  python3 tools/tests/test_export_assets.py
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export_assets import (  # noqa: E402
    TABLES, TEXT_RECORDS, compare_dirs, export_all,
    tileset_palette_index)
from decode_map import KNOWN  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GFX_COMMITTED = REPO_ROOT / "assets" / "gfx"


def find_rom():
    """Locate rop-original.gen (repo root, $ROP_ROM, or cwd)."""
    cands = []
    if os.environ.get("ROP_ROM"):
        cands.append(Path(os.environ["ROP_ROM"]))
    cands.append(REPO_ROOT / "rop-original.gen")
    cands.append(Path.cwd() / "rop-original.gen")
    for c in cands:
        if c.is_file():
            return c
    return None


def _skip_if_no_rom():
    rom = find_rom()
    if rom is None:
        print("SKIP: rop-original.gen not found "
              "(repo root or $ROP_ROM)")
        return None
    return rom


def _export_to_temp(rom):
    """Export all records into a fresh temp dir; returns (dir, summary)."""
    tmp = Path(tempfile.mkdtemp(prefix="export_assets_test_"))
    try:
        summary = export_all(rom, tmp)
        return tmp, summary
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def test_regeneration_matches_committed():
    """Regeneration is byte-identical to committed assets/gfx/."""
    rom = _skip_if_no_rom()
    if rom is None:
        return
    if not GFX_COMMITTED.is_dir():
        raise AssertionError("committed assets/gfx/ not found: %s"
                             % GFX_COMMITTED)
    tmp, _summary = _export_to_temp(rom)
    try:
        differing, missing, extra = compare_dirs(tmp, GFX_COMMITTED)
        assert not differing, (
            "regenerated files differ from committed: %s" % differing[:10])
        assert not missing, (
            "regenerated output is missing files: %s" % missing[:10])
        assert not extra, (
            "regenerated output has extra files: %s" % extra[:10])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_record_counts():
    """400 records: 37 tilesets, 21 maps, 90 sprites, 252 chunks;
    exactly the 4 text records skipped."""
    rom = _skip_if_no_rom()
    if rom is None:
        return
    tmp, summary = _export_to_temp(rom)
    try:
        assert summary["records"] == 400, (
            "expected 400 records, got %d" % summary["records"])
        assert summary["kinds"] == {"tileset": 37, "map": 21,
                                    "sprite": 90, "chunk": 252}, (
            "kind counts differ: %r" % summary["kinds"])
        assert summary["skipped_text"] == sorted(TEXT_RECORDS), (
            "skipped records %r != text records %r"
            % (summary["skipped_text"], sorted(TEXT_RECORDS)))
        assert set(summary["skipped_text"]) == {32, 55, 59, 61}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_manifest_matches_committed():
    """The exported manifest.json is byte-identical to the committed one."""
    rom = _skip_if_no_rom()
    if rom is None:
        return
    tmp, _summary = _export_to_temp(rom)
    try:
        got = (tmp / "manifest.json").read_bytes()
        want = (GFX_COMMITTED / "manifest.json").read_bytes()
        assert got == want, (
            "manifest.json differs (%d bytes vs %d committed)"
            % (len(got), len(want)))
        m = json.loads(got)
        assert m["tables"] == {
            name: {"table_addr": spec[0], "data_base": spec[1],
                   "count": spec[2]}
            for name, spec in TABLES.items()}, "manifest tables differ"
        assert len(m["records"]) == 400
        assert [r["index"] for r in m["records"]
                if r["table"] == "96120" and r["kind"] == "map"] == sorted(
                    KNOWN), "manifest map indices != KNOWN"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_tileset_palette_index():
    """palette_index = first KNOWN map using the tileset, else 1."""
    # (tileset rec, expected palette_index) — from decode_map.KNOWN.
    cases = {6: 11, 21: 15, 34: 30, 53: 17, 56: 27,
             0: 1, 12: 1, 37: 1, 42: 1}
    for rec, want in cases.items():
        got = tileset_palette_index(rec)
        assert got == want, (
            "tileset rec %d: palette_index %d != %d" % (rec, got, want))
    # every tileset in the committed manifest agrees, and its
    # palette_words are the master palette at that index.
    rom = _skip_if_no_rom()
    if rom is None:
        return
    import struct
    rom_bytes = Path(rom).read_bytes()
    manifest = json.loads((GFX_COMMITTED / "manifest.json").read_text())
    for rec in manifest["records"]:
        if rec["kind"] != "tileset":
            continue
        idx = rec["index"]
        pal = json.loads((GFX_COMMITTED / rec["palette"]).read_text())
        assert pal["palette_index"] == tileset_palette_index(idx), (
            "tileset rec %d: committed palette_index %d != derived %d"
            % (idx, pal["palette_index"], tileset_palette_index(idx)))
        words = struct.unpack_from(">16H", rom_bytes,
                                   0x0CC9D8 + pal["palette_index"] * 32)
        assert tuple(pal["palette_words"]) == words, (
            "tileset rec %d: palette_words != master palette %d"
            % (idx, pal["palette_index"]))


def test_chunk_entry_keys():
    """Chunk entries carry palette/priority keys exactly when the
    word sets bits 13-15 (both keys together, never independently)."""
    if not GFX_COMMITTED.is_dir():
        raise AssertionError("committed assets/gfx/ not found: %s"
                             % GFX_COMMITTED)
    with_keys = 0
    total = 0
    for path in sorted((GFX_COMMITTED / "chunks").glob("*.json")):
        d = json.loads(path.read_text())
        for e in d["entries"]:
            total += 1
            has = ("palette" in e, "priority" in e)
            assert has in ((False, False), (True, True)), (
                "%s: entry %r has palette/priority keys independently"
                % (path.name, e))
            if has[0]:
                with_keys += 1
                assert 0 <= e["palette"] <= 3
                assert isinstance(e["priority"], bool)
    assert total == 119889, "chunk entries total %d != 119889" % total
    assert with_keys == 27359, (
        "chunk entries with palette/priority keys %d != 27359" % with_keys)


def main():
    tests = [test_regeneration_matches_committed,
             test_record_counts,
             test_manifest_matches_committed,
             test_tileset_palette_index,
             test_chunk_entry_keys]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
