/* Targeted probe 2 for issue #019: why did the clear harness leave
 * EEPROM[126]=0xFF? The first probe (test_save_probe126_harness.s)
 * proved 125/126/127 are writable and that writing 0x44 to 127 does
 * NOT corrupt a 0x33 in 126. The remaining suspects are the ZERO
 * value: either writing 0x00 to 126 itself fails, or writing 0x00 to
 * 127 corrupts a 0x00 in 126.
 *
 * Same hook/padding pattern (hook at 0x35C, harness at 0xFD0CC,
 * results at $FFD004+, rts exits -- never jmp, #021 Q13).
 *
 * Result layout (words), base $FFD004:
 *  [ 0] Case A: EEPROM[126] after writing 0x33 then 0x00 to 126.
 *       Expect 0x00 if writing zero to 126 works.
 *  [ 1] Case B: EEPROM[126] after writing 0x33 to 126 then 0x00 to
 *       127. Expect 0x33 if writing zero to 127 leaves 126 alone.
 *  [ 2] Case B': EEPROM[127] after writing 0x00 to 127. Expect 0x00.
 *  [ 3] $FF014E final: expect 0
 *  [ 4] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
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

    /* ---- Case A: write 0x33 to 126, then 0x00 to 126 ---- */
    lea 0xFFD200, %a0
    move.b #0x33, (%a0)
    moveq #126, %d0
    jsr 0x430F4
    lea 0xFFD200, %a0
    move.b #0x00, (%a0)
    moveq #126, %d0
    jsr 0x430F4
    /* [0] read back 126 */
    moveq #126, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+

    /* ---- Case B: write 0x33 to 126, then 0x00 to 127 ---- */
    lea 0xFFD200, %a0
    move.b #0x33, (%a0)
    moveq #126, %d0
    jsr 0x430F4
    lea 0xFFD200, %a0
    move.b #0x00, (%a0)
    moveq #127, %d0
    jsr 0x430F4
    /* [1] read back 126 */
    moveq #126, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+
    /* [2] read back 127 */
    moveq #127, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+

    /* ---- [3] $FF014E final ---- */
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
