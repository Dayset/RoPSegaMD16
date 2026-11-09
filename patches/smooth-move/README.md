# Smooth-motion patch — Rings of Power (Mega Drive)

Pixel-precision camera for the overworld: when the camera steps one tile,
the scroll registers step 1 px/frame instead of the whole 16-px (2-tile)
snap at once. Game logic stays tile-based (`$1C21A`, `$32C56` untouched).

## The problem (player-visible)

The Master Talamus cutscene is the reference: its character movement is
smooth (sprites move in pixels) but the whole background scene shifts
abruptly in 16-px snaps (2 tiles per step). The overworld does the same —
every step, the entire visible map jumps 16 px at once.

## Cause (verified by live tracing, see `issues/037-*.md` and
`.scratch037/cutscene-findings.md`)

All addresses are 68000 ROM offsets (= file offsets). RAM variables are
`$FFxxxx`.

### The cutscene scrolls smoothly; the overworld does not

- The cutscene's soft in-between animation is the `$171D6` per-line
  H-scroll table (VRAM `$4000`), rewritten every VBlank: in the `$15C08`
  picture loop the counter steps 4 px/frame (1316 px over 5.5 s); in the
  `$15012` story loop the tile counter steps 8/frame and the scroll counter
  4/frame, with two parallax planes (four bands, scaled ×7/8, ×3/4, ×11/16,
  ×19/32). Sprites are pixel-positioned via `$1119E`.
- The cutscene's abrupt whole-screen shift is the `$15C08` loop exit at
  counter 1000 → a 14-frame gap with **no** `$171D6` calls → the next
  picture is drawn wholesale (blitter `$1194A` + layout change `$12C20`).
- The overworld has **no** per-frame scroll at all: `$DC16` (the scroll
  writer) is called only at layout install (twice in a 4000-frame run, both
  `(0,0,0,0)`), and `$1B918` re-uploads the whole visible map
  (`$DA04($FF1EC0, $FF8674<<5, $33C0 words = 26,496 bytes)`) on every tile
  step. Scroll registers are only set at layout install (`$11E06`/`$12C20`).
  So the background jumps 16 px per step while sprites are pixel-positioned.

### The choke point: `$1B918` and `$FF0098`

- `$FF0098` is set **only** by `$1BA16` (light, `0x1BA1A`: `move.w #$FFFF,
  $FF0098`) and `$1BA26` (heavy, `0x1BA2A`: also sets `$FFB08A`/`$FF009A`/
  `$FF009C`), and cleared by `$1B918` (`0x1B9CA`) after the DMA. `$1BA16`
  is called from the `$1C21A` movement tail (`0x1C7F0`) and from the
  entity-update loop (`0x231CA`); `$1BA26` from `0xD2B2`, `0x12F3E`,
  `0x163E4` (map changes / teleports).
- `$1B918` (called 2× per `$D28E` iteration) gates everything on
  `$FF0098`: if set, it runs `$11DE8` + `$1BA4E(camY,camX)` (map rebuild)
  and the `$33C0`-word DMA; if clear (and the other flags are clear) it
  returns early. Clearing `$FF0098` at `$1B918` entry suppresses the
  rebuild + DMA for that frame.
- `$DC16(a,b,c,d)` writes VSRAM words 0–1 = (a,b) = plane A/B vertical
  scroll, and VRAM `$2000` words 0–1 = (c,d) = plane A/B horizontal
  scroll (layout G, R11=`$00`, full-screen). Values are **negated** (the
  map viewer passes `-$6,-$6,-$4,-$4`).

## The patch

