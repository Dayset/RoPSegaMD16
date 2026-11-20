/*
 * source.s — big-rework proof-of-concept FIX 2 for Rings of Power
 * (Sega Mega Drive). Fixes the PoC (patches/big-rework) per Dayset's
 * 2026-11-13 playtest: the room image went stale / looked small and
 * stuck, and only Buc was visible, because the PoC's redraw gate
 * suppressed EVERY room re-decode after install, so the frozen
 * image never followed the camera and the baked figures never
 * updated. Diagnosis (see .scratch-big-rework-poc-fix2/REPORT.md):
 *   - The diamond is the SAME size as the original (283x169 vs
 *     278x160 game px, same aspect) — it only LOOKS small because
 *     the install blanks the pink decoration/HUD, leaving the
 *     diamond floating on black. The black background is an
 *     accepted side effect (Dayset doesn't mind); this fix does
 *     NOT restore the decoration.
 *   - Only Buc is visible at the save state's camera (7,7) in the
 *     ORIGINAL too: Thalmus (9,17) and the students (20,13)/(19,12)
 *     are outside the 10x10 window (x 2-11, y 2-11). Not a PoC bug
 *     at that camera — but the frozen image made it permanent: even
 *     when the camera moved, the figures never came into view.
 *   - The install can fire late (first redraw_check with $FF0098
 *     set), i.e. at a walked-to camera, so the frozen view need not
 *     be the load camera's view — Dayset's shot shows the big blue
 *     pool, not the (7,7) stone-walls view.
 * Fix (one change only): the gate now re-installs — lets the body
 * run its decode+DMA for the new camera, which updates the Plane B
 * image (redirected room draws + pattern DMA) and re-bakes the
 * figures at their current positions — whenever the camera has
 * moved from the install camera:
 *   - camera unmoved: suppress as before (decode-once holds);
 *   - camera exactly 1 cell away AND the D-pad scroll has caught
 *     up to that move (accumulators equal the expected values):
 *     seamless re-install (new image at scroll 0 == old image at
 *     the scroll extreme), scroll reset to (0,0);
 *   - camera >1 cell away (teleport / fast move / scroll lagged):
 *     re-install with a 1-cell jump (strip streaming, the full
 *     rework, will close that gap; the jump is still half as often
 *     as the original's per-cell jump).
 * The gate runs on every redraw_check (main_loop calls it every
 * iteration), so a 1-cell move that hasn't caught up yet is simply
 * suppressed until the scroll reaches it a few frames later.
 * No strip streaming, no sprites, no tick governor, no decoration
 * restore. Dialogues/panels/menus are untouched (they don't depend
 * on $FF0098). The D-pad scroll, logic and dialogues keep working.
 *
 * Same three trampolines in one blob (at $FD900, in the 0xFF
 * padding past the runtime checksum's summed range $000000-$FD07B):
 *   vbl_entry    — VBlank hook ($1272): per-frame D-pad scroll.
 *   redraw_entry — redraw_check hook ($1B918): Plane B install +
 *                  camera-aware re-decode gate (this fix).
 *   scene_entry  — world_map_draw hook ($12C20): reset the install
 *                  state on every scene setup.
 * Plus the same three static patches applied by build.py:
 *   $12C9A  move.w #$8400,-(sp) -> #$8402   (R4: Plane B $4000)
 *   $12E68  pea $001000.w -> pea $004000.w  (room draw -> Plane B)
 *   $16326  pea $001000.w -> pea $004000.w  (redraw room -> Plane B)
 * R16 is already $01 (planes 64x32) in world_map_draw ($12CDE).
 *
 * State: dead RAM $FF00A0-$FF00C0 (0 refs in disasm/src/rop.s).
 *   A0 magic $9C07 | A2 armed | A6 installed | A8 hAcc | AA vAcc
 *   B0 lastH | B2 lastV | B4 lastLoc | BC installCamX | C0 installCamY
 * $FF00A4 is NOT used (1 ref: tst at $1CF3C). $FF00AC/$FF00AE are
 * live menu fields and are NOT used. $FF00BC/$FF00C0 have 0 refs.
 * Every state word is range-validated on each use; anything out of
 * range re-initialises to safe defaults (no scroll, no suppression)
 * so a stray game write fails safe to original behaviour.
 * installCamX/Y hold the camera ($FF0E8E/$FF0E90) the Plane B image
 * was decoded for; $FFFF = "none yet" (forces a re-install).
 *
 * Scroll (design §5.2, signs double-checked against §3):
 *   screenX = planeX + hScroll; screenY = planeY - vScroll.
 *   Per camera cell: dH = -(dcx-dcy)*14, dV = +(dcx+dcy)*8.
 *   The D-pad drives the same deltas (the leader walks while the
 *   room slides, exactly as if the camera moved): Right (east)
 *   dH -14 / dV +8, Left (west) +14 / -8, Down (south) +14 / +8,
 *   Up (north) -14 / -8 per cell. Per VBlank the accumulators step
 *   dH 16/16 px and dV 9/16 px (8/14 = 0.571 px/fr; 9/16 = 0.5625,
 *   a 1 px shortfall per cell of travel, irrelevant under the
 *   +/-1-cell clamp). Accumulators are 1/16-px fixed point, clamped
 *   to hAcc [-224,224] (+/-14 px), vAcc [-128,128] (+/-8 px).
 *   Load scroll is (0,0): the room draw places the image at plane
 *   (2,0) cells (x0=2 in the $12E50 call), so with the viewport at
 *   screen cols 2-37 the image is already aligned at scroll 0.
 *   (The design's §8.2 (16,0) assumed plane origin (0,0); the
 *   actual draw call uses x0=2, so the load scroll is (0,0).)
 *
 * The VBlank hook only writes $DC16 when the scroll CHANGED, so it
 * emits no VDP traffic while idle, and it writes (0,0,0,0) once
 * when leaving the room. Known limitation (see README): while the
 * PoC is armed, opening the world map fights the map's own scroll
 * writes if the D-pad is held; close the map to resume the demo.
 * A jsr hook MUST exit with rts/jmp-on, never a plain jmp that
 * leaks the return address (proven in #021). The VBlank hook is a
 * jmp hook (proven pattern, debug-overlay) and resumes with
 * jmp $127A; the jsr hooks discard their return (addq #4,%sp) and
 * re-execute the displaced prologue before jumping on.
 *
 * Assemble: m68k-linux-gnu-as -m68000 -o source.o source.s
 *   (GAS: use 0x hex, %-prefixed registers; verify with objdump.)
 * build.py places the blob at $FD900 and resolves the three entry
 * offsets with m68k-linux-gnu-nm.
 */
    .text
    .globl vbl_entry
    .globl redraw_entry
    .globl scene_entry

