#!/usr/bin/env python3
"""asset_roundtrip.py — asset extract -> re-pack round-trip (issue #285, M10).

Export all 400 asset records from rop-original.gen into a fresh
scratch directory with tools/export_assets.py, then rebuild them
into a ROM with tools/build_assets.py from that scratch export, and
require the rebuilt ROM to be byte-identical to the original. This
is the `assets` class of `make roundtrip` (tools/roundtrip.py).

Both halves are imported, never reimplemented: the export side is
export_assets.export_all, the re-pack side is build_assets.main
(import + Okumura compress + splice). The scratch directory lives
in a tempfile and is deleted afterwards, so no extracted assets are
left in the repo — the committed assets/gfx/ sources are not read
or written by this check at all (the export is proven against the
ROM itself, not against the committed copy).

Record counts (export_assets.TABLES): $96120 62 (37 tilesets + 21
maps + 4 text records, which the exporter skips), $B86AE 90
sprites, $43850 252 map chunks = 400 records.

Usage: python3 tools/asset_roundtrip.py [--rom PATH]
Exit 0 only when the export yields 400 records and the rebuilt ROM
is byte-identical to the original.
"""
import argparse
import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
from export_assets import TEXT_RECORDS, export_all  # noqa: E402
import build_assets  # noqa: E402

EXPECTED_RECORDS = 400
EXPECTED_KINDS = {"tileset": 37, "map": 21, "sprite": 90, "chunk": 252}


def check(rom_path=None):
    """Export to scratch, rebuild from the scratch export, compare.

    Returns a summary string. Raises AssertionError / RuntimeError
    on the first failure. The scratch dir is always deleted.
    """
    rom_path = Path(rom_path or "rop-original.gen")
    rom = rom_path.read_bytes()
    with tempfile.TemporaryDirectory(prefix="asset_roundtrip_") as tmp:
        tmp = Path(tmp)
        summary = export_all(rom_path, tmp)
        assert summary["records"] == EXPECTED_RECORDS, (
            f"exported {summary['records']} records, "
            f"expected {EXPECTED_RECORDS}")
        assert summary["kinds"] == EXPECTED_KINDS, (
            f"kind counts {summary['kinds']} != {EXPECTED_KINDS}")
        assert summary["skipped_text"] == sorted(TEXT_RECORDS), (
            f"skipped records {summary['skipped_text']} != text records "
            f"{sorted(TEXT_RECORDS)}")
        out_path = tmp / "assets.gen"
        rc = build_assets.main([
            "--rom", str(rom_path),
            "--gfx", str(tmp),
            "--out", str(out_path),
            "--quiet",
        ])
        assert rc == 0, f"build_assets failed with exit {rc}"
        rebuilt = out_path.read_bytes()
        assert rebuilt == rom, (
            "rebuilt ROM differs from the original "
            f"({len(rebuilt)} bytes vs {len(rom)})")
    kinds = ", ".join(f"{v} {k}" for k, v in
                      sorted(EXPECTED_KINDS.items(), key=lambda kv: -kv[1]))
    return (f"{EXPECTED_RECORDS}/{EXPECTED_RECORDS} records export + "
            f"rebuild byte-identical ({kinds})")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default="rop-original.gen")
    args = ap.parse_args(argv)
    try:
        summary = check(args.rom)
    except (AssertionError, RuntimeError, FileNotFoundError,
            ValueError) as e:
        print(f"assets: FAIL {e}", file=sys.stderr)
        return 1
    print(f"assets: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
