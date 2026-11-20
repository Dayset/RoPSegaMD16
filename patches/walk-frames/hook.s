; walk-frames hero_track hook: draw Buc half a cell toward the next cell
; during the second half of each 8-tick cell, so the cutscene walk is
; 2x more animated with a smaller Y shift.
; Base: rop-cutscene-loop.rom (MD5 79bccdcd927707802332f64f38faa641) —
; flat only on mode 2, feet fix, cutscene loop-walk. Blob at $FDA00
; (free 0xFF padding; above the runtime checksum range $000000-$FD07B,
; so it does not affect the runtime sum, but the hook-site change at
; $023202 does, and the header checksum covers the whole ROM — both
; are fixed by checksum.py fix-all).
;
; HOW THE DOUBLING WORKS (Dayset's direction: repeat the existing
; frames, no new art; smaller Y shift):
; - The loop driver (loop.s, rebuilt $FD800 blob) now steps Buc every
;   OTHER sys_event_run call: one cell per 8 ticks instead of 4.
;   The walk template is indexed by grid+$A, a 4-phase counter (0-3,
;   one phase per tick). Over an 8-tick cell the counter cycles TWICE,
;   so each of the 4 existing walk frames (tiles 384+0/6/1/7 south,
;   384+0/6/1/7 east, 384+8/14/9/15 north, 384+9/14/8/15 west) is
;   shown twice per cell — the frames are REPEATED, no new art.
; - This hook draws Buc halfway to the next cell during the second
;   half of the cell (walk_half $FFD104 == 1, ticks 4-7). The half-step
;   is half the cell step vector (N +7,-4; E +7,+4; S -7,+4; W -7,-4).
;   So for a south step Buc's drawn Y goes 8, 12, 16, 20, 24 over the
;   walk (step 4) instead of 8, 16, 24 (step 8) — Dayset's exact
;   values: same start (8) and end (24), step by 4 instead of 8, with
;   the intermediate values 12 and 20 added.
; - The hook also SUBTRACTS the template's dx/dy wobble for the
;   current phase, so the drawn position is exactly the slide. The
;   wobble (+-6 px) is larger than the half-step (4 px Y, 7 px X), so
;   leaving it on top would make the motion non-monotonic (jerk back
;   and forth). The image still cycles (legs step); the position is
;   purely the slide. (Same reasoning as the interp ROM.)
; - The direction comes from loop_dir ($FFD100), the direction the
;   loop is walking; the half-step table is in this blob.
;
; WHAT THIS HOOK DOES:
; - Hook site: hero_track $023202 (lea.l $197B0,a0) -> jsr walk_hook.
;   The hook site is 6 bytes; the displaced lea is re-executed before
;   the rts, and d0 (the template offset hero_track computed) is
;   preserved — the record's template is never overridden, so the
;   image cycle is the record's own walk template.
; - Gates: mode 2 only, Buc's draw record only (char 1, $FF02EC),
;   cutscene active ($FF0110 != 0, pointer $FFC384 in [$1A228,$1A390]).
;   Otherwise the original lea stands and nothing changes.
; - The hook writes the adjusted X/Y to 12(a6)/14(a6) (hero_track's
;   X/Y args) BEFORE hero_track reads them. It fires whether the draw
;   comes from map_chunk_pos directly or via the feet-fix fig_replay
;   post-pass (the hook is inside hero_track, which both call).
; - Registers: saves/restores d1-d3/a0-a2 (movem); d0 is the template
;   offset for hero_track (preserved); a6 untouched; stack balanced.
;   Exits with rts (jsr hook), never jmp.
;
; RAM used: $FFD100 (loop_dir, owned by the loop driver), $FFD104
; (walk_half, owned by the loop driver). No new RAM.
; No collision with the feet-fix list ($FFD800+) or the loop blob
; ($FD800-$FD90A) or the flat blob ($FD400-$FD600).

        org     $FDA00

