# Sub-cell movement reference (#27, #31)

Status: cutscene mechanism traced live (2026-11-11, see "Cutscene sub-cell mechanism"). Player-walk subcell built and playtested 2026-11-12 (see "Player-walk subcell mechanism"). Current best walk ROM is `rop-walk-unused-frames.rom` (smooth walk, no teleport); the big rework (fractional camera / chunked world loading) is scoped in GitHub issues, not built.

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
- **Redraw cost per tick (#29, 2026-11-12, static).** The render costs ~11.4 frames of the 19–20-frame tick (~60%); the DMA is only ~0.5 frames (2.6%). `redraw_check` runs once per main-loop iteration; `$FF0098` is set unconditionally at the end of every `combat_turn_run` (loop over 56 chars, then `jsr redraw_flag_set` at `$0231CA`), so one full render per world tick. `map_chunk_pos` is `$01BA4E`: a 10×10 window centred on the leader −5 — 100 top-tile `$E358` calls (~8.5 frames; each decodes one whole ~182-byte terrain stream, 22 dispatches, ~10,900 cycles) + ~18 height-stack calls (~1.3 frames; "hidden levels" are the lower levels of a height stack, drawn with the `$230` filler tile — interior cells need bit 9 + height>0, edge cells height>0 only; measured over all 252 chunks / 119,889 cells) + `clear_decode_buffer` zeroing 26,496 bytes (~1.1 frames) + cache reads (~0.5) + DMA 26,496 bytes (~0.5). The DMA uploads the whole 36×23 room (36×23×32 = 26,496 B = `$33C0` words) to VRAM `0x71C0` even though only the 10×10 patch changed. Verdict: the tick is work-bound on these numbers, not a deliberate wait — but the render alone doesn't explain all 19–20 frames; ~7.5 frames are tick logic outside the redraw path, so cutting the render alone doesn't reach 60 fps. Cheapest cuts (options only): pre-decoded tile-pattern cache (~8 frames, needs ~10 KB free RAM, unverified); scroll-and-patch the room buffer (~5–7 frames net); dirty-region DMA (~0.4); clear only the patch (~0.9); skip hidden levels (~1.3, visible). Cycle counts are hand-counted estimates (±30%); live confirmation of the 11.4/7.5 split is open (breakpoints at `map_chunk_pos` entry/exit `$01BA4E`/`$01C0EA`, `dma_upload` `$00DA04`/`$00DA8C`, `combat_turn_run`).
- **Live correction to #29 (2026-11-12, measured, not estimated).** The render is **~16.0 frames/tick live, not ~11.4** (128 renders, 125×16 + 3×15); tick logic is **~2.4 frames** (`combat_turn_run`, 309/128), not ~7.5 — the static 7.5 was a residual that absorbed the render undercount; cadence in this window **~22.1 frames** (min 20, max 24), not 19–20; DMA 1 frame by the counter (~0.5 true). Decomposition: 22.13 = render 15.98 + DMA 1.00 + tick 2.41 + other 2.74. Per-call cost ~15,300 cycles (~71 cycles/pattern byte vs the hand-counted ~46) — the per-call cost, not the call count, was the weak link. Top/height `$E358` calls confirmed exactly 100/20 per render, plus 3 other-site calls per tick (animated-tile wrappers `$0232AC`/`$0232D2`, ~0.36 fr).
- **The tile cache does NOT fit (2026-11-12, live + simulator).** One `$E358` call paints a median **215 bytes scattered over a median 3,480-byte span** — not a contiguous 32-byte tile pattern — and neighbouring cells' calls **overlap by a median ~50 bytes** (up to 149): the decode is an and/or composite across cells, so no per-tile independent pattern exists; the write pattern is also not a pure translation across positions (79–87% match). A write-list cache would need ~205 KB and would still pay the per-byte and/or work. And no single free 10,176 B RAM region exists (largest apparently-free gap 8,514 B at `$FF868A–$FFA7CC`, 1,662 B short) — moot given the span result. No prototype was built (the task's stop condition). The ~8-frame saving estimate rested on the 32-byte-copy premise, which is false. Directions the numbers now favour: scroll-and-patch the room buffer; clear only the patch (~1.1 fr); skip hidden levels (~1.3 fr, visible). (Lead note: the cache-test report's `$436E0` "correction" is wrong — the original `(i//8)·0x480 + (i%8)·4` matches all 64 ROM entries; the simulator reads the table directly, so its results are unaffected.)
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

## Player-walk subcell mechanism (2026-11-12, built + playtested)

The player walk in the B-zoom view (mode 2, the room) now has the
cutscene's sub-cell machinery, built as a chain of one-fix ROMs on
top of the flat zoomed view (`rop-flat-zoomed.rom`) + feet fix
(`rop-flat-zoomed-feet.rom`). This section records the mechanism,
the ROM chain, and the playtest verdicts, so the big rework (fractional
camera / chunked world loading) starts from what is already known.
Original ROM untouched throughout (MD5
`30c18fdbe2183f64702ae9f1a45d63f9`).

### The sub-cell counter: grid+$A (0–3)

- Writer: `world_tick` `$02155E` sets grid+$A = (old+1) mod 4
  (`divs.w #4` at `$021572`–`$021580`). `$FFB0B6` is
  (ram_map_grid_base `$FFA7FC`)+$A — base `$FFB0AC` in the Buc room,
  `$FFB09C`/`$FFB08C`/`$FFB0BC` elsewhere.
- `$FF0094` = phase mod grid+$8 (derived in `world_tick`).
  `new_game_init` `$01B5D6` sets grid+$8 = **1** for the overworld
  (`$FFB08C`) and room grids `$FFB09C` / `$FFB0AC` (ROM-verified
  immediates `3F3C 0001` at `$01B6A8`/`$01B6AC`/`$01B6EC`), and 4
  only for `$FFB0BC` (`3F3C 0004` at `$01B70C`).
- **Cell commit on the phase 3→0 wrap.** The record stepper
  (`$022F52`) steps a draw record when its template stepphase matches
  the phase; `sys_event_run` runs only at grid+$A == 0 (`$022764`
  gate); the camera moves at phase 0. One cell = 4 ticks ≈ 74 frames
  (live: 74.3 frames/cell in the cutscene, §"Exact frame counts").

### Leader commits every tick in rooms (the pacing problem)

- `combat_turn_run` `$022790` runs the per-char movement loop only
  when `$FF0094 == 0`. In a room grid+$8 == 1, so
  `$FF0094 = phase mod 1 = 0` **always** — the gate never fires.
- Path A (`$022826`, mode 2) pops the leader's queued direction and
  calls `combat_move_unit` (`$024984`), which commits the cell
  (writes char X/Y at `$024CE8`–`$024D64`) with no phase gate. So
  Buc's cell commits **every tick** in the room — the figure jumps a
  full cell per tick and the walk template only adds a ±6 px wobble.
- Why the cutscene is smooth: `sys_event_run` runs only at
  grid+$A == 0 and the movement block is skipped while a script runs
  (`$FF0110 != 0`, `$0227C6`), so Buc moves one cell per 4 ticks
  via op-5. The player walk has no such gate — until the pacing gate.
- Precedent: the NPC wander path (`$022B56`) already gates its
  `combat_move_unit` call on grid+$A == 0.

### Pacing gate — 1 cell per 4 ticks (rop-pacing.rom)

- Hook in Path A at `$0228CC` (`cmpi.w #$4,-$e(a6)`, 6 bytes) →
  `jsr pace_gate`, blob 34 bytes at `$FD900`. If grid+$A != 0,
  discard the `jsr` return address and jump to `$022960` (the
  block's standard skip exit). If phase == 0, execute the displaced
  `cmpi.w` and return to `$0228D2`. Cell commits once per 4 ticks
  (phase 3→0 wrap).
- The hook sits **after** `queue_pop` deliberately: the direction
  queue still drains every tick, so no accumulation or
  direction-change lag. The queue is a 34-entry FIFO that drops
  pushes when full — gating before the pop would have filled it
  with the old direction and stalled direction changes up to 34
  cells.
- **A brief tap during phases 1–3 is discarded.** Holding a
  direction walks one cell per 4 ticks, as in the cutscene.
- Playtest (2026-11-12 ~21:57 EST): "Buc is not moving, just
  standing for 4 ticks, his cape moving but his feets are dead,
  then he teleports 1 cell." The gate works (cell commits once per
  4 ticks) but the slide is missing: pacing only delays WHEN the
  cell commits; it does not make the figure's drawn position slide
  between cells. Timing (21:59 EST): with a direction held, Buc
  moves at about half the normal game's speed; once the cutscene
  starts, he is extremely fast (the flat render makes each tick
  faster, so the script advances ~1.6× faster — the pacing gate
  never fires during a script).

### Interp slide — room-relative (rop-interp.rom)

- The cutscene does NOT slide across the screen — the camera
  follows the walker so the figure stays centred. Its smoothness is
  the walk template (38) cycling the image per phase (legs step) +
  a ±6 px dx/dy sway + the room jumping one cell per 4 ticks (world
  scrolls past), at 1 cell per 4 ticks. The template offsets are a
  sway, not a slide.
- A true on-screen slide is impossible in this framing (tile-based
  room, integer-cell camera), so the fix is a room-relative slide:
  the drawn cell interpolates old → new over phases 0–3 (0, ¼, ½, ¾,
  then commit). Step vectors measured from live `map_chunk_pos`
  tables: East (+14,+8), South (−14,+8), North (+14,−8),
  West (−14,−8).
- In `hero_track`, for Buc's record in mode 2, drawn X/Y are
  overridden to the interpolated slide position, with the walk-template
  dx/dy wobble subtracted (wobble ±6 px > one slide step ~3.5 px/phase,
  so leaving it would make motion non-monotonic). Image still cycles
  per phase (legs step). Slide applies only when no script runs
  (`$FF0110 == 0`), so the cutscene keeps walk template + wobble.
- Playtest (2026-11-12 ~22:28 EST): "This one is even slower, no
  subcell movement." Follow-up: "i was barely able to navigate
  through the academy, but cutscene went okay fast." Diagnosis
  (interp-fix report): the slide is room-relative, but the camera
  tracks the figure's committed cell exactly, so on screen the figure
  stays centred and the slide just oscillates ~10 px behind centre —
  net on-screen progress over a full step cycle is zero. Reads as "no
  subcell movement" / "standing then teleporting". The interp hook
  itself is sound; the failure is the interaction. A visible on-screen
  slide requires the camera NOT to jump with the cell — a camera delay
  or a smooth-scrolling (fractional) camera (the big rework).

### Camera — mode-6 absolute set, 3-cell dead zone

- Camera RAM `$FF0E8E` (X) / `$FF0E90` (Y); only runtime writer
  `leader_spawn` `$01C21A`. Mode 6 (absolute set) writes cam X at
  `$01C242` and cam Y at `$01C264` and snaps immediately; modes 0–3
  and 5 fall through to the step path (`$01C2D8`/`$01C300`).
- In the room grid+$C == 0 (verified via `table_init_b`: 0 for room
  grids, 1 for overworld), so `world_reposition_leader` (`$02513E`,
  `combat_move_unit`'s epilogue) takes the L0251EE path and calls
  `leader_spawn(mode 6)` — absolute set — on (nearly) every Buc step.
- **3-cell dead zone** (`world_reposition_leader` L025294):
  the camera only moves when Buc is 3+ cells from the camera centre
  (`|dX| >= 3` or `|dY| >= 3` via `cmp.w #$3`); else the target =
  the current camera. The camera stays put while Buc walks within
  3 cells, so the slide IS visible on screen without any delay.
- **Diagonal snap yoink (interp-fix3 diagnosis).** The L025294
  block (`$025294`–`$0252F8`) is all-or-nothing per axis pair: if
  EITHER |dX| or |dY| is >= 3, the target is Buc's cell on BOTH
  axes; if both are < 3, the target is the current camera on both.
  When Buc turns (e.g. east → north), his X offset is whatever it
  drifted to while walking east (0, 1, or 2), and his Y offset grows
  to 3 — so the camera snaps diagonally by (Xoffset, 3). That
  diagonal snap is the yoink; it fires ~2/3 of turns. Fix
  (interp-fix3): per-axis snap — an axis that has not crossed the
  3-cell dead zone keeps the current camera on that axis; only the
  crossed axis moves to Buc's cell. Hook at `$02529C`
  (`sub.w $FF0E8E,d0` → `jsr $FDE00.l`), blob 102 bytes at `$FDE00`,
  gated to mode 2 AND no script.
- **Camera delay is fundamentally flawed for the room**
  (interp-fix2 diagnosis). The interp-fix ROM delayed the camera
  one step (hooks on the step-mode writes `$01C2D8`/`$01C300`),
  but in the room the camera is set absolutely (mode 6, NOT hooked)
  on nearly every step and never clears the pending flag, so the
  step-mode hooks fire unpredictably and apply a STALE pending camera
  from a different step/direction → camera jumps to the wrong cell
  (off-screen), offset flips on turns (zigzag). The room camera needs
  NO delay. Reverted in interp-fix2.
- **Cutscene lag (probe-confirmed).** Buc's cutscene record has
  +10 == 1, so the record does not step in `combat_move_unit`
  during a script and waits for the record stepper at phase 2,
  while the camera moves at phase 0; the world jumps first, then
  Buc catches up (2 phases); lag at most 1 tick. In the original ROM
  they jump together (the room is re-rendered each tick with camera
  and figure at current positions). The record+10 value comes from
  the shipped data, so the 2-phase record lag exists in the original
  too, but at ~22 frames/tick it is less noticeable than at
  ~9 frames/tick on the flat ROM.

### Face rotation — pacing gate discards taps

- The v1 pacing gate discards ANY popped direction when grid+$A != 0
  (phases 1–3), before the dir==4 check, and the queue is drained
  by the pop, so a discarded tap is lost. A single tap lands on
  phase 0 only 1 time in 4, hence 3–4 presses to rotate the face
  after a stop (Dayset, interp-fix2 playtest 2026-11-12 ~23:34 EST).
- `combat_move_unit` updates Buc's heading (+0x0A, `$FF02F2`) to the
  new direction even when the step is blocked (the heading write at
  `$024D76` is in the shared epilogue, reached via the d4==0 skip) —
  so a tap in a new direction WOULD turn the face in one press if it
  reached `combat_move_unit`.
- Fix (interp-fix3): v2 pacing blob (58 bytes, replaces the v1 blob
  in place at `$FD900`; the `$0228CC` hook already points there).
  Turn check BEFORE the phase gate: if the popped direction
  (−$E(a6)) differs from Buc's heading (`$FF02F2`), the move goes
  through immediately. Same-direction moves keep the v1 phase gate,
  so walk pace (1 cell / 4 ticks) and slide are unchanged. The dir==4
  stop sentinel still works (takes the allow path, displaced `cmpi.w`
  sets the flags, Path A's `beq` skips the move).
- Known artifact (interp-fix3): a turn commits the cell mid-phase,
  so the interp slide starts at that phase's offset (e.g. a turn at
  phase 2 starts halfway) — Buc jumps about half a cell, then slides
  the rest. Legs still cycle, face turns in one press. Re-timing the
  slide would mean touching the interp blob — out of scope there.
- Playtest (interp-fix3, 2026-11-12 ~23:54 EST): "Subcell animation
  now is even more beautiful but turns are wonky, zigzag movement is
  the worst, cutscene in the previous one was better (smooth normal)
  this one does something strange like jumps forward." The wonky
  turns / worst zigzag are the mid-phase turn artifact (the half-cell
  jump on every turn). The cutscene jump-forward is not fully
  diagnosed (the per-axis snap and v2 pacing blob are gated to no
  script). Dayset's call (2026-11-12 ~23:56 EST): the smooth walk
  with no teleport is enough for now — the interp-fix3 line is parked.

### Walk templates (36–55)

- Template table `$197B0`: 36 bytes per template — 4 groups ×
  (stream offset, param, dx, dy) + tail (stepcode at +0x20,
  stepphase at +0x22). Template offset = template*36 + phase*8
  (`muls.w #$24,d0` in `hero_track`).
- Templates 0/4/5/6/7/29 static (all dx/dy 0,0). Templates 36–55
  are walk templates (stepcode = dir+1, stepphase 1–2).
  **Template 38 is the cutscene walkers' template** (Buc walking
  south); groups (0,0,0,0), (6,0,−4,2), (1,0,6,−4), (7,0,2,−2),
  tail stepcode 3, stepphase 2.
- Direction mapping (`world_get_step_delta` `$01E022`): dir 0=N,
  1=E, 2=S, 3=W. Walk template = 36 + dir. Per-direction walk
  frames (tile offsets): North (36): 8, 14, 9, 15; East (37):
  0, 6, 1, 7; South (38): 0, 6, 1, 7; West (39): 9, 14, 8, 15.
- Templates 16–27 are combat/cast, NOT walk: 16–19 = caster's cast
  pose (stepcode 5, stepphase 1), 20–23 = target resisted,
  24–27 = target hit (both static, stepcode 0). Offsets 4, 5, 10,
  11, 12, 13 are used by templates 16–27 — there are NO unused
  poses. See docs/spells.md §6.9 (PR #226).
- The record stepper (`$022F52`) steps a record when its template
  stepphase matches the phase; static templates have stepcode 0,
  routed to a fall-through no-op (jump table `$023076`).

### map_promote_record vs hero_track — the root cause of "no subcell movement"

- Record+$A selects the figure-draw routine in `map_chunk_pos`
  (jump table `$01BE86`): +$A=0 → `hero_track` `$0231D8`,
  +$A=1 → `map_promote_record` `$02343A`, +$A=2 →
  `map_tile_at_offset` `$0232AC`, +$A=3 → `map_animated_tile`
  `$0232D2`.
- **Buc's record+$A = 1** (probe-confirmed in the cutscene room),
  so **Buc is drawn via `map_promote_record`, NOT `hero_track`.**
  It reads the record's own template — static template 6 in the zoom
  view — so the image never cycles and the legs don't move. In the
  cutscene his record IS a walk template (38), so the legs move there.
- This is why the subcell, pacing, and interp ROMs (hooks only in
  `hero_track` at `$023202`) showed "no subcell movement" in the
  zoom view: the hooks never fired for Buc there. Fix (interp-fix2):
  hook `map_promote_record` at `$023480` (`lea.l $197B0,a0` →
  `jsr $FDA00.l`), routing it through the EXISTING interp blob
  (frame layout matches `hero_track` exactly — record 8(a6), X 12(a6),
  Y 14(a6), heightOff 16(a6), d0 template offset; blob saves/restores
  d1–d3/a0–a2, never touches d4/d5/a3/a6). `hero_track` hook kept
  intact (harmless).
- The feet-fix replay calls the recorded routine, so for Buc
  (`map_promote_record`) the hook fires at the actual draw time
  (during `fig_replay`, after the terrain is drawn) — the slide and
  template apply on the flat room, and the figure is drawn on top of
  the finished terrain (feet visible).

### ROM chain and playtest verdicts (2026-11-12)

| ROM | MD5 | Verdict |
|---|---|---|
| rop-subcell.rom | `fa3255df47fe90efc6cb1c36c2e495db` | "Can't see subcell movement here" (21:31 EST) — hooks only in `hero_track`, never fired for Buc |
| rop-pacing.rom | `6abeec0bea66365f223c75760983df8b` | Stand 4 ticks, cape moving, feet dead, then teleport 1 cell (21:57 EST); ~half speed held, cutscene "fast as rocket" (21:59 EST) |
| rop-interp.rom | `309d87c5a97cdbc5c2066f11a2f98399` | "Even slower, no subcell movement" (22:28 EST); "barely able to navigate through the academy, cutscene went okay fast" (22:29 EST) — camera cancellation |
| rop-interp-fix.rom | `44353892c7a006300bfae2535ad6eaf8` | "Legs not moving at all in zoom view, walking speed like default or slightly worse, BUC can run behind the screen, sometimes zigzag. Cutscene fast normal walking" (23:12 EST) — camera delay flawed for the room |
| rop-interp-fix2.rom | `30233662e411ecf0046ffc43c734c971` | "Walking smoother with subcell wow" (23:33 EST) — WORKS. Then: "camera yoinks on direction change, 3–4 short presses to rotate face after stop. If you hold direction he will walk beautifully" (23:34 EST) |
| rop-interp-fix3.rom | `8ada8b985aad8ae6c3929ae6d39d4139` | "Subcell even more beautiful but turns wonky, zigzag worst, cutscene jumps forward; previous cutscene better (smooth normal)" (23:54 EST) — parked per Dayset 23:56 EST |
| rop-walk-frames.rom | `a698a2f697939fd8a5b11b94837f32f7` | "Cutscene BUC slower than before, smooth but after 2 steps standing still longer, additional Y values did worse" (23:29 EST) — Y-shift hook never fired (hero_track only); slowness from 8-tick doubling |
| rop-walk-frames-fix.rom | `9ba279759436b96a732d11d9a3f6be0d` | "Walks even better than previous, no yoinks, movement begins with 1–2 press (rarely from 2nd) but cutscene Y completely off. 2 steps then waiting longer than usual and jumps screen, repeat" (23:38 EST) — zoom walk very good, cutscene Y off |
| rop-walk-unused-frames.rom | `6764e6ee86976e1a3607388f4cb5faa3` | **"BUC walks very good here, no stalls on direction, no funky camera, cutscene is smooth but nothing extra on top" (23:50 EST) — CURRENT BEST.** Y-shift hook off, 4-tick cadence restored |
| rop-cutscene-loop.rom | `79bccdcd927707802332f64f38faa641` | "He walks a bit more, at least ive seen other directions, still jumpy on world shift" (22:56 EST) — loop works, world shift jumpy (integer-cell camera) |

Walk-frames mechanism (for the record): loop driver steps Buc every
OTHER `sys_event_run` call (one cell per 8 ticks), so the 4-phase
template cycles twice per cell (each of 4 walk frames shown twice);
`walk_half` flag (`$FFD104`) tracks which half; the Y-shift hook
(blob `$FDA00`) draws Buc half a cell toward the next cell during
the second half (half-step table: N (+7,−4), E (+7,+4), S (−7,+4),
W (−7,−4)). Dayset's values for a south step: drawn Y 8, 12, 16, 20,
24 (step 4) instead of 8, 16, 24 (step 8). The Y shift decoupled
Buc's drawn position from the camera (half a cell ahead during the
second half; at a turn the half-step direction flips and the drawn
position jumps; when the camera re-centres, the screen jumps) and
the 8-tick cadence made him slow with long waits (12 ticks between
steps at a turn). The fix (walk-unused-frames): Y-shift hook off at
both draw sites (`$023202`, `$023480` → `lea.l $197B0,a0`) and loop
driver steps on every `sys_event_run` call (one cell per 4 ticks).

### Open decisions (Dayset's call, not part of any ROM above)

1. **Restoring original walk speed** (pacing change — the walk is
   1 cell per 4 ticks, ~half speed; "barely navigable" at ~36
   frames/cell vs ~22 original).
2. **Slowing the cutscene** (tick-rate change — it runs ~1.6× faster
   on the flat render, because `sys_event_run` fires ~1.6× more
   often in real time).
3. **The big rework** (decode-once-and-reuse / scroll-and-patch +
   sprites, starting with the stable-tiles investigation, now scoped
   as chunked world loading — see GitHub issues). The only thing
   that fully smooths the world shift at the commit (integer-cell
   camera jumping a whole cell) and the cutscene record+10 lag.
   Dayset (2026-11-12 ~21:53 EST): "we are going to address that,
   right? big fix but worth it". Confirmed: yes.
