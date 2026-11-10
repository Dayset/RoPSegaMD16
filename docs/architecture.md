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
(446 functions, 1,449 edges, after #011) agrees: entry `FUN_00000200` calls
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
`$FF0120` and calls `$2A2CA` / `$26A8C`. The full trace of `$D28E`
and the state machine is issue #020, in the section below
("Main loop + game state machine").

## Main loop + game state machine (issue #020, 2026-11-09) — verified

Status: **verified** — every claim below was checked with a tool run
(Capstone range disassembly, ROM table reads). Confidence is marked
per section; the places the trace stops are labelled open, not
papered over.

### Top-level flow

- `$119E` does `jmp $D25C`; `$D25C` calls seven routines in order:
  `$11E06`, `$14FB6`, `$1B5D6`, `$32D0E`, `$173BC`, `$D28E`,
  `$179B6`. `$D28E`'s `rts` is dead in practice: when `$D28E`
  returns, `$D25C` calls `$179B6` — the **soft reset** (`movea.l
  $FFEC1E,a7; jmp $200`) — which never returns, so the game reboots
  through the whole entry path after the main loop exits.
- `$D28E` (`0xD28E–0xD9DE`, 1,876 bytes). Entry: clears
  `$FF010E`/`$FF00AC`, `$FF00AE=1`, `$26CCA(1)`, `$1BA26`,
  `$1B918`. Loop head at `$D2BE`; loop-back at `$D9DA`: `tst
  $FF00BE; beq $D2BE` (loop while `$FF00BE==0`); else `bra $D392`
  → `unlk; rts` (exit to `$D25C` → `$179B6` → reset).
  **`$FF00BE` is set to -1 at exactly one site, `0x20188`**
  (inside the `$1F296` verb executor) — that is the only exit from
  the main loop.
- Frame pacing at `$D95C`: `$FF00AC` set + `$FF0030 ≤ $32` +
  `$FF02A2` bit 0 set → `$226BC`; else a 10000-iteration delay
  loop. `$FF0030` is a per-iteration counter clamped to `$7530`
  (30000), reset to 0 when `$FF00AC` is set and a command byte is
  present. `$1B918` (the per-frame redraw checker) is called twice
  per `$D28E` iteration — head and tail.

### The seven $D25C callees

- `$11E06` — VDP register setup (writes R0=`$04`, R1=`$34`,
  R2=`$00`, R3=`$04`, R4=`$00`, R5=`$12`, R13=`$08`, R7=`$00`,
  R10=`$FF`, R11=`$00`… via `$D9E2`; the dump cuts off at 0x78
  bytes, one `jsr $aaaaaaaa.l` mis-decode at `0x117C`).
- `$14FB6` — intro/story driver. Loops on `$123B0`'s return:
  1 → `$147D0(0,0x20)`, 2 → `$147D0(0,0x3D)`, 3 →
  `$147D0(0,0x3B)`, 0 → `$12C20` (world-map draw), then `rts`.
  Helper `$15012` plays music `$173BC(1)` + `$15C08`. Sets
  `$FF0128=-1` at `0x15512` (the "intro ran" flag — see `$1B5D6`
  below).
- `$1B5D6` — new-game init (next section).
- `$32D0E` — song picker: returns `0x11` (17) if the leader
  struct `+0x06` == 2 or 3, else 2; d0 is passed to `$173BC`.
- `$173BC` — location-song player (known from the music-off patch).
- `$D28E` — main loop (this section).
- `$179B6` — soft reset (above).

### New-game init $1B5D6 — answers #008's $FF0E18[2] question

- `$1E390($FF0E18, 8)` at `0x1B5DA` — this **confirms** the
  message-queue capacity initialiser: new-game init sets capacity
  8. (#008's partial answer confirmed; the owner is `$1B5D6` in
  the live new-game flow.)
- Then: `$FFC324=-1`; rank-table pointers at `$FFA7CC`
  (`0x1B5F4`); `$FF00B6=$134`; `$FF00B8=$FF00B6*16+$20`;
  `$1961A($FFA880, 4)`; `$1C0EC` (10×10 grid fill — **not** party
  init, per #008); `$1D9BC($FF0E8E)`; `$1DA10` table inits
  (`$FFB08C`, `$FFB09C`, `$FFB0AC`, `$FFB0BC`); `$2A454(-1)`;
  `$FF0E78=$FF0E7E=0`; `$20C5E`; `$FFA7FC=$FFB08C`; `$23A9E`;
  `$2B5F4`.
- Leader spawn: if `$FF0128 == 0` → `$1C21A(6, 0x6F, 0x7D)`
  then `$23B84(1, -1, 0, 0, 1, 0x6F, 0x7D)` → d0 → `$FF02B2`
  (leader index), `$FF0E16=$21C` (540); else (`$FF0128 != 0`)
  → random X=`$12B82(0x160)`, Y=`$12B82(0xE0)`,
  `$1C21A(6, Y, X)`, `$12B82(4)`, `$23B84(1, -1, 0, 4, rand4,
  Y, X)` → `$FF02B2`, `$FF0E16=$834` (2100). So the leader
  spawns at fixed map position (111, 125) when the intro did
  **not** set `$FF0128`, or at a random position when it did.
  `$FF0128` is written at exactly one site, `0x15512` (in the
  `$14FB6` intro flow) — so the fixed spawn is the no-intro path
  and the random spawn is the normal post-intro path.
  **`$FF0128` is likely a "loaded/continued game" flag** — still
  to confirm (medium confidence: it is the only write, and it
  sits in the intro driver).
- Then `$25456(leader, …)` + `$2CDD4` + `$243D6(leader)`.

### Character creation $23B84 — the Arrow/Feather answer, and a puzzle

- Finds the first free slot in the `0x38`-entry char table
  (first slot with `+0x00 & $F == 0`); `$12FA0(0x1A)` if the
  table is full; `$12FA0(0x1B)` if arg `$C ≥ $1CE` (type 1) or
  `≥ $CA` (type 4). 27 call sites (enemies, NPCs, party) —
  `$23B84` is the general entity spawner, not a party-only
  routine.
- Sets `+0x00` low nibble = arg `$8 & $F`; clears `+0x00`
  bit 15; if arg `$A != -1` sets `+0x18` bits 4–9 =
  arg `$A << 4` (level), else sets `+0x18` bits 4–9 = `0x20`;
  if arg `$8 == 1` and arg `$C != -1`, template byte
  `+0x13` (`$CF1BF + $C*0x18`) → `+0x18` bits 4–9 (level);
  if arg `$8 == 6` sets `+0x18` bits 4–9 = `0x90`; clears
  `+0x18` bits 10–11; if arg `$8 == 4` sets `+0x18` bit 12,
  else clears it; stores arg `$C` at
  `struct[$FF02B6 + idx*0x34]` and `0xFF` at
  `struct[$FF02B8 + idx*0x34]`; if arg `$C != -1` and arg
  `$8 == 1`, copies template words from `$CF1AC + $C*0x18`
  (24-byte templates).
- Template copy (0x23D5C–0x23D92): 6 words from
  `$CF1AC + template*0x18` → struct `+0x14`…`+0x1E`. So
  **template word 0 is the name index (`+0x14`)**.
- Templates (24 bytes each at `$CF1AC`;
  `disasm/main-loop/entity_templates.txt`): template 0 = name
  1 "Man", t1 "Fiver", t2 "Hideous", t3 "NEXUS", t4
  "Abattoir", t5 "VOID", t6 "Bob", t7 "Eddie", t10/t11
  "Alexi" (62), t35/t52–54 "Buc" (57).
- **The new-game leader is created with template 0 in both
  `$FF0128` branches — so its name index is 1 ("Man") at
  creation.** That is not Buc (57). And the other party
  members' templates (Slash 58, Mortimer 59, Obliky 60,
  Feather 61) do not appear in templates 0–199 at all.
  Conclusion: the party is **not** built from this template
  table at new-game init — the leader's name must be set
  after `$23B84` (by `$25456`/`$243D6`/`$2CDD4` or by the
  intro/story flow), or the party joins later. **Open for
  #021:** find where `+0x14` is written with 57–62.
- What **is** settled: the six **disciplines are named in
  ROM** (PARTY menu: Sorc, Knight, Archer, Necro, Enchnt,
  Conjur — see the verb table below). "Archer" exists as a
  discipline name; the character name 61 is "Feather" and
  "Arrow" is name 80 (also a spell name_idx 200). The fan
  guide's "Arrow" is the archer's discipline name conflated
  with the character — **the ROM calls the character
  Feather**. Discipline↔spell-block mapping is still **not**
  proven from code (the six blocks' names only suggest the
  mapping).

### $D28E flag dispatch

- `$FF011E != 0` or `$FF0120 != -1` → `$D8BA` (entity
  processing: `$FF0120` index → struct `$FF02DB` byte →
  struct `$FF02B4`, `+0x00` bits 4–9 == 5 or `0x11` → set
  bits, then `$2A2CA($FF0120, $FF0E82)`; then `$26A8C` if
  `$FF011E`).
- `$FF0094` / `$FF00AC` gates; `$FF0128` / `$FF0112` select
  input paths.
- `$FF0030` is a frame counter incremented each iteration,
  clamped to `0x7530` (30000); reset to 0 when `$FF00AC` is
  set and a command byte is present.
- Command switch at `$D740` (subtract-and-branch chain,
  re-verified 2026-11-09; full table in
  `disasm/main-loop/d28e_switch.txt`): 0 → idle; 10 →
  `$1EEEE` (the `$FF0128` path); 20 → `$1E3B0`
  (message-queue push); 21 → `$1F296` (verb executor); 22 →
  `$207D8`; 23 → `$1E5A0`; 24 → `$20884`; 25 → `$20A36`; 30 →
  `$265BE`; 35 → `$2A562`; 37 → `$26CCA` + `$17586(0x11,-1)`
  (confirm, `$FF0030=0x64`); 40 → `$2AFF2`; 45 →
  `$FF0138=-1` (inline); 50 → `$2619C`; 55 → `$32C18` /
  `$26A8C` / `$2AD64`.
- Combat-trigger checks at `$D7A2`/`$D84C`: `$FF013A` /
  `$FF0138` with `$FF010E` bit 0 and `$FF0EA8`
  (spell-sequencer step) gates → `$20A36(1, 0)` calls;
  `$36A00(leader +0x29 byte)` must return 0 and `$FF0EA8 < 5`.
  `$FF00AC` / `$FF02B2` / `$FF02DB` checks precede them.

### The verb executor $1F296 (partially traced)

- `0x1F296–~0x2077A` (~3.6 KB). Head reads `$FFBB82`
  (pointer to the current menu record), byte `+0x0A`, then
  `bra $1FE8A` (a big switch). `$FF00BE=-1` at `0x20188` is
  one branch — the quit/reset action that exits the main
  loop (→ `$D28E` returns → `$179B6` soft reset → title).
  The routine also calls `$2BBD2` (resource routine) at
  `0x1FE0C` with the leader index. Full case mapping is
  #021 work.

### Menu verb table (verified, ROM 0xCCDB8–0xCCFF0)

- Records: item = 14 bytes `[10-byte name, NUL-padded][A][B][C][grp]`;
  header = 12 bytes `[10-byte name, NUL-padded][A][grp]`.
  Headers are the menu titles: MAIN, FIGHT, MOOD, PARTY,
  TACTIC, BUY, INVEN, USE. Full dump with raw trailer bytes:
  `disasm/main-loop/verb_menus.txt`. (The last 'No' record
  at `0xCCFE6` is truncated by the dump range — its trailer
  lies past `0xCCFF0`.)
- Main (grp 1): MAIN, Inven, Spells, Party, Search, Map,
  Camp, System.
- Combat: FIGHT, Flee, ------, Berzrk, Advnce, Hold, Wary
  (grp 8 items; `------` is a grp-1 separator).
- MOOD: Berzrk, Advnce, Hold, Wary (grp 8, C=1–4).
- PARTY disciplines: **Sorc, Knight, Archer, Necro, Enchnt,
  Conjur** (grp 2, C=0–5) — the six disciplines, named in ROM.
- TACTIC: Asasin, GangUp, Cover, Guard (grp 8, C=8–11).
- Shop: BUY, (No), INVEN, Goods, Items, Papers, Keys, Rings,
  USE, SYSTEM. Goods/Items/Papers C values (`0x0E`/`0x0D`/
  `0x11` = 14/13/17) match #007's item-category numbers for
  goods/items/papers; Keys (`0x69`=105) and Rings
  (`0x66`=102) do **not** match their category numbers
  (12/10) — unexplained.
- The C byte reads as the item's verb/action code for the
  main menu (Party=`0x64`, Search=`0x13`, Map=`0x11`,
  Camp=`0x1C`). The exact mapping from (A,B,C,grp) to the
  `$D28E` switch codes is **not** proven — #021.

### Input: where the VBlank joypad queue is consumed

- The queue is the 16-entry ring `$FF001C` (head `$FF001A`,
  tail `$FF001B`), filled by the VBlank handler `0x1272`,
  popped by `$1350` (returns the next byte in d0 and
  `$FF002C`; empty → returns the last value).
- `$1350` has **16 call sites**: 2 in `$D28E` itself
  (`0xD366`, `0xD398`); the menu-input block `$12F48`
  (`0x12F4C`, `0x12F6C`), `$12FB4` (`0x12FCA`), `$12FE8`
  (`0x12FF2`); the intro/story block `$15012` (`0x1537A`),
  `$1664E` (`0x166D8`, `0x169C6`, `0x16ACA`, `0x16B04`); and
  sites at `0x12AC8`, `0x14E54`, `0x14F2C`, `0x1591E`,
  `0x161AA` inside large routines of the same blocks.
- `$12FE8` (`0x12FE8–0x13650`) is the **menu/verb input
  decoder**: pops `$1350`, takes the low nibble of the
  button byte (the D-pad), maps it through jump tables (at
  `0x13052`, `0x13078`, `0x130D8`, `0x130FE`) gated by
  `$FF0116` and `$FF0134` mode flags, producing d6 = 0–4
  (direction/selection index). It writes the `$FF0240`
  command byte from the **button pressed + mode flags**
  (0x12FE8–0x13650, full map in #021): D-pad only → 10
  (when the selection returns to 4 / `$FF0086==4`) or 0;
  A (bit 4) → 21 (if `$FF00AC`) / 30 (if `$FF00AE==1`) / 35
  (otherwise), plus 40/0 variants; B (bit 5) → 22 (if
  `$FF00AC`) / 50 (if `$FF00AE==1`) / 55 (otherwise); C
  (bit 6) → 37 (if `$FF00AC`) / 45 (if `$FF010E` bit 0) / 40
  (selection changed) / 0; Start (bit 7) → 20, and combos 24
  (Start+C, selection byte 6) / 25 (Start+A or Start+B).
  `$FF00AE` (1/2) is the input mode flag (set 1 at `$D29E`
  each `$D28E` iteration; set 2 at `0x1DC1C`, back to 1 at
  `0x1DE6A`). The record at `$FF0240` is [byte0 = command,
  byte1 = d6, word = -1]. Writes `$FF0136` = d6 (current menu
  selection index) when `$FF00AC == 0` and `$FF010E` bit 0
  == 0, else `$FF0136` = 4. If `$FF0112 != 0` it copies the
  record to `$FF0240` and returns `$FF0240`.
  **CORRECTED in #021 — this was described as producing only
  command 0 or 37; it produces 0, 10, 20, 21, 22, 24, 25,
  30, 35, 37, 40, 45, 50, 55.**
- `$FF0136` (menu selection index) is read at `0x138D2`
  (inside a routine at `0x138A8` that indexes a 6-byte
  table at `$1B446` by `$FF0136*6` and formats a display
  value).
- Note: `$12FE8` produces 0, 10, 20, 21, 22, 24, 25, 30,
  35, 37, 40, 45, 50, 55 (see above) — 14 of the `$D28E` switch's
  15 cases are reachable from it. The remaining command
  value, 23, has **no writer anywhere in the ROM** — no literal
  `move.b #$17` into the command slot in either disassembly file,
  no register write or arithmetic on the slot, and `$FF0240`'s only
  writers are the reset RAM-clear and `$12FE8`'s three exit sites —
  so the command-23 dispatch entry (`$D566`, which calls `$1E5A0`)
  is dead code [static, resolved 2026-11-10]. The handler `$1E5A0`
  itself is NOT dead (called live from 4 other sites). Other writers:
  `$D328` writes 10 literally in the `$FF0128` branch;
  `$D43E` clears the command to 0 when a message is pending
  (unless the command is 0/37/40) and calls `$17586(-1, 0x14`).
  The `$D28E` switch is on the `$FF0240` command byte; the
  verb C codes are NOT `$D28E` codes — the bridge is `$D28E`
  case 21 → `$1F296`, which dispatches on the selected
  record's C byte (full `$1F296` case map in #021).

### Per-frame world tick $2155E (partially traced)

- Called once per `$D28E` iteration (via the `$D95C` path).
  Updates animation counters: `$FFA7FC` record `+0x0A` =
  (x+1)%4, `$FF0092` = (x+1)%2; **`$FF0E16` = (`$FF0E16`+1) %
  `0x960` (2400) — the step counter**; `$FF0144` =
  (`$FF0144`+1) % `0xC8` (200).
- Palette fades via `$170DA` (called when `$FF0124 != 0`, or
  when `$FF0126 == 2` and `$FF0E16`/18 is 0 or 30): `$170DA`
  loads palettes `$CCC38`/`$CCB18`/`$CCCB8` via `$11082` or
  cross-fades them via `$1225C`, depending on `$FF0126`
  (mode 1/2/4) and `$FF0E16`/18. `$FF0124` is the "palette
  refresh requested" flag, cleared by `$170DA`.
- Location/arrival checks on `$FFC364`/`$FFC366` (a
  coordinate pair): both > 500 → merchant-attitude loop
  with delta +5; both > 1 → `$35612(0x44, 0x24)` +
  `$17586(0x14,-1)`; else → `$35612(0x44, 2)`, palette 22
  load, `$FF0124=-1`, `$25456(leader,…)`,
  `$32C56(leader X, leader Y, 1)`, `$32D0E` → `$173BC`
  (music change), `$17586(0x14,-1)`.
- Merchant attitude drift (`0x21850+`): iterates the 6
  merchants in `$FF0E82`, adjusting struct `+0x1C` by d7
  (+5 or -4) with clamping against `+0x20`, and `+0x1E`
  by d7*10+30 against `+0x22`; calls `$37B82` (death check)
  per merchant. This is the live attitude drift behind
  #007's price function.
- `$FF0E16` step-counter readers elsewhere: `$D372`
  (`$FF0E16`/10 == 3 test), `$170DA`, `$2EC80`/`$2EC9C`
  (predicates: `$FF0E16`/18 > 30 → `0xFF`/0, else 0/`0xFF`),
  `0x2F1F0`/`0x2FA2A`/`0x302F0`.

### Food/water consumption — NOT located (honest gap, narrowed)

- `$170DA` is a palette routine, **not** the consumption
  routine (the `$FF0E16`/18 triggers in `$2155E` drive
  palette fades, not food/water).
- The `$2BBD2` codes `0x380`/`0x381` (food/water goods slots
  0/1) are inventory-count codes (`$2C8F2`), not consumption.
  No `$2BBD2` call site with a per-step decrement was found.
  The consumption routine is still open for #021; the
  strongest remaining leads are the `$FF0E16` step
  counter's readers (`$2F1F0`, `$2FA2A`, `$302F0`, `$2EC80`)
  and the `$32C56` position-based call in `$2155E`.

### Terrain grid — NOT located, but the decoder is now understood (partial close of the #006 gap)

- The threaded decoder at `0xE3B4`/`0xE412` **is** the
  terrain/map bitmap decoder: it sets up tables a1=`$435C0`
  (nibble expansion), a2=`$436E0` (tile offsets), a3=`$433C0`
  (masks), a4=`$FF1EC0` (output bitmap), a6=`$DF58` (jump
  table), reads a byte stream from a0, and dispatches
  through the `$DF58` table (which alternates `$E3E2`/
  `$E43C` — the two entry continuations) via `move.l
  (a6,d2.w), -(a7); rts` (threaded code). It has **no direct
  jsr/bsr callers** — it is entered only through the `$DF58`
  table itself. The output is a bitmap at `$FF1EC0` (the "MM
  map" bitmap; the unrolled writer at `0xE47C` writes
  33-byte rows).
- What is still missing: which routine jumps into the
  decoder with a0 pointing at the stream (the source block
  — the `0x044000–0x05FFFF` high-entropy block is still the
  prime suspect) and how the `$FF1EC0` bitmap is consumed by
  movement/collision. So the terrain grid itself is still
  not located — but the decoder mechanism is now
  documented, which narrows #021's search to the decoder's
  entry points and the `$FF1EC0` consumers.

### Live combat — not driven headlessly (bounded, with evidence)

- The live-combat half of #007 Q1 (watching `$3A62E`
  dispatch during real gameplay) was **not** attempted
  headlessly: there is no credible path without a
  save-state + scripted-input driver. The #008 harness
  pattern (hook at `0x35C`, fabricated structs, results in
  `$FFD000+`) proves the dispatch at the routine level —
  both branches, `$FFC418`/`$FFC41A` set correctly — but
  driving a real fight needs starting a new game,
  navigating menus, positioning the party next to an enemy,
  and triggering the fight, which is a full playthrough
  driver, not a harness. The dispatch-level answer from
  #008 stands; the live half stays open for #021 (needs a
  save-state/input driver).

