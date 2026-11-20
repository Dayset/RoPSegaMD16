; walk-unused-frames patch: cutscene Y fix (disable the Y-shift hook,
; restore the 4-tick step cadence). Base: rop-walk-frames-fix.rom
; (MD5 9ba279759436b96a732d11d9a3f6be0d).
;
; Dayset's correction: the unused poses (offsets 4, 5, 10, 11, 12, 13)
; are NOT walk frames — they are combat moves / a cast. They are
; used by templates 16-27 (the combat/cast templates), so they are
; not unused at all, and they must NOT be fitted into the walk
; routine. The walk templates 36-55 already use every walk-frame
; pose (0, 1, 6, 7, 8, 9, 14, 15). There are no unused walk-frame
; poses. The unused-poses idea is dropped; this patch is the
; cutscene Y fix only.
;
; THE CUTSCENE Y PROBLEM (Dayset's playtest of the fix ROM):
; "cutscene Y is completely off. He is doing 2 steps and then
; waiting for longer than usual and jumps screen, and repeat.
; Like he is waiting and running after 2 cells."
; Causes (diagnosed statically):
;  1. The Y-shift hook draws Buc half a cell ahead of his record
;     cell during the second half of each 8-tick cell, while the
;     camera follows the record cell. At a turn (loop_dir changes)
;     the half-step direction flips, so Buc's drawn position jumps
;     back/forward; when the camera re-centres, the screen jumps.
;     The drawn position is decoupled from the camera.
;  2. The frame doubling (one cell per 8 ticks) makes Buc slow and
;     makes him stand still longer after 2 steps; at a turn there
;     is an extra 4-tick delay (the non-step call), so the pause
;     after a short leg reads as "waiting for longer than usual".
; The zoom walk is very good on this ROM and does not use the loop
; driver or the Y-shift hook (both are gated to the cutscene), so
; this fix cannot break it.
;
; THE FIX (three byte changes, no new blob):
;  1. $023202 (hero_track): jsr $FDA00.l -> lea.l $197B0,a0
;     (restore the original figure-draw entry; the Y-shift hook
;     no longer fires from hero_track).
;  2. $023480 (map_promote_record): jsr $FDA00.l -> lea.l $197B0,a0
;     (restore the original figure-draw entry; the Y-shift hook
;     no longer fires from map_promote_record, the routine Buc
;     is actually drawn through).
;     The $FDA00 walk-hook blob becomes dead code (unreferenced).
;     It is left in place (0xFF padding region, outside the runtime
;     checksum range) — harmless, and the patch stays reversible.
;  3. $FD866 (loop_drive): beq.b $FD86A -> bra.b $FD88A
;     (always step Buc on every sys_event_run call; the .half
;     non-step block becomes dead code, walk_half stays 0).
;     This restores the original cutscene-loop cadence: one cell
;     per 4 ticks (the pace Dayset already saw working on the
;     cutscene-loop ROM), instead of one cell per 8 ticks.
; After the fix the cutscene walk is the cutscene-loop walk:
; Buc walks the loop S,E,N,W, turning when blocked or after 20
; steps, at 4 ticks/cell, with no Y shift. The world shift is
; still jumpy (integer-cell camera) — that is the big rework,
; not this fix. The flat, feet fix, loop driver (except the
; cadence), and cutscene dialog/script are otherwise unchanged.
; The big world stays textured.
;
; Byte encodings (verified with vasm before building):
;   lea.l $197B0,a0 = 41F9 000197B0
;   bra.b $FD88A from $FD866 = 60 22
;     (target $FD88A, PC after = $FD868, disp = $22)

        org     $023202
        lea.l   $197B0,a0       ; was jsr $FDA00.l (hero_track hook)
        org     $023480
        lea.l   $197B0,a0       ; was jsr $FDA00.l (map_promote hook)
        org     $FD866
        bra.b   $FD88A          ; was beq.b $FD86A (non-step call)
