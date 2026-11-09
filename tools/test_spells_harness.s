/* Test harness for Rings of Power issue #008 (spells / skills).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called once from a
 * hook at 0x35C (attract loop top, replaces `move.w $C00004,d1`).
 * Runs the game's own spell routines with crafted inputs and stores
 * every result as a word at $FFD004 onwards (results pointer a5).
 * Scratch: $FFD000-$FFD1FF (gap in the game's RAM map; canary-checked).
 * The game then continues to the title screen; results are read back
 * with the BlastEm debugger (`p/x $FFD0xx`, breakpoint at 0).
 *
 * Build: m68k-linux-gnu-as -m68000 -o harness008.o test_spells_harness.s
 *        m68k-linux-gnu-objcopy -O binary harness008.o harness008.bin
 * Inject: copy rop-original.gen to /tmp/test008.gen, write harness008.bin
 *        at 0xFD0CC, write jsr $FD0CC.l (4E B9 00 0F D0 CC) at 0x35C,
 *        then `python3 tools/checksum.py fix-all` (runtime first,
 *        header last) and verify with `verify-all`.
 *
 * NOTE: GNU as (m68k-linux-gnu-as 2.42) wants %-prefixed registers
 * (%d0, %a5, %sp), no .l on absolute addresses, and no .s on branches
 * (it picks branch sizes itself; several are >8-bit range).
 *
 * Result layout (words, in order), base $FFD004:
 *  [ 0..5] S1A $3A62E melee (+0x24=0): $FF012C,$FF012A,$FFC418,$FFC41A,
 *       tgt HP, $FFC380. expect [0,0,-1,-1,72,28]
 *  [ 6..11] S1B $3A62E special (+0x24=0x50): same 6.
 *       expect [0x50,1,1,0,100,0]
 *  [12..17] S1C $3A62E spell code 0x8E: expect [0x8E,1,1,0,100,0]
 *  [18..23] S1D $3A62E spell code 0x7D: expect [0x7D,1,1,0,100,0]
 *  [24] S2 $3C2C0 cost, rec19 mod0: expect 3000 (1000*1*3)
 *  [25] S2 $3C2C0 cost, rec19 mod1: expect 6000 (1000*2*3)
 *  [26] S2 $3C2C0 cost, rec0  mod3: expect 0    (0*4*3)
 *  [27..30] S3a $37D0E deduct rec19 mod0, Pwr 5000: +0x1E,+0x1C,$FFC37C,
 *       $FF012C. expect [2000,100,-1,0x91] ($FFC37C is -1: the $37D0E
 *       tail unconditionally overwrites the 0x7777 sentinel with -1)
 *  [31..34] S3b $37D0E deduct rec19 mod1, Pwr 9000:
 *       expect [3000,100,-1,0x91]
 *  [35..38] S3c $37D0E out-of-power rec19 mod1, Pwr 5000, HP 100:
 *       expect [0,95,-1,0x91] (Power 0, HP -5)
 *  [39] S4a $3B6C0(0) link chain -> expect 5
 *  [40] S4b $3B748(0) target pick, mod3 -> expect 2 (farthest member)
 *  [41..42] S4c $3B51E(0) full path: slot0.+0x2C, $FF012C.
 *       expect [0x0B02,0]
 *  [43] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 *
 * Environment notes: the harness runs at the attract loop, before any
 * new game. The rank-pointer table $FFA7CC..$FFA7F0 is cold (0) there,
 * and $37D0E/$3C2C0/$3B748 read the spell record through it, so the
 * harness installs the new-game table (same 10 pointers as 0x1B5F4)
 * and restores it afterwards. The message-queue header $FF0E18 is
 * initialised to (0,0,7) defensively, as in the #007 harness, and
 * restored. $3A62E's melee path calls $17586(-1) (sound) and $23AE0;
 * $37D0E's tail calls $25456 twice. $25456 is NOT contained: when
 * struct.+0x00 & 0xF == 0 it calls $12FA0(0x1C) -> $12072 (sound), which
 * never returns in the cold attract context. setup_spell therefore
 * resets slot 0 (+0x00 = 4) before every $37D0E case; S1's dispatches
 * leave +0x00 = 0xA0, which is what stalled the first harness runs.
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
    /* ---- save $FFA7CC rank table (10 longs) at $FFD060 ---- */
    lea 0xFFA7CC, %a0
    lea 0xFFD060, %a1
    moveq #9, %d7