### States identified (summary)

- Title/attract: `0x35C–0x390` loop (entry path), then
  `$14FB6` intro/story driver, then `$1B5D6` new-game init,
  then `$D28E`.
- Overworld/town: `$D28E` main loop + `$2155E` world tick +
  `$1B918` redraw checker + `$170DA` palette fades;
  movement via `$1C21A` (position setter, mode 6 = direct
  add into `$FF0E8E`/`$FF0E90` modulo area size).
- Menu: `$12FE8` decoder + `$FF0240` command record +
  `$D28E` switch + `$1F296` verb executor; verb table at
  `0xCCDB8`.
- Combat: `$D7A2`/`$D84C` trigger checks → `$20A36`;
  `$3A62E` dispatch (melee `$3B1EE` vs giant spell machine
  `0x3E2D4`, selected by `+0x24`) per #008; `$FF0EA8` is
  the spell-sequencer step.
- Dialogue/message: `$26CCA` message-queue pop/display
  (`$1E426` pop; record at `$FFBC94 + slot*0xD2`);
  `$1E3B0` enqueue (switch case 20).
- Exit: `$FF00BE=-1` (only at `0x20188`) → `$D28E` returns
  → `$179B6` soft reset → `$200` (full reboot through
  entry).

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

## $4323C and its helpers — call-graph level (full analysis is #019, see `docs/save.md`)

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
  clear → write). **Data bit on D7, clock on D6** (corrected in
  #019 — the old text said "DI = D0", which misread CPU register d0
  as data-bus bit D0; see `docs/save.md` §2).
