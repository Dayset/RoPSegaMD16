# Sound — Z80 driver + music/SFX map (issue #018)

Written 2026-11-09 (agent session) from verified repo evidence:
`docs/architecture.md` (#003 sound sections), `docs/overview.md`,
`patches/music-off/README.md` (the deepest sound trace in the repo),
`docs/research/rings-of-power-ru/SCRAPE-REPORT.md` (track list).
The Z80 driver binary itself has **not** been disassembled (tooling
gap, §5) — everything below is the 68000-side map, which is traced.

## 1. Driver location + entry — verified (68000 side)

- The Z80 driver is **uploaded, not resident in a fixed ROM bank**:
  `$EB806` copies **1,576 bytes (`$1576`) from ROM `$EBB6E` to Z80
  RAM `$A00000`** via the byte-copy loop `$EB920`, under Z80
  reset/bus control (`$A11100`/`$A11200`). Callers: `$119E` (boot),
  `$EB88A` (start-song), `0xEBB10`.
- At boot (`0x200` init) the Z80 first gets a 38-byte stub: RAM-clear
  + `di; im 1; ld (hl),$E9; jp (hl)` — a parked jump-to-self loop
  until `$EB806` installs the real driver.
- Driver entry points on the 68000 side: `$EB806` upload/restart,
  `$EB88A` start-song, `$EB7C8` stop-sound (dead code in the
  original — 0 callers), `$EB92A` Z80-access prologue
  (SR=`$2700` + bus request + `a0=$A00000`).

## 2. Per-frame operation — verified

- VBlank `0x1272` calls **`$EB772` (sound tick)** every frame — its
  only call site (`0x12F2`).
- `$EB772`: tempo tick — `$FF0234 += $100` (NTSC) or `+= $133` when
  the PAL flag `$FF0222` is set; low byte written to Z80 RAM
  `$A000E6`. Then `jsr $EBAC6` (command queue). Every 16 frames,
  `jsr $EBA00` (music streamer).
- `$EBA00` streamer: active only while `$FF021E` (sound-on) = 1;
  polls the driver request byte at Z80 `$A0000B`; copies 255-byte
  chunks from `$FF0224` to Z80 `$A01600` via `$EB922`; source wraps
  `$FF0230` (song end) → `$FF022C` (song start) — the song loops
  inside the streamer.
- `$EBA7E` load-song: sets `$FF0228=$A01600`, `$FF021F=$16`, copies
  `$3FF` bytes into the Z80's `$A000DA` region.
- Watchdog: `0x21608–0x2161E` (in `$2155E`, every 8 frames):
  `jsr $EB9C4; tst; bne skip; jsr $173EC($FF012E)` — restarts the
  current song whenever the driver reports done. `$EB9C4` returns 0
  iff `$FF021E==0` or the Z80 request byte is 0.

## 3. How the 68000 triggers music/SFX — verified

- **Song request path:** `$173BC(song_index)` (location code, 15
  call sites) → `$173EC` dispatch (17 direct call sites) → jump
  table at `0x17546` (indices < 21) → per-song block → `$EB88A`
  (sets `$FF021E=1`, writes `$0D`/`$00` to Z80 `$A0000B`/`$A0000A`).
  Current song in `$FF012E` (`$FFFF` = none at boot).
- **The song list** (Music menu text at `0xCD208`, indices 0–18):
  Quiet(18 — a **no-op dispatch entry**, table word `$0002` →
  `0x17582` `unlk;rts`), then Rings, Wilds, Seas, TnFinD, Death,
  Quest, Victry, Combat, House, Inside, Castle, Guilds, Sorcer,
  Knight, Archer, Necro, Conjur (indices 0–17). Full bug analysis:
  `patches/music-off/README.md`.
- **Location songs:** `$32D0E` song picker returns 17 if the leader
  struct `+0x06` is 2 or 3, else 2, passed to `$173BC` (#020).
- **Command queue:** `$EBAC6` dispatches two slots
  `$FF0236`/`$FF023A` to handlers in the `$EBB04`/`$EBBFE` region —
  **those two handlers are not yet traced** (open, from #003).
- **SFX:** `$17586(code, …)` is the effect trigger seen across the
  codebase (combat SFX `0x1A`/9/`0x13` in `$3B1EE`'s apply block,
  death SFX `0x5B` in `$37B82`, level-up jingle `$173EC(8)`).
  SFX set `$FF021E=1` but cannot restart music (request byte stays
  0 after a stop) — proven in the music-off analysis.

## 4. Track list (fan-site, for cross-check) — player-observed

rings-of-power.ru lists **17 named soundtrack tracks** (MP3):
Main theme (Rings theme), Wizards, Knights, Archers, Sorceresses,
Necromancers, Enchanters (also the map theme), Battle, Castle,
Death, Nexus, Quest, At sea, Someone's home, Tavern, Victory, On
the street. One commenter names a "Guilds" track not in that list —
the ROM menu list above *does* contain "Guilds", so the fan list
is incomplete or renames it. Mapping fan names ↔ ROM song indices
0–17 is **not proven** (names plausibly align: Rings/Death/Quest/
Victry/Combat/Castle… but "TnFinD", "Wilds", "Seas" have no fan-list
counterpart). Treat as a hypothesis table for #030.

## 5. Tooling gap (the issue's own warning, confirmed)

The driver code executes in **Z80 address space**; Ghidra's 68000
project does not cover it. Nobody in this repo has disassembled the
1,576 uploaded bytes as Z80 code. Remaining #018 work (owner's
machine): extract ROM `$EBB6E–$EC1E4` (1,576 bytes) and disassemble
as Z80 (Ghidra `z80:BE:16:default` or equivalent), identify the
YM2612/PSG register-write loops, and locate the SFX table the
`$EBB04`/`$EBBFE` handlers consume. **Blocked in this VM: no ROM.**