/* ------------------------------------------------------------------ */
/* vbl_entry: VBlank hook. Replicates the replaced instruction
 * (move.w #$0,$FF0016) then, if armed in room 156, advances the
 * scroll accumulators from the pad state ($FF0018, previous frame's
 * byte: bit0 Up, bit1 Down, bit2 Left, bit3 Right) and writes the
 * Plane B scroll via $DC16 only when it changed. Resets the install
 * state when the location changes; disarms and restores scroll 0
 * when leaving room 156. Clobbers d0-d4/a0-a1 (saved/restored).
 */
vbl_entry:                       /* at PAD_BASE ($FD900) */
    move.w #0, 0xFF0016          /* replicate the replaced handler instr */
    movem.l %d0-%d4/%a0-%a1, -(%sp)
    cmpi.w #0x9C07, 0xFF00A0
    beq .vok
    /* init state */
    move.w #0x9C07, 0xFF00A0
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B0
    clr.w 0xFF00B2
    move.w #0xFFFF, 0xFF00B4
    move.w #0xFFFF, 0xFF00BC     /* installCamX = none yet */
    move.w #0xFFFF, 0xFF00C0     /* installCamY = none yet */
    bra .vdone
.vok:
    /* validate armed/installed in {0,1} */
    move.w 0xFF00A2, %d0
    cmpi.w #1, %d0
    bls .vaok
    bra .vreset
.vaok:
    move.w 0xFF00A6, %d0
    cmpi.w #1, %d0
    bls .viok
    bra .vreset
.viok:
    /* validate accumulator ranges */
    move.w 0xFF00A8, %d0
    cmpi.w #224, %d0
    bgt .vreset
    cmpi.w #-224, %d0
    blt .vreset
    move.w 0xFF00AA, %d0
    cmpi.w #128, %d0
    bgt .vreset
    cmpi.w #-128, %d0
    blt .vreset
    bra .vmain
.vreset:
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B0
    clr.w 0xFF00B2
    move.w #0xFFFF, 0xFF00BC
    move.w #0xFFFF, 0xFF00C0
    bra .vdone
.vmain:
    /* location change resets the install state (any door/teleport/
       save-load into another location reinstalls on next decode) */
    move.w 0xFF0E98, %d0
    cmp.w 0xFF00B4, %d0
    beq .vloc_ok
    move.w %d0, 0xFF00B4
    clr.w 0xFF00A6
    clr.w 0xFF00A2
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    move.w #0xFFFF, 0xFF00BC
    move.w #0xFFFF, 0xFF00C0
