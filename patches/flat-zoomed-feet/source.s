; flat-zoomed-feet: draw figures AFTER all terrain fills, so the figure's
; feet are not covered by the flat fill. Base: the re-gated flat ROM
; (rop-flat-zoomed.rom, MD5 4ee66e521ac9a636d2167c0d55409d92) — flat only on
; mode 2 (the zoomed view / room), big world textured. Blob at $FD600
; (free 0xFF padding, after the flat-zoomed blob at $FD400-$FD5F0).
;
; DIAGNOSIS (Dayset's playtest, image-27.png; confirmed against the
; flat-zoomed probe screenshots zoom_probe_orig_zoom.png /
; zoom_probe_rz_zoom.png): in the original ROM Buc is fully visible down
; to his yellow feet; in the flat ROM his robe ends at the waist and the
; legs/feet are covered by flat green. The cause is the interleaving in
; map_chunk_pos: per window cell the terrain is drawn first (face/hidden/
; top), then the figure for that cell. The flat_top 3x2 block fill is a
; SOLID 24x16 px rectangle, unlike the original $E358 terrain decode,
; which writes only the diamond-shaped tile pixels (transparent corners).
; So a cell processed AFTER the figure's cell whose solid fill overlaps
; the figure's lower pixels covers the feet — in particular the cell at
; (d4+1, d5+1) has the same buffer X and Y+16, so its fill lands exactly
; on the tile the figure's feet stand on. No fill-shrinking fixes it:
; even a 1x1 fill of that tile covers the feet, because the feet ARE on
; that tile. The figure must be drawn after the fills that overlap it.
; The height offset is NOT the cause: the fig_* stubs already zero it so
; the figure stands on the flat plane at baseY, and the figure is at the
; correct Y — only its lower pixels are overwritten.
;
; FIX: defer every figure draw to a post-pass. The 8 fig_* stubs (which
; already hook the figure call sites in map_chunk_pos) RECORD the call
; instead of drawing when gated (mode 2): (routine addr, record, X, Y,
; heightOff=0) into a list in RAM. fig_replay, hooked at the end of
; map_chunk_pos ($01C0D6, replacing the 6-byte tst.w $FF013C.l with a
; jsr), draws every recorded figure on top of the finished terrain, then
; re-executes the tst and returns so the beq at $01C0DC works as before.
; When not gated (mode 1, big world) the stubs draw immediately exactly
; as before (the original textured render orders figures correctly via
; the diamond transparency), and the replay is a no-op.
;
; The map-promote side effect is NOT deferred: the $B36C/$B76C map update
; in map_chunk_pos (L01BF22) runs inline, before the jsr to the fig_*
; stub, so it still happens during the cell loop. Only the DRAW is
; deferred. The update moves a record between the two cell->record maps
; for the CURRENT cell only, so deferring the draw cannot affect any
; other cell's lookup in the same render.
;
; FIGURE LIST (RAM, free: no code references $FFD800+, ram.csv names
; nothing there except $FFD2EA, below this region; probes used $FFD800
; for logs without breaking the game; the stack only reaches ~$FFEB42):
;   $FFD800: count (word), $FFD802: entries, 14 bytes each:
;     routine addr (4), record ptr (4), X (2), Y (2), heightOff (2).
;   Max 128 entries ($FFD802-$FFDF02). If the list is full the stub falls
;   back to drawing immediately (old behaviour, height offset zeroed).
;
; Gate: $FF00AE==2 (room / zoomed view), same as the flat-zoomed patch.
; The overworld (mode 1) is untouched: every stub tail-calls the original
; routine when not gated, and the replay skips when not gated.
;
; Register discipline:
;   The record stubs use only d0/d3/a1 (scratch; the figure routines may
;   clobber d0-d3/a0-a2) and never touch d4-d7/a3-a4/a6 (map_chunk_pos's
;   loop counters / frame pointer) or the stack (no pushes, so the arg
;   offsets 4/8/10/12 stay valid). On stub entry the stack is
;   [ret(4)][record(4)][X(2)][Y(2)][heightOff(2)].
;   fig_replay saves/restores d0-d7/a0-a5 around the loop (a6 untouched,
;   it is map_chunk_pos's frame pointer) and keeps the stack balanced.

        org $FD600

; --- fig_hero: hero_track call site. Gated -> record, else draw now.
fig_hero:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        move.w  $00FFD800.l,d3      ; count
        cmpi.w  #128,d3
        bge.s   .full
        move.w  d3,d0
        mulu.w  #14,d0              ; d0 = count*14
        lea.l   $00FFD802,a1
        adda.l  d0,a1               ; a1 = entry ptr
        move.l  #$0231D8,(a1)+      ; routine = hero_track
        move.l  4(a7),(a1)+         ; record
        move.w  8(a7),(a1)+         ; X
        move.w  10(a7),(a1)+        ; Y
        clr.w   (a1)+               ; heightOff = 0 (flat plane)
        addq.w  #1,d3
        move.w  d3,$00FFD800.l      ; count++
        rts
.full:
        clr.w   12(a7)              ; zero height offset (flat plane)
.go:
        jmp     $0231D8.l           ; hero_track

; --- fig_promote: map_promote_record call site.
fig_promote:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        move.w  $00FFD800.l,d3
        cmpi.w  #128,d3
        bge.s   .full
        move.w  d3,d0
        mulu.w  #14,d0
        lea.l   $00FFD802,a1
        adda.l  d0,a1
        move.l  #$02343A,(a1)+      ; routine = map_promote_record
        move.l  4(a7),(a1)+
        move.w  8(a7),(a1)+
        move.w  10(a7),(a1)+
        clr.w   (a1)+
        addq.w  #1,d3
        move.w  d3,$00FFD800.l
        rts
.full:
        clr.w   12(a7)
.go:
        jmp     $02343A.l           ; map_promote_record

; --- fig_tile: map_tile_at_offset call site.
fig_tile:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        move.w  $00FFD800.l,d3
        cmpi.w  #128,d3
        bge.s   .full
        move.w  d3,d0
        mulu.w  #14,d0
        lea.l   $00FFD802,a1
        adda.l  d0,a1
        move.l  #$0232AC,(a1)+      ; routine = map_tile_at_offset
        move.l  4(a7),(a1)+
        move.w  8(a7),(a1)+
        move.w  10(a7),(a1)+
        clr.w   (a1)+
        addq.w  #1,d3
        move.w  d3,$00FFD800.l
        rts
.full:
        clr.w   12(a7)
.go:
        jmp     $0232AC.l           ; map_tile_at_offset

; --- fig_anim: map_animated_tile call site.
fig_anim:
        cmpi.w  #2,$FF00AE.l
        bne.s   .go
        move.w  $00FFD800.l,d3
        cmpi.w  #128,d3
        bge.s   .full
        move.w  d3,d0
        mulu.w  #14,d0
        lea.l   $00FFD802,a1
        adda.l  d0,a1
        move.l  #$0232D2,(a1)+      ; routine = map_animated_tile
        move.l  4(a7),(a1)+
        move.w  8(a7),(a1)+
        move.w  10(a7),(a1)+
        clr.w   (a1)+
        addq.w  #1,d3
        move.w  d3,$00FFD800.l
        rts
.full:
        clr.w   12(a7)
.go:
        jmp     $0232D2.l           ; map_animated_tile

; --- fig_replay: draw every recorded figure on top of the finished
;     terrain, then re-execute the tst that this hook replaced.
;     Hooked at $01C0D6 (replaces tst.w $FF013C.l); returns to $01C0DC
;     (the beq), whose flags are set by the tst below, exactly as the
;     original code intended.
;     Entry: no args. Clobbers nothing (saves/restores d0-d7/a0-a5).
fig_replay:
        cmpi.w  #2,$FF00AE.l
        bne.s   .tst
        movem.l d0-d7/a0-a5,-(a7)
        move.w  $00FFD800.l,d7      ; count
        beq.s   .done
        lea.l   $00FFD802,a5        ; entry ptr
        moveq   #0,d6               ; index
.loop:
        cmp.w   d7,d6
        bge.s   .done
        move.l  (a5)+,a0            ; routine addr
        move.l  (a5)+,d0            ; record
        move.w  (a5)+,d1            ; X
        move.w  (a5)+,d2            ; Y
        move.w  (a5)+,d3            ; heightOff
        move.w  d3,-(a7)            ; push heightOff
        move.w  d2,-(a7)            ; push Y
        move.w  d1,-(a7)            ; push X
        move.l  d0,-(a7)            ; push record
        jsr     (a0)                ; call the figure routine
        lea.l   10(a7),a7           ; pop 10 bytes of args
        addq.w  #1,d6
        bra.s   .loop
.done:
        clr.w   $00FFD800.l         ; reset count
        movem.l (a7)+,d0-d7/a0-a5
.tst:
        tst.w   $00FF013C.l
        rts
