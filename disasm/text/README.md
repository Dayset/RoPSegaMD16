# Text encoding — Rings of Power (Mega Drive)

Everything in this directory was produced by `tools/extract_text.py` from
`rop-original.gen` (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`). All offsets are
file offsets, which equal ROM addresses 1:1.

## Files

| File | Contents |
|---|---|
| `spaced_strings.txt` | Every plain-ASCII run ≥ 4 chars (offset, length, string). 14,133 runs ≥ 4 chars, 1,807 ≥ 8. The ≥ 4 count is inflated by tile data that happens to look ASCII; the ≥ 8 list is mostly real text. |
| `dictionary.txt` | The 3,466-word dictionary, 1-based index, blob offset, word. |
| `records_ddbd8.txt` | All 1,184 dialogue records at `0x0DDBD8`, expanded with the literal `$136FC` semantics below. |
| `dd5c_streams.txt` | The 3 `$DD5C`-compressed text streams, decompressed. |
| `inventory.json` | Counts, key addresses, and the corpus-validation result. |

## 1. The dictionary system (dialogue + location descriptions)

The original text system is **dictionary-based**. The Russian fan
translation's author states it himself (see §5): he changed the text system
"from dictionary-based to compressed blocks".

### Storage

- **Word blob** `0x0D6EBA–0x0DC0C0` (20,998 bytes): all words concatenated,
  plain ASCII, no separators (`Anunknownbuilding ASorcerer'sGuildYou…`).
  Two bytes `FF 6F` sit between the blob end and the offset table
  (`0x0DC0C0–0x0DC0C1`, meaning unknown).
- **Offset table** `0x0DC0C2`: 3,467 big-endian u16 entries, monotonically
  increasing, last entry 20,998 = blob length. Entry *i* is the start
  offset of word *i+1*.
- **Dictionary**: 3,466 words, indices **1-based**: word *i* =
  `blob[offs[i-1] : offs[i]]`. Word 1 = `An`, 2 = `unknown`,
  3 = `building`, 4 = ` ` (single space), 5 = `A`, 6 = `Sorcerer's`,
  7 = `Guild`, 8 = `You`, 9 = `feel`, 10 = `eyes`, 11 = `watching`,
  12 = `you`, 13 = `of`, 14 = `the`, … word 3466 = `differences`.
  Word 463 is the literal placeholder `<NA>` (see §4).

### Record tables

`$13654` (0x13654) dispatches on 10-byte records
`(u32 data_offset, u32 length, u16 type)`:

| type | action |
|---|---|
| 0 | `jsr $DE1A` — plain byte copy, count = record length |
| 1 | `jsr $DD5C` — decompress (see §2) |
| 5 | `bsr $136FC` — word expansion, count = (length >> 1) + 1 |

Record index × 10 into the table; data pointer = base + record+0.
Known callers: `0x11AFE` (table `$B8A32`, base `$B86AE`),
`0x13856` and `0x1485E` (table `$96120`, base `$9638C`),
`0x19778` (call site not yet disassembled),
`0x32EC4` (table `$DDBD8`, base `$E0A18` — the dialogue/location table).

**`$DDBD8` table** (used by `0x32EC4`): 1,184 records, `0x0DDBD8–0x0E0A18`,
all type 5. Word arrays at `0x0E0A18–0x0EB772` (ends exactly where the
`$EB772` sound-tick code starts). Records 0–1180 render real text;
1181–1182 are literal `<NA>` placeholders; 1183 is malformed (its array
overruns into `$EB772` code and is never meant to be rendered).

**`$96120` table**: 62 records, all type 1 — they decompress to binary
(tile/map) data, not text. Type 1 = compressed binary assets, not dialogue.

### The `$136FC` word expander (0x136FC–0x1383A) — exact semantics

Verified instruction by instruction (Capstone) and against ground truth
(§4). Arguments: word-index array pointer, output buffer, count.

1. Loop index `d4` starts at **1** and runs while `d4 < count` — i.e. it
   **skips array[0] and reads one entry past the record's nominal end**
   (the next record's first entry, normally the ` ` token). Every
   record's array[0] is the ` ` token (word 4), except record 0, whose
   array[0] is `An` (see quirk below).
2. Each u16 entry = **low 14 bits word index + top 2 bits separator
   selector**: `00` → space `0x20`, `01` → `,`, `10` → `.`, `11` → `?`.
3. Word lookup is 1-based: start = `offs[idx-1]`, end = `offs[idx]`
   (the code does `table[idx-1]` then `table[idx]`).
4. The word is copied, then the separator is appended **unless the word
   is 1 char and equals a space or equals the separator char itself**
   (then it is suppressed). This is how the ` ` token and bare `.`
   tokens work.
5. Returns the output length in `d0`.

Example (record 1, `ptr=6 len=20`): array
`[4, 5, 6, 0x8007, 4, 8, 9, 10, 11, 0x800C]` renders as
`A Sorcerer's Guild. You feel eyes watching you. ` — the leading ` `
token (array[0]) is skipped, the trailing ` ` comes from the read-past
entry (record 2's array[0]).

### Quirk: record 0 drops its `An`

Record 0's array is `[1, 2, 0x8003]` (`An`, `unknown`, `building.`).
Because `$136FC` skips array[0], the game renders it as
`unknown building. ` — the `An` is dropped. The fans' transcription
(§4) has `An unknown building.`; whether the game really shows the
dropped article on screen, or some other path restores it, needs live
observation (see #020). Every other record's array[0] is the ` ` token,
so nothing else is lost. This is most likely a genuine 1992 off-by-one
in `$136FC`'s `d4 = 1` initialisation (or in the record-0 array, which
is missing its leading space token).

### Caller post-processing (`0x32EC4`)

After `$13654` returns, the caller copies the expanded buffer byte by
byte into a second buffer, treating `&` (`0x26`) as a **string
separator**: the byte before an `&` terminates the current string (the
destination is pre-zeroed, so the skipped slot leaves a NUL) and the
next string starts after it. No dictionary word contains `&`, so the
`&` must come from the type-0/type-1 paths or from a different table's
expansions. Open question, not needed for `$DDBD8`.

## 2. The `$DD5C` LZSS decompressor (story / title text)

`$DD5C` (0xDD5C–0xDE00) is a general LZSS decompressor, also used for
tile/map data (the `$96120` type-1 records). Format, re-implemented in
`tools/extract_text.py` and verified by decoding clean English:

- Input starts with a 32-bit **little-endian** decompressed length.
- Then mask bytes; per mask bit (LSB first), `1` = literal byte,
  `0` = 2-byte back-reference: **12-bit offset** = first byte |
  ((second byte & 0xF0) << 4), **length** = (second byte & 0x0F) + 3
  (the `dbra` loop runs one extra iteration past the `nibble + 2`
  loaded into `d5`).
- 4 KB ring buffer at `$FF0EAC`, **pre-filled with spaces (0x20)**;
  write position starts at `0xFEE`.

Four text streams found by scanning (all decode to clean English):

| Offset | Decompressed | Contents |
|---|---|---|
| `0x0A66E6` | 2,105 bytes | "From the Book of Nexus: Before Nexus, we lived in darkness. The sun shone as brightly as ever…" (story intro) |
| `0x0B3D40` | 1,810 bytes | "From the Book of Buc: So it was that the victorious Sorcerer Buc, of the Academy of the Mind, did defeat the evil Void…" |
| `0x0B6221` | 1,590 bytes | Title screen: "Rings of Power / A Fantasy Adventure by / Naughty Dog, Inc. / Published by / Electronic Arts / Produced by / Christopher Erhardt / Naughty Dog Team: Jason Rubin, Andy Gavin, Vijay Pande, Alexander Hinds…" |
| `0x0B83A1` | 1,188 bytes | Bestiary/class text ("Here are but some of the beings you will encounter: The Red Priests are the servants of Nexus…") — `$96120` rec 61, found in #005 (the original scan missed it: its first literals include a 0xF1 control byte, which the old all-printable quick filter rejected; fixed 2026-11-09) |

The decompressed streams contain embedded non-text bytes: `\x00` separators
and sequences like `( (( #$%&(()*+((/<=>` (probably icon/formatting
control codes for the text renderer). Their meaning is unknown — #020.

Note the earlier "strided/interleaved" description of this text (8-char
chunks separated by `0xFF` bytes) is explained: `0xFF` mask bytes mean
8 literal bytes, so the compressed stream *looks* like 8-char chunks
separated by `0xFF`. It is `$DD5C` output, not a separate striding scheme.

## 3. Spaced UI / message strings (plain ASCII)

NUL-terminated plain ASCII, no encoding. Verified locations:

- `0x01215A` — Void death message (format string with a `\x00`
  placeholder for the seconds count): `By a cruel twist of fate, Void
  has found your party and exterminated you in a mere \x00 seconds.
  There was nothing you could do. Please try again with a saved game.`
- `0x015BB8` — menu words; `Continue` at `0x15BE1`.
- `0x023934` — debug format `N^NuSp:%i Dir:%i Ac:%i St:%i Dr:%i`.
- `0x02752A` — `Help Off`, `Diags On/Off` at `0x2752A`/`0x27548`.
- `0x02937D–0x029767` — XP/gold/shop/spell-effect messages, e.g.
  `Sorry you don't have enough gold to buy that.` (`0x29653`),
  `Rod of Creation` (`0x29767`).
- `0x01B324` — credits block, plain spaced ASCII (`LICENSED BY SEGA`…).

## 4. Ground-truth validation (fan-site corpus)

`docs/research/rings-of-power-ru/txt/english-and-russian.txt` (UTF-8,
from `english-and-russian.doc`) is a 2009–2010 Russian fan site's
transcription of the game's actual strings (9,948 words; the site's
translation never shipped, so these are transcriptions, not ROM data).
Full scrape report: `docs/research/rings-of-power-ru/SCRAPE-REPORT.md`.
A 3,217-word EN→RU glossary sits alongside it
(`txt/4translate.txt` — geography, the 6 Disciplines, spells
STUN/CLUE/DISPERSE/MIRAGE, races/classes, items, interface).

Validation (run by `tools/extract_text.py`, result in `inventory.json`):
**647/649 (99.7%) of the corpus's English sentences appear verbatim in
the rendered `$DDBD8` records** (after normalising whitespace,
`--` → `-`, and ellipsis runs, which are transcription artifacts —
the ROM uses `...`, the doc typed `.....`). The 2 misses:

1. `An unknown building.` — the record-0 `An` quirk (§1).
2. `--- I regret that Thalmus' death has thrown us into such
   disarray.` — the words (`regret`, `thrown`, `disarray`) are all in
   the dictionary (blob offsets near `0xD90C8`), but the sentence is in
   no `$DDBD8` record. It belongs to an undecoded dialogue bank
   (the `$B8A32` table does not parse as `$13654` records — its layout
   is different; `$96120` is all type-1 binary). **Gap: NPC dialogue
   outside `$DDBD8` is not yet decoded** — #020's territory.

Four bare `<NA>` records (102, 112, 113, 131) also appear in the corpus
verbatim (`<NA> <NA> <NA> <NA>` before the innkeeper line), confirming
`<NA>` is a real dictionary word (index 463) that the game can display.

## 5. The Russian fan translation (independent confirmation)

`romhacking.ru` — "Rings of Power [ru] + 3 мода" 1.0, 2012-06-14, by
**bybyc9lc9l** (editor Dizzy), 59.8 KB patch, changes text + graphics,
5,809 downloads. Pages:
https://romhacking.ru/load/rings_of_power_ru_3_moda/6-1-0-221 and
https://romhacking.ru/news/rusifikacija_rings_of_power_smd/2012-06-15-1729

The author writes (translated): he sped the game up by "changing the
text input system from dictionary-based to compressed blocks" — an
independent statement that the original system is dictionary-based.
The patch file (`Rings of Power [ru].ips`, 104,864 bytes, 1,549 records,
108,252 patched bytes) was downloaded and diffed against the original
(no translated text copied into this repo). What the diff proves about
the original system:

- The `$136FC` offset-table base is patched at `0x1378C` and `0x1379C`
  (`$DC0C2` → `$D6F30`), confirming `$DC0C2` is the dictionary offset
  table and `$136FC` is the word expander.
- The old blob area (`0xD6EC0` onward) is replaced by the new system:
  a 32-bit pointer table at `$D7030` (19 block pointers, ending
  `$FFFFFFFF`), a u16 offset table at `$D7170`, and compressed text
  blocks at `$D72A0`, `$D7C00`, `$D8300`, `$D9000`, `$DA000`, `$DB100`,
  `$DBF00`, `$DCD40`, `$DDB60`, … (read by a new routine at `$D6F50`:
  block = id >> 6, string = id & 63, strings `0xFF`-terminated; bytes
  `< 0x20` are dictionary references via `$D7170`/`$D71B0`, bytes
  `>= 0x80` expand to 2-byte sequences via `$D7080`, ASCII passes
  through).
- New VDP font-upload routines at `$FD0D0`, `$1AA70`, `$E8C70`
  (longword tables terminated by the `$C0D0E0F0` sentinel, written to
  VRAM via `$C00004`/`$C00000`), called from patched sites
  (`0x12D1E` → `jsr $FD0D0`, `0x12D5A` → `jsr $1AA70`,
  `0x12DE2` → `jsr $E8C70`). The Russian font is drawn by remapping
  ASCII codes to Cyrillic glyphs (e.g. the Void message at `0x1215E`
  is re-encoded, `0x12125` `0x8E` → `0x83` — likely the text-speed
  delay).
- The runtime checksum is **neutralised**, not fixed: `0xFD09C`
  `bne` (`6602`) → `nop` (`4E71`), so the compare runs but the
  mismatch branch never fires. The runtime immediate at `0xFD098`
  is left at the old value `0x8F33608C` (the patched ROM fails
  `verify-all` on the runtime sum — by design, since the check is
  dead). The header checksum *is* fixed (`0x8B9F` → `0x33CA`).
- The patch also ships 3 mods in the same RAR (not studied beyond
  listing): fast level growth + immortality, infinite provisions/money,
  and a joke "shot mod" (ignored); plus a remove-modifications patch
  and `Kommentarii.txt` (CP1251; "text translation 100%, text output
  system changed, game runs faster; graphics translation 100%").

For #019 (record only): a commenter on the page notes the native Serial
EEPROM save is inconvenient — flash carts and some emulators don't
support it — and says the game needs its save reworked to common SRAM.
For #021 (record only): a user reports turning music off in-game
doesn't stick — it auto-enables on location/screen change.

## 6. Same-length replacement test (proven end to end)

- Patch a copy of the ROM (never the original): `Continue` at
  `0x15BE1` (8 bytes) → `Resumed ` (8 bytes, same length).
- `tools/checksum.py fix-all` → header `0x8B9F` → `0xDDAD`,
  runtime `0x8F33608C` → `0x4B464D80`; `verify-all` passes both.
  Exactly 14 bytes differ from the original: 8 text + 2 header
  checksum + 4 runtime immediate.
- Boot in BlastEm 0.6.3.4 (Xvfb + `SDL_AUDIODRIVER=dummy`): the patched
  ROM passes the runtime checksum and boots — Naughty Dog logo, title
  screen (`RINGS of POWER`), then (after Start) the "From the Book of
  Nexus" story page, which renders the `$DD5C` text decoded in §2
  verbatim on screen ("Before Nexus, we lived in darkness. The sun
  shone as brightly as ever…") — a live confirmation of the decompressor.
  A checksum failure hangs at `0xFD0CA` before any display, so any
  rendered frame proves the check passed. Screenshot evidence:
  `disasm/text/boot-test-patched.png` (Naughty Dog logo). The test was
  first run before a VM restart (which wiped `/tmp`) and then fully
  re-run on the fresh VM with identical results (same checksums
  `0xDDAD` / `0x4B464D80`, same boot sequence). Note: BlastEm shows a
  "Failed to set vsync to off" modal on Xvfb at startup — dismiss the
  `BlastEm Info` window (Return key to that window) to proceed.
- The changed string is in the ROM and reachable (menu word `Continue`);
  the Start/Continue menu itself was not displayed in this test — after
  the title screen, Start advances the story intro (the load menu
  likely needs a save to exist). The acceptance's "at least boots to
  gameplay" bar is met; showing `Resumed ` on screen is a small
  follow-up for #022 (it would need a save file present).

## 7. What remains unknown (for later issues)

- Record 0's dropped `An`: display bug or another path? Needs live
  observation (#020).
- The `&` string separator in `0x32EC4`'s post-processing: no dictionary
  word contains `&`; its source is unknown.
- `$B8A32` (caller `0x11AFE`): does not parse as `$13654` records —
  different layout or different routine; its text (incl. the Thalmus
  line) is undecoded.
- Control codes in the `$DD5C` text streams (`\x00` separators,
  `( (( #$%&(()*+((/<=>` sequences): icon/formatting codes, meaning
  unknown (#020).
- `FF 6F` at `0x0DC0C0–0x0DC0C1` between blob and offset table.
- Font tile data / glyph encoding: not decoded (the Russian patch's
  font uploads at `$FD740+` show where new glyphs go, but the original
  font table is #005/#016 work).
- The `$DD5C` streams' exact callers (which code calls the decompressor
  for the story/title text) — #017/#020.
