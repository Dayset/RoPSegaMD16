# Rings of Power — editable dialogue text (issue #18)

The game's dialogue ($DDBD8, 1,184 records) and its 3,466-word
dictionary, exported as plain text. Edit these files, then rebuild the
exact original ROM bytes with `tools/text_encode.py` (which verifies the
result byte-for-byte against the ROM).

## Files

- `dictionary.txt` — one word per line: `<index> <repr(word)>`.
  Indices are 1-based. Words are unique, so a word maps to exactly one
  index. Word 4 is the space token `' '`.
- `rec_NNNN.txt` — one file per dialogue record (0–1183). Header
  (comment lines) gives the record id, ptr/len/type, the $136FC
  rendering (as repr), and the read-past entry. Then one line per
  stored array entry:
  ```
  N idx=K sep=NAME # 'word'
  ```
  The entry (idx + sep) is authoritative for re-encoding; the word
  after `#` is a human-readable comment from the dictionary and is
  ignored by the encoder.

## Format rules (from $136FC / $13654, see tools/extract_text.py)

- Each u16 entry is low 14 bits word index + top 2 bits separator
  selector: 00 space, 01 comma, 10 period, 11 question.
- The game renders array[1..len/2] — array[0] is stored but skipped,
  and one entry past the record's nominal end is read (the next
  record's first entry, normally the `' '` token). That is why rec 0
  renders "unknown building." — its array[0] is the word 'An', which
  the game drops.
- A 1-char word that equals a space or equals the separator itself
  suppresses the separator (this is how the `' '` and `'.'` tokens work).
- Each record file stores exactly its own len/2 entries. The read-past
  word lives in the next record's file, never duplicated.
- Rec 1183 is malformed: its array overruns into $EB772 code. Its
  entry [2] is idx 3531 (out of range, rendered `<?3531>`), and its
  read-past entry is the first u16 of code at $EB772 (0x48E7 → idx 2279
  `'vessle'`, sep comma). That entry is code, not text: it is recorded
  as a header note and never stored as an entry.
- The 2 bytes at 0x0DC0C0–0x0DC0C1 (`FF 6F`) sit between the dictionary
  blob and the offset table. They are not text data and are not
  exported or rebuilt.

## Commands

```sh
# export (regenerate this tree from the ROM)
python3 tools/text_export.py [--rom rop-original.gen] [--out assets/text]

# re-encode + verify byte-for-byte (exit 0 only on a full pass)
python3 tools/text_encode.py [--rom rop-original.gen] [--text-dir assets/text]
```

Round-trip proof (2026-11-11): dictionary blob 20,998 B, offset table
6,934 B, record table 11,840 B, array region 44,378 B — all IDENTICAL;
per-record arrays 1184/1184 byte-identical; renderings 1184/1184
identical. A mutation test (one separator + one dictionary word
changed) fails exactly as expected, proving the encoder is driven by
these files and not by the ROM.

## Longer text (M9-dependent)

This pipeline reproduces the existing records byte-identically; it does
not resize them. Growing a record past its current length needs M9
(shiftable build, #16): the record table stores byte lengths and the
arrays are packed contiguously, so a longer record must shift every
following array and update all subsequent ptrs — impossible while
absolute addresses are hard-coded.
