/* Test harness for Rings of Power issue #019 (save/SRAM validation),
 * boot-report variant. Same hook/padding pattern as test_save_harness.s
 * (hook at 0x35C, harness at 0xFD0CC, results at $FFD004+, rts exits).
 * Reports what $4323C left behind after the boot read of whatever
 * EEPROM image BlastEm persisted from a previous run: $FF0168, the
 * $FF016A buffer's magic/tail bytes, and a recomputation of $4323C's
 * checksum-error count over $FF016A itself.
 *
 * TIMING: this harness hooks the attract loop (0x35C), which runs
 * AFTER vdp_ram_clear has zeroed all of work RAM (docs/logic-audit.md
 * §19: the clear is intended — movea.l #$FFFF0000,a0 is $FF0000 on
 * the 24-bit bus, $3FF7 longwords = 65,500 bytes). The clear zeroes
 * the $FF016A buffer that save_validate ($04323C) filled just before,
 * so at this hook $FF016A is ALWAYS zeros, whatever the EEPROM holds.
 * The per-case (blank / valid save / cleared save) distinctions below
 * are therefore UNREACHABLE at this timing: [1]-[4] are 0x00 and [5]
 * is 2 in every case. The boot EEPROM state itself is observable
 * only BEFORE the clear, at $000312 — see
 * tools/test_boot_eeprom_harness.s (PR #129): on a fresh blank
 * EEPROM $FF016A bytes 0/1/2/3/64/126/127 are all 0xFF, $FF0168 = 0,
 * $FF014E = 0.
 *
 * Build/inject exactly like test_save_harness.s (same hook, same
 * fix-all order). Run with the SAME ROM filename as the run that
 * wrote the EEPROM, so BlastEm loads the persisted image. Save runs
 * must delete the BlastEm save dir first (fresh zero EEPROM).
 *
 * Result layout (words, in order), base $FFD004 — measured dump on a
 * fresh blank EEPROM (#112 batch 3): 0000 0000 0000 0000 / 0000 0002 A5A5:
 *  [ 0] $FF0168: expect 0
 *  [ 1] $FF016A[0]: expect 0x00 (buffer wiped by vdp_ram_clear; the
 *       0xFF blank value is only observable pre-clear, at $000312)
 *  [ 2] $FF016A[1]: expect 0x00 (same)
 *  [ 3] $FF016A[126]: expect 0x00 (same)
 *  [ 4] $FF016A[127]: expect 0x00 (same)
 *  [ 5] $4323C checksum-error count over $FF016A: expect 2 (all-zero
 *       buffer: sum=0, byte[127]=0==sum ok; byte[126]=0 vs ~0=0xFF
 *       fail; byte[127]=0 vs ~byte[126]=0xFF fail)
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
