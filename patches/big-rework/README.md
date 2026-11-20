# Big-rework proof-of-concept — Rings of Power (Mega Drive)

Proves **decode-once + hardware scroll** for the Academy room
(chunk 233, location 156), per `.scratch-big-rework/DESIGN.md` §8.
Built from the original ROM in this worktree; the original stays
untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## What it does

- The room image is decoded **once** by the unmodified
  `map_chunk_pos` (`$01BA4E`) and DMA'd to VRAM, exactly as the
  original does at scene setup. After that one decode,
  `redraw_check` (`$01B918`) never re-decodes the room again.
- The room name table lives in **Plane B** (VRAM `$4000`, R4=`$02`),
  the window plane stays full-screen, and the window room rect is
  blanked with a known-transparent tile, so the room shows through
  transparent window pixels.
- The **D-pad slides the whole room** 1 px per VBlank via the Plane B
  scroll (`$DC16`), clamped to ±1 cell from centre
  (ΔhScroll ±14 px, ΔvScroll ±8 px). The window-plane HUD/frame
  stays fixed while the room slides beneath it.
- Figures are baked into the image, **frozen**. No sprites, no
  collision/game changes, no strip streaming, no tick governor, no
  overworld change (the gate and the scroll are room-156-only; other
  scenes get a clean Plane B install at scroll 0 and otherwise run
  exactly as the original).

## How it works

