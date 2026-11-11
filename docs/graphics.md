# Graphics — VDP registers, VRAM layout, draw dispatch (issue #015)

Status: **verified** — every register value below was read from the ROM
bytes (Capstone range disassembly) or from a live BlastEm run; the live
values are in §7. Confidence is marked per claim. The places the trace
stops are labelled open, not papered over.

**Correction to the issue file:** the third acceptance bullet says the
per-frame draw dispatch is "traced from VBlank `jsr $EB772`". That
premise is wrong — $EB772 is the per-frame **sound** tick only
(PAL/NTSC tempo tick to Z80 RAM $A000E6, `jsr $EBAC6` sound command
queue, every 16 frames `jsr $EBA00` music streamer; #003/#020). It does
no drawing, and the VBlank handler 0x1272 does frame counter + joypad
ring + `jsr $EB772` and nothing else visual. The real per-frame draw
path lives in the main loop $D28E: the $1B918 redraw checker (called
twice per iteration), the $170DA palette routine, and the upload
helpers $1194A/$11A7C/$11B2E/$DA04. This document traces the draw
dispatch from $D28E (§6), not from $EB772.

Related docs: the blitter and tilemap records are in `docs/maps.md`
(#006); palettes and tile formats in #005 (`disasm/graphics/`,
`tools/render_tiles.py`); the packed-vs-planar paradox is **#016's**,
not this issue's — it is recorded as open in §8 and not solved here.
The map-chunk loader ($19692/$1C802, buffers $FF868C + slot×2048) is
#017's; it feeds VRAM through the upload path in §6.3.

## 1. How the game talks to the VDP

All VDP access goes through the two ports: data `$C00000`, control
`$C00004`. Three tiny helpers do almost all of it:

| helper | body | use |
|---|---|---|
| `$D9E2(word)` | `move.w $4(a7),d0; move.w d0,$C00004; rts` | Write one word to the VDP control port. 88 of the 94 `jsr` sites pass a packed `$80RR` register word (high byte `$80` + register number, low byte the value); the other 6 pass CRAM-address command words (`$C000`/`$C020`/… + `$0000`) from the palette loaders `$11082`/`$110D0`/`$1110A` (§6.5), and 2 more pass computed R17 window-position words (0x1623A/0x16294, §5). |
| `$D9EE(word)` | `move.w $4(a7),d0; move.w d0,$C00000; rts` | VDP **data** write (one word, auto-increments by R15). |
| `$D9FA()` | `moveq #0,d0; move.w $C00000,d0; rts` | VDP **data** read (one word, auto-increments by R15). |
| `$DC60(addr)` | splits a VRAM byte address into the two-word write command and writes both words to `$C00004` | Set VRAM **write** address. 23 `jsr` sites. |
| `$DA04(src, dest, count)` | DMA upload, §6.3 | The only DMA path. 5 `jsr` sites. |

**Command-word format** (two 16-bit writes to `$C00004`; verified
against every constant in the ROM): first word = address bits 13–0
plus the CD bits in bits 15–14; second word = address bits 15–14 in
bits 1–0, plus a memory select in bits 5–4 (`00` VRAM, `01` VSRAM,
`10` CRAM read). The constants used:

| command long | meaning |
|---|---|
| `$40000000` | VRAM write, address 0 |
| `$00000000` | VRAM read, address 0 |
| `$C0000000` | CRAM write, address 0 |
| `$40000010` | VSRAM write, address 0 |
| `$60000000` | VRAM write, address `$2000` (H-scroll table) |
| `$49200001` | VRAM write, address `$4920` (attract tile upload, §8) |
| `$40000080` | VRAM write, address `$0080`, with R23=`$80` = DMA **fill** mode (boot) |

**VRAM read note (verified live, §7):** the first data-port read
after setting a read address returns the word **at** that address —
there is no dummy word to discard. (An early version of the §7
harness did a dummy read and its snapshots came out shifted by exactly
one word; removing it aligned every region with the code trace and
with BlastEm's own `vs` dump.)

**Register-number encoding:** a register write is one word
`$80RR` where `RR` = register number × 1 + value in the low byte,
i.e. `$82VV` writes value `VV` to R2, `$8DVV` to R13, etc. Base
addresses are the register value × a fixed stride:

| register | base = value × | what it sets |
|---|---|---|
| R2 | `$400` | Plane A (Scroll A) name table |
| R3 | `$400` | Window name table |
| R4 | `$2000` | Plane B (Scroll B) name table |
| R5 | `$200` | Sprite attribute table |
| R6 | — | sprite pattern base (never written after boot; `$00`) |
| R13 | `$400` | H-scroll data table |
| R15 | — | data-port auto-increment (`$02` everywhere except `$16512`, §6.4) |
| R16 | — | plane size: bits 1–0 width (0=32, 1=64, 3=128 cells), bits 5–4 height (0=32, 1=64) |

Other registers: R0 bit 4 = H-int enable (0 in every set — the
HBlank handler `$1270` is a bare `rte` and never fires); R1 bit 6 =
display enable, bit 5 = V-int enable, bit 4 = DMA enable, bit 2 =
Mode 5; R7 = backdrop colour (palette in bits 5–4, colour in bits
3–0; always `$00` = palette 0 colour 0); R10 = H-int counter
(`$FF`, moot with H-int off); R11 bits 1–0 = H-scroll mode (0 = full
screen, 3 = per-line), bit 2 = V-scroll mode (0 = full screen);
R12 bit 0 = H40 (1 = 320 px) vs H32 (0 = 256 px); R17 = window H
position (bit 7 = right/left, bits 5–0 = cell); R18 = window V
position (bit 7 = down/up, bits 4–0 = cell); R19/R20 = DMA length
low/high byte; R21/R22/R23 = DMA source address bytes (word
address); R23=`$80` also selects DMA fill mode at boot.

## 2. Register set 1 — boot table at `0x28E` (entry `0x200`)

The 108-byte table at `0x28E` is consumed by the entry code
(`lea $28E(pc),a5; movem.w (a5)+,d5-d7; movem.l (a5)+,a0-a4`),
verified field by field against the ROM bytes:

- Header words: `d5=$8000` (register-write base), `d6=$3FFF` (RAM
  clear count), `d7=$0100` (register-number step); longs
  `a0=$A00000` (Z80 RAM), `a1=$A11100` (Z80 bus request),
  `a2=$A11200` (Z80 reset), `a3=$C00000` (VDP data),
  `a4=$C00004` (VDP control).
- Then a 24-iteration loop (`moveq #$17,d1; move.b (a5)+,d5;
  move.w d5,(a4); add.w d7,d5; dbra`) writes the 24 register bytes
  in order, R0–R23:

| reg | val | meaning |
|---|---|---|
| R0 | `$04` | H-int off, display generator on |
| R1 | `$14` | display **off**, V-int off, DMA on |
| R2 | `$30` | Plane A `$C000` |
| R3 | `$3C` | Window `$F000` |
| R4 | `$07` | Plane B `$E000` |
| R5 | `$6C` | sprite table `$D800` |
| R6 | `$00` | sprite pattern base 0 |
| R7 | `$00` | backdrop = pal 0 colour 0 |
| R8/R9 | `$00` | unused |
| R10 | `$FF` | H-int counter 255 (moot, H-int off) |
| R11 | `$00` | full-screen scroll both planes |
| R12 | `$81` | H40, 320 px |
| R13 | `$37` | H-scroll `$DC00` |
| R14 | `$00` | unused |
| R15 | `$01` | auto-increment 1 |
| R16 | `$01` | planes 64×32 |
| R17/R18 | `$00` | window top-left, position 0 |
| R19/R20 | `$FF` | DMA length `$FFFF` |
| R21/R22 | `$00` | DMA source 0 |
| R23 | `$80` | DMA **fill** mode |

- After the loop the table continues: long `$40000080` (VRAM write
  at `$0080`) + one zero word to the data port = DMA fill of VRAM
  (length `$FFFF`, fill mode); then the 38-byte Z80 upload (first 14
  bytes decode as a Z80 RAM-clear stub: `xor a; ld bc,$1FD9;
  ld de,$0027; ld hl,$0026; ld sp,hl; ld (hl),a; ldir`, then
  register-restore + `di; im 1; ld (hl),$E9; jp (hl)` — a parked
  Z80); then long `$81048F02` (packed R1=`$04` blank + R15=`$02`
  auto-inc 2); long `$C0000000` (CRAM write address 0) + 32 longs
  of 0 (CRAM clear, 128 B); long `$40000010` (VSRAM write address
  0) + 20 longs of 0 (VSRAM clear, 80 B); 4 bytes `9F BF DF FF` to
  `$C00011` (PSG silence). Total: exactly 108 bytes, `0x28E–0x2F9`.
  (Note: the two address longs are table bytes, but the zero words
  are not — the entry code writes them in loops after reading each
  address long: CRAM's 32 zero longs at 0x266–0x26A, VSRAM's 20 at
  0x270–0x274. That is why the table is exactly 108 bytes: the
  tail is fill long (4) + Z80 stub (38) + `$81048F02` (4) +
  `$C0000000` (4) + `$40000010` (4) + PSG bytes (4) = 58, on top
  of the 26-byte header + 24 register bytes.)

Note R13=`$37` puts the boot H-scroll table at `$DC00`, and R5=
`$6C` puts the boot sprite table at `$D800` — both are overwritten
by the next set before anything is displayed.

## 3. Register set 2 — `$A14` (attract layout)

`$A14` (0xA14–0xAB0) runs from the `0x2FA` entry path, after the
runtime checksum and the save check, before the display is turned
on. Verified by disassembly:

1. `clr.w $FFC000`; clears RAM (`move.w #$3FF6,d0` longs from
   `$FF0000`).
2. The second register set, written directly to `$C00004`
   (not via `$D9E2`):

| reg | val | meaning |
|---|---|---|
| R0 | `$04` | H-int off |
| R1 | `$34` | display **off**, V-int on, DMA on |
| R2 | `$28` | Plane A `$A000` |
| R3 | `$30` | Window `$C000` |
| R4 | `$05` | Plane B `$A000` (same table as Plane A) |
| R5 | `$6E` | sprite table `$DC00` |
| R7 | `$00` | backdrop 0 |
| R11 | `$03` | **per-line** H-scroll, full-screen V-scroll |
| R16 | `$03` | planes 128×32 |
| R10 | `$01` | H-int counter 1 (moot) |
| R12 | `$81` | H40, 320 px |
| R13 | `$08` | H-scroll `$2000` |
| R15 | `$02` | auto-inc 2 |
| R17 | `$00` | window left, position 0 |
| R18 | `$00` | window top, position 0 |

3. VRAM clear: `$40000000` + `0x4000` longs of 0 (all 64 KB).
   VSRAM: `$40000010`, then `$AB2` writes two zero words (VSRAM
   words 0–1 = 0; the boot clear already zeroed the rest). The
   rest of `$AB2` builds a RAM table at `$FFC0EA` (the
   `$55555555`/`$44444444`/`$66666666` patterns) — not VDP.
4. `move.l #$60000000,$C00004` — leaves the VDP write cursor at
   VRAM `$2000` (the H-scroll table) — and returns.

This is the layout the title/attract screen runs in, and the one
verified live in §7 (BlastEm `vr` prints exactly these values).
Plane A and Plane B share the name table at `$A000`.

Then `0x2FA` writes R1=`$8134` (display still blank, V-int + DMA
on), and after a second `$A14` + joypad read, R1=`$8174`
(**display ON**) — the attract loop `0x35C–0x390` starts.

## 4. Register set 3 — `$11E06` (game layout) and `$4323C` tail (hang layout)

### 4.1 `$11E06` — the game VDP setup

`$11E06` (0x11E06–0x11F36) is the first of the seven `$D25C`
callees, i.e. it runs once when the game proper starts (after a
button press leaves the attract). Verified by disassembly — it
writes the third layout via `$D9E2`:

| reg | val | meaning |
|---|---|---|
| R0 | `$04` | H-int off |
| R1 | `$34` → `$74` at the end | display off, then **on** |
| R2 | `$00` | Plane A `$0000` |
| R3 | `$04` | Window `$1000` |
| R4 | `$00` | Plane B `$0000` (same table as Plane A) |
| R5 | `$12` | sprite table `$2400` |
| R13 | `$08` | H-scroll `$2000` |
| R7 | `$00` | backdrop 0 |
| R10 | `$FF` | H-int counter 255 (moot) |
| R11 | `$00` | full-screen scroll |
| R12 | `$81` | H40, 320 px |
| R15 | `$02` | auto-inc 2 |
| R16 | `$03` | planes 128×32 |
| R17 | `$80` | window **right** side, position 0 |
| R18 | `$00` | window top, position 0 |

Then: `$DC60(0)` + a `$8000`-iteration `$D9EE(0)` loop (VRAM
clear, 64 KB); R1=`$8174` (display ON); palette loads
`$11082($CCB18, slot 0)` (pal 10) and `$11082($CC9D8, slot 1)`
(pal 0, the master table's first palette); R7=`$00` again;
`$11B76` (writes 4 zero words at VRAM[`$FF8644`], i.e. clears one
sprite attribute at the current sprite base); `$DC16(0,0,0,0)`
(zero scroll, §6.4); `$173BC(0)` (play song 0).

Note: **Plane A and Plane B are again the same table** (`$0000`).
The game uses one name table for both planes in this layout; the
blitter (`$1194A`, §6.3) selects the plane by its `dest` argument.

### 4.2 `$4323C` tail — the save-check hang layout

The save-validation routine `$4323C` ends, on failure, in a
deliberate hang at `$4333A` (#019). It first resets the VDP to a
fourth layout (verified by disassembly, 0x4333A–0x433BE):

R0=`$04`, R1=`$04` (display off, V-int off, DMA **off**),
R2=`$00` (Plane A `$0000`), R3=`$00` (Window `$0000`),
R4=`$00` (Plane B `$0000`), R5=`$00` (sprites `$0000`),
R6–R9=`$00`, R10=`$FF`, R11=`$00`, R12=`$00` (**H32, 256 px** —
the only place R12=`$00` is written), R13=`$00` (H-scroll
`$0000`), R14=`$00`, R15=`$02`, R16=`$00` (planes 32×32),
R17=`$00`, R18=`$00`. Then CRAM write address 0 + one word
(`d0`, the checksum residue) to CRAM[0]; VRAM clear (`$40000000`
+ `0x1000` longs of 0); R1=`$8144` (display **on**, V-int on, DMA
off); infinite `bra $433BE`. The hang screen is 256 px wide with
both planes and the sprite table all at VRAM 0.

## 5. Runtime layouts — two modes, plus single-register tweaks

Every `$D9E2` call site in the ROM (94 sites, extracted
mechanically) writes one of two values for each of R2/R3/R5/R13.
R4 is always `$00`. So the game has **two** runtime layouts, and
the register sets are installed inline by the scene routines:

### Layout G — game/overworld (`$11E06` + `$12C20`)

- R2=`$00` (Plane A `$0000`), R3=`$04` (Window `$1000`),
  R4=`$00` (Plane B `$0000`), R5=`$12` (sprites `$2400`),
  R13=`$08` (H-scroll `$2000`), R17=`$80`, R11=`$00`.
- Installed by `$11E06` (§4.1) and again by `$12C20` (the
  world-map routine, 0x12C6E–0x12CE2), which additionally sets
  R16=`$01` (planes **64×32** — the world map is 28×40 and fits;
  #006's blitter calls use stride `$40` = 64-wide) and
  `$FF8644=$2400` (the sprite-table base variable, §6.3).
- This is the layout the overworld, towns and menus run in.

### Layout L — intro / story / location pictures

- R2=`$08` (Plane A `$2000`), R3=`$3C` (Window `$F000`),
  R4=`$00` (Plane B `$0000`), R5=`$22` (sprites `$4400`),
  R13=`$10` (H-scroll `$4000`), R17=`$00`, R11=`$00` (or `$03`,
  see below).
- Installed inline by five routines, each setting
  `$FF8644=$4400` alongside: `$123B0` (0x12524, the intro/story
  return-code routine called from `$14FB6`), `$147D0` (0x148EE,
  the intro story driver, called by `$14FB6` with 0x20/0x3D/0x3B),
  `$15C08` (0x15D1E, called from the intro helper `$15012`),
  `$17B88` (0x17C72 and 0x18BF0 — the scene-draw driver, called
  from FUN_0003d9f8 right after the `$E358` terrain decode, so
  this is the overworld/location-picture draw path).
- `$147D0`/`$15012`/`$17B88` also write R16=`$11` (planes
  **64×64**) at some sites (0x1494A, 0x155B8, 0x186D4, 0x19022) —
  the taller plane is used by the intro/story and location scenes.

### Single-register tweaks (scattered sites)

- **R11 per-line H-scroll on/off:** `$8B03` at 0x15D6E, 0x17D08,
  0x18C40 (inside Layout L routines — those scenes scroll
  per-line); `$8B00` at 0x1554E, 0x17CB6, 0x186B2, 0x19000 (back
  to full-screen). R11=`$03` is also the attract value (§3).
- **R15 auto-increment `$80`:** only in `$16512` (0x1651E, the
  column writer, §6.4), restored to `$02` at 0x1663E. An
  auto-increment of 128 bytes = one 64-wide plane row, so each
  data-port write lands one row below the last.
- **R16 plane size:** `$9003` (128×32, the default) in 6 sites
  (5 via `$D9E2` + 1 direct write in `$A14` at 0xA64);
  `$9001` (64×32) once via `$D9E2` in `$12C20` (world map,
  0x12CDE) — the only other `$01` is the boot table's own R16;
  `$9011` (64×64) in the Layout L scenes above.
- **R17/R18 window position:** R17=`$80` (right) in Layout G,
  `$00` (left) in Layout L; R18=`$00` everywhere except
  `$9294` at 0x1297C (inside `$123B0`: window **down**, V
  position 20 — the intro's window starts at row 20; its exact
  role is not traced, §8). R17 is also written **computed** by
  the map-scroll routine at 0x1623A (`$9100`+pos, window left)
  and 0x16294 (`$9180`+pos, window right), where pos is the
  scroll offset / 16 clamped to 0–127 — the window's horizontal
  position tracks the map scroll.
- **R1 display toggles:** `$8134` (blank, V-int + DMA on) at
  entry/`$11E06`/`$12C20`; `$8174` (display on) at entry,
  `$11E06` (0x11EE4), `$12C20` (0x12ED6); `$8104`/`$8144` only
  in the `$4323C` hang (§4.2).
- **R7 backdrop:** `$00` everywhere it is written.
- R6, R8, R9, R14 are never written after the boot table (all
  `$00`). R19–R23 are written only by `$DA04` (DMA, §6.3) and the
  boot fill.

### VRAM layout per mode

| region | boot `0x28E` | attract `$A14` | game G | location L | hang `$4323C` |
|---|---|---|---|---|---|
| Plane A name table (R2) | `$C000` | `$A000` | `$0000` | `$2000` | `$0000` |
| Plane B name table (R4) | `$E000` | `$A000` | `$0000` | `$0000` | `$0000` |
| Window name table (R3) | `$F000` | `$C000` | `$1000` | `$F000` | `$0000` |
| Sprite table (R5) | `$D800` | `$DC00` | `$2400` | `$4400` | `$0000` |
| H-scroll table (R13) | `$DC00` | `$2000` | `$2000` | `$4000` | `$0000` |
| Plane size (R16) | 64×32 | 128×32 | 128×32 (64×32 in `$12C20`) | 128×32 / 64×64 | 32×32 |
| H-scroll mode (R11) | full | **per-line** | full | full / per-line | full |
| Screen (R12) | H40 320 px | H40 | H40 | H40 | **H32 256 px** |

Pattern (tile) data lives in the VRAM not covered by the tables
above — e.g. in the attract layout the tiles occupy `$0000–$2000`
and `$2400–$A000` (the `$4E6` phase-2 upload writes tiles at
VRAM `$4920` = tile 585, §8; the `$11A7C` running cursor
`$FF0076` places tiles from `$0000` up in the game layout). The
exact tile placement is per-scene (the upload path in §6.3), not
a fixed partition — the game DMA-uploads each scene's tiles to a
base chosen by the caller.

## 6. Per-frame draw dispatch (from `$D28E`, not `$EB772`)

### 6.1 The main loop and the redraw checker `$1B918`

`$D28E` (0xD28E–0xD9DE) is the flag-driven dispatcher (#020).
Entry clears `$FF010E`/`$FF00AC`, sets `$FF00AE=1`, calls
`$26CCA(1)` (message display), `$1BA26` (request full redraw,
§6.2), `$1B918`. Loop head is `$D2BE`; `$1B918` is called twice
per iteration (entry 0xD2B8 and tail 0xD9CE — the only two
`$1B918` call sites in the ROM). Frame pacing is at `$D95C`;
the loop exits only when `$FF00BE` = −1 (set at exactly one
site, 0x20188, in the `$1F296` verb executor).

`$1B918` (0x1B918–0x1BA15) is the per-frame redraw checker,
verified by disassembly. It reads five redraw flags and services
each one that is set, then clears them:

| flag | set by | `$1B918` does when set |
|---|---|---|
| `$FF0098` (word) | `$1BA16` / `$1BA26` only | `$11DE8` (clear the `$FF1EC0` decode buffer, 0x19E0 longs) + `$1BA4E($FF0E90, $FF0E8E)` (map-chunk position math) + **DMA upload** `$DA04($FF1EC0 → VRAM $FF8674×32, $33C0 words)` — the map chunk (828 tiles) hits VRAM |
| `$FF009A` (word) | `$1BA26` + verb-executor sites 0x1F056, 0x1F152, 0x1F1DA, 0x1FC98, 0x1FE80, 0x1FFBA | `jsr $275B0` (message draw) |
| `$FF009C` (word) | `$1BA26` + 0x1DA74 + verb sites 0x1EF58–0x1F08C | `jsr $26E44` |
| `$FFB08A` (byte) | `$1BA26` + verb sites 0x1EF50–0x1F084 (cleared at 0x1EEB4) | `jsr $1E5A0` if `$FF00AC != 0`, else `jsr $26DD2` |
| `$FF009E` (word) | set to 1 at 0x1DFF8, cleared at 0x1DC44 | `jsr $17860($FF009E)` (location-picture draw, #006) then `$FF009E = $FFFF` |

Regardless of the flags, `$1B918` always calls `$138A8` (the
menu formatter — reads `$FF0136`, indexes the 6-byte table at
`$1B446`, calls the sprite writer `$11BD8`; #021). The local
"redraw requested" byte is (`$FF009C` OR `$FFB08A` OR
`$FF009A`); if `$FF0098` is also 0 and the local byte is 0, it
returns immediately.

### 6.2 Who requests a redraw

- `$1BA26` (0x1BA26–0x1BA4D): sets **all four** flags
  (`$FF0098`, `$FFB08A=$FF`, `$FF009A`, `$FF009C` = −1) — the
  "request full redraw" routine. Callers: `$D28E` entry (0xD2B2),
  `$12C20` (0x12F3E, after the world-map draw), 0x163E4 (after
  the 0x16360 map draw). So a full redraw is requested once at
  main-loop entry and after each map draw — not every frame.
- `$1BA16` (0x1BA16–0x1BA24): sets only `$FF0098` (map-chunk
  redraw). Callers: 0x1C7F0, 0x231CA (gameplay code).
- Verb actions (inside the `$1F296` executor) set `$FF009A` /
  `$FF009C` / `$FFB08A` as they change the screen (menu
  navigation, dialogue, combat); `$FF009E` is the
  location-picture request (set at 0x1DFF8).
- `$26CCA` (message display, called from `$D28E` entry and from
  `$D28E` case 37) draws through `$11AE4` (loads a `$B86AE`
  record into `$FF1EC0`), `$275B0` (message draw), `$11A1A`
  (tile upload) and waits a VBlank via `$1386A`.

### 6.3 The upload path — blitter, DMA, sprite writers

- **Blitter `$1194A(src, base, rows, cols, yoff, xoff, stride,
  dest)`** (#006, verified): VRAM word = map word + `base`
  (`base` = tileset VRAM tile index plus palette/priority bits:
  `+$2000` pal 1, `+$4000` pal 2, `+$6000` pal 3, `+$8000`
  priority); dest byte address =
  `((r + yoff) * stride + xoff + c) * 2 + dest`, stride in
  **words** (`$40` = 64-wide plane, `$80` = 128-wide). Per row
  it calls `$DC60` (set VRAM write address) and `$D9EE` per
  word. The plane is selected by `dest` and its size by R16.
- **DMA `$DA04(src, dest, count)`** (0xDA04–0xDA91, verified):
  args are a ROM source address (long), a VRAM dest (long) and a
  word count. Sets R15=`$02`; R19 = count low byte, R20 = count
  high byte (DMA length in words); R21/R22/R23 = the source
  address / 2, low/mid/high byte; then the VRAM-write command
  with the DMA bit (`$80` OR'd into the second word) starts the
  transfer, and it polls `$C00004` bit 1 (DMA busy) until clear.
  Only 5 call sites: `$11A7C`, `$11ABC`, `$11B2E` (below),
  0x12EC8 (in `$12C20`), `$1B918` (the map-chunk upload, §6.1).
- **`$11A7C(src, count)`**: DMA-uploads `count` tiles at the
  running cursor `$FF0076` (dest = cursor × 32 bytes, count × 16
  words), returns the old cursor, advances it by `count`.
  **`$11ABC(count, base, src)`**: uploads `count` tiles from
  `src` to VRAM at tile `base` (dest = base × 32).
  **`$11B2E(count, base, src)`**: same with an explicit base.
  The tile data comes from the `$96120`/`$B86AE` records via
  `$1383C`/`$13654` (#006/#017).
- **Sprite writers** (all write at the current sprite-table base
  `$FF8644`, which the scene routines set to `$2400` in Layout G
  or `$4400` in Layout L — so the writers follow the active
  layout):
  - `$11B76`: `$DC60($FF8644)` + 4 zero words — clears one
    8-byte sprite attribute. Called from `$11E06` and `$12C20`.
  - `$11BD8(slot, x, y, ?, ?, ?, tile)`: writes one 4-word
    sprite attribute at `$FF8644 + slot×8`: word 0 = Y, word 1 =
    link + size + (computed from three args), word 2 = tile
    word, word 3 = X. Called from the menu formatter `$138A8`.
  - `$11C4A(slot, ...)`: rewrites only word 1 (size/link) of
    one sprite, at `$FF8644 + slot×8 + 2`.
  - `$11C9A(...)`: writes a rows×cols **grid** of sprite
    attributes starting at `$FF8644`, with per-cell tile math
    and flip reversal from the `$18(a6)` arg bits (`$800`
    flip-H, `$1000` flip-V).
  - Sprite attribute format (verified against the live §7
    snapshot and BlastEm's `vs` dump): word 0 = Y (bits 0–8);
    word 1 = link (bits 0–6), vertical size (bits 8–9),
    horizontal size (bits 10–11) — size 0/1/2/3 = 1/2/3/4
    cells; word 2 = tile index (bits 0–10), flip-H (bit 11),
    flip-V (bit 12), palette (bits 13–14), priority (bit 15);
    word 3 = X (bits 0–8). On-screen coordinates are the
    register value − 128.
- **Name-table word format** (#006, verified): bits 0–10 tile
  index, `0x0800` flip-H, `0x1000` flip-V, bits 13–14 palette,
  bit 15 priority.

### 6.4 Scroll — `$DC16` and the column writer `$16512`

- **`$DC16(a, b, c, d)`** (0xDC16–0xDC5E, verified): writes
  VSRAM words 0–1 = `a, b` (Plane A/B **vertical** scroll) and
  VRAM `$2000` words 0–1 = `c, d` (Plane A/B **horizontal**
  scroll, full-screen values — only the first two H-scroll words
  matter while R11=`$00`). 5 call sites: `$11E06` (0,0,0,0),
  `$12C20` (0,0,0,0), the 0x1702C routine (0,0,0,0), and two
  map-scroll sites (0x166FA, 0x16D6A) that pass computed values
  as `(v, v, h, h)` — both planes scrolled together by the map
  offset.
- **`$16512`** (0x16512–0x1664D, tier 2, doc-pinned): the
  column writer. Sets R15=`$80` (auto-inc 128 = one 64-wide row
  per write), sets the VRAM address from its args, then writes
  32 cells down a column, each word built from the `$1AE98`
  descriptor table plus the tile base `$FF8678`, and restores
  R15=`$02`. Called only from `map_view` (`$1664E`): `$016C1A`
  (scroll-right edge) and `$016C6A` (scroll-left edge). The
  descriptor packs **two tile variants per entry**, selected by
  cell bit 12: low variant = flip bits from descriptor bits 0–1
  and tile 0–63 from bits 2–7; high variant = flips from bits
  8–9 and tile from bits 10–15. Final word = flip bits | tile
  (0–63) | `$FF8678` (a VRAM tile-index base, the
  `gfx_dma_tile_upload` return copied from `$FF867C` at
  `$012DC0`); palette and priority are always 0. 434/512
  descriptor entries have identical variants; 78 differ. Cell
  semantics resolved 2026-11-11 [static] — full layout in
  `docs/maps.md` (chunk cell word: bits 0–8 tile-type index
  0–511, bit 9 height-stack flag, bit 10 step-tile flag,
  bit 11 hazard floor — lava (Temple of Variation, tile 279,
  26 damage), traps (217 scattered cells, 1 damage/step), and
  sensors (8 cells, tile 1) are distinct hazards keyed on the
  location number; the fifteen 71-cell rooms' bit-11 cells are
  inert — bit 12 variant, bits 13–15 height).

### 6.5 Palette — `$170DA` and the loaders

(Already traced in #005/#020; cited here for completeness.)

- **`$11082(table_ptr, slot)`**: loads one 16-word palette from
  the master table at ROM `0x0CC9D8` (31 palettes × 32 bytes)
  into CRAM slot 0–3. It sets the CRAM write address as
  `slot×32` (two-word command: `slot×32 − $4000`, then `$0000`)
  and writes the 16 words via `$D9EE`. Palette index =
  `(table_ptr − 0x0CC9D8) / 32`: `$CCB18` = 10, `$CCC38` = 19,
  `$CCCB8` = 23, `$CCB38` = 11 (world map, code-pinned), `$CCAD8`
  = 8 (all black).
- **`$110D0(slot, index, value)`**: writes one CRAM entry.
  **`$1110A(slot, index)`** → `d0`: reads one CRAM entry (CRAM
  read command, second word `$0020`, then `$D9FA`).
- **`$1225C(palA, palB, step, slot)`**: cross-fades palette A
  to palette B in 9 steps (step clamped to 0–8), interpolating
  each colour channel separately (9-bit BGR word `0BBB0GGG0RRR0`,
  channel masks `$000E`/`$00E0`/`$0E00`).
- **`$170DA`** (0x170DA–0x171D5, verified): the per-frame
  palette routine. Clears `$FF0124` (the "palette refresh
  requested" flag) on entry; computes `$FF0E16 / 18` (the step
  counter divided by 18). By mode `$FF0126`: mode 2 with
  quotient 0 → cross-fade pal 10 (`$CCB18`) → pal 19 (`$CCC38`)
  via `$1225C` with step = (`$FF0E16` % 18) / 2; mode 2 with
  quotient 30 → cross-fade pal 19 → pal 10; mode 1, or mode 2
  with quotient < 30 → load pal 19 slot 0; mode 4 → load pal 23
  (`$CCCB8`) slot 0; default → load pal 10 slot 0. Callers:
  `$2155E` (the world tick, 0x215F6 — gated by `$FF0124 != 0`,
  tested at 0x215DA), `$17860` (0x17976, the location-picture
  draw), and a `bsr` at 0x170C6. `$FF0124` is set to −1 by scene
  code (0x1DC98, 0x1DE24, 0x1E000, 0x21780, 0x2DE7E, 0x30100,
  0x30336); `$FF0126` is set at 0x1DCBA (from `d1`), 0x1DE2C
  (= 2, cross-fade), 0x1E008 (= 0).
- **CRAM word format:** 9-bit BGR, `0BBB0GGG0RRR0`, channel =
  value × 255/7 (#005).

## 7. Live verification (BlastEm, attract screen)

Harness: `tools/test_vdp_harness.s` (264 B assembled), hooked at
`0x35C` (replaces `move.w $C00004,d1`, 6 bytes) with the harness in
the `0xFF` padding at `0xFD0CC`; hook exits use `rts`, never `jmp`
(#021 Q13). The harness snapshots VRAM/CRAM regions into
`$FFD004+` once `$FFC002` decays into [60,70] (~85 frames into the
attract), then never runs again. Test ROM checksums: header
`0xA955`, runtime `0x7C7B5FDB` (`verify-all` passes). The game was
stepped 90 frames (breakpoint at `$4E6`, once per frame) and the
results read back with `p/x`, plus BlastEm's own `vr` (VDP
registers) and `vs` (sprite list) at the same stop. Original ROM
MD5 re-verified unchanged at the end: `30c18fdbe2183f64702ae9f1a45d63f9`.
Re-run note (2026-11-09 verification): some BlastEm launches stall
on the first debugger `continue` (no breakpoint hit, no prompt) —
an intermittent vsync-dialog race at startup; a fresh launch
usually works. If it stalls, kill BlastEm and relaunch rather than
sending a second `c` (a queued second `c` corrupts the next read).

### 7.1 Live registers — the `$A14` layout, confirmed

BlastEm `vr` at frame 90 prints exactly the §3 set:

```
R0=04 (H-int off)  R1=74 (display on, V-int on, Mode 5)
R11=03 (H-scroll per-line)  R12=81 (H40, 320 px)
R2=28 → Scroll A $A000   R3=30 → Window $C000
R4=05 → Scroll B $A000   R5=6E → Sprite $DC00
R13=08 → H-scroll $2000  R15=02 (auto-inc 2)
R16=03 (128×32)          R7=00 (backdrop 0)  R10=01
```

### 7.2 H-scroll table — the `$4E6` zigzag, live

Snapshot at `$FFC002` = 70 (harness `$FFD004` = `0x46`). VRAM
`$2000`, first 16 words:

```
FFB9 0140 0047 0140  FFB9 0140 0047 0140  ...
```

i.e. per line pair `[−X, $140, +X, $140]` with X = 71 =
`$FFC002`+1 (the last `$4E6` write used X = 71, then decremented
to 70). This is exactly the `$4E6` phase-1 write pattern (§8
below): line 2k gets Plane A = −X, Plane B = `$140`; line 2k+1
gets Plane A = +X, Plane B = `$140`. It proves the H-scroll
table is at VRAM `$2000`, the per-line format is **[Plane A,
Plane B] per line**, and the attract title shimmers with a
per-line ±X zigzag on Plane A while Plane B sits at a constant
`$140` (320).

### 7.3 Name table, sprite table, window, CRAM — live

- **Name table VRAM `$A000`, row 0, cols 0–31: all 32 words
  zero.** The top row of the attract name table is blank (the
  title art sits lower). The table address itself is confirmed
  by the `vr` R2/R4 values plus the non-zero content the same
  read found at the other tables.
- **Sprite table VRAM `$DC00`, first 4 attributes** (harness
  `$FFD074+`):

| sprite | words | decoded |
|---|---|---|
| 0 | `00C8 0C01 8201 00D0` | Y=200, link 1, 32×8, tile 513, pal 0, pri 1, X=208 |
| 1 | `00C8 0C02 8205 00F0` | Y=200, link 2, 32×8, tile 517, pal 0, pri 1, X=240 |
| 2 | `00CE 0C03 8209 00D0` | Y=206, link 3, 32×8, tile 521, pal 0, pri 1, X=208 |
| 3 | `00CE 0C04 820D 00F0` | Y=206, link 4, 32×8, tile 525, pal 0, pri 1, X=240 |

  These match BlastEm's own `vs` dump at the same stop
  **word for word** (sprite 0: `X=208(80), Y=200(72),
  Width=32, Height=8, Link=1, Pal=0, Pri=1, Pat=4020` — Pat is
  the tile's VRAM byte address, 513×32 = `$4020`; the parenthesised
  X/Y are the on-screen coordinates, register value − 128).
  All 32 sprites are present in `vs`: two blocks — sprites 0–17
  in 9 rows × 2 columns (X 208/240, Y 200–248, step 6, tiles
  513–581 step 4) and sprites 18–31 in 7 rows × 2 columns
  (X 264/296, Y 220–226, step 1, tiles 585–637 step 4).
  (An earlier draft said 513–677 / 681–821 — wrong; the live `vs`
  dump gives 513–581 / 585–637. Corrected during the #016
  verification.)
  The sprite table is animated during the attract: an earlier
  snapshot at frame ~30 showed the same sprites at Y≈233–236,
  X≈223–243 — the block drifts up-left over the first seconds.
- **Window VRAM `$C000`, 8 words: all zero.** The window table
  is empty in the attract, so the window plane contributes
  nothing there (R17/R18 = 0).
- **CRAM palette 0, 16 words** (one animation phase):
  `F111 F575 F19B FF97 F9F9 F1B1 F5F5 FBBB F555 F5F5 FB53
  F1DF F111 FB53 F9FF FFFF` — 9-bit BGR blues/whites
  (e.g. `F111` = blue, `FFFF` = white). The values are
  animation-phase-dependent: `$4E6` phase 2 rewrites CRAM
  colours directly (§8), and a snapshot at a different phase
  reads different values.
- Harness scalars at the snapshot: `$FFC004` = 15, `$FFC006` =
  0, `$FFC000` = 0 (scroll not done), `$FF8644` = 0, `$FF0076` =
  0, `$FF0126` = 0, `$FF0E16` = 0. `$FF8644`/`$FF0076` are 0 in
  the attract because the sprite-base variable and the tile
  cursor are only set by the game-mode routines (`$12C20` sets
  `$FF8644=$2400`); the attract uses `$DC00` sprites set up by
  the title code, not the `$11BD8` writers.

## 8. (Appendix) The attract scroll `$4E6`

`$4E6` (0x4E6–0x889) is the attract-loop animation driver, called
once per attract iteration (when `$FFC000==0`). Verified by
disassembly; its H-scroll write is verified live in §7.2.

- **Phase 1** (while `$FFC002 >= 0`; `$FFC002` starts at `$96` =
  150, set at 0xCF0 by the title setup): each frame, X =
  `$FFC002`, decrement it; set VRAM write `$60000000` and write
  448 words: per line pair `[−X, $140, +X, $140]` (112
  iterations × 4 words = 224 lines × 2 words). Plane A zigzags
  ±X per scanline; Plane B is a constant `$140` (320).
- **Phase 2** (once `$FFC002 < 0`, gated by the `$FFC006`
  countdown — it runs every other frame): `$FFC004++`; uploads
  `0x240` longs from RAM `$FFD2EA` to VRAM `$4920` (command
  `$49200001` — 72 tiles at tile 585); at `$FFC004` counts 7, 13
  and 20 it writes CRAM colours **directly** (CRAM write
  commands `$C00C0000` etc. with literal values `$A0`, `$4E4`,
  `$A42`, `$E86`, `$8A`, `$CE` — a palette pulse), in 3 variants
  selected by `$FFC00C` (0–2, cycling when `$FFC004` passes 24,
  which also resets `$FFC006=$50`). When `$FFC002 < 0` and
  `$FFC004 == 0`, `$FFC000=$FF` and `$4E6` becomes a no-op.
- The exact visual (which title element shimmers, what the
  `$4920` tile upload animates) is not chased further here — the
  mechanism and the live values are the finding.

## 9. Open items (not solved here)

- **Packed-vs-planar: RESOLVED (#016 §10.1, #23).** The decompressed tile
  bytes are packed 4bpp, 2 px per byte, high nibble first, and the VDP
  consumes them as packed. The Mega Drive VDP's pattern format is packed
  4bpp (8x8 tile = 32 bytes); bitplanar is the SNES, Game Boy and SMS format.
  The earlier "textbook bitplanar" claim was wrong for this system.
- **CRAM R/B order (new, #016 §10.2).** Corrected to
  `r=(w>>1)&7, b=(w>>9)&7` by the test ROM. The world-map sea colour
  (pal 11 code-pinned reads as browns/reds under the corrected
  decoding, vs the blue sea #006 described from the old rendering)
  should be re-verified against a live game CRAM snapshot on the
  world map; the #005 PNGs should be regenerated with the corrected
  palette.
- **`$16512` column writer:** RESOLVED 2026-11-11 [static] — the
  cell semantics, the `$1AE98` descriptor table layout (two tile
  variants per entry, selected by cell bit 12), the `$FF8678` tile
  base, and the exact column/row mapping are traced in `docs/maps.md`
  (column-writer section) and §6.4 above.
- **Tile bases `$FF8674` / `$FF8678`:** `$FF8678` is RESOLVED
  2026-11-11 — it is the `gfx_dma_tile_upload` return (the old VRAM
  cursor = the base tile index), copied from `$FF867C` at `$012DC0`.
  `$FF8674` is RESOLVED 2026-11-11 — it is the VRAM tile-index base
  of the software-rendered room (36×23 = 828 tiles), reserved by
  `sys_counter_add($33C)` at `$012D7E` in `world_map_draw`
  (`$12C20`): the same `$FF0076` allocator the upload returns draw
  from, but allocate-only (no upload attached). In the standard
  scene setup its value is `$38E` (counter starts at `$134` at
  `$012D00`; font 103 + rec 1: 25 + rec 6: 438 + `$24` reserve).
  Its `$1B918` consumer is `redraw_check`: when `$FF0098` is set
  it re-renders the room into `$FF1EC0` via `map_chunk_pos`
  (`$1B950`) and DMA-uploads `$FF1EC0 → VRAM $FF8674×32`
  (`$33C0` words) at `$01B9E8`; the same upload runs once at scene
  setup (`$012EB4`). The room name table is drawn into the window
  plane (VRAM `$1000`, rows 0–22, cols 2–37) by
  `gfx_tilemap_draw` with base `$FF8674` (23 rows × 36 cols,
  `$012E50`; re-drawn by `world_map_redraw`, `$0162FE`). The panel
  routines repaint bands of the same grid via
  `gfx_tilemap_fill_seq`: `gfx_fill_panel_plain` rows 0–11,
  `gfx_fill_panel_flagged` rows 12–17, `text_event_message` rows
  20–22. `$FF8674` (window-plane room render, `$38E`) and
  `$FF8678` (Plane A scrolling-map tileset, `$72A`) are two
  different tile regions, not a duplicate. `$38E` is now
  live-confirmed (2026-11-11): 3 breakpoint hits at `$01B9E8`
  (`redraw_check`'s `dma_upload`), Buc save state, `$FF8674` = 0x38E
  every time, d0 = $71C0 = $38E×32; `$FF8648` = $36A, `$FF8678` =
  $72A, `$FF867A` = $6CA at the same hits.
- **`$FF8648` = `$36A`: a shared 36-tile VRAM slot holding the
  currently-active sprite record's tiles (palette 3), reloaded per
  context** (pinned 2026-11-11, static; value live-confirmed above).
  Reserved by `sys_counter_add($24)` at `$012D60–$012D6C`; a `$B86AE`
  record is 1184 B = 32 B palette + 36 tiles, and `tile_record_load`
  (`$011AE4`) uploads exactly 36 tiles (hardcoded `0x24`) from
  `$FF1EE0` to VRAM `vram_base×32` plus the record's palette into slot
  `pal_index`. Four `tile_record_load` sites pass `$FF8648` (all pal
  3): rec 38 in the dialogue path (`$0120EC`), rec 23 at scene setup
  (`$012EF2`), variable `$FF0E78` after `palette_fade` (`$01796E`),
  variable `-$4(a6)` at `$026D6E` (guarded by `$FF0E78 != -$4(a6)`,
  sets `$FF0E78` first). Six sites build the tilemap word `$E000 |
  $FF8648` (palette 3, priority 1) to draw those tiles: `$012082`,
  `$016372`, `$0195CA`, `$0275DE`, `$029140`, `$0163AC`. `$FF0E78` is
  the currently-loaded record index for this slot.
- **R18=`$94` window position** (0x1297C, inside `$123B0`):
  window down, V position 20 — the intro's window placement.
  Role not traced.
- **`$4E6` phase 2 visuals:** the `$FFD2EA`→VRAM `$4920` tile
  upload and the three `$FFC00C` CRAM-animation variants are
  traced as mechanism only; what they animate on screen, and
  the second sprite block's purpose (sprites 18–31, Y stepping
  1 px), are not identified.
- **`$D28E` case 23's writer** is still not found (no literal
  `move.b #$17` into the command slot) — open since #021.
- The `$DC60` call sites that take computed addresses (21 of
  23) were not individually decoded; the two immediate ones
  pass `$4000` (VRAM `$4000` = tile 512, in the `$170DA`/`$17860`
  area).

## 10. Issue #016 — packed-vs-planar resolution, palettes, sprites (done 2026-11-09)

### 10.1 The packed-vs-planar paradox — RESOLVED (packed is real)

**Resolution: the decompressed tile bytes ARE packed, 2 px/byte, high
nibble first, and the VDP consumes them as packed. There is no
packed→planar conversion anywhere in the ROM, because none is
needed.** The paradox is resolved by disproving the textbook premise,
not by finding a conversion routine.

Evidence chain (all live, all in this issue):

1. **Upload path is verbatim (disassembly, #015 §6.3).** `$1383C` →
   `$11A7C` → `$DA04` DMA and `$11AE4` → `$11B2E` → `$DA04` DMA copy
   the decompressed bytes to VRAM with no transformation. The
   `$13654` dispatcher, the `$11ABC`/`$11B2E` uploaders, and the
   `$DA04` DMA routine are all verbatim. No conversion routine exists
   on that path (and a full-ROM search finds no packed→planar
   converter feeding it).
2. **Live VRAM snapshot (harness 2, `tools/test_tiles2_harness.s`,
   230 B, hook `$35C`, `rts` exit).** The decode buffer at `$FF1EC0`
   holds tile 93 as `1111 1111 FFFF FFFF 1F11 1F11 1F1F 1F1F 1F1F
   1F11 1F11 1F1F FFFF FFFF 1111 1111`; VRAM tile `0x700+93` holds
   the **byte-identical** 32 bytes. The bytes that arrive in VRAM
   are the packed bytes. (Harness 1, `test_tiles_harness.s`, had a
   one-word VRAM-read shift — the first VRAM read after setting the
   address returns the word **at** that address, no dummy word;
   harness 2 corrected this.)
3. **Minimal VDP test ROM (`.scratch016/vdp_test.s`/`.gen`, greyscale
   palette).** Tile 93's packed bytes are written to VRAM tile 1 and
   an interleaved planar copy of the same tile to VRAM tile 2; both
   are displayed on Plane A. Tile 1 displays as the intended glyph
   (**64/64 pixels** match the packed reading, greyscale-confirmed);
   tile 2 displays as the **packed reading of the planar bytes**
   (vertical bars). The VDP consumes the bytes as packed. A planar
   copy does not display as the glyph — so if the game stored
   planar data, its graphics would be bars, and they are not.
4. **The `$AB2` generated tiles are packed by construction (§10.3).**
   The generator writes longwords `0x66666666` / `0x44444444` /
   `0x55555555` — each byte is a pair of identical nibbles, i.e.
   packed pixels — and the game displays them correctly as the
   attract logo. A bitplanar format would make those bytes
   meaningless.

**Resolved (#23).** The earlier "Genesis VDP pattern format is bitplanar"
description was wrong: the Mega Drive VDP uses packed 4bpp, the same as this
game's data (see Sega Mega Drive VDP documentation and plutiedev). The live
VRAM and test ROM evidence in §10.1 stands.

**Test-ROM gotchas (recorded for reuse).** BlastEm faults on a TMSS
write to `$A14000` for an unrecognised SHA1 — omit it. R15 must be
`0x02` for sequential word writes (R15=`0x01` overlaps them and
garbles VRAM/CRAM — this caused a solid-blue screen). VDP control
word for CRAM write is `0xC0000000`, VRAM write `0x4000|addr`
(word2 = addr>>14).

### 10.2 Palettes — the master table (31 palettes, corrected decoding)

**Correction 1 — the table's boundary (count unchanged).** The master
table at ROM `0x0CC9D8` holds palettes 0–30 (31 × 32 B = 992 B,
ending at `0x0CCDB8`) — #005's count of 31 was correct. The new
finding is what comes next: the 32nd 32-byte slot (slot 31, ROM
`0x0CCDB8`) is **not** a palette, it is ASCII menu text — `MAIN`,
`Inven…`, `Spells`, `Party`, `Search`, `Map`, `Camp`, `System`,
`FIGHT`, `Flee` — the `$D28E` verb/command menu table. (An earlier
draft of this section said "30 palettes" — an off-by-one in counting
0–30; corrected during verification.)

**Correction 2 — the CRAM channel order (R/B swap).** #005 and
`tools/render_tiles.py` decoded the CRAM word as
`r=(w>>9)&7, g=(w>>5)&7, b=(w>>1)&7`. That is **wrong: R and B are
swapped**. The correct order is `r=(w>>1)&7, g=(w>>5)&7,
b=(w>>9)&7` (word layout `0BBB0GGG0RRR0` — B at bits 9–11, R at
bits 1–3, which is what the `render_tiles.py` docstring already
said; the code contradicted it). Proof: a colour variant of the
minimal VDP test ROM (same code as `.scratch016/vdp_test.s`, only
the `pal:` table replaced: CRAM[1] = `0x0E00`, CRAM[5] = `0x00E0`,
CRAM[7] = `0x000E`, CRAM[15] = `0x0EEE`) shows pixel value 1 as
pure **blue** (0,0,255) and pixel value 5 as pure **green** — so
bits 9–11 are blue and bits 1–3 are red. Evidence: the crops
`.scratch016/vdp_tile_left.png` / `vdp_tile_right.png` (blue glyph
vs green bars — the two wrap instances of the tile pair), and an
independent re-run during verification with the same colour palette
counted 408 saturated-blue pixels and 0 saturated-red pixels. (The
preserved `vdp_test.s` is the greyscale variant used for the §10.1
display test.) Corroborated by the `$B86AE` rec 0 embedded palette, which
decodes to warm browns/red (skin tones) only under the corrected
order; under the old order it is all blues/greens. **`render_tiles.py`
`md_word_to_rgb` is fixed in this issue; the #005 PNGs in
`disasm/graphics/` (rendered with the old order) have red and blue
swapped — shapes correct, colours not — and are flagged for
regeneration, not silently trusted.**

The full table below uses the corrected decoding (channel ×255/7).
Words are ground truth; RGB is the corrected reading. Uses are from
code where pinned, otherwise best-fit from #005/#006 (marked `?`).

| pal | words (16 × 9-bit BGR) | RGB (corrected) | use |
|----:|------------------------|-----------------|-----|
| 0 | `0000 0A00 00A0 0AA0 000A 0A0A 004A 0AAA 0444 0E44 04E4 0EE4 044E 0E4E 04EE 0EEE` | `#000000 #0000B6 #00B600 #00B6B6 #B60000 #B600B6 #B64800 #B6B6B6 #484848 #4848FF #48FF48 #48FFFF #FF4848 #FF48FF #FFFF48 #FFFFFF` | RGB cube; slot 1 on title (`$11E06`) |
| 1 | `0000 0000 0444 0888 0AAA 0CCC 0024 0026 0046 0048 0268 028A 0E62 000C 008E 0EEE` | `#000000 #000000 #484848 #919191 #B6B6B6 #DADADA #482400 #6D2400 #6D4800 #914800 #916D24 #B69124 #246DFF #DA0000 #FF9100 #FFFFFF` | default for renders; grey-brown ramp |
| 2 | `00E0 0000 000C 004E 008E 00AE 02CE 04EE 0E40 0E60 0E80 0EA0 0EC0 0CC2 0CC8 0EEE` | `#00FF00 #000000 #DA0000 #FF4800 #FF9100 #FFB600 #FFDA24 #FFFF48 #0048FF #006DFF #0091FF #00B6FF #00DAFF #24DADA #91DADA #FFFFFF` | ? (colour 0 is green) |
| 3 | `00EE 0000 0020 0060 0080 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0000 0088 06EE 0EEE` | `#FFFF00 #000000 #002400 #006D00 #009100 #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #000000 #919100 #FFFF6D #FFFFFF` | ? (mostly magenta) |
| 4 | `00E0 0000 0444 0666 0888 0AAA 0CCC 0EEE 0222 0444 0666 0888 0AAA 0CCC 0EEE 0E0E` | `#00FF00 #000000 #484848 #6D6D6D #919191 #B6B6B6 #DADADA #FFFFFF #242424 #484848 #6D6D6D #919191 #B6B6B6 #DADADA #FFFFFF #FF00FF` | ? (grey ramp ×2) |
| 5 | `00E0 0000 0444 0666 0888 0AAA 0CCC 0EEE 0000 0444 0666 0888 0000 0088 06EE 0EEE` | `#00FF00 #000000 #484848 #6D6D6D #919191 #B6B6B6 #DADADA #FFFFFF #000000 #484848 #6D6D6D #919191 #000000 #919100 #FFFF6D #FFFFFF` | ? (grey ramp) |
| 6 | `0EE0 0000 0A26 0E40 0E80 0880 00C0 00E8 00EE 008E 004E 004C 000A 0006 00AE 00CE` | `#00FFFF #000000 #6D24B6 #0048FF #0091FF #009191 #00DA00 #91FF00 #FFFF00 #FF9100 #FF4800 #DA4800 #B60000 #6D0000 #FFB600 #FFDA00` | ? (rainbow) |
| 7 | `0000 0000 066C 046A 044A 0248 0028 0026 0006 0004 0E40 04EE 028C 0AAA 0CCC 0EEE` | `#000000 #000000 #DA6D6D #B66D48 #B64848 #914824 #912400 #6D2400 #6D0000 #480000 #0048FF #FFFF48 #DA9124 #B6B6B6 #DADADA #FFFFFF` | ? |
| 8 | all `0000` | all `#000000` | ALL ZERO (black) |
| 9 | all `0EEE` | all `#FFFFFF` | ALL WHITE |
| 10 | `0000 0A00 0C60 0080 0EA0 02C2 0004 0444 04E4 0666 0028 0AAA 044E 0000 04EE 0EEE` | `#000000 #0000B6 #006DDA #009100 #00B6FF #24DA24 #480000 #484848 #48FF48 #6D6D6D #912400 #B6B6B6 #FF4848 #000000 #FFFF48 #FFFFFF` | title, slot 0 (`$11E06`); cross-fade source (`$170DA` mode 2) |
| 11 | `0000 0000 0666 0222 0024 044A 0026 0448 0008 046A 0888 028A 066C 0444 0246 04EE` | `#000000 #000000 #6D6D6D #242424 #482400 #B64848 #6D2400 #914848 #910000 #B66D48 #919191 #B69124 #DA6D6D #484848 #6D4824 #FFFF48` | world map — code-pinned (#006) |
| 12 | `0000 0000 0024 0008 0224 0226 0002 000A 0248 0268 046C 028A 048C 044A 088C 04AA` | `#000000 #000000 #482400 #910000 #482424 #6D2424 #240000 #B60000 #914824 #916D24 #DA6D48 #B69124 #DA9148 #B64848 #DA9191 #B6B648` | ? |
| 13 | `00A0 0000 0008 00EE 00CC 008E 006E 004E 002E 000C 08EE 0088 0006 0E6E 0E6E 0EEE` | `#00B600 #000000 #910000 #FFFF00 #DADA00 #FF9100 #FF6D00 #FF4800 #FF2400 #DA0000 #FFFF91 #919100 #6D0000 #FF6DFF #FF6DFF #FFFFFF` | fan-map colour match (#006) |
| 14 | `0E0E 0000 0222 0444 0666 0888 0026 0048 046A 068C 0040 0060 0080 00A0 00EE 0EEE` | `#FF00FF #000000 #242424 #484848 #6D6D6D #919191 #6D2400 #914800 #B66D48 #DA916D #004800 #006D00 #009100 #00B600 #FFFF00 #FFFFFF` | night landscape best-fit (#006) |
| 15 | `0000 00E0 0EEC 0ECA 0EA8 0E86 0E64 0E42 0E8E 0E8E 0266 0488 06AA 08CC 0AEE 0EEE` | `#000000 #00FF00 #DAFFFF #B6DAFF #91B6FF #6D91FF #486DFF #2448FF #FF91FF #FF91FF #6D6D24 #919148 #B6B66D #DADA91 #FFFFB6 #FFFFFF` | ? |
| 16 | `0000 00E0 0020 0060 0080 0024 0240 0460 0680 08A0 0AC0 0CE0 00E0 00E0 0EEC 0EEE` | `#000000 #00FF00 #002400 #006D00 #009100 #482400 #004824 #006D48 #00916D #00B691 #00DAB6 #00FFDA #00FF00 #00FF00 #DAFFFF #FFFFFF` | ? |
| 17 | `0404 0000 0222 0444 0666 0888 0AAA 0E8E 0644 0866 0A88 0CAA 06AA 00EE 0EEE 0E8E` | `#480048 #000000 #242424 #484848 #6D6D6D #919191 #B6B6B6 #FF91FF #48486D #6D6D91 #9191B6 #B6B6DA #B6B66D #FFFF00 #FFFFFF #FF91FF` | archway map pal (#006) |
| 18 | `0E0E 0000 0000 0C20 0A00 0666 0040 0080 0EA4 0800 0020 0400 0E80 0EEE 0C40 0200` | `#FF00FF #000000 #000000 #0024DA #0000B6 #6D6D6D #004800 #009100 #48B6FF #000091 #002400 #000048 #0091FF #FFFFFF #0048DA #000024` | ? |
| 19 | `0000 0200 0400 0420 0820 0640 0204 0000 0640 0200 0202 0824 0406 0000 0844 0A66` | `#000000 #000024 #000048 #002448 #002491 #00486D #480024 #000000 #00486D #000024 #240024 #482491 #6D0048 #000000 #484891 #6D6DB6` | cross-fade target (`$170DA` mode 2, `$1225C`) |
| 20 | `0000` then 15 × `0EEE` | `#000000` then 15 × `#FFFFFF` | mostly white |
| 21 | `0000 0A00 0C44 0000 0E88 0000 0000 0C44 0C44 0C66 0000 0EAA 0C44 0000 0EEE 0EEE` | `#000000 #0000B6 #4848DA #000000 #9191FF #000000 #000000 #4848DA #4848DA #6D6DDA #000000 #B6B6FF #4848DA #000000 #FFFFFF #FFFFFF` | ? |
| 22 | `0000 0004 000A 000A 006E 000E 0004 0008 00AE 0006 0008 002E 000E 0000 04EE 0EEE` | `#000000 #480000 #B60000 #B60000 #FF6D00 #FF0000 #480000 #910000 #FFB600 #6D0000 #910000 #FF2400 #FF0000 #000000 #FFFF48 #FFFFFF` | ? |
| 23 | `0000 0A00 0C60 0680 0EA0 0CC2 0A04 0E44 0EE4 0E66 0A28 0EAA 0E4A 0000 0ECC 0ECC` | `#000000 #0000B6 #006DDA #00916D #00B6FF #24DADA #4800B6 #4848FF #48FFFF #6D6DFF #9124B6 #B6B6FF #B648FF #000000 #DADAFF #DADAFF` | ? |
| 24 | `0000 0E88 0ECA 0AEA 0ECA 0AEA 088A 0AAA 0CEC 0AAA 0ACE 0CCC 0CCE 0888 0CEE 0EEE` | `#000000 #9191FF #B6DAFF #B6FFB6 #B6DAFF #B6FFB6 #B69191 #B6B6B6 #DAFFDA #B6B6B6 #FFDAB6 #DADADA #FFDADA #919191 #FFFFDA #FFFFFF` | ? |
| 25 | `0000 0E40 0E62 0EA2 0EC4 0EE6 0000 00E0 000E 0222 0444 0400 0888 0AAA 0CCC 0EEE` | `#000000 #0048FF #246DFF #24B6FF #48DAFF #6DFFFF #000000 #00FF00 #FF0000 #242424 #484848 #000048 #919191 #B6B6B6 #DADADA #FFFFFF` | ? |
| 26 | `0E0E 0000 0022 0066 0088 00CC 00EE 0EEE 0200 0600 0ECA 0C00 0E00 00E0 0E82 0E0E` | `#FF00FF #000000 #242400 #6D6D00 #919100 #DADA00 #FFFF00 #FFFFFF #000024 #00006D #B6DAFF #0000DA #0000FF #00FF00 #2491FF #FF00FF` | ? |
| 27 | `0000 0000 0AAC 0CAA 088A 0A88 0666 0444 00CC 0088 0044 0022 000E 0060 0080 00E0` | `#000000 #000000 #DAB6B6 #B6B6DA #B69191 #9191B6 #6D6D6D #484848 #DADA00 #919100 #484800 #242400 #FF0000 #006D00 #009100 #00FF00` | castle map pal (#006) |
| 28 | `0E0E 0E00 0E22 0E66 0EAA 0ECC 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E` | `#FF00FF #0000FF #2424FF #6D6DFF #B6B6FF #DADAFF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF` | ? (mostly magenta) |
| 29 | `0E0E 000A 000E 046E 088E 0CCE 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E 0E0E` | `#FF00FF #B60000 #FF0000 #FF6D48 #FF9191 #FFDADA #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF #FF00FF` | ? (mostly magenta) |
| 30 | `00E0 0000 0222 000E 0400 0800 0A00 0666 0888 0446 0668 0E22 0000 000A 0444 0EEE` | `#00FF00 #000000 #242424 #FF0000 #000048 #000091 #0000B6 #6D6D6D #919191 #6D4848 #916D6D #2424FF #000000 #B60000 #484848 #FFFFFF` | starfield map pal (#006) |

Loader: `$11082(table_ptr, slot)` → 16 words into CRAM
(`$D9E2`/`$D9EE`); `$170DA` cross-fades (mode 2: pal 10↔19 via
`$1225C`, 9 steps). Pal 8 all-zero, pal 9 all-white, pal 20
mostly-white — these are fade/clear sentinels, not scene palettes.

### 10.3 Sprite patterns — two sources, neither is a plain `$DD5C` tile record

The task's premise ("sprite pattern from a `$DD5C` record") is only
half right. There are two sprite-pattern sources, and the attract
sprites — the ones the issue file meant — are **not** `$DD5C`
records at all.

**A. The attract sprites (tiles 513–584) are GENERATED by `$AB2`,
not decompressed.** `$AB2` (0xAB6–0xB28, inside `$A14`, called from
0xAA2) builds 72 tiles in a RAM buffer at `$FFC0EA` and CPU-copies
them to VRAM `$4020` (tile 513; 576 longwords = 2304 B = 72 tiles).
The generator reads run-length bytes from the byte table `$D92`
and, for each run, writes longwords `0x66666666` / `0x44444444` /
`0x55555555` into the buffer at stride 32 (`d6 += 32` per longword,
8 longwords per tile) — i.e. the generated bytes are packed pixel
pairs by construction (each byte is two identical nibbles). The
attract sprite table (§7.3) points at these tiles: sprite 0 is
tile 513 (`Pat=$4020`, VRAM byte address = tile × 32 = 513×32 =
`$4020`), and all 32 sprites use tiles 513–637 step 4 — sprites 0–17
(tiles 513–581) are the `$AB2`-generated tiles; sprites 18–31
(tiles 585–637, 7 rows × 2 columns, Y stepping 1 px) sit past the
generated range, so their pattern source is open (tile 585 is the
`$FFD2EA` buffer uploaded by `$4E6` phase 2; tiles 589–637 are
unaccounted — see §10.5). (An earlier draft said "513–677" — a
transcription slip; the live `vs` dump gives 513–637. Corrected
during verification.) A Python simulation of `$AB2`
reproduces the live VRAM tiles exactly (tiles 513–516, 564–567
verified against harness 1's snapshot). The generated tiles are
rendered in `.scratch016/gen_packed.png` (packed) vs
`.scratch016/gen_planar.png` (planar = noise) — the packed render
is the dithered logo; the planar render is bars. **Note:** that
scratch PNG was rendered with the old (R/B-swapped) palette; its
shapes are correct, its colours are not.
`$FFD2EA` is a separate zero buffer, uploaded by `$4E6` phase 2 to
VRAM `$4920` (tile 585).

**B. The `$B86AE` records ARE the `$DD5C` sprite-pattern sets.**
Each is `[32-byte embedded palette][36 tiles]` (1152 B of packed
tiles). Rendered in this issue (corrected palette):
`disasm/graphics/016_portrait_b86ae_rec00_full.png` — rec 0, 36
tiles, 6×6, scale 8, its own embedded palette (words `0080 0000
0AAA 0666 0444 0008 0068 0048 0046 0026 0024 0004 0002 0088 00AA
0EEE` → warm browns/reds, i.e. skin tones under the corrected
decoding). Tile-index → pattern-address mapping: `$11AE4` loads
the record's 36 tiles to a VRAM tile base (via `$11B2E` → `$DA04`
DMA, §6.3); the sprite attribute word 2 (tile+flip+pal+pri, §7.3)
selects the tile within that base, and the pattern's VRAM byte
address is tile × 32. The portrait is a face — it renders
coherently only packed, which is the tile-data confirmation (§10.4).

### 10.4 Tile-data confirmation — full tilesets, correct palettes

Rendered in this issue (all packed layout, corrected palette,
`tools/render_tiles.py`):

- `disasm/graphics/016_font_rec00_full.png` — `$96120` rec 0, the
  full ASCII font, **103 tiles** (3296 B decompressed), 16 cols,
  scale 8, pal 1. The font + "MORE" UI text; coherent only packed.
- `disasm/graphics/016_terrain_rec06_full.png` — `$96120` rec 6,
  **438 tiles** (14016 B decompressed), 16 cols, scale 8, pal 1.
  The terrain set.
- `disasm/graphics/016_portrait_b86ae_rec00_full.png` — `$B86AE`
  rec 0, 36 tiles, embedded palette (see §10.3B).

No `$96120`/`$B86AE` record renders as noise under the packed
interpretation. The stale premise is corrected: raw ROM
`0x060000–0x093FFF` is **not** tiles (it is not raw tiles in any
layout; the `$96120` streams start at `0x09638C`, and
`0x068300–0x093FFF` is ~172 KB of unknown data, #017). The real
tiles are the `$DD5C` records in the `$96120` table (62 records,
sources `0x09638C–0x0B86AE`) and the `$B86AE` table (90 records),
all decompressed clean by #005 (62/62 + 90/90).

### 10.5 What stays open (from #016)

- (resolved #23) The "bitplanar" claim: packed 4bpp is the Mega Drive VDP format.
- Pal 11 / pal 13 sea-colour question: under the corrected decoding
  the world-map palette (pal 11, code-pinned) reads as browns/reds
  rather than the blue sea #006 described from the old (swapped)
  rendering. The sea colour should be re-verified against a live
  game CRAM snapshot on the world map; the #006 "fan colours match
  pal 13" claim was itself made under the old decoding.
- Sprite tiles 589–637 (sprites 18–31) have no identified pattern
  source — only tile 585 is accounted for (`$FFD2EA` via `$4E6`
  phase 2).
- The `#005` PNGs in `disasm/graphics/` (rendered with the old
  R/B-swapped palette) should be regenerated with the corrected
  `render_tiles.py`.
- `$D28E` case-23 writer, R18=`$94`, `$4E6` phase-2 visuals — carried
  from §9. ($16512 cell semantics and the `$FF8674`/`$FF8678` tile
  bases are resolved — see §6.4 / §8.)

## Files

- `docs/graphics.md` (this file) — §10 added for #016
- `tools/test_tiles_harness.s`, `tools/test_tiles2_harness.s`,
  `tools/test_tiles3_harness.s`, `tools/test_tiles4_harness.s` —
  the #016 VRAM-snapshot harnesses (harness 2 is the one that
  proved the packed upload; harness 4 hooks `$D292`, not yet run —
  its trigger design may not fire without input)
- `.scratch016/vdp_test.s` / `.scratch016/vdp_test.gen` — the
  minimal VDP test ROM (packed vs planar, greyscale + colour
  palettes) that proved the VDP consumes packed bytes and the
  CRAM R/B order
- `tools/render_tiles.py` — `md_word_to_rgb` corrected (R/B swap),
  paradox docstring updated to RESOLVED
- `issues/016-tiles-sprites-palettes.md` — marked done (with the
  stale first bullet corrected)
- `disasm/graphics/016_font_rec00_full.png`,
  `disasm/graphics/016_terrain_rec06_full.png`,
  `disasm/graphics/016_portrait_b86ae_rec00_full.png` — the #016
  full-tileset renders (corrected palette)

## LZSS stream check (2026-11-11, `tools/lzss_check.py`, read only)

- `$96120` table (base `0x09638C`): 62 of 62 type-1 records decode to their
  declared length; last stream ends `0x0B86AE`.
- `$B86AE` table (90 records, `0x0B86AE–0x0B8A31`), streams base `0x0B8A32`:
  90 of 90 type-1 records decode to their declared length; last stream ends
  `0x0CC9D8`.
- Correction: `disasm/text/README.md` lists the `$B8A32` table with base
  `$B86AE`, which is swapped. The table is at `0x0B86AE` and the streams base is
  `0x0B8A32`.

The decoder is the documented `$DD5C` format (32-bit LE length, mask bytes,
12-bit offset, 4 KB ring pre-filled with 0x20). A clean length match on every
record is strong evidence, and it covers the whole `lzss-stream` span.

**Live:** the game's own `$DD5C` decodes all 404 records live
(62 `$96120` + 90 `$B86AE` + 252 `$43850`), output byte-sum-identical to
the static decode, 404/404, 0 mismatches — validating `tools/dd5c.py`
and `tools/lzss_check.py` live. (A single record-0 call had already
matched the static decode on its first 256 bytes, checksum `0x3CA`.)