save_ranktab:
    move.l (%a0)+, (%a1)+
    dbra %d7, save_ranktab
    /* ---- save msg-queue header $FF0E18 (24 bytes) at $FFD088 ---- */
    lea 0xFF0E18, %a0
    lea 0xFFD088, %a1
    moveq #5, %d7
save_q:
    move.l (%a0)+, (%a1)+
    dbra %d7, save_q
    /* ---- save misc globals at $FFD0A0 (12 words) ---- */
    move.w 0xFF0EAA, 0xFFD0A0
    move.w 0xFF012A, 0xFFD0A2
    move.w 0xFF012C, 0xFFD0A4
    move.w 0xFFC418, 0xFFD0A6
    move.w 0xFFC41A, 0xFFD0A8
    move.w 0xFFC37C, 0xFFD0AA
    move.w 0xFFC380, 0xFFD0AC
    move.w 0xFF009A, 0xFFD0AE
    move.w 0xFF010E, 0xFFD0B0
    move.w 0xFF0130, 0xFFD0B2
    move.w 0xFF02B2, 0xFFD0B4
    move.w 0xFF0072, 0xFFD0B6
    /* ---- save $FFB0CC enemy record (12 bytes) at $FFD0B8 ---- */
    lea 0xFFB0CC, %a0
    lea 0xFFD0B8, %a1
    moveq #2, %d7
