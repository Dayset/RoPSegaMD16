# Graphics — VDP registers + VRAM layout (issue #015)

Written 2026-11-09 (agent session, no ROM in VM) entirely from
verified repo evidence: `docs/architecture.md` (#003/#020),
`docs/maps.md` (#006), `disasm/graphics/README.md` (#005),
`tools/render_tiles.py`. Anything not in those sources is marked
**open**, not guessed. Audio lives in `docs/sound.md` (#018).

## 1. VDP register sets — verified

Three distinct register configurations are proven, plus the game
setup in `$11E06`. Register writes go to `$C00004`; the boot loader
steps register numbers with `add.w #$100` from base `$8000`.

### 1a. Boot table at `0x28E` (108 bytes of data at `0x28E`, written by `0x200`)

| Reg | Value | Meaning (hardware) |
|---|---|---|
| R0 | `$04` | H-int enable bit = 0 → HBlank never fires |
| R1 | `$14` | Display OFF (bit 6 = 0), V-int off, DMA on |
| R2 | `$30` | Plane A base `$C000` |
| R3 | `$3C` | Window base `$F000` |
| R4 | `$07` | Plane B base `$E000` |
| R5 | `$6C` | Sprite table base `$D800` |
| R6/R8/R9 | `$00` | — |
| R7 | `$00` | Background colour palette 0, colour 0 |
| R10 | `$FF` | H-int line count (irrelevant, H-int off) |
| R11 | `$00` | Full-screen vertical scroll, no H-scroll split |
| R12 | `$81` | H40 (320 px), no shadow/highlight |
| R13 | `$37` | H-scroll table base `$DC00` |
| R14 | `$00` | — |
| R15 | `$01` | Auto-increment 1 at boot (later sets use 2) |
| R16 | `$01` | Planes 64×32 |
| R17/R18 | `$00` | Window position |
| R19/R20 | `$FF` | DMA length (used by the VRAM fill) |
| R23 | `$80` | DMA mode = fill |

Boot then DMA-fills VRAM with `$0000`, clears CRAM (32 longs to CRAM
address 0) and VSRAM (20 longs), silences the PSG (`9F BF DF FF` to
`$C00011`), and parks the Z80 (see `docs/sound.md`).

### 1b. Display-on sequence (`0x2FA` stage)

- `#$8134` after the first VBlank wait: R1 = `$34` — display still
  blank (bit 6 = 0), V-int + DMA on.
- `$A14` (second set, different layout — see §2) runs, then
  `#$8174`: R1 = `$74` — **display ON** (bit 6 = 1).

### 1c. `$A14` second set (from `docs/architecture.md`)

Packed writes include `$8004, $8134, $8228, $8330, …`: Plane A
`$A000`, Window `$C000`, Plane B `$A000`, sprite table `$DC00`,
H-scroll `$2000`, R16 = `$03` (128×32 planes), R10 = `$01`; then
64 KB VRAM + CRAM cleared via `$AB2`.

### 1d. `$4323C` tail writes — PARTIAL / open

Issue #015 names "$4323C tail writes" as a set to document. The repo
evidence does **not** support that framing: `$4323C` is the
save/EEPROM validation routine (`docs/architecture.md` §$4323C) and
no VDP register writes are attributed to it in any committed doc.
Its tail behaviour that IS documented is the byte-sum validation of
the `$FF016A` buffer and its return value (see
`docs/save-validation.md`). **This acceptance sub-item is recorded
as not evidenced — likely a stale issue note from before #003
identified `$4323C`.** Do not invent a register set for it.

### 1e. Game setup `$11E06` (#020)

Writes (via `$D9E2`) R0=`$04`, R1=`$34`, R2=`$00`, R3=`$04`,
R4=`$00`, R5=`$12`, R13=`$08`, R7=`$00`, R10=`$FF`, R11=`$00`… —
a per-screen reconfiguration (plane bases move; the dump in
`docs/architecture.md` cuts off at 0x78 bytes with one mis-decode).
Full per-screen register sets remain open.

## 2. VRAM layout — verified pieces, honest gaps

VRAM is 64 KB. Name-table bases are register-derived, so the layout
**changes between boot and game configurations**:

| Region | Boot (`0x28E`) | `$A14` set | Evidence |
|---|---|---|---|
| Plane A name table | `$C000` | `$A000` | R2 `$30` / `$28` |
| Plane B name table | `$E000` | `$A000` | R4 `$07` / (shared, per arch. doc) |
| Window | `$F000` | `$C000` | R3 `$3C` / `$30` |
| Sprite table | `$D800` | `$DC00` | R5 `$6C` / … |
| H-scroll table | `$DC00` | `$2000` | R13 `$37` / `$08`-family |
| Pattern (tile) data | uploaded per screen | uploaded per screen | `$11ABC`/`$11A7C` DMA, §3 |

- Plane size: 64×32 cells at boot (R16=`$01`); `$A14` uses 128×32
  (R16=`$03`); the `$1194A` blitter's stride is in **words** —
  `$40` = 64-wide plane, `$80` = 128-wide plane (`docs/maps.md`).
- The blitter selects the plane by `dest`: `$0000` = plane B at
  R4=0, `$2000` = plane A at R2=8 in the map-drawing configuration
  (`docs/maps.md`) — i.e. bases are runtime values, not constants.
- Scroll values: the attract animation writes H-scroll values to
  VRAM `$2000` via `$4E6` (entry path, `docs/architecture.md`).
  Per-frame scroll updates in gameplay are **open**.
- Tile uploads: `$1383C(index)` decompresses a `$96120` record;
  `$11ABC(count, base, src)` uploads `count` tiles to VRAM at
  `base`; `$11A7C`/`$11B2E` feed the `$DA04` DMA verbatim
  (`docs/maps.md`, `disasm/graphics/README.md`).

## 3. Per-frame draw dispatch — CORRECTED (issue text is stale)

Issue #015 asks for the draw dispatch "traced from VBlank
`jsr $EB772`". #003 proved that premise wrong: **`$EB772` is the
sound tick only** (`docs/architecture.md` §$EB772, correcting
`docs/overview.md`). The VBlank handler `0x1272` does exactly:
frame counter `$FF0010++`, joypad port-1 read + debounce/queue,
`jsr $EB772`. **No graphics work happens in VBlank.**

Where drawing actually happens (verified pieces):
- `$1B918` — per-frame redraw checker, called twice per `$D28E`
  main-loop iteration (head and tail) (`docs/architecture.md` #020).
- `$1194A` blitter + `$DC60`/`$D9EE` per-row VDP writes for maps.
- `$170DA` — palette loads/cross-fades from `$CCC38`/`$CCB18`/`$CCCB8`
  via `$11082`/`$1225C`, driven by `$2155E` world tick flags.
- The full draw list (sprite table upload site, per-frame plane
  update order) is **open** — it is main-loop work for a future
  trace, not VBlank work.

## 4. The packed-vs-planar paradox (carried from #005)

Decompressed tiles are **packed** (2 px/byte, high nibble first —
proven by coherent renders), yet the DMA upload path shows no
packed→planar conversion and the game displays correctly on
hardware/emulator. Unresolved here; it constrains #016 and the
#024 exporter (reproduce what the game displays). See
`docs/tiles-sprites-palettes.md`.

## 5. Runtime VDP capture (2026-11-09, session #3 — BlastEm debugger, ORIGINAL ROM)

Method: BlastEm 0.6.3.4 under Xvfb, debugger driven over a PTY
(`blastem -d` on a scratch copy of the verified ROM). Register
state read with the debugger's `vr` at breakpoints on the setup
routines; screens stepped deterministically with `a 1272`
(advance to next VBlank handler). Frame counts below are
$FF0010 VBlank counts relative to $14FB6 entry where noted.
Everything in this section was observed, not inferred.

### 5a. Per-screen register sets — captured

| # | Screen state (breakpoint) | R1 | A | Win | B | SAT | HScr | R11 | Size |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Boot table just written (0x242) | $14 off | $C000 | $F000 | $E000 | $D800 | $DC00 | 0 | 64×32 |
| 2 | After $A14 set (0x334) | $34 off | $A000 | $C000 | $A000 | $DC00 | $2000 | **3 line** | 128×32 |
| 3 | Boot animation, display on (0x388) | $74 on | $A000 | $C000 | $A000 | $DC00 | $2000 | 3 line | 128×32 |
| 4 | $11E06 entry (pre-setup) | $34 off | $A000 | $C000 | $A000 | $DC00 | $2000 | 3 line | 128×32 |
| 5 | $14FB6 entry (post-$11E06) | $74 on | $0000 | $1000 | $0000 | $2400 | $2000 | 0 full | 128×32 |
| 6 | Intro screen A (+600 VBlanks) | $74 on | $2000 | $F000 | $0000 | $4400 | $4000 | 0 full | 128×32 |
| 7 | Intro screen B (+1800 VBlanks) | $74 on | $2000 | $F000 | $0000 | $4400 | $4000 | **3 line** | 128×32 |
| 8 | Main loop $D28E entry, +600, +2400 | $74 on | $0000 | $1000 | $0000 | $2400 | $2000 | 0 full | **64×32** |

Confirmations/corrections against §1–§2:
- §1a boot table and §1c $A14 set are **confirmed value-for-value
  at runtime**, including R10 ($FF boot / $01 in $A14), R15
  (1 → 2), and the DMA fill setup (length $FFFF, type Copy).
- $A14's R11 = $03 (**per-line H-scroll**) is now explicit —
  the boot animation (state 3) runs in line-scroll mode, with
  $4E6 writing the $2000 H-scroll table.
- State 4 = state 2 with R10 back to $FF: $119E writes
  $8AFF after the animation, before $D25C.
- State 5 confirms the $11E06 static decode exactly ($8512 →
  SAT $2400; R17=$80; display turned ON at $11E06's exit).
- The **intro driver reconfigures the VDP per screen** (states
  6–7 are neither the boot nor the $11E06 set): planes move to
  $2000/$F000/$0000, SAT to $4400, H-scroll table to $4000,
  and R11 flips between full (screen A) and line (screen B)
  scroll on the same bases.
- By main-loop entry (state 8) the $11E06 bases are back, but
  **R16 is $01 (64×32), not $11E06's $03** — a later setup
  pass in the intro-exit/new-game-init path shrinks the
  planes (the single write was not isolated in this trace).

### 5b. Draw trace — the $11E06 → intro-screen transition

Breakpoint/backtrace trace across the transition (window:
$11E06 entry → intro screen build), all observed:

- **$11E06 itself issues no DMA.** Registers go through
  $D9E2; the VRAM clear is CPU work: $DC60(0) + a $D9EE
  data-port loop ($8000 words), then $DC60 again; palettes
  via $11082 → CRAM.
- **Tile uploads are DMA via $11A7C → $DA04:** 13 consecutive
  sampled $DA04 hits in the window *all* return to 0x11A98
  (inside $11A7C) — the decompressed-graphics path of §2,
  driven by the intro code after $14FB6 entry.
- **Nametables are built by the $1194A blitter** from the
  intro draw cluster at $15ECE–$15FA0 (4 sampled hits, all
  from that cluster, inside $14FB6's screen builders).
- **Window/text rows** are written via $DC60 with addresses
  $F000, $F080, $F100, … (step $80 = one 64-cell row) in the
  intro configuration (Window base $F000).
- **The sprite table is written entry-by-entry by CPU**
  ($DC60(SAT base) observed live, caller $11B84 in $11B76):
  see docs/tiles-sprites-palettes.md §6 for the writer
  routine ($11BD8) and the base variable ($FF8644).
- Per-frame in the main loop, $1B918 remains the only redraw
  dispatcher (flags $FF0098/$FF009A/$FF009C — §3), and the
  tile re-upload it performs when $FF0098 is set is a single
  $DA04 DMA of $33C0 words from the $FF1EC0 scratch buffer
  to VRAM $FF8674<<5 (read from the code at 0x1B9D0–0x1B9E8).
  Sprites are **not** re-uploaded per frame; SAT entries
  persist in VRAM until a draw routine rewrites them.

### 5c. The packed/planar paradox — runtime note

No packed→planar conversion step appears in any traced draw
path this session (uploads are the verbatim $11A7C/$11AE4
DMAs; sprite pattern words reference the uploaded tile
indices directly). The paradox of §4 stands unresolved, but
the runtime evidence narrows it: whatever the VDP is fed, it
is fed unconverted on every path traced.
