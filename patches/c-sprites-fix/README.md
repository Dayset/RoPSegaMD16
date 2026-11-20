# Phase C: figures as sprites with per-frame interpolation

Base: `rop-big-rework-full-b2.rom` (MD5 `ec7bcffe9c45fd851a6752dec5bcf788`).
Output: `rop-big-rework-full-c-fix.rom` (MD5 `535288396024b3892d89d74b980436ac`,
header checksum $B752, runtime $54512C6C — both verified by
`tools/checksum.py verify-all`)
+ `rings-of-power-big-rework-full-c-fix.ips` (base → C-fix, round-trip verified)
+ `changed-bytes.txt`.

Fixes vs the broken C (`385fa655…`): (1) `addq.w #4,sp` at the start of
`.sh_run`/`.sp_run` (discard the hook jsr's return — the D-crash bug);
(2) install camera moved off $FF00BC/$FF00C0 (merchant-attitude table)
to $FFD320/$FFD322; (3) redraw_entry restores the saved registers
BEFORE calling the body (B2's order — the second bug, found by
bisection when the v1 fix still froze). See
`.scratch-big-rework-full/d-crash-fix/REPORT.md` (§§1–3, §2b).

Full design, ground facts, sim measurements and test notes:
`.scratch-big-rework-full/c-sprites/REPORT.md` (§§1–5).

## What it does

- The install draws **terrain only**: `hero_track` ($0231D8) and
  `map_promote_record` ($02343A) are hooked; during the body's
  terrain decode (in `redraw_entry`, when installed) they return
  immediately, so no figure is ever baked into the Plane B image.
  Kinds 2/3 (static/animated scenery) are not hooked and stay baked.
- After the body returns (the DMA upload has finished, so the
  decode buffer $FF1EC0 is free), `redraw_entry` decodes up to
  K=3 figures — the leader at window (5,5) always, plus 2
  round-robin — by calling the game's own figure routines into
  $FF1EC0, scanning the bbox, and repack-copying the tiles into
  the VRAM pattern cache with a sub-tile alignment shift, so every
  figure occupies at most 4×4 aligned tiles (20 with the feet row).
- Every VBlank, the sprite updater steps each figure's CUR toward
  its TARGET (clamped ±32/16 px horizontal, ±18/16 vertical per
  frame), computes the screen position from CUR + installCam +
  scroll, and writes the 12 figure sprites (8 bodies + 3 feet)
  plus the chain through sprite 22. Figures hide when off-screen,
  when the menu ($FF00AC) or dialog ($FF0114) is open, or when
  their pattern is empty. No teleport ever: CUR only moves by the
  clamp.

B2's camera-driven scroll + Scheme B re-install gate are unchanged
(only re-assembled). `scene_entry` / `mapclose_entry` are B2's code
and are verified byte-identical by instruction stream
(`check_entries.py`, capstone). `redraw_entry` now wraps the body
(`jsr $1B922`, the body returns to the blob) instead of jumping to
it, so the figure decode can run after the DMA.

## Blob

One contiguous blob at $FD400, 4806 bytes ($FD400–$FE6C5):
the 0xFF padding $FD400–$FD8FF, B2's old blob region
$FD900–$FDE30 (replaced), and the padding $FDE30–$FE6C6. The
original ROM is 0xFF from $FDE30 to the end of the 1 MB ROM, so
the blob extends past $FE000; `build.py` asserts the padding
before overwriting. Entries (from the listing, never hardcoded):
vbl +0x0, redraw +0x642, scene +0x1256, mapclose +0x1290,
skip_hero +0x1210, skip_promote +0x1232.

Hooks (old bytes asserted first):
- $1272 `jmp $FD900.l ; nop` → `jmp $FD400.l ; nop`
- $1B918 `jsr $FDB54.l` → `jsr $FDA42.l`
- $12C20 `jsr $FDDC0.l` → `jsr $FE656.l`
- $16302 `jsr $FDDFA.l` → `jsr $FE690.l`
- $0231D8 `link a6,#0 ; move.l a3,-(sp)` → `jsr $FE610.l`
- $02343A `link a6,#0 ; movem.l d4-d5/a3,-(sp)` → `jsr $FE632.l ; nop`

Sprite state lives in $FFD000–$FFD2FF (B2's $FF00A0–$FF00C0
unchanged). Pattern cache: feet quads $6E4–$6EF (3×4 tiles),
body slot 0 $6F0–$6FF, body slots 1–8 $780+(i−1)×16 — 156 tiles
total, exactly the reserved regions.

## Build

`python3 patches/c-sprites/build.py` — assembles with vasm,
asserts the base MD5, the B2 blob bytes and the 0xFF padding,
verifies the unchanged entries against the B2 blob, patches the
6 hooks, asserts the statics/allocator are unchanged from B2,
fixes checksums, emits the IPS + round-trip verification +
`changed-bytes.txt`, and re-verifies the original and base ROMs
are untouched.

## Known limitations

- Trailing lag (phase D's job): TARGET updates only on
  body-decode ticks (~every 16 fr while walking); the sprite
  trails Buc by up to ~2 cells mid-walk and catches up at
  pauses. It never teleports.
- Feet pool: 3 quads for 9 slots — a 4th simultaneous 5-row
  (combat-extra) figure shows 4 rows until its next decode.
- A figure not decoded this tick keeps its old pattern, anchor
  and TARGET; its sprite still interpolates.

Nothing is landed on main. Dayset is the tester.