Three trampolines in one 980-byte blob at `$FD900` (0xFF padding,
past the runtime checksum's summed range `$000000-$FD07B`):

| Trampoline | Hook site | Job |
|---|---|---|
| `vbl_entry` | `$1272` VBlank handler (`jmp`, overlay pattern) | Per-frame D-pad scroll from `$FF0018`; writes `$DC16` only when the scroll changed; disarms + restores scroll 0 on leaving room 156; resets install state on location change |
| `redraw_entry` | `$01B918` `redraw_check` (`jsr`, smooth-move pattern) | One-time Plane B install (R4/R16, blank Plane B table, draw room table into Plane B, blank window room rect), then clears `$FF0098` at entry to suppress every further room re-decode. Menu/panel/dialog arms keep running |
| `scene_entry` | `$012C20` `world_map_draw` (`jsr`) | Resets the install state on every scene setup (a setup re-uploads rec 6 over VRAM `$4000-$4FFF`) |

Three static patches (original bytes asserted first):

| Site | Change |
|---|---|
| `$12C9A` | `move.w #$8400,-(a7)` → `#$8402` (R4: Plane B `$4000`) |
| `$12E68` | `pea $001000.w` → `pea $004000.w` (room draw → Plane B) |
| `$16326` | `pea $001000.w` → `pea $004000.w` (`world_map_redraw` room → Plane B) |

R16 needs no change: `world_map_draw` already sets `$9001`
(planes 64×32); `gfx_layout_game`'s `$9003` is re-set by it before
gameplay. State lives in dead RAM `$FF00A0-$FF00B4` (0 refs in
`disasm/src/rop.s`; `$FF00A4` and the live `$FF00AC/$FF00AE` menu
fields are avoided). Every state word is range-validated; anything
out of range fails safe to original behaviour (no scroll, no
suppression).

Scroll signs (design §5.2, re-checked): Right (east) ΔhScroll −14 /
ΔvScroll +8 per cell; Left +14/−8; Down +14/+8; Up −14/−8. Per
VBlank the accumulators step 1 px horizontally and 9/16 px
vertically (8/14 = 0.571 px/fr; 9/16 = 0.5625 — a 1 px shortfall
per cell of travel, irrelevant under the ±1-cell clamp). Load
scroll is (0,0): the room draw places the image at plane (2,0),
so it is already aligned with the viewport at scroll 0 (the
design's §8.2 (16,0) assumed plane origin (0,0); the actual draw
call uses x0=2).

## How to use (Dayset's check)

1. Run `rop-big-rework-poc.rom` (or apply
   `rings-of-power-big-rework-poc.ips` to a clean original ROM).
2. Load the Buc save state (`slot_0_1_ou3l.state`, Academy room).
   The install is automatic: `$FF0098` is set at the end of every
   world tick even standing still (`redraw_flag_set` at `$0231CA`),
   so the one decode + Plane B install happen within a tick of
   loading the state (or after closing any open menu).
3. The room should look exactly like the original. Hold the D-pad:
   the whole room slides smoothly under the fixed frame; release
   and it stays. No figure moves (frozen — expected). No hitch,
   no jump, no flicker. At the ±1-cell clamp the room stays
   correct; beyond it (not reachable — clamped) blank plane cells
   would show.

Note: the D-pad also walks the leader logically (game input is
untouched), so Buc's logical position advances while his baked
figure stays put. That is the honest limit of "decode once" for
this PoC.

## Files

- `rings-of-power-big-rework-poc.ips` — IPS patch (1,426 bytes,
  101 records). Apply to a clean original ROM. Round-trip
  verified: base + IPS == ROM exactly.
- `rop-big-rework-poc.rom` — the patched ROM (worktree root,
  `rop-big-rework-poc.rom`; MD5
  `64b742edf92cf8b3b2227b8654d550e9`). The ROM is the deliverable;
  the IPS is the committable form.
- `source.s` — the patch source (m68k assembly, GNU as).
- `build.py` — rebuilds the patch, the IPS, and the ROM from the
  original. Run: `python3 patches/big-rework/build.py`.
- `changed-bytes.txt` — the full list of changed bytes with
  addresses (original → patched), for review without applying
  the IPS.
- `source.bin` — the assembled trampoline blob (980 bytes).

## What was verified (build checks only)

- `tools/checksum.py verify-all` on the patched ROM: header
  `0x4C25` OK, runtime `0x334083AE` OK. (Original: header `0x8B9F`,
  runtime `0x8F33608C`.)
- IPS round-trip: applying the IPS to the original reproduces the
  patched ROM byte-for-byte (independent re-check, not just the
  builder's own).
- Diff audit: the only changed bytes are the header checksum
  (`0x18E`), the three hooks, the three statics, the runtime
  immediate (`0xFD098`), and the `$FD900-$FDCD3` blob. Nothing
  else in the ROM differs.
- Design arithmetic re-verified independently: whole chunk
  896×512 px = 112×64 tiles = 7,168 tiles = 229,376 B (3.5× VRAM);
  viewport 36×23 = 828 tiles = 26,496 B = `$33C0` words; Plane B
  table 64×32 = 4,096 B; blank tile `$7FF` pattern at VRAM
  `$FFE0-$FFFF`, past the highest tile upload (`$7F5` → `$FEBF`);
  scroll deltas, clamp ranges, and the (0,0) load scroll.
- The blob assembles cleanly and the disassembly was read back
  (entry offsets vbl +0, redraw +`$224`, scene +`$3AA`;
  `pea`/`jsr`/`movem`/`link` encodings as intended).
- Original ROM untouched (MD5 re-verified after the build);
  nothing landed on main.

## What was NOT verified (Dayset is the tester)

- **No live run.** The ROM was never booted in an emulator or on
  hardware by the build: no boot check, no screenshot, no
  pixel-compare of the first frame vs the original, no breakpoint
  log proving `$E358`/`map_chunk_pos` stay silent after load, no
  cadence measurement. All of §8.3 criteria 1–5 await Dayset's
  playtest. The mechanism is proven by construction + code
  reading only.
- **Tile 0 is not blank** (see REPORT.md): the PoC uses tile
  `$7FF` as the blank, not tile 0 as the design suggested. Tile
  `$7FF`'s zero pattern is established by code reading (VRAM
  cleared at boot; no upload touches `$FFE0-$FFFF`), not by a
  live VRAM read.

## Known limitations

- **World map:** while the PoC is armed, opening the world map
  fights the map's own scroll writes if the D-pad is held (both
  write all four scroll values via `$DC16`). The map may not
  scroll properly until it is closed; closing it restores the
  room correctly, but the first D-pad step after closing can jump
  by the stored scroll offset (the hook writes only on change, so
  it does not notice the map zeroed the scroll — see REPORT.md).
  Out of the §8 demo scope.
- **Other rooms / overworld:** the gate and the scroll are
  room-156-only. Other locations run as the original (with a
  clean Plane B install at scroll 0).
- **D-pad walks Buc logically** (see "How to use"). Walking
  through a door changes location; the PoC disarms, and the new
  room installs fresh on entry.
- **Water does not shimmer** (baked at one `$FF0092` phase) and
  figures do not walk, animate, or turn — §8.4, by design.
- **VBlank-hook VDP interleave:** the scroll write runs in
  interrupt context (same accepted hazard class as the debug
  overlay's hook); it only writes when the scroll changed, and a
  corrupted write self-corrects on the next VBlank.

## Checksums

- Patched ROM MD5 `64b742edf92cf8b3b2227b8654d550e9`, header
  checksum `0x4C25`, runtime checksum `0x334083AE`.
- Original ROM MD5 `30c18fdbe2183f64702ae9f1a45d63f9` (untouched).
