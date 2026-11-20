; walk-frames-fix: route the Y-shift hook through map_promote_record.
;
; Problem: the walk-frames ROM's Y-shift hook is in hero_track
; ($023202, blob at $FDA00), but Buc is drawn via map_promote_record,
; NOT hero_track. Record+$A selects the figure-draw routine in
; map_chunk_pos (jump table $01BE86): +$A=0 -> hero_track, +$A=1 ->
; map_promote_record, and Buc's record+$A = 1 (probe-confirmed in the
; cutscene room, rec10 = 1 in every record). So the Y-shift hook never
; fires for Buc. The frame doubling (one cell per 8 ticks, in the loop
; driver blob at $FD800) DOES work, but the smaller Y shift
; (8,12,16,20,24) does NOT happen — Buc still jumps by 8 px per step.
;
; Fix: hook map_promote_record at $023480 (lea.l $197B0,a0) -> jsr to
; the EXISTING walk-hook blob at $FDA00. The blob ends with the
; displaced lea.l $197B0,a0 + rts (at $FDAAA), which is exactly what
; both hook sites need, and the frame layout matches hero_track
; (record 8(a6), X 12(a6), Y 14(a6), heightOff 16(a6), d0 template
; offset — d0 is computed at $023462-$02347E, before the hook; a3 is
; set AFTER the hook at $023486; X/Y are read AFTER the hook at
; $02349C/$0234AA). The blob saves/restores d1-d3/a0-a2, preserves d0,
; never touches d4/d5/a3/a6 — safe here. The hero_track hook at
; $023202 is kept intact (harmless).
;
; This file assembles to the 6-byte patch (jsr $FDA00.l). The build
; script verifies it equals 4EB9 000FDA00, then writes it at $023480.

        jsr     $FDA00.l