save_enemy:
    move.l (%a0)+, (%a1)+
    dbra %d7, save_enemy
    /* ---- save S4 spot fields at $FFD0C4 (10 words) ---- */
    move.w 0xFF0330, 0xFFD0C4    /* slot2.+0x14 */
    move.w 0xFF0376, 0xFFD0C6    /* slot3.+0x26 (as word) */
    move.w 0xFF03CC, 0xFFD0C8    /* slot5.+0x14 */
    move.w 0xFF03CE, 0xFFD0CA    /* slot5.+0x16 */
    move.w 0xFF03D0, 0xFFD0CC    /* slot5.+0x18 */
    move.w 0xFF03D2, 0xFFD0CE    /* slot5.+0x1A */
    move.w 0xFF03D4, 0xFFD0D0    /* slot5.+0x1C */
    move.w 0xFF03D6, 0xFFD0D2    /* slot5.+0x1E */
    move.w 0xFF03E4, 0xFFD0D4    /* slot5.+0x2C */
    move.w 0xFF03E0, 0xFFD0D6    /* slot5.+0x28/+0x29 (group link byte) */

    /* ---- install rank table (new-game values, 0x1B5F4) ---- */
    move.l #0xD6B6C, 0xFFA7CC
    move.l #0xD6BEA, 0xFFA7D0
    move.l #0xD6C68, 0xFFA7D4
    move.l #0xD6CE6, 0xFFA7D8
    move.l #0xD6D64, 0xFFA7DC
    move.l #0xD6DE2, 0xFFA7E0
    move.l #0xD6BEA, 0xFFA7E4
    move.l #0xD6BEA, 0xFFA7E8
    move.l #0xD6BEA, 0xFFA7EC
    move.l #0xD6BEA, 0xFFA7F0
    /* ---- init msg-queue header (0,0,7), RNG seed 0 ---- */
    move.b #0, 0xFF0E18
    move.b #0, 0xFF0E19
    move.b #7, 0xFF0E1A
    clr.w 0xFF0072

    /* ---- S1: $3A62E dispatch, 4 cases ---- */
    /* S1A melee: +0x24 = 0 */
    bsr setup_combat
    move.w #0, 0xFF02D8         /* att +0x24 = 0 */
    bsr dispatch_case
    /* S1B special: +0x24 = 0x50 */
    bsr setup_combat
    move.w #0x50, 0xFF02D8
    bsr dispatch_case
    /* S1C spell code 0x8E */
    bsr setup_combat
    move.w #0x8E, 0xFF02D8
    bsr dispatch_case
    /* S1D spell code 0x7D */
    bsr setup_combat
    move.w #0x7D, 0xFF02D8
    bsr dispatch_case

    /* ---- S2: $3C2C0 cost formula ---- */
    move.w #0, 0xFF0EAA         /* actor = slot 0 */
    move.w #0x11, 0xFF02CC      /* slot0 +0x18 rank 1 */
    move.b #19, 0xFF02D9        /* slot0 +0x25 = 19 (byte) */
    move.w #0, 0xFF02E0         /* slot0 +0x2C mod 0 */
    move.l #0xD6BDE, -(%sp)     /* rank1 rec 19 */
    jsr 0x3C2C0
    addq.w #4, %sp
    move.w %d0, (%a5)+          /* expect 3000 */
    move.w #0x0100, 0xFF02E0    /* mod 1 */
    move.l #0xD6BDE, -(%sp)
    jsr 0x3C2C0
    addq.w #4, %sp
    move.w %d0, (%a5)+          /* expect 6000 */
    move.w #0x0300, 0xFF02E0    /* mod 3 */
    move.b #0, 0xFF02D9         /* +0x25 = 0 */
    move.l #0xD6B6C, -(%sp)     /* rank1 rec 0 (w4 = 0) */
    jsr 0x3C2C0
    addq.w #4, %sp
    move.w %d0, (%a5)+          /* expect 0 */

    /* ---- S3: $37D0E Power deduction ---- */
    /* S3a: rec19 mod0, Power 5000/9000, HP 100 */
    bsr setup_spell
    move.w #5000, 0xFF02D2      /* slot0 +0x1E cur Power */
    move.w #9000, 0xFF02D6      /* slot0 +0x22 max Power */
    move.w #100, 0xFF02D0       /* slot0 +0x1C cur HP */
    move.w #0, 0xFF02E0         /* mod 0 */
    bsr deduct_case             /* expect 2000,100,0x7777,0x91 */
    /* S3b: rec19 mod1, Power 9000 */
    bsr setup_spell
    move.w #9000, 0xFF02D2
    move.w #9000, 0xFF02D6
    move.w #100, 0xFF02D0
    move.w #0x0100, 0xFF02E0    /* mod 1 */
    bsr deduct_case             /* expect 3000,100,0x7777,0x91 */
    /* S3c: rec19 mod1, Power 5000 (out of power: HP -5) */
    bsr setup_spell
    move.w #5000, 0xFF02D2
    move.w #9000, 0xFF02D6
    move.w #100, 0xFF02D0
    move.w #0x0100, 0xFF02E0    /* mod 1 */
    bsr deduct_case             /* expect 0,95,-1,0x91 */

    /* ---- S4a: $3B6C0 link chain ---- */
    /* chain: slot0.+0x27=1 -> slot1.+0x29=2 -> slot2.+0x14=3
     * -> slot3.+0x26=5 (alive) */
    move.b #1, 0xFF02DB         /* slot0 +0x27 */
    move.b #2, 0xFF0311         /* slot1 +0x29 */
    move.w #3, 0xFF0330         /* slot2 +0x14 */
    move.b #5, 0xFF0376         /* slot3 +0x26 */
    move.w #0, 0xFF03E4         /* slot5 +0x2C alive */
    move.w #0, -(%sp)
    jsr 0x3B6C0
    addq.w #2, %sp
    move.w %d0, (%a5)+          /* expect 5 */

    /* ---- S4b: $3B748 target pick ---- */
    /* group = slot 5, members [1,2,3] at (3,4),(6,8),(0,5); caster (0,0) */
    bsr setup_combat
    move.b #5, 0xFF02DB         /* slot0 +0x27 = group 5 */
    move.w #0x0B00, 0xFF02E0    /* slot0 +0x2C: status 2, mod 3 */
    move.b #0, 0xFF02D9         /* slot0 +0x25 = 0 (rec 0) */
    move.w #1, 0xFF03CC         /* slot5 +0x14 = 1 */
    move.w #2, 0xFF03CE         /* slot5 +0x16 = 2 */
    move.w #3, 0xFF03D0         /* slot5 +0x18 = 3 */
    move.w #0, 0xFF03D2
    move.w #0, 0xFF03D4
    move.w #0, 0xFF03D6
    move.b #5, 0xFF03E1         /* slot5 +0x29 = 5 (group self-link):
                                 * rec 0 bit 11 is clear, so $3B748 takes
                                 * group = struct[5].+0x29; cold RAM (0)
                                 * sent it to struct[0]'s words instead */
    move.w #100, 0xFF0304       /* slot1 HP */
    move.w #100, 0xFF0338       /* slot2 HP (+0x1C at $FF031C+0x1C) */
    move.w #100, 0xFF036C       /* slot3 HP (+0x1C at $FF0350+0x1C) */
    move.w #6, 0xFF0328         /* slot2 x (+0x0C at $FF031C+0x0C) */
    move.w #8, 0xFF032A         /* slot2 y */
    move.w #0, 0xFF035C         /* slot3 x */
    move.w #5, 0xFF035E         /* slot3 y */
    move.w #0, 0xFF0348         /* slot2 +0x2C alive ($FF031C+0x2C) */
    move.w #0, 0xFF037C         /* slot3 +0x2C alive ($FF0350+0x2C) */
    move.w #0, -(%sp)
    jsr 0x3B748
    addq.w #2, %sp
    move.w %d0, (%a5)+          /* expect 2 (farthest member) */

    /* ---- S4c: $3B51E full path ---- */
    /* same setup as S4b, but caster +0x02 = 0x6E so $3BB4E returns 0
     * deterministically (and sets +0x25 = 19; rec19 bit11=0, eff 6,
     * mod 3 -> still picks farthest member 2) */
    bsr setup_combat
    move.b #5, 0xFF02DB         /* slot0 +0x27 = group 5 */
    move.w #0x0B00, 0xFF02E0    /* slot0 +0x2C: status 2, mod 3 */
    move.w #0x6E, 0xFF02B6      /* slot0 +0x02 = 0x6E */
    move.w #1, 0xFF03CC
    move.w #2, 0xFF03CE
    move.w #3, 0xFF03D0
    move.w #0, 0xFF03D2
    move.w #0, 0xFF03D4
    move.w #0, 0xFF03D6
    move.b #5, 0xFF03E1         /* slot5 +0x29 = 5 (group self-link, as S4b) */
    move.w #100, 0xFF0304
    move.w #100, 0xFF0338
    move.w #100, 0xFF036C
    move.w #6, 0xFF0328
    move.w #8, 0xFF032A
    move.w #0, 0xFF035C
    move.w #5, 0xFF035E
    move.w #0, 0xFF0314
    move.w #0, 0xFF037C         /* slot3 +0x2C at $FF0350+0x2C */
    move.w #0, 0xFF012C
    move.w #0, -(%sp)
    jsr 0x3B51E
    addq.w #2, %sp
    move.w 0xFF02E0, (%a5)+     /* slot0 +0x2C: expect 0x0B02 */
    move.w 0xFF012C, (%a5)+     /* expect 0 */

    /* ---- restore char slots 0,1 ---- */
    lea 0xFFD100, %a0
    lea 0xFF02B4, %a1
    moveq #25, %d7
