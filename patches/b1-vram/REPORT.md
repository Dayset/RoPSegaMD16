# B1 report — VRAM layout migration to allocation B (36×23 fallback)

Worktree: `~/workspace/rop-work/big-rework-full/` (main tip `416d623`).
Base: `rop-big-rework-poc-fix2.rom` (MD5 `d4fc661f333ca2425987d2407693bce9`).
Deliverable: `rop-big-rework-full-b1.rom`
(MD5 `49530033f2f191d938e9f0ec3f86e845`, 1,048,576 bytes).
Patch: `patches/b1-vram/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `rings-of-power-big-rework-full-b1.ips`,
`source.bin`). Original ROM untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`, re-verified after the build).

## 1. What B1 is

Phase B1 migrates the VRAM layout from the PoC to allocation B
(DESIGN.md §3.2/§3.4) and was tasked with building the 40×28 banded
image. The layout migration **landed**. The 40×28 image **did not**:
the R2 verification (§2) proves the ROM `$E358` decode tables cap the
window at exactly 10×10 cells (36×23 tiles), so per the brief's
fallback clause B1 ships the **36×23 image at the new base `$1B4` /
Plane B `$E000`**. B2 (strip streaming) still works with 0 margin.

## 2. R2 verification — the 40×28 banded build is impossible with the ROM tables

Script: `.scratch-big-rework-full/b1-vram/verify_banded.py`
(log: `verify_banded.log`, ~53 s run). It uses `sim_span2.py` /
`sim_span.py` (exact `$E358` simulation from the disassembly + ROM
tables) over all 944 tile streams × d3 ∈ {0,1}.

Geometry (from `grid_fill` + `$E358`): `d0 = 196+14(r−c)`,
`d1 = 18+8(r+c)`; buffer offset =
`T436E0(2·d1+2k) + T435C0(d3v)`; `T435C0(d) = ((d>>3)<<5)|((d>>1)&3)`;
`T436E0(i) = (i//16)*1152 + ((i%16)//2)*4`; buffer 26,496 B = 36×23
tiles, stride 1152 B/row. Table limits: `$435C0` valid `d3v ∈ [0,288)`
⇒ `d0 ∈ [68,321]` ⇒ `Δ ∈ [−9,8]`; `$436E0` valid index `[0,368)` ⇒
`2·d1+2k < 368`. Out-of-range = offset < 0 or ≥ 26,496.

### Window validity

| Window | Bad cells | Bad offsets | Offset range | Rows |
|---|---|---|---|---|
| 10×10 (today) | 0/100 | 0 | [514, 26046] | 0..22 |
| 11×10 | 0/110 | 0 — but silent corruption* | [514, 26172] | 0..22 |
| 10×11 | 1/110 | 101,504 | [−14937, 26046] | −13..22 |
| 11×11 | 1/121 | 101,504 | [−14937, 26172] | −13..22 |
| 12×12 | 3/144 | 321,583 | [−14937, 47066] | −13..40 |
| 12×13 (40×28) | **6/156** | **720,666** | [−14937, 49370] | −13..42 |

\* 11×10 has no out-of-range offsets, but d3v ≥ 288 reads `$436E0`
words 0..28 instead of ~1088..1152, so right-edge content lands at
column 0 — e.g. cell (10,0), d0=336: d3v ≥ 288 for L≥8.

The failure is real for actual rooms, not just synthetic streams:
Academy chunk 233 (decoded record 233, 22 distinct tile streams in
the window) — the new cells' real streams produce **2,490 bad
offsets**. Negative offsets write *before* the `$FF1EC0` decode
buffer into live RAM.

### The band-remap method itself is sound — DESIGN §4.3's version is not

- **d1-only remap** (`d1′ = d1 − 8R`, d0 unchanged) is an **exact row
  translation: 0 mismatches over 107,009 writes** for R ∈ {1,2,5,10}.
- **DESIGN §4.3's literal remap** (`(r−bandR0, c)` in both formulas)
  is **wrong: 106,922/109,135 mismatches for R=1** (it also shifts
  columns by 14 px per band step; R=2: 101,124/103,011).
