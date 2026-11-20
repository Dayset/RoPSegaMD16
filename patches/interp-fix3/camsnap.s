; camsnap.s — per-axis camera snap in world_reposition_leader's room path.
;
; Base: rop-interp-fix2.rom (MD5 30233662e411ecf0046ffc43c734c971) — flat
; checkerboard (mode 2), feet fix, subcell template override, pacing gate
; (1 cell / 4 ticks), interpolation slide (room-relative, via
; map_promote_record), camera mode-6 with a 3-cell dead zone.
; One fix only (half of interp-fix3): stop the camera yoinking on a
; direction change. Hook site: $02529C inside world_reposition_leader's
; L025294 dead-zone block (sub.w $FF0E8E,d0, 6 bytes) -> jsr $FDE00.l.
;
; DIAGNOSIS (static; full read in .scratch-interp-fix3/REPORT.md):
; - The room camera is mode-6 (absolute set) with a 3-cell dead zone:
;   world_reposition_leader ($02513E, combat_move_unit's epilogue) takes
;   the L0251EE path when grid+$C == 0 (room), and the L025294 block
;   computes |dX| = |BucX - camX| and |dY| = |BucY - camY|. If EITHER is
;   >= 3 it jumps to the clamp ($025300) leaving the target as Buc's
;   cell on BOTH axes; if both are < 3 it sets the target to the current
;   camera on both axes. The snap is all-or-nothing per axis pair.
; - When Buc turns (e.g. east -> north), his X offset from the camera
;   centre is whatever it drifted to while walking east (0, 1 or 2 —
;   the camera re-centres only every 3rd east step), and his Y offset
;   grows 1, 2, 3 as he walks north. The moment |dY| hits 3 the camera
;   snaps to Buc's cell on BOTH axes: (Xoffset, 3) — a DIAGONAL jump of
;   1-2 cells sideways plus 3 cells up. That diagonal snap is the
;   "yoink" Dayset sees on a direction change (it fires ~2/3 of turns,
;   whenever the X offset is 1 or 2 at the turn).
; - The fix: make the snap PER-AXIS. If |dX| < 3 keep targetX = camX;
;   if |dY| < 3 keep targetY = camY; only the axis that crossed the
;   dead zone moves to Buc's cell. A north turn then moves the camera
;   purely north (0, 3); the sideways offset stays put until Buc
;   actually drifts 3 cells sideways. The camera still follows Buc
;   exactly as in the original ROM (same 3-cell dead zone, same clamp,
;   same mode-6 set) — it just never jumps diagonally.
; - The blob is gated to mode 2 AND no script ($FF0110 == 0), so the
;   cutscene keeps the original all-or-nothing snap (unchanged). The
;   L025294 block is only reached on the room path (grid+$C == 0), so
;   the overworld is untouched by construction.
; - The blob jumps to $025300 (the clamp) after setting the per-axis
;   target, bypassing the rest of the dead-zone logic. The clamp and
;   the leader_spawn(mode 6, targetX, targetY) call at $025394 then run
;   exactly as before, on the per-axis target. -$8(a6) stays 0 (it was
;   cleared at $025294 and nothing here sets it), so the extra
;   leader_spawn call at $0253F2 is skipped, as in the original path.
; - Buc can never go off-screen from this: the non-snapped axis keeps
;   him within 2 cells of the camera centre (the dead zone is 3), and
;   the snapped axis centres him. The room is ~36x23 cells; he stays
;   well inside the window.
;
; Inputs (a6 is world_reposition_leader's frame pointer; the jsr does
; not change it): -$6(a6) = BucX (target X), -$4(a6) = BucY (target Y),
; $FF0E8E/$FF0E90 = current camera. The blob writes -$6/-$4 (the
; target) and jumps to $025300, or (gated out) executes the displaced
; sub.w and returns to $0252A2.
; Registers: saves/restores d0 (movem); a6 untouched; the clamp reloads
; d0/d1/a0 from memory, so nothing else needs preserving.
; Exits: jmp $025300.l (jsr hook, return address discarded) on the
; per-axis path; rts (jsr hook) on the gated-out path. Never jmp on a
; path that must return — the jmp here is the deliberate bypass, the
; same pattern the pacing gate uses for its skip path.
;
; Blob at $FDE00 (the camdelay region, restored to 0xFF padding by
; interp-fix2; 124 bytes $FDE00-$FDE7B, this blob is ~98 bytes).
; RAM used: none (reads $FF00AE/$FF0110/$FF0E8E/$FF0E90 only).

        org     $FDE00

; --- game addresses ---
MODE     equ     $FF00AE  ; world/room mode flag (1 = overworld, 2 = room)
SCRIPT   equ     $FF0110  ; $FF0110 != 0 while an event script runs
CAMX     equ     $FF0E8E  ; camera X (cell)
CAMY     equ     $FF0E90  ; camera Y (cell)

cam_snap:
        movem.l d0,-(a7)
        ; gate: mode 2 only, no script (cutscene keeps the original snap)
        cmpi.w  #2,MODE
        bne     cs_orig
        tst.w   SCRIPT
        bne     cs_orig
        ; ---- per-axis target ----
        ; X: if |BucX - camX| < 3, targetX = camX; else keep BucX
        move.w  -$6(a6),d0            ; d0 = BucX (target X)
        sub.w   CAMX,d0               ; d0 = BucX - camX
        bpl     cs_xpos
        neg.w   d0                    ; d0 = |BucX - camX|
cs_xpos:
        cmpi.w  #3,d0
        bge     cs_xmove              ; |dX| >= 3: keep BucX
        move.w  CAMX,-$6(a6)          ; |dX| < 3: targetX = camX
cs_xmove:
        ; Y: if |BucY - camY| < 3, targetY = camY; else keep BucY
        move.w  -$4(a6),d0            ; d0 = BucY (target Y)
        sub.w   CAMY,d0               ; d0 = BucY - camY
        bpl     cs_ypos
        neg.w   d0                    ; d0 = |BucY - camY|
cs_ypos:
        cmpi.w  #3,d0
        bge     cs_ymove              ; |dY| >= 3: keep BucY
        move.w  CAMY,-$4(a6)          ; |dY| < 3: targetY = camY
cs_ymove:
        movem.l (a7)+,d0
        addq.l  #$4,a7                ; discard the jsr return address
        jmp     $025300.l             ; go to the clamp
cs_orig:
        movem.l (a7)+,d0
        sub.w   CAMX,d0               ; displaced instruction
        rts                           ; return to $0252A2
