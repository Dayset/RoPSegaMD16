; flat-zoomed: ONE flat ground plane for the ZOOMED view ONLY (the room /
; location interior, mode 2) — the big world (overworld, mode 1) stays
; fully textured. Base: ORIGINAL ROM. Blob at $FD400 (free 0xFF padding).
;
; The zoomed view is the location interior reached by pressing B (ENTER)
; in the overworld: verb $1E -> sys_struct52_flag_test -> a mode-1
; location transition into a room (mode 2, room grid $FFB09C/$FFB0AC/
; $FFB0BC, $FF0E98 = the location number). Probe-verified twice (run 1 +
; run 2, .scratch-zoomed-gate): B in the overworld flips mode 1 -> 2 and
; $FF0E98 $FFFF -> $001E (location 30); walking Right out of the room
; flips it back (mode 1, $FF0E98 $FFFF).
;
; $FF0E98 is NOT the discriminator (the earlier hypothesis): it is ALWAYS
; $FFFF in the overworld (mode 1) — in every mode-1 observation across
; both probe runs, including after walking and after exiting a room. So a
; gate of (mode 1 + grid $FFB08C + $FF0E98==$FFFF) is IDENTICAL to the
; flat-ground-plane gate (mode 1 + grid $FFB08C): it would still flatten
; the big world and change nothing. The real discriminator is the MODE:
; mode 1 = big world (textured), mode 2 = zoomed view / room (flat).
; Hence this patch gates on $FF00AE==2 ONLY (mode 2 implies a room grid).
;
; The ground is ONE geometric plane: all ground cells at one level.
;   - face ($01BC1A) and hidden ($01BC3C) $E358 calls are SKIPPED when gated
;     (the height-stack sides are not drawn at all).
;   - top ($01BC84) is replaced by a 32-byte BLOCK FILL at the tile's own block
;     (base Y, not the height-adjusted Y), so the ground is a single plane.
;     Block start = $FF1EC0 + (baseY//8)*1152 + ((X-64)//8)*32.
;     baseY = Y_arg + d0 (d0 = height*7, set by map_chunk_pos at $01BC70).
;     Land = 0x33 (green), water = 0x11 (dark blue), from the props word
;     at -$6(a6) (terrain type bits 10-15, water table below).
;   - figures (hero_track / map_promote_record / map_tile_at_offset /
;     map_animated_tile, 8 call sites) get their height-offset arg zeroed
;     when gated, so they stand ON the flat plane instead of floating
;     height*7 px above it.
; Trees are entities drawn via the figure path, so they stay detailed.
; Buildings are terrain tiles, so they flatten with the ground.
;
; Gate: $FF00AE==2 (room / zoomed view). The overworld (mode 1) is
; untouched: every stub tail-calls the original $E358 / routine when not
; gated. $E358 is SKIPPED for the ground when gated.
;
; Register discipline (follows the flat-zoom v5 stub):
;   flat_top reads X/Y/stream from the stack BEFORE any movem, uses d0-d3
;   as scratch (the caller reloads d0/d1 after the call; d2/d3 are dead),
;   preserves d4-d7/a0-a1/a3 around the fill, never touches a6 (frame ptr).
;   The gate check is a single cmpi.w on $FF00AE (no data register needed).
;   (cmpi.l #imm,An is not a valid 68000 instruction, so a grid compare
;   would need a Dn — but this gate needs no grid compare at all.)

        org $FD400

; --- flat_skip: face ($01BC1A) / hidden ($01BC3C). Gated -> draw nothing (rts).
;     Not gated -> tail-call the original $E358.
;     (d6 is the height-loop counter, so it is never touched here.)
flat_skip:
        cmpi.w  #2,$FF00AE.l
        bne.s   flat_orig
        rts
flat_orig:
        jmp     $00E358.l

; --- flat_top: top tile ($01BC84). Gated -> 3x2 block fill at base Y
;     (bridges the 14-px isometric X step so the plane is solid, not a
;     checkerboard). Not gated -> tail-call the original $E358.
;     Entry: d0 = height*7 (map_chunk_pos $01BC70); stack: stream 4(a7),
;     X 6(a7), Y 8(a7) (Y = baseY - height*7).
; --- DEBUG counters (RAM $FFD7F6-$FFD7FA, free scratch near the probe):
;     $FFD7F6 = flat_top gated calls, $FFD7F8 = bounds-check skips,
;     $FFD7FA = fills actually written. Read after a run to see whether
;     the checkerboard is a skip problem or an offset problem.
flat_top:
        cmpi.w  #2,$FF00AE.l
        bne.s   flat_orig
        addq.w  #1,$FFD7F6          ; gated call
        move.w  8(a7),d1            ; Y arg
        add.w   d0,d1               ; d1 = baseY (d0 = height*7, untouched above)
        move.w  6(a7),d2            ; X arg
        move.w  d1,d3
        bmi.w   .skip               ; baseY < 0 -> skip (.w: .skip is >127B away now)
        cmpi.w  #184,d1
        bge.w   .skip               ; baseY >= 184 -> skip
        cmpi.w  #64,d2
        blt.w   .skip               ; X < 64 -> skip
        cmpi.w  #352,d2
        bge.w   .skip               ; X >= 352 -> skip
        movem.l d4-d7/a0-a1/a3,-(a7)
        move.w  -$6(a6),d3          ; props word (cell terrain)
        lsr.w   #8,d3
        lsr.w   #2,d3               ; d3 = terrain type (bits 10-15)
        lea.l   water_tbl,a1
        move.b  (a1,d3.w),d3
        tst.b   d3
        bne.s   .water
        move.l  #$33333333,d4       ; land green 0x33
        bra.s   .fill
.water:
        move.l  #$11111111,d4       ; water dark blue 0x11
.fill:
; 3x2 block fill: the isometric X step (14 px = 1.75 tiles) means the
; central tile column takes only EVEN values, so a 1-block fill leaves
; the odd columns black (the checkerboard). Filling (tc..tc+2,
; tr..tr+1) bridges the column gaps (and the diagonal row jump).
        move.w  d1,d6
        lsr.w   #3,d6               ; d6 = tile_row = baseY//8 (0..22)
        move.w  d2,d5
        subi.w  #64,d5
        lsr.w   #3,d5               ; d5 = tile_col = (X-64)//8 (0..35)
        move.w  d6,d3
        mulu.w  #1152,d3            ; d3 = tile_row * 1152
        move.w  d5,d7
        mulu.w  #32,d7              ; d7 = tile_col * 32
        add.w   d7,d3               ; d3 = base offset (tc,tr)
        lea.l   $FF1EC0,a0
        adda.w  d3,a0               ; block (tc,tr)
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        cmpi.w  #35,d5
        bge.s   .nocol              ; tc==35: no tc+1
        lea.l   $FF1EC0,a0
        adda.w  d3,a0
        adda.w  #32,a0              ; block (tc+1,tr)
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        cmpi.w  #34,d5
        bge.s   .nocol              ; tc>=34: no tc+2
        lea.l   $FF1EC0,a0
        adda.w  d3,a0
        adda.w  #64,a0              ; block (tc+2,tr)
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
.nocol:
        cmpi.w  #22,d6
        bge.s   .norow              ; tr==22: no tr+1
        lea.l   $FF1EC0,a0
        adda.w  d3,a0
        adda.w  #1152,a0            ; block (tc,tr+1)
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        cmpi.w  #35,d5
        bge.s   .norow
        lea.l   $FF1EC0,a0
        adda.w  d3,a0
        adda.w  #1184,a0            ; block (tc+1,tr+1) = +1152+32
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        cmpi.w  #34,d5
        bge.s   .norow
        lea.l   $FF1EC0,a0
        adda.w  d3,a0
        adda.w  #1216,a0            ; block (tc+2,tr+1) = +1152+64
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
        move.l  d4,(a0)+
.norow:
        addq.w  #1,$FFD7FA          ; fill written
        movem.l (a7)+,d4-d7/a0-a1/a3
.done:
        rts
.skip:
        addq.w  #1,$FFD7F8          ; bounds-check skip
        rts

; --- fig_* : figure-draw call sites. Gated -> zero the height-offset arg
;     (first-pushed arg; on stub entry the stack is [ret(4)][record(4)]
;     [X(2)][baseY(2)][heightOff(2)], so the height offset is at 12(a7))
;     so the figure stands on the flat plane.
;     Not gated -> pass through unchanged. Tail-call the real routine.
fig_hero:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        clr.w   12(a7)
.go:
        jmp     $0231D8.l           ; hero_track
fig_promote:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        clr.w   12(a7)
.go:
        jmp     $02343A.l           ; map_promote_record
fig_tile:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        clr.w   12(a7)
.go:
        jmp     $0232AC.l           ; map_tile_at_offset
fig_anim:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        clr.w   12(a7)
.go:
        jmp     $0232D2.l           ; map_animated_tile

; --- water_tbl: 64 bytes, 1 = water terrain type, 0 = land.
;     Water types: 0,2,3,10,11,15,21,22,23.
water_tbl:
        dc.b 1,0,1,1,0,0,0,0,0,0,1,1,0,0,0,1
        dc.b 0,0,0,0,0,1,1,1,0,0,0,0,0,0,0,0
        dc.b 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
        dc.b 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
