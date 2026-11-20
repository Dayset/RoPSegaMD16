; interp-fix2.s — zoom-view legs + on-screen + straight walk.
;
; Base: rop-interp-fix.rom (MD5 44353892c7a006300bfae2535ad6eaf8) — flat
; checkerboard (mode 2), feet fix, subcell template override, pacing gate
; (1 cell / 4 ticks), interpolation slide (room-relative, in hero_track),
; one-step camera delay (step-mode camera writes in leader_spawn).
; One fix only: make the zoom-view (mode 2) walk animate, stay on-screen,
; and walk straight.
;
; DIAGNOSIS (static; see .scratch-interp-fix2/REPORT.md for the full read):
; 1. DEAD LEGS — the root cause. Record+$A selects the figure-draw
;    routine in map_chunk_pos (jump table at $01BE86): +$A=0 -> hero_track
;    ($0231D8), +$A=1 -> map_promote_record ($02343A), +$A=2 ->
;    map_tile_at_offset, +$A=3 -> map_animated_tile. The interp/subcell
;    hooks live ONLY in hero_track ($023202). Buc's record+$A = 1
;    (probe-confirmed in the cutscene room, rec10 = 1; his +0x06 is the
;    same on foot in any room, so +$A = 1 in room 30 too), so Buc is
;    drawn via map_promote_record, NOT hero_track. map_promote_record
;    reads the RECORD's own template — Buc's record template in the zoom
;    view is the static template 6 (the record in RAM is never modified
;    by the hooks, which only override d0 inside hero_track) — so the
;    image never cycles and the legs don't move. In the cutscene his
;    record IS a walk template (38), so map_promote_record cycles the
;    image per phase and the legs move. This also explains every earlier
;    "no subcell movement" playtest (subcell, pacing, interp ROMs): the
;    hero_track hooks never fired for Buc in the zoom view.
; 2. OFF-SCREEN / ZIGZAG — the camera delay is fundamentally flawed for
;    the room. It hooks ONLY the step-mode camera writes in leader_spawn
;    ($01C2D8/$01C300). But in the room, grid+$C == 0 (table_init_b sets
;    grid+$C = 0 for the room grids $FFB09C/$FFB0AC, 1 for the overworld
;    $FFB08C), so world_reposition_leader takes the L0251EE path and
;    calls leader_spawn(mode 6) — the ABSOLUTE set — on every step,
;    which writes the camera at $01C242/$01C264 (NOT hooked) and does
;    NOT clear PEND_VALID. The step-mode hooks fire only unpredictably
;    (via the $0253F2 leader_spawn($a(a6)) call in the same path, and
;    other step-mode callers), and when they do they apply a STALE
;    pending camera from a different step/direction — so the camera
;    jumps to the wrong cell (Buc off-screen) and the offset direction
;    flips (zigzag). The delay is also per-call, not per-step, so the
;    X and Y hooks can desync (X delayed, Y immediate) on a turn.
;    The room camera does NOT need a delay at all: world_reposition_leader
;    only moves it when Buc is 3+ cells from the camera centre
;    (L025294: |dX|>=3 or |dY|>=3, else the target = the current
;    camera). That 3-cell dead zone is the original game's behaviour —
;    the camera stays put while Buc walks within 3 cells, so the slide
;    IS visible on screen without any delay, and the camera follows
;    him (snapping at 3 cells) exactly as in the original ROM.
;
; THE FIX (three byte changes, one fix):
; A. Hook map_promote_record's template computation at $023480:
;        lea.l $197B0,a0        (41F9 000197B0)
;     -> jsr $FDA00.l           (4EB9 000FDA00)
;    This routes map_promote_record through the EXISTING interp blob at
;    $FDA00 (unchanged). The blob ends with the displaced
;    "lea.l TPLBASE,a0; rts", which is exactly what both hook sites
;    need, and the frame layout matches hero_track (record 8(a6),
;    X 12(a6)/$C(a6), Y 14(a6)/$E(a6), heightOff 16(a6)/$10(a6);
;    template offset in d0; d4 dead after the hook; a3 set after the
;    hook; blob saves/restores d1-d3/a0-a2, never touches d4/d5/a3/a6).
;    The blob gates on mode 2 + Buc's record, so non-Buc figures pass
;    through with d0 unchanged. The slide is gated off while a script
;    runs ($FF0110 != 0), so the cutscene keeps its own walk template +
;    wobble exactly as before. This fixes the legs (walk template 36+dir
;    cycles per phase), the slide (position interpolates old -> new
;    over phases 0-3), and the figure zigzag (smooth direction changes).
;    The hero_track hook at $023202 is kept intact (harmless; hero_track
;    never runs for Buc in the zoom view, and it still serves any
;    +$A=0 figure).
; B. Revert the camera-delay step-mode hooks to the original moves:
;        $01C2D8: jsr $FDE00    (4EB9 000FDE00)
;               -> move.w d0,$FF0E8E.l  (33C0 00FF0E8E)
;        $01C300: jsr $FDE3A    (4EB9 000FDE3A)
;               -> move.w d0,$FF0E90.l  (33C0 00FF0E90)
;    This removes the flawed delay. The camera returns to the original
;    mode-6 behaviour (3-cell dead zone + clamp), which keeps Buc
;    on-screen and the walk straight. The overworld is unchanged (the
;    hooks took the immediate path in mode 1; the original moves are
;    the immediate path). The cutscene is unchanged (the hooks took the
;    immediate path while a script ran; the original moves are the
;    immediate path, and the cutscene camera moves via mode 6 anyway).
; C. Restore the camdelay blob region $FDE00-$FDE7B (124 bytes) to 0xFF
;    padding. The blob is now unreferenced (both hook sites reverted);
;    restoring it to padding keeps the ROM clean. It sits above the
;    runtime checksum range, so this does not affect the runtime sum.
;
; No new code is assembled here (the interp blob is reused verbatim);
; build.py applies these byte changes and fixes both checksums.
; The flat / checkerboard, feet fix, subcell override, pacing gate,
; and interp slide are byte-identical to the base. Big world stays
; textured. Cell rate is unchanged (1 cell / 4 ticks, pacing gate);
; restoring original walk speed is a separate pacing decision
; (Dayset's call). The room still jumps once per cell at the commit
; (and the camera snaps at 3 cells) — fully smoothing the world shift
; needs a fractional (smooth-scrolling) camera, the big rework, NOT
; this fix.
;
; Changed bytes (vs rop-interp-fix.rom):
;   $023480-$023485  jsr $FDA00.l (map_promote_record hook)
;   $01C2D8-$01C2DD  move.w d0,$FF0E8E.l (revert cam X hook)
;   $01C300-$01C305  move.w d0,$FF0E90.l (revert cam Y hook)
;   $FDE00-$FDE7B    0xFF padding (camdelay blob removed)
;   $00018E-$00018F  header checksum (fix-all)
;   $0FD098-$0FD09B  runtime immediate (fix-all)
