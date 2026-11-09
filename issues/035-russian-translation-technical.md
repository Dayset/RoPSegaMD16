# Issue #035 — Russian 2012 translation: technical notes

**Milestone:** Research
**Epic 6** (Research & history)
**Status:** open

## Goal
Document what the 2012 Russian fan translation ("Rings of Power
[ru] + 3 мода 1.0", romhacking.ru, 2012-06-14, by bybyc9lc9l,
editor Dizzy) reveals about the game's internals — from its patch
and its description, not from its text. It changed the text system,
which is exactly the kind of thing #004/#009 need to know about.

## Acceptance
- [ ] The translation's own change list summarised (text + graphics
  changes, gender splits, faster text output, redone fonts,
  archer-randomness experiment removed)
- [ ] Its technical approach documented from the patch diff: it
  repoints the `$136FC` table base `$DC0C2`→`$D6F30`, adds a pointer
  table `$D7030` + compressed blocks + a new reader `$D6F50`, font
  uploads `$FD0D0`/`$1AA70`/`$E8C70`, and NOPs the runtime checksum
  at `0xFD09C` (verify each claim against the patch, don't trust
  the description alone)
- [ ] Its 3 mods described (what each does, in one line each)
- [ ] The user comment about the music-off bug recorded (it is the
  same bug our music-off patch fixes) and the EEPROM→SRAM comment
  recorded (for #019/#022)

## Notes
- This is a research/diffing job, not a translation job. Do not copy
  the patch's translated text into this repo — describe the mechanism.
- The key hint this patch gave #004: the author changed the text
  system FROM dictionary-based TO compressed blocks, which is what
  cracked the dictionary reading. Say so in the issue.
- Download the patch (59.8 KB, 5,809 downloads as of 2026-11-09)
  only to diff it; keep it out of the repo (git-ignored, like the ROM).

## Depends on
#004 (done — the dictionary reading this patch illuminates).
Start now.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/research/russian-translation-2012.md — technical notes from the patch-diff evidence recorded in #004 (PROGRESS.md): repoint $DC0C2->$D6F30, new table $D7030 + compressed blocks + reader $D6F50, font uploads $FD0D0/$1AA70/$E8C70, checksum NOP at 0xFD09C, and why that cracked the dictionary reading; the change list summarised from the issue; both user comments (music-off bug, EEPROM->SRAM) recorded with their repo cross-refs.
- **Acceptance:** MET: technical approach (diff-verified in #004) + the dictionary hint + comments. PARTIAL: only one of the '3 mods' is identifiable from repo evidence (archer-randomness removal); the other mods' one-liners need the romhacking.ru release page read — owed, not guessed. The patch was not re-downloaded this session (by design it stays out of the repo).

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation session)

- **romhacking.ru release page: NOT found.** Four searches run (Russian by-author/mod query, English romhacking.net query, exact-title Russian query, site-targeted Russian query); the release page did not surface in any of them and was not read. Recorded honestly in docs/research/russian-translation-2012.md §3 — not claimed as checked.
- **New lead (unverified, not the release page):** NES Ninja's ROM listing (http://nesninja.com/game/sega/rings-of-power/roms) catalogues bybyc9lc9l variants named (4 Mods Hack), (Easy Hack), (Ero Hack), (Money Hack), plus a Hand of Nexus translated variant. This suggests the bundled mods circulate as Money / Easy / Ero hacks — consistent with the IA [RUS] "Money Hack" listing from #034 — but set file names are not the release page's mod list, the count disagrees ("+3 мода" vs a combined "4 Mods" variant), and none of the names obviously maps to the known archer-randomness removal. **The other two mods remain UNVERIFIED; do not treat the lead as the answer.**
- **Background:** Emu-Land interview with bybyc9lc9l confirms he took the game up on se1katsu's suggestion and rebuilt the dictionary text system into plain blocks with gender/number splits (matches the diff findings); no mod list there.
- **Still open:** read the romhacking.ru release page itself (or a Wayback capture of it) and record the 3 mods from its own text.
