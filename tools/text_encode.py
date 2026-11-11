#!/usr/bin/env python3
"""Re-encode the editable text export (assets/text/) back to ROM bytes
and verify the result byte-for-byte against the original ROM.

Usage:
    python3 tools/text_encode.py [--rom PATH] [--text-dir DIR]

Defaults: --rom rop-original.gen, --text-dir assets/text

Checks (all must pass; exit 0 only on a full pass):
  1. dictionary blob      rebuilt 20,998 B == original
  2. offset table         rebuilt  6,934 B == original
  3. record table         rebuilt 11,840 B == original (ptr/len/type)
  4. array region         rebuilt 44,378 B == original
  5. per-record arrays    1184/1184 byte-identical
  6. renderings           1184/1184 identical (rebuilt regions spliced
                          into a ROM copy, $136FC re-run via
                          extract_text.expand_record_words)

The export is authoritative on (idx + sep) per entry; the word comment
after '#' is ignored. The dictionary is authoritative on word strings;
the offset table is derived from the concatenated words. Record ptrs
are derived from the packed contiguous arrays (ptr of record r = sum
of the lengths of records 0..r-1), which the exporter verified matches
the original layout.

The 2 bytes at 0x0DC0C0-0x0DC0C1 (FF 6F) are not text and are not
rebuilt; the read-past entry of rec 1183 (code at $EB772) is likewise
not stored — it is read from the ROM at render time, exactly as the
original game does.
"""
import argparse
import ast
import os
import re
import struct
import sys

_argv = sys.argv
sys.argv = [sys.argv[0]]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_text  # noqa: E402
sys.argv = _argv

BLOB_START = extract_text.BLOB_START
BLOB_END = extract_text.BLOB_END
OFF_TABLE = extract_text.OFF_TABLE
N_WORDS = extract_text.N_WORDS
RECORD_TABLE = extract_text.RECORD_TABLE
N_RECORDS = extract_text.N_RECORDS
ARRAY_BASE = extract_text.ARRAY_BASE
ARRAY_END = 0xEB772
SEP_CODE = {"space": 0, "comma": 1, "period": 2, "question": 3}

ENTRY_RE = re.compile(r"^(\d+) idx=(\d+) sep=(space|comma|period|question)\s*#")
DICT_RE = re.compile(r"^(\d+) (.*)$")


def load_dictionary(path):
    """Parse assets/text/dictionary.txt -> words list (1-based)."""
    words = {}
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            m = DICT_RE.match(line)
            if not m:
                raise ValueError("bad dictionary line: %r" % line)
            words[int(m.group(1))] = ast.literal_eval(m.group(2))
    if sorted(words) != list(range(1, N_WORDS + 1)):
        raise ValueError("dictionary indices are not exactly 1..%d" % N_WORDS)
    return [words[i] for i in range(1, N_WORDS + 1)]


def load_record(path):
    """Parse one rec file -> [(idx, sep_name), ...] in entry order."""
    entries = {}
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            m = ENTRY_RE.match(line)
            if not m:
                raise ValueError("%s: bad entry line: %r" % (path, line))
            entries[int(m.group(1))] = (int(m.group(2)), m.group(3))
    if sorted(entries) != list(range(len(entries))):
        raise ValueError("%s: entry numbers are not 0..%d" % (path, len(entries) - 1))
    return [entries[i] for i in range(len(entries))]


def rebuild_dictionary(words):
    """Return (blob, offset_table_bytes) from the word list."""
    blob = bytearray()
    offs = [0]
    for w in words:
        blob += w.encode("ascii")
        offs.append(len(blob))
    return bytes(blob), struct.pack(">%dH" % len(offs), *offs)


def rebuild_records(all_entries):
    """Return (record_table_bytes, array_bytes, per_record_arrays)."""
    table = bytearray()
    arrays = bytearray()
    per_record = []
    ptr = 0
    for entries in all_entries:
        arr = b"".join(struct.pack(">H", (SEP_CODE[sep] << 14) | idx)
                       for idx, sep in entries)
        table += struct.pack(">IIH", ptr, len(arr), 5)
        arrays += arr
        per_record.append(arr)
        ptr += len(arr)
    return bytes(table), bytes(arrays), per_record


