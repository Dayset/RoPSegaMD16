#!/usr/bin/env python3
"""Export the Rings of Power dialogue ($DDBD8, 1184 records) and its
3,466-word dictionary to editable text files under assets/text/.

Usage:
    python3 tools/text_export.py [--rom PATH] [--out DIR]

Defaults: --rom rop-original.gen, --out assets/text

The export is losslessly re-encodable: tools/text_encode.py reads these
files back and rebuilds the exact original bytes (dictionary blob +
offset table + record table + word arrays), verified byte-for-byte.

Format
------
assets/text/dictionary.txt — one word per line as `<index> <repr(word)>`
(1-based indices; repr makes the space token ' ' unambiguous). Words are
unique, so a word maps to exactly one index.

assets/text/rec_NNNN.txt — one file per dialogue record:
  - header (comment lines): record id, ptr/len/type, the $136FC
    rendering (as repr, so trailing spaces are visible), a note on
    which entries $136FC actually renders, and the read-past entry.
  - one line per stored array entry:
        N idx=K sep=NAME # 'word'
    The entry (idx + sep) is authoritative for re-encoding; the word
    after '#' is a human-readable comment from the dictionary.
    Each file stores exactly its own len/2 entries; the read-past word
    lives in the next record's file, never duplicated.

$136FC quirks preserved (see tools/extract_text.py expand_record_words):
  - indices are 1-BASED; each u16 entry is low 14 bits word index +
    top 2 bits separator selector (00 space, 01 ',', 10 '.', 11 '?').
  - the loop starts at array[1] and reads one entry past the record's
    nominal end (the next record's first entry, normally the ' ' token).
    array[0] is stored but not rendered.
  - a 1-char word that equals a space or equals the separator itself
    suppresses the separator.
  - rec 0 drops its 'An' (array[0] is the word 'An', skipped by the
    loop) — the game renders "unknown building.", not "An unknown...".
  - rec 1183 is malformed: its array overruns into $EB772 code. Its
    entry [2] is idx 3531 (out of range, rendered <?3531>), and its
    read-past entry is the first u16 of code at $EB772 (0x48E7 ->
    idx 2279 'vessle', sep comma). The read-past entry is code, not
    text: it is recorded as a note, never stored as an entry.
  - the 2 bytes at 0x0DC0C0-0x0DC0C1 (FF 6F) sit between the dictionary
    blob and the offset table; they are not text data and are not
    exported or rebuilt.
"""
import argparse
import os
import struct
import sys

# extract_text.py binds ROM/OUT from sys.argv at import time; shield argv
# so the import only brings in its constants and expand_record_words.
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
SEP = extract_text.SEP
SEP_NAME = {0: "space", 1: "comma", 2: "period", 3: "question"}


def load_rom(path):
    with open(path, "rb") as f:
        return f.read()


def load_dictionary(data):
    """Return (words, offs): words[i] is dictionary word i+1 (1-based)."""
    offs = struct.unpack_from(">%dH" % (N_WORDS + 1), data, OFF_TABLE)
    assert offs[0] == 0 and offs[N_WORDS] == BLOB_END - BLOB_START, \
        "offset table sentinel mismatch: %d / %d" % (
            offs[N_WORDS], BLOB_END - BLOB_START)
    blob = data[BLOB_START:BLOB_END]
    words = [blob[offs[i - 1]:offs[i]].decode("ascii")
             for i in range(1, N_WORDS + 1)]
    return words, offs


def load_records(data):
    """Return [(ptr, ln, typ, entries)] for all 1184 records."""
    records = []
    for r in range(N_RECORDS):
        ptr, ln, typ = struct.unpack_from(">IIH", data, RECORD_TABLE + r * 10)
        n = ln >> 1
        entries = struct.unpack_from(">%dH" % n, data, ARRAY_BASE + ptr) \
            if n else ()
        records.append((ptr, ln, typ, entries))
    return records


