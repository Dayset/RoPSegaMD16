# Issue #030 — Audio (music & SFX in the tribute)

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Give the tribute its sound: music and SFX from the original's audio
map, with the same off-switch behaviour the original should have
had (and the music-off patch implements on the ROM).

## Acceptance
- [ ] Track list implemented from #018's music/SFX map (17 named
  soundtrack tracks are known from the rings-of-power.ru research;
  verify against #018)
- [ ] Music plays per location as in the original (song dispatch via
  the `$173BC`/`$173EC` behaviour)
- [ ] A working music-off option (Quiet) that actually stays off
  across location changes — the original bug (Quiet = song 18, a
  no-op) must NOT be reproduced, in either mode; document this as
  a deliberate fix, not a classic behaviour
- [ ] SFX present for the main actions (decide the list in the issue
  from #018)

## Notes
- The original's audio path: per-frame sound tick `$EB772`,
  streamer `$EBA00`, command queue `$EBAC6`, Z80 driver (#018).
  The remake does not need to emulate the Z80 — it needs the same
  audible result.
- The music-off patch (`patches/music-off/README.md`) documents the
  bug precisely: no music-off flag existed; "Quiet" is song index
  18 whose dispatch entry is a clean no-op; the watchdog at
  0x21608 restarts the current song. Read it before designing the
  option.
- Owns: `tribute/audio/`. Do not touch the UI menu itself (#029
  owns the menu; this issue owns what the option does).

## Depends on
#018 (sound/Z80 driver + music/SFX map). Track-list prep from the
fan-site research can start now.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tribute/030-audio.md — spec from #018: ROM-verified 19-entry song list (0xCD208) vs the 17 fan track names kept as a labelled hypothesis mapping; per-location playback model from $173BC/$32D0E behaviour; Quiet implemented as a real music_enabled flag checked at every request (the deliberate fix, in BOTH modes); SFX code list from $17586 call sites.
- **Acceptance:** PARTIAL: spec complete; playback waits on #023 and on audio assets (the Z80 driver has never been disassembled — #018 partial — so SFX ship as code-keyed placeholders).

**Status after this session:** in progress — partial (see below). Not marked done.
