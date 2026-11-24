# Remix ROM data regions — The Ring of Perfection (ROPREMIX-01)

Labels for the remix ROM's new data and code, from the full diff in
`~/workspace/rop-work/remaster-reddit/REPORT.md` §8 (corrected 2026-11-24).
The remix ROM is **not in this repo** — these are documented addresses only,
so the labels can be checked against a copy obtained elsewhere. Addresses are
68k addresses, equal to file offsets in the first 1 MB; `$100000+` is the
extra 3 MB. Remix identity: 4,194,304 B, MD5
`7ae0e32e32760f35d23255945c5d20fd`, header `RINGS OF POWER: THE RING OF
PERFECTION`, serial `GM ROPREMIX-01`, 16 KB SRAM `$200001–$203FFF`.

Corrections applied here (all 2026-11-24, from the report): the Academy is
**song 13**, not song 11 (song 11 is the Knights Guild theme); the
location→song table `$0D63E4` is **intact**, not erased; `$101ACE` is a
viewport-visibility test, not a redraw step; the erased run ends at `$D25C`,
not `$D2BD`; `$603E4`/`$433C0` are **unchanged original data**; the two OST
tables agree on 10 songs and differ on 7 (not 9/8); the opening is a **2D
animated cutscene**, not a 3D flight over the live map.

## Identity and layout

| Address | What | Evidence |
|---|---|---|
| `$0–$FFFFF` | Original ROM embedded at the same offsets | 345,109/1,048,576 B differ (32.9%); 101/256 4 KB blocks verbatim |
| `$100000–$3FFFFF` | Extra 3 MB: new code + dense tile/data | Five 64 KB chunks entirely `$FF` (`$1C0000`, `$200000`, `$270000`, `$3E0000`, `$3F0000`) — unused |
| `$1394–$D25C` | Erased region, 48,840 B of `$FF` | Contiguous `$FF` run; `$D25C–$D2BC` is intact original code |
| `$1394–$6929` (erased) | SFX payload | `disasm/regions.csv` `snd-sfx-payload` |
| `$692A–$692D` (erased) | `song_prefix_11` | 4-byte end-pointer prefix |
| `$692E–$9B2D` (erased) | `snd_song_11` — song 11, Knights Guild theme | 12,800 B; NOT the Academy |
| `$9B2E–$D25B` (erased) | `region_009b2e`, binary table ~13 KB | Unnamed |
| `$ED0E4–$FCAE1` | Whole original song block `$FF` | All 18 original songs fail to parse at original addresses in the remix |

## Sound engine — new tables, descriptors, OST state

| Address | What | Evidence |
|---|---|---|
| `$17480` | Song dispatch table — **unchanged** | New engine remaps at runtime instead |
| `$17546` | Dispatch table (force-patched to `$FF76` for song-13 capture) | `force_dispatch.py` |
| `$EB88A` | `sound_start_song` — hooked at head `jmp $1F6940` | `$EB93E`→`$2FD354`, `$EB946`→`$1F6C2A`, `$EB968`→`$2FD340`, `$EB96E`→`$1F6C08` |
| `$1F6940` | Song-start remapper | `$FFCD7D==0` → OLD path (`jmp $EB892`); else NEW path, table select via `$1F6A26` |
| `$1F6200` | Song table A — 17 entries × 10 B (key + descriptor + 2 skip bytes) | Selected when `$FFCD7D != 2` |
| `$1F6800` | Song table B — 17 entries × 10 B | Selected when `$FFCD7D == 2` |
| `$2CDFEA` | Song 13 (Academy) descriptor in table A | w0 `$0068`, data `$2CE052`; b4 = 3 voice blocks; b6 = 7 |
| `$2DA378` | Song 13 (Academy) descriptor in table B | w0 `$0048`, data `$2DA3C0`; b4 = 2; b6 = 0 |
| `$2CA92A` | Song 11 (Knights Guild) descriptor — **same in both tables** | w0 `$00BA`, data `$2CA9E4`; Knights theme identical in both OST modes |
| — | Tables agree on 10 songs, differ on 7: **1, 4, 6, 8, 9, 12, 13** | Matches the post's "7 pieces newly arranged"; song 13 IS one of the 7 |
| `$1F62AE` | Song remap table, 13 entries × 10 B (key + new addr) | Consulted by `$1F6C42`; targets are relocated SFX/graphics data, not song format |
| `$1F6334` | 32-byte FM voice table | Indexed by first song byte masked `$1F`, `<<5` |
| `$1F6B72` | New song engine | `$FFCD7C` flag: clear → original Z80 upload; set → new path, voice block to Z80 |
| `$EBAF4`/`$EBB14` | Song-start — `jmp $1F6B72` replaces `movem.l` | Tail `$EBB6E+` is `$FF`-filled |
| `$2FD22E` | Per-frame music manager | Called from VBlank ISR at `$12F2`, replacing `jsr $EB772` |
| `$FFCD7D` | OST table selector (1 → `$1F6200`, 2 → `$1F6800`, 0 → original path) | Set to 1 on first call by `$1F6AF2` |
| `$FFCD7C` | New-engine flag | Tested by `$1F6B72` |
| `$FFFB94` | OST state struct, magic `$A3B1` | Mode byte `$FFFB96` ∈ {1,2,3}, word `$FFFB9A`; countdown `$FFFB9E` from `$3C` |
| `$2FD51C` | Song switch | Called when the `$2FD470` "should use new music?" decision changes (`$FFFB98`) |
| `$0D63E4` | Location→song table — **UNCHANGED (0/256 B differ)** | Same song-per-location mapping as the original |
| `$2FD470` | "Should use new music?" decision | Reads `$D63E7`, nibble 1 or 3; else `$FF0E16` in 9..0x225 |
| `$2FD32C`/`$2FD336` | OST wrappers → `$2FD36A` | Mode 3 → `$FFFB9A = 0x96` (150) |