- `$42EEE` — shift **one bit in**: write `$80`, write `$C0`, read
  `$200000` → d1, write `$80`; the read bit comes back on D7
  (`asl.b d1` / `roxl d0`). (Corrected in #019 — the old text
  labelled this routine `$42F96`.)
- `$42F96` — **ACK read**: write `$80`, write `$C0`, read `$200000`
  → d1, write `$80`; the caller does `tst.b d1; bpl` — ACK = DO bit
  7 LOW (0); bit 7 = 1 means no-ACK/error.
- `$43012` — EEPROM **read** (block): takes a buffer pointer, address
  and count off the stack, stores them at `$FF0150–$FF015C`, clocks the
  command out via `$42EBA` ×8 (with `or.w #1` in the command word — the
  read bit), reads an ACK bit via `$42F96`, then reads bytes back through
  the `$42EEE` bit-in loop (`move.b d0, (a0)+`), looping `$FF015C` times.
  On error `$FF014E++` and retries up to `$FF014C` (10).
  **CORRECTED in #021 — this was labelled "write" in #003; the call-site
  proof is decisive: boot validation calls `$43012(d1=$80, a0=$FF016A)`
  and then validates the buffer, so it must be the read.**
- `$430F4` — EEPROM **write** (one byte): same bit-bang pattern
  (command out via `$42EBA` ×8 **without** the `or #1`, ACK in via
  `$42F96`), then sends the byte (`move.b (a0), d0; lsl #8; $42EBA` ×8)
  and waits out the write cycle (`move.w #$1518, d0; dbra`).
  **CORRECTED in #021 — this was labelled "read" in #003; the clear-save
  loop calls `$430F4` 128× with a0 advancing through the zeroed buffer,
  so it must be the write.**
