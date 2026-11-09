# Architecture — entry, vectors, interrupts (issue #003, 2026-11-09)

Status: **verified** — every claim below was checked with a tool run
(Capstone range disassembly, Ghidra headless call graph, BlastEm
address-log run). Confidence is marked per section. Ghidra guesses are
not presented as facts; the one place Ghidra was silent is noted.

- CPU: Motorola 68000. Entry point `0x200` (reset vector at `0x004`).
- RAM: `0xFF0000–0xFFFFFF` (64 KB work RAM, per header).
- ROM: `0x000000–0x0FFFFF` (1 MB).
- Header checksum at `0x18E`, covers words `0x200` to end of ROM.
- Credits in ROM: Naughty Dog, design A. Gavin / J. Rubin / V. Pande,
  programming Andy Gavin / Vijay Pande, music Alexander Hinds.

## Vector table (0x000–0x0FF) — verified

All 64 vectors read from the ROM; only four longwords are non-zero.
Every other vector is `0x00000000` — including bus error (2), address
error (3), illegal instruction (4), divide by zero (5), CHK/TRAP/TRAPV
(6–7, 32–47), privilege violation (8), trace (9), and all level
interrupts except 4 and 6.

| Vector | Address | Target | Notes |
|---|---|---|---|
| 0 SSP | `0x000` | `0x00FFEC1E` | Initial stack pointer (top of 64 KB RAM, minus 0x1E) |
| 1 reset | `0x004` | `0x00000200` | Entry point |
| 28 level 4 (HBlank) | `0x070` | `0x00001270` | Single instruction: `rte` — empty handler |
| 30 level 6 (VBlank) | `0x078` | `0x00001272` | Real handler (see below) |

**Consequence: the game has no fault handlers.** A bus error, address
error, illegal instruction, or trap jumps to address `0x00000000` —
the vector table itself — and executes whatever the first bytes decode
to (`0x00FFEC1E` = `ori.b #0,d7`… then falls into the header). In
practice a fault is a hang, not a recovery. Any rebuild must keep the
zero vectors as-is; filling them in would change behaviour (and the
runtime checksum sum).

## Entry / reset path (0x200 → 0xD25C) — verified

BlastEm address log (10 s run, 2,487 unique addresses, first-hit
order) confirms the runtime flow: `200 → 2FA → 119E → D25C`, then
`D28E` and the sound upload `EB806`. Ghidra headless call graph
(436 functions, 1,434 edges) agrees: entry `FUN_00000200` calls
`$FD07C`, `$119E`, `$4323C`, `$3AA`, `$A14`, `$4E6`.

### 0x200 — TMSS check + table-driven hardware init

- `tst.l $A10008` / `tst.w $A1000C` — TMSS hardware check. If the
  version register reads back, the console has no TMSS and the
  `"SEGA"` write is skipped.
- `lea $28E(pc),a5` — the init table at `0x28E` is **data** (108 bytes),
  not code; the linear sweep in `disasm/rop.s` mis-decodes it. Setup:
  `d5=$8000, d6=$3FFF, d7=$0100`; `a0=$A00000` (Z80 RAM),
  `a1=$A11100` (Z80 bus request), `a2=$A11200` (Z80 reset),
  `a3=$C00000` (VDP data), `a4=$C00004` (VDP control).
- 24 VDP register bytes are written with `add.w d7` stepping the
  register number (boot table, register → value):
  R0=`$04`, R1=`$14`, R2=`$30` (Plane A `$C000`), R3=`$3C` (Window
  `$F000`), R4=`$07` (Plane B `$E000`), R5=`$6C` (sprite table
  `$D800`), R6=`$00`, R7=`$00`, R8/R9=`$00`, R10=`$FF`, R11=`$00`,
  R12=`$81` (H40, 320 px), R13=`$37` (H-scroll `$DC00`), R14=`$00`,
  R15=`$01`, R16=`$01` (planes 64×32), R17/R18=`$00`, R19/R20=`$FF`,
  R21/R22=`$00`, R23=`$80`.
  R1=`$14` means display **off** (bit 6 = 0), V-int **off** (bit 5 = 0),
  DMA on (bit 4 = 1). R0=`$04` has H-int enable (bit 4) = 0 — the
  HBlank handler is never fired (confirmed: BlastEm log, 0 hits on
  `0x1270` in 10 s).
