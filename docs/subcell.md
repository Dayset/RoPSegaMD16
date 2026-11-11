# Sub-cell movement reference (#27, #31)

Status: cutscene mechanism traced live (2026-11-11, see "Cutscene sub-cell mechanism"). Player-walk patch not started.

## Repro (#31)
- `tools/walk_repro.sh ROM STATE KEYS [FRAMES]` runs BlastEm from a state, sends keys, writes `build/walk-repro/events.bin`.
- Route: New Game → `1R 8U 5R 4U 1L 1S` → `4L 10U 17L 1Dn` → `d`, `a`, `a` (Buc cutscene).
- Keys were not verified in this CI VM (xdotool keys did not reach BlastEm here). Confirm bindings on the run machine.
- A 60 fps capture comes from the run machine (ROM not in this repo).

## Scroll writers (static, from disasm/src/rop.s)
- `$DC16` (`vdp_set_scroll`): writes VSRAM 0–1 (vertical) and VRAM `$2000` 0–1 (horizontal). Callers: `$11E06`, `$12C20`, `$1702C`, `$166FA`, `$16D6A` (map scroll, `(v,v,h,h)`).
- `$171D6` (`vdp_write_hscroll_wave`): per-line H-scroll table writer with a wave term. Callers: `$1511C`, `$1544A`, `$1546E` (in the function labelled `intro_helper`), `$161DC`, `$18E08` (in `scene_draw`).
- Per-line H-scroll (R11=`$03`) is set at `$15D6E`, `$17D08`, `$18C40` (docs/graphics.md §6.x).
- `$1C21A` is the position setter (mode 6) and `$1B918` the redraw checker (docs/architecture.md).

## Open
- Which caller the Buc cutscene uses. Needs a `-l` address log from the cutscene state.
- Label conflict: `$161DC` sits inside the function labelled `snd_music_start` in rop.s. Recorded as a question; not resolved here.