- So the save hardware is a **Microwire-style serial EEPROM**
  bit-banged through the cartridge `$200000` window (separate DI/DO/
  CLK lines: **DI = D7, CLK = D6, DO = D7** — corrected in #019;
  DI and DO share data-bus bit D7). Chip identity (93C46 family
  is the usual suspect) is **unknown** — #019 did not confirm it.
  Corroboration: BlastEm's `rom.db` lists this ROM (`T-50176`) as
  `EEPROM { type i2c, size 128 }` with `bits_read { 7 sda }` and
  `bits_write { 6 scl, 7 sda }` — an independent match for the
  wiring. BlastEm auto-detected the EEPROM from the `$200000`
  access pattern and saved a **128-byte** `save.eeprom`, matching
  the 128-byte buffer at `$FF016A`. Note the ROM header declares
  **no backup RAM** (bytes `0x1B0–0x1BF` are spaces) — the EEPROM
  is only discoverable from the code, not the header. (Also #019:
  BlastEm's fresh EEPROM reads as `0x00`, not `0xFF` — a real
  erased 93C46 reads `0xFF`.)
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
  Full analysis is #019 (`docs/save.md`): the buffer holds the
  EEPROM image (magic `0x2A` + parity + 1001-bit packed game state
  in `$FFA800`); the byte-sum check is vestigial — a valid save
  fails it 3/3 — and `$FF0168` is never read by any code.

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
disassembly. Those three (plus 8 more the analyser missed —
`$EBA00`, `$EB7C8`, `$EB8E0`, `$2B2B2`, `$2B502`, `$2988E`,
`$3536C`, `$3539A`) were created manually in **#011**, bringing the
graph to 446 functions / 1,449 edges; exports are under
`disasm/ghidra/` (see `disasm/ghidra/README.md`).

