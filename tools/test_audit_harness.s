/* Test harness for Rings of Power issue #021 (logic-flaw audit).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called once from a
 * hook at 0x35C (attract loop top, replaces `move.w $C00004,d1`).
 * Runs the game's own routines with crafted inputs and stores every
 * result as a word at $FFD004 onwards (results pointer a5).
 * Scratch: $FFD000-$FFD1FF (gap in the game's RAM map; canary-checked).
 * The game then continues to the title screen; results are read back
 * with the BlastEm debugger (`p/x $FFD0xx`).
 *
 * Build: m68k-linux-gnu-as -m68000 -o harness021.o test_audit_harness.s
 *        m68k-linux-gnu-objcopy -O binary harness021.o harness021.bin
 * Inject: copy rop-original.gen to /tmp/test021.gen, write harness021.bin
 *        at 0xFD0CC, write jsr $FD0CC.l (4E B9 00 0F D0 CC) at 0x35C,
 *        then `python3 tools/checksum.py fix-all` (runtime first,
 *        header last) and verify with `verify-all`.
 *
 * NOTE: GNU as (m68k-linux-gnu-as 2.42) wants %-prefixed registers
 * (%d0, %a5, %sp), no .l on absolute addresses, and no .s on branches
 * (it picks branch sizes itself; several are >8-bit range).
 *
 * Result layout (words, in order), base $FFD004:
 *  [ 0] gold: 15000 + 17767 -> expect 15000 (32767, no overflow, capped)
 *  [ 1] gold: 15000 + 17768 -> expect 0 (32768, signed overflow -> 0)
 *  [ 2] gold: 14000 + 20000 -> expect 0 (34000, signed overflow -> 0)
 *  [ 3] gold: 15000 + 20000 -> expect 0 (35000, signed overflow -> 0)
 *       ($2C474 clamps with SIGNED compares: a 16-bit sum > 32767 wraps
 *       negative, skips the 15000 cap (ble taken on the wrapped value),
 *       then the floor check (tst/bge) zeroes it.)
 *  [ 4] neg damage d0: atk 0, def 31, base 140, mods 0/3, rank 1
 *       expect -6 (0xFFFA): 0+140-135+0+0-26 = -21; -21/3+1 = -6
 *  [ 5] neg damage target HP: expect 106 (100 - (-6): the hit HEALS)
 *  [ 6] neg damage $FFC380: expect -6
 *  [ 7] ctrl damage d0 (same, target mod 0): expect 2 (140-135=5; 5/3+1)
 *  [ 8] ctrl damage target HP: expect 98
 *  [ 9] ctrl damage $FFC380: expect 2
 *  [10] $3B4AC(0x87D) -> $FF012C: expect 0x87D (full word stored, no mask)
 *  [11] $3B4AC(0x08E) -> $FF012C: expect 0x08E
 *  [12] $3B4AC guard: $FF012C was 7, arg 0x50 -> expect 7 (refused)
 *  [13..18] $1350 pops, ring [11,22,33,44], head=4 tail=0:
 *       expect [0x11,0x22,0x33,0x44,0x44,0x44] (empty -> last value)
 *  [19] $FF001A head after test 1: expect 4
 *  [20] $FF001B tail after test 1: expect 4
 *  [21..23] $1350 wrap pops, tail=15 head=1, ring[15]=AA ring[0]=BB:
 *       expect [0xAA,0xBB,0xBB]
 *  [24] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 *
 * Environment note: the gold test needs slot 0 as type 4 with +0x27=0
 * (same setup as #007) and the leader pinned to slot 0. The $1350
 * test saves/restores the joypad ring ($FF001A/$FF001B/$FF001C/$FF002C).
 * $1350 sets SR=$2000 on exit (enables interrupts); that is the
 * routine's own behaviour, not the harness's.
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    bne run_tests
    /* already ran: displaced instruction, back to attract loop.
     * rts, NOT jmp 0x362: the hook is `jsr $FD0CC`, which pushed 0x362
     * as the return address; jmp would leak 4 stack bytes per hook hit,
     * and the hook sits at 0x35C (the attract loop's VBlank spin target),
     * so the stack plummets into RAM and the game faults at PC=0 in ~3 s
     * (#021 Q13). rts returns to 0x362 and pops the address: no leak. */
    move.w 0xC00004, %d1
    rts
run_tests:
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE
    lea 0xFFD004, %a5

    /* ---- save char slots 0,1 (52 bytes each) ---- */
    lea 0xFF02B4, %a0
    lea 0xFFD100, %a1
    moveq #25, %d7              /* 26 longwords = 104 bytes (2 slots) */