## Cell-commit point (#28, static)
- Position setter `$1C21A` adds whole-cell deltas to `ram_sys_ff0e8e` (X, `$1C2D8`) and `ram_sys_ff0e90` (Y, `$1C300`); mode-6 init writes them at `$1C242`/`$1C264`.
- Redraw request: `ram_sys_ff0098 = $FFFF` at `$1BA1A`/`$1BA2A`. The checker `redraw_check` (`$1B918`) consumes it and calls `map_chunk_pos` with the committed cell (`$1B96A`).
- So the scroll is derived from the committed cell. Sub-cell motion needs an offset between the commit and the redraw, which the original does not have.
- Not yet implemented: the interpolation patch, input queueing, and frame-accurate checks. Those need the live capture (#31) and are not done here.

## Measured walk timing (#27, #28)
Source: BlastEm recording at 60.4 fps (640x480), walk started from `slot_0.state` after dialog #1 (D) and dialog #2 (A, A).
- Cell steps: large frame-to-frame changes (mean abs diff 6.6–9.2 on 0–255) at 9987, 12542, 13836, 15164, 16458, 17785, 19079, 20406 ms (video time).
- Step interval: 1294–1328 ms, about 79 frames at 60.4 fps.
- Between steps: a small change (mean abs diff ~0.6) on nearly every frame. Consistent with sub-cell motion or per-frame animation. Not yet separated from character animation.
- Debugger, same run type: X cell `0x0006` fixed; Y cell `0x0012`→`0x0017`, one cell per step, each Y commit preceded by an X write (`0x1C2D8` then `0x1C300`).
- Open: map video time to keypress time (video start not aligned to the AHK F9 start); confirm the 60.4 fps rate (container reports ~30.1 fps).

## Exact frame counts from the debugger (#127)
The game keeps its own frame counter: long `$FF0010`, `addq.l #1` at `$127A` in `vblank_handler`, once per vblank. Read it at each Y commit instead of counting vblank breakpoint stops. No vblank breakpoint, so the game runs freely and keys register.

```
blastem -d -s slot_0.state rom-original.gen
di/d 0xFF0010.l     prints L = counter at state load, and again at every stop
di/x d0             low word = Y about to be written at $1C300
b 0x1C300
c                   press D, A (dialog 1), A (dialog 2) in the game window
c                   at each "68K Breakpoint 0 hit", just c again
```
- Frame of a Y commit since load = printed counter − L. Frames per step = difference between consecutive stops.
- Verified on BlastEm 0.6.3 (Linux): `di/d 0xFF0010.l` prints `0xFF0010.l: N` at every stop; counter steps by exactly 1 per vblank.
- BlastEm 0.6.3 quirks seen here: it sometimes aborts at startup (`stack smashing detected`), rerun; `co` command lists did not parse (`end` unrecognized), so use `di`.
- Results (BlastEm 0.6.3, own state at the same spot: New Game route below to cell (7,7), then `d`, `a`, `a`; not `slot_0.state`):

| commit | Y (d0 low word) | frame | frames since previous |
|---|---|---|---|
| 1 | `$12` | 15009 | |
| 2 | `$13` | 15082 | 73 |
| 3 | `$14` | 15156 | 74 |
| 4 | `$15` | 15230 | 74 |
| 5 | `$16` | 15304 | 74 |
| 6 | `$17` | 15380 | 76 |
| 7 | `$18` | 15454 | 74 |
| 8 | `$19` | 15529 | 75 |

  X stays `$06`. Mean 74.3 frames per cell (≈1.24 s at 59.92 Hz). The 79-frame figure from the video is a capture-rate artefact. Re-runs from a save made before `d` give the same 74-frame spacing (14401, 14474, 14548, 14622, 14696).

## Cutscene sub-cell mechanism (#27, #28, live 2026-11-11)
Traced in BlastEm 0.6.3 debugger from the save before `d`, breakpoints logged with `$FF0010`.

- **No scroll and no sprites.** `vdp_set_scroll` (`$DC16`) is never called during the walk. `vs` shows only HUD sprites (dialog frame, pad icon); `sprite_write` callers are the HUD set `$13916`–`$13C58`, same as idle. Figures are software-rendered into the planes.
- **World tick every 18–19 frames.** The tick routine (`$226BC`, labelled `combat_turn_run`) ends at `$231CA` `jsr redraw_flag_set`. 19 hits in 355 frames. Each tick, `redraw_check` (`$1B918`) re-renders the room into `$FF1EC0` via `map_chunk_pos` and uploads it with `dma_upload` at `$1B9E8` (`$33C0` words). That DMA is the only upload during the walk (25 hits in 468 frames).
- **4-phase animation counter = sub-cell step.** `geom+$A` (here `$FFB0B6`; `$FFA7FC` = `$FFB0AC` in this room) logged at each tick: 0, 1, 2, 3, 0, … The cell commit (`$1C300`) lands on the 3→0 wrap, so one cell = 4 ticks = 74 frames.
- **Entity cells do not move between commits.** Entity records (`$FF02B4 + i×$34`, cell at +`$C`/+`$E`, previous cell at +`$10`/+`$12`) change only at the commit frame. The two walkers are entities 1 (X `$06`) and 3 (X `$08`).
- **The offset comes from the draw template.** Walker draw records at `$FFB0CC` (records 0 and 1) have +2 = 2, +4 = `$24`, i.e. `$197B0` template 38. Its 4 groups (stream offset, param, dx, dy) are (0,0,0,0), (6,0,−4,2), (1,0,6,−4), (7,0,2,−2), tail (3,2). The renderer (`hero_track` `$231D8`, called from `map_chunk_pos` at `$1BD98`/`$1BF14`) adds group[`geom+$A`] dx/dy to the figure's screen position and picks the image frame. Non-walking figures use templates 5 and 7 (no offsets).
- Screen check (Xvfb grabs every 0.15 s): between cell jumps only a ~170×120 px box around the figures changes (≈5.5k px vs ≈60k px at a jump); the walker's outline shifts a few pixels on each of the 3 updates (one direction), then snaps back when the room jumps one cell.
- **Reusable for #28:** the per-tick 4-phase template (templates 36–55) already gives pixel offsets per phase. A smooth player walk can: keep the leader's cell commit at phase 3→0, draw the leader with a walk template during the 3 in-between ticks, and offset the room render by the same phase fraction. The camera jump at commit is what still needs an offset (the cutscene does not have one).
- Route note: `1S` in the repro route is the `s` key (B); the first press of a new direction may only turn the figure (no cell change).

## Movement sequence (observed in the 60.4 fps recording, #28)
1. Start: first cell step begins (video ≈ 9987 ms).
2. Stop: step ends, screen holds still.
3. World move: whole-screen scroll.
4. Character move: character advances one cell.
5. Sub-cell move: small per-frame motion between cell steps (mean diff ≈ 0.6).
