#!/usr/bin/env python3
"""lzss_roundtrip.py — $DD5C LZSS round-trip over every known record (issue #285, M10).

Decode each $DD5C record from rop-original.gen with the canonical
decompressor, re-compress it with the Okumura encoder (tools/dd5c.py),
and require the re-compressed bytes to be byte-identical to the
original stream — then decode the re-compressed bytes again and
require the decompressed bytes back. This is the `lzss` class of
`make roundtrip` (tools/roundtrip.py).

Record tables (10-byte entries: u32 offset, u32 decompressed length,
u16 type=1; offsets relative to the data base; compressed length is
implicit from the next record's offset):

  $96120  62 records, data base 0x09638C, data ends 0x0B86AE
  $B86AE  90 records, data base 0x0B8A32, data ends 0x0CC9D8
  $43850 252 records, data base 0x044228, data ends 0x05EDC4

The table spec is the same one tools/tests/test_dd5c.py uses; the
decode/compress work is imported, never reimplemented. Read only
with respect to the ROM; writes nothing.

Usage: python3 tools/lzss_roundtrip.py [--rom PATH]
Exit 0 only when all 404 records re-compress byte-identical.
"""
import argparse
import struct
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
from dd5c import dd5c_compress, dd5c_decompress  # noqa: E402

# table -> (table addr, n_records, data base, data end exclusive)
TABLES = {
    "96120": (0x096120, 62, 0x09638C, 0x0B86AE),
    "b86ae": (0x0B86AE, 90, 0x0B8A32, 0x0CC9D8),
    "43850": (0x043850, 252, 0x044228, 0x05EDC4),
}
EXPECTED_RECORDS = 404


def check(rom_path=None):
    """Round-trip every $DD5C record. Returns a summary string.

    Raises AssertionError on the first failure (with the record id).
    """
    rom = Path(rom_path or "rop-original.gen").read_bytes()
    total = identical = roundtripped = 0
    per_table = {}
    for name, (taddr, n, base, dend) in TABLES.items():
        ptrs = [struct.unpack_from(">IIH", rom, taddr + i * 10)
                for i in range(n)]
        ok_t = 0
        for i, (ptr, declen, typ) in enumerate(ptrs):
            rid = f"{name}_{i:03d}"
            assert typ == 1, f"{rid}: type {typ}, not $DD5C"
            start = base + ptr
            comp_len = ((ptrs[i + 1][0] if i + 1 < n else dend - base)
                        - ptr)
            comp = bytes(rom[start:start + comp_len])
            res = dd5c_decompress(rom, start)
            assert res is not None, f"{rid}: dd5c_decompress returned None"
            decomp, consumed = res
            assert len(decomp) == declen, (
                f"{rid}: decomp len {len(decomp)} != table declen {declen}")
            assert consumed == comp_len, (
                f"{rid}: consumed {consumed} != implicit comp_len {comp_len}")
            got = dd5c_compress(decomp)  # default: Okumura encoder
            assert got == comp, (
                f"{rid}: re-compressed {len(got)} bytes != original "
                f"{len(comp)} bytes")
            res2 = dd5c_decompress(got, 0, max_out=len(decomp))
            assert res2 is not None and res2[0] == decomp, (
                f"{rid}: re-compressed bytes do not decode back")
            total += 1
            identical += 1
            roundtripped += 1
            ok_t += 1
        per_table[name] = (ok_t, n)
    assert total == EXPECTED_RECORDS, (
        f"expected {EXPECTED_RECORDS} records, got {total}")
    detail = ", ".join(f"${k} {v}/{n}" for k, (v, n) in per_table.items())
    return (f"{identical}/{total} $DD5C records decode + re-compress "
            f"byte-identical ({detail}), {roundtripped}/{total} decode back")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default="rop-original.gen")
    args = ap.parse_args(argv)
    try:
        summary = check(args.rom)
    except (AssertionError, FileNotFoundError) as e:
        print(f"lzss: FAIL {e}", file=sys.stderr)
        return 1
    print(f"lzss: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