save_slots:
    move.l (%a0)+, (%a1)+
    dbra %d7, save_slots
    /* ---- save party array $FF0E82 (12 bytes) ---- */
    lea 0xFF0E82, %a0
    lea 0xFFD19C, %a1
    moveq #2, %d7
save_party:
    move.l (%a0)+, (%a1)+
    dbra %d7, save_party
    /* ---- zero party array (hermetic gold test) ---- */
    lea 0xFF0E82, %a0
    moveq #2, %d7
zero_party:
    clr.l (%a0)+
    dbra %d7, zero_party
    /* ---- pin party leader to slot 0 ---- */
    move.w 0xFF02B2, 0xFFD1A8
    move.w #0, 0xFF02B2
    /* ---- save misc globals the tests clobber ---- */
    move.w 0xFF012C, 0xFFD1AA
    move.w 0xFFC37C, 0xFFD1AC
    move.w 0xFFC380, 0xFFD1AE
    move.w 0xFF02A0, 0xFFD1B0
    /* ---- save joypad ring state ---- */
    move.b 0xFF001A, 0xFFD1B2
    move.b 0xFF001B, 0xFFD1B3
    move.b 0xFF002C, 0xFFD1B4
    lea 0xFF001C, %a0
    lea 0xFFD1B6, %a1
    moveq #3, %d7
save_ring:
    move.l (%a0)+, (%a1)+
    dbra %d7, save_ring

    /* ---- setup damage structs (slots 0,1) ---- */
    /* attacker slot 0 at $FF02B4 */
    move.w #4, 0xFF02B4         /* +0x00 type 4 */
    move.w #0, 0xFF02B6         /* +0x02 = 0 (not immune) */
    move.w #100, 0xFF02D0       /* +0x1C cur HP */
    move.w #140, 0xFF02D4       /* +0x20 max HP (also the damage base) */
    move.w #1000, 0xFF02D6      /* +0x22 max Power */
    move.w #0x0000, 0xFF02DC    /* +0x28: atk bits 6-10 = 0 */
    move.w #0x0000, 0xFF02E0    /* +0x2C: bits 8-9 = 0 */
    move.w #0, 0xFF02C0         /* +0x0C pos x */
    move.w #0, 0xFF02C2         /* +0x0E pos y */
    move.b #0, 0xFF02DB         /* +0x27 byte = 0 */
    move.w #0x01, 0xFF02CC      /* +0x18 order: rank 1, level 0 */
    /* target slot 1 at $FF02E8 */
    move.w #4, 0xFF02E8         /* +0x00 type 4 */
    move.w #0, 0xFF02EA         /* +0x02 = 0 */
    move.w #100, 0xFF0304       /* +0x1C cur HP */
    move.w #100, 0xFF0308       /* +0x20 max HP */
    move.w #1000, 0xFF030A      /* +0x22 max Power */
    move.w #0xF800, 0xFF0310    /* +0x28: def bits 11-15 = 31 */
    move.w #0x0300, 0xFF0314    /* +0x2C: bits 8-9 = 3 */
    move.w #3, 0xFF02F4         /* +0x0C pos x */
    move.w #4, 0xFF02F6         /* +0x0E pos y */
    move.b #0, 0xFF030F         /* +0x27 byte = 0 */

    /* ---- 1. gold overflow boundary via $2BBD2 (code 0x400) ---- */
    move.w #15000, 0xFF02DE     /* +0x2A gold = 15000 */
    move.w #1, -(%sp)
    move.w #17767, -(%sp)
    move.w #0x400, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02DE, (%a5)+     /* expect 15000 */
    move.w #15000, 0xFF02DE
    move.w #1, -(%sp)
    move.w #17768, -(%sp)
    move.w #0x400, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02DE, (%a5)+     /* expect 0 */
    move.w #14000, 0xFF02DE
    move.w #1, -(%sp)
    move.w #20000, -(%sp)
    move.w #0x400, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02DE, (%a5)+     /* expect 0 */
    move.w #15000, 0xFF02DE
    move.w #1, -(%sp)
    move.w #20000, -(%sp)
    move.w #0x400, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02DE, (%a5)+     /* expect 0 */

    /* ---- 2. negative damage (heal) via $3B1EE(0, 1, 140) ---- */
    move.w #100, 0xFF0304       /* tgt HP = 100 */
    move.w #-1, 0xFFC37C
    clr.w 0xFFC380
    move.w #0, 0xFF012C
    move.w #140, -(%sp)
    move.w #1, -(%sp)
    move.w #0, -(%sp)
    jsr 0x3B1EE
    addq.w #6, %sp
    move.w %d0, (%a5)+          /* expect -6 */
    move.w 0xFF0304, (%a5)+     /* expect 106 */
    move.w 0xFFC380, (%a5)+     /* expect -6 */

    /* ---- 3. control damage (target mod 0) ---- */
    move.w #0x0000, 0xFF0314    /* tgt +0x2C mod = 0 */
    move.w #100, 0xFF0304
    move.w #-1, 0xFFC37C
    clr.w 0xFFC380
    move.w #140, -(%sp)
    move.w #1, -(%sp)
    move.w #0, -(%sp)
    jsr 0x3B1EE
    addq.w #6, %sp
    move.w %d0, (%a5)+          /* expect 2 */
    move.w 0xFF0304, (%a5)+     /* expect 98 */
    move.w 0xFFC380, (%a5)+     /* expect 2 */
    move.w #0x0300, 0xFF0314    /* restore tgt mod = 3 */

    /* ---- 4. $3B4AC action-code install ---- */
    move.w #0, 0xFF012C
    move.w #0x87D, -(%sp)
    jsr 0x3B4AC
    addq.w #2, %sp
    move.w 0xFF012C, (%a5)+     /* expect 0x87D */
    move.w #0x08E, -(%sp)
    jsr 0x3B4AC
    addq.w #2, %sp
    move.w 0xFF012C, (%a5)+     /* expect 0x08E */
    move.w #7, 0xFF012C
    move.w #0x50, -(%sp)
    jsr 0x3B4AC
    addq.w #2, %sp
    move.w 0xFF012C, (%a5)+     /* expect 7 (refused while == 7) */

    /* ---- 5. $1350 joypad-queue pop ---- */
    /* ring [11,22,33,44], head=4 tail=0, last=0x99 */
    move.b #4, 0xFF001A
    move.b #0, 0xFF001B
    move.b #0x99, 0xFF002C
    move.b #0x11, 0xFF001C
    move.b #0x22, 0xFF001D
    move.b #0x33, 0xFF001E
    move.b #0x44, 0xFF001F
    moveq #5, %d7
