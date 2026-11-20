; cutscene-loop: drive Buc in a loop during the Buc cutscene (script $1A228).
; Base: rop-flat-zoomed-feet.rom (MD5 9373c0d01cf08c20f28e256daa9ea142)
; — flat only on mode 2, feet fix. Blob at $FD800 (free 0xFF padding,
; after the feet-fix blob at $FD600-$FD780).
;
; WHY A LOOP DRIVER, NOT A BIGGER LOOP: the room (location 156, chunk 233)
; is a 32x32 maze, not an open floor. Decoded chunk 233 and mapped
; walkability (terrain 5/9/18 or tile $24, no height stack, no step-tile,
; no hazard): a 20x20 square loop from Buc's start (6,17) does NOT fit —
; south runs out of bounds at Y=37, and the largest fitting rectangle
; from (6,17) is only 7x2 (7 south, 2 east, 7 north, 2 west). So instead
; of a fixed square, Buc walks up to 20 cells per leg in the order
; S,E,N,W (Dayset's "20 down, 20 right, 20 up, 20 left") and TURNS to
; the next direction when blocked (wall / student) or after 20 steps.
; He walks each direction as far as the room allows, keeps moving
; (no long stands on blocked legs), and the loop repeats while the
; cutscene is active.
;
; TWO HOOKS:
;   loop_drive - sys_event_run $02D56E (replaces tst.w $FF010A.l, 6 bytes).
;     While the Buc cutscene is active, steps Buc one cell along the loop
;     via combat_move_unit, once per sys_event_run call (one cell per
;     4 ticks, the script's pace). Runs even during dialog stalls
;     ($FF010A==0), because the hook sits before sys_event_run's early
;     return — so Buc keeps walking while a message is on screen.
;   loop_op5   - op-5 handler $02D7F6 (replaces jsr combat_move_unit.l).
;     Suppresses the script's own op-5 moves for Buc (char 1) while the
;     loop is active, so the script doesn't move Buc a second cell in
;     the same tick (which would desync the loop's step count from Buc's
;     position). Thalmus's moves (char 3) and other scripts are unaffected.
;
; GATE (both hooks): script pointer $FFC384 in [$1A228, $1A390] (the Buc
; script). loop_drive additionally requires $FF0110 != 0.
; On the first call (pointer == $1A228) the state is reset (dir=S,
; step=0) and the move is skipped (the op-1 teleport runs in the same
; call, placing Buc at (6,17)).
;
; LOOP STATE (RAM, free: not in disasm/symbols/ram.csv; not the feet-fix
; list $FFD800/$FFD802; not the subcell latch $FFD000-$FFD006):
;   $FFD100: loop_dir  (word) 0=N,1=E,2=S,3=W. Start 2 (S).
;   $FFD102: loop_step (word) steps taken in the current leg (0..19).
; Direction order S,E,N,W = 2,1,0,3; next dir = (dir+3) mod 4.
; A leg ends after 20 steps OR when Buc is blocked (his X/Y unchanged
; by combat_move_unit); on a block Buc turns immediately.
;
; Register discipline:
;   loop_drive saves/restores d0-d7/a0-a6 (combat_move_unit clobbers) and
;   re-executes the displaced tst.w $FF010A.l last, so the bne at
;   $02D574 reads the correct flags. It returns with rts to $02D574.
;   loop_op5 uses only d0 (scratch; the op-5 handler does not use d0
;   after the jsr). It either rts (skip the move) or tail-calls
;   combat_move_unit with jmp (stack already holds ret/char/dir exactly
;   as a direct jsr would).

        org $FD800

; --- loop_drive: hook 1 (sys_event_run $02D56E) ---
loop_drive:
        movem.l d0-d7/a0-a6,-(a7)
        tst.w   $00FF0110.l
        beq.w   .done
        move.l  $00FFC384.l,d0
        cmpi.l  #$1A228,d0
        blt.w   .done
        cmpi.l  #$1A390,d0
        bgt.w   .done
        cmpi.l  #$1A228,d0
        bne.s   .drive
        ; first call: reset state, skip the move (op-1 teleports Buc next)
        move.w  #2,$00FFD100.l
        clr.w   $00FFD102.l
        bra.w   .done
.drive:
        ; validate state (safety net for garbage RAM)
        move.w  $00FFD100.l,d0
        cmpi.w  #3,d0
        bhi.s   .reset
        move.w  $00FFD102.l,d1
        cmpi.w  #20,d1
        bhs.s   .reset
        bra.s   .go
.reset:
        move.w  #2,$00FFD100.l
        clr.w   $00FFD102.l
.go:
        ; Buc's cell: char 1 struct $FF02B4+0x34=$FF02E8;
        ; X at +0x0C=$FF02F4, Y at +0x0E=$FF02F6
        move.w  $00FF02F4.l,d2
        move.w  $00FF02F6.l,d3
        move.w  $00FFD100.l,d1
        move.w  d1,-(a7)
        move.w  #1,-(a7)
        jsr     $024984.l
        addq.w  #4,a7
        move.w  $00FF02F4.l,d4
        move.w  $00FF02F6.l,d5
        cmp.w   d2,d4
        bne.s   .moved
        cmp.w   d3,d5
        bne.s   .moved
        ; blocked: turn to the next direction
        bra.s   .nextleg
.moved:
        move.w  $00FFD102.l,d0
        addq.w  #1,d0
        cmpi.w  #20,d0
        blt.s   .store_step
        bra.s   .nextleg
.store_step:
        move.w  d0,$00FFD102.l
        bra.w   .done
.nextleg:
        clr.w   $00FFD102.l
        move.w  $00FFD100.l,d0
        addq.w  #3,d0
        cmpi.w  #4,d0
        blt.s   .store_dir
        subq.w  #4,d0
.store_dir:
        move.w  d0,$00FFD100.l
.done:
        movem.l (a7)+,d0-d7/a0-a6
        tst.w   $00FF010A.l
        rts

; --- loop_op5: hook 2 (op-5 handler $02D7F6) ---
; Entry (via jsr): (a7)=ret $02D7FC, 4(a7)=char, 6(a7)=dir.
loop_op5:
        move.w  4(a7),d0
        cmpi.w  #1,d0
        bne.s   .go
        move.l  $00FFC384.l,d0
        cmpi.l  #$1A228,d0
        blt.s   .go
        cmpi.l  #$1A390,d0
        bgt.s   .go
        rts
.go:
        jmp     $024984.l
