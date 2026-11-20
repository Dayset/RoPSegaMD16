# Big-rework PoC fix2 — REPORT

Date: 2026-11-13. Worktree: `~/workspace/rop-work/big-rework-poc-fix2/`
(base: main `416d623`, PR #233). Base PoC ROM MD5
`64b742edf92cf8b3b2227b8654d550e9`. Fixed ROM MD5
`d4fc661f333ca2425987d2407693bce9`.

## Dayset's verdict (2026-11-13 ~08:56 EST, PoC playtest)

> "academy room is just first screen and nothing on it, small chunk is
> stuck in the left corner, but it moves smooth on the screen logic
> works dialogues, only i can't see any actors, motions are equal to
> original room no smooth jerky slow"

Plus: "outer decoration paper is gone for some reason (i don't mind)".

Screenshot: `~/workspace/user/media_library/image/image-34.png`
(634x472). What it shows: the Academy room as a textured diamond
(red ground, blue water, green trees, grey stone walls/pillars) on a
BLACK background (top, bottom, right); only ONE figure visible, Buc
(green hood/robe, on the right side of the blue water); NO Thalmus,
NO students; a small brown paper/frame with a building image in the
bottom-right corner; a Genesis controller overlay top-right
(emulator overlay, ignore it).

## Diagnosis

### (a) The room image: same size as the original, not a static install bug

Measured the diamond from terrain colours only (red ground / blue
water / green trees / grey stone), excluding the controller overlay
(top-right) and the paper frame (bottom-right):

| shot | diamond (game px) | frac of 320x224 | aspect |
|---|---|---|---|
| Dayset image-34 | 283 x 169 | 0.88 x 0.75 | 1.67 |
| my PoC run (poc3) | 278 x 160 | 0.87 x 0.71 | 1.74 |
| my original run (orig3) | same as poc3 (rows match) | — | — |

The diamond in Dayset's shot is the SAME size as in my PoC run and
in the original (within a few px of measurement noise; the 10x10
window's isometric diamond is ~252x144 px by construction, aspect
1.75). There is NO static install bug making the image small — in my
controlled run (same slot_0 state, 3 s, no input) the PoC room fills
the viewport identically to the original.

So why does it LOOK small and "stuck in the left corner" to Dayset?
Two reasons, both confirmed:

1. **The background is black, not pink.** The install blanks the
   window room rect (rows 0-22, cols 2-37) with tile `$7FF` and blanks
   the whole Plane B table, erasing the pink decoration and the HUD
   (GOLD/TIME/compass) that normally fill the screen around the
   diamond. In the original the pink makes the screen feel full; in
   the PoC the same-size diamond floats on black, so it reads as
   small and isolated. Orig-vs-PoC pixel diff: 225,377/480,000 px
   differ (47%), almost all background/HUD/paper; the centre room
   differs in only 20,578/150,000 px (14% — water-shimmer phase +
   wandering students, see below). The black background is an
   ACCEPTED side effect (Dayset doesn't mind); this fix does NOT
   restore the decoration.
2. **The image is frozen and goes stale as he walks.** The PoC's
   gate (`.rgate` in `redraw_entry`) clears `$FF0098` on EVERY
   `redraw_check` after install, so the room NEVER re-decodes. The
   D-pad scroll is clamped to +/-1 cell (14 px / 8 px). Once Buc
   walks more than 1 cell from the install camera, the frozen image
   can't follow — it stays "stuck" where it was, showing the wrong
   cells, while the logic (Buc, camera) has moved on. That is the
   "small chunk stuck in the left corner": the image doesn't follow
   the camera.

A third, subtler point: **the install can fire late.** It fires on
the first `redraw_check` with `$FF0098` set, which need not be the
load camera — if Dayset walked before the first such call, the
install fires at a walked-to camera. His shot shows the big blue
pool, NOT the (7,7) stone-walls/chests view my controlled run shows.
So the frozen view in his run is a different part of the room than
the load view. (In my run the install fires at camera (7,7) on the
first frame.)

### (b) The actors: only Buc is visible — normal at this camera, made permanent by the freeze

At the save state's camera (7,7), the 10x10 window covers x 2-11,
y 2-11. Positions at 3 s (same in both runs):

| figure | position | in window? |
|---|---|---|
| Buc | (8,7) | yes — visible |
| Thalmus | (9,17) | no (10 cells south) |
| student | (20,13) | no |
| student | (19,12) | no |

The ORIGINAL at the same state/camera also shows only Buc (verified
in orig3). So "no Thalmus/students" is NOT a PoC bug at this camera
— it's the camera position. BUT the PoC made it permanent: the image
is frozen, so even when the camera moves (walking, cutscene, NPC
wander), the figures are never re-baked and never come into view.
The students do wander logically (their char X/Y change between the
orig and PoC runs — RNG divergence, not a bug), but their drawn
positions never update in the PoC.

The fix makes the figures re-bake on camera moves (see below), so
Thalmus and the students come into view as Dayset walks the camera
toward them.

### (c) The motions: figure frozen by design; scroll + logic are smooth

Confirmed: the figures are baked into the Plane B image by
`map_chunk_pos` at install time and frozen (the gate suppresses every
re-decode). The D-pad walks Buc logically (char X/Y + camera move)
and the VBlank hook slides the whole image smoothly (1 px/frame,
clamped to +/-1 cell) — that is the smooth motion Dayset reports
("it moves smooth on the screen logic works"). But the figure ON the
screen is frozen in the image: it does not walk, turn, or animate.
So Dayset's "motions are equal to original room no smooth jerky
slow" is exactly right — the motion he sees is the whole-screen
slide + the logical walk, not figure animation. The fix does NOT add
sprites or figure animation (out of scope); it makes the baked
figures update whenever the camera re-installs, so the figure
position tracks the logic instead of staying at the install pose.

### Side notes

- **Paper frame:** present WITH the building image in Dayset's shot,
  blank (pink, no building) in my poc3. Timing difference: the panel
  routines repaint at scene entry; in his run a re-setup repainted
  the paper after the install blanked it, in mine it didn't. Minor;
  not pursued (Dayset doesn't mind the paper being gone).
- **Water shimmer / students:** the 14% centre-room orig-vs-PoC
  pixel diff is the water shimmer phase (frozen in the PoC, animating
  in the original) plus the students wandering to different cells
  (RNG divergence). Not bugs.
- **HUD (GOLD/TIME/compass) and pink background:** erased by the
  install's blanking, as in (a). Accepted side effect.

## The fix (one change only)

**Camera-aware re-decode gate** in `redraw_entry` (`source.s`,
`patches/big-rework-poc-fix2/`). The transition now records the
install camera in `$FF00BC` (X) / `$FF00C0` (Y) — dead RAM, 0 refs in
`disasm/src/rop.s` (verified; `$FF00A4` was NOT used because the game
tests it at `$1CF3C`; `$FF00AC`/`$FF00AE` are live menu fields).
`$FFFF` = "none yet" (forces a re-install). The gate, which runs on
every `redraw_check` (main_loop calls it every iteration), now:

- **Camera unmoved** (`dx==0` and `dy==0`): suppress as before —
  `clr.w $FF0098`. Decode-once holds; no per-tick re-decode.
- **Camera exactly 1 cell away AND the scroll has caught up**
  (accumulators equal the expected values for the move,
  `hExp = -(dx-dy)*224`, `vExp = (dx+dy)*128`, clamped to the
  +/-1-cell range): seamless re-install. The new image at scroll 0
  is exactly the old image at the scroll extreme, so there is no
  jump. Updates the install camera, resets the scroll to (0,0)
  (VDP via `$DC16` + state), and does NOT clear `$FF0098` so the
  body runs its decode+DMA for the new camera. If the scroll hasn't
  caught up yet, suppress and wait — the gate re-checks next frame.
- **Camera >1 cell away** on either axis (teleport / fast move /
  scroll lagged): re-install now, with a 1-cell jump. Strip
  streaming (the full rework) will close that gap; the jump is still
  half as often as the original's per-cell jump.

Why letting the body run updates Plane B: the body's re-decode runs
`map_chunk_pos` (re-decodes for the new camera, re-baking the figures
at their current positions) + the DMA (re-uploads the patterns to
VRAM `$71C0`), and the room draws at `$12E68`/`$16326` are redirected
to Plane B `$4000` by the static patches, so the Plane B name table
is refreshed. The name table itself is sequential indices, so the new
patterns at the same indices show the new camera's view. `installed`
stays 1, so the transition (Plane B blank + window blank) does NOT
re-run — the window keeps its dialogue text and the Plane B table is
not erased.

**Scroll reset:** the re-install writes (0,0) to `$DC16` immediately
in the gate (same call sequence as the VBlank hook) and clears
`hAcc`/`vAcc`/`lastH`/`lastV`, so the fresh decode shows unshifted
and the VBlank hook then keeps it 0 until the D-pad builds it again
for the next cell.

**Untouched:** D-pad scroll, game logic, collision, dialogues,
panels, menus (none depend on `$FF0098`). No strip streaming, no
sprites, no tick governor, no decoration restore.

**Camera X/Y confirmed:** `$FF0E8E` = X, `$FF0E90` = Y
(`leader_spawn` `$01C21A` writes X from the grid width and Y from
the grid height; the scroll signs agree: east `dx=+1` gives
`hAcc=-224, vAcc=+128`, matching the VBlank hook's Right deltas).

**Known limitations of this fix:**
- A >1-cell move re-installs with a 1-cell jump.
- A diagonal 1-cell move also jumps partially: the scroll clamp
  covers only half a diagonal (e.g. southeast needs `vScroll +16`
  but clamps at `+8`), so the re-install jumps up to 1 cell on the
  clamped axis. Cardinals (the common case) are seamless.
- The black background / missing pink decoration + HUD remains
  (accepted side effect).
- The re-install path is verified by disassembly only (see below);
  the live behaviour is Dayset's playtest.

## Build

`python3 patches/big-rework-poc-fix2/build.py` (adapted from the PoC
builder; same `$FD900` blob base, same three hook sites + three
static sites, asserting the original bytes first).

- Blob: **1318 bytes** at `$FD900` (was 980; +338 for the gate logic
  + camera tracking). Entries: vbl `+0x0`, redraw `+0x254`,
  scene `+0x4EC`.
- Checksums verify: header stored `0x9818` computed `0x9818` OK;
  runtime stored `0x34B283AE` computed `0x34B283AE` OK.
- Hooks + statics verified in place (`$1272` jmp `$FD900`,
  `$1B918` jsr `$FDB54`, `$12C20` jsr `$FDDEC`, R4 `$8402`, both
  `pea $004000`).
- IPS: `rings-of-power-big-rework-poc-fix2.ips`, **1928 bytes,
  145 records**; round-trip verified (base + IPS == ROM exactly).
- Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`
  re-verified after the build).
- Fixed ROM: `rop-big-rework-poc-fix2.rom`, 1,048,576 bytes, MD5
  **`d4fc661f333ca2425987d2407693bce9`**.

## Build checks done (no playtest verification — Dayset is the tester)

1. **Disassembly verification of the new gate.** The assembled blob
   was disassembled (`m68k-linux-gnu-objdump`) and the gate read
   instruction by instruction: suppress path (`clr.w $FF0098`),
   seamless re-install path (camera compare, `|dx|`/`|dy|`,
   expected-accumulator compare, install-camera update, scroll
   reset, `$DC16` call with balanced stack), >1-cell path,
   `.rdone` prologue re-execution (`link a6,#-2; tst.w $FF0098`
   ... `tst.w $FF009C; jmp $1B922`), and `scene_entry` camera reset.
   Branch targets, `cmp` operand order, `bgt`/`bne` conditions, and
   stack balance all check out.
2. **Smoke check (BlastEm + slot_0, 180 frames).** Installs
   correctly: magic `$9C07`, armed `1`, installed `1`, install
   camera `(7,7)` (the load camera), loc `156`, mode `2`,
   tilebase `$38E`. No crash. `fix2_check.py` / `fix2_state.json`.
3. **Base rendering unchanged.** The fix2 screenshot at the same
   state/frames is pixel-identical to the PoC screenshot
   (`fix2_shot.png` vs `poc3_shot.png`: **0/480,000 px differ**) —
   when the camera doesn't move, the fix changes nothing.
4. **NOT verified live: the re-install path.** A live camera-move
   probe was blocked because this BlastEm debugger build has no
   memory-write command (`se` is register-only; `set` is
   unrecognised; the `?` help lists only `se REG|ADDRESS` which
   rejects addresses with "Invalid destinatino"). So the re-install
   firing on a real camera move is verified by disassembly only.
   The live behaviour — room following the camera, actors appearing,
   scroll staying smooth — is Dayset's playtest.

## Deliverables

- Fixed ROM (for Dayset): `rop-big-rework-poc-fix2.rom`
  (MD5 `d4fc661f333ca2425987d2407693bce9`)
- Patch: `patches/big-rework-poc-fix2/` (`source.s`, `build.py`,
  `rings-of-power-big-rework-poc-fix2.ips`, `changed-bytes.txt`,
  `README.md`)
- This report: `.scratch-big-rework-poc-fix2/REPORT.md`
- Diagnosis artefacts: `run_compare.py`, `fix2_check.py`,
  `poc3_shot.png`, `orig3_shot.png`, `fix2_shot.png`,
  `fix2_state.json` (worktree root)

Nothing landed on main. The original ROM was never modified.

## What Dayset should test (playtest)

1. Walk Buc around the Academy, especially south/east toward
   Thalmus (9,17) and the students — do the room image and the
   actors follow the camera now, and do Thalmus/students come into
   view?
2. Is the scroll still smooth while walking, and is there a visible
   jump when moving fast / diagonally (the known 1-cell jump)?
3. Do dialogues still work (talk to Thalmus / trigger the cutscene
   text) and does the D-pad logic still work?
4. Does the room still fill the viewport the way the original does
   (same diamond size), and is the black background acceptable?

## Open / queued (not this task)

- Full big rework: strip streaming (Scheme A) + `sim_span2.py`
  figures-as-sprites measurement — scoped, not built.
- Tick governor + 16-tick NPC/script gate — Dayset's call, not built.
- 9 hunt corrections + 2 water-plane corrections in `docs/maps.md`
  (promised 2026-11-12, still not landed).