## Dirty-cell renderer

| Address | What | Evidence |
|---|---|---|
| `$E358` | `map_terrain_tile_lookup` — hook point | Prologue intact to `$E36A`, then `jmp $FEE0C` |
| `$E370` | Hooked → `jmp $435C0` (new viewport bounds check) | Original `moveq`/`and.w` replaced |
| `$E378–$E37C` | Original bounds check NOPed out | `cmp.w #$FFEB,d1; blt $11074` removed |
| `$E37E` | `lea.l $37E38C,a1` replaces `lea.l $5F524,a1` | New terrain offset table (see below) |
| `$FEE0C` | Dirty-cell entry | `tst.b $FF6BE0`; clear → original flow; set → `jmp $FFF46` |
| `$FFF46` | New per-cell lookup | Iso projection, rolling hash (`rol.l #5` + XOR), viewport clip, work list at `$10(a1)` bounded by `$FF7D40` |
| `$FEE88` | Per-cell routine | Hash compare vs `$FFECA4`/`$FF7D40` tables; unchanged + flag clear → skip; changed → `$FEF1C` bounds + `$FEF84` redraw; hash set to sentinel `$6B8B4567` |
| `$FEF1C` | Bounding min/max update | Called on changed cells |
| `$FEF84` | Cell redraw | Called on changed cells |
| `$FF6BE0` | Dirty-cell mode flag + state struct (26 refs) | Fields `$38`/`$3A`/`$80` camera/scroll; `$4` index, `$6` cell count (< `$FF`), `$1E` limit, `$3E` force flag |
| `$FFECA4` | Per-cell hash table (6 refs) | Slot `$FFECA4 + cell*4` |
| `$FF7D40` | Second hash table (13 refs) | Slot `$FF7D40 + cell*4` |
| `$FFCA54–$FFCA57` | Viewport bounds (RAM) | Used by `$101ACE` |
| `$101ACE` | **Viewport-visibility test, not a redraw step** | Compares cell's 4 bytes vs bounds; returns d1 = 0 (inside) / 1 (outside); single caller `$FEED4` |
| `$FD7C8` | Scroll-offset computation | Player cell + camera fields → `$80(a1)`; sub-cell math (`*8`, `asr #1`) |
| `$435C0` | New viewport bounds check | d1 in `-32..111`, d0 in `0x40..0x18A` (or `0x18C`); out → `jmp $11074`; original `$435C0` was unrelated data |
| `$FEE58` / `$FEE78` | Entry points calling `$FEE88` | Re-enter original `$1BA66` (`map_chunk_pos` cell head) and `$1C0D6` (spell step) — same two hooks as the topdown patch |
| `$101B88` | Per-cell driver | `bsr $101BCA; bsr $101BE2`; called only from `$1C1E2` (rewritten scroll code `$1C1CA`) |
| `$101B0A` | Tile-buffer shift routine | Shifts 0x1A-longword buffer at `$FFF820`; calls `$FF552` |
| `$FF552` | Xorshift PRNG | State `$FFF88C`, seed `$2545F491`; drives staggered terrain-animation phase |
| `$FF584` | PRNG-adjacent reset routine | `clr.w $FFEC84; move.w #$FFFF,$FF0098/$FF009A/$FF009C` |

## Terrain data

