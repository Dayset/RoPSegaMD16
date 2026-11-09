# Project overview — Rings of Power (Mega Drive) decompile & mod

Goal in one line: **take the 1 MB ROM apart into labelled, rebuildable
68000 assembly, put it back together byte-identical, prove it runs on an
emulator and on original hardware, and only then change a few things —
inside the hardware's limits.**

Repo: https://github.com/Dayset/RoPSegaMD16
Status: M1 done (toolchain + first disassembly). See `PROGRESS.md`.
Confidence key used everywhere here: **verified** = checked against the
ROM/code with a tool run; **hardware** = a fact about the Mega Drive
itself, not about this game; **unknown** = not yet proven, filed as a task.

## The bigger goal — tribute remake (Epic 5, milestone M7)

The disassembly is not the end point. The project's goal (Dayset,
2026-11-09) is to **recreate the same environment with an open-source
custom 3D engine — a tribute project** — in the **Esenthel C++
Titan Engine** (full source: https://github.com/Esenthel/EsenthelEngine).
The RE work in this repo is the spec the remake implements: all the
routines and game logic, reimplemented in C++.

Two switches define the tribute: **classic (isometric) vs modern (3D)**
presentation of the same world and logic, and **old vs new combat** —
the broken/crutched original combat preserved as "classic", a fixed
combat as "new", switchable. Full design: `docs/tribute-remake.md`,
issues #023–#031. The ROM-rebuild contract below still stands: it is
how the RE is proven right, and the mod workflow (Epic 4) continues
in parallel — the remake does not replace it.

## The rebuild contract (Epic 1 — the spine)

Nothing counts as "decompiled" until this holds:

1. `tools/build.sh` assembles `disasm/` into a ROM.
2. That ROM is **byte-identical** to the original (except the two
   checksum fields, which are then fixed by `tools/checksum.py fix-all`).
3. It boots in BlastEm, passes the game's own runtime checksum, and
   reaches gameplay. Same ROM must also be valid for real hardware:
   correct header, TMSS "SEGA" write, no reliance on emulator quirks.
4. Any mod is a **small, named diff** on top of that baseline, with its
   own patch file in `patches/` and an emulator smoke test.

What this rules out: editing the linear-sweep `disasm/rop.s` directly
(it mis-decodes data as code everywhere — density 0.70–1.00 even in
tile data), hand-patching bytes without fixing **both** checksums, and
any change that needs more ROM, RAM, VRAM, or CPU than the hardware has.

## Hardware limits every change must respect (hardware facts)

- CPU: Motorola 68000 @ 7.67 MHz. ROM: 1 MB flat (`0x000000–0x0FFFFF`),
  no bank switching seen in the header. Work RAM: 64 KB
  (`0xFF0000–0xFFFFFF`); stack starts at `0x00FFEC1E`.
- VDP: 64 KB VRAM, 128 bytes CRAM (64 colours, 4 palettes × 16), 4 bits
  per pixel tiles, two scroll planes (A/B) + window plane, 80 sprites
  max, 20 sprites per scanline, 320×224 (or 256×224) display.
  All VDP access goes through `$C00000` (data) / `$C00004` (control);
  the game references `$C00004` 103× in the sweep, `$C00000` 18×.
- DMA: VDP DMA via the control port; VRAM writes must fit in blanking
  time or they tear — VBlank work belongs in the VBlank handler.
- Sound: Z80 co-processor, bus control at `$A11100` (referenced 28×);
  the 68000 must request/release the bus before touching Z80 RAM.
- No fault tolerance in this game: see "Weak points" below.
- ROM budget: the last 12,084 bytes are `0xFF` padding
  (`0x0FD0CC–0x0FFFFF`) — that is the only free space inside the
  current 1 MB image. Anything bigger needs a bigger ROM (new header
  end address, new checksums) or freeing space elsewhere.

## Epics

### Epic 1 — Rebuildable ROM
Decompile → recompile byte-identical → boot. Issues #001, #002 (done),
#009, #011, #012, #013, #014.
The spine everything else hangs off. No mod work starts before the
rebuild gate passes, or patches cannot be maintained.

### Epic 2 — Game structure & logic
How the game actually works: entry, main loop, state machine, save,
stats, combat, spells. Issues #003, #007, #008, #019, #020, #021.
Output is a structure map with weak/strong points and a logic-flaw
audit — each claim cited to an address, not asserted from a feeling.

### Epic 3 — Graphics & audio pipeline
How pictures and sound get to the screen/speakers: VDP setup, tile
maps, sprites, palettes, compression, Z80 driver. Issues #004, #005,
#006, #015, #016, #017, #018.
Output is a pipeline description plus decoded assets (first rendered
tileset, palette list, map sketch).

### Epic 4 — Mods
A few chosen changes, each as a patch + test. Issue #010 (milestone),
#022 (first mod). Target still TBD — Dayset picks.

### Epic 5 — Tribute remake (Esenthel / Titan Engine)
Recreate the same environment in a modern 3D engine: the RE docs as
spec, classic-isometric vs modern-3D presentation, old vs new combat,
switchable. Issues #023–#031, milestone M7. Design:
`docs/tribute-remake.md`.

### Epic 6 — Research & history
Fansites, translations, interviews, reception — the history chapter
and the reference database the RE work checks itself against. Issues
#032–#036. Junior-agent work: searching, scraping, summarising.

## Game structure — what is verified so far

Boot path (verified, `disasm/map.md`):
`0x200` TMSS check → "SEGA" write at `$A14000` → VDP register table
at `0x28E` → clear RAM/VRAM/CRAM → `jsr $FD07C` runtime checksum →
`jsr $4323C` save validation → wait VBlank → display on (`$8134`) →
joypad read (`$3AA`) → main game via `jmp $D25C` (dispatcher, #020).
Per-frame sound is driven from the VBlank handler via `jsr $EB772`.

Per-frame (verified, `0x1272` VBlank handler):
frame counter `$FF0010++`, vblank flag `$FF0016` cleared, Z80 bus
requested/released around joypad reads, buttons read from `$A10003`
(standard two-phase read), result debounced into a 16-entry ring
buffer at `$FF001C` (head `$FF001A`, tail `$FF001B`, current `$FF0018`,
3-frame hold counter `$FF0019`). HBlank handler (`0x1270`) is a
single `rte` — empty, unused.

Save validation (verified code, purpose inferred — #019):
`$4323C` clears `$FF0168`, calls `$42FC8` and `$DCE2`, compares a
returned byte against `$E0`/`$B0`, byte-sums a 128-byte buffer at
`$FF016A` with NOT/swap checks, and sets `$FF0168` to 0, 1, or −1.
It smells like cartridge save/RAM validation; what `$DCE2` reads
and whether the game uses SRAM, EEPROM, or password saves is unknown.

Known code regions (verified/likely): entry + handlers `0x200–0x12FF`,
main code `0x1300–0x43FFF` (208 KB, includes UI strings and the
`$4323C` routine), mixed code/data `0xE0000–0xFBFFF`, checksum tail
`0xFC000–0xFD0CB`. Compressed/high-entropy blocks `0x44000–0x5FFFF`
and `0x94000–0xCBFFF` and tile data `0x60000–0x93FFF` are provisional.

## Strong points (verified)

- **Runtime checksum self-test is genuinely robust.** `0xFD07C` sums
  the ROM in 32-bit words and hangs forever (`bra $FD0CA`) on
  mismatch. It is the single biggest obstacle to modding — and the
  reason `fix-all` exists. Any mod that forgets it fails at boot
  with a blank screen.
- **VBlank input handling is careful.** Debounced, queued joypad
  input with a ring buffer instead of polling raw buttons in game
  code; Z80 bus discipline around the reads.
- **Startup is textbook-clean.** TMSS, VDP table, RAM/VRAM clears,
  then game code — no shortcuts that would break on real hardware.

## Weak points (verified code, impact to be measured)

- **No fault handlers at all.** Every exception vector except reset,
  HBlank, and VBlank is `0x00000000` — a bus error, illegal
  instruction, or divide-by-zero jumps to address 0. One bad pointer
  in a mod = instant crash with no recovery.
- **HBlank is empty.** No raster effects, no mid-frame palette/VDP
  changes — the game leaves a whole timing tool unused. (Also an
  opportunity: a mod that needs one must write the handler from
  scratch and prove it fits in HBlank time.)
- **Save validation looks weak.** Single-byte sums with NOT/swap
  checks over 128 bytes, magic-byte compares (`$E0`/`$B0`) — this
  is a presence/format check, not a real integrity check. To be
  confirmed in #019 before anyone claims saves can be forged or
  corrupted by a mod.
- **Text is packed, not plain.** The 21 KB dialogue blob
  (`0x0D6EBA–0x0DC0C0`) is tokenised/concatenated words; the title
  and story text are strided/interleaved. Dialogue edits are not
  a search-and-replace job — #004 has to crack the encoding first.

## Logic flaws — audit list (answered in #021, see `docs/logic-audit.md`)

These were questions, not findings. #021 answered each with an address,
a trace, and (where claimed) a harness reproduction:

1. Does the save checksum actually catch a corrupted save, or does
   it accept predictable byte patterns? — **WEAK, and the result is
   never used.** `$4323C`: 1-byte sum + complement over 126 bytes;
   any 126 payload bytes + 2 recomputed check bytes pass. `$FF0168`
   (the validation result) is never read by any code.
2. Is there an overflow in XP/gold/stats arithmetic (8/16-bit
   counters wrapping at level or money caps)? — **YES, gold.**
   `$2C474` clamps with signed compares: any gold+amount in
   (32767, 65535] wraps negative and zeroes gold (reproduced:
   15000+17768 → 0; boundary 15000+17767 → 15000). Likely
   unreachable in normal play (max realistic single add ~4500).
   XP cannot overflow (cap 13000, small adds). **Negative damage
   heals:** `$3B1EE` has no damage clamp; atk 0 / def 31 / base 140 /
   mods 0/3 → −6 damage → target HP 100 → 106 (reproduced).
3. Does the 16-entry joypad queue drop inputs under fast mashing,
   and does the 3-frame debounce eat legitimate presses? — **Queue
   semantics proven** (`$1350`: FIFO, tail==head = empty → returns
   last value, wrap-around verified by harness). Whether mashing
   overflows the 16 entries is unmeasured in live play — open.
4. Combat/spell formulas: any divide-by-zero, unsigned underflow,
   or enemy-stat edge case (0 HP, 0 defence)? — **Divide-by-zero
   hazard proven** (`$1E3B0` divides by `$FF0E18[2]`, 0 in cold RAM;
   the queue capacity is initialised by `$1B5D6` in the live new-game
   flow, so it is safe in real play but fatal in a cold harness).
   No other divide-by-zero found in the combat/spell paths traced.
5. The Void death message ("a cruel twist of fate… exterminated
   you in a mere N seconds") — what triggers it, and is the timer
   reachable in normal play or only by a bug? — **Text located
   (0x1215A); trigger and timer NOT located** (no pointer to 0x1215A
   in ROM; reference mechanism unknown). Open.
6. Any unreachable code / dead routines left from development
   (the debug format string at `0x023934` and `Diags On/Off`
   at `0x02752A` suggest a debug mode — is it still reachable?). —
   **Debug mode IS reachable** (SYSTEM menu → Diags toggles `$FF0134`,
   persisted in the save; affects the D-pad decoder mapping).
   The debug format string at 0x23934 is **dead data** (no references
   in ROM). `$EB7C8` (stop-sound) is dead code (zero callers); the
   `$3A84C` damage-apply block is dead (only if max HP < 0).

## Graphics rendering pipeline — current description

Verified pieces + hardware-standard steps, in frame order. Steps
marked unknown are the #015–#017 work.

1. **Setup (verified):** VDP register table at `0x28E` written to
   `$C00004` at boot; a second register set written by `$A14`
   (`$8004, $8134, $8228, $8330, …`); display enabled with `$8134`
   after the first VBlank wait.
2. **Tile data (provisional):** `0x060000–0x093FFF` (208 KB) reads
   as 4-bpp tile patterns. Not yet decoded to images (#016).
3. **Compressed assets (unknown):** `0x044000–0x05FFFF` and
   `0x094000–0x0CBFFF` (336 KB total), entropy 7.0–7.6 — the usual
   Genesis codecs to test are Nemesis, Kosinski, and Enigma (#017).
   Which block is graphics vs maps is unknown.
4. **Per-frame (verified, corrected #003):** VBlank handler bumps the frame counter
   and calls `$EB772` — that is the per-frame **sound/music tick only**,
   not a draw dispatch. Where the draw list lives (plane A/B updates, sprite
   table upload, palette changes, DMA scheduling) is unknown (#015).
5. **Planes/sprites/palette (unknown):** VRAM layout (name tables,
   pattern base, sprite table, scroll values), CRAM palette contents,
   and sprite usage are all #015/#016 work. Hardware caps apply:
   80 sprites, 20/line, 64 colours.
6. **Sound (partially known, #003):** sound tick `$EB772`, upload `$EB806`
   (1,576 bytes ROM `$EBB6E` → Z80 RAM), start-song `$EB88A`, music streamer
   `$EBA00`, command queue `$EBAC6` are traced. Music/SFX data format is
   still #018 work. The 68000 touches the Z80 via `$A11100` bus
   request/release.

## How a mod gets made (Epic 4 process)

1. Pick a target (#022) — small, one system, one address range.
2. Prove the rebuild gate still passes with no changes.
3. Implement in the labelled disassembly (preferred) or as a
   minimal binary patch with a written reason why asm was not
   possible.
4. `fix-all` both checksums; boot in BlastEm; play through the
   affected scene; check the hardware-limits list (ROM/RAM/VRAM/
   sprite/CPU budget) for the change.
5. Ship as `patches/<name>.ips` + description + before/after.
   Original ROM is never committed and never modified in place.

## Open questions (the project's unknowns, owned by issues)

- Where does real code end? (#011 — Ghidra recursive analysis)
- Which compression codec(s)? (#017)
- How is dialogue tokenised? (#004)
- Save medium: serial EEPROM, Microwire-style via `$200000` (#003) — chip
  identity (93C46 family suspected, unconfirmed) and 128-byte buffer layout
  still #019.
- What is the main loop / state machine past the `$D25C` dispatcher? (#020)
- `$42FC8` = EEPROM enable/init, `$43012` = EEPROM **read** (block),
  `$430F4` = EEPROM **write** (one byte), `$DCE2` = joypad port 2 read
  (#003, labels corrected #021 — they were swapped) — remaining save
  details still #019.
- Debug mode (`Diags On/Off`) **is** reachable (#021): SYSTEM menu →
  Diags toggles `$FF0134`, persisted in the save. The format string at
  `0x023934` is dead data (no references).
