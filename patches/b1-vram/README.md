# B1 — VRAM layout migration to allocation B (36×23 image fallback)

Phase B1 of the full big rework (`big-rework-full`). Base ROM is the
PoC-fix2 ROM — **the IPS applies to `rop-big-rework-poc-fix2.rom`
(MD5 `d4fc661f333ca2425987d2407693bce9`), NOT to the original ROM.**

## What B1 does

Migrates the VRAM layout from the PoC to allocation B (DESIGN.md §3.2/§3.4):

- **Plane B nametable moves $4000 → $E000** (R4 `$8402` → `$8407` at
  `$12C9A`; room draws at `$12E68`/`$16326` re-pointed; the install in
  the blob fills/draws Plane B at `$E000`). R16 is already `$01`
  (planes 64×32) and is unchanged.
- **Allocator re-sequenced** in `world_map_draw` (`$12D00–$12DE7`):
  font `$134` → rec 1 `$19B` → image `$1B4` (828 tiles) → map tileset
  `$4F0` (128 tiles) → shared 36-tile slot `$614` → sprite tiles `$638`
  (96) → `$FF867E` `$698` (76). Free gap `$570–$613` (164 tiles).
- **Record 6 evicted** (438 tiles): `$FF8676` is set to `$1B4`, its
  map-view reload base. During gameplay nothing uploads rec 6.
- **Map tileset RELOCATED to `$4F0`, not evicted** (deviation from the
  brief — see below).
- **Sprite-pattern cache reserved empty**: `$6E4–$6FF` (28 tiles) and
  `$780–$7FF` (128 tiles). The sprites agent fills them; B1 uses
  neither.
- **NEW `mapclose_entry` hook** on `world_map_redraw` (`$16302`): the
  map view's entry/exit reloads clobber image tiles, so the install
  state is reset on map close and the room is re-installed on the
  first `redraw_check` after close.
- The PoC-fix2 re-decode gate is kept verbatim (suppress while the
  camera is unmoved; seamless re-install 1 cell away; re-install
  with a jump when further). Blob stays at `$FD900` (now 1376 bytes).

## The 40×28 banded image is NOT built — fallback to 36×23

The R2 verification (`.scratch-big-rework-full/b1-vram/verify_banded.py`,
exact `$E358` simulation from the disassembly) proves the ROM tables
cap the decode at exactly the 10×10 window (36×23 tiles). A 12×13
window (the 40×28 image) produces **720,666 bad offsets over 6 cells**
(range −14937…49370 — negative offsets write *before* the decode
buffer into live RAM), and the Academy's own real streams produce
2,490 bad offsets. The 40×28 image needs custom `$E358` tables (own
tables with 1280 stride + extended ranges, RAM table pointers,
relocated d0/d1 tables) — a future redesign, not B1. Per the brief,
**B1 falls back to the 36×23 image at the new base `$1B4` / Plane B
`$E000`**. Strip streaming (B2) still works with 0 margin. The
allocation-B scroll (−96,36) and clamp [−112,−80]×[16,56] belong only
to the 40×28 image and do **not** apply; B1 keeps load scroll (0,0)
and the ±1-cell D-pad clamp.

Two DESIGN §4.3 corrections found by the same verification (for the
future 40×28 work): the literal band remap (`(r−bandR0, c)` in both
formulas) is wrong — it shifts columns by 14 px per band step
(106,922/109,135 mismatches for R=1); the correct remap is d1-only
(`d1′ = d1 − 8R`, d0 unchanged), which is an exact row translation
(0 mismatches over 107,009 writes). And the §4.3 DMA formula assumes
buffer stride = imageW×32 (1280); the true stride is 1152 (36×32).

## Why the map tileset was relocated, not evicted

DESIGN R6's eviction rationale is refuted by a gameplay use site:
`$0145D8` in `world_sprites_setup` (`$13D84`, runs at every scene
setup) unconditionally draws a 32×32 sprite at screen (4,187) from
16 tiles at `$FF867C` (+ tile 67), palette 2. Evicting the tileset
would break that sprite (and the map view's own scroll writes). In
the fallback the free gap `$4F0–$613` fits the 128-tile tileset, so
keeping it resident costs nothing and preserves the sprite and the
map view exactly. If the 40×28 image ever lands, the sprites agent /
coordinator decides the tileset's home then.

## How to build / apply

```
python3 patches/b1-vram/build.py
```

Rebuilds `rop-big-rework-full-b1.rom` from the poc-fix2 ROM, fixes
checksums, writes the IPS + `changed-bytes.txt` here, and verifies
the IPS round-trip (base + IPS == ROM exactly). Or apply
`rings-of-power-big-rework-full-b1.ips` to a copy of
`rop-big-rework-poc-fix2.rom` with any IPS patcher.

## Patch map

| Site | Before | After |
|---|---|---|
| `$1272` VBlank hook | `jmp $FD900.l; nop` | unchanged (verified) |
| `$1B918` redraw_check hook | `jsr $FDB54.l` | `jsr $FDB54.l` (redraw_entry, unchanged offset) |
| `$12C20` world_map_draw hook | `jsr $FDDEC.l` | `jsr $FDDF0.l` (scene_entry) |
| `$16302` world_map_redraw hook | `jsr wait_vblank.l` | `jsr $FDE2A.l` (mapclose_entry, NEW) |
| `$12C9A` | `move.w #$8402,-(sp)` | `move.w #$8407,-(sp)` (R4 → Plane B $E000) |
| `$12E68` / `$16326` | `pea $004000.w` | `pea $00E000.w` (room draws → Plane B) |
| `$12CDE` | `move.w #$9001,-(sp)` | unchanged (R16 `$01`, verified) |
| `$12D00–$12DE7` | allocator, PoC order | re-sequenced (see above) + 2 new `move.w #imm` + 7 NOPs |
| `$FD900–$FDE5F` | fix2 blob, 1318 B | B1 blob, 1376 B (vbl +0, redraw +0x254, scene +0x4F0, mapclose +0x52A) |

(`pea.w $E000` sign-extends to `$FFFFE000`, but
`vdp_set_write_addr` rebuilds all 16 address bits from the low word,
so it lands at `$E000` — verified against the disassembly.)

## Known limitations

- **Map-view background regression (documented, same as PoC):** while
  the map is open, the room image shows through transparent window
  pixels instead of the intact room (the map's reloads clobber it).
  The room is fully restored on close (new mapclose hook).
- **Inherited PoC limitation:** opening the map fights the map's own
  scroll writes if the D-pad is held.
- **Black background / missing pink + HUD** (accepted side effect from
  the PoC; Dayset doesn't mind). The install still blanks the
  decoration; this phase does not restore it.
- No strip streaming (B2), no sprites (C), no governor (D).
- Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Files

- `source.s` — the 4-entry blob (assembled with `m68k-linux-gnu-as`)
- `build.py` — builds the ROM, IPS, `changed-bytes.txt`; asserts every
  hook site's original bytes first; recomputes `jsr map_decode(pc)`
  displacements for moved allocator blocks (EA = jsr address + 2)
- `rings-of-power-big-rework-full-b1.ips` — base (poc-fix2) → B1
- `changed-bytes.txt` — full byte diff, base → B1
- `source.bin` — assembled blob (1376 bytes)
- Full record: `.scratch-big-rework-full/b1-vram/REPORT.md`
