; tall.s -- highlighted tall objects for Rings of Power (Mega Drive, 68000)
;
; Rebuilds the $FD400 flat blob on top of rop-noise.rom.
; Keeps the grey-noise fill for walkable land and water, and gives the
; tall objects (walls/trees -- the solid impassable objects) a grey
; shading/texture so they read as tall and stand out clearly, not just a
; flat dark grey. Dayset: "textures are the missing piece now, at least
; some solid should be highlighted."
;
; Entry points (unchanged): flat_skip $FD400, flat_top $FD412.
;
; Palette: the room render uses CRAM slot 0 (pal 10 day / pal 19 night,
; cross-faded). Grey ladder, monotonic in BOTH palettes:
;   idx 11 lum 182 (day) / 59 (night), idx 9 lum 109 / 36,
;   idx 7  lum 72 / 0, idx 0 black.
;
; Tall objects (impassable, tested with the same $1C892 move-path gate
; as the noise ROM): a vertical gradient + horizontal courses, in grey:
;   top tile row (lit top edge, the highlight): rows alternate
;     idx 11 (lum 182, the brightest grey) and idx 9 (lum 109) --
;     the bright top catches the eye, so the solid stands out clearly
;     against the land (avg lum ~145).
;   bottom tile row (shadowed base): rows alternate idx 7 (lum 72)
;     and idx 0 (black) -- the dark base grounds the object.
;   whole object avg lum ~91 (day), vs land ~145 and water ~90.
;   The object stays clearly darker than land on average (reads as a
;   solid, not ground), while its bright top edge highlights it.
;   The alternating rows are the texture (stone courses); the
;   bright-top / dark-base gradient is the height cue (reads as tall).
;   The gradient repeats per cell (each cell is bright at its top and
;   dark at its base), so a wall reads as stacked courses -- the fill
;   only ever sees one cell at a time, so a per-object gradient is not
;   possible. At night (pal 19) the greys go very dark, as in the noise
;   ROM -- the day distinction is the one that carries.
;
; The impassable rule is unchanged from the noise ROM (the $1C892
; terrain jump table, move_cost_calc returning 0 = blocked), NOT the
; $02DC0C statue-summon gate (which would wrongly mark Grass as a wall).
; Validated on chunk 233 (location 156): 286 impassable cells
; (Forest 4 x184, 31 x84, 32 x6, 33 x12).
;
; Implementation: the impassable category in the noise table is now 4
; FIXED tall patterns (top-even, top-odd, base-even, base-odd), not
; 4 hash variants. .blocked loads all 4 directly (d4/d0 = top pair,
; d1/d2 = base pair) and jumps to .fill, skipping the hash-based
; .patterns load. .patterns (land/water) copies d4/d0 into d1/d2, so
; the base pair equals the top pair (flat ground/water, no gradient).
; The fill writes the top 3 blocks with d4/d0, then swaps d1/d2 into
; d4/d0 and writes the bottom 3 blocks with the base pair. The fill is
; still 48 straight-line longword writes per cell, the same count as
; the solid/checkerboard/noise fill.
;
; Frame layout (map_chunk_pos, verified in rop.s):
;   -$4(a6) = chunk cell word (bits 0-8 tile index, bits 13-15 height)
;   -$6(a6) = $5EDC4 props word (terrain type bits 10-15)
;   -$2(a6) = tile index, but adjusted +-1 by the $FF0092 shimmer phase
;     AFTER the props word is loaded -- a tile-index test must use
;     -$4(a6) & $1FF, not -$2(a6). (No tile-index test is needed here:
;     the terrain type alone distinguishes water/impassable/walkable.)
; flat_top receives d0 = height*7. Stack: stream 4(a7), X 6(a7), Y 8(a7).
; The render buffer $FF1EC0 is tile-major: 36x23 tiles, 32 bytes per tile
; (8 longwords = 8 rows of 8 pixels at 4bpp), tile_row*1152 + tile_col*32.
; Each fill "block" is one tile = 8 consecutive longwords, d4/d0 alternating
; (even rows d4, odd rows d0). The 3x2 fill covers (tc..tc+2, tr..tr+1).
;
; Registers: d0 = odd-line pattern, d1 = terrain type then base-pair even
;   (tall base-even for impassable; copy of d4 for land/water),
;   d2 = cell hash then base-pair odd (tall base-odd for impassable;
;   copy of d0 for land/water), d3 = buffer base offset,
;   d4 = even-line pattern, d5 = tile_col, d6 = tile_row,
;   d7 = scratch (tile_col*32, then table offset),
;   a0 = buffer pointer, a1 = noise table pointer, a3 = preserved (movem).
; movem saves/restores d4-d7/a0-a1/a3, as in the flat-zoomed/dither/noise
; blobs. d0-d3 are scratch (already clobbered by the noise blob).

        org $FD400

    ; ---- flat_skip: skip $E358 for face/hidden calls (mode 2 only) ----
flat_skip:
    cmpi.w #2,$FF00AE.l
    bne.s flat_orig
    rts
flat_orig:
    jmp $E358.l

    ; ---- flat_top: flat fill for the top-tile call (mode 2 only) ----
