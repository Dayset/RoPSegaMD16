# topdown — smooth top-down test view on the original engine (#249)

A test build that keeps the whole game (logic, input, menus, messages,
map data, RAM) and replaces only the world picture with a cheap
top-down one: the world as 16×16 blocks, characters as 16×16 blobs,
scrolled and moved every frame.

```
make rom FEATURES=topdown        # -> build/rop-topdown.rom (+ .ips)
```

![](../../docs/img/topdown-vs-original.png)

## What you see

- **World:** one 16×16 block per map cell, from the game's own map
  tileset (record 10, the tiles the map screen uses) through the
  descriptor table `$1AE98`, pixel-doubled at load time. Day/night
  works (palette slot 0 is the world palette, as in the original).
- **Blobs:** every character with a map-draw record. Yellow = the party
  leader's figure (the leader, or the type-4 avatar that redirects to
  it in rooms), white = everyone else. Up to 12 on screen.
- **Camera:** follows the leader's blob, centred on screen line 84 (the
  HUD covers the bottom), clamped to the map; maps smaller than the
  screen (11×11 rooms) are centred.
- HUD, messages and menus are the game's own window-plane drawing,
  unchanged. While a menu is open the blobs are taken off.

## Measured (tools/md_smooth.py, frame-stepped GPGX, no human eye)

| | original | topdown |
|---|---|---|
| World tick, overworld | 26.7 frames (25–30) | 26.0 frames (24–28) |
| World tick, Academy room | 17.0 frames | 17.0 frames |
| Overworld walk: picture change | one redraw per tick, torn over 3–5 frames by the 26 KB DMA | scroll every frame the camera moves: 2,248 × 1 px, 56 × 2 px, 1 × 3 px in 13,000 frames |
| Room walk: leader figure | jumps one cell per tick | 272 × 1 px steps, 0 jumps in 1,150 frames |
| Whole-picture redraws while walking | every tick | 0 (scene changes only) |
| Main thread waiting for the next tick | 0 % (render-bound) | 92–93 % of frames |
| Buc cutscene (TALK Thalmus, A, A) | Buc ends at (6,25) | Buc ends at (6,25) |
| 3 × 30,000 random-input frames | — | no crash, no hang (longest VBlank gap = a soft reset, same as original) |

Routes: `tools/playtest_route_orig.txt`, `tools/playtest_route_topdown_explore.txt`,
`tools/playtest_route_buc_topdown.txt` (the original needs
`playtest_route_buc_orig.txt`: same targets, its own frame timing).

## How it works

**Frame-locked tick.** The original main loop has no frame lock: one
iteration = world tick + render, so game speed *is* render speed
(17–30 frames per tick depending on the scene). `td_tick` replaces the
render inside `redraw_check`: it waits until the tick period has passed
(TD_T1 = 26 overworld, TD_T2 = 17 rooms — the measured original pace),
and spends the wait updating the picture once per frame.

**One update per frame, only inside VBlank.** An update (`td_frame`)
recomputes the blob positions, the camera, writes the scroll and the
sprites, then streams cells. It runs from safe points of the main
thread — never from the interrupt, because the game writes the VDP
from everywhere and an interrupt would break its address sequences:
the tick wait, the main-loop head, before `combat_turn_run`, the head
of its 56-character loop, after `menu_format`, and inside
`wait_vblank` (messages, menus). A poll that finds the frame already
past VBlank skips it rather than tear; ~2 % of frames are held and
caught up next frame (the 2 px steps above).

**Slides.** A character's cell changes once per tick. Each blob keeps
(target cell, from-pixel, start frame) and moves linearly to the target
over one tick period, starting from where it is drawn now — a step that
lands before the previous slide ended continues smoothly instead of
jumping. Moves of more than 2 cells (doors, teleports) snap.

**Ring-buffer streaming = the world in chunks.** The plane is 64×32
tiles = 32×16 cells; the view needs 21×15. When the camera crosses a
cell edge, one new column (15 cells) or row (21 cells) is read with the
game's own `map_chunk_cache_read` (its 4-slot chunk cache, 32×32-cell
chunks) and written off-screen. A full redraw (315 cells, ~3 frames)
happens only on a scene change. Inside `wait_vblank` the update does
not stream (the caller may hold game state) and the camera is clamped
to the cells already in the plane.

**Window plane.** The original draws the room picture into the
full-screen window as an identity map of 828 tiles at `$FF8674`, over
the parchment on Plane B. Here Plane A/B (table `$0000`, 64×32) carry
the world; every window word that points into the room bitmap is
written as the transparent font blank — at the source, in
`gfx_tilemap_draw` / `gfx_tilemap_fill_seq` (`td_vdw`), plus a full
scan per tick as a backstop. The freed room bank holds our tiles: 256
map quadrants, 1 blank, 16 blob tiles.

**Sprites.** Blobs use slots 68–79 (the game's chain ends at 67) and
are linked in at the head of the chain: sprite 0 → blobs → the game's
first sprite. `menu_format` rewrites sprite 0 every pass, so the update
after it re-links.

### Hooks

| Site | Was | Now |
|---|---|---|
| `$00D2BE` | `tst.w $FF00AC` (main loop head) | `jsr td_poll_head` |
| `$00D97E` | `jsr combat_turn_run` | `jsr td_poll_turn` |
| `$0118A6` | `jsr vdp_data_write` (gfx_tilemap_draw) | `jsr td_vdw` |
| `$01191A` | `jsr vdp_data_write` (gfx_tilemap_fill_seq) | `jsr td_vdw` |
| `$013876` | `move.w $FF0016,d0` (wait_vblank loop) | `jsr td_wv` |
| `$01B958` | `jsr clear_decode_buffer` | `jsr td_tick` |
| `$01B95E` | `move.w $FF0E90,-(a7)` … `jsr map_chunk_pos` | `bra $01B970` |
| `$01B97E` | `jsr menu_format` | `jsr td_menufmt` |
| `$01B9D0` | `move.w #$33C0,-(a7)` (room DMA) | `bra $01B9F2` |
| `$0227FC` | `move.w d4,d0; muls.w #$34,d0` (char loop head) | `jsr td_poll` |

RAM `$FFDC00–$FFDF17` (free in play: the attract buffer ends at
`$FFDBEA`, the stack low-water mark on the test routes is `$FFE972`;
the boot RAM clear resets it). Blob ~4 KB in the `$FD0CC` padding.

## Limits (test build)

- Blobs only: no facing, no walk frames; projectiles and spell effects
  (drawn by the removed renderer) are not shown.
- `map_chunk_pos` is skipped entirely, so its record promotion between
  the two figure grids (`$2343A`, draw order only) no longer happens.
- One tick period per mode: rooms whose original render was slower
  than 17 frames (e.g. the 32×32 room 156: 22 frames/tick) now walk
  faster than the original. TD_T1/TD_T2 are the knobs.
- Sprite slots 68–79 assume the game's chain stays below 68 (true on
  every tested screen).
- Measured in Genesis Plus GX (stable-retro); smoke-tested in BlastEm
  0.6.3 (input-replay overlay moved to `$FF000`, overworld → room →
  walking, 4,700 frames). Not yet on hardware.
