# C report — figures as sprites with per-frame interpolation

Worktree: `~/workspace/rop-work/big-rework-full/` (main tip `416d623`).
Base: `rop-big-rework-full-b2.rom` (MD5 `ec7bcffe9c45fd851a6752dec5bcf788`, asserted).
Deliverable: `rop-big-rework-full-c.rom`.
Patch: `patches/c-sprites/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `.ips`, round-trip verified).
Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).
Dayset is the tester — no live probes, no screenshots, no cadence measurements.
One phase only: sprites. No governor, no chunk loading.

## 0. Docs read (in order, per brief)

- `BLOB_MAP.md` — B1 + B2 findings, fluidity proposals (accepted by Dayset).
- `DESIGN.md` §6 (figures as sprites) — budget 12 figures, pattern cache
  156 tiles, LRU eviction, VBlank position recompute.
- `.scratch-big-rework-full/measurements/REPORT.md` — R4 GO (separability:
  every `$E358` write is a per-nibble select; overlay test 0 differing
  bytes; occlusion 0% at realistic args), R5 GO (1 sprite / 16 tiles per
  walk figure, 19–24 x 28–30 px; only the combat-extra call needs
  2 sprites / 20 tiles).
- `.scratch-big-rework-full/b2-strip/REPORT.md` — B2 blob 1328 bytes at
  `$FD900`, camera-driven scroll + Scheme B gate, free blob space
  `$FD400–$FD8FF` + `$FDE30+`, install camera `$FF00BC`/`$FF00C0`.

## 1. Ground facts from the disassembly + sim

### 1.1 Figure draws (map_chunk_pos $01BA4E, verified in rop.s)
- Per window cell, two byte maps give draw-record indices:
  `$FFB76C` (site 1, read first) and `$FFB36C` (site 2); `$FF` = none.
  Draw records at `$FFB0CC + i*12` (56 x 6 words):
  `[0]=base stream, [1]+[2]=template, [4]=flags (+$8), [5]=kind (+$A)`.
  Dispatch on kind: 0 `hero_track` $0231D8, 1 `map_promote_record`
  $02343A, 2 `map_tile_at_offset` $0232AC, 3 `map_animated_tile` $0232D2.
  Map index = ((x+offX) mod 32)*32 + ((y+offY) mod 32), where the
  offsets come from `map_scroll_offset` $020D58: (0,0) in rooms
  (grid+$C == 0), (6-camX, 6-camY) in the overworld (grid+$C != 0).
  Grid base pointer `$FFA7FC`; room grid `$FFB0BC` (+$A = phase 0-3,
  +$C = 0, +$8 = 1 per the live probe).
- Live Academy records (probe_live.json): 6 walking figures kind 1
  (rec0-5: bases 0x180/0x120/0x2B0, templates 6/7/29/6/4, rec[2]==4 on
  four of them) + 2 static kind-2 objects (rec6-7) + 48 dummy kind-0
  records (base 0x270F, never mapped). Kind 2/3 stay baked in the
  terrain (static/animated scenery); only kinds 0/1 become sprites.
- `map_terrain_tile_lookup` IS `$E358` (args: stream, d0, d1, d3;
  writes into FIXED buffer `$FF1EC0`). The figure routines call it
  directly, so a runtime decode that calls `hero_track` /
  `map_promote_record` reproduces the game's own frames exactly
  (including the `rec[2]==4` random template variant and the combat
  extra call). No reimplementation of the call sequence.
- Template group = `template*36 + grid+$A*8` into `$197B0`
  (walk phase 0-3). The extra calls (flags bits 0/1/2) use stream
  `0x222/0x224/0x22E + $FF0092` (shimmer 0/1) — NOT +phase as the
  measurements sim assumed (sim inaccuracy; runtime decode is exact
  by construction). Combat flag `$FF010E` bit 0 selects the
  0x200/0x201 extra call. Figure arg =
  `-(7*(height+bit7) + 4*bit8)` from the cell word + `$5EDC4` record.
- `redraw_check` body ends `unlk a6; rts` (all exits via $01B94C),
  so the redraw hook can WRAP it: `jsr $1B922` (body returns to the
  blob) -> figure-decode work -> `rts` to the main loop. The decode
  runs in the main loop (not VBlank), once per tick, budgeted.

### 1.2 Sprite table + chain (verified in rop.s)
- Writers: `sprite_write` $011BD8 (one sprite), `sprite_set_link`
  $011C4A (word 1 only), `sprite_grid_write` $011C9A (grid).
  `menu_format` $0138A8 runs EVERY redraw_check (every tick) and
  rewrites slot 0's link (-> 2, or -> 22 when `$FF0114 != 0`) plus
  links for 21, 25, 46 and the menu sprites 59-62 (-> 60,61,62,47)
  and 67 (-> 0, END). `world_sprites_setup` $013D84 writes the
  bottom bar as one long consecutive chain 2->3->...->30->31->...->46
  ->67 at scene setup; scene grids use slots 0-15.
- Chain during gameplay: 0 -> (2 or 22) -> ... -> 46 -> 67 -> END.
  Sprite 22's link is NEVER rewritten by menu_format (only 0, 21,
  25, 46 are) and is 23 at scene setup. **Insertion point: sprite
  22** — every VBlank rewrite its word 1 as (size 3,3, link = first
  figure slot); the last figure sprite links to 23. Reached in
  both slot-0 branches (0->2->...->22->figs, and 0->22->figs).
  Figure slots 68-79 (12: 9 bodies + 3 feet) — see F4 (§1.5):
  slot 71 IS used by the game, so the figure sprites are
  68,69,70,72-79 (11: 8 bodies + 3 feet); pattern slot 8 is a
  decode spare with no sprite.
- Palette: figure patterns index the same CRAM palette 0 as the
  terrain, so sprite word 2 palette bits = 0, priority bit = 0.
  (A low-priority sprite beats low-priority Plane B and the low
  window plane, so a figure can show through the dialog box / menu
  panel — handled by hiding figures that overlap the dialog/panel
  rects; see §2.5.)
- `$FFD000+` is free in this ROM line (no `FFD0xx` references in
  rop.s — verified by grep; the interp-fix4 RAM $FFD000-$FFD014 was
  a different ROM line). Sprite state lives at $FFD000-$FFD2FF.

### 1.3 Walk pace (subcell.md, verified)
- Buc commits 1 cell per TICK in rooms (grid+$8 == 1 ->
  $FF0094 == 0 always, no phase gate). Tick = main-loop iteration:
  ~3 fr with the camera still, ~19 fr on a camera move (re-decode),
  ~8 fr/cell average while walking. The original was 1 cell / ~22 fr.
  (B2 already walks ~2.7x fast — the tick governor is phase D's job.)
- Slide step must therefore track up to ~1 cell / 3 fr in bursts.
  Chosen: CUR in WORLD diamond-px (1/16 fixed point), clamp
  +-32/16 px/fr horizontal (2 px/fr), +-18/16 vertical (1.125 px/fr)
  — a cell in ~7 fr on both axes (ratio 18/32 ~ 8/14, as the B2
  scroll rates). Teleport snap when the target jumps > 1 cell
  between VBlanks. Screen = CUR (world) - installCam + scroll, so
  the figure stays glued to the terrain during camera slides and
  the re-install (installCam update + scroll reset) is invariant.

### 1.4 Sim measurements M1-M4 (corrected model; scripts in this dir)

The measurements sim conflated the walk phase with the extra phase.
The corrected model (from the disassembly): group phase g =
grid+$A (0-3) selects the walk-template group; extra phase e =
$FF0092 (0/1) selects the extra streams 0x222+e etc.; template =
rec[1]+rec[2] (rec[2]==4 also randomly uses rec[1]+0x20);
combat flag $FF010E bit 0 selects the 0x200/0x201 extra call.
All decodes at the reference cell (5,5) -> d0b=196, d1b=98.
Realistic set: live templates {4,6,7,29,32,34,35} + walk 36-55,
bases {0x120,0x180,0x1CC,0x2B0}, flags {0,7,0x4000}, cf {0,1},
e {0,1}, g 0-3, arg {0,-7,-14,-28,-49} (51,840 decodes).

- M1 tile span (UNALIGNED, single pass): only 2.9% of decodes are
  tile-aligned; 54% of live-template decodes need >= 5 rows, 16%
  need 5 cols. R5's "1 sprite / 16 tiles" (pixel extent 19-24 x
  28-30 px) MISSED the alignment effect: a 30 px-tall figure
  starting 4 px into a tile spans 5 tile rows. A single-pass
  decode into a 16-tile slot is WRONG for ~half the figures.
  -> The blob aligns the decode (see 2.3 repack copy): the aligned
  span is always <= 4 cols x 5 rows = 20 tiles, w <= 32 px always
  (0 cases wider), and the 5th row is almost entirely the
  combat-extra case (cf=1: 13,140 of 25,920 rows=5; cf=0: 700).
  Aligned spans: (3,4) 25,920; (4,5) 12,240; (4,4) 7,440;
  (3,5) 1,600; (4,2) 2,680; (4,3) 1,960.
  Slot = 20 tiles (body 16 + feet 4). Cache: 9 body slots x 16 =
  144 + 3 feet quads x 4 = 12 = 156 tiles, EXACTLY the reserved
  regions ($6E4-$6FF + $780-$7FF). Feet pool holds 3 figures' 5th
  rows; a 4th simultaneous combat figure shows 4 rows (feet cut)
  until its next decode re-allocates (LRU).
- M2 clear region (per decode, positioned by the figure's own
  (r,c,arg)): rows [8 + arg>>3 + (r+c-10) .. +8] (9 rows, clipped
  0-22), cols [15 + (5k)/3 - 2 .. +10] (11 cols, clipped 0-35),
  k = r-c. Measured bands: arg=0 -> rows 9-15; arg=-60 -> rows
  1-8; k=0 -> cols 15-21; k=-6 -> 5-10; k=+6 -> 26-31. The d1
  shift is exact (+8 d1 = +1 row = +1152 bytes); the d0 shift is
  ~+60/-41 bytes per 14 px (asymmetric), covered by the 11-col
  band with margin. Max ~3,168 bytes cleared per decode.
- M3 anchors (stored per slot from the decode scan, no table):
  ax in -76..-52, ay in -74..+6 (unaligned bbox; aligned anchor
  = bbox origin minus (d0b,d1b), see 2.4).
- M4 call counts per figure decode: 1 call 28,224; 2 calls
  12,096; 4 calls 4,032; 5 calls 4,032 (full sweep). Max 5
  $E358 calls (main + combat extra + 3 extras).

### 1.5 Static facts nailed (F1-F6)
- F1 leader: actor records at $FF02BA + i*$34 (NOT $FF02B4, which
  is ram_merchant_base; the probe read entities 6 bytes low — its
  "cells" are true record offsets +6/+8/+10/+12 = cur/prev cell
  pairs). ram_party_leader = $FF02B2. The camera cell
  ($FF0E8E/$FF0E90) is the leader's cell: render_window shows map
  cell (camx-5+r, camy-5+c) at window (r,c), so the leader is
  ALWAYS at window (5,5). Leader identification = the record
  mapped at window cell (5,5); no entity matching needed.
  (The leader's TARGET is the install camera cell itself.)
- F2 map_chunk_cache_read $01C176: args (x=$8(a6), y=$a(a6),
  ptr=$c(a6), pushed in that order after the pointer) — returns
  d0 = $FF0248, a pointer to the 1-word buffer holding the cell
  word. The ptr arg is not read by the routine (vestigial); the
  blob pushes a scratch pointer anyway, exactly as map_chunk_pos
  does. Cell word -> tile = & $1FF; height = >>13 & 7;
  rec5 = $5EDC4[tile*2]; arg = -(7*(height + rec5>>7&1) +
  4*(rec5>>8&1)).
- F3 $FF0114 = ram_world_field_0114: dialog/message active
  (gates msg-queue consumption at $00D6B0; menu_format rewrites
  slot 0's link to 22 when it is set). $FF00AC =
  ram_menu_field_00ac: menu-open flag (tested all over main_loop).
  Both are the hide conditions for figure sprites (2.5).
- F4 sprite slots 68-79 are FREE: sprite_write immediates max at
  71 (slots 60,61,62,67,71 used); sprite_set_link max 46; the
  computed-slot writer sprite_write_block runs only from slots
  6, 10, 14 (max ~19). No game code writes >= 72. (Slot 71 is
  the highest game slot; 68-79 minus 71 leaves 68,69,70,72-79 —
  wait: 71 IS in 68-79. Recheck: sprite_write immediates >= 60
  are {60,61,62,67,71} — slot 71 is used by the game (menu_format
  writes slot 0x47=71 at $018048/$018566). So figure slots are
  68,69,70,72-79 = 11 slots, NOT 68-79 (12). Layout change: 8
  body slots (68,69,70,72,73,74,75,76) + 3 feet slots
  (77,78,79)? That gives 8 bodies, not 9. The cache holds 9
  bodies (144 tiles) + 3 feet (12) = 156, but the SPRITE slots
  only allow 8 bodies + 3 feet = 11 sprites if slot 71 is taken.
  Resolution: 8 body sprites + 3 feet sprites = 11 figure
  sprites; the 9th body slot has NO sprite — it is a pattern-only
  slot (decoded but not drawn) used as the eviction spare... NO.
  Cleaner: 8 live figures max (leader + 7). The Academy has 6.
  The 9th cache slot is the spare for the round-robin (a figure
  being decoded into the spare while its old slot still shows).
  Hmm — simpler: keep 9 pattern slots, 8 body sprites; the 9th
  pattern slot is decoded into but its sprite is only assigned
  when a body sprite frees. This is over-engineering: the
  Academy has 6 figures; 8 body sprites is plenty. DECISION:
  8 body sprites (slots 68,69,70,72,73,74,75,76) + 3 feet
  sprites (77,78,79); 9 pattern slots (the 9th is the decode
  spare, unused by any sprite until a body sprite frees — in
  practice never needed with <= 8 figures). Cache layout:
  feet quads $6E4-$6EF (3x4), body slot 0 $6F0-$6FF, body slots
  1-8 $780+(i-1)*16.
- F5 $DC16: as B2 (scroll write; args a=0,b=vScroll,c=0,d=hScroll).
- F6 frame counter $FF0010 (long; probe confirms). Used for
  lastSeen timestamps (low word only).

### 1.6 Corrections to the pre-compaction notes
- Byte maps are indexed by MAP cell, not window cell — but the
  map index ((d4+1) mod 32)*32 + ((d5+1) mod 32) reduces to
  window-cell indexing with a +1 shift: byte at
  $FFB76C/$FFB36C + (r+1)*32 + (c+1). Site 1 ($FFB76C) read
  first; $FF = none.
- d0/d1 tables $FFAE7A/$FFAF42 are camera-independent:
  d0b = 196-14c+14r, d1b = 18+8(r+c) (verified against the probe
  tables). The blob computes them; it does not read the tables.
- The anchor is (bx-d0b, by-d1b) for the figure's OWN (d0b,d1b),
  not (tx0*8-196, ty0*8-98) (that is only the (5,5) special
  case). Sprite screen formulas (derived from the gate's
  seamlessness, not trusted blindly): spriteX_raw = 340 +
  (CURx>>4) - 14*(icx-icy) + ax + hScroll; spriteY_raw = 226 +
  (CURy>>4) - 8*(icx+icy) + ay - vScroll. (340 = 212+128,
  226 = 98+128: sprite X/Y are stored +128; menu sprites at
  screen 150-201 confirm the +128 encoding. Hide = Y raw 0.)
  Verified: the formulas reduce to screen = (16 + bx +
  hScroll, by - vScroll), i.e. the sprite sits exactly on its
  buffer pixels.
- $FF02B4 is ram_merchant_base, not the entity array (see F1).
- Sprite slot 71 IS used by the game (see F4) — figure sprites
  are 68,69,70,72-79 (11 sprites: 8 bodies + 3 feet).

## 2. Design (detail)

### 2.1 Blob placement and entries
- One contiguous blob at $FD400, <= 0xC00 bytes (to $FE000):
  $FD400-$FD8FF (0xFF padding, 1280 B) + $FD900-$FDE30 (B2's
  blob, replaced) + $FDE30-$FE000 (0xFF padding, 464 B).
  build.py asserts the B2 blob bytes in the base ROM and the
  0xFF padding around it before overwriting.
- Entries (offsets from the vasm listing, never hardcoded):
  vbl_entry (VBlank $1272, jmp hook), redraw_entry
  (redraw_check $1B918, jsr hook), scene_entry ($12C20, jsr),
  mapclose_entry ($16302, jsr), skip_hero ($0231D8, jsr),
  skip_promote ($02343A, jsr + nop). scene/mapclose are B2's
  code re-assembled and verified byte-identical by instruction
  stream (check_entries.py vs the B2 blob); redraw/vbl are new.
- State: B2's $FF00A0-$FF00C0 UNCHANGED (magic, armed,
  installed, hAcc/vAcc, lastH/lastV, lastLoc, installCam
  $FF00BC/$FF00C0). Sprite state $FFD000-$FFD2FF (see 2.2).
  Skip flag $FFD100 (word): 1 = skip figure draws during the
  body's terrain decode, 0 = run. Checked by the skip entries
  (which also require the sprite magic, else run).

### 2.2 Sprite state ($FFD000-$FFD2FF)
- $FFD000 magic $9C07 (sprite subsystem init), $FFD002
  round-robin cursor (word), $FFD004 suppressed-this-tick
  (word, set by the gate's suppress branch), $FFD100 skip flag.
- 9 pattern slots, 24 bytes each at $FFD010 + i*24:
  +0 recIdx ($FFFF = empty), +2 state (0 empty, 1 live),
  +4 CURx, +6 CURy, +8 TGTx, +10 TGTy (all 1/16 fixed),
  +12 ax, +14 ay, +16 cols, +18 rows, +20 feetQuad
  ($FFFF = none), +22 lastSeen (low word of $FF0010).
- Feet pool at $FFD0E8: 3 x (ownerSlot word, lru word).
  Sprite assignment: body sprite for pattern slot i (i<8)
  is slot 68,69,70,72,73,74,75,76 (i -> 68+i, skipping 71);
  pattern slot 8 has no sprite (decode spare).
  Feet sprites 77,78,79 map to feet quads 0,1,2.
- Pattern cache (VRAM tile indices): feet quads $6E4+q*4;
  body slot 0 $6F0-$6FF; body slots 1-8 $780+(i-1)*16.
  VRAM byte address of tile t = t*32.

### 2.3 Figure decode (redraw_entry, after the body returns)
- Runs only when installed AND the body decoded this tick:
  snapshot $FF0098 at entry; run iff snapshot==1 AND
  suppressed==0. (The gate's suppress path sets suppressed;
  the reinstall/transition paths leave it clear.) On
  suppressed ticks the decode is SKIPPED (not re-run on stale
  maps — the decode is idempotent but costs ~0.7 fr/tick if
  run every tick; the sprite keeps interpolating in VBlank).
- Scan: check window (5,5) first (the leader), then all
  (r,c) in order. recIdx = byte $FFB76C+(r+1)*32+(c+1), else
  byte $FFB36C+same; $FF = none. kind = rec[5]; keep only
  kinds 0/1 (kinds 2/3 stay baked in the terrain). Cap 12.
- Round-robin K=3 per tick: the leader (record at (5,5))
  ALWAYS decoded; 2 others rotate (cursor in $FFD002).
  A figure not decoded this tick keeps its old pattern,
  anchor and TARGET; its sprite still interpolates.
- Per figure (recIdx, r, c):
  1. recPtr = $FFB0CC + recIdx*12; d0b = 196-14c+14r;
     d1b = 18+8(r+c); mx = icx-5+r; my = icy-5+c.
  2. cellw = *map_chunk_cache_read(mx, my) (push scratch
     ptr, my, mx; d0 = $FF0248). tile, height, rec5, arg
     per F2.
  3. Clear the decode region in $FF1EC0 (M2 formula;
     9 rows x 11 cols max, ~3,168 B, word loop).
  4. jsr hero_track ($0231D8, kind 0) or
     map_promote_record ($02343A, kind 1) with
     (recPtr, d0b, d1b, arg) pushed. Skip flag is 0 here,
     so the skip hooks pass through (prologue + jmp-on).
     The routines read $FF0092 (shimmer), $FF010E (combat)
     and grid+$A (phase) themselves.
  5. Scan the cleared region for nonzero bytes -> bbox
     (byte granularity: minx always even). Empty bbox ->
     rows=0 (VBlank hides the sprite), TARGET still updated.
  6. Aligned origin tx0 = minx//8, ty0 = miny//8;
     sx = minx%8 in {0,2,4,6}, sy = miny%8;
     cols = maxx//8-tx0+1 (<=4), rows = maxy//8-ty0+1
     (<=5); ax = tx0*8-d0b; ay = ty0*8-d1b.
  7. Repack-copy to the VRAM cache (interrupts masked):
     body rows 0-3 to the slot's 16 tiles, row 4 (if any)
     to an allocated feet quad (LRU evict if all 3 in use;
     release the slot's quad when rows<5). The copy shifts
     by (sx,sy): output row r of tile (tc,tr) takes source
     row (tr*8+r+sy) from buffer tile (tx0+tc [+1 if the
     row crosses]) and the 4 bytes at byte offset sx/2 of
     the source row pair (tileA row ++ tileB row), via
     longword shift+OR (4 cases). One VDP address-set per
     contiguous run (jsr $DC60), then inline data-port
     writes (move.w d0,$C00000; R15=2 as the game's
     helpers rely on it).
  8. Slot update: recIdx, ax, ay, cols, rows, feetQuad,
     TARGET = (224*mx-224*my, 128*mx+128*my). If the slot
     is new or TARGET jumped > 1 cell from the old TARGET,
     snap CUR = TARGET; else keep CUR (it slides).
     lastSeen = $FF0010 low word.
- Slot assignment: match by recIdx; free slots go to new
  figures; if all 9 live, evict the oldest lastSeen
  non-leader slot. Slots whose recIdx is absent from the
  current scan are freed (their sprites hidden by VBlank).
- Cost: ~0.23 fr per figure, K=3 -> ~0.7 fr per decode
  tick; decodes happen only on body-decode ticks (~every
  16 fr while walking), so the amortised cost is negligible.

### 2.4 VBlank sprite update (vbl_entry, at .vdone, guarded
### by installed==1 — runs in room 156 AND the overworld)
- Per pattern slot i (0-8, body sprites for i<8):
  step CUR toward TARGET (clamp +-32/16 x, +-18/16 y per
  frame); scrX = 212 + (CURx>>4) - 14*(icx-icy) + ax +
  hScroll; scrY = 98 + (CURy>>4) - 8*(icx+icy) + ay -
  vScroll. Hide if scrX < -32 or > 320, scrY < -32 or >
  224, rows==0, or the menu/dialog hide applies (2.5).
  Words: w0 = scrY+128 (0 if hidden), w1 =
  (3<<10)|(3<<8)|link, w2 = base tile, w3 = scrX+128.
  Feet sprite (if rows==5 and a quad is allocated):
  w0 = scrY+32+128, w1 = (0<<10)|(3<<8)|link (32x8),
  w2 = quad tile, w3 = scrX+128.
- Chain: 22 -> live bodies (slot order) -> live feet
  (quad order) -> 23. Sprite 22's word1 is rewritten every
  VBlank (size 3,3, link = first live figure sprite, or 23
  if none); only word1 is touched (the game's sprite 22
  keeps its Y/pattern/X). The last live figure sprite links
  to 23. All 12 figure sprites' 4 words are written every
  VBlank (empty slots get Y=0); ~60 VDP ops, ~0.014 fr.
- Interpolation note (known limitation, phase D's job):
  TARGET updates only on body-decode ticks (~every 16 fr
  while walking, because the gate waits for scroll
  catch-up); the slide takes ~7 fr/cell (14 fr for a
  2-cell diagonal jump). The sprite therefore trails Buc by
  up to ~2 cells mid-walk and catches up at pauses. It
  NEVER teleports (the clamp) — the zigzag teleport is
  dead. The underlying pace mismatch (Buc 1 cell / ~8 fr
  vs scroll 1 cell / ~14 fr) is the phase-D governor's fix.

### 2.5 Menu/dialog hide
- When $FF00AC != 0 (menu open) or $FF0114 != 0 (dialog
  active), hide ALL figure sprites that VBlank. This
  matches the baked behaviour (figures are under the panel
  in the Plane B image) and needs no rect math. The menu
  is modal; figures reappear when it closes (CUR kept
  sliding while hidden, so no pop beyond one cell).

### 2.6 Figure-skip hooks
- hero_track $0231D8: 6 bytes displaced (link a6,#0;
  move.l a3,-(sp) = 4E56 0000 2F0B) -> jsr skip_hero.
- map_promote_record $02343A: 8 bytes displaced (link;
  movem.l d4-d5/a3,-(sp) = 4E56 0000 48E7 0C10) ->
  jsr skip_promote + nop (2 bytes, never executed).
- skip entries: if the sprite magic is not $9C07 OR the
  skip flag is 0 -> re-execute the displaced prologue,
  jmp to func+6 (hero) / func+8 (promote); the function's
  own rts returns to its caller. If the flag is 1 ->
  addq #4,sp (discard the hook's return) then rts (return
  to the caller of the figure routine as if it returned
  immediately). Stack stays balanced on both paths.
- The flag is set only around the body's decode in
  redraw_entry, and only when installed. Outside that
  window every figure call runs normally (other callers,
  scene setup, the blob's own decode).

### 2.7 Interrupt hazard
- The blob's main-loop VRAM sequences (the repack tile
  copy) mask interrupts (move.w sr,-(sp); ori #$0700,sr;
  ...; move.w (sp)+,sr). The $E358 decode is RAM-only
  (no masking). The VBlank hook's VRAM writes run inside
  VBlank (atomic w.r.t. the main loop). The game's own
  main-loop VDP sequences are unchanged (its pre-existing
  hazard, not made worse: the blob adds no main-loop VDP
  writes outside the masked copy).

### 2.8 Blob-size correction (found while building)
- The design (§2.1) budgeted the blob at <= 0xC00 bytes (to
  $FE000). The assembled blob is 4806 bytes ($FD400-$FE6C5) --
  the decode engine (clear/bbox/repack/slot alloc/evict) is
  bigger than the budget. The budget was conservative, not a
  hard limit: the original ROM is 0xFF from $FDE30 to the end
  of the 1 MB ROM (verified by a padding scan of both the
  original, MD5 30c18f..., and the B2 ROM), so the blob extends
  past $FE000 into verified-free padding. build.py asserts the
  padding ($FD400-$FD900 and $FDE30 to end-of-ROM) before
  overwriting, and asserts the bytes past the new blob end are
  0xFF. No stale B2 tail to clear: the new blob covers the
  whole old B2 blob.

### 2.9 Repack bounds guard (found on review, before building)
- The sub-tile shift reads up to 7 px rows past a figure's
  maxy. A figure at the very bottom of the 23-row decode
  window (miny >= 145, 5 rows) would read past the buffer end
  ($FF1EC0 + 26496 = $FF8640) into unrelated RAM (the sprite
  attribute area starts at $FF8644). The read is harmless, but
  nonzero bytes there would show as garbage pixels in the
  feet tile's bottom rows. Fix: repack_copy treats any source
  row with byte offset >= 26464 as a zero row (the threshold
  also covers tile B at +32). The M2 margin says the bbox
  never reaches buffer col 35 / row 22 in practice, so this
  is belt-and-braces.

## 3. Build checks (2026-11-13, build.py run)
- Base ROM MD5 ec7bcffe9c45fd851a6752dec5bcf788 asserted;
  original MD5 30c18fdbe2183f64702ae9f1a45d63f9 re-verified
  untouched. B2 blob (1328 bytes at $FD900) asserted equal to
  patches/b2-strip/source.bin; padding $FD400-$FD900 and
  $FDE30 to end-of-ROM asserted all 0xFF.
- Assemble: vasm, no errors. Blob 4806 bytes at $FD400:
  vbl +0x0, redraw +0x642, scene +0x1256, mapclose +0x1290,
  skip_hero +0x1210, skip_promote +0x1232.
- Unchanged-entry check (check_entries.py, capstone): scene
  10 insns and mapclose 9 insns disassemble to the identical
  instruction stream as the B2 blob, 0 non-equal ops.
- Hooks patched, old bytes asserted first:
  $1272 jmp $FD900 -> jmp $FD400 (nop kept);
  $1B918 jsr $FDB54 -> jsr $FDA42;
  $12C20 jsr $FDDC0 -> jsr $FE656;
  $16302 jsr $FDDFA -> jsr $FE690;
  $0231D8 link/move.l -> jsr $FE610;
  $02343A link/movem.l -> jsr $FE632 + nop.
- Statics unchanged from B2, asserted: R4 $8407 at $12C9A,
  pea $E000 at $12E68 and $16326, R16 $9001 at $12CDE,
  allocator $12D00-$12DE7 byte-identical to the base.
- Checksums: fix-all then verify-all OK (header stored
  0xBA42 = computed; runtime stored 0x544D2C66 = computed).
- IPS: rings-of-power-big-rework-full-c.ips, 6239 bytes,
  362 records; round-trip verified (base + IPS == ROM
  exactly). changed-bytes.txt: 362 records.
- Output ROM: rop-big-rework-full-c.rom, MD5
  385fa655a5a060ac6b66de8b9de795dd, 1,048,576 bytes.
- Original + base ROMs re-verified untouched after the build.
- NOT checked (per the task: minimal build checks only, no
  live probes, no screenshots, no cadence measurements):
  runtime behaviour, sprite positions, interpolation
  smoothness, decode cost, or the trailing-lag limitation.

## 4. What Dayset should test
- Boot the C ROM, walk into the Academy (room 156) and
  around the overworld. Buc, Thalmus, the students and NPCs
  should be visible as figures that GLIDE between cells
  (a few pixels per frame) instead of jumping, and the
  zigzag teleport should be gone.
- The figures should sit exactly on their terrain cells
  (no offset, no height-offset bugs) and stay glued to the
  terrain while the camera slides.
- Walk Buc 2 cells diagonally: the sprite should trail by
  up to ~2 cells mid-walk and catch up at the pause, never
  teleporting (known limitation, §5).
- Open the menu and a dialog: figures should hide while
  the panel is open and reappear when it closes.
- Combat: a figure with the 5-row (combat-extra) pattern
  should show its feet; with 4+ combat figures at once, the
  4th may briefly show 4 rows until its next decode.
- If anything looks wrong, note the exact place and what
  the figure did -- the sprite positions are numbers in
  $FFD010+, so a bad frame is diagnosable from the state.

## 5. Open / queued items
- Trailing lag (phase D's job): TARGET updates only on
  body-decode ticks (~every 16 fr while walking, because the
  gate waits for scroll catch-up); the slide takes ~7 fr/cell
  (14 fr for a 2-cell diagonal jump). The sprite therefore
  trails Buc by up to ~2 cells mid-walk and catches up at
  pauses. It never teleports (the clamp). The underlying pace
  mismatch (Buc 1 cell / ~8 fr vs scroll 1 cell / ~14 fr) is
  the phase-D governor's fix.
- Feet pool: 3 quads for 9 slots. A 4th simultaneous
  5-row (combat-extra) figure shows 4 rows (feet cut) until
  its next decode re-allocates (LRU). The 4th figure's body
  is always correct.
- Round-robin staleness: a figure not decoded this tick
  keeps its old pattern, anchor and TARGET; its sprite still
  interpolates. With 12 figures, each non-leader figure is
  re-decoded about every 4th decode tick.
- The blob is 4806 bytes ($FD400-$FE6C5); the remaining free
  padding ($FE6C6 to end-of-ROM, ~8 KB) is available for
  phase D.
- Nothing landed on main. The C ROM and patch are in the
  worktree only, for Dayset to test.
