/*
 * overlay.s — debug overlay for Rings of Power (Sega Mega Drive)
 *
 * On-screen readout of the live song state, for a playthrough check of the
 * Life sting (song 8) audibility. Draws one 20-cell row in the Window plane
 * (row 0, cols 14-33), re-drawn every VBlank:
 *
 *   S02 0F363E 0F373E FF
 *   ^   ^      ^      ^
 *   |   |      |      sound-on $FF021E (FF=on)
 *   |   |      song end $FF0230 (low 24 bits)
 *   |   song start $FF022C (low 24 bits)
 *   song index $FF012E (low byte)
 *
 * Song 8 via Life shows as "S02 0F363E 0F373E FF" — the index does NOT
 * change (the Life path bypasses the $173C0 wrapper that sets $FF012E),
 * but the start address flips to $0F363E for ~72 frames, then back.
 * Watch the start address flip to 0F363E to see song 8 start, and flip
 * back to see it finish.
 *
 * Mechanism (see .scratch028/overlay-investigation.md):
 *   - Hook: $1272 (VBlank handler entry). Replaces the 8-byte
 *     `move.w #$0,$FF0016` with `jmp $FD200.l` + `nop` (the proven
 *     .scratch026 pattern). Trampoline replicates the replaced
 *     instruction, then `jmp $00127A` (resume handler).
 *   - Draw: Window plane, VRAM $1000 (Layout G). Row 0, col 14 = $101C.
 *     Row 0 is stride-independent (works in both Layout G variants).
 *   - Font: base read from $FF8640 at runtime (scene-dependent);
 *     tile = base + (ASCII - $20). Digits '0'-'9' = base+$10+v,
 *     'A'-'F' = base+$21+(v-10), 'S' = base+$33, ' ' = base+$00.
 *   - Layout G check: only draw when $FF8644 == $2400 (sprite-table
 *     base). In Layout L the window is $F000 and $101C would scribble
 *     Plane B, so the hook skips drawing there.
 *   - No PC/SP snapshot (the .scratch027 bisection proved that corrupts
 *     boot/title). The hook saves/restores d0-d4/a0-a1 only.
 *   - Hazard (known, acceptable for a debug tool): VDP writes from
 *     interrupt context can interleave with the main loop's VDP writes
 *     (no VBlank sync in the $D28E loop tail), producing a transient
 *     misplaced tile now and then. Self-correcting on the next redraw.
 *     If it shows up, the fallback is the two-hook variant in
 *     .scratch028/overlay-investigation.md §3.6.
 *
 * Assemble: m68k-linux-gnu-as -m68000 -o overlay.o overlay.s
 *   (GAS: use 0x hex, %-prefixed registers; verify with objdump.)
 */
    .text
    .globl _start
_start:                          /* overlay_vbl, at PAD_BASE ($FD200) */
    move.w #0, 0xFF0016          /* replicate the replaced handler instr */
    movem.l %d0-%d4/%a0-%a1, -(%sp)
    cmpi.w #0x2400, 0xFF8644     /* Layout G check (sprite base $2400) */
    bne done
    move.w 0xFF8640, %a0         /* font base (runtime; $134 world map) */
    /* set VRAM write to $101C (window row 0, col 14) */
    move.w #0x8F02, 0xC00004     /* R15 = $02 (auto-inc 2) */
    move.w #0x501C, 0xC00004     /* VRAM write cmd word 1 ($4000|$101C) */
    move.w #0x0000, 0xC00004     /* VRAM write cmd word 2 (addr bits 15-14) */
    /* 'S' (label) */
    move.w %a0, %d4
    addi.w #0x33, %d4
    move.w %d4, 0xC00000
    /* song index: 2 hex digits of low byte of $FF012E */
    move.w 0xFF012E, %d0
    andi.w #0xFF, %d0
    move.w #2, %d1
    jsr write_hex
    /* ' ' */
    move.w %a0, 0xC00000
    /* song start: 6 hex digits of $FF022C (low 24 bits) */
    move.l 0xFF022C, %d0
    move.w #6, %d1
    jsr write_hex
    /* ' ' */
    move.w %a0, 0xC00000
    /* song end: 6 hex digits of $FF0230 (low 24 bits) */
    move.l 0xFF0230, %d0
    move.w #6, %d1
    jsr write_hex
    /* ' ' */
    move.w %a0, 0xC00000
    /* sound-on: 2 hex digits of $FF021E */
    move.b 0xFF021E, %d0
    andi.w #0xFF, %d0
    move.w #2, %d1
    jsr write_hex
done:
    movem.l (%sp)+, %d0-%d4/%a0-%a1
    jmp 0x00127A                 /* resume the VBlank handler */

/* write_hex: write %d1 hex digits of %d0 (MSB first) to the VDP data port.
 * %d0 = value (long), %d1 = digit count (2 or 6), %a0 = font base.
 * Clobbers %d0-%d4. %a0 preserved. */
write_hex:
    move.l %d0, %d4              /* copy value */
    move.w %d1, %d2
    subq.w #1, %d2
    lsl.w #2, %d2                /* shift = (digits-1)*4 (MSB nibble) */
whex_loop:
    move.l %d4, %d0
    lsr.l %d2, %d0               /* shift right to the target nibble */
    andi.w #0xF, %d0             /* isolate nibble */
    cmpi.w #10, %d0
    blt whex_digit
    addi.w #0x21-10, %d0         /* 'A'-'F': offset $21 + (v-10) */
    bra whex_out
whex_digit:
    addi.w #0x10, %d0            /* '0'-'9': offset $10 + v */
whex_out:
    add.w %a0, %d0               /* + font base */
    move.w %d0, 0xC00000         /* write name-table word (auto-inc +2) */
    subq.w #4, %d2               /* next nibble (4 bits lower) */
    bpl whex_loop
    rts
