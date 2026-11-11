# Sub-cell movement reference (#27, #31)

Status: partial. Static findings only. The Buc cutscene offset path is not yet traced.

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
- Results table: not yet run (needs `slot_0.state` from the run machine).

## Movement sequence (observed in the 60.4 fps recording, #28)
1. Start: first cell step begins (video ≈ 9987 ms).
2. Stop: step ends, screen holds still.
3. World move: whole-screen scroll.
4. Character move: character advances one cell.
5. Sub-cell move: small per-frame motion between cell steps (mean diff ≈ 0.6).
