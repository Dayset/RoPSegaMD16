/* Test harness for Rings of Power issue #016 (packed-vs-planar paradox).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called from a hook at
 * 0x35C (attract loop top, replaces `move.w $C00004,d1`).
 * Snapshots live VRAM pattern bytes + the decode buffer into $FFD010+
 * once the attract scroll counter $FFC002 has decayed into [60,70]
 * (about 85 frames in: the title setup sets it to 150, $4E6 decrements
 * it once per frame). The game then continues; results are read back
 * with the BlastEm debugger (`p/x $FFD0xx`).
 *
 * The question: the decompressed tile bytes in $FF1EC0 are PACKED
 * (2 px/byte, hi nibble first -- proven by #005's renders), the DMA
 * upload path ($1383C -> $11A7C -> $DA04) copies them VERBATIM to
 * VRAM, yet the game displays correctly on a bitplanar VDP. This
 * harness captures what the VDP actually receives, so the VRAM bytes
 * can be compared against the decompressed record bytes (packed) and
 * their planar conversions.
 *
 * Build: m68k-linux-gnu-as -m68000 -o harness016.o test_tiles_harness.s
 *        m68k-linux-gnu-objcopy -O binary harness016.o harness016.bin
 * Inject: copy rop-original.gen to /tmp/test016.gen, write harness016.bin
 *        at 0xFD0CC, write jsr $FD0CC.l (4E B9 00 0F D0 CC) at 0x35C,
 *        then `python3 tools/checksum.py fix-all` (runtime first,
 *        header last) and verify with `verify-all`.
 *
 * NOTE: GNU as (m68k-linux-gnu-as 2.42) wants %-prefixed registers
 * (%d0, %a5, %sp), no .l on absolute addresses, and no .s on branches.
 *
 * Result layout (words, base $FFD000):
 *  $FFD000 = 0xBEEF (snapshot taken). $FFD002 = 0xA5A5 (canary 1).
 *  $FFD004: $FFC002 at snapshot (expect 60..70)
 *  $FFD006: $FF0076 (tile cursor)
 *  $FFD008: $FF8640  $FFD00A: $FF8642  $FFD00C: $FF8644
 *  $FFD00E = 0x5A5A (canary 2).
 *  $FFD010: block A: VRAM $4020, 64 words (tiles 513-516, the first
 *          attract sprite patterns; sprite 0 Pat=4020 = tile 513)
 *  $FFD090: block B: VRAM $4680, 64 words (tiles 564-567; $123B0 loads
 *          $96120 rec 0, the font, at cursor 564)
 *  $FFD110: block C: VRAM $0000, 64 words (tiles 0-3)
 *  $FFD190: block D: VRAM $4920, 16 words (tile 585; $4E6 phase-2
 *          zero-upload target -- control, expect all zero)
 *  $FFD1B0: block E: VRAM $A000, 32 words (Plane A name table row 0)
 *  $FFD1F0: block F: VRAM $DC00, 16 words (sprite table, first 4)
 *  $FFD210: block G: RAM $FF1EC0, 16 words (decode buffer head)
 *  (ends $FFD230, below the $4E6 zero buffer at $FFD2EA.)
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
    move.w #0x5A5A, 0xFFD00E
    /* R15 = auto-increment 2 (already $02 in the $A14 layout; be safe) */
    move.w #0x8F02, 0xC00004
    lea 0xFFD004, %a0
    move.w 0xFFC002, (%a0)+
    move.w 0xFF0076, (%a0)+
    move.w 0xFF8640, (%a0)+
    move.w 0xFF8642, (%a0)+
    move.w 0xFF8644, (%a0)+
    lea 0xFFD010, %a0
    /* block A: VRAM $4020, 64 words (tiles 513-516) */
    move.l #0x4020, %d0
    moveq #63, %d1
    bsr vram_read
    /* block B: VRAM $4680, 64 words (tiles 564-567) */
    move.l #0x4680, %d0
    moveq #63, %d1
    bsr vram_read
    /* block C: VRAM $0000, 64 words (tiles 0-3) */
    move.l #0x0000, %d0
    moveq #63, %d1
    bsr vram_read
    /* block D: VRAM $4920, 16 words (tile 585, zero control) */
    move.l #0x4920, %d0
    moveq #15, %d1
    bsr vram_read
    /* block E: VRAM $A000, 32 words (name table row 0) */
    move.l #0xA000, %d0
    moveq #31, %d1
    bsr vram_read
    /* block F: VRAM $DC00, 16 words (sprite table, first 4) */
    move.l #0xDC00, %d0
    moveq #15, %d1
    bsr vram_read
    /* block G: RAM $FF1EC0, 16 words (decode buffer head) */
    movea.l #0xFF1EC0, %a1
    moveq #15, %d1
g_loop:
    move.w (%a1)+, (%a0)+
    dbra %d1, g_loop
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
 * word AT that address (verified live in #015) -- there is no dummy
 * word to discard. Clobbers d0/d2. */
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