restore_slots:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_slots
    /* ---- restore S4 spot fields ---- */
    move.w 0xFFD0C4, 0xFF0330
    move.w 0xFFD0C6, 0xFF0376
    move.w 0xFFD0C8, 0xFF03CC
    move.w 0xFFD0CA, 0xFF03CE
    move.w 0xFFD0CC, 0xFF03D0
    move.w 0xFFD0CE, 0xFF03D2
    move.w 0xFFD0D0, 0xFF03D4
    move.w 0xFFD0D2, 0xFF03D6
    move.w 0xFFD0D4, 0xFF03E4
    move.w 0xFFD0D6, 0xFF03E0    /* slot5.+0x28/+0x29 */
    /* ---- restore $FFB0CC enemy record ---- */
    lea 0xFFD0B8, %a0
    lea 0xFFB0CC, %a1
    moveq #2, %d7
restore_enemy:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_enemy
    /* ---- restore rank table ---- */
    lea 0xFFD060, %a0
    lea 0xFFA7CC, %a1
    moveq #9, %d7
restore_ranktab:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_ranktab
    /* ---- restore msg-queue header ---- */
    lea 0xFFD088, %a0
    lea 0xFF0E18, %a1
    moveq #5, %d7
restore_q:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_q
    /* ---- restore misc globals ---- */
    move.w 0xFFD0A0, 0xFF0EAA
    move.w 0xFFD0A2, 0xFF012A
    move.w 0xFFD0A4, 0xFF012C
    move.w 0xFFD0A6, 0xFFC418
    move.w 0xFFD0A8, 0xFFC41A
    move.w 0xFFD0AA, 0xFFC37C
    move.w 0xFFD0AC, 0xFFC380
    move.w 0xFFD0AE, 0xFF009A
    move.w 0xFFD0B0, 0xFF010E
    move.w 0xFFD0B2, 0xFF0130
    move.w 0xFFD0B4, 0xFF02B2
    move.w 0xFFD0B6, 0xFF0072

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