- `"SEGA"` (`$53454741`) is written to `$A14000` via `$2F00(a1)` when
  the region byte at `-$10FF(a1)` (i.e. `$A10001`) has a non-zero low
  nibble. Without this write a TMSS console shows the red
  "produced by or under license" screen and halts — this is the
  trademark security check, not game code.
- RAM cleared via stack push (`a6=0`, `d6=$3FFF`, 64 KB).
  VDP DMA fill: R19/R20=`$FFFF`, R23=`$80` (fill mode), command
  `$40000080`, fill value `$0000` written once to VDP data.
  Then `long2=$81048F02` (packed R1=`$04` blank + R15=`$02` auto-inc 2),
  `long3=$C0000000` (CRAM write address 0) + 32 longs of 0 (CRAM clear,
  128 B), `long4=$40000010` (VSRAM write address 0) + 20 longs of 0
  (VSRAM clear, 80 B).
- 38-byte Z80 RAM upload: the first 12 bytes are a Z80 RAM-clear stub
  (`xor a; ld bc,$1FD9; ld de,$0027; ld hl,$0026; ld sp,hl; ld (hl),a;
  ldir`), then register-restore + `di; im 1; ld (hl),$E9; jp (hl)` —
  a parked Z80 that sits in a jump-to-self loop until the real sound
  driver is uploaded later by `$EB806`.
- PSG silenced with bytes `9F BF DF FF` to `$C00011`.
- Registers restored from zeroed RAM via `movem.l (a6),...` (a6 wraps
  to `$FF0000`); `SR=$2700` (all interrupts masked); `bra $2FA`.

### 0x2FA — checksum, save check, display on, attract loop

- `tst.w $C00004` (read VDP status), `jsr $FD07C` — the **runtime
  checksum self-test** (sums words `0x000000–0xFD07B`, expects
  `0x8F33608C`, hangs at `0xFD0CA` on mismatch; see `disasm/map.md`),
  `nop`, `SR=$2700`.
