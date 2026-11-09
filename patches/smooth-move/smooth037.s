/*
 * smooth037.s — #037 smooth-motion patch for Rings of Power (Sega Mega Drive)
 *
 * Pixel-precision camera: when the overworld camera steps, delay the full
 * name-table DMA ($1B918 / $DA04) and step the scroll registers 1 px/frame
 * via $DC16 until the tile boundary, then let the DMA run once. Game logic
 * stays tile-based ($1C21A, $32C56 untouched).
 *
 * Mechanism (proven live, see .scratch037/cutscene-findings.md):
 *   - The cutscene scrolls smoothly via $171D6's per-line H-scroll table.
 *   - The overworld has NO per-frame scroll: $DC16 is called only at layout
 *     install (traceB cntD=2, both (0,0,0,0)), and $1B918 re-uploads the
 *     whole visible map ($33C0 words = 26,496 bytes) on every camera step.
 *     The camera moves in +/-2-tile steps (traceB 'C' entries: X +2 every
 *     ~20 frames while walking right, Y -2 per step), so the visible snap
 *     is 16 px, not 8 px. This patch interpolates ANY axis-aligned camera
 *     step of 1-4 tiles (8-32 px) at 1 px/frame.
 *   - $FF0098 is set ONLY by $1BA16 (light, 0x1BA1A) and $1BA26 (heavy,
 *     0x1BA2A, also sets $FFB08A/$FF009A/$FF009C), cleared by $1B918 after
 *     the DMA. Clearing it at $1B918 entry suppresses the rebuild+DMA.
 *   - $1B918 is called 2x per $D28E iteration (twice per frame), so the
 *     interp is gated on the VBlank frame counter ($FF0012) to advance
 *     exactly 1 px/frame, not 2.
 *
 * Hook: $1B918 entry (6-byte jsr). Trampoline below re-executes the replaced
 * prologue (link a6,#-2 ; tst.w $FF009C) and jmps to $1B918+6. The hook is
 * entered via jsr, so it does addq #4,%sp to discard the hook return before
 * jumping on (the $1B918 body's own rts then returns to $1B918's caller).
 * A jsr hook MUST exit with rts/jmp-on, never a plain jmp that leaks the
 * return address (proven in #021).
 *
 * State: dead RAM $FF00A0-$FF00BC (0 refs in rop.s, no lea into the block).
 * $FF00A4 is NOT used (1 ref: tst at 0x1CF3C). $FF00B6/$FF00B8/$FF00BA/
 * $FF00BE are game variables and are NOT used. Every state word is range
 * validated on each call; anything out of range re-inits to safe defaults
 * (active=0, no DMA suppression) so a stray game write fails safe.
 *
 * v1 limitation: during the interp the leading edge strip shows stale tiles
 * (the name table still holds the old window). Fixed when the DMA runs at
 * the boundary. A v2 preload (DMA just the new strip via $DA04 during the
 * interp) would remove it.
 *
 * Assemble: m68k-linux-gnu-as -m68000 -o smooth037.o smooth037.s
 *   (GAS: use 0x hex, %-prefixed registers; verify with objdump.)
 */
    .text
    .globl _start
_start:                      /* = hook1B918, at PAD_BASE */
    addq.w #4, %sp
    movem.l %d0-%d3, -(%sp)
    bsr patch_step
    movem.l (%sp)+, %d0-%d3
    link.w %a6, #-2
    move.w 0xFF009C, %d0         /* tst.w $FF009C (re-executed prologue) */
    /* NOTE: the original is tst.w, which sets flags from the value. We use
       move.w into d0 then tst.w d0 to reproduce the flags exactly. */
    tst.w %d0
    jmp 0x1B922

/* ------------------------------------------------------------------ */
/* patch_step: the per-frame smooth-scroll logic. Called from the hook
 * with d0-d3 saved. Clobbers d0-d3 (saved by caller). Preserves a0-a6.
 * State words (all $FF00xx, 0 refs):
 *   A0 magic 0x5A37 | A2 active | A6 dirX | A8 dirY | AA step
 *   B0 prevCamX | B2 prevCamY | B4 total (px) | BC lastFrame
 */
