/* Test harness for Rings of Power issue #019 (save/SRAM validation),
 * boot-report variant. Same hook/padding pattern as test_save_harness.s
 * (hook at 0x35C, harness at 0xFD0CC, results at $FFD004+, rts exits).
 * Reports what $4323C left behind after the boot read of whatever
 * EEPROM image BlastEm persisted from a previous run: $FF0168, the
 * $FF016A buffer's magic/tail bytes, and a recomputation of $4323C's
 * checksum-error count over $FF016A itself.
 *
 * Build/inject exactly like test_save_harness.s (same hook, same
 * fix-all order). Run with the SAME ROM filename as the run that
 * wrote the EEPROM, so BlastEm loads the persisted image.
 *
 * Result layout (words, in order), base $FFD004:
 *  [ 0] $FF0168: expect 0 in every case (blank EEPROM, valid save,
 *       cleared save all leave it 0 unless $B0 was held at boot)
 *  [ 1] $FF016A[0]: 0xFF blank / 0x2A valid save / 0x00 cleared save
 *  [ 2] $FF016A[1]: 0xFF blank / parity valid save / 0x00 cleared save
 *  [ 3] $FF016A[126]: 0xFF blank / tail valid save / 0x00 cleared save
 *  [ 4] $FF016A[127]: 0xFF blank / tail valid save / 0x00 cleared save
 *  [ 5] $4323C checksum-error count over $FF016A: expect 3 blank,
 *       1 or 2 valid save, 2 cleared save (never 0 on game-produced
 *       images: the check is inert for every state the game writes)
 *  [ 6] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    bne run_tests
    /* already ran: displaced instruction, back to attract loop.
     * rts, NOT jmp 0x362 (#021 Q13: jmp leaks the jsr return address
     * on every hook hit and faults the game at PC=0). */
    move.w 0xC00004, %d1
    rts
run_tests:
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE
    lea 0xFFD004, %a5

    /* ---- [0..4] $FF0168 + $FF016A bytes ---- */
    move.w 0xFF0168, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016B, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A+126, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A+127, %d0
    move.w %d0, (%a5)+

    /* ---- [5] $4323C checksum-error count over $FF016A ----
     * Same replication as in test_save_harness.s. */
    lea 0xFF016A, %a0
    moveq #0, %d0
    moveq #125, %d7
sum_loop:
    add.b (%a0)+, %d0
    dbra %d7, sum_loop
    moveq #0, %d1
    cmp.b 0xFF016A+127, %d0
    beq chk1ok
    addq.w #1, %d1
chk1ok:
    not.b %d0
    cmp.b 0xFF016A+126, %d0
    beq chk2ok
    addq.w #1, %d1
chk2ok:
    move.b 0xFF016A+126, %d2
    not.b %d2
    cmp.b 0xFF016A+127, %d2
    beq chk3ok
    addq.w #1, %d1
chk3ok:
    move.w %d1, (%a5)+

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
