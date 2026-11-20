; flat-zoom v5: terrain decodes -> flat fills in the room view ($FF00AE==2).
; The decoder scatters a tile's 8 lines (row[Y+k] + col[k+(X-64)/2], k=0..7),
; so a contiguous 32-byte block does NOT cover the tile (v1-v4 proved it:
; only scattered squares, black interior). This version writes the flat
; colour to the exact 8 line positions $E358 computes, 4 bytes each.
;   flat_level -> $01BC1A (face, k=d6+1) and $01BC3C (hidden $230, k=d6+1)
;   flat_top   -> $01BC84 (top tile; k=height+1, water tiles k=9)
; If $FF00AE != 2 (world view) both tail-call the original $E358.
; Preserves d4-d6/a3-a6 (movem save/restore around the fill).

        org $FD400

flat_level:
        cmpi.w  #2,$FF00AE.l
        bne.s   flat_orig
        move.w  6(a7),d0            ; X
        move.w  8(a7),d1            ; Y
        move.w  d6,d2               ; level
        addq.w  #1,d2               ; k = level+1
        bra.s   flat_fill8

flat_top:
        cmpi.w  #2,$FF00AE.l
        bne.s   flat_orig
        move.w  6(a7),d0            ; X
        move.w  8(a7),d1            ; Y
        move.w  4(a7),d2            ; stream = tile index
        cmpi.w  #28,d2
        beq.s   flat_water
        cmpi.w  #29,d2
        beq.s   flat_water
        cmpi.w  #494,d2
        beq.s   flat_water
        move.w  -4(a6),d2           ; cell word
        rol.w   #3,d2
        and.w   #7,d2               ; height 0..7
        addq.w  #1,d2               ; k = height+1
        bra.s   flat_fill8
flat_water:
        moveq   #9,d2               ; k = 9 (water)
        bra.s   flat_fill8

flat_orig:
        jmp     $00E358.l           ; tail-call original decode

; flat_fill8: d0=X, d1=Y, d2=k. Writes 4 flat bytes at each of the 8 line
; positions row[Y+k]+col[k+(X-64)/2], k=0..7. Skips out-of-range lines.
flat_fill8:
        movem.l d4-d6/a3,-(sp)
        move.w  d2,d3
        lsl.w   #4,d3
        or.w    d2,d3               ; d3 = fill byte (k<<4)|k
        move.w  d0,d4
        subi.w  #64,d4
        asr.w   #1,d4               ; d4 = (X-64)/2 (base col word index)
        lea.l   $435C0,a0           ; col table
        lea.l   $436E0,a1           ; row table
        lea.l   $FF1EC0,a2          ; buffer base
        moveq   #0,d5               ; k2 = 0..7
.line_loop:
        move.w  d1,d6
        add.w   d5,d6               ; Y+k2
        bmi.s   .next               ; Y+k2 < 0 -> skip
        cmpi.w  #184,d6
        bge.s   .next               ; Y+k2 >= 184 -> skip
        add.w   d6,d6               ; (Y+k2)*2 byte offset
        move.w  (a1,d6.w),d6        ; row word
        move.w  d5,d7
        add.w   d4,d7               ; k2 + (X-64)/2
        bmi.s   .next               ; col idx < 0 -> skip
        cmpi.w  #144,d7
        bge.s   .next               ; col idx >= 144 -> skip
        add.w   d7,d7               ; *2 byte offset
        move.w  (a0,d7.w),d7        ; col word
        lea.l   (a2,d6.w),a3        ; a3 = buffer + row
        adda.w  d7,a3               ; a3 += col
        move.b  d3,(a3)+
        move.b  d3,(a3)+
        move.b  d3,(a3)+
        move.b  d3,(a3)+
.next:
        addq.w  #1,d5
        cmpi.w  #8,d5
        blt.s   .line_loop
        movem.l (sp)+,d4-d6/a3
        rts