/* One $3A62E dispatch case: reset $FF012C/$FF012A/$FFC418/$FFC41A/
 * $FFC37C/$FFC380, target HP=100, enemy record zeroed; call $3A62E(0);
 * store $FF012C, $FF012A, $FFC418, $FFC41A, target HP, $FFC380. */
dispatch_case:
    move.w #0, 0xFF012C
    move.w #0, 0xFF012A
    move.w #-1, 0xFFC418
    move.w #-1, 0xFFC41A
    move.w #-1, 0xFFC37C
    clr.w 0xFFC380
    move.w #100, 0xFF0304       /* tgt +0x1C HP = 100 */
    clr.w 0xFFB0CC
    clr.w 0xFFB0CE
    clr.w 0xFFB0D0
    clr.w 0xFFB0D2
    clr.w 0xFFB0D4
    clr.w 0xFFB0D6
    move.w #0, -(%sp)
    jsr 0x3A62E
    addq.w #2, %sp
    move.w 0xFF012C, (%a5)+
    move.w 0xFF012A, (%a5)+
    move.w 0xFFC418, (%a5)+
    move.w 0xFFC41A, (%a5)+
    move.w 0xFF0304, (%a5)+
    move.w 0xFFC380, (%a5)+
    rts

/* Setup for $37D0E cases: actor slot 0, rank 1, spell rec 19.
 * MUST reset the whole slot first: S1's $3A62E dispatches mutate
 * slot0.+0x00 (left at 0xA0 after S1D, low nibble 0), and $37D0E's
 * tail calls $25456, which takes its $12FA0(0x1C) -> $12072 sound
 * branch whenever struct.+0x00 & 0xF == 0 -- $12072 never returns
 * in the cold attract context, so the harness stalled inside S3a
 * (bisected 2026-11-09: $3C2C0 returns, $25456 #1 never returns).
 * setup_combat restores +0x00 = 4 (low nibble != 0, $12FA0 skipped).
 * +0x04 is forced to 0 (not setup_combat's 0xFF) so the tail's
 * $25DE4/$2140A pair indexes enemy record 0, which the harness
 * saves/restores, instead of the bogus 0xFF slot ($FFBCC0). */
setup_spell:
    bsr setup_combat
    move.w #0, 0xFF02B8      /* +0x04 = 0: contained $2140A index */
    move.w #0, 0xFF0EAA
    move.w #0x11, 0xFF02CC      /* +0x18 rank 1 */
    move.b #19, 0xFF02D9        /* +0x25 = 19 (byte) */
    move.w #0, 0xFF012C
    move.w #0x7777, 0xFFC37C
    rts

/* One $37D0E case: call $37D0E(0); store +0x1E, +0x1C, $FFC37C, $FF012C. */
deduct_case:
    move.w #0, -(%sp)
    jsr 0x37D0E
    addq.w #2, %sp
    move.w 0xFF02D2, (%a5)+     /* +0x1E cur Power */
    move.w 0xFF02D0, (%a5)+     /* +0x1C cur HP */
    move.w 0xFFC37C, (%a5)+
    move.w 0xFF012C, (%a5)+
    rts

