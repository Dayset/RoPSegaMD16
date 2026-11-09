/* Test harness for Rings of Power issue #015 (VDP register + VRAM map).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called from a hook at
 * 0x35C (attract loop top, replaces `move.w $C00004,d1`).
 * Snapshots live VRAM/CRAM regions into $FFD004+ once the attract scroll
 * counter $FFC002 has decayed into [60,70] (about 85 frames in:
 * the title setup sets it to 150, $4E6 decrements it once per frame).
 * The game then continues; results are read back with the BlastEm
 * debugger (`p/x $FFD0xx`).
 *
 * Build: m68k-linux-gnu-as -m68000 -o harness015.o test_vdp_harness.s
 *        m68k-linux-gnu-objcopy -O binary harness015.o harness015.bin
 * Inject: copy rop-original.gen to /tmp/test015.gen, write harness015.bin
 *        at 0xFD0CC, write jsr $FD0CC.l (4E B9 00 0F D0 CC) at 0x35C,
 *        then `python3 tools/checksum.py fix-all` (runtime first,
 *        header last) and verify with `verify-all`.
 *
 * NOTE: GNU as (m68k-linux-gnu-as 2.42) wants %-prefixed registers
 * (%d0, %a5, %sp), no .l on absolute addresses, and no .s on branches.
 *
 * Result layout (words, base $FFD004):
 *  [ 0] $FFC002 at snapshot (expect 60..70)
 *  [ 1] $FFC004  [ 2] $FFC006  [ 3] $FFC000
 *  [ 4] $FF8644 (sprite-table base var)  [ 5] $FF0076 (tile cursor)
 *  [ 6] $FF0126 (palette mode)  [ 7] $FF0E16 (step counter)
 *  [ 8..23]  VRAM $2000, 16 words (H-scroll table, first 8 lines:
 *       expect [-X, $140, +X, $140, ...] with X = $FFC002)
 *  [24..55]  VRAM $A000, 32 words (Plane A/B name table, row 0)
 *  [56..71]  VRAM $DC00, 16 words (sprite table, first 4 attributes)
 *  [72..79]  VRAM $C000, 8 words (window name table, first row)
 *  [80..95]  CRAM palette 0, 16 words
 * $FFD000 = 0xBEEF (snapshot taken). $FFD002 = 0xA5A5 (canary 1).
 * $FFD0FE = 0x5A5A (canary 2, checked by the driver).
 *
 * Hook exit is `rts`, NOT jmp 0x362: the hook is `jsr $FD0CC`, which
 * pushed 0x362 as the return address; jmp would leak 4 stack bytes per
 * hook hit, and the hook sits at 0x35C (the attract loop's VBlank spin
 * target), so the stack plummets and the game faults at PC=0 in ~3 s
 * (#021 Q13). The displaced instruction `move.w $C00004,d1` is executed
 * by the harness before rts so the loop's `btst #3,d1` sees the status.
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    beq already_done
    /* snapshot only while 60 <= $FFC002 <= 70 */
    move.w 0xFFC002, %d0
    cmpi.w #60, %d0
    blt not_yet
    cmpi.w #70, %d0
    bgt not_yet
    /* take the snapshot */
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE
    /* R15 = auto-increment 2 (already $02 in the $A14 layout; be safe) */
    move.w #0x8F02, 0xC00004
    lea 0xFFD004, %a0
    move.w 0xFFC002, (%a0)+
    move.w 0xFFC004, (%a0)+
    move.w 0xFFC006, (%a0)+
    move.w 0xFFC000, (%a0)+
    move.w 0xFF8644, (%a0)+
    move.w 0xFF0076, (%a0)+
    move.w 0xFF0126, (%a0)+
    move.w 0xFF0E16, (%a0)+
    /* VRAM $2000: H-scroll table, 16 words */
    move.l #0x2000, %d0
    moveq #15, %d1
    bsr vram_read
    /* VRAM $A000: name table, 32 words (row 0, cols 0-31) */
    move.l #0xA000, %d0
    moveq #31, %d1
    bsr vram_read
    /* VRAM $DC00: sprite table, 16 words */
    move.l #0xDC00, %d0
    moveq #15, %d1
    bsr vram_read
    /* VRAM $C000: window name table, 8 words */
    move.l #0xC000, %d0
    moveq #7, %d1
    bsr vram_read
    /* CRAM palette 0, 16 words */
    moveq #15, %d1
    bsr cram_read
    movem.l (%sp)+, %d0-%d3/%a0-%a1
already_done:
    move.w 0xC00004, %d1
    rts
not_yet:
    move.w 0xC00004, %d1
    rts

/* vram_read: a0 = dest (words), d0 = VRAM byte address, d1 = count-1.
 * Sets a VRAM READ command, then reads count words with
 * auto-increment 2. The first read after setting the address returns the
 * word AT that address (verified live: VRAM[$2000] = -$FFC002, see the
 * run notes) -- there is no dummy word to discard. Clobbers d0/d2. */
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

/* cram_read: a0 = dest (words), d1 = count-1. Reads CRAM from 0.
 * Clobbers d0. */
cram_read:
    move.w #0, 0xC00004
    move.w #0x20, 0xC00004
cr_loop:
    move.w 0xC00000, (%a0)+
    dbra %d1, cr_loop
    rts