- `jsr $4323C` — serial-EEPROM / save validation (call-graph level,
  see below; full analysis is #019).
- `movea.l #$0,a7`, wait for VBlank bit 3 of `$C00004`,
  `move.w #$8134,$C00004` — R1=`$34`: display still **blank**
  (bit 6 = 0), V-int + DMA on (bits 5, 4 = 1).
- `bsr $3AA` (joypad read), `bsr $A14` (RAM clear + second VDP
  register set — different layout: Plane A `$A000`, Window `$C000`,
  Plane B `$A000`, sprite table `$DC00`, H-scroll `$2000`, R16=`$03`,
  R10=`$01` — and clears 64 KB VRAM + CRAM via `$AB2`), `bsr $3AA`
  again, clear `$FFC00E`/`$FFC010`, wait for DMA-busy bit 1 of
  `$C00004` to clear, `move.w #$8174,$C00004` — R1=`$74`: **display ON**
  (bit 6 = 1).
- Title/attract loop `0x35C–0x390`: wait VBlank, read joypad, exit the
  loop if any button is pressed; otherwise, if `$FFC000==0`, call
  `$4E6` (writes H-scroll values to VRAM `$2000` — the attract scroll
  animation — and sets `$FFC000=$FF` when its counter expires), loop.
- `bra $119E`.

### 0x119E — main init, then `jmp $D25C`

- `movea.l #$FFEC1E,a7` (restore the initial stack pointer), save the
  frame counter `d7=$FF0010`, clear 64 KB RAM, VDP registers
  `$8004/$8134/$8AFF`, copy `$240` bytes from ROM `$FCE3C` to RAM
  `$FF0000`, zero RAM `$FF0240–$FFC41D`, `$FF000C=$FFC41E`, write
  `"MANX"` (`$4D414E58`) at `$FFC422`, clear joypad state
  `$FF0018/$FF002C/$FF001A/$FF001B`, `$FF0019=3`, restore the frame
  counter.
- `jsr $EB806` — sound-driver upload (see below), `SR=$2000`
  (interrupts unmasked to level 0), `jmp $D25C`.

### 0xD25C — game-code dispatcher (not the main loop itself)

`$D25C` is a 50-byte routine (`link a6` … `unlk` / `rts`) that calls
seven routines in this order (Ghidra + Capstone agree on the set):
`$11E06`, `$14FB6`, `$1B5D6`, `$32D0E`, `$173BC`, `$D28E`, `$179B6`
(BlastEm log shows `D25C → 179B6 → D28E` among the first hits, so
`$179B6` runs before `$D28E` in practice). Its `rts` at `0xD28C` is
not reached in normal flow — the called routines contain the game's
continuing execution and never return to it. The main loop / state
machine lives below `$D28E` and is #020's work, not this issue's.

`$D28E` (1,876 bytes, 25 callees per Ghidra) is the big flag-driven
dispatcher: it tests state flags (`$FF00AC`, `$FF0030`, `$FF011E`,
`$FF0120`, `$FF0094`, `$FF0128`, `$FF0112`, …) and calls, among others,
`$26CCA(1)`, `$1BA26`, `$1B918`, `$1350` (the joypad-queue pop
routine), `$12B82`, `$12FE8`, and branches to `$D8BA` from three
sites (`0xD2EC`, `0xD2F8`, `0xD30A`). `$D8BA` indexes 52-byte
(`$34`) structs in tables at `$FF02B4`/`$FF02DB` via the index in
`$FF0120` and calls `$2A2CA` / `$26A8C`. What those structs are is
#020's question.

## Interrupt handlers — verified

### VBlank — 0x1272 (level 6), fully traced

Called every frame (BlastEm log: `1272` hit; `EB772` hit). Full trace
(Capstone `0x1272–0x134E`):

1. `move.w #0,$FF0016` (clear the vblank flag), `addq.l #1,$FF0010`
   (**frame counter++**), save d0–d2/a0.
2. Z80 bus request (`$A11100=$100`), two-phase joypad read from
   **port 1 only** (`$A10003`: write `$00`, delay loop, read, shift/mask;
   write `$40`, delay loop, read, `and $3F`, `or`, `not` — result in
   d0 with 1 = pressed), Z80 bus release. Port 2 is **not** read here.
3. `jsr $EB772` — the sound/music tick (see below).
4. Debounce / queue logic (after `0x12D0`):
   - If the button byte changed vs `$FF0018`: `$FF0018=d0`,
     `$FF0019=3` (3-frame debounce counter), restore, `rte` (`0x1312`).
   - If unchanged: `$FF0019--`; while it is non-zero, restore and
     `rte` (`0x134E`) — the same held byte is **not** re-queued.
   - When `$FF0019` reaches 0: push the byte into the 16-entry ring
     buffer `$FF001C` at head `$FF001A`, unless full (head+1 & `$F`
     == tail `$FF001B`); advance head; restore, `rte` (`0x1340`).
   So a held button re-queues once every 3 frames — this is the
   game's key-repeat. Three `rte` exits: `0x1312`, `0x1340`, `0x134E`.
5. `$1350` is a separate **polled pop** routine (`rts`, not `rte`,
   called from `$D28E`): returns the next queued byte into d0 and
   `$FF002C`, advancing tail `$FF001B`; if the queue is empty it
   returns the last value `$FF002C`. SR masked `$2700` during the
   pop, restored `$2000`.

### HBlank — 0x1270 (level 4), empty

Single instruction: `rte`. And it never fires: boot R0=`$04` leaves
the H-int enable bit (bit 4) at 0, and no later VDP setup in the entry
path sets it. BlastEm log: 0 hits on `0x1270` in a 10 s run (vs 1 hit
each on `0x1272`/`$EB772`). The handler exists only because the vector
table has to point somewhere.

### Level interrupts

No level 1/2/3/5/7 handlers exist — their vectors are zero. The only
interrupt sources the game uses are VBlank (level 6) and the
never-enabled HBlank (level 4).

## What $EB772 dispatches to — verified (sound tick, not graphics)

`$EB772` (`0xEB772–0xEB7C6`, `rts` at `0xEB7C6`) is the **per-frame
sound/music tick**, called only from the VBlank handler (single call
site `0x12F2`; Ghidra did not auto-create this function — see
"Ghidra note" below — the call is visible in the Capstone dump).

- Saves all registers. If `$FF0222` (PAL flag, set by `$EB806` from
  `$A10001` bit 6) is set, `$FF0234 += $33`; then always `+= $100`.
  The low byte of `$FF0234` is written to Z80 RAM `$A000E6` under
  Z80 bus request/release — a music **tempo tick**: +`$100`/frame on
  NTSC, +`$133` on PAL.
- `jsr $EBAC6` — sound **command-queue dispatcher**: two slots at
  `$FF0236`/`$FF023A`; a non-zero slot is cleared and its handler
  (`$EBB04` / `$EBBFE` region) is called.
- `$FF0220++`; every 16 frames (`& $F == 0`) `jsr $EBA00` — the
  **music streamer**: if `$FF021E` (sound on) is set, it checks the
  Z80 driver's request byte at `$A0000B`; when the driver wants the
  next chunk, it copies `$FF` bytes from `$FF0224` to the Z80's
  `$A01600` region via `$EB922`, wraps the source pointer to
  `$FF022C` at the end (`$FF0230`), and clamps the destination to
  `$A01600` at `$A01A00`.
- Restores registers, `rts`.

Related sound routines (call-graph level, all in `0xEB700–0xEBB00`):

- `$EB806` — sound-driver **upload**: reads `$A10001`, sets `$FF0222`
  from bit 6 (PAL); zeroes `$FF022C/$FF0236/$FF023A`; asserts Z80
  reset/bus, copies `$1576` bytes from ROM `$EBB6E` to Z80 RAM
  `$A00000` via `$EB920` (byte-copy loop), releases reset, delays
  `$1F4`, re-asserts reset. Called from `$119E` (`0x1260`), from
  `$EB88A` (`0xEB892`), and from `0xEBB10` (Ghidra xrefs).
- `$EB88A` — start-song: calls `$EB806`, sets `$FF022C`, calls
  `$EBA7E`, writes `$0D`/`$00` to Z80 RAM `$A0000B`/`$A0000A` as a
  sound command, sets `$FF021E=1`. (BlastEm log: `EB88A`/`EBA7E` hit
  late in the run — the title music starts.)
- `$EBA7E` — load song data: sets `$FF0228=$A01600`, `$FF021F=$16`,
  copies `$3FF` bytes into the Z80's `$A000DA` region.
- `$EB7C8` — stop-sound: clears `$FF021E`, calls `$EB92A` (SR=`$2700`
  + Z80 bus request + `a0=$A00000`), writes 0 to Z80 `$A0000B` /
  `$A0000A`, Z80 reset pulse, delay `$1C2`, release.
- `$EB92A` — Z80-access prologue (SR + bus request + `a0=$A00000`).

**Correction to `docs/overview.md`:** the overview says the
"per-frame update/draw dispatch lives [at $EB772]". That is wrong —
`$EB772` is sound-only. No graphics/draw dispatch happens in the
VBlank handler; the VBlank handler does frame counter + joypad +
sound tick only. (Overview fix itself is a one-line edit, left for
review — this file records the correction.)

## $4323C and its helpers — call-graph level (full analysis is #019)

`$4323C` (386 bytes) is called once from entry (`0x30C`; its only
call site) and calls `$42FC8`, `$DCE2`, `$43012`, `$430F4` (Ghidra).

- `$42FC8` — serial-EEPROM **enable/init**: sets `$FF014C=10`
  (retry limit), `$FF014E=0` (error count), a `$1964` delay loop,
  then 8× {write `$80` to `$200000`, NOPs, `jsr $42E34`}, then
  `jsr $42E76`.
- `$42E34` / `$42E76` — clock/idle sequences: write `$C0`/`$40`/`$00`
  (resp. `$00`/`$40`/`$C0`/`$80`) to `$200000` with NOP delays.
- `$42EBA` — shift **one bit out**: `lsl d0` → `roxr d1`, bit 6 of
  the `$200000` word is the clock (clear → write → set → write →
  clear → write). Data bit on D0, clock on D6.
- `$42F96` — shift **one bit in**: write `$80`, write `$C0`, read
  `$200000` → d1, write `$80`; the read bit comes back on D7
  (`asl.b d1` / `roxl d0`).
- `$43012` — EEPROM **write**: takes address/buffer args off the
  stack, stores them at `$FF0150–$FF015C`, clocks the command out via
  `$42EBA` ×8, reads an ACK bit via `$42F96`; on error `$FF014E++`
  and retries up to `$FF014C` (10).
- `$430F4` — EEPROM **read**: same bit-bang pattern (command out,
  ACK in), then reads bytes back through `$42EBA`/`$3DC2A`.
- So the save hardware is a **Microwire-style serial EEPROM**
  bit-banged through the cartridge `$200000` window (separate DI/DO/
  CLK lines: DI = D0, CLK = D6, DO = D7). Chip identity (93C46 family
  is the usual suspect) is **unknown** — #019 must confirm it.
  Corroboration: BlastEm auto-detected an EEPROM from the
  `$200000` access pattern and saved a **128-byte** `save.eeprom`
  (all `$FF` — erased state, the game read it at boot and found it
  blank), matching the 128-byte buffer at `$FF016A`. Note the ROM
  header declares **no backup RAM** (bytes `0x1B0–0x1BF` are spaces)
  — the EEPROM is only discoverable from the code, not the header.
- `$DCE2` — **joypad port 2 read** (shared utility, not
  save-specific): same two-phase pattern as `$3AA` on `$A10005`,
  returns the inverted button byte in d0. Ghidra xrefs: 8 call sites
  (`0x4324A`, `0x432A8`, `0x432FE`, `0x43316` inside `$4323C`;
  `0x11BC8`, `0x12420`, `0x16B10`, `0x12F58` in game code — e.g.
  `0x11BC8` stores the result to `$FF8646`, and `0x12420` compares
  `$FF8646` to `$FA`).
- `$4323C` itself: calls `$42FC8`, reads joypad 2 via `$DCE2`, and
  compares the byte to `$E0`. Decoded: `$E0` = **B+C+Start** held on
  pad 2; `$B0` (also compared at `0x432AE`/`0x43304`/`0x4331C`) =
  **A+C+Start** held on pad 2. If `$E0` is held at boot, `$FF0168=1`,
  the 128-byte buffer at `$FF016A` is zeroed and `$FF01E8=$FF`, then
  a fill loop runs via `$430F4` — i.e. a hidden pad-2 button
  combination forces a fresh/blank save. Otherwise the buffer's
  **byte-sum is validated** (126 bytes summed, NOT/swap variants
  checked, error count in d1; `d1==0` = valid) and `$4323C` returns
  `$F0` if either combo is held, else the raw pad-2 byte. BlastEm
  log shows the validation branches (`0x43316`, `0x4333A`,
  `0x4332E`, `0x432F6`, `0x432B6`) all execute on a clean boot.
  What the buffer holds (character data? which slots?) and what the
  return value means to callers is #019's work.

## Joypad read — $3AA (0x3AA–0x44A) — verified

Reads **both** ports with 10-iteration delay loops between the two
phases: port 1 (`$A10003`) → `$FFC00E`, port 2 (`$A10005`) →
`$FFC010`; returns the port-1 byte in d0 (port 2 in d1, saved in
`$FFC010`). Called from entry (`0x3AA` twice, either side of `$A14`)
and available as the polled read; the VBlank handler inlines only
the port-1 half.

## Ghidra note

Ghidra 11.4.2 auto-analysis (headless, `-noanalysis` on the existing
project, `DumpCalls.py` post-script — the flag is `-postScript`, not
`-script`, and scripts need the `@author/@description/@category`
header) produced 436 functions / 1,434 call edges, and confirms the
call sets above. It did **not** auto-create functions at the
interrupt entry points `0x1270` / `0x1272` or at `$EB772` — vector
targets have no call sites, so the analyser never discovered them;
the `jsr $EB772` at `0x12F2` is visible only in the Capstone linear
disassembly. Any future Ghidra work on interrupts must create those
functions manually. The call-graph dump is at `/tmp/ghidra_calls.txt`
(scratch, not in the repo).

## What remains unknown (for #011 / #019 / #020)

- **#011 (Ghidra recursive analysis):** function boundaries in
  `0x010000–0x043FFF` and `0x0E0000–0x0FBFFF` are still provisional;
  the linear sweep mis-decodes data as code. The 436-function graph
  is a start, not a map — and the interrupt handlers need manual
  function creation (see above).
- **#019 (save validation):** EEPROM chip identity; the `$FF016A`
  128-byte buffer's layout (what is stored where); the exact ACK/
  error semantics of `$43012`/`$430F4`; what `$4323C`'s return value
  means; whether the pad-2 `$E0`/`$B0` combos are a deliberate
  "clear save" feature or a side effect of the validation path.
- **#020 (main loop / state machine):** what `$D25C`'s seven callees
  each do; the `$D28E` flag dispatch and the `$FF02B4`/`$FF02DB`
  52-byte structs behind `$D8BA`; where the eternal main loop
  actually sits (the `rts` at `0xD28C` is not reached in normal flow).
- **#003 open ends, kept:** `$42E00` is a jump-table dispatcher on
  d0 (branches to `$40DD4`/`$3E384`/`$3E38E`/`$40CDC`/`$40E22`/
  `$40EDC`/`$41EB4`/`$3E418`) — purpose unknown; `$EBB04`/`$EBBFE`
  (sound-command handlers called from `$EBAC6`) not yet traced.
