#!/usr/bin/env python3
"""Byte-identical rebuild gate (issue #013).

Usage: python3 tools/verify_rebuild.py <rebuilt.gen> <original.gen>

Exit 0 iff the two 1 MB images are identical everywhere EXCEPT the
two checksum fields that tools/checksum.py fix-all rewrites:
  - header checksum word at 0x18E (2 bytes)
  - runtime checksum immediate longword at 0xFD098 (4 bytes)
    (docs/toolchain.md, disasm/map.md: runtime sum at 0xFD07C
     compares against the immediate at 0xFD098, expected 0x8F33608C)
On mismatch: prints the FIRST differing address (and total count)
and exits 1 — that is the #013 acceptance behaviour.
Pure stdlib; works without the ROM present in CI by unit-testing
the comparison function (see --selftest).
"""
import sys

ROM_SIZE = 1_048_576
EXEMPT = [(0x18E, 0x190), (0xFD098, 0xFD09C)]  # [start, end)


def first_diff(a: bytes, b: bytes):
    """Return (first_addr, total_diffs) ignoring EXEMPT ranges, or None."""
    if len(a) != ROM_SIZE or len(b) != ROM_SIZE:
        raise ValueError(f"both images must be {ROM_SIZE} bytes "
                         f"(got {len(a)} and {len(b)})")
    exempt = bytearray(ROM_SIZE)
    for s, e in EXEMPT:
        exempt[s:e] = b"\x01" * (e - s)
    first, total = None, 0
    for i in range(ROM_SIZE):
        if a[i] != b[i] and not exempt[i]:
            total += 1
            if first is None:
                first = i
    return None if total == 0 else (first, total)


def main(argv):
    if argv[1:] == ["--selftest"]:
        base = bytearray(ROM_SIZE)
        same = bytes(base)
        assert first_diff(bytes(base), same) is None
        base[0x18E] ^= 0xFF; base[0xFD098] ^= 0xFF
        assert first_diff(bytes(base), same) is None, "exempt fields must pass"
        base[0x500] ^= 0xFF
        got = first_diff(bytes(base), same)
        assert got == (0x500, 1), got
        print("verify_rebuild selftest: PASS")
        return 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    with open(argv[1], "rb") as f:
        rebuilt = f.read()
    with open(argv[2], "rb") as f:
        original = f.read()
    try:
        diff = first_diff(rebuilt, original)
    except ValueError as exc:
        print(f"verify_rebuild: FAIL — {exc}")
        return 1
    if diff is None:
        print("verify_rebuild: PASS — identical except checksum fields; "
              "run tools/checksum.py fix-all to make it fully identical")
        return 0
    first, total = diff
    print(f"verify_rebuild: FAIL — first differing address 0x{first:06X} "
          f"(rebuilt 0x{rebuilt[first]:02X} != original 0x{original[first]:02X}); "
          f"{total} differing byte(s) outside the checksum fields")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