- DESIGN §4.3 step 4's DMA formula (`source $FF1EC0 + bandR0 ×
  imageW × 32`) wrongly assumes buffer stride = imageW×32; the true
  stride is **1152** (= 36×32), not 1280.

### Conclusion

**FALL BACK to the 36×23 image at the new base/table.** The 40×28
image needs custom `$E358` tables (own tables with 1280 stride +
extended ranges, RAM table pointers, relocated d0/d1 tables) — a
future redesign, not B1. Do not stall on it. The band-remap finding
(d1-only) is recorded here for that redesign.

## 3. Layout migration — what changed

### 3.1 Statics

| Site | Before | After |
|---|---|---|
| `$12C9A` | `move.w #$8402,-(sp)` | `move.w #$8407,-(sp)` (R4: Plane B `$E000`) |
| `$12E68` | `pea $004000.w` | `pea $00E000.w` (room draw → Plane B) |
| `$16326` | `pea $004000.w` | `pea $00E000.w` (redraw room → Plane B) |
| `$12CDE` | `move.w #$9001,-(sp)` | unchanged — R16 already `$01` |

`pea.w $E000` sign-extends to `$FFFFE000`, but
`vdp_set_write_addr` (`$DC60`) rebuilds all 16 address bits from the
low word (`and.w #$3FFF` + `rol.w #2` for bits 15–14), so it lands at
`$E000`. Verified against the disassembly of `vdp_set_write_addr`,
`gfx_tilemap_draw` (`$11820`) and `gfx_tilemap_fill` (`$11A1A`),
which both feed the dest long only into `vdp_set_write_addr`.
(The blob's own `pea.l $E000` assembles to the 6-byte long form
`4879 0000E000`, so no sign issue there.)

### 3.2 Allocator re-sequence (`$12D00–$12DE7`, 232 bytes)

Rebuilt in place by `build.py` from base-ROM block slices, with the
two new `move.w #imm` instructions and 7 NOPs of padding. New order:

```
$12D00  init    move.w #$134,$FF0076
$12D08  font    decode(0), gfx_dma_tile_upload(103)  -> $FF8640=$134, cursor $19B
$12D24  rec 1   decode(1), gfx_dma_tile_upload(25)   -> $FF8642=$19B, cursor $1B4
$12D42  image   sys_counter_add($33C=828)            -> $FF8674=$1B4, cursor $4F0
$12D54  mapset  decode($10), gfx_dma_tile_upload(128)-> $FF867C=$4F0, cursor $570
$12D72          move.w $FF867C,$FF8678
$12D7C  NEW     move.w #$614,$FF0076
$12D84  shared  sys_counter_add($24=36)              -> $FF8648=$614, cursor $638
$12D96  sprite  decode($B), gfx_dma_tile_upload(96)  -> $FF867A=$638, cursor $698
$12DB4  $FF867E decode($11), gfx_dma_tile_upload(76)  -> $FF867E=$698, cursor $6E4
$12DD2  NEW     move.w #$1B4,$FF8676
$12DDA  NOP x7
```

Cursor flow verified by disassembly of the output ROM (all five
decode blocks call `gfx_dma_tile_upload` `$11A7C`, which advances
`$FF0076` by the count and returns the old cursor — this is why rec 1
consumes 25 tiles of cursor even though it uploads via DMA).
Free gap: `$570–$613` (164 tiles). Sprite-pattern cache `$6E4–$6FF`
(28) + `$780–$7FF` (128) stays empty, reserved for phase C.
Plane B table `$E000` = tiles `$700–$77F` (no pattern data lives there;
the table is nametable only).

`jsr map_decode(pc)` displacements: five survive (rec 6's is dropped
with its block). **Caught in verification:** my first build used
disp = target − (jsr + 4); the original ROM's disps prove the 68000
PC-relative EA is jsr address + 2 (e.g. font jsr at `$12D0E`, disp
`$0B2C` → `$12D10 + $0B2C = $1383C`). The +4 build put all five jsrs
at `$1383A` (2 bytes before `map_decode`) — a real misaligned-jump
bug. Fixed to +2, rebuilt, and re-verified: all five land on
`$1383C` and the two unmoved jsrs are byte-identical to the original.
(This is the one substantive defect the build/verify loop caught; it
never reached a ROM handed to Dayset.)

### 3.3 Eviction verification

**Record 6 (438 tiles, `$FF8676`): EVICTED.** Use sites all map /
Plane-A, invisible during gameplay behind the full-screen window:
`$012E82` + `$016342` (record-9 full-screen Plane A draws);
`$0149F2`/`$014A36`/`$14BB4`/`$14EAC` (inside `gfx_plane_write`
`$147D0`, which reloads its own rec 6, record `$176`/`$C`, at
`$148A2`); `map_view` entry `$16758` (`tile_upload` record `$21`,
328 tiles at `$FF8676`); `map_view` exit `$17054` (`tile_upload`
record `$1B6`/6, 438 tiles at `$FF8676`). Reload base set to `$1B4`
(inside the image; restored on map close — see §4).

