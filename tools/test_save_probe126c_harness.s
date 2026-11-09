/* Targeted probe 3 for issue #019: isolate the clear-path byte-126
 * anomaly. The clear harness left EEPROM[126]=0xFF after writing 128
 * zeros; probes 1-2 proved 126/127 are writable and that writing 0 to
 * 127 does not corrupt a 0x33 in 126, and that writing 0 to 126 works
 * when it held 0x33. This probe reproduces just the clear loop's TAIL:
 * write 0x00 to 126, then 0x00 to 127, then read 126.
 *
 * Same hook/padding pattern (hook at 0x35C, harness at 0xFD0CC,
 * results at $FFD004+, rts exits -- never jmp, #021 Q13).
 *
 * Result layout (words), base $FFD004:
 *  [ 0] EEPROM[126] after writing 0x00 to 126 then 0x00 to 127.
 *       0x00 = tail sequence is innocent (the full 0..127 run is the
 *       trigger); 0xFF = the 126-then-127 zero-write pair is the
 *       trigger.
 *  [ 1] EEPROM[127] after the same. Expect 0x00.
 *  [ 2] $FF014E final: expect 0
 *  [ 3] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
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

    /* write 0x00 to 126 */
    lea 0xFFD200, %a0
    move.b #0x00, (%a0)
    moveq #126, %d0
    jsr 0x430F4
    /* write 0x00 to 127 */
    lea 0xFFD200, %a0
    move.b #0x00, (%a0)
    moveq #127, %d0
    jsr 0x430F4

    /* [0] read back 126 */
    moveq #126, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+
    /* [1] read back 127 */
    moveq #127, %d0
    moveq #1, %d1
    lea 0xFFD210, %a0
    jsr 0x43012
    moveq #0, %d0
    move.b 0xFFD210, %d0
    move.w %d0, (%a5)+

    /* [2] $FF014E final */
    move.w 0xFF014E, (%a5)+

    /* canary check */
    cmpi.w #0x5A5A, 0xFFD0FE
    beq canary_ok
    move.w #0xDEAD, (%a5)+
    bra done
canary_ok:
    move.w #0xA5A5, (%a5)+
done:
    move.w 0xC00004, %d1
    rts
