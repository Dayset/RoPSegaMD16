; pacing.s — pacing gate for the leader figure's (Buc, char 1) movement in
; the B-zoom view (mode 2, the room).
;
; Hook: combat_turn_run Path A $0228CC (cmpi.w #$4,-$e(a6)) -> jsr pace_gate.
; Path A pops the leader's queued direction and calls combat_move_unit,
; which commits the cell (writes char X/Y at $024CE8-$024D64). The move
; block runs every tick in the room because grid+$8 == 1 for the room
; grids ($FFB09C, $FFB0AC), so $FF0094 = phase mod 1 = 0 always, and the
; $022790 gate never fires. The cutscene is smooth because sys_event_run
; runs only at grid+$A == 0 ($022764 gate) and the movement block is
; skipped while a script runs ($FF0110 != 0, $0227C6).
;
; What it does:
;   - Only in the leader-move block of Path A (mode 2, room): if the
;     grid+$A phase (0-3, writer world_tick $02155E) is not 0, discard
;     the jsr return address and jump to $022960, the block's standard
;     skip exit (same as the dir==4 skip). The direction was already
;     popped by queue_pop, so the queue still drains every tick (no
;     accumulation, no direction-change lag); the move itself only
;     happens on phase-0 ticks, so the cell commits once per 4 ticks.
;   - On phase 0, execute the displaced cmpi.w and return normally, so
;     the dir==4 check and the move proceed exactly as before.
;   - The cutscene is unaffected (the movement block is skipped while
;     $FF0110 != 0, so this hook never fires during a script). The
;     overworld is unaffected (Path A only runs in mode 2).
;
; Blob at $FD900 (0xFF padding in the base ROM; above the runtime-checksum
; range $000000-$FD07B, so it does not affect the runtime sum, but the
; hook-site change at $0228CC does, and the header checksum covers the
; whole ROM — both are fixed by checksum.py fix-all).

        org     $FD900

; --- game addresses ---
GRIDBASE equ     $FFA7FC  ; ram_map_grid_base (pointer); +$A = grid+$A phase
SKIPEXIT equ     $022960  ; Path A block exit (bra.b L022972)

pace_gate:
        movem.l a0,-(a7)          ; a0 is dead here (reloaded at $0228B2),
                                  ; saved anyway so the hook clobbers nothing
        movea.l GRIDBASE,a0
        tst.w   $A(a0)            ; grid+$A phase (0-3)
        movem.l (a7)+,a0
        bne     pace_skip         ; phase != 0 -> skip the move
        cmpi.w  #$4,-$E(a6)       ; displaced instruction
        rts                       ; back to $0228D2 (beq.w L022960)
pace_skip:
        addq.l  #$4,a7            ; discard the jsr return address
        jmp     SKIPEXIT          ; $022960 (bra.b L022972)