def word_comment(idx, words):
    """Human-readable comment for an entry index."""
    if 1 <= idx <= N_WORDS:
        return repr(words[idx - 1])
    return "'<?%d>'" % idx


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rom", default="rop-original.gen")
    ap.add_argument("--out", default="assets/text")
    args = ap.parse_args()

    data = load_rom(args.rom)
    words, offs = load_dictionary(data)
    if len(set(words)) != len(words):
        dups = [w for w in set(words) if words.count(w) > 1]
        raise SystemExit("dictionary words not unique: %r" % dups[:5])
    records = load_records(data)

    # --- sanity checks (all verified on the first build; re-assert) --------
    bad_types = [(r, t) for r, (_, _, t, _) in enumerate(records) if t != 5]
    if bad_types:
        raise SystemExit("non-type-5 records: %r" % bad_types[:5])
    total = 0
    for r, (ptr, ln, typ, entries) in enumerate(records):
        if ptr != total:
            raise SystemExit(
                "record %d not contiguous: ptr=%d, expected %d" % (r, ptr, total))
        total += ln
    array_end = ARRAY_BASE + total
    if array_end != 0xEB772:
        raise SystemExit("array region ends at 0x%X, expected 0xEB772" % array_end)
    sep_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    oob = []
    for r, (ptr, ln, typ, entries) in enumerate(records):
        for i, e in enumerate(entries):
            sep_counts[(e >> 14) & 3] += 1
            if not (1 <= (e & 0x3FFF) <= N_WORDS):
                oob.append((r, i, e & 0x3FFF))
    print("dictionary: %d words, %d unique" % (len(words), len(set(words))))
    print("records: %d, all type 5; arrays contiguous, %d bytes "
          "(0x%06X-0x%06X)" % (len(records), total, ARRAY_BASE, array_end))
    print("separators: space %d, comma %d, period %d, question %d"
          % (sep_counts[0], sep_counts[1], sep_counts[2], sep_counts[3]))
    print("out-of-range indices: %r" % oob)

    os.makedirs(args.out, exist_ok=True)

    # --- dictionary ---------------------------------------------------------
    with open(os.path.join(args.out, "dictionary.txt"), "w") as f:
        f.write("# Rings of Power dictionary — %d words, 1-based indices\n"
                % N_WORDS)
        f.write("# blob 0x%06X-0x%06X (%d bytes); offset table 0x%06X "
                "(%d u16 BE)\n" % (BLOB_START, BLOB_END, BLOB_END - BLOB_START,
                                   OFF_TABLE, N_WORDS + 1))
        f.write("# Each line: <index> <word as Python repr>. Word strings "
                "are unique (no duplicates), so a word maps to exactly one "
                "index. Word 4 is the space token ' '.\n")
        f.write("# The 2 bytes at 0x0DC0C0-0x0DC0C1 (FF 6F) sit between the "
                "blob and the offset table; they are not text and are not "
                "rebuilt.\n")
        for i, w in enumerate(words, start=1):
            f.write("%d %r\n" % (i, w))

    # --- records ------------------------------------------------------------
    for r, (ptr, ln, typ, entries) in enumerate(records):
        n = len(entries)
        count = (ln >> 1) + 1  # $13654: count = (len >> 1) + 1
        # read-past entry: the u16 just after this record's array
        (read_past,) = struct.unpack_from(">H", data, ARRAY_BASE + ptr + ln)
        rp_idx = read_past & 0x3FFF
        rp_sep = SEP_NAME[(read_past >> 14) & 3]
        # rendering needs array[1..n] incl. the read-past entry
        arr = list(entries) + [read_past]
        text = extract_text.expand_record_words(data, arr, count)
        if r + 1 < N_RECORDS:
            rp_note = ("read-past entry: rec %d array[0], idx=%d sep=%s %s"
                       % (r + 1, rp_idx, rp_sep, word_comment(rp_idx, words)))
        else:
            rp_note = ("read-past entry: code at $EB772 (0x%04X -> idx=%d "
                       "sep=%s %s) — not stored, preserved as note"
                       % (read_past, rp_idx, rp_sep,
                          word_comment(rp_idx, words)))
        with open(os.path.join(args.out, "rec_%04d.txt" % r), "w") as f:
            f.write("# rec %d | ptr=0x%05X len=%d type=%d | entries=%d\n"
                    % (r, ptr, ln, typ, n))
            f.write("# rendered: %r\n" % text)
            f.write("# $136FC skips array[0] and renders array[1..%d], "
                    "inclusive of the read-past entry\n" % n)
            f.write("# (%s). array[0] below is stored but not rendered "
                    "in this record.\n" % rp_note)
            f.write("# Separators (top 2 bits of each entry): space=0 "
                    "comma=1 period=2 question=3. The entry (idx + sep) "
                    "is authoritative\n")
            f.write("# for re-encoding; the word after '#' is a "
                    "human-readable comment from the dictionary.\n")
            for i, e in enumerate(entries):
                idx = e & 0x3FFF
                sep = SEP_NAME[(e >> 14) & 3]
                f.write("%d idx=%d sep=%s # %s\n"
                        % (i, idx, sep, word_comment(idx, words)))

    print("wrote %d record files + dictionary.txt to %s"
          % (N_RECORDS, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