.vloc_ok:
    move.w 0xFF0E98, %d0
    cmpi.w #156, %d0
    bne .vnotroom
    tst.w 0xFF00A2
    beq .vdone
    /* pad byte -> per-frame (dh,dv) in d1/d2 (1/16 px) */
    moveq #0, %d0
    move.b 0xFF0018, %d0
    clr.w %d1
    clr.w %d2
    btst #0, %d0                /* Up (north): dh -16, dv -9 */
    beq .v1
    subi.w #16, %d1
    subi.w #9, %d2
.v1:
    btst #1, %d0                /* Down (south): dh +16, dv +9 */
    beq .v2
    addi.w #16, %d1
    addi.w #9, %d2
.v2:
    btst #2, %d0                /* Left (west): dh +16, dv -9 */
    beq .v3
    addi.w #16, %d1
    subi.w #9, %d2
.v3:
    btst #3, %d0                /* Right (east): dh -16, dv +9 */
    beq .v4
    subi.w #16, %d1
    addi.w #9, %d2
.v4:
    /* hAcc += dh, clamp [-224,224] */
    move.w 0xFF00A8, %d3
    add.w %d1, %d3
    cmpi.w #224, %d3
    ble .vh1
    move.w #224, %d3
.vh1:
    cmpi.w #-224, %d3
    bge .vh2
    move.w #-224, %d3
.vh2:
    move.w %d3, 0xFF00A8
    /* vAcc += dv, clamp [-128,128] */
    move.w 0xFF00AA, %d4
    add.w %d2, %d4
    cmpi.w #128, %d4
    ble .vv1
    move.w #128, %d4
.vv1:
    cmpi.w #-128, %d4
    bge .vv2
    move.w #-128, %d4
.vv2:
    move.w %d4, 0xFF00AA
    /* hScroll = hAcc>>4, vScroll = vAcc>>4 */
    move.w %d3, %d0
    asr.w #4, %d0
    move.w %d4, %d1
    asr.w #4, %d1
    /* write only when changed */
    cmp.w 0xFF00B0, %d0
    bne .vwrite
    cmp.w 0xFF00B2, %d1
    bne .vwrite
    bra .vdone
.vwrite:
    move.w %d0, 0xFF00B0
    move.w %d1, 0xFF00B2
    bra .vscroll
.vnotroom:
    /* outside room 156: disarm, keep `installed` (the overworld
       keeps its clean Plane B install; it reinstalls per scene),
       restore scroll 0 once if needed */
    clr.w 0xFF00A2
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    move.w 0xFF00B0, %d0
    or.w 0xFF00B2, %d0
    beq .vdone
    clr.w 0xFF00B0
    clr.w 0xFF00B2
    moveq #0, %d0
    moveq #0, %d1
    /* fall through to .vscroll with (hScroll,vScroll) = (0,0) */
.vscroll:
    /* $DC16(a=0, b=vScroll, c=0, d=hScroll): push d, c, b, a */
    move.w %d0, -(%sp)
    clr.w -(%sp)
    move.w %d1, -(%sp)
    clr.w -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
.vdone:
    movem.l (%sp)+, %d0-%d4/%a0-%a1
    jmp 0x00127A                 /* resume the VBlank handler */

/* ------------------------------------------------------------------ */
/* redraw_entry: redraw_check hook. Entered via jsr: discard the
 * return, run the gate/install logic, re-execute the displaced
 * prologue (link a6,#-2 ; tst.w $FF009C) and jump to $1B922.
 * The body's own rts then returns to redraw_check's caller.
 *
 * Transition (installed==0, in room 156, $FF0098 set): install the
 * Plane B layout for this scene — R4=$02, R16=$01, blank the whole
 * Plane B name table with tile $7FF (32 zero bytes: VRAM is cleared
 * at boot and no upload touches tiles $7F6-$7FF), draw the room
 * name table into Plane B, blank the window room rect with tile
 * $7FF — then let the body run its one decode+DMA. After that the
 * gate (below) suppresses the per-tick re-decode while the camera
 * stays put, and re-installs when the camera moves (fix2).
 * The install also runs for non-156 scenes (overworld etc.): the
 * Plane B layout is clean there too, but the gate and the scroll
 * stay room-156-only.
 * The transition records the install camera in $FF00BC/$FF00C0 so
 * the gate can tell a real camera move from a per-tick re-decode.
 */
