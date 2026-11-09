# #030 — Audio spec (tribute)

Status 2026-11-09: **spec complete** from #018's map
(`docs/sound.md`) + the music-off patch analysis; playback
implementation waits on #023 (and uses exported audio, not Z80
emulation — the remake needs the same audible result, not the
same driver).

## Track list (two sources, honestly labelled)

- **ROM-verified:** the Music menu list at `0xCD208` — indices
  0–17: Rings, Wilds, Seas, TnFinD, Death, Quest, Victry, Combat,
  House, Inside, Castle, Guilds, Sorcer, Knight, Archer, Necro,
  Conjur; index 18 = Quiet. Dispatch `$173EC` via table `0x17546`.
- **Fan-observed:** rings-of-power.ru's 17 named MP3s (Main theme,
  Wizards, Knights, Archers, Sorceresses, Necromancers, Enchanters
  = map theme, Battle, Castle, Death, Nexus, Quest, At sea,
  Someone's home, Tavern, Victory, On the street).
- The name↔index mapping is **a hypothesis, not verified** (see
  `docs/sound.md` §4): implement tracks by ROM index; attach fan
  names as display metadata only where they plainly align
  (Rings/Death/Quest/Victry/Combat/Castle/Guilds).

## Per-location playback (verified behaviour to reproduce)

- Location changes request the location's song via `$173BC`;
  `$32D0E` picks 17 when leader `+0x06` ∈ {2,3}, else 2, for its
  call path; the world tick's arrival branch also re-requests via
  `$32D0E → $173BC` (#020). Model this as: every location has a
  song index; entering requests it; requesting the current song
  is a no-op (except the watchdog semantics below).
- The original's 8-frame watchdog restarts a finished song —
  in the tribute this is simply "loop the location track".

## Quiet — the deliberate fix (acceptance item 3)

Quiet must **stop playback immediately and stay off across
location changes, in BOTH combat/presentation modes**. The
original bug (Quiet = no-op index 18; stop routine `$EB7C8` dead;
no off-flag anywhere) must NOT be reproduced — this is the one
place the tribute intentionally diverges from classic behaviour,
documented in `patches/music-off/README.md` and mirrored by the
ROM patch. Implement as a real `music_enabled` flag checked by
every song request (the patch's Hook-A/Hook-B choke-point design
is the model).

## SFX list (decision from #018 evidence)

Trigger via the tribute equivalent of `$17586(code)`: combat hit
codes from `$3B1EE`'s apply block (`0x1A`/9/`0x13` by selector),
death `0x5B`, level-up jingle = song-dispatch (8). Until the Z80
driver is disassembled (#018 remaining work), SFX are
placeholders keyed by these codes — the code→sound mapping table
ships in `tribute/audio/` so the real sounds drop in without
call-site changes.
