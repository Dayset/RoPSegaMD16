; pace.s — pacing gate v2: a turn always goes through.
;
; Base: rop-interp-fix2.rom (MD5 30233662e411ecf0046ffc43c734c971) — flat
; checkerboard (mode 2), feet fix, subcell template override, pacing gate
; (1 cell / 4 ticks), interpolation slide (room-relative, via
; map_promote_record), camera mode-6 with a 3-cell dead zone.
; One fix only (half of interp-fix3): make a single short press rotate
; Buc's face after a stop. The hook site ($0228CC, jsr $FD900.l) already
; points here; this blob REPLACES the v1 pacing blob in place (same
; address $FD900, grown from 34 to ~58 bytes into the free 0xFF padding
; at $FD922+). No hook-site change for this half.
;
; DIAGNOSIS (static; full read in .scratch-interp-fix3/REPORT.md):
; - Path A ($022826, mode 2) pops the leader's queued direction every
;   tick and calls combat_move_unit, which commits the cell AND updates
;   Buc's heading (+0x0A, $FF02F2) to the new direction — even when the
;   step is blocked (the heading write at $024D76 is in the shared
;   epilogue, reached via the d4==0 skip as well as the step path).
;   So a tap in a NEW direction turns Buc's face in one press — IF the
;   move reaches combat_move_unit.
; - The v1 pacing gate ($FD900) discards ANY popped direction when
;   grid+$A != 0 (phases 1-3), BEFORE the dir==4 check. A brief tap
;   lands on phase 0 only 1 time in 4, so a single tap to turn is
;   discarded ~75% of the time; Dayset needs 3-4 taps to rotate the
;   face. The queue is drained by the pop, so a discarded tap is LOST
;   (it does not stay queued).
; - The fix: if the popped direction (-$E(a6)) differs from Buc's
;   heading ($FF02F2), the move goes through immediately (turn), no
;   phase check. Same-direction moves keep the v1 phase gate (the cell
;   still commits once per 4 ticks while holding a direction, so the
;   walk pace and the slide are unchanged). The dir==4 stop sentinel
;   still works: dir 4 != any heading 0-3, so it takes the allow path,
;   the displaced cmpi.w sets the flags, and Path A's beq skips the
;   move exactly as before.
; - Known minor artifact (noted, not hidden): a turn commits the cell
;   mid-phase (not on the phase 3->0 wrap), so the interp slide starts
;   at that phase's offset (e.g. a turn at phase 2 starts halfway) —
;   Buc jumps about half a cell, then slides the rest. The legs still
;   cycle and the face turns in one press; the slide itself is not
;   re-timed (that would mean touching the interp blob, out of scope).
;
; Registers: saves/restores d0-d1/a0 (movem); a6 untouched (it is
; combat_turn_run's frame pointer; -$E(a6) is the popped direction).
; Exits with rts (jsr hook) on the allow path, or discards the return
; address and jmps to $022960 (Path A's standard skip exit) on the
; gated path — exactly as the v1 blob did.
;
; Blob at $FD900 (0xFF padding in the base ROM past the v1 blob's end;
; above the runtime checksum range $000000-$FD07B, so it does not affect
; the runtime sum, but the blob bytes do, and the header checksum
; covers the whole ROM — both are fixed by checksum.py fix-all).
; RAM used: none (reads $FF02F2 and grid+$A only, writes nothing).

        org     $FD900

; --- game addresses ---
MODE     equ     $FF00AE  ; world/room mode flag (1 = overworld, 2 = room)
GRIDBASE equ     $FFA7FC  ; ram_map_grid_base (pointer); +$A = grid+$A phase
BUC_DIR  equ     $FF02F2  ; char 1 (Buc) +0x0A: heading (0-3)

pace_gate:
        movem.l d0-d1/a0,-(a7)
        ; ---- turn check: a new direction goes through immediately ----
        move.w  -$E(a6),d0            ; d0 = popped direction (0-4)
        move.w  BUC_DIR,d1            ; d1 = Buc's heading
        andi.w  #3,d1                 ; mask heading to 0-3 (safety)
        cmp.w   d1,d0
        bne     pace_allow            ; different direction = turn: allow
        ; ---- same direction: the original phase gate ----
        movea.l GRIDBASE,a0
        tst.w   $A(a0)                ; phase (grid+$A, 0-3)
        bne     pace_skip             ; phase != 0: discard
pace_allow:
        movem.l (a7)+,d0-d1/a0
        cmpi.w  #$4,-$E(a6)           ; displaced instruction
        rts
pace_skip:
        movem.l (a7)+,d0-d1/a0
        addq.l  #$4,a7                ; discard the jsr return address
        jmp     $022960.l             ; Path A block's standard skip exit