| Address | What | Evidence |
|---|---|---|
| `$37E38C` | New terrain offset table (extra 3 MB) | `lea $37E38C,a0; movea.l (a0,d2.w),a0; adda.l #$603E4,a0` at `$105716–$105724` |
| `$603E4` / `$433C0` | Terrain tile data bases — **unchanged original data** | 0 B differ; the NEW part is the `$37E38C` offset table, not these blocks |
| `$5F524` | Original terrain pointer table | Also indexes `$603E4` (`$114AA6–$114ABA`) |

## Full-screen map and camera

| Address | What | Evidence |
|---|---|---|
| `$12D42` | `world_map_draw` — parchment-frame draw call NOPed out | Frame simply not drawn; VDP R17 not reconfigured |
| `$12D72` | Draw width `$33C` (828) → `$4F2` (1266) | Wider draw area passed to `$11B58` |
| `$12D9C` | `move.w d0,$FF867A` → `jsr $1AC8C2` | New routine in the extra 3 MB |
| `$FFF8F8` | Sub-pixel scroll accumulator | `d0 = (d4-d5)*14 + $FFF8F8; d1 = d0>>3` (pixel scroll), remainder `& 7` kept; 1/8-pixel steps |
| `$1013A4` | Accumulator added to VDP hardware scroll | Before the `$C00004`/`$C00000` writes |
| `$FF6C18` / `$FF6C1A` | Camera fields `$38`/`$3A` | Set at `$FEE2E` (default `$38=$D4`, `$3A=$12`) or `$FEE3A–$FEE4A` |
| — | No camera-trailing/lerp variable found | "Gliding" is sub-pixel stepping, not a lagging camera |

## Movement — 8-direction walking, wall sliding

| Address | What | Evidence |
|---|---|---|
| `$24984` | `combat_move_unit` — head hooked `jmp $1F0028` | Second hook at `$249DC` → `jmp $FE8B0` |
| `$1F0028` | New movement dispatcher | Precondition chain (d0 `0..0x38`, `$FF02B2`, `$FF010F` bit 0 clear, `$FF0110 == 0`, magic `$5313` at `$FFFB80`); type 6 → `$1F0CDC` |
| `$1F0CDC` | Type-6 diagonal movement | Decomposes diagonal into separate x and y cardinal moves via `$1F03C2` |
| `$1F03C2` | Cardinal move attempt | `jmp $2498C` (original move body); step normaliser `$1F0486` |
| `$1F0482` | Diagonal reject | Both deltas non-zero → return 0; the caller tries each axis separately — **that is the wall slide** |
| `$FE8B0` | Second hook | Type-6 check vs per-entity flag table `$FFEC40`; set → move-succeeded path `$249EC` |
| `$FF010F` bit 0 | New-map mode flag | Gates the new shimmer (`$38938` → `$3602A`) and movement preconditions |
| `$FF0110` | Movement gate | Must be 0 for the dispatcher to proceed |

## Save — EEPROM → SRAM

| Address | What | Evidence |
|---|---|---|
| `$200001–$203FFF` | 16 KB SRAM (odd addresses), header type `0xF8` | Original declares no backup RAM |
| `$42E00–$43238` | EEPROM bit-bang helpers — 90% rewritten | 975/1080 B differ |
| `$43020` | New SRAM read | `move.b #1,$A130F1` (SRAM enable), `lea.l $200001,a1`, ×2 stride (odd addresses only) |
| `$A130F1` | SRAM control | Referenced at `$43020` |
| `$1F2000` | Quest notebook, ASCII `NOTE` magic | Checked at `$43054`; entries at `$1F20B4`, `$1F20D4`, `$1F257A` |
| `$177B4` / `$176A0` | Save validation (magic `0x2A`) / parity — **kept** | `$177B4` unchanged; `$176A0` 6 B changed only |
| `$4323C` | Boot save check — unchanged | 0/512 B differ |

## Boot and new-code pages

| Address | What | Evidence |
|---|---|---|
| `$100000` | New-code page, ASCII magic `PAD6` + bra.w jump table | Entries `$100004` → `$100010`, `$100008` → `$100072`, `$10000C` → `$100144`, … |
| `$3AA` | Boot hook `jmp $100004` | Replaces `move.b #$40,$A10009` |
| `$100010` | 6-button pad controller read | Reads `$A10003`/`$A10005` via `$1000A2` bit-bang; X/Y/Z/Mode bits 7/8/9/10; stores `$FFCD70`/`$FFCD72`/`$FFC00E`/`$FFC010` |
| `$100072` | Second jump-table entry | Also calls `$10025E` |
| `$102xxx–$105xxx` | Largest unexplored new-code area | Candidate for the dragon sprite/portrait data |

## VBlank and input

