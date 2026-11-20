; noise.s -- grey-noise flat fill for Rings of Power (Mega Drive, 68000)
;
; Rebuilds the $FD400 flat blob on top of rop-dither.rom.
; Replaces the checkerboard fill with a deterministic grey-noise fill:
;   walkable land = light grey noise, water = darker grey noise,
;   impassable terrain (walls/trees) = darkest grey noise (clearly darker
;   than the walkable ground, so Dayset can navigate by sight).
;
; Entry points (unchanged): flat_skip $FD400, flat_top $FD412.
; The four fig_* stubs from the flat-zoomed blob are DEAD CODE on this base
; (figure call sites point at the $FD600 feet-fix stubs; nothing calls the
; $FD400 fig stubs) -- they are removed here to make room for the noise
; table and the terrain test.
;
; Palette: the room render uses CRAM slot 0 (pal 10 day / pal 19 night,
; cross-faded). Grey ladder, monotonic in BOTH palettes:
;   idx 11 lum 182 (day) / 59 (night), idx 9 lum 109 / 36,
;   idx 7  lum 72 / 0, idx 0 black.
; Categories (tested in order):
;   water (terrain type in {0,2,3,10,11,15,21,22,23}) -> idx 9/7, avg lum ~90
;   impassable non-water (blocked on foot, $1C892 terrain jump table)   -> idx 7/0, avg lum ~36
;   walkable land (everything else)                                      -> idx 11/9, avg lum ~145
; Land:water ~1.6x, land:impassable ~4x, water:impassable ~2.5x (day).
; The exact darkening factor does not matter -- impassable must only read
; clearly darker than the walkable ground (Dayset's correction).
;
; Noise: 4 precomputed longword patterns per category (all-A, 6A+2B,
; alternating A/B, all-B), selected per cell by a deterministic hash of
; (tile_col, tile_row): h = ((col*0x9E37 + row*0x7F4A) >> 8) & 3.
; Even lines use pattern[h], odd lines pattern[(h+1)&3], so the shade varies
; per cell AND per line. Deterministic per cell -- no flicker.
; The fill itself is still 48 straight-line longword writes per cell, the
; same count as the solid/checkerboard fill.
;
; Terrain test (from -$6(a6) = the $5EDC4 props word, terrain type bits 10-15):
;   type >= 32 -> blocked (types 30-34 are mode-7-only; types 35-63 are
;     out of the $1C892 jump table's range and set the blocked flag)
;   type < 32  -> water mask $00E08C0D (types 0,2,3,10,11,15,21,22,23),
;     then blocked-low mask $E0017010 (types 4,12,13,14,16,29,30,31),
;     else walkable land. Type 15 is in both the water set and the blocked
;     set; water is tested first, so it draws as water.
; This is the $1C892 move-path gate (move_cost_calc returning 0 = blocked),
; NOT the $02DC0C statue-summon gate (which would wrongly mark Grass as a
; wall). Validated on chunk 233 (location 156): 286 impassable cells
; (Forest 4 x184, 31 x84, 32 x6, 33 x12); the $02DC0C rule would mark 475.
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
; Registers: d0 = odd-line pattern, d1 = terrain type then category base,
;   d2 = cell hash then pattern offset, d3 = buffer base offset,
;   d4 = even-line pattern, d5 = tile_col, d6 = tile_row,
;   d7 = scratch (tile_col*32, then table offset),
;   a0 = buffer pointer, a1 = noise table pointer, a3 = preserved (movem).
; movem saves/restores d4-d7/a0-a1/a3, as in the flat-zoomed/dither blobs.

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
    moveq #32,d1                 ; category base 32 (impassable)
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
    ; --- fill: 3x2 block fill, 48 longword writes (as the dither fill) ---
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

    ; ---- noise table: 3 categories x 4 patterns (48 bytes) ----
    ; land (idx 11/9): P0 all-11, P1 6x11+2x9, P2 alt 11/9, P3 all-9
noise_tbl:
    dc.l $BBBBBBBB,$BB9BBB9B,$B9B9B9B9,$99999999
    ; water (idx 9/7): P0 all-9, P1 6x9+2x7, P2 alt 9/7, P3 all-7
    dc.l $99999999,$99799979,$97979797,$77777777
    ; impassable (idx 7/0): P0 all-7, P1 6x7+2x0, P2 alt 7/0, P3 all-0
    dc.l $77777777,$77077707,$70707070,$00000000