patch_step:
    /* frame gate: $1B918 runs 2x/frame; advance the interp once per frame */
    move.w 0xFF0012, %d0
    cmp.w 0xFF00BC, %d0
    beq .sameframe
    move.w %d0, 0xFF00BC
    bra .go
.sameframe:
    /* same frame as last call: still need to suppress the DMA if an interp
       is active (the 2nd $1B918 call in this frame would otherwise run it).
       Never trust `active` before the magic is set (first call at boot). */
    cmpi.w #0x5A37, 0xFF00A0
    bne .done
    tst.w 0xFF00A2
    beq .done
    clr.w 0xFF0098
.done:
    rts
.go:
    /* validate magic; init if absent */
    cmpi.w #0x5A37, 0xFF00A0
    beq .valid
    /* init: magic, active=0, dir=0, step=0, total=0, prevCam=current */
    move.w #0x5A37, 0xFF00A0
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B4
    move.w 0xFF0E8E, 0xFF00B0
    move.w 0xFF0E90, 0xFF00B2
    rts
.valid:
    /* validate state ranges; reset if corrupt */
    move.w 0xFF00A2, %d0            /* active in {0,1} */
    cmpi.w #1, %d0
    bls .act_ok
    bra .reset
.act_ok:
    move.w 0xFF00A6, %d0            /* dirX in {-1,0,1} */
    cmpi.w #1, %d0
    bgt .reset
    cmpi.w #-1, %d0
    blt .reset
    move.w 0xFF00A8, %d0            /* dirY in {-1,0,1} */
    cmpi.w #1, %d0
    bgt .reset
    cmpi.w #-1, %d0
    blt .reset
    move.w 0xFF00AA, %d0            /* step in 0..32 */
    cmpi.w #32, %d0
    bgt .reset
    tst.w %d0
    blt .reset
    move.w 0xFF00B4, %d0            /* total in {0,8,16,24,32} */
    tst.w %d0
    blt .reset
    cmpi.w #32, %d0
    bgt .reset
    move.w %d0, %d1
    andi.w #7, %d1
    bne .reset
    bra .state_ok
.reset:
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B4
    move.w 0xFF0E8E, 0xFF00B0
    move.w 0xFF0E90, 0xFF00B2
    rts
.state_ok:
    /* if an interp is active, advance it (don't re-detect the step) */
    tst.w 0xFF00A2
    bne .interp
    /* no interp: detect a camera step */
    move.w 0xFF0E8E, %d0
    sub.w 0xFF00B0, %d0             /* dx = camX - prevCamX */
    move.w 0xFF0E90, %d1
    sub.w 0xFF00B2, %d1             /* dy = camY - prevCamY */
    tst.w %d0
    bne .dxnz
    tst.w %d1
    bne .dynz
    rts                             /* no change: nothing to do */
.dxnz:
    tst.w %d1
    bne .notsingle                  /* diagonal: not a single-axis step */
    bra .axisx
.dynz:
    bra .axisy
    /* ---- axis X: dx in d0 ---- */
.axisx:
    move.w %d0, %d2
    bpl .px
    neg.w %d2                       /* d2 = |dx| */
.px:
    cmpi.w #4, %d2
    bgt .notsingle                  /* >4 tiles: teleport */
    /* heavy flags set? then don't suppress (map change / teleport) */
    tst.w 0xFFB08A
    bne .notsingle
    tst.w 0xFF009A
    bne .notsingle
    tst.w 0xFF009C
    bne .notsingle
    /* start interp: dirX = sign(dx), total = 8*|dx|, step = 1 */
    move.w #1, 0xFF00A2
    tst.w %d0
    bpl .dxpos
    move.w #-1, 0xFF00A6
    bra .dxdir
.dxpos:
    move.w #1, 0xFF00A6
