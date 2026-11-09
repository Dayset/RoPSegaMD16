#!/usr/bin/env python3
"""Extract all text from Rings of Power (Sega Mega Drive) ROM.

Usage:
    python3 tools/extract_text.py [rom_path] [out_dir]

Defaults: rom_path = rop-original.gen, out_dir = disasm/text/

Outputs (all offsets are file offsets == ROM addresses, 1:1 mapping):
  spaced_strings.txt   plain ASCII runs (>= 4 chars, 0x20-0x7E), offset + string
  dictionary.txt       the 3467-word dictionary: index, blob offset, word
                       (blob 0x0D6EBA-0x0DC0C0, offset table 0x0DC0C2)
  records_ddbd8.txt    the 1184 dialogue records at 0x0DDBD8 (10 bytes each:
                       u32 ptr, u32 len, u16 type) with the $136FC expansion
                       of each record's word-index array (base 0x0E0A18)
  dd5c_streams.txt     $DD5C LZSS-compressed text streams found by scanning
                       (LE32 length, mask bytes, 12-bit backrefs, length
                       = low nibble + 3, 4 KB space-prefilled ring $FF0EAC,
                       write position starts at 0xFEE)
  inventory.json       summary counts + the key addresses

Proven by (see disasm/text/README.md):
  - $136FC word-expander (0x136FC-0x1383A): word indices are 1-BASED
    (word i = blob[offs[i-1]:offs[i]]); each u16 word-index entry is
    low 14 bits word index + top 2 bits separator selector
    (00 -> space, 01 -> ',', 10 -> '.', 11 -> '?'); the loop starts at
    array index 1 and reads one entry past the record (the next record's
    first entry, normally the ' ' token). A 1-char word that equals a
    space or the separator itself suppresses the separator.
  - $13654 record dispatcher (10-byte records; type 5 -> $136FC with
    count = (len >> 1) + 1, type 1 -> $DD5C decompress, type 0 -> $DE1A
    plain copy).
  - $DD5C decompressor re-implemented and verified: the streams at
    0x0A66E6 (Book of Nexus, 2105 bytes), 0x0B3D40 (Book of Buc,
    1810 bytes), 0x0B6221 (title credits, 1590 bytes) and 0x0B83A1
    (bestiary/class text, 1188 bytes; $96120 rec 61, found in #005)
    decompress to clean readable English.
  - Ground-truth validation: docs/research/rings-of-power-ru/
    english-and-russian.txt (fan-site transcription, 2009-2010) --
    647/649 of its English sentences (99.7%) appear verbatim in the
    rendered $DDBD8 records. The 2 misses: record 0 drops its 'An'
    ($136FC skips array[0] -- likely a real display quirk, needs live
    observation), and one NPC line ("I regret that Thalmus' death...")
    whose words are in the dictionary but which is not in $DDBD8
    (undecoded dialogue bank, see README.md).
  - The Russian fan translation (romhacking.ru, bybyc9lc9l, 2012) states
    the original text system is dictionary-based and replaced it with
    compressed blocks -- independently confirming this analysis.

Do NOT copy any translated text from that fan patch into this repo.
"""
import json
import os
import struct
import sys

ROM = sys.argv[1] if len(sys.argv) > 1 else "rop-original.gen"
OUT = sys.argv[2] if len(sys.argv) > 2 else "disasm/text"

BLOB_START = 0x0D6EBA
BLOB_END = 0x0DC0C0
OFF_TABLE = 0x0DC0C2
# Dictionary: 3466 words, indices are 1-BASED (proven by $136FC, see below).
# Word i (1..3466) = blob[offs[i-1]:offs[i]]; the table holds 3467 u16
# entries (one start offset per word + the end sentinel 20998).
N_WORDS = 3466
RECORD_TABLE = 0x0DDBD8
# 1184 records; 0..1180 render real text, 1181-1182 are literal "<NA>"
# placeholders, 1183 is malformed (its array overruns into $EB772 code).
N_RECORDS = 1184
N_REAL_RECORDS = 1181
ARRAY_BASE = 0x0E0A18
SEP = {0: " ", 1: ",", 2: ".", 3: "?"}
CORPUS = "docs/research/rings-of-power-ru/txt/english-and-russian.txt"


def dd5c_decompress(data, start, max_out=60000):
    """Re-implementation of $DD5C. Returns (bytes, bytes_consumed) or None."""
    if start + 4 > len(data):
        return None
    (n,) = struct.unpack_from("<I", data, start)
    if n < 16 or n > max_out:
        return None
    ring = bytearray(b" " * 4096)  # $DD5C pre-fills $FF0EAC with 0x20
    wpos = 0xFEE
    out = bytearray()
    p = start + 4
    try:
        while len(out) < n:
            mask = data[p]
            p += 1
            for bit in range(8):
                if len(out) >= n:
                    break
                if mask & (1 << bit):
                    b = data[p]
                    p += 1
                    out.append(b)
                    ring[wpos] = b
                    wpos = (wpos + 1) & 0xFFF
                else:
                    b1 = data[p]
                    b2 = data[p + 1]
                    p += 2
                    off = b1 | ((b2 & 0xF0) << 4)
                    ln = (b2 & 0x0F) + 3  # dbra: nibble+2 in d5, loop runs +1
                    for _ in range(ln):
                        if len(out) >= n:
                            break
                        b = ring[off]
                        off = (off + 1) & 0xFFF
                        out.append(b)
                        ring[wpos] = b
                        wpos = (wpos + 1) & 0xFFF
    except IndexError:
        return None
    if len(out) != n:
        return None
    return bytes(out), p - start


