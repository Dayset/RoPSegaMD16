# Flat overworld plane — patch README

One fix only: the OVERWORLD (outside, mode `$FF00AE` == 1) renders as a single
flat plane — land one flat colour, water its own flat colour. No glide, no
subcell, no room change, no other change. Built on the ORIGINAL ROM.

## Deliverable

- ROM: `rop-flat-world.rom` (in the worktree root), MD5
  `c362a4595cb550dcb7047357b85e3fd9`, header checksum `0x013C`, runtime
  checksum `0xD0F760DB`. Original ROM untouched (MD5
  `30c18fdbe2183f64702ae9f1a45d63f9`).
- This patch dir: `source.s` (generated assembly), `gen_flatworld.py`
  (generates `source.s`), `build.py` (assembles + patches + fixes checksums +
  writes the IPS), `changed-bytes.txt`, `flat-world.ips` (11,471 B;
  round-trip verified: original + IPS == fixed ROM exactly).

## Design

Hooks the `$E358` (`map_terrain_tile_lookup`) handler dispatch, not the
call sites. The three `map_chunk_pos` (`$01BA4E`) call sites (face `$01BC1A`,
hidden `$01BC3C`, top `$01BC84`) are retargeted to a call-site stub that sets
the flat byte in RAM `$FF00B0` from the cell's terrain type (props word at
`-$6(a6)`, type bits 10–15), then tail-calls `$E358`. `$E358` computes the
buffer position (`a5`) and advances the stream exactly as the original; the
dispatch hook (replacing the 6 bytes at `$E40C` and 12 bytes at `$E470`)
substitutes a flat handler for the original handler from table `$DF58`.

- A flat handler is a mechanical copy of its original handler with the
  stream read (`move.b (a0)+,d5`) replaced by `addq.l #1,a0` (keeps the
  stream in sync; `d5` holds the flat byte from the hook) and the path-B
  nibble-swap remap omitted (a no-op for a flat byte with equal nibbles).
  112 handlers, ~9,800 bytes.
- The hook fires only when ALL of these hold: the return address is one of
  the three `map_chunk_pos` sites (terrain, not figures or the `$03Cxxx`
  callers), mode `$FF00AE` == 1 (overworld), the grid base `$FFA7FC` ==
  `$FFB08C` (the overworld grid slot), and the dispatch-table entry is
  nonzero. Otherwise the original handler runs.
- Colours: land flat byte `0x33` (palette index 3, pure green `(0,144,0)`
  in the overworld palette `$CCB18`); water flat byte `0x11` (palette
  index 1, dark blue `(0,0,180)`). Water = terrain types
  `{0,2,3,10,11,15,21,22,23}`. The room (mode 2, grid `$FFB0AC`/`$FFB09C`/
  `$FFB0BC`) never satisfies the gate and renders exactly as the original.
- Blob: 10,990 bytes at `$FD0CC`–`$FFBC2` in the 12,084-byte `0xFF` padding
  (1,094 bytes spare). RAM byte `$FF00B0` holds the current flat byte; it
  is free in the ORIGINAL ROM (zero references) but conflicts with nothing
  here — this ROM is built on the original, not on v3 (v3 uses
  `$FF00B6`/`$FF00B8`/`$FF00BA`; the glide-edge fix uses `$FF00B2`/`$FF00B4`).
  Do NOT combine this ROM with v3 without resolving RAM use.

## Why the grid check

Mode flips to 1 at the same time the grid switches to the overworld slot in
the Buc cutscene transition (both at frame ~4200), so the grid check is
defensive here — but it is the correct gate: mode alone would flatten the
room if a future path ever set mode 1 while a room grid was still active.
Room grids are `$FFB0AC`/`$FFB09C`/`$FFB0BC` (set by
`world_location_transition` `$01DC00`/`$01DC0E`/`$01DFB2`); the overworld
branch sets `$FFB08C` (`$01DE08`), as does boot (`$01B74E`).

## Colour note

The first build used land nibble 4 (numerically dominant in grass tiles
16/17). It rendered BLUE in the overworld palette (`$CCB18` idx 4 =
`(0,180,252)` light blue; idx 2 = `(0,108,216)` blue). The green is idx 3
(`(0,144,0)`), so land is now `0x33`. If the green shade is wrong for
Dayset's eye, change `LAND_K` in `gen_flatworld.py` (and `WATER_K` for the
water) and rebuild.

## How to rebuild

```
python3 gen_flatworld.py            # writes flatworld.s
vasm/vasmm68k_mot -m68000 -Fbin -L flatworld.lst -o flatworld.bin flatworld.s
python3 build.py                    # writes ../rop-flat-world.rom + patches
```
`build.py` parses stub addresses from `flatworld.lst` (never hardcodes
them), asserts the original MD5 and the `0xFF` padding, patches the call
sites + dispatch sites + blob, runs `checksum.py fix-all`, and verifies the
IPS round-trip. NOTE: `build.py` does NOT assemble — run vasm first, or the
ROM is rebuilt from a stale `flatworld.bin` (this bit the author once).

## What this does NOT do (honest limits)

- The flat plane covers the terrain only. Buildings, trees, plaza and other
  height-stack terrain in the overworld are terrain tiles, so they flatten
  into the ground plane too — the town becomes a flat green plane with blue
  water patches; its buildings/trees are not separately preserved. Figures
  (the party leader, NPCs) are drawn by `hero_track`, not `$E358` terrain,
  so they stay visible. UI, dialog, and the room are untouched.
- The flat colour is per terrain type (land vs water), not per tile or per
  height level — height shading and terrain texture are gone by design.
- The `$03Cxxx` `$E358` callers are unaffected by design (return-address
  gate), and the room is untouched by design (mode + grid gate).
- NOT verified (Dayset is the tester): the overworld cadence was NOT
  measured; the final ROM's look was NOT live-verified after the last colour
  change except through a diagnostic probe; world-view/room/menu/teleport
  were not re-checked on the final ROM. See `REPORT.md` for the full
  verified / not-verified list.
