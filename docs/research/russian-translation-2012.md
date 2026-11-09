# Russian 2012 translation — technical notes (issue #035)

Status 2026-11-09 (agent session): written from the **patch-diff
evidence already recorded in this repo during #004** (PROGRESS.md
#004 entry) — i.e. the claims below were verified against the
patch by the #004 session, which is exactly the verification the
acceptance asks for; the patch itself was NOT re-downloaded in
this session (it must stay out of the repo, git-ignored like the
ROM) and no translated text is copied here — mechanism only.
Patch: "Rings of Power [ru] + 3 мода 1.0", romhacking.ru,
2012-06-14, by **bybyc9lc9l**, editor Dizzy; 59.8 KB; 5,809
downloads as of 2026-11-09 (issue file). Web corroboration this
session: the patch circulates as `Rings of Power UE [T+Rus
bybyc9lc9l]` (Internet Archive [RUS] collection listing) and the
author's other bybyc9lc9l translations are widely catalogued.

## 1. The translation's own change list (acceptance item 1)

Per the issue file (from the patch's description): translated
text + graphics changes; **gender splits** (Russian grammar needs
masculine/feminine variants the English system lacks); **faster
text output**; **redone fonts** (Cyrillic); the **archer-randomness
experiment removed**. (The description itself was not re-fetched
this session — recorded from the issue, flagged as description-
level, distinct from the diff-verified §2.)

## 2. Technical approach — from the patch diff (acceptance item 2, verified in #004)

- It **repoints the `$136FC` dictionary-table base**:
  `$DC0C2` → `$D6F30` (the dictionary offset table moves).
- It adds a **new pointer table at `$D7030`** plus **compressed
  blocks**, read by a **new reader routine at `$D6F50`** — i.e. it
  replaces the dictionary-based text system with compressed-block
  text for the translated strings.
- **Font uploads** hooked at `$FD0D0` / `$1AA70` / `$E8C70`
  (Cyrillic glyphs into the game's font path).
- It **NOPs the runtime checksum check at `0xFD09C`** (inside the
  `0xFD07C` self-test) instead of recomputing the expected sum —
  the pragmatic hacker's alternative to our `checksum.py fix-all`.
- **Why this cracked #004:** the author changed the text system
  FROM dictionary-based TO compressed blocks. That a translator
  *had* to replace the system was the key hint that the original
  is dictionary-based — which is how the 3,466-word dictionary
  reading (`$136FC`, blob `0x0D6EBA–0x0DC0C0` + table `0x0DC0C2`)
  was found and then validated 647/649 against the fan corpus.

## 3. The 3 mods (acceptance item 3 — PARTIAL)

The patch ships as "[ru] + 3 мода" (translation + 3 mods). The
repo's recorded evidence names only one mod-adjacent change with
confidence: the **archer-randomness experiment removal** (§1).
The other mods are **not described in any committed repo file**,
and their one-line descriptions require reading the romhacking.ru
release page — **owed** (browser read of that page; not fetched
this session). Do not guess them here.

## 4. User comments (acceptance item 4)

- **Music-off bug comment:** recorded in `patches/music-off/README.md`
  — the player report that opens that file ("if you turn the music
  off in the game, when the location/screen changes it automatically
  turns back on") is the same bug class the translation's users
  reported; our patch README is the canonical record and the fix.
  (The comment text lives there in Russian + translation; not
  duplicated here.)
- **EEPROM→SRAM comment:** commenters on the translation asked
  for the save system to be reworked from EEPROM to SRAM (issue
  #031 notes this; `docs/save-validation.md` §3 confirms EEPROM
  is the shipped medium — which is what makes the request
  intelligible). Relevance: #019 (medium decided: serial EEPROM)
  and #031 (tribute does NOT reproduce the weak validation; an
  SRAM-style rework on ROM would be a #022-class mod).
