#!/usr/bin/env python3
"""Tests for the $DD5C LZSS compressor (tools/dd5c.py, issue #17).

The main test derives all 404 known $DD5C records from the ROM itself —
no fixtures, no scratch files. Record tables (10-byte entries: u32 ptr,
u32 decompressed length, u16 type; type 1 = $DD5C; compressed length is
implicit from the next record's pointer):

  $96120  62 records, data $09638C-0x0B86AE (tilemaps + tilesets)
  $B86AE  90 records, data $0B8A32-0x0CC9D8 (sprite-pattern sets, 1184 B each)
  $43850 252 records, data $044228-0x05EDC4 (map chunks: 99 x 2048 B + 153 x 242 B)

See docs/graphics.md ($96120, $B86AE), docs/maps.md ($43850) and
disasm/regions.csv. The ROM (rop-original.gen, never committed) is found
in the repo root or via $ROP_ROM; the tests skip gracefully if it is absent.

pytest-style (test_* functions, plain asserts). pytest is not installed in
this repo, so the file also runs standalone:
  python3 tools/tests/test_dd5c.py
"""
import os
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dd5c import dd5c_compress, dd5c_decompress  # noqa: E402

# table: (record-table addr, n_records, data base, data end exclusive)
TABLES = {
    "96120": (0x096120, 62, 0x09638C, 0x0B86AE),
    "b86ae": (0x0B86AE, 90, 0x0B8A32, 0x0CC9D8),
    "chunk": (0x043850, 252, 0x044228, 0x05EDC4),
}
EXPECTED_RECORDS = 404


def find_rom():
    """Locate rop-original.gen (repo root, $ROP_ROM, or cwd)."""
    cands = []
    if os.environ.get("ROP_ROM"):
        cands.append(Path(os.environ["ROP_ROM"]))
    # repo root = parent of tools/
    cands.append(Path(__file__).resolve().parent.parent.parent
                 / "rop-original.gen")
    cands.append(Path.cwd() / "rop-original.gen")
    for c in cands:
        if c.is_file():
            return c
    return None


def iter_records(rom):
    """Yield (id, table, index, original_comp_bytes, decompressed_bytes).

    Derives every record from the ROM + the tables above. Raises
    AssertionError if a record fails to decompress, if the decompressed
    length disagrees with the table, or if the decompressor's consumed
    byte count disagrees with the implicit compressed length.
    """
    for table, (taddr, n, base, dend) in TABLES.items():
        ptrs = [struct.unpack_from(">IIH", rom, taddr + i * 10)
                for i in range(n)]
        for i, (ptr, declen, typ) in enumerate(ptrs):
            rid = f"{table}_{i:03d}"
            assert typ == 1, f"{rid}: type {typ}, not $DD5C"
            rom_start = base + ptr
            comp_len = ((ptrs[i + 1][0] if i + 1 < n else dend - base)
                        - ptr)
            comp = bytes(rom[rom_start:rom_start + comp_len])
            res = dd5c_decompress(rom, rom_start)
            assert res is not None, f"{rid}: dd5c_decompress returned None"
            decomp, consumed = res
            assert len(decomp) == declen, \
                f"{rid}: decomp len {len(decomp)} != table declen {declen}"
            assert consumed == comp_len, \
                f"{rid}: consumed {consumed} != implicit comp_len {comp_len}"
            yield rid, table, i, comp, decomp


def test_all_records_byte_identical():
    """#17 acceptance: compress(decompressed) == original bytes, all 404."""
    rom_path = find_rom()
    if rom_path is None:
        try:
            import pytest
            pytest.skip("rop-original.gen not found "
                        "(repo root or $ROP_ROM)")
        except ImportError:
            print("SKIP test_all_records_byte_identical: "
                  "rop-original.gen not found")
            return
    rom = rom_path.read_bytes()
    t0 = time.time()
    total = identical = roundtripped = 0
    failures = []
    for rid, table, i, comp, decomp in iter_records(rom):
        total += 1
        got = dd5c_compress(decomp)  # default: Okumura encoder
        if got == comp:
            identical += 1
        else:
            failures.append(rid)
        res = dd5c_decompress(got, 0, max_out=len(decomp))
        assert res is not None, f"{rid}: our output rejected by decompressor"
        assert res[0] == decomp, f"{rid}: round-trip mismatch"
        roundtripped += 1
    dt = time.time() - t0
    print(f"test_all_records_byte_identical: {identical}/{total} "
          f"byte-identical, {roundtripped}/{total} round-tripped "
          f"in {dt:.1f}s")
    assert total == EXPECTED_RECORDS, \
        f"expected {EXPECTED_RECORDS} records, got {total}"
    assert not failures, f"not byte-identical: {failures[:10]}"
    assert identical == total
    assert roundtripped == total


def test_greedy_roundtrip():
    """The greedy fallback must round-trip, even where it is not identical."""
    rom_path = find_rom()
    if rom_path is None:
        try:
            import pytest
            pytest.skip("rop-original.gen not found")
        except ImportError:
            print("SKIP test_greedy_roundtrip: rop-original.gen not found")
            return
    rom = rom_path.read_bytes()
    checked = 0
    for rid, table, i, comp, decomp in iter_records(rom):
        if table != "b86ae":
            continue
        got = dd5c_compress(decomp, method="greedy")
        res = dd5c_decompress(got, 0, max_out=len(decomp))
        assert res is not None and res[0] == decomp, \
            f"{rid}: greedy round-trip failed"
        checked += 1
    print(f"test_greedy_roundtrip: {checked}/90 $B86AE records round-tripped")
    assert checked == 90


def test_compress_rejects_short_input():
    """The format's length prefix requires n >= 16."""
    for bad in (b"", b"x", b"x" * 15):
        try:
            dd5c_compress(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"dd5c_compress({len(bad)} bytes) "
                                 "should raise ValueError")
    # 16 bytes is the smallest valid input.
    out = dd5c_compress(b"x" * 16)
    res = dd5c_decompress(out, 0, max_out=16)
    assert res is not None and res[0] == b"x" * 16


def test_bad_method_rejected():
    try:
        dd5c_compress(b"x" * 16, method="bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("dd5c_compress(method='bogus') "
                             "should raise ValueError")


def main():
    tests = [test_all_records_byte_identical, test_greedy_roundtrip,
             test_compress_rejects_short_input, test_bad_method_rejected]
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