| Address | What | Evidence |
|---|---|---|
| `$1272` | VBlank ISR rewritten | Starts `jmp $1F7046`; controller bit-bang reads NOPed; `jsr $EB772` → `jsr $2FD22E` (music manager); input-queue ring code `$1314–$134A` unchanged |
| `$1F7046` | ISR entry | Sets flag `$FFCD6F`, `jmp $1B1FF4` (bra.w table in extra 3 MB) |
| `$1F7052` | ISR exit | Clears `$FFCD6F`, calls `$1F6FD4`, `rte` |
| `$1F6FD4` | Z80/sound watchdog | Waits for Z80 bus, checks Z80 RAM `'R'`/`'M'` magic at `$D0`/`$D1` |
| `$1350` | `joypad_queue_pop` — **UNCHANGED** | Remix does NOT fix the input-buffering defect (60 changed bytes in its window are erased SFX data) |

## Waterfall animation vs clouds — gating defect, not missing data

| Address | What | Evidence |
|---|---|---|
| `$232D2` | `map_animated_tile` rerouted (140/512 B differ) | Both `$E358` lookups replaced by calls to new dispatch `$11207C` (`$233A2`, `$234B0`) |
| `$11207C` | New per-tile dispatch (bra.w jump table) | Handlers `$1120CA`, `$112EA0`, `$112FA8`, `$113318`, `$11344A`, `$113926`, `$1145BA`, `$112E76`, `$114194` |
| `$1120CA` | First handler | Gates on `$FFEC2A`, tiles `$200`/`$201` (flag `$1120B4` reads `0x0000` → unconditional skip), `$FF6BE0` (dirty-cell flag), `$FFCA72` animation mode, tile ranges `$3B0..$3DA` → table `$1AC512` |
| `$197B0` | Animation frame-counter records — **unchanged** | 0/1024 B differ; waterfall data intact |
| `$38938` | `map_animate_tiles` hooked → `$3602A` | `$FF010F` bit 0 set → new list-driven shimmer; clear → original body |
| `$FFC602` | Shimmer tile list, **capped at 255 entries** | Count `$FFC600`; populated as tiles are drawn (`$1BEE82`/`$1BEF06`); cleared by `$35E22` |
| `$FF012A` | Frame parity | Shimmer toggles listed tiles' low bit by parity; skips tiles 495 (`$1EF`) and 213 (`$D5`) |
| `$13D84` | `world_sprites_setup` — three sprite_write calls NOPed | At `$14100`, `$1412E`, `$1415C` (tiles `$13`/`$14`/`$15`); fourth call (`$1418A`, tile `$16`) intact |
| — | Exact cloud gate unresolved | Candidates: (a) the `$FF6BE0` gate in `$1120CA`, (b) the 255-entry `$FFC602` list cap; runtime watch of `$FF6BE0`, `$FF010F` bit 0, `$FFC600` + list contents, `$FFCA72` while clouds are on screen |

## Dragon opening — 2D animated cutscene (corrected)

| Fact | Evidence |
|---|---|
| Not 3D, not a scripted flight over the live map | Live stable-retro frames `captures/dragon-md2/` (report §8.9) |
| Sequence: "The Adventure Begins" card over starry sky → starry sky, twinkling stars → sky lightens to blue, pink clouds, distant dragon silhouette → orange wyvern close-up from below, big wings spread → wyvern small/distant toward a coastal city at sunset → city alone → fade → gameplay (song 2) | Frame captures f2490–f4120 |
| Ocean/city dragon shots are **gameplay** — riding the dragon as a vehicle over the live map (HUD visible) | `dragon-flight-ocean.png`, `dragon-flight-city.png` |
| Dragon is most likely entity type 6 | Movement hook `$1F0028` routes type-6 entities to `$1F0CDC`; `$FE8B0` checks type-6 flag table `$FFEC40` |
| Dragon sprite/portrait data not located to a precise address | Candidate: new-code page `$102xxx–$105xxx` |

## Open / unresolved

- Which OST table is OLD vs NEW (`$FFCD7D==1 → $1F6200`, `==2 → $1F6800`; mode 0 → original path, likely unreachable/broken).
- `$1F62AE` remap keys `$1Bxxxx` point at `$FF`-filled areas — second-level indirection or an earlier layout?
- Exact cloud gate (§ Waterfall above) — runtime watch needed.
- `$1120B4` flag reads `0x0000`, so tiles `$200`/`$201` are unconditionally skipped by `$1120CA`.
- Remap targets sharing identical first 48 bytes (`$1D8000` = `$2DF400`, `$1D9820` = `$3BEBF0`, `$1DB6D0` = `$3BF5D0`) — OLD/NEW duplication suspected, not proven.