redraw_entry:
    addq.w #4, %sp
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    cmpi.w #0x9C07, 0xFF00A0
    beq .rok
    /* init state (same as VBlank hook) */
    move.w #0x9C07, 0xFF00A0
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B0
    clr.w 0xFF00B2
    move.w #0xFFFF, 0xFF00B4
    move.w #0xFFFF, 0xFF00BC
    move.w #0xFFFF, 0xFF00C0
    bra .rdone
.rok:
    move.w 0xFF00A2, %d0
    cmpi.w #1, %d0
    bls .raok
    bra .rreset
.raok:
    move.w 0xFF00A6, %d0
    cmpi.w #1, %d0
    bls .riok
    bra .rreset
.riok:
    /* installed? then gate (room 156 only) */
    tst.w 0xFF00A6
    bne .rgate
    /* not installed: transition only when a room decode is pending */
    tst.w 0xFF0098
    beq .rdone
    /* no scene tiles yet (should not happen in main_loop): retry later */
    move.w 0xFF8674, %d0
    beq .rdone
    /* ---- transition: install the Plane B layout ---- */
    move.w #0x8402, -(%sp)      /* R4 = $02: Plane B $4000 */
    jsr 0xD9E2                  /* vdp_ctrl_write */
    addq.w #2, %sp
    move.w #0x9001, -(%sp)      /* R16 = $01: planes 64x32 */
    jsr 0xD9E2
    addq.w #2, %sp
    /* fill Plane B name table ($4000, 64x32) with blank tile $7FF.
       (Without this, cells outside the image rect would show
       rec-6 pattern bytes left in VRAM $4000-$4FFF as garbage.) */
    move.w #0x07FF, -(%sp)      /* tile */
    move.w #32, -(%sp)          /* rows */
    move.w #64, -(%sp)          /* cols */
    clr.w -(%sp)                /* y0 */
    clr.w -(%sp)                /* x0 */
    move.w #0x40, -(%sp)        /* stride */
    pea.l 0x00004000            /* dest */
    jsr 0x11A1A                 /* gfx_tilemap_fill */
    adda.w #16, %sp
    /* draw the room name table into Plane B $4000 */
    move.w 0xFF8674, -(%sp)     /* base */
    move.w #23, -(%sp)          /* rows */
    move.w #36, -(%sp)          /* cols */
    clr.w -(%sp)                /* y0 */
    move.w #2, -(%sp)           /* x0 */
    move.w #0x40, -(%sp)        /* stride */
    pea.l 0x00004000            /* dest */
    jsr 0x11820                 /* gfx_tilemap_draw */
    adda.w #16, %sp
    /* blank the window room rect (rows 0-22, cols 2-37) with $7FF
       so Plane B shows through (needed on the save-state path,
       where the window still holds the original room table) */
    move.w #0x07FF, -(%sp)      /* tile */
    move.w #23, -(%sp)          /* rows */
    move.w #36, -(%sp)          /* cols */
    clr.w -(%sp)                /* y0 */
    move.w #2, -(%sp)           /* x0 */
    move.w #0x40, -(%sp)        /* stride */
    pea.l 0x00001000            /* dest */
    jsr 0x11A1A                 /* gfx_tilemap_fill */
    adda.w #16, %sp
    move.w #1, 0xFF00A6         /* installed */
    move.w #1, 0xFF00A2         /* armed (scroll; VBlank gates on 156) */
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    /* record the install camera (fix2): the gate compares against it */
    move.w 0xFF0E8E, 0xFF00BC    /* installCamX = camera X */
    move.w 0xFF0E90, 0xFF00C0    /* installCamY = camera Y */
    bra .rdone
.rgate:
    /* installed: camera-aware re-decode gate, room 156 only (fix2).
       The body re-decodes (map_chunk_pos + DMA) whenever $FF0098 is
       set; the Plane B image follows because the room draws are
       redirected to Plane B and the patterns are re-uploaded, and
       the figures are re-baked at their current positions. Suppress
       the per-tick re-decode only while the camera is still within
       the scroll's +/-1-cell reach of the install camera; once it
       has moved, let the body run so the image follows it.
       d0 = dx = camX - installCamX, d1 = dy = camY - installCamY. */
    move.w 0xFF0E98, %d0
    cmpi.w #156, %d0
    bne .rdone
    move.w 0xFF0E8E, %d0
    sub.w 0xFF00BC, %d0         /* d0 = dx */
    move.w 0xFF0E90, %d1
    sub.w 0xFF00C0, %d1         /* d1 = dy */
    tst.w %d0
    bne .gdxnz
    tst.w %d1
    beq .gsuppress              /* dx==0 and dy==0: camera unmoved */
