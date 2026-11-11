/* Test harness for Rings of Power issue #112 (save family) follow-up:
 * boot-EEPROM probe. The boot harness (tools/test_save_boot_harness.s)
 * hooks the attract loop (0x35C), but by then vdp_ram_clear has already
 * wiped $FF016A, so the boot EEPROM state is unobservable at that
 * timing. This harness hooks the boot sequence itself, before
 * vdp_ram_clear runs, and snapshots $FF016A while it still holds the
 * image save_validate ($04323C) just read from the EEPROM.
 *
 * Hook point: $000312, the first instruction after save_validate
 * returns (jsr $4323C at $00030C) and strictly before vdp_ram_clear
 * (bsr.w $a14 at $000330). The instruction there is
 * `movea.l #$0, a7` (6 bytes: 2e7c 00000000), which fits the standard
 * 6-byte `jsr $FD0CC.l` hook. $000330 itself is a 4-byte bsr.w and
 * cannot take the 6-byte hook without clobbering the next instruction,
 * so the hook is at $000312 instead — same observable state, verified
 * by the #112 breakpoint at $000312 ($FF016A=FFFF right after the jsr
 * returns).
 *
 * Displaced-instruction note: `movea.l #$0, a7` sets the stack pointer
 * to 0, so the trampoline CANNOT rts (rts reads the return address
 * from (a7)). It replicates the displaced instruction and then
 * `jmp $000318.l` instead. This is safe here ONLY because the hook
 * fires once during boot: the single orphaned return address is
 * irrelevant once a7=0 (the game's own movea.l orphans the stack
 * anyway). Do NOT copy this jmp-exit pattern to a repeatedly-firing
 * hook — #021 Q13 (jmp leaks the jsr return address every hit).
 *
 * The probe itself does not use the stack (straight-line reads/writes
 * only), so a7=0 does not affect it. It saves/restores d0 and a5
 * (the only registers it clobbers) around the probe, before the
 * displaced instruction runs.
 *
 * Timing note: vdp_ram_clear (bsr at $000330, right after the hook
 * returns) wipes all of work RAM $FF0000-$FFFFDB, INCLUDING $FFD000.
 * The results below must be read at the $000318 breakpoint, before
 * continuing past $000330 — after that they are gone. The run script
 * does exactly that (break at the hook return, read, then continue to
 * confirm the game keeps running).
 *
 * Run with a FRESH blank EEPROM (delete the BlastEm save dir first),
 * so the expected values below are the blank-image ones. Run with the
 * SAME ROM filename as the run that wrote the EEPROM, so BlastEm loads
 * the persisted image.
 *
 * Result layout (words, in order), base $FFD004:
 *  [ 0] $FF0168: expect 0 (blank EEPROM leaves it 0)
 *  [ 1] $FF016A[0]: expect 0xFF (blank magic)
 *  [ 2] $FF016A[1]: expect 0xFF (blank parity)
 *  [ 3] $FF016A[2]: expect 0xFF (buffer is $FFFF throughout)
 *  [ 4] $FF016A[3]: expect 0xFF
 *  [ 5] $FF016A[64]: expect 0xFF (mid-buffer)
 *  [ 6] $FF016A[126]: expect 0xFF (tail)
 *  [ 7] $FF016A[127]: expect 0xFF (tail)
 *  [ 8] $FF014E: expect 0
 *  [ 9] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    bne run_tests
    /* already ran: displaced instruction, then jmp to $000318
     * (rts is impossible — see header; movea.l #$0,a7 kills the stack). */
    movea.l #0, %a7
    jmp 0x318
run_tests:
    movem.l %d0/%a5, -(%sp)
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE
    lea 0xFFD004, %a5

    /* ---- [0] $FF0168 ---- */
    move.w 0xFF0168, (%a5)+

    /* ---- [1..7] $FF016A bytes: 0, 1, 2, 3, 64, 126, 127 ---- */
    moveq #0, %d0
    move.b 0xFF016A, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016B, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A+2, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A+3, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A+64, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A+126, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF016A+127, %d0
    move.w %d0, (%a5)+

    /* ---- [8] $FF014E ---- */
    move.w 0xFF014E, (%a5)+

    /* ---- [9] canary check ---- */
    cmpi.w #0x5A5A, 0xFFD0FE
    beq canary_ok
    move.w #0xDEAD, (%a5)+
    bra done
canary_ok:
    move.w #0xA5A5, (%a5)+
done:
    movem.l (%sp)+, %d0/%a5
    /* displaced instruction, then jmp (rts impossible — see header). */
    movea.l #0, %a7
    jmp 0x318
