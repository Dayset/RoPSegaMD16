; interp.s — smooth slide for the leader figure (Buc, char 1) in the
; B-zoom view (mode 2, the room).
;
; Base: rop-pacing.rom (MD5 6abeec0bea66365f223c75760983df8b) — flat
; checkerboard only on mode 2, feet fix (figures deferred to a post-pass),
; subcell template override (hero_track hook at $023202 -> $FD800),
; pacing gate (cell commits once per 4 ticks, phase 3->0 wrap).
; One fix only: make Buc's DRAWN position slide smoothly across a cell
; over the 4 phases instead of standing then teleporting, and keep the
; feet stepping (the walk-cycle image).
;
; DIAGNOSIS (static + two RAM reads from the slot_0 save state):
; - The cutscene walk is smooth because the walker uses template 38
;   (image cycles per phase = legs step; dx/dy wobble = sway) AND the
;   room jumps one cell per 4 ticks (the world scrolls past a centred
;   figure). The record's cell commits on the phase 3->0 wrap; the
;   template offsets are a sway, not a slide.
; - The overworld walk has the same cadence (1 cell per 4 ticks, pacing
;   gate) and the same walk template (subcell hook), so the image cycles
;   (Dayset: "cape moving") — but the figure does NOT translate: it sits
;   at the room centre (the camera follows the committed cell) wobbling
;   a few px, then the room jumps. The feet look "dead" because the feet
;   never travel across the ground; the jump reads as a teleport.
; - A true on-screen slide is impossible with this renderer (tile-based
;   room in the window plane; the camera is an integer grid cell, so the
;   room can only jump whole cells). The achievable slide is the
;   ROOM-RELATIVE one: the figure's drawn cell interpolates from the old
;   cell to the new cell over phases 0-3 (0, 1/4, 1/2, 3/4, then the
;   commit). Relative to the room the motion is continuous and monotonic;
;   the whole-screen jump at the commit is the room scrolling, exactly
;   as in the cutscene.
; - Screen step per cell (measured from the map_chunk_pos tables
;   $FFAE7A/$FFAF42 in the live RAM): East (+14,+8), South (-14,+8),
;   North (+14,-8), West (-14,-8). Uniform across the window.
; - Buc's base tile is 384 (RAM read: char 1 record 0, word0=384,
;   template 6 at rest); the cutscene walk frames are 384+0/6/1/7, the
;   same tiles the subcell walk template (36+dir) selects. So the image
;   cycle is already the right walk cycle; only the position was missing.
; - The walk template's dx/dy wobble (+-6 px) is LARGER than one slide
;   step (~3.5 px/phase), so leaving it on top of the slide would make
;   the motion non-monotonic (jerk back and forth). The hook therefore
;   SUBTRACTS the template's dx/dy for the current phase, so the net
;   drawn position is exactly the slide. The image still cycles (legs
;   step); the position is purely the slide.
;
; WHAT THIS HOOK DOES (extends the subcell hook; the subcell template
; override logic is kept verbatim):
; - Hook site: hero_track $023202 (lea.l $197B0,a0) -> jsr interp_hook.
;   The hook site is repointed from $FD800 to $FDA00. The $FD800 blob
;   (subcell) is left in place, unreferenced; this blob contains its
;   logic verbatim plus the slide.
; - Gates: mode 2 only, Buc's draw record only (char 1, $FF02EC).
; - Latch: as the subcell hook (ON when Buc's cell changes, OFF at the
;   next phase-0 render with no change), PLUS it remembers the PREVIOUS
;   cell (OLD_X/OLD_Y) so the step direction is known.
; - Template: walk template 36+dir (dir = Buc heading, as before) in d0,
;   so the image cycles per phase (legs step). The record in RAM is never
;   modified, so the $022F52 record stepper still sees the original
;   static template and never moves the record on its own.
; - Slide: ONLY when no event script is running ($FF0110 == 0). During
;   a cutscene the figure keeps the walk template + wobble exactly as
;   before (the cutscene is already smooth; this fix does not touch it).
;   The step direction comes from the cell delta (new - old). If it is
;   not a single-cell step, no slide is applied (safe fallback: template
;   only). The slide offset for [dir][phase] is a table in this blob
;   (measured step vectors, quarter steps, integer px). The hook writes
;   the adjusted X/Y to 12(a6)/14(a6) (hero_track's X/Y args) BEFORE
;   hero_track reads them, with the template wobble subtracted, so the
;   net drawn position is exactly the slide.
; - Registers: saves/restores d1-d3/a0-a2 (movem); d0 is the template
;   offset for hero_track (preserved); a6 untouched; stack balanced.
;   Exits with rts (jsr hook), never jmp.
;
; Blob at $FDA00 (0xFF padding in the base ROM; above the runtime
; checksum range $000000-$FD07B, so it does not affect the runtime sum,
; but the hook-site change at $023202 does, and the header checksum
; covers the whole ROM — both are fixed by checksum.py fix-all).
; RAM used: $FFD000-$FFD00E (subcell latch $FFD000-$FFD006 plus
; OLD_X/OLD_Y $FFD008/$FFD00A and SLIDE scratch $FFD00C/$FFD00E).
; No collision with the feet-fix list ($FFD800+) or the pacing blob.

        org     $FDA00

; --- RAM state (free scratch; not game variables) ---
LATCH_X  equ     $FFD000  ; Buc cell X at last observed step (subcell)
LATCH_Y  equ     $FFD002  ; Buc cell Y at last observed step
LATCH_ON equ     $FFD004  ; 1 = a step is in progress (subcell)
LATCH_IN equ     $FFD006  ; 1 = latch initialised (subcell)
OLD_X    equ     $FFD008  ; Buc cell X before the last step (interp)
OLD_Y    equ     $FFD00A  ; Buc cell Y before the last step (interp)
SLIDE_DX equ     $FFD00C  ; slide offset dx, scratch (interp)
SLIDE_DY equ     $FFD00E  ; slide offset dy, scratch (interp)

; --- game addresses ---
MODE     equ     $FF00AE  ; world/room mode flag (1 = overworld, 2 = room)
SCRIPT   equ     $FF0110  ; $FF0110 != 0 while an event script runs
BUC_REC  equ     $FF02EC  ; char 1 (Buc) +0x04: draw record index
BUC_DIR  equ     $FF02F2  ; char 1 (Buc) +0x0A: heading (0-3)
BUC_X    equ     $FF02F4  ; char 1 (Buc) +0x0C: grid X
BUC_Y    equ     $FF02F6  ; char 1 (Buc) +0x0E: grid Y
GRIDBASE equ     $FFA7FC  ; ram_map_grid_base (pointer); +$A = grid+$A phase
RECBASE  equ     $FFB0CC  ; draw records (12 bytes each)
TPLBASE  equ     $197B0   ; template table (36 bytes per template)

interp_hook:
        movem.l d1-d3/a0-a2,-(a7)
        ; gate: mode 2 (room / B-zoom view) only
        cmpi.w  #2,MODE
        bne     ip_orig
        ; Buc's draw record index -> record pointer
        move.w  BUC_REC,d1
        cmpi.w  #$FFFF,d1
        beq     ip_orig
        cmpi.w  #56,d1
        bcc     ip_orig
        mulu.w  #12,d1
        lea.l   RECBASE,a0
        adda.l  d1,a0            ; a0 = Buc's record pointer
        movea.l 8(a6),a1         ; a1 = record being drawn
        cmpa.l  a0,a1
        bne     ip_orig
        ; ---- Buc, mode 2: movement latch ----
        ; current phase (grid+$A, 0-3)
        movea.l GRIDBASE,a0
        move.w  $A(a0),d1        ; d1 = phase
        move.w  d1,d2            ; d2 = phase (kept)
        ; first call: initialise the latch cell (old == new: no step yet)
        tst.w   LATCH_IN
        bne     ip_have
        move.w  #1,LATCH_IN
        move.w  BUC_X,LATCH_X
        move.w  BUC_Y,LATCH_Y
        move.w  BUC_X,OLD_X
        move.w  BUC_Y,OLD_Y
        bra     ip_orig
ip_have:
        ; did Buc's cell change since the last step?
        move.w  BUC_X,d1         ; d1 = Buc X
        cmp.w   LATCH_X,d1
        bne     ip_changed
        move.w  BUC_Y,d1         ; d1 = Buc Y
        cmp.w   LATCH_Y,d1
        beq     ip_nochange
ip_changed:
        ; cell changed: remember the old cell, store the new cell, latch on
        move.w  LATCH_X,OLD_X
        move.w  LATCH_Y,OLD_Y
        move.w  #1,LATCH_ON
        move.w  BUC_X,LATCH_X
        move.w  BUC_Y,LATCH_Y
        bra     ip_apply
ip_nochange:
        ; no cell change: at phase 0 the step is over, latch off
        tst.w   d2
        bne     ip_apply
        clr.w   LATCH_ON
ip_apply:
        tst.w   LATCH_ON
        beq     ip_orig
        ; ---- apply the walk template (subcell behaviour, verbatim) ----
        ; dir = Buc heading (0-3); walk template = 36 + dir
        move.w  BUC_DIR,d1
        andi.w  #3,d1
        addi.w  #36,d1
        mulu.w  #36,d1           ; d1 = template*36
        move.w  d2,d0            ; d0 = phase
        lsl.w   #3,d0            ; d0 = phase*8
        add.w   d1,d0            ; d0 = template*36 + phase*8
        ; ---- slide: only when no script is running ----
        ; (during a cutscene the figure keeps the walk template + wobble
        ;  exactly as before; the slide is for the overworld walk only)
        tst.w   SCRIPT
        bne     ip_done
        ; step direction from the cell delta (new - old)
        move.w  LATCH_X,d1
        sub.w   OLD_X,d1         ; d1 = dx_grid
        move.w  LATCH_Y,d3
        sub.w   OLD_Y,d3         ; d3 = dy_grid
        ; (dx,dy) -> dir 0=N,1=E,2=S,3=W; else not a unit step: no slide
        tst.w   d3
        bne     ip_sdy
        ; dy == 0: E (dx=1) or W (dx=-1)
        cmpi.w  #1,d1
        beq     ip_s1
        cmpi.w  #-1,d1
        beq     ip_s3
        bra     ip_done
ip_sdy:
        ; dy != 0: dx must be 0; N (dy=-1) or S (dy=1)
        tst.w   d1
        bne     ip_done
        cmpi.w  #-1,d3
        beq     ip_s0
        cmpi.w  #1,d3
        beq     ip_s2
        bra     ip_done
ip_s0:
        moveq   #0,d1
        bra     ip_sgo
ip_s1:
        moveq   #1,d1
        bra     ip_sgo
ip_s2:
        moveq   #2,d1
        bra     ip_sgo
ip_s3:
        moveq   #3,d1
ip_sgo:
        ; d1 = dir (0-3), d2 = phase (0-3), d0 = template offset
        move.l  d0,-(a7)         ; save template offset
        ; slide offset from the table: (dir*4 + phase) entries of 2 words
        lsl.w   #2,d1            ; d1 = dir*4
        add.w   d2,d1            ; d1 = dir*4 + phase
        lsl.w   #2,d1            ; d1 = byte offset
        lea.l   slide_tab,a0
        adda.l  d1,a0
        move.w  (a0)+,SLIDE_DX   ; slide dx
        move.w  (a0),SLIDE_DY    ; slide dy
        ; template wobble for this group: group = TPLBASE + template offset
        move.l  (a7),a0          ; a0 = template offset (peek)
        lea.l   TPLBASE,a2
        adda.l  a0,a2            ; a2 = &template group
        move.w  4(a2),d0         ; d0 = template dx (scratch; offset on stack)
        ; new_X = 12(a6) + slide_dx - template_dx
        move.w  12(a6),d2        ; d2 = base X (phase no longer needed)
        add.w   SLIDE_DX,d2
        sub.w   d0,d2
        move.w  d2,12(a6)
        move.w  6(a2),d0         ; d0 = template dy
        ; new_Y = 14(a6) + slide_dy - template_dy
        move.w  14(a6),d2        ; d2 = base Y
        add.w   SLIDE_DY,d2
        sub.w   d0,d2
        move.w  d2,14(a6)
        move.l  (a7)+,d0         ; restore template offset
ip_done:
        movem.l (a7)+,d1-d3/a0-a2
        lea.l   TPLBASE,a0       ; displaced instruction
        rts
ip_orig:
        ; d0 unchanged: the original template offset stands
        bra     ip_done

; --- slide offset table: (dx, dy) screen px, relative to the base X/Y
;     (the NEW cell's screen position). The figure is drawn at the old
;     cell at phase 0 and slides toward the new cell: phase 0 = -step,
;     phase 1 = -step + step/4, phase 2 = -step + step/2,
;     phase 3 = -step + 3*step/4. Step vectors (measured): N (+14,-8),
;     E (+14,+8), S (-14,+8), W (-14,-8). Integer px (divs truncates
;     toward zero); a 1 px rounding is invisible.
;     Layout: dir-major, [dir][phase], each entry dx,dy.
slide_tab:
        ; dir 0 = North, step (+14,-8)
        dc.w    -14,8,  -11,6,  -7,4,  -4,2
        ; dir 1 = East, step (+14,+8)
        dc.w    -14,-8,  -11,-6,  -7,-4,  -4,-2
        ; dir 2 = South, step (-14,+8)
        dc.w    14,-8,  11,-6,  7,-4,  4,-2
        ; dir 3 = West, step (-14,-8)
        dc.w    14,8,  11,6,  7,4,  4,2
