# Smooth picture: why the original is jerky, the top-down test, and the path to a Landstalker-style view (#249)

Status: measured 2026-11-23 on the original ROM and on `make rom
FEATURES=topdown`, frame-stepped in Genesis Plus GX (`tools/md_run.py`,
`tools/md_smooth.py`). Patch: `patches/topdown/README.md`.

![](img/topdown-vs-original.png)

*Left: original. Right: topdown. Overworld walk, the Academy room,
the Buc cutscene (same dialogue line, same positions).*

## Short answers

- **Can the game be made smooth on its own engine?** Yes. With the
  world picture replaced by a cheap one, the same game logic runs at
  the original pace with the picture moving every frame in 1-px steps,
  and the 68000 waits for the next tick on 92–93 % of frames.
- **Can the world be split into chunks?** It already is: 252 chunks of
  32×32 (overworld, big rooms) or 11×11 cells, behind a 4-slot cache
  (`map_chunk_cache_read`). The top-down view streams it through a
  32×16-cell ring buffer on the plane, one column or row per cell
  crossed; nothing is decoded per tick.
- **Why didn't the faster-render patches help?** Because render cost is
  only one of five causes, and fixing it alone makes the game *run
  faster*, not move smoother (cause 1 below).

## Five causes (original ROM, measured)

1. **No frame lock.** One main-loop pass = world tick + full render, so
   game speed *is* render speed: 26.7 frames per tick in the overworld
   (25–30), 17.0 in the Academy room, ~22 in the 32×32 room 156. Speed
   differs per scene, and every render speedup sped the game up (the
   "cutscene fast as rocket" verdicts of #234).
2. **Full software re-render every tick.** Clear 26 KB, decode 100 cell
   tops + height stacks with `$E358`, draw figures into the same
   bitmap: ~16 frames per tick (`docs/subcell.md`).
3. **26,496-byte DMA during active display.** The room bank is uploaded
   whenever the render ends, not in VBlank; the VDP feeds active-display
   DMA a few bytes per line, so each update reaches the screen over 3–5
   consecutive frames (torn), with the 68000 held meanwhile.
4. **The picture lives in the window plane**, which the VDP cannot
   scroll (#242): every movement needs a new picture.
5. **Figures are baked into the bitmap at integer cells**: no
   independent figure motion, no sub-cell positions.

## What the top-down test does about each

| Cause | topdown |
|---|---|
| 1 | Frame-locked tick: `td_tick` waits until 26 (overworld) / 17 (rooms) frames have passed. Pace measured: 26.0 / 17.0 frames per tick. |
| 2 | No per-tick render. Cells are drawn once, when they scroll in: 15 or 21 cells per cell crossed; 315 on a scene change. |
| 3 | No bulk DMA in play. Per frame: 2 scroll words + ≤ 12 sprites, written only inside VBlank (a poll that finds the frame past VBlank skips it rather than tear). |
| 4 | World on Plane A/B (table `$0000`, 64×32); the window keeps HUD/menus, its room cells point at the transparent font blank. |
| 5 | Characters are sprites; each slides from where it is drawn to its new cell over one tick; the camera follows the leader's sprite. |

| Measure | original | topdown |
|---|---|---|
| Overworld walk, picture change | one redraw per tick, torn over 3–5 frames | 2,248 × 1 px, 56 × 2 px, 1 × 3 px scroll steps in 13,000 frames |
| Room walk, leader figure | one-cell jump per tick | 272 × 1 px steps, never hidden, 1,150 frames |
| Main thread idle (waiting for the tick) | 0 % | 92–93 % of frames |
| Buc cutscene end state | Buc (6,25) | Buc (6,25) |
| 3 × 30,000 random-input frames | — | no crash, no hang |

The 56 two-pixel steps are frames where no safe point fell inside
VBlank (long game routines); 52 of them follow a held frame.

## Path to a Landstalker-style isometric view

What makes Landstalker smooth is the same split topdown uses: the
background is a ready-made tilemap scrolled by the hardware, characters
are sprites, and the loop is frame-locked. Its 3D look is baked into
the tiles before the game runs; nothing is composed per frame. Rings
of Power composes its isometric picture at run time (cause 2), and the
composition overlaps neighbouring cells, so there is no per-cell tile to
cache (#231). The fix is to move the composition offline:

1. **Keep the topdown scheduler as is** — tick governor, per-frame
   VBlank updates, slides, ring-buffer streaming. It does not care what
   the tiles look like.
2. **Pre-render the isometric world offline.** Port the `$E358`
   composite to Python and check it byte-for-byte against `$FF1EC0`
   captures from the original (`tools/md_run.py` reads RAM per frame).
   Render each location once, cut it into 8×8 tiles, deduplicate, and
   emit per-area tile sets + tilemaps.
3. **Size it.** The original's 36×23-tile view holds 249 distinct tiles
   on average (510 max) out of 828. A pre-rendered map aligns tiles
   globally and repeats far more, but the overworld image is large
   (352×224 cells), so its atlas plus tilemap will not fit in the 12 KB
   left in the 1 MB ROM; a 2–4 MB ROM (no mapper needed up to 4 MB) is
   the expected container. Rooms are small. Step 2 gives exact numbers.
4. **Stream it** through the same ring buffer, isometric rows instead
   of square cells, switching tile sets at chunk or location edges;
   figures as sprites (their `$197B0` template images), tall objects
   in front via Plane A priority tiles.

Until step 2 exists, topdown is the playable smooth build.

## Tools

- `tools/md_run.py` — frame-stepped runner (stable-retro / Genesis Plus
  GX): route files as for the input-replay overlay, per-frame RAM words
  and screen CRC, screenshots. ~500 frames/s, no X display.
- `tools/md_smooth.py` — per-frame background shift (best translation
  in ±4 px), redraws, palette changes, and the slot-68 blob position,
  from the rendered frames.
- `tools/md_vram.py` — VRAM/CRAM/VSRAM/registers from a GPGX state.
- `tools/md_video.py` — side-by-side 60 fps MP4 of ROMs on routes.

One emulator per process (stable-retro limit); `md_video.py` forks.