pop_loop:
    jsr 0x1350
    move.w %d0, (%a5)+
    dbra %d7, pop_loop
    /* head/tail after: expect 4, 4 */
    moveq #0, %d0
    move.b 0xFF001A, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFF001B, %d0
    move.w %d0, (%a5)+
    /* wrap test: tail=15 head=1, ring[15]=AA ring[0]=BB */
    move.b #1, 0xFF001A
    move.b #15, 0xFF001B
    move.b #0xBB, 0xFF001C
    move.b #0xAA, 0xFF002B      /* $FF001C+15 */
    moveq #2, %d7
pop_wrap:
    jsr 0x1350
    move.w %d0, (%a5)+
    dbra %d7, pop_wrap

    /* ---- restore char slots 0,1 ---- */
    lea 0xFFD100, %a0
    lea 0xFF02B4, %a1
    moveq #25, %d7
restore_slots:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_slots
    /* ---- restore party array ---- */
    lea 0xFFD19C, %a0
    lea 0xFF0E82, %a1
    moveq #2, %d7
restore_party:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_party
    /* ---- restore party leader ---- */
    move.w 0xFFD1A8, 0xFF02B2
    /* ---- restore misc globals ---- */
    move.w 0xFFD1AA, 0xFF012C
    move.w 0xFFD1AC, 0xFFC37C
    move.w 0xFFD1AE, 0xFFC380
    move.w 0xFFD1B0, 0xFF02A0
    /* ---- restore joypad ring state ---- */
    move.b 0xFFD1B2, 0xFF001A
    move.b 0xFFD1B3, 0xFF001B
    move.b 0xFFD1B4, 0xFF002C
    lea 0xFFD1B6, %a0
    lea 0xFF001C, %a1
    moveq #3, %d7
restore_ring:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_ring

    /* ---- canary check ---- */
    cmpi.w #0x5A5A, 0xFFD0FE
    beq canary_ok
    move.w #0xDEAD, (%a5)+
    bra done
canary_ok:
    move.w #0xA5A5, (%a5)+
done:
    /* displaced instruction, back to attract loop (rts, not jmp 0x362:
     * see the note at the "already ran" branch — jmp leaks the jsr's
     * return address on every hook hit and faults the game at PC=0). */
    move.w 0xC00004, %d1
    rts
