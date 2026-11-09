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