flat_top:
    cmpi.w #2,$FF00AE.l
    bne.s flat_orig
    addq.w #1,$FFD7F6            ; gated call
    move.w 8(a7),d1              ; Y arg
    add.w d0,d1                  ; d1 = baseY
    move.w 6(a7),d2              ; X arg
    move.w d1,d3
    bmi.w .skip
    cmpi.w #184,d1
    bge.w .skip
    cmpi.w #64,d2
    blt.w .skip
    cmpi.w #352,d2
    bge.w .skip
    movem.l d4-d7/a0-a1/a3,-(a7)
    ; --- tile_row / tile_col / buffer base offset (needed by the hash) ---
    move.w d1,d6
    lsr.w #3,d6                  ; d6 = tile_row = baseY//8
    move.w d2,d5
    subi.w #64,d5
    lsr.w #3,d5                  ; d5 = tile_col = (X-64)//8
    move.w d6,d3
    mulu.w #1152,d3              ; d3 = tile_row * 1152
    move.w d5,d7
    mulu.w #32,d7                ; d7 = tile_col * 32
    add.w d7,d3                  ; d3 = buffer base offset
    ; --- cell hash h = ((col*0x9E37 + row*0x7F4A) >> 8) & 3 ---
    move.w d5,d2
    mulu.w #$9E37,d2             ; d2 = col * 0x9E37 (32-bit)
    move.w d6,d1
    mulu.w #$7F4A,d1             ; d1 = row * 0x7F4A (32-bit)
    add.l d1,d2                  ; d2 = sum
    lsr.l #8,d2
    andi.w #3,d2                 ; d2 = hash 0-3
    ; --- terrain type from the $5EDC4 props word ---
    move.w -$6(a6),d1
    lsr.w #8,d1
    lsr.w #2,d1                  ; d1 = terrain type (0-63)
    ; --- type >= 32 -> blocked (30-34 mode-7-only; 35-63 out of range) ---
    cmpi.w #32,d1
    bge.s .blocked
    ; --- water test (types < 32) ---
    move.l #$00E08C0D,d7         ; water mask: 0,2,3,10,11,15,21,22,23
    btst d1,d7
    bne.s .water
    ; --- blocked-low test (types < 32) ---
    move.l #$E0017010,d7         ; blocked mask: 4,12,13,14,16,29,30,31
    btst d1,d7
    bne.s .blocked
    ; --- walkable land: category base 0 ---
    moveq #0,d1
    bra.s .patterns
.water:
    moveq #16,d1                 ; category base 16 (water)
    bra.s .patterns
.blocked:
    ; tall objects: FIXED highlight/shadow patterns, no hash variation.
    ; top pair (lit, stands out) in d4/d0; base pair (shadow) in d1/d2.
    lea.l noise_tbl,a1
    move.l 32(a1),d4             ; tall top-even (idx 11, lum 182)
    move.l 36(a1),d0             ; tall top-odd  (idx 9,  lum 109)
    move.l 40(a1),d1             ; tall base-even (idx 7, lum 72)
    move.l 44(a1),d2             ; tall base-odd  (idx 0, black)
    bra.s .fill
.patterns:
    lea.l noise_tbl,a1
    move.w d2,d7
    asl.w #2,d7                  ; d7 = hash*4
    add.w d1,d7                  ; d7 = cat_base + hash*4
    move.l (a1,d7.w),d4          ; d4 = pattern[hash] (even rows)
    addq.w #1,d2
    andi.w #3,d2                 ; d2 = (hash+1) & 3
    asl.w #2,d2                  ; d2 = hash2*4
    add.w d1,d2                  ; d2 = cat_base + hash2*4
    move.l (a1,d2.w),d0          ; d0 = pattern[hash2] (odd rows)
    move.l d4,d1                 ; base pair = top pair (flat ground/water)
    move.l d0,d2
    ; --- fill: 3x2 block fill, 48 longword writes (as the noise fill) ---
.fill:
    lea.l $FF1EC0,a0
    adda.w d3,a0                 ; block (tc,tr)
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    cmpi.w #35,d5
    bge.s .nocol                 ; tc==35: no tc+1
    lea.l $FF1EC0,a0
    adda.w d3,a0
    adda.w #32,a0                ; block (tc+1,tr)
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    cmpi.w #34,d5
    bge.s .nocol                 ; tc>=34: no tc+2
    lea.l $FF1EC0,a0
    adda.w d3,a0
    adda.w #64,a0                ; block (tc+2,tr)
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
.nocol:
    cmpi.w #22,d6
    bge.s .norow                 ; tr==22: no tr+1
    move.l d1,d4                 ; base pair for the bottom tile row
    move.l d2,d0
    lea.l $FF1EC0,a0
    adda.w d3,a0
    adda.w #1152,a0              ; block (tc,tr+1)
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    cmpi.w #35,d5
    bge.s .norow
    lea.l $FF1EC0,a0
    adda.w d3,a0
    adda.w #1184,a0              ; block (tc+1,tr+1) = +1152+32
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    cmpi.w #34,d5
    bge.s .norow
    lea.l $FF1EC0,a0
    adda.w d3,a0
    adda.w #1216,a0              ; block (tc+2,tr+1) = +1152+64
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
    move.l d4,(a0)+
    move.l d0,(a0)+
.norow:
    addq.w #1,$FFD7FA            ; fill written
    movem.l (a7)+,d4-d7/a0-a1/a3
.done:
    rts
.skip:
    addq.w #1,$FFD7F8            ; bounds-check skip
    rts

    ; ---- noise table: land + water (4 hash patterns each), tall (4 fixed) ----
    ; land (idx 11/9): P0 all-11, P1 6x11+2x9, P2 alt 11/9, P3 all-9
noise_tbl:
    dc.l $BBBBBBBB,$BB9BBB9B,$B9B9B9B9,$99999999
    ; water (idx 9/7): P0 all-9, P1 6x9+2x7, P2 alt 9/7, P3 all-7
    dc.l $99999999,$99799979,$97979797,$77777777
    ; tall (impassable): top-even idx 11, top-odd idx 9,
    ;   base-even idx 7, base-odd idx 0 (bright top, dark base)
    dc.l $BBBBBBBB,$99999999,$77777777,$00000000