**Map tileset (128 tiles, `$FF8678`/`$FF867C`): NOT evicted —
relocated to `$4F0` instead.** The brief's eviction rationale
(DESIGN R6) is refuted by a gameplay use site: `$0145D8` in
`world_sprites_setup` (`$13D84`, runs at every scene setup) — an
unconditional `sprite_grid_write` of a 32×32 sprite at screen
(4,187), 16 tiles from `$FF867C` (+ tile 67), palette 2. Other uses:
`$0164AA`/`$0164F0` (`row_write`/`column_write`, map scrolling);
`map_view` entry `$16738` (`tile_upload` record `$A`, 64 tiles at
`$FF8678`); exit `$17034` (`tile_upload` record `$80`/`$10`, 128
tiles at `$FF867C`). In the fallback the 292-tile free gap
`$4F0–$613` fits the 128-tile tileset, so keeping it resident costs
nothing and preserves the sprite + map view exactly. **Deviation to
report:** the sprites agent / coordinator decides the tileset's home
if the 40×28 image ever lands (there the gap is gone and the tileset
must live elsewhere or be evicted with the sprite re-pointed).

`map_view` (`$1664E`, sole caller `$2DD30`) makes no `vdp_ctrl_write`
calls, so the window stays full-screen during the map view; its exit
block (`$16FBA+`) reloads both records and calls `world_map_redraw`
(`$162FE`, sole caller `$1709E`). `world_map_draw` callers:
`$15008`, `$1552C`, `$195C4`.

## 4. Map open/close + the new `mapclose_entry` hook

The map-view reloads clobber image tiles `$1B4–$2FB` + `$36A–$3A9`
(entry) / `$1B4–$369` + `$36A–$3E9` (exit). Without intervention the
fix2 gate would suppress the post-close re-decode (camera unmoved)
and the room would show rec-6/map tiles. Hence the new hook:
`world_map_redraw` at `$16302` displaced `jsr wait_vblank.l`
(`4EB9 0001386A` → `jsr $FDE2A.l`).

`mapclose_entry` (`$FDE2A`, +0x52A in the blob):
`addq #4,sp` (drops the jsr return address) → clear
installed/armed/hAcc/vAcc → installCam = `$FFFF` (forces a full
transition) → `jsr wait_vblank` (`$1386A`, the displaced call,
preserved) → `jmp $16308` (the instruction after the displaced jsr;
jmp-on, not rts — correct for a jsr hook whose return address was
dropped; uses no registers; stack net 0). The next `redraw_check`
then re-blanks Plane B, re-decodes + DMAs the room image, and
re-installs.

Known cosmetic regression (documented, same as PoC): during the map
view, the clobbered room image shows through transparent window
pixels instead of the intact room; the room is fully restored on
close. Inherited PoC limitation (out of scope): opening the map
fights the map's own scroll writes if the D-pad is held.

## 5. Blob (`$FD900–$FDE5F`, 1376 bytes)

Four entries, offsets from `m68k-linux-gnu-nm` (never hardcoded):

| Entry | Offset | Address | Notes |
|---|---|---|---|
| `vbl_entry` | +0x0 | `$FD900` | VBlank hook, byte-identical to fix2 |
| `redraw_entry` | +0x254 | `$FDB54` | fix2 gate kept verbatim; install constants changed to R4 `$8407`, Plane B dest `$E000` (both the nametable fill and the room-table draw; `pea.l $E000` is the 6-byte long form) |
| `scene_entry` | +0x4F0 | `$FDDF0` | code unchanged; comment updated (scene setup no longer uploads rec 6) |
| `mapclose_entry` | +0x52A | `$FDE2A` | NEW (see §4) |