; --- game addresses ---
MODE     equ     $FF00AE  ; world/room mode flag (1 = overworld, 2 = room)
SCRIPT   equ     $FF0110  ; $FF0110 != 0 while an event script runs
PTR      equ     $FFC384  ; script pointer (sys_event_run)
BUC_REC  equ     $FF02EC  ; char 1 (Buc) +0x04: draw record index
RECBASE  equ     $FFB0CC  ; draw records (12 bytes each)
TPLBASE  equ     $197B0   ; template table (36 bytes per template)
LOOPDIR  equ     $FFD100  ; loop direction (0=N,1=E,2=S,3=W)
WALKHALF equ     $FFD104  ; 0 = first half of cell, 1 = second half

walk_hook:
        movem.l d1-d3/a0-a2,-(a7)
        ; gate: mode 2 (room / B-zoom view) only
        cmpi.w  #2,MODE
        bne     wh_orig
        ; Buc's draw record index -> record pointer
        move.w  BUC_REC,d1
        cmpi.w  #$FFFF,d1
        beq     wh_orig
        cmpi.w  #56,d1
        bcc     wh_orig
        mulu.w  #12,d1
        lea.l   RECBASE,a0
        adda.l  d1,a0            ; a0 = Buc's record pointer
        movea.l 8(a6),a1         ; a1 = record being drawn
        cmpa.l  a0,a1
        bne     wh_orig
        ; gate: cutscene active (Buc script only)
        tst.w   SCRIPT
        beq     wh_orig
        move.l  PTR,d1
        cmpi.l  #$1A228,d1
        blt     wh_orig
        cmpi.l  #$1A390,d1
        bgt     wh_orig
        ; ---- Buc, mode 2, cutscene: apply the half-cell slide ----
        ; template wobble for this group: group = TPLBASE + d0
        ; (d0 = template*36 + phase*8, computed by hero_track)
        lea.l   TPLBASE,a2
        adda.l  d0,a2            ; a2 = &template group
        move.w  4(a2),d1         ; d1 = template dx (wobble)
        move.w  6(a2),d2         ; d2 = template dy (wobble)
        ; half-step from loop_dir: table of (dx,dy) per dir
        move.w  LOOPDIR,d3
        cmpi.w  #3,d3
        bhi     wh_orig          ; garbage dir: no slide (safety)
        lsl.w   #2,d3            ; d3 = dir*4 (byte offset)
        lea.l   half_tab,a0
        adda.l  d3,a0            ; a0 = &half_tab[dir]
        ; new_X = 12(a6) + (walk_half ? half_dx : 0) - template_dx
        move.w  12(a6),d3        ; d3 = base X
        tst.w   WALKHALF
        beq.s   wh_nox
        add.w   (a0),d3          ; + half_dx
wh_nox:
        sub.w   d1,d3            ; - template_dx
        move.w  d3,12(a6)
        ; new_Y = 14(a6) + (walk_half ? half_dy : 0) - template_dy
        move.w  14(a6),d3        ; d3 = base Y
        tst.w   WALKHALF
        beq.s   wh_noy
        add.w   2(a0),d3         ; + half_dy
wh_noy:
        sub.w   d2,d3            ; - template_dy
        move.w  d3,14(a6)
wh_done:
        movem.l (a7)+,d1-d3/a0-a2
        lea.l   TPLBASE,a0       ; displaced instruction
        rts
wh_orig:
        ; d0 unchanged: the original template offset stands
        bra     wh_done

; --- half-step table: (dx, dy) screen px, half the cell step vector.
;     Cell steps (measured): N (+14,-8), E (+14,+8), S (-14,+8),
;     W (-14,-8). Layout: dir-major, [dir], each entry dx,dy.
half_tab:
        ; dir 0 = North, half step (+7,-4)
        dc.w    7,-4
        ; dir 1 = East, half step (+7,+4)
        dc.w    7,4
        ; dir 2 = South, half step (-7,+4)
        dc.w    -7,4
        ; dir 3 = West, half step (-7,-4)
        dc.w    -7,-4
