/* Text-grow harness for Rings of Power issue #18 (longer text).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called once from a
 * hook at 0x35C (attract loop top, replaces `move.w $C00004,d1`).
 * Calls the game's own text_word_expand ($0136FC) for rec 0 (grown by
 * +6 bytes) and rec 1 (control), reading ptr/len from the record table
 * at runtime, and stores the results as words at $FFD004 onwards.
 * Scratch: $FFD000-$FFD1FF. Out buffers $FFD100 (rec 0) and $FFD140
 * (rec 1). Results are read back with the BlastEm debugger.
 *
 * Build: m68k-linux-gnu-as -m68000 -o text_grow_harness.o tools/text_grow_harness.s
 *        m68k-linux-gnu-objcopy -O binary text_grow_harness.o text_grow_harness.bin
 * Inject: copy build/grown-rebuilt.gen to build/grown-test/harness.gen,
 *        write text_grow_harness.bin at 0xFD0CC, write jsr $FD0CC.l
 *        (4E B9 00 0F D0 CC) at 0x35C, fix both checksums with
 *        tools/checksum.py fix-all on a COPY (never the original).
 *
 * NOTE: GNU as (m68k-linux-gnu-as 2.42) wants %-prefixed registers
 * (%d0, %a5, %sp), no .l on absolute addresses, and no .s on branches.
 * text_word_expand preserves d4-d7/a3-a4 (movem) but clobbers
 * d0-d3/a0-a2; a5 is untouched, so the results pointer lives in a5.
 * Result slots are written by absolute address (no a5 arithmetic).
 *
 * Result layout (words), base $FFD004:
 *  $FFD004 [0] rec 0 rendered length (d0 from $136FC)  expect 35
 *  $FFD006 [1] rec 0 match count vs expected string   expect 35
 *  $FFD008 [2] rec 1 rendered length (control)        expect 48
 *  $FFD00A [3] rec 0 table len (as read from $DDBDC)  expect 12
 *  $FFD00C [4] rec 1 table len (as read from $DDBE6)  expect 20
 *  $FFD00E [5] canary flag: 0xA5A5 if $FFD0FE intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 * $FFD100 holds rec 0's rendered bytes (35), $FFD140 rec 1's (48).
 *
 * Expected rec 0 text: 'unknown building dark stone tower. '
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    bne run_tests
    /* already ran: displaced instruction, back to attract loop. */
    move.w 0xC00004, %d1
    rts
run_tests:
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE

    /* ---- rec 0: ptr/len from the record table ($DDBD8) ---- */
    move.l 0xDDBDC, %d6         /* rec 0 len (longword) */
    move.w %d6, 0xFFD00A        /* [3] rec 0 table len */
    move.l %d6, %d0
    lsr.l #1, %d0
    addq.l #1, %d0
    move.l %d0, -(%sp)          /* count = (len>>1)+1 */
    move.l #0xFFD100, -(%sp)    /* out_buffer */
    move.l 0xDDBD8, %d1         /* rec 0 ptr */
    add.l #0xE0A18, %d1         /* array_ptr = ARRAY_BASE + ptr */
    move.l %d1, -(%sp)
    jsr 0x136FC
    lea 12(%sp), %sp
    move.w %d0, 0xFFD004        /* [0] rec 0 rendered length */

    /* ---- compare rec 0 output ($FFD100) to expected (35 bytes) ---- */
    lea 0xFFD100, %a0
    lea expected0(%pc), %a1
    moveq #0, %d7               /* match count */
    moveq #34, %d6              /* 35 bytes: dbra 34..0 */
cmp0:
    move.b (%a0)+, %d0
    cmp.b (%a1)+, %d0
    bne cmp0_next
    addq.w #1, %d7
cmp0_next:
    dbra %d6, cmp0
    move.w %d7, 0xFFD006        /* [1] rec 0 match count */

    /* ---- rec 1 (control): ptr/len from $DDBE2/$DDBE6 ---- */
    move.l 0xDDBE6, %d6         /* rec 1 len */
    move.w %d6, 0xFFD00C        /* [4] rec 1 table len */
    move.l %d6, %d0
    lsr.l #1, %d0
    addq.l #1, %d0
    move.l %d0, -(%sp)          /* count */
    move.l #0xFFD140, -(%sp)    /* out_buffer */
    move.l 0xDDBE2, %d1         /* rec 1 ptr */
    add.l #0xE0A18, %d1
    move.l %d1, -(%sp)
    jsr 0x136FC
    lea 12(%sp), %sp
    move.w %d0, 0xFFD008        /* [2] rec 1 rendered length */

    /* ---- canary check ---- */
    cmpi.w #0x5A5A, 0xFFD0FE
    beq canary_ok
    move.w #0xDEAD, 0xFFD00E
    bra done
canary_ok:
    move.w #0xA5A5, 0xFFD00E
done:
    move.w 0xC00004, %d1
    rts

expected0:
    .ascii "unknown building dark stone tower. "
