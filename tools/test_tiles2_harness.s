/* Test harness #2 for Rings of Power issue #016 (packed-vs-planar paradox).
 * Drives the PRODUCTION tile-upload path live and snapshots both ends:
 *   $1383C(0)      -- decompress $96120 rec 0 (ASCII font) into $FF1EC0
 *   $11A7C($FF1EC0, 103) -- DMA-upload all 103 tiles at a scratch cursor (0x700)
 * then snapshots $FF1EC0 tile 93 (a fully-nonzero glyph tile:
 * 11 11 11 11 ff ff ff ff 1f 11 1f 11 ...) and VRAM tile 0x700+93
 * (what the VDP actually received).
 * If VRAM == $FF1EC0, the production path delivers packed bytes verbatim
 * to VRAM (confirming the static trace); if VRAM is the planar
 * conversion, a conversion exists in the path.
 *
 * Hook at 0x35C, harness at 0xFD0CC. Same pattern as test_tiles_harness.s:
 * snapshot once while 60 <= $FFC002 <= 70, flag 0xBEEF at $FFD000,
 * canaries 0xA5A5/0x5A5A. $FF0076 (tile cursor) is saved and restored
 * around the $11A7C call so the game's own loading is undisturbed;
 * VRAM $E000 (tiles 1792+) is unused pattern area in the attract layout.
 * Hook exit is `rts` (never jmp -- #021 Q13).
 *
 * Result layout (words, base $FFD000):
 *  $FFD000 = 0xBEEF. $FFD002 = 0xA5A5. $FFD00E = 0x5A5A.
 *  $FFD004: $FFC002  $FFD006: $FF0076 (restored value)
 *  $FFD010: $FF1EC0 tile 93, 16 words (decompressed font glyph)
 *  $FFD030: VRAM tile 0x700+93 ($EBA0), 16 words (uploaded tile)
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    beq already_done
    move.w 0xFFC002, %d0
    cmpi.w #60, %d0
    blt not_yet
    cmpi.w #70, %d0
    bgt not_yet
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD00E
    move.w #0x8F02, 0xC00004
    /* save the game's tile cursor in a scratch word (d3 is clobbered by
     * $DD5C, so it cannot hold the saved value across the calls) */
    move.w 0xFF0076, 0xFFD00C
    move.w #0x700, 0xFF0076
    /* $1383C(0): decompress $96120 rec 0 (font) into $FF1EC0; returns d0=$FF1EC0 */
    clr.w -(%sp)
    jsr 0x1383C
    addq.w #2, %sp
    /* $11A7C(d0=$FF1EC0, 103): DMA all 103 font tiles at cursor 0x700
     * -> VRAM $E000. $11A7C takes (src, count); count is pushed first. */
    move.w #103, -(%sp)
    move.l %d0, -(%sp)
    jsr 0x11A7C
    addq.w #6, %sp
    /* restore the game's tile cursor */
    move.w 0xFFD00C, 0xFF0076
    /* scalars */
    lea 0xFFD004, %a0
    move.w 0xFFC002, (%a0)+
    move.w 0xFF0076, (%a0)+
    /* $FF1EC0 tile 93, 16 words */
    lea 0xFFD010, %a0
    movea.l #0xFF2A60, %a1
    moveq #15, %d1
g_loop:
    move.w (%a1)+, (%a0)+
    dbra %d1, g_loop
    /* VRAM tile 0x700+93 ($EBA0), 16 words */
    move.l #0xEBA0, %d0
    moveq #15, %d1
    bsr vram_read
    movem.l (%sp)+, %d0-%d3/%a0-%a1
already_done:
    move.w 0xC00004, %d1
    rts
not_yet:
    move.w 0xC00004, %d1
    rts

/* vram_read: a0 = dest (words), d0 = VRAM byte address, d1 = count-1.
 * First read after setting the address returns the word AT that address
 * (verified live in #015) -- no dummy word. Clobbers d0/d2. */
vram_read:
    move.w %d0, %d2
    andi.w #0x3FFF, %d0
    move.w %d0, 0xC00004
    move.w %d2, %d0
    rol.w #2, %d0
    andi.w #3, %d0
    move.w %d0, 0xC00004
vr_loop:
    move.w 0xC00000, (%a0)+
    dbra %d1, vr_loop
    rts
