#!/usr/bin/env python3
"""Grow a text record and splice the grown text region into a new ROM
(#18 acceptance (2): "Longer text allowed once M9 lands (records can grow)").

Usage:
    python3 tools/text_grow.py [--rom PATH] [--text-dir DIR]
                               [--out ROM] [--table BIN] [--arrays BIN]

Defaults: --rom rop-original.gen, --text-dir assets/text,
          --out rop-grown.gen, --table build/grown_table.bin,
          --arrays build/grown_arrays.bin.

The record table stores byte lengths and the arrays are packed
contiguously, so growing a record shifts every following array and
updates all subsequent ptrs (rebuild_records derives ptrs from the
packed layout). The dictionary blob and offset table are unchanged
(the grown record uses words already in the dictionary).

New ROM layout (G = growth in bytes, here from rec 0):
    orig[0:RECORD_TABLE]          unchanged prefix (dictionary, offsets,
                                  gap bytes, everything before the table)
    + new record table            same size (11,840 B), ptrs updated for
                                  every record after the grown one
    + new arrays                  44,378 + G bytes
    + orig[ARRAY_END:0x100000-G]  everything after the text region shifts
                                  by exactly +G
    (the last G bytes of the original ROM are dropped; they must be $FF
    padding, verified here — the ROM stays 1,048,576 bytes.)

Outputs are the reference grown ROM plus the two region binaries the
shiftable build consumes (the scratch src replaces the two incbin
slices for the record table and the arrays with these files, and
shrinks the trailing dcb.b padding by G).

Exit 0 only if every check passes:
  1. dropped tail bytes are all $FF
  2. new ROM is exactly 1,048,576 bytes
  3. prefix before RECORD_TABLE is byte-identical to the original
  4. the tail after the grown arrays equals the original tail shifted by G
  5. the grown record renders (via $136FC emulation) with the added words
  6. every other record renders identically to the original
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import text_encode  # noqa: E402  (reuses load_dictionary/load_record/rebuild_records/render_all)
import extract_text  # noqa: E402

RECORD_TABLE = extract_text.RECORD_TABLE
N_RECORDS = extract_text.N_RECORDS
ARRAY_BASE = extract_text.ARRAY_BASE
ARRAY_END = text_encode.ARRAY_END
ROM_SIZE = 0x100000


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", default="rop-original.gen")
    ap.add_argument("--text-dir", default="assets/text")
    ap.add_argument("--out", default="rop-grown.gen")
    ap.add_argument("--table", default="build/grown_table.bin")
    ap.add_argument("--arrays", default="build/grown_arrays.bin")
    args = ap.parse_args()

    orig = open(args.rom, "rb").read()
    assert len(orig) == ROM_SIZE, "ROM must be 1 MB, got %d" % len(orig)
    ok = True

    # --- rebuild the record table + arrays from the (grown) export -------
    words = text_encode.load_dictionary(os.path.join(args.text_dir, "dictionary.txt"))
    all_entries = [text_encode.load_record(os.path.join(args.text_dir, "rec_%04d.txt" % r))
                   for r in range(N_RECORDS)]
    table, arrays, per_record = text_encode.rebuild_records(all_entries)
    grown = [r for r in range(N_RECORDS)
             if len(per_record[r]) !=
             struct.unpack_from(">I", orig, RECORD_TABLE + r * 10 + 4)[0]]
    print("grown records: %r" % grown)
    for r in grown:
        old_len = struct.unpack_from(">I", orig, RECORD_TABLE + r * 10 + 4)[0]
        print("  rec %d: len %d -> %d bytes (+%d)"
              % (r, old_len, len(per_record[r]), len(per_record[r]) - old_len))
    G = len(arrays) - (ARRAY_END - ARRAY_BASE)
    print("array region: %d -> %d bytes (growth G = %+d)"
          % (ARRAY_END - ARRAY_BASE, len(arrays), G))
    if G <= 0:
        print("FAIL: no growth (G = %d); nothing to prove" % G)
        return 1

    # --- splice the grown ROM ---------------------------------------------
    dropped = orig[ROM_SIZE - G:]
    if dropped != b"\xff" * G:
        print("FAIL: dropped tail bytes are not all $FF: %s" % dropped.hex())
        ok = False
    else:
        print("check 1: dropped %d tail bytes are all $FF -> ok" % G)
    new = bytearray()
    new += orig[:RECORD_TABLE]
    new += table
    new += arrays
    new += orig[ARRAY_END:ROM_SIZE - G]
    if len(new) != ROM_SIZE:
        print("FAIL: new ROM is %d bytes, expected %d" % (len(new), ROM_SIZE))
        ok = False
    else:
        print("check 2: new ROM is %d bytes -> ok" % ROM_SIZE)
    if bytes(new[:RECORD_TABLE]) != orig[:RECORD_TABLE]:
        print("FAIL: prefix before RECORD_TABLE changed")
        ok = False
    else:
        print("check 3: prefix before RECORD_TABLE byte-identical -> ok")
    tail_start = RECORD_TABLE + len(table) + len(arrays)
    if bytes(new[tail_start:]) != orig[ARRAY_END:ROM_SIZE - G]:
        print("FAIL: tail after the grown arrays != original tail shifted by G")
        ok = False
    else:
        print("check 4: tail after grown arrays == original tail shifted by +%d -> ok" % G)
    # the record table itself: only ptrs after the grown record(s) change
    table_diffs = [i for i in range(0, len(table), 10)
                   if table[i:i + 10] != orig[RECORD_TABLE + i:RECORD_TABLE + i + 10]]
    print("record-table entries changed: %d (records %s)"
          % (len(table_diffs),
             sorted(set(i // 10 for i in table_diffs))[:5] + (["..."] if len(table_diffs) > 5 else [])))

    # --- renderings --------------------------------------------------------
    orig_rendered = text_encode.render_all(orig)
    new_rendered = text_encode.render_all(bytes(new))
    bad = [r for r in range(N_RECORDS) if orig_rendered[r] != new_rendered[r]]
    print("renderings: %d/%d identical (differing: %r)"
          % (N_RECORDS - len(bad), N_RECORDS, bad[:10]))
    if bad != grown:
        print("FAIL: differing records %r != grown records %r" % (bad, grown))
        ok = False
    else:
        print("check 5: only the grown record(s) render differently -> ok")
    for r in grown:
        print("  rec %d original: %r" % (r, orig_rendered[r]))
        print("  rec %d grown   : %r" % (r, new_rendered[r]))
    if all(orig_rendered[r] == new_rendered[r] for r in range(N_RECORDS) if r not in grown):
        print("check 6: every other record renders identically -> ok")
    else:
        print("FAIL: an ungrown record renders differently")
        ok = False

    if not ok:
        print("GROW: FAIL")
        return 1

    # --- write outputs -----------------------------------------------------
    os.makedirs(os.path.dirname(args.table) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.arrays) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(args.out, "wb").write(bytes(new))
    open(args.table, "wb").write(table)
    open(args.arrays, "wb").write(arrays)
    print("wrote %s (%d bytes), %s (%d B), %s (%d B)"
          % (args.out, len(new), args.table, len(table), args.arrays, len(arrays)))
    print("GROW: PASS — record(s) %r grew by %d bytes; everything after "
          "$%05X shifts by +%d" % (grown, G, ARRAY_END, G))
    return 0


if __name__ == "__main__":
    sys.exit(main())