def expand_record_words(data, word_array, count):
    """Literal emulation of $136FC (0x136FC-0x1383A), verified against the
    ground-truth corpus (docs/research/rings-of-power-ru/).

    - Word indices are 1-BASED: word i = blob[offs[i-1]:offs[i]] (the code
      loads table[idx-1] as the start and table[idx] as the end).
    - Each u16 entry: low 14 bits = word index, top 2 bits = separator
      selector (00 -> space, 01 -> ',', 10 -> '.', 11 -> '?').
    - The loop index d4 starts at 1 and runs while d4 < count, i.e. it
      SKIPS array[0] and reads ONE ENTRY PAST the record's nominal end
      (the next record's first entry, normally the ' ' token). The caller
      ($13654) passes count = (record_len >> 1) + 1, so the rendering of
      record r is array[1..len/2] inclusive of the read-past entry.
    - Separator is appended after the word UNLESS the word is 1 char and
      equals a space or equals the separator char itself (then it is
      suppressed -- this is how the ' ' token and '.' tokens work).
    - Quirk (verified): record 0's array[0] is the word 'An' (not a space
      token), so the game renders record 0 as "unknown building." -- the
      'An' is dropped. The fans' transcription has "An unknown building.";
      whether the game really shows the dropped article or some other path
      restores it needs live observation (#020).
    """
    blob = data[BLOB_START:BLOB_END]
    offs = struct.unpack_from(">%dH" % (N_WORDS + 1), data, OFF_TABLE)
    words = []
    for i in range(1, count):  # d4 = 1; while d4 < count
        entry = word_array[i]
        idx = entry & 0x3FFF
        sep = SEP[(entry >> 14) & 3]
        if idx < 1 or idx > N_WORDS:
            words.append("<?%d>" % idx)
            continue
        w = blob[offs[idx - 1]:offs[idx]].decode("ascii", "replace")
        words.append(w)
        if not (len(w) == 1 and (w == " " or w == sep)):
            words.append(sep)
    return "".join(words)


def validate_against_corpus(rendered):
    """Check rendered $DDBD8 records against the fan-site ground-truth
    corpus (english-and-russian.txt). Returns a dict for inventory.json.
    Corpus sentences are matched as substrings of the joined rendered
    text after normalising whitespace, '--' -> '-', and ellipsis runs.
    """
    import re
    try:
        corpus = open(CORPUS, encoding="utf-8").read()
    except FileNotFoundError:
        return {"corpus": "missing", "checked": 0}

    def norm(s):
        s = s.replace("\ufeff", "").replace("--", "-")
        s = re.sub(r"\.{3,}", "...", s)
        return re.sub(r"\s+", " ", s).strip()

    big = " ".join(norm(x) for x in rendered)
    is_cyr = lambda s: bool(re.search(r"[\u0400-\u04FF]", s))
    en_lines = [l.strip() for l in corpus.split("\n")
                if l.strip() and not is_cyr(l)]
    flow = " ".join(en_lines)
    sentences = [norm(p) for p in re.split(r"(?<=[.?!])\s+", flow)
                 if norm(p)]
    # drop the doc artifact that concatenates 4 bare <NA> records
    sentences = [s for s in sentences if not s.startswith("<NA> <NA>")]
    found = [s for s in sentences if s in big]
    missing = [s for s in sentences if s not in big]
    return {"corpus": CORPUS,
            "sentences_checked": len(sentences),
            "sentences_found": len(found),
            "sentences_missing": missing}