def render_all(data):
    """Render all 1184 records from a ROM image via $136FC emulation."""
    rendered = []
    for r in range(N_RECORDS):
        ptr, ln, typ = struct.unpack_from(">IIH", data, RECORD_TABLE + r * 10)
        count = (ln >> 1) + 1
        arr = struct.unpack_from(">%dH" % (count + 1), data, ARRAY_BASE + ptr)
        rendered.append(extract_text.expand_record_words(data, arr, count))
    return rendered


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", default="rop-original.gen")
    ap.add_argument("--text-dir", default="assets/text")
    args = ap.parse_args()

    data = open(args.rom, "rb").read()
    ok = True

    def check(label, rebuilt, original):
        nonlocal ok
        same = rebuilt == original
        print("  %-18s rebuilt %6d B, original %6d B -> %s"
              % (label, len(rebuilt), len(original),
                 "IDENTICAL" if same else "DIFFER"))
        if not same:
            ok = False
            for i, (a, b) in enumerate(zip(rebuilt, original)):
                if a != b:
                    print("    first diff at offset %d: rebuilt 0x%02X, "
                          "original 0x%02X" % (i, a, b))
                    break
            if len(rebuilt) != len(original):
                print("    length differs: rebuilt %d, original %d"
                      % (len(rebuilt), len(original)))
        return same

    # --- 1-2. dictionary ----------------------------------------------------
    words = load_dictionary(os.path.join(args.text_dir, "dictionary.txt"))
    blob, offs = rebuild_dictionary(words)
    print("region byte-identical check:")
    check("dictionary blob", blob, data[BLOB_START:BLOB_END])
    check("offset table", offs,
          data[OFF_TABLE:OFF_TABLE + 2 * (N_WORDS + 1)])

    # --- 3-4. records -------------------------------------------------------
    all_entries = [load_record(os.path.join(args.text_dir, "rec_%04d.txt" % r))
                   for r in range(N_RECORDS)]
    table, arrays, per_record = rebuild_records(all_entries)
    check("record table", table,
          data[RECORD_TABLE:RECORD_TABLE + 10 * N_RECORDS])
    check("array region", arrays, data[ARRAY_BASE:ARRAY_END])

    # --- 5. per-record arrays ----------------------------------------------
    bad = []
    orig_arrays = data[ARRAY_BASE:ARRAY_END]
    pos = 0
    for r, arr in enumerate(per_record):
        if orig_arrays[pos:pos + len(arr)] != arr:
            bad.append(r)
        pos += len(arr)
    print("per-record arrays: %d/%d byte-identical%s"
          % (N_RECORDS - len(bad), N_RECORDS,
             "" if not bad else " (failing: %r)" % bad[:10]))
    if bad:
        ok = False

    # --- 6. renderings ------------------------------------------------------
    spliced = bytearray(data)
    spliced[BLOB_START:BLOB_END] = blob
    spliced[OFF_TABLE:OFF_TABLE + 2 * (N_WORDS + 1)] = offs
    spliced[RECORD_TABLE:RECORD_TABLE + 10 * N_RECORDS] = table
    spliced[ARRAY_BASE:ARRAY_END] = arrays
    orig_rendered = render_all(data)
    new_rendered = render_all(bytes(spliced))
    bad_render = [r for r in range(N_RECORDS)
                  if orig_rendered[r] != new_rendered[r]]
    print("renderings: %d/%d identical%s"
          % (N_RECORDS - len(bad_render), N_RECORDS,
             "" if not bad_render else " (differing: %r)" % bad_render[:10]))
    if bad_render:
        ok = False
        for r in bad_render[:3]:
            print("  rec %d original: %r" % (r, orig_rendered[r]))
            print("  rec %d rebuilt : %r" % (r, new_rendered[r]))

    print("ROUND-TRIP: %s"
          % ("PASS — all regions byte-identical, all renderings identical"
             if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