.dxdir:
    clr.w 0xFF00A8
    move.w #1, 0xFF00AA
    lsl.w #3, %d2                   /* total = |dx| * 8 */
    move.w %d2, 0xFF00B4
    clr.w 0xFF0098                  /* suppress this frame's DMA */
    /* $DC16(0, 0, -dirX*1, -dirX*1): H-scroll 1 px */
    move.w 0xFF00A6, %d2
    neg.w %d2
    move.w %d2, -(%sp)
    move.w %d2, -(%sp)
    clr.w -(%sp)
    clr.w -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
    rts
    /* ---- axis Y: dy in d1 ---- */
.axisy:
    move.w %d1, %d2
    bpl .py
    neg.w %d2                       /* d2 = |dy| */
.py:
    cmpi.w #4, %d2
    bgt .notsingle
    tst.w 0xFFB08A
    bne .notsingle
    tst.w 0xFF009A
    bne .notsingle
    tst.w 0xFF009C
    bne .notsingle
    move.w #1, 0xFF00A2
    clr.w 0xFF00A6
    tst.w %d1
    bpl .dypos
    move.w #-1, 0xFF00A8
    bra .dydir
.dypos:
    move.w #1, 0xFF00A8
.dydir:
    move.w #1, 0xFF00AA
    lsl.w #3, %d2
    move.w %d2, 0xFF00B4
    clr.w 0xFF0098
    /* $DC16(-dirY*1, -dirY*1, 0, 0): V-scroll 1 px */
    move.w 0xFF00A8, %d2
    neg.w %d2
    clr.w -(%sp)
    clr.w -(%sp)
    move.w %d2, -(%sp)
    move.w %d2, -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
    rts
.notsingle:
    /* teleport / multi-tile (>4) / diagonal / heavy: reset scroll, sync
       prevCam, no suppression (DMA runs immediately, as original) */
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B4
    move.w 0xFF0E8E, 0xFF00B0
    move.w 0xFF0E90, 0xFF00B2
    clr.w -(%sp)
    clr.w -(%sp)
    clr.w -(%sp)
    clr.w -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
    rts
.interp:
    /* advance the in-progress interp by one pixel */
    move.w 0xFF00AA, %d0
    addq.w #1, %d0
    move.w %d0, 0xFF00AA
    cmp.w 0xFF00B4, %d0
    bge .finish
    /* step < total: scroll to `step` px, suppress DMA */
    clr.w 0xFF0098
    move.w 0xFF00A6, %d1            /* dirX */
    tst.w %d1
    bne .ix
    /* Y step: $DC16(-dirY*step, -dirY*step, 0, 0) */
    move.w 0xFF00A8, %d2
    muls.w %d0, %d2                 /* dirY * step */
    neg.w %d2                       /* -dirY*step */
    clr.w -(%sp)
    clr.w -(%sp)
    move.w %d2, -(%sp)
    move.w %d2, -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
    rts
.ix:
    /* X step: $DC16(0, 0, -dirX*step, -dirX*step) */
    move.w %d1, %d2
    muls.w %d0, %d2                 /* dirX * step */
    neg.w %d2
    move.w %d2, -(%sp)
    move.w %d2, -(%sp)
    clr.w -(%sp)
    clr.w -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
    rts
.finish:
    /* step == total: boundary. Let the DMA run, reset scroll, sync prevCam. */
    clr.w 0xFF00A2
    clr.w 0xFF00A6
    clr.w 0xFF00A8
    clr.w 0xFF00AA
    clr.w 0xFF00B4
    move.w #0xFFFF, 0xFF0098        /* re-set: DMA runs in this $1B918 call */
    move.w 0xFF0E8E, 0xFF00B0
    move.w 0xFF0E90, 0xFF00B2
    clr.w -(%sp)
    clr.w -(%sp)
    clr.w -(%sp)
    clr.w -(%sp)
    jsr 0xDC16
    addq.w #8, %sp
    rts