def main():
    data = open(ROM, "rb").read()
    os.makedirs(OUT, exist_ok=True)

    # --- 1. spaced ASCII strings -------------------------------------------
    spaced = []
    i = 0
    while i < len(data):
        if 0x20 <= data[i] <= 0x7E:
            j = i
            while j < len(data) and 0x20 <= data[j] <= 0x7E:
                j += 1
            if j - i >= 4:
                spaced.append((i, data[i:j].decode("ascii")))
            i = j
        else:
            i += 1
    with open(os.path.join(OUT, "spaced_strings.txt"), "w") as f:
        for off, s in spaced:
            f.write("0x%06X %4d %s\n" % (off, len(s), s))

    # --- 2. dictionary ------------------------------------------------------
    # Indices are 1-BASED: word i = blob[offs[i-1]:offs[i]] ($136FC loads
    # table[idx-1] as the start offset). offs[0] = 0, offs[3466] = 20998.
    offs = struct.unpack_from(">%dH" % (N_WORDS + 1), data, OFF_TABLE)
    assert offs[0] == 0 and offs[N_WORDS] == BLOB_END - BLOB_START
    blob = data[BLOB_START:BLOB_END]
    words = [blob[offs[i - 1]:offs[i]].decode("ascii")
             for i in range(1, N_WORDS + 1)]
    with open(os.path.join(OUT, "dictionary.txt"), "w") as f:
        for i, w in enumerate(words, start=1):
            f.write("%4d 0x%05X %r\n" % (i, offs[i - 1], w))

    # --- 3. dialogue records ($DDBD8, 1184 x 10 bytes) ----------------------
    rendered = []
    with open(os.path.join(OUT, "records_ddbd8.txt"), "w") as f:
        for r in range(N_RECORDS):
            ptr, ln, typ = struct.unpack_from(">IIH", data, RECORD_TABLE + r * 10)
            if typ != 5:
                f.write("rec %4d ptr=0x%05X len=%3d type=%d\n"
                        % (r, ptr, ln, typ))
                continue
            if r >= N_REAL_RECORDS + 2:  # rec 1183: malformed dummy
                f.write("rec %4d ptr=0x%05X len=%3d type=5 MALFORMED "
                        "(array overruns into $EB772 code; not rendered)\n"
                        % (r, ptr, ln))
                continue
            count = (ln >> 1) + 1  # $13654: count = (record+4 >> 1) + 1
            arr = struct.unpack_from(">%dH" % (count + 1), data,
                                     ARRAY_BASE + ptr)
            text = expand_record_words(data, arr, count)
            rendered.append(text.strip())
            f.write("rec %4d ptr=0x%05X len=%3d type=5 words=%d\n  %s\n"
                    % (r, ptr, ln, count, text))
    validation = validate_against_corpus(rendered)

    # --- 4. $DD5C streams (scan) -------------------------------------------
    streams = []
    for start in range(0, len(data) - 4):
        (n,) = struct.unpack_from("<I", data, start)
        if n < 100 or n > 20000:
            continue
        # quick filter: first literals mostly printable (allow up to 2
        # control bytes — real text streams embed control sequences,
        # e.g. $96120 rec 61 has 0xF1 among its first 8 literals)
        window = data[start + 5:start + 13]
        if sum(1 for b in window
               if 0x20 <= b <= 0x7E or b in (9, 10, 13)) < 6:
            continue
        res = dd5c_decompress(data, start)
        if res is None:
            continue
        out, used = res
        letters = sum(1 for b in out if 0x41 <= b <= 0x5A or 0x61 <= b <= 0x7A)
        spaces = sum(1 for b in out if b == 0x20)
        printable = sum(1 for b in out
                        if 0x20 <= b <= 0x7E or b in (9, 10, 13))
        # Text, not tile data: dense letters, bounded space share. The
        # space-prefilled ring makes backref-heavy binary streams (tile
        # data, e.g. 0x042E42) decompress to mostly spaces -- those are
        # real $DD5C streams but not text, so they are excluded here.
        if (printable * 100 // len(out) < 90
                or letters * 100 // len(out) < 35
                or spaces * 100 // len(out) > 45):
            continue
        streams.append((start, n, used, out))
    with open(os.path.join(OUT, "dd5c_streams.txt"), "w") as f:
        for start, n, used, out in streams:
            f.write("=== stream at 0x%06X, decompressed %d bytes, "
                    "compressed %d bytes ===\n" % (start, n, used))
            f.write(out.decode("ascii", "replace"))
            f.write("\n\n")

    inventory = {
        "rom": os.path.basename(ROM),
        "rom_size": len(data),
        "spaced_strings_ge4": len(spaced),
        "spaced_strings_ge8": sum(1 for _, s in spaced if len(s) >= 8),
        "dictionary_words": N_WORDS,
        "dictionary_blob": "0x%06X-0x%06X" % (BLOB_START, BLOB_END),
        "dictionary_offset_table": "0x%06X" % OFF_TABLE,
        "dialogue_records": N_RECORDS,
        "dialogue_real_records": N_REAL_RECORDS,
        "dialogue_placeholders": [1181, 1182],
        "dialogue_malformed": [1183],
        "dialogue_record_table": "0x%06X-0x%06X" % (RECORD_TABLE, ARRAY_BASE),
        "dialogue_word_arrays": "0x%06X-0x%06X" % (ARRAY_BASE, 0xEB772),
        "dd5c_streams_found": len(streams),
        "dd5c_stream_offsets": ["0x%06X" % s[0] for s in streams],
        "decoder_routine": "0x136FC (word expander, 1-based indices), "
                           "0x13654 (record dispatcher)",
        "decompressor_routine": "0xDD5C",
        "corpus_validation": validation,
    }
    with open(os.path.join(OUT, "inventory.json"), "w") as f:
        json.dump(inventory, f, indent=2)
    print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    main()