.gdxnz:
    /* adx = |dx| in d2, ady = |dy| in d3 */
    move.w %d0, %d2
    bpl .gdxp
    neg.w %d2
.gdxp:
    move.w %d1, %d3
    bpl .gdyp
    neg.w %d3
.gdyp:
    /* >1 cell away on either axis: moved too far for the scroll
       (teleport / fast move / scroll lagged) -> reinstall now
       (1-cell jump; strip streaming will close that gap) */
    cmpi.w #1, %d2
    bgt .greinstall
    cmpi.w #1, %d3
    bgt .greinstall
    /* exactly 1 cell away: reinstall only once the scroll has
       caught up to the move, else suppress and wait — the gate
       runs every main_loop iteration, so it re-checks next frame.
       Expected accumulators for (dx,dy), clamped to the scroll
       range: hExp = -(dx-dy)*224, vExp = (dx+dy)*128. Each of
       (dx-dy),(dx+dy) is in [-2,2]; |.|>=1 clamps to the extreme,
       so hExp = sign(dx-dy)*224 (or 0), vExp = sign(dx+dy)*128. */
    move.w %d0, %d4
    sub.w %d1, %d4              /* d4 = dx - dy */
    neg.w %d4                   /* d4 = -(dx-dy) */
    tst.w %d4
    beq .gh0
    bpl .ghpos
    move.w #-224, %d4           /* hExp = -224 */
    bra .ghhave
.ghpos:
    move.w #224, %d4            /* hExp = +224 */
    bra .ghhave
.gh0:
    clr.w %d4                   /* hExp = 0 */
.ghhave:
    cmp.w 0xFF00A8, %d4
    bne .gsuppress              /* hAcc != hExp: scroll still sliding */
    move.w %d0, %d5
    add.w %d1, %d5              /* d5 = dx + dy */
    tst.w %d5
    beq .gv0
    bpl .gvpos
    move.w #-128, %d5           /* vExp = -128 */
    bra .gvhave
.gvpos:
    move.w #128, %d5            /* vExp = +128 */
    bra .gvhave
.gv0:
    clr.w %d5                   /* vExp = 0 */
.gvhave:
    cmp.w 0xFF00AA, %d5
    bne .gsuppress              /* vAcc != vExp: scroll still sliding */
    /* scroll caught up: the new image at scroll 0 is exactly the
       old image at the scroll extreme -> seamless reinstall */
    bra .greinstall
.gsuppress:
    clr.w 0xFF0098
    bra .rdone
.greinstall:
    /* update the install camera to the current camera */
    move.w 0xFF0E8E, 0xFF00BC
    move.w 0xFF0E90, 0xFF00C0
    /* reset the scroll to (0,0) now (VDP + state) so the body's
       fresh decode shows unshifted; the VBlank hook then keeps it
       0 until the D-pad builds it again for the next cell */
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B0
    clr.w 0xFF00B2
    clr.w -(%sp)                /* $DC16(a=0, b=0, c=0, d=0) */
    clr.w -(%sp)
    clr.w -(%sp)
    clr.w -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
    /* fall through to .rdone WITHOUT clearing $FF0098: the body
       runs its decode+DMA for the new camera. */
    bra .rdone
.rreset:
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B0
    clr.w 0xFF00B2
    move.w #0xFFFF, 0xFF00BC
    move.w #0xFFFF, 0xFF00C0
    bra .rdone
.rdone:
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    link.w %a6, #-2
    move.w 0xFF009C, %d0         /* tst.w $FF009C (re-executed prologue) */
    tst.w %d0
    jmp 0x1B922

/* ------------------------------------------------------------------ */
/* scene_entry: world_map_draw hook. Entered via jsr: discard the
 * return, reset the install state (a scene setup re-uploads rec 6
 * over VRAM $4000-$4FFF, so the Plane B table must be reinstalled),
 * re-execute the displaced prologue (link a6,#-4 ; pea.l $0CCAD8)
 * and jump to $12C2A. Uses no registers, so nothing is saved.
 */
scene_entry:
    addq.w #4, %sp
    clr.w 0xFF00A6               /* installed */
    clr.w 0xFF00A2               /* armed */
    clr.w 0xFF00A8               /* hAcc */
    clr.w 0xFF00AA               /* vAcc */
    move.w #0xFFFF, 0xFF00BC     /* installCamX = none yet */
    move.w #0xFFFF, 0xFF00C0     /* installCamY = none yet */
    link.w %a6, #-4
    pea.l 0x000CCAD8
    jmp 0x012C2A
