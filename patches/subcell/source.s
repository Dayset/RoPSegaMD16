; subcell.s — subcell movement for the leader figure (Buc, char 1) in the
; B-zoom view (mode 2, the room).
;
; Hook: hero_track $023202 (lea.l $197B0,a0) -> jsr subcell_hook.
; The hook runs inside hero_track, after the frame is linked, so a6 is the
; frame pointer and the draw record is the stack arg at 8(a6).
;
; What it does:
;   - Only in mode 2 ($FF00AE == 2, room / B-zoom view) and only for Buc's
;     draw record (char 1, record index at $FF02EC = char+0x04).
;   - Overrides the template index d0 with a WALK template (36 + facing
;     dir, where dir 0=N,1=E,2=S,3=W; Buc walking south uses template 38,
;     the cutscene walkers' template) so hero_track applies the
;     per-phase dx/dy from the $197B0 table during the 3 in-between ticks.
;   - The record in RAM is NEVER modified (only the d0 register), so the
;     $022F52 record stepper still sees the original static template
;     (stepcode 0 = no-op) and never moves the record on its own.
;   - A movement latch (RAM $FFD000-$FFD006) applies the walk template
;     only while Buc is actually stepping: it latches ON when Buc's cell
;     changes and OFF at the next phase-0 render with no cell change, so
;     a standing Buc is drawn with the original static template (no idle
;     wobble). Walk-template group 0 has dx/dy (0,0), so phase 0 is exact
;     in any case.
;
; Open question (Dayset's playtest is the check): whether the leader
; figure's cell commits every 4 ticks (phase 3->0 wrap, as docs/subcell.md
; says) or every tick. If it commits every tick, the figure will still
; jump a full cell per tick with a wobble on top, and a pacing gate in the
; movement block would be the follow-up. See REPORT.md.
;
; Blob at $FD800 (0xFF padding in the base ROM; above the runtime-checksum
; range $000000-$FD07B, so it does not affect the runtime sum, but the
; hook-site change at $023202 does, and the header checksum covers the
; whole ROM — both are fixed by checksum.py fix-all).

        org     $FD800

; --- RAM latch state (free scratch; not a game variable) ---
LATCH_X  equ     $FFD000  ; Buc cell X at last observed step
LATCH_Y  equ     $FFD002  ; Buc cell Y at last observed step
LATCH_ON equ     $FFD004  ; 1 = a step is in progress (apply walk template)
LATCH_IN equ     $FFD006  ; 1 = latch initialised

; --- game addresses ---
MODE     equ     $FF00AE  ; world/room mode flag (1 = overworld, 2 = room)
BUC_REC  equ     $FF02EC  ; char 1 (Buc) +0x04: draw record index
BUC_DIR  equ     $FF02F2  ; char 1 (Buc) +0x0A: heading (0-3)
BUC_X    equ     $FF02F4  ; char 1 (Buc) +0x0C: grid X
BUC_Y    equ     $FF02F6  ; char 1 (Buc) +0x0E: grid Y
GRIDBASE equ     $FFA7FC  ; ram_map_grid_base (pointer); +$A = grid+$A phase
RECBASE  equ     $FFB0CC  ; draw records (12 bytes each)
TPLBASE  equ     $197B0   ; template table (36 bytes per template)

subcell_hook:
        movem.l d1-d2/a0-a2,-(a7)
        ; gate: mode 2 (room / B-zoom view) only
        cmpi.w  #2,MODE
        bne     sc_orig
        ; Buc's draw record index -> record pointer
        move.w  BUC_REC,d1
        cmpi.w  #$FFFF,d1
        beq     sc_orig
        cmpi.w  #56,d1
        bcc     sc_orig
        mulu.w  #12,d1
        lea.l   RECBASE,a0
        adda.l  d1,a0            ; a0 = Buc's record pointer
        movea.l 8(a6),a1         ; a1 = record being drawn
        cmpa.l  a0,a1
        bne     sc_orig
        ; ---- Buc, mode 2: movement latch ----
        ; current phase (grid+$A, 0-3)
        movea.l GRIDBASE,a0
        move.w  $A(a0),d1        ; d1 = phase
        move.w  d1,d2            ; d2 = phase (kept)
        ; first call: initialise the latch cell, do not latch on
        tst.w   LATCH_IN
        bne     sc_have
        move.w  #1,LATCH_IN
        move.w  BUC_X,LATCH_X
        move.w  BUC_Y,LATCH_Y
        bra     sc_orig
sc_have:
        ; did Buc's cell change since the last step?
        move.w  BUC_X,d1         ; d1 = Buc X
        cmp.w   LATCH_X,d1
        bne     sc_changed
        move.w  BUC_Y,d1         ; d1 = Buc Y
        cmp.w   LATCH_Y,d1
        beq     sc_nochange
sc_changed:
        ; cell changed: latch on, store the new cell
        move.w  #1,LATCH_ON
        move.w  BUC_X,LATCH_X
        move.w  BUC_Y,LATCH_Y
        bra     sc_apply
sc_nochange:
        ; no cell change: at phase 0 the step is over, latch off
        tst.w   d2
        bne     sc_apply
        clr.w   LATCH_ON
sc_apply:
        tst.w   LATCH_ON
        beq     sc_orig
        ; ---- apply the walk template ----
        ; dir = Buc heading (0-3); walk template = 36 + dir
        move.w  BUC_DIR,d1
        andi.w  #3,d1
        addi.w  #36,d1
        mulu.w  #36,d1           ; d1 = template*36
        move.w  d2,d0            ; d0 = phase
        lsl.w   #3,d0            ; d0 = phase*8
        add.w   d1,d0            ; d0 = template*36 + phase*8
        bra     sc_done
sc_orig:
        ; d0 unchanged: the original template offset stands
sc_done:
        movem.l (a7)+,d1-d2/a0-a2
        lea.l   TPLBASE,a0       ; displaced instruction
        rts
