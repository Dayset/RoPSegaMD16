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