Why scene moved +4 vs fix2: GAS encodes `pea.l $E000` as 6 bytes
(long form — `$E000` doesn't fit the signed 16-bit short form) while
`pea.l $4000` was 4 bytes; two such peas = +4 bytes. The build
resolves all hook targets from `nm`, so the shift is handled, not
assumed. Blob fits `$FD900–$FDFFF` (1376 B; tail padding
`$FDE60–$FDFFF` all `0xFF`, verified).

State: dead RAM `$FF00A0–$FF00C0` (magic `$9C07`, armed, installed,
hAcc, vAcc, lastH, lastV, lastLoc, installCamX `$FF00BC`,
installCamY `$FF00C0`; `$FFFF` = none yet). `$FF00A4` NOT used (game
tests it at `$1CF3C`); `$FF00AC`/`$FF00AE` are live menu fields, not
used. Tile `$7FF` kept as the transparent blank tile: tile 0 is NOT
blank (its pattern bytes are the Plane A nametable at VRAM `$0000`,
written by the `$12DE8` fill with font tile `$134`); `$7FF`'s
pattern slot (VRAM `$FFE0–$FFFF`) is untouched by any upload in B1
or the PoC and behaved as transparent in the PoC playtest. (Note: a
check of ROM *file* bytes at `$FFE0` is meaningless — that's ROM
data, not VRAM; VRAM `$FFE0` is written only by a DMA targeting it,
and none exists.)

Scroll for the fallback: image 36×23 at plane (2,0), load scroll
(0,0), D-pad clamp ±1 cell. The allocation-B scroll (−96,36) and
clamp h [−112,−80], v [16,56] belong only to the 40×28 image and do
**not** apply.

## 6. Build checks (all passed)

- Base MD5 asserted `d4fc661f…`; original MD5 asserted and
  re-verified `30c18fdbe2183f64702ae9f1a45d63f9` after the build.
- Every hook site's original bytes asserted before patching
  (`$1272`, `$1B918`, `$12C20`, `$16302`, `$12C9A`, `$12E68`,
  `$16326`); R16 `$12CDE` asserted `$9001` (unchanged).
- Allocator region in the base asserted equal to the original ROM's;
  exactly six `jsr map_decode(pc)` in the region before the rebuild;
  block-start prefixes asserted per slice; dropped rec-6 block
  asserted to start with `move.w #$1B6`.
- Blob placement asserted in free `0xFF` padding (`$FDE26–$FDFFF`
  all `0xFF` in the base); blob 1376 B ≤ `$FD900–$FDFFF`.
- Checksums: `tools/checksum.py fix-all` (safe — ROM not shifted;
  all patches are in-place replacements + blob overwrite in
  padding) then `verify-all`: size stored `0x31B9` = computed,
  runtime stored `0x53208B43` = computed.
- Disassembly verification of the output ROM: allocator region
  (block order, cursor-set immediates `$614`/`$1B4`, all five jsr
  targets `$1383C`, 7 NOPs); blob (install `move.w #$8407`,
  `pea.l $E000` long form ×2, window fill `pea $1000` unchanged,
  `scene_entry` displaced-prologue tail, `mapclose_entry`
  instruction-by-instruction incl. stack balance and `jmp $16308`).
- IPS: 1098 bytes, 85 records, base → B1. **Round-trip verified:
  base + IPS == ROM exactly.** 665 bytes differ base → B1.
- `changed-bytes.txt`: full byte diff (85 records).

## 7. What Dayset should test

Walk the Academy (and other rooms): the room should render as in
the PoC-fix2 ROM (same 36×23 image, same D-pad scroll, same
re-decode on camera moves). Then:

1. Open the map (`map_view`) and close it — the room must restore
   fully (this is the new `mapclose_entry` hook's job; without it the
   room would show rec-6/map tiles after close).
2. Dialogues / menus / scene transitions — HUD/dialog/menu untouched
   by design; confirm nothing regressed (the allocator now runs at
   every scene setup with a new block order).
3. Walk far enough to force a >1-cell camera move (teleport/fast
   walk) — the fix2 gate's re-install-with-jump behaviour is
   unchanged.
4. The visible 32×32 sprite drawn at scene setup (from the relocated
   map tileset at `$4F0`) — confirm it still appears as before.

Expected unchanged from fix2: black background, no pink decoration
or HUD (accepted side effect); map-view background shows the
clobbered room through transparent pixels while open.

## 8. Open / queued items

- **40×28 image (future redesign):** custom `$E358` tables — own
  tables with 1280 stride + extended ranges, RAM table pointers,
  relocated d0/d1 tables. Use the d1-only band remap (§2), not
  DESIGN §4.3's literal remap; use stride 1152 for the current
  buffer, 1280 only for the new tables. The tileset's home must be
  re-decided then (§3.3).
- **B2 strip streaming, C sprites, D governor:** not built (one
  phase only, per the brief).