## What remains unknown (for #011 / #019 / #020)

- **#011 (Ghidra recursive analysis): DONE 2026-11-09** — 446
  functions / 1,449 edges; boundaries for `0x010000–0x043FFF`
  (90.7% code, every gap ≥64 B classified) and `0x0E0000–0x0FBFFF`
  (0.9% code, sound cluster only, both gaps classified as data)
  decided per function; entry, VBlank, `$4323C`, and `$EB772` call
  trees mapped. Exports under `disasm/ghidra/`; `disasm/map.md`
  updated.
- **#019 (save validation): DONE 2026-11-09** — see `docs/save.md`
  (new doc). Medium decided: **128-byte serial EEPROM**, Microwire
  bit-bang via `$200000`, **DI = D7, CLK = D6, DO = D7** (corrects
  the "DI = D0" line above); `$DCE2`/`$42FC8`/`$43012`/`$430F4` fully
  traced; `$E0` = B+C+Start, `$B0` = A+C+Start on pad 2; `$FF0168`
  mapped (0/1/−1) and re-verified never read; the real format is
  magic `0x2A` + `$176A0` parity + 1001-bit packed `$FFA800`, and a
  valid save **fails** `$4323C`'s byte-sum check 3/3 (harness-proven)
  — the check is vestigial. Save/load round-trip proven end to end
  (`$2F11A` → `0x48`, `$2F896` → `0x49`, magic `0x2A`, parity
  `0x1B` verified by independent recomputation). Real Load/Save are
  `$2068E` cases **81/82** (corrects the #021 "C=14" label — case 14
  is the 'Goods' shop verb). Open: chip identity (93C46 family
  unproven), `$FFBB6C` setter, `$2F896`'s
  `0x4E` acceptance. BlastEm notes: fresh EEPROM reads as `0x00`
  (not `0xFF`); it writes `save.eeprom` on exit but does not reload
  it, so a live boot-from-save was not observed — persistence is
  proven at the file level + via `$43012`. `$FF00C0` is the
  persistent merchant-attitude table (36 words, resolved 2026-11-10;
  see `docs/save.md`). M2 is now COMPLETE.
- **#020 (main loop / state machine): DONE 2026-11-09** — see the
  "Main loop + game state machine" section above. What it left
  open for #021: the exact mapping from the `0xCCDB8` verb-table
  (A,B,C,grp) records to the `$D28E` command-switch codes; the
  full `$1F296` verb-executor case map; where `+0x14` is written
  with the party names 57–62 (the leader is created as template
  0 "Man"); the food/water consumption routine; the terrain-grid
  stream source and the `$FF1EC0` bitmap's consumers; the
  live-combat half of #007 Q1 (needs a save-state/input driver).
- **#003 open ends, kept:** `$42E00` is a jump-table dispatcher on
  d0 (branches to `$40DD4`/`$3E384`/`$3E38E`/`$40CDC`/`$40E22`/
  `$40EDC`/`$41EB4`/`$3E418`) — purpose unknown; `$EBB04`/`$EBBFE`
  (sound-command handlers called from `$EBAC6`) not yet traced.