One 6-byte hook + one trampoline in the unused `0xFF` padding at the end
of the ROM (`0xFD0CC–0xFFFFF`, 12,084 bytes; outside the runtime
checksum's summed range). No game code is moved.

### Hook — `$1B918` entry

At `0x1B918`, replace `link a6,#-2 ; tst.w $FF009C` (first 2 bytes)
(`4E 56 FF FE 4A 79`) with `jsr $FD0CC.l` (`4E B9 00 0F D0 CC`).

Trampoline at `0xFD0CC` (896 bytes, `smooth037.s`): the hook discards its
own `jsr` return (`addq.w #4,sp`), runs the per-frame logic
(`patch_step`), re-executes the displaced prologue (`link a6,#-2`;
`move.w $FF009C,d0; tst.w d0` — flags identical to the original `tst.w`),
and jumps to `0x1B922` (the instruction after the displaced `tst.w`).
The `$1B918` body's own `rts` returns to `$1B918`'s caller, so the stack
is exactly as the original left it (a `jsr` hook must never exit with a
plain `jmp` that leaks its return address — proven in #021). `$1B918`
is called 2× per `$D28E` iteration (twice per game frame), so
`patch_step` is gated on the VBlank frame counter (`$FF0012`) and
advances the interpolation at most once per frame; the second call in a
frame only re-clears `$FF0098` if an interp is active.

### Per-frame logic (`patch_step`)

State in dead RAM `$FF00A0–$FF00BC` (0 refs in `rop.s`, no `lea` into the
block; `$FF00A4` is **not** used — 1 ref, a `tst` at `0x1CF3C` — and
`$FF00B6`/`$FF00B8`/`$FF00BA`/`$FF00BE` are game variables and are **not**
used). Layout: `$FF00A0` magic `0x5A37`, `$FF00A2` active (0/1),
`$FF00A6` dirX (−1/0/+1), `$FF00A8` dirY, `$FF00AA` step (0–total),
`$FF00B0` prevCamX, `$FF00B2` prevCamY, `$FF00B4` total (px),
`$FF00BC` lastFrame. Every state word is range-validated
on each call; anything out of range re-initialises to safe defaults
(active=0, no DMA suppression), so a stray game write fails safe to
original behaviour.

- **No interp active:** read the camera (`$FF0E8E`/`$FF0E90`), compare to
  prevCam. If the delta is a single-axis step of 1–4 tiles (the camera
  moves ±2 tiles per step while walking, so a step is 8–32 px) **and**
  the heavy flags (`$FFB08A`/`$FF009A`/`$FF009C`) are all 0 (a light
  `$1BA16` step, not a `$1BA26` redraw), start an interpolation:
  active=1, step=1, total=`8·|delta|`, clear `$FF0098` (suppress this
  frame's DMA), and call `$DC16(0,0,−dirX·1,−dirX·1)` for an X step or
  `$DC16(−dirY·1,−dirY·1,0,0)` for a Y step — 1 px of scroll.
- **Interp active:** step += 1 each frame (frame-gated). While
  step < total, call `$DC16` with the pixel offset (−dir·step) and keep
  `$FF0098` clear (DMA stays suppressed). At step == total (the tile
  boundary), finish: active=0, set `$FF0098 = $FFFF` so the DMA runs in
  this `$1B918` call, call `$DC16(0,0,0,0)` (scroll back to 0), and sync
  prevCam to the new tile.
- **Anything else** (teleport, >4-tile jump, diagonal, heavy redraw, no
  change): reset the scroll to 0, sync prevCam, leave `$FF0098` alone —
  the DMA runs immediately, exactly as in the original.

`$1BA4E`/`$11DE8` rebuilds are idempotent, so delaying the DMA by up to 15
frames is safe (7 for a 1-tile step, 15 for a 2-tile step); the only cost is
a ≤15-frame delay in NPC/map updates,
which is imperceptible. The patch adds a few dozen instructions per
`$1B918` call (once per frame in the overworld) — no measurable cost.

### Why the scroll sign is what it is

For a +X step (camera moves east), the view must move east, so the plane
shifts west: H-scroll = −dirX·step (negative, matching the map viewer's
negation convention). Same for Y: V-scroll = −dirY·step. If a live check
ever shows the image shifting the wrong way, flip the `neg.w` in
`patch_step`.

### v1 limitation (known artifact)

During the interpolation the leading edge strip shows **stale tiles**
(the name table still holds the old window; only the scroll register
has moved). For a 2-tile camera step the interp runs 15 frames, so the
stale strip is visible for up to 15 frames. It is fixed when the DMA
runs at the boundary. A v2 preload (DMA just the new strip via `$DA04`
during the interp, using the `$19692` 4-slot cache / `$1C802` lazy
getter) would remove it. Preload the facing direction: the name tables
are already 128×32 cells (R16=`$03`) vs 40 visible, so the strip can be
streamed in the facing direction — and the neighbouring map chunk, via
the `$19692` cache — during VBlank before it scrolls into view. Facing
is known before movement starts, so the preload can begin a few frames
early. Vertical headroom is only 4 rows, so horizontal is the easy win.

### Multilevel terrain without lag (design note)

The 68000 draws nothing, the VDP scans planes in hardware, and scrolling
is a register write — the cost is per changed cell. The fix is high ground
on one scroll plane, low ground on the other, window/sprites for raised
features, and strip updates only — never full layer-by-layer redraws.
(This patch does not implement multilevel terrain; it removes the snap so
a two-plane layout can scroll without the 16-px jump.)

### Checksums

The patch changes bytes inside the runtime checksum's summed range
(`0x000000–0xFD07B` — the `$1B918` hook site), so both checksums were
re-fixed with `tools/checksum.py fix-all`:

- Header checksum at `0x18E`: `0x8B9F` → `0x8FA9`
- Runtime checksum immediate at `0xFD098`: `0x8F33608C` → `0x15E8609D`

The trampoline itself sits at `0xFD0CC+`, outside the runtime sum range,
so it does not affect the runtime value.

## Files

- `rings-of-power-smooth-move.ips` — IPS patch (1294 bytes, 95 records).
  Apply to a clean copy of the original ROM (`Rings of Power (USA,
  Europe).gen`, MD5 `30c18fdbe2183f64702ae9f1a45d63f9`) with any IPS
  patcher (e.g. Lunar IPS, Floating IPS). It produces the patched ROM; no
  full ROM is shipped here. Round-trip verified: applying the IPS to the
  original reproduces the patched ROM byte-for-byte.
- `rop-smooth.gen` — the patched ROM itself (git-ignored, for Dayset to
  run directly). MD5 `3676f49a4a2dfcf7ff70a323a5bef298`.
- `smooth037.s` — the patch source (m68k assembly, GNU as).
- `build.py` — rebuilds the patch, the IPS, and the ROM from the original.
- `changed-bytes.txt` — the full list of changed bytes with addresses
  (original → patched), for review without applying the IPS.

## How to use

1. Apply `rings-of-power-smooth-move.ips` to a copy of the original ROM
   (or run `rop-smooth.gen` directly).
2. Play through the intro into the overworld and walk. The camera now
   glides 1 px/frame between tiles instead of snapping 16 px at once.
3. The patched ROM is otherwise identical to the original.

## What was tested (verified)

- **Checksums:** `tools/checksum.py verify-all` on the patched ROM:
  header `0x8FA9` OK, runtime `0x15E8609D` OK.
- **Boot (BlastEm 0.6.3.4 headless, Xvfb + dummy audio):** the patched
  ROM boots, passes its own runtime checksum, reaches the overworld loop
  (camera moves, `$1BA16` fires), and keeps running (no hang at `0xFD0CA`,
  the checksum-fail address). The traceP run (STOP=5000) completed
  SUCCESS on attempt 1, lastFrame 5005, camera (285,122).
- **Scroll stepping (BlastEm debugger, patch + trace harness,
  `.scratch037/traceP_out.txt`, STOP=5000):** the `$DC16` calls the patch
  makes were logged with arguments while walking right in the overworld
  (camera X 134→285, Y constant 122). The unpatched ROM makes 2 `$DC16`
  calls in the whole run (both `(0,0,0,0)` at layout install); the
  patched ROM makes 179. The H-scroll (args 3,4) takes exactly the
  values `{-15,…,-1,0}` — four complete interp cycles fully inside the
  ring window each read `-1,-2,…,-15` then `0` (e.g. ending frames 4766,
  4835, 4921), i.e. 1 px per call over a 16-px (+2-tile) camera step,
  resetting to 0 at the tile boundary. The V-scroll (args 1,2) is
  `(0,0)` in every logged call — the correct axis for east/west
  movement, and no 16-px snap anywhere. The camera moves +2 tiles per
  step (~every 20 frames); the patch interpolates the full 16 px.
- **No frame drops:** the patched STOP=5000 run completed in ~115 s
  (~43 fps emulated) vs the unpatched STOP=6500 run at the same rate
  (~43 fps); the patch adds a few dozen instructions per `$1B918` call
  (once per game frame). No measurable slowdown.
- **IPS round-trip:** applying the IPS to the original reproduces the
  patched ROM byte-for-byte. The original ROM is untouched
  (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## What was NOT proven

- **A visible overworld screenshot of the smooth scroll.** Headless
  BlastEm runs show a black screen when the debugger pauses at the spin
  breakpoint in the overworld (both the original and the patched ROM —
  the original shows the overworld fine when running unpaused, e.g.
  `/tmp/shot3.png`). The scroll stepping is verified from the `$DC16`
  argument log, not from a screenshot. A visual check on real hardware
  or a normal emulator session is still owed.
- **The scroll sign** (image shifting the correct direction) was derived
  from the map viewer's negation convention, not confirmed visually.
  If the image shifts the wrong way on a live check, flip the `neg.w`
  in `patch_step`.
- **The 15-frame stale edge strip** (v1 artifact above) was not
  screenshotted; it is a direct consequence of delaying the DMA and is
  fixed at the tile boundary.
- **Multilevel terrain** is a design note only; no two-plane layout was
  built or tested.
- **Real hardware was not tested.** BlastEm only.
