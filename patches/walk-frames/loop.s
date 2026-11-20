; walk-frames loop driver: drive Buc in a loop during the Buc cutscene
; (script $1A228). Base: rop-cutscene-loop.rom (MD5
; 79bccdcd927707802332f64f38faa641) — flat only on mode 2, feet fix,
; cutscene loop-walk (Buc walks the loop in all four directions).
; Blob at $FD800 (free 0xFF padding, after the feet-fix blob at
; $FD600-$FD780). This is the cutscene-loop driver REBUILT with one
; change only: Buc steps every OTHER sys_event_run call (one cell per
; 8 ticks instead of 4), and a walk_half flag ($FFD104) tracks which
; half of the cell the render is in, so the hero_track hook
; (walk-frames hook.s, $FDA00) can draw the half-cell slide.
;
; WHY 8 TICKS PER CELL: the walk template is indexed by grid+$A, a
; 4-phase counter (0-3, one phase per tick). Over an 8-tick cell the
; counter cycles TWICE, so each of the 4 existing walk frames is shown
; twice per cell — the frames are REPEATED (Dayset: no new art), and
; the animation has twice as many frames. The Y shift between the
; half-cell positions is 4 px (8, 12, 16, 20, 24 over the walk) instead
; of the 8 px cell jump (8, 16, 24) — Dayset's exact values, same
; start (8) and end (24), step by 4 instead of 8.
;
; The rest of the loop is unchanged from cutscene-loop: Buc walks up
; to 20 cells per leg in the order S,E,N,W and TURNS to the next
; direction when blocked (wall / student) or after 20 steps; the loop
; repeats while the cutscene is active.
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
;   $FFD104: walk_half (word) 0 = first half of the cell (ticks 0-3,
;            Buc drawn at the record cell), 1 = second half (ticks 4-7,
;            Buc drawn half a cell toward the next cell). Set by
;            loop_drive (once per sys_event_run call, i.e. once per
;            4 ticks); read by the hero_track hook in hook.s.
; Direction order S,E,N,W = 2,1,0,3; next dir = (dir+3) mod 4.
; A leg ends after 20 steps OR when Buc is blocked (his X/Y unchanged
; by combat_move_unit); on a block Buc turns immediately.
; A cell now takes 8 ticks (two sys_event_run calls): the first call
; after a step is the non-step call (walk_half 0->1, no move), the
; second call steps Buc (walk_half 1->0). The first step after the
; reset is therefore 8 ticks after the reset call, not 4 — a 4-tick
; delay at the very start of the cutscene, while the dialog is up.
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
        clr.w   $00FFD104.l
        bra.w   .done
.drive:
        ; validate state (safety net for garbage RAM)
        move.w  $00FFD100.l,d0
        cmpi.w  #3,d0
        bhi.s   .reset
        move.w  $00FFD102.l,d1
        cmpi.w  #20,d1
        bhs.s   .reset
        ; --- walk-frames: half-cell pacing ---
        ; walk_half==0: this is the non-step call (second half of the
        ; cell) — do NOT step, set walk_half=1 so the render draws the
        ; half-cell slide. walk_half==1: this call steps Buc (start of
        ; a new cell) — fall through to .go and set walk_half=0 there.
        tst.w   $00FFD104.l
        beq.s   .half
        bra.s   .go
.half:
        move.w  #1,$00FFD104.l
        bra.w   .done
.reset:
        move.w  #2,$00FFD100.l
        clr.w   $00FFD102.l
        clr.w   $00FFD104.l
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
        clr.w   $00FFD104.l
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
        clr.w   $00FFD104.l
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