/* Full combat setup: attacker slot 0 at (0,0), target slot 1 at (3,4).
 * Attacker: type 4, +0x04=0xFF (dodges $210D8 in $23AE0), +0x18=0x11,
 * +0x1E=1 (target idx), +0x20=60, +0x22=0 (caster idx), +0x28 atk 20,
 * +0x2C mod 2. Target: type 4, +0x04=0, +0x28 def 10, +0x2C mod 1. */
setup_combat:
    /* attacker slot 0 at $FF02B4 */
    move.w #4, 0xFF02B4         /* +0x00 type 4 */
    move.w #0, 0xFF02B6         /* +0x02 = 0 */
    move.w #0xFF, 0xFF02B8      /* +0x04 = 0xFF */
    move.w #0, 0xFF02BA         /* +0x06 */
    move.w #0, 0xFF02BC         /* +0x08 */
    move.w #0, 0xFF02BE         /* +0x0A */
    move.w #0, 0xFF02C0         /* +0x0C x */
    move.w #0, 0xFF02C2         /* +0x0E y */
    move.w #0, 0xFF02C4         /* +0x10 */
    move.w #0, 0xFF02C6         /* +0x12 */
    move.w #0, 0xFF02C8         /* +0x14 name */
    move.w #0, 0xFF02CA         /* +0x16 */
    move.w #0x11, 0xFF02CC      /* +0x18 rank 1 */
    move.w #0, 0xFF02CE         /* +0x1A XP */
    move.w #100, 0xFF02D0       /* +0x1C cur HP */
    move.w #1, 0xFF02D2         /* +0x1E = target idx 1 */
    move.w #60, 0xFF02D4        /* +0x20 max HP */
    move.w #0, 0xFF02D6         /* +0x22 = caster idx 0 */
    move.w #0, 0xFF02D8         /* +0x24 selector (set by caller) */
    move.b #0, 0xFF02D9         /* +0x25 spell idx */
    move.b #0, 0xFF02DA         /* +0x26 */
    move.b #0, 0xFF02DB         /* +0x27 */
    move.w #0x0500, 0xFF02DC    /* +0x28 atk 20 */
    move.w #0, 0xFF02DE         /* +0x2A */
    move.w #0x0200, 0xFF02E0    /* +0x2C mod 2 */
    move.w #0, 0xFF02E2         /* +0x2E */
    move.w #0, 0xFF02E4         /* +0x30 */
    move.w #0, 0xFF02E6         /* +0x32 */
    /* target slot 1 at $FF02E8 */
    move.w #4, 0xFF02E8         /* +0x00 type 4 */
    move.w #0, 0xFF02EA         /* +0x02 = 0 */
    move.w #0, 0xFF02EC         /* +0x04 = 0 */
    move.w #0, 0xFF02EE
    move.w #0, 0xFF02F0
    move.w #0, 0xFF02F2
    move.w #3, 0xFF02F4         /* +0x0C x */
    move.w #4, 0xFF02F6         /* +0x0E y */
    move.w #0, 0xFF02F8
    move.w #0, 0xFF02FA
    move.w #0, 0xFF02FC
    move.w #0, 0xFF02FE
    move.w #0x11, 0xFF0300      /* +0x18 rank 1 */
    move.w #0, 0xFF0302
    move.w #100, 0xFF0304       /* +0x1C cur HP */
    move.w #1000, 0xFF0306      /* +0x1E cur Power */
    move.w #100, 0xFF0308       /* +0x20 max HP */
    move.w #1000, 0xFF030A      /* +0x22 max Power */
    move.w #0, 0xFF030C         /* +0x24 */
    move.b #0, 0xFF030D         /* +0x25 */
    move.b #0, 0xFF030E         /* +0x26 */
    move.b #0, 0xFF030F         /* +0x27 */
    move.w #0x5000, 0xFF0310    /* +0x28 def 10 */
    move.w #0, 0xFF0312         /* +0x2A */
    move.w #0x0100, 0xFF0314    /* +0x2C mod 1 */
    move.w #0, 0xFF0316
    move.w #0, 0xFF0318
    move.w #0, 0xFF031A
    rts
