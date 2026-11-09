/* Targeted probe for issue #019: is EEPROM address 126 writable in
 * BlastEm's I2C emulation, and does writing address 127 corrupt 126?
 * Background: the clear harness (test_save_clear_harness.s) wrote 128
 * zero bytes via $430F4 with $FF014E=0 (all verifies passed), yet the
 * re-read and the flushed save.eeprom both show EEPROM[126]=0xFF while
 * every other byte is 0. That makes the cleared image pass $4323C's
 * byte-sum check (errcount 0), not fail it (errcount 2) as predicted.
 * This probe isolates the mechanism.
 *
 * Same hook/padding pattern (hook at 0x35C, harness at 0xFD0CC,
 * results at $FFD004+, rts exits -- never jmp, #021 Q13).
 *
 * Result layout (words), base $FFD004:
 *  [ 0] EEPROM[126] after writing 0x33 to 126: expect 0x33 if 126 is
 *       writable in isolation
 *  [ 1] EEPROM[126] after writing 0x44 to 127: 0x33 if 127's write
 *       leaves 126 alone, 0xFF if it corrupts 126
 *  [ 2] EEPROM[127] after writing 0x44 to 127: expect 0x44
 *  [ 3] EEPROM[125] after writing 0x11 to 125: expect 0x11 (control)
 *  [ 4] $FF014E final: expect 0
 *  [ 5] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    bne run_tests
    /* already ran: displaced instruction, back to attract loop.
     * rts, NOT jmp 0x362 (#021 Q13). */
    move.w 0xC00004, %d1
    rts
run_tests:
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE
    lea 0xFFD004, %a5

    /* EEPROM init (as $4323C's entry does) */
    jsr 0x42FC8

    /* ---- write 0x33 to address 126 via $430F4 ---- */
    lea 0xFFD200, %a0
    move.b #0x33, (%a0)
    moveq #126, %d0
    jsr 0x430F4

    /* ---- [0] read back 126 via $43012 ---- */
    moveq #126, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+

    /* ---- write 0x44 to address 127 via $430F4 ---- */
    lea 0xFFD200, %a0
    move.b #0x44, (%a0)
    moveq #127, %d0
    jsr 0x430F4

    /* ---- [1] read back 126 again ---- */
    moveq #126, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+

    /* ---- [2] read back 127 ---- */
    moveq #127, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+

    /* ---- write 0x11 to address 125 (control) ---- */
    lea 0xFFD200, %a0
    move.b #0x11, (%a0)
    moveq #125, %d0
    jsr 0x430F4

    /* ---- [3] read back 125 ---- */
    moveq #125, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+

    /* ---- [4] $FF014E final ---- */
    move.w 0xFF014E, (%a5)+

    /* ---- canary check ---- */
    cmpi.w #0x5A5A, 0xFFD0FE
    beq canary_ok
    move.w #0xDEAD, (%a5)+
    bra done
canary_ok:
    move.w #0xA5A5, (%a5)+
done:
    move.w 0xC00004, %d1
    rts
