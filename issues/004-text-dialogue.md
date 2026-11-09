# Issue #004 — Text / dialogue extraction + tables

**Milestone:** M3
**Epic 3**
**Status:** ✅ done 2026-11-09

## Goal
Extract all in-game text with addresses, so dialogue edits are safe.

## Acceptance
- [x] `tools/extract_text.py` dumps strings with file offsets
- [x] Dialogue blob start/end + pointer table (if any) identified
- [x] A same-length text replacement proven: patch → checksum → loads in emulator
- [x] Text inventory saved under `disasm/text/`

## Evidence

Full write-up: `disasm/text/README.md`. Inventory: `disasm/text/inventory.json`.

### The dictionary system (verified)

- Word blob `0x0D6EBA–0x0DC0C0` (20,998 bytes, concatenated ASCII) +
  offset table `0x0DC0C2` (3,467 u16 entries, last = 20,998).
- **3,466 words, indices 1-based**: word *i* = `blob[offs[i-1]:offs[i]]`.
  Word 1 = `An`, 4 = ` `, 5 = `A`, 6 = `Sorcerer's`, 7 = `Guild`.
- `$13654` dispatcher (10-byte records: u32 offset, u32 length, u16 type):
  type 0 → `$DE1A` plain copy, type 1 → `$DD5C` decompress,
  type 5 → `$136FC` word expansion, count = (length >> 1) + 1.
- `$136FC` (0x136FC–0x1383A), exact semantics from Capstone: loop index
  starts at 1 (skips array[0], reads one entry past the record); each u16
  = low 14 bits word index + top 2 bits separator
  (00 space, 01 `,`, 10 `.`, 11 `?`); separator suppressed for 1-char
  words that are a space or the separator itself.
- `$DDBD8` table: 1,184 records, all type 5, word arrays
  `0x0E0A18–0x0EB772`. Records 0–1180 real text; 1181–1182 literal
  `<NA>` placeholders; 1183 malformed (array overruns into `$EB772` code).
- `$96120`: 62 records, all type 1 — decompress to tile/map binary, not text.

### `$DD5C` LZSS (verified)

LE32 length, mask bytes (1 = literal, 0 = 2-byte backref: 12-bit offset,
length = low nibble + 3), 4 KB space-prefilled ring `$FF0EAC`, write pos
starts `0xFEE`. Four text streams decode to clean English:
`0x0A66E6` Book of Nexus (2,105 B), `0x0B3D40` Book of Buc (1,810 B),
`0x0B6221` title credits (1,590 B), `0x0B83A1` bestiary/class text
(1,188 B; `$96120` rec 61 — found in #005, scanner quick-filter fix
2026-11-09). The "strided" look is `0xFF` mask
bytes (8 literals) — not a separate scheme.

### Ground-truth validation

`docs/research/rings-of-power-ru/txt/english-and-russian.txt`
(fan-site transcription, 2009–2010): **647/649 (99.7%) of its English
sentences appear verbatim in the rendered `$DDBD8` records.** Misses:
record 0 drops its `An` (the `$136FC` skip-array[0] quirk — likely a
real 1992 display bug, needs live observation), and one NPC line
("I regret that Thalmus' death…") whose words are in the dictionary
but which lives in an undecoded dialogue bank.

### Russian fan translation (independent confirmation)

romhacking.ru, bybyc9lc9l, 2012: author says he changed the text system
"from dictionary-based to compressed blocks". His IPS patch (1,549
records) was diffed against the original (no translated text copied):
it repoints `$136FC`'s table base `$DC0C2` → `$D6F30`, replaces the blob
with a pointer table (`$D7030`) + compressed blocks + a new reader
routine (`$D6F50`: block = id >> 6, string = id & 63), adds VDP
font-upload routines (`$FD0D0`, `$1AA70`, `$E8C70`), and neutralises
the runtime checksum (`0xFD09C` bne → nop) while fixing the header
checksum. See `disasm/text/README.md` §5.

### Same-length replacement (proven)

`Continue` at `0x15BE1` → `Resumed ` (8 bytes). `fix-all`: header
`0x8B9F` → `0xDDAD`, runtime `0x8F33608C` → `0x4B464D80`; `verify-all`
passes both; exactly 14 bytes differ from the original. Booted in
BlastEm 0.6.3.4 (Xvfb + dummy audio) — Naughty Dog logo, title screen,
then (after Start) the "From the Book of Nexus" story page, which renders
the `$DD5C` text verbatim on screen. A checksum failure hangs at
`0xFD0CA` before any display, so any rendered frame proves the check
passed. Screenshot: `disasm/text/boot-test-patched.png`. The test was
first run before a VM restart (which wiped `/tmp`) and then fully
re-run on the fresh VM with identical results. The Start/Continue menu
itself was not displayed (Start advances the story intro; the load menu
likely needs a save to exist) — showing `Resumed ` on screen is a small
follow-up for #022.

## Open (for later issues)

- Record 0's dropped `An`: display bug or another path? (#020, live observation)
- `&` string separator in `0x32EC4` post-processing: source unknown.
- `$B8A32` (caller `0x11AFE`) does not parse as `$13654` records —
  its text (incl. the Thalmus line) is undecoded.
- Control codes in `$DD5C` streams (`\x00`, `( (( #$%&(()*+((/<=>`).
- `FF 6F` at `0x0DC0C0–0x0DC0C1`; original font table (#005/#016).
- For #019: Russian-patch commenter says the Serial EEPROM save needs
  rework to common SRAM (flash carts/emulators don't support it).
- For #021: music-off doesn't stick, auto-enables on location change.
