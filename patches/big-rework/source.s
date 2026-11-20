/*
 * source.s — big-rework proof-of-concept patch for Rings of Power
 * (Sega Mega Drive). Design: .scratch-big-rework/DESIGN.md §8.
 *
 * Proves decode-once + hardware scroll for the Academy room
 * (chunk 233, location 156): the room image is decoded ONCE by the
 * unmodified map_chunk_pos, its name table lives in Plane B
 * (VRAM $4000), the window plane shows through transparently, and
 * the D-pad slides the whole room via the Plane B scroll ($DC16).
 * Figures are baked into the image, frozen; no sprites, no
 * collision/game changes, no strip streaming, no tick governor.
 *
 * Three trampolines in one blob (placed at $FD900, in the 0xFF
 * padding past the runtime checksum's summed range $000000-$FD07B):
 *   vbl_entry    — VBlank hook ($1272): per-frame D-pad scroll.
 *   redraw_entry — redraw_check hook ($1B918): one-time Plane B
 *                  install + suppression of the per-tick re-decode.
 *   scene_entry  — world_map_draw hook ($12C20): reset the install
 *                  state on every scene setup.
 * Plus three static patches applied by build.py (asserting the
 * original bytes first):
 *   $12C9A  move.w #$8400,-(sp) -> #$8402   (R4: Plane B $4000)
 *   $12E68  pea $001000.w -> pea $004000.w  (room draw -> Plane B)
 *   $16326  pea $001000.w -> pea $004000.w  (redraw room -> Plane B)
 * R16 is already $01 (planes 64x32) in world_map_draw ($12CDE) and
 * needs no change; gfx_layout_game's $9003 is re-set by
 * world_map_draw before gameplay.
 *
 * State: dead RAM $FF00A0-$FF00B4 (0 refs in disasm/src/rop.s).
 *   A0 magic $9C07 | A2 armed | A6 installed | A8 hAcc | AA vAcc
 *   B0 lastH | B2 lastV | B4 lastLoc
 * $FF00A4 is NOT used (1 ref: tst at $1CF3C). $FF00AC/$FF00AE are
 * live menu fields and are NOT used. Every state word is
 * range-validated on each use; anything out of range re-initialises
 * to safe defaults (no scroll, no suppression) so a stray game
 * write fails safe to original behaviour.
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
 * gate suppresses every further room re-decode (installed==1 in
 * room 156 clears $FF0098 at entry; menu/panel/dialog arms, which
 * do not depend on $FF0098, keep running).
 * The install also runs for non-156 scenes (overworld etc.): the
 * Plane B layout is clean there too, but the gate and the scroll
 * stay room-156-only.
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
    bra .rdone
.rgate:
    /* installed: suppress the room re-decode in room 156 only */
    move.w 0xFF0E98, %d0
    cmpi.w #156, %d0
    bne .rdone
    clr.w 0xFF0098
    bra .rdone
.rreset:
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B0
    clr.w 0xFF00B2
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
    link.w %a6, #-4
    pea.l 0x000CCAD8
    jmp 0x012C2A
