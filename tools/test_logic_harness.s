/* Test harness for Rings of Power issue #007 (game logic).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called once from a
 * hook at 0x35C (attract loop top, replaces `move.w $C00004,d1`).
 * Runs the game's own routines with crafted inputs and stores every
 * result as a word at $FFD004 onwards (results pointer a5).
 * Scratch: $FFD000-$FFD1FF (gap in the game's RAM map; canary-checked).
 * The game then continues to the title screen; results are read back
 * with the BlastEm debugger (`p/x $FFD0xx`).
 *
 * Build: m68k-linux-gnu-as -m68000 -o harness007.o test_logic_harness.s
 *        m68k-linux-gnu-objcopy -O binary harness007.o harness007.bin
 * Inject: copy rop-original.gen to /tmp/test007.gen, write harness007.bin
 *        at 0xFD0CC, write jsr $FD0CC.l (4E B9 00 0F D0 CC) at 0x35C,
 *        then `python3 tools/checksum.py fix-all` (runtime first,
 *        header last) and verify with `verify-all`.
 *
 * NOTE: GNU as (m68k-linux-gnu-as 2.42) wants %-prefixed registers
 * (%d0, %a5, %sp), no .l on absolute addresses, and no .s on branches
 * (it picks branch sizes itself; several are >8-bit range).
 *
 * Result layout (words, in order), base $FFD004:
 *  [ 0] $2F030 XP->level for XP = 0,99,100,199,200,399,400,799,800,
 *       1599,1600,3199,3200,6399,6400,12799,12800,13000   (18 words)
 *       expected levels [0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8]
 *       (level = smallest L with XP < 100*2^L; XP 12800+ -> level 8,
 *       NOT 7: 100*2^7 = 12800 is not > 12800. Max level is 8.)
 *  [18] $31958 max HP for level 0..8                        (9 words)
 *       expected [20,35,50,65,80,95,110,125,140]
 *  [27] $31946 max Power for level 0..7                    (8 words)
 *       expected [1000,2000,3000,4000,5000,6000,7000,8000]
 *       (level 8 -> 9000, confirmed by the XP test below)
 *  [35] $377FE isqrt for n = 0,1,2,3,4,5,20,25,30,100,10000,65025 (12)
 *       expected [0,1,1,2,2,2,4,5,5,10,100,255]
 *  [47] $3778E distance (0,0)-(3,4)                        (1 word)
 *       expected 5
 *  [48] RNG $12B82(19) x3, $12B82(7) x3 from seed 0        (6 words)
 *       expected [0,17,13,4,5,1] (glibc LCG, computed in Python)
 *  [54] gold: +0x2A after +500, after +20000 (cap), after -20000 (floor)
 *       expected [1500,15000,0]
 *  [57] XP: after +150: +0x1A, order-high, +0x20, +0x22   (4 words)
 *       expected [150,1,35,2000]
 *  [61] XP: after +13000: +0x1A, order-high, +0x20, +0x22 (4 words)
 *       expected [13000,8,140,9000] (XP 150+13000 caps at 13000 -> level 8)
 *  [65] damage D1..D7: each d0, target HP, $FFC380          (21 words)
 *       D1 order 0x00 base 60: [28,72,28]; D2 order 0x27: [6,94,6];
 *       D3 order 0x38: [8,92,8]; D4 order 0x49: [5,95,5];
 *       D5 $FF012C=0x8E: [70,30,70]; D6 $FF012C=0x97: [5,95,5];
 *       D7 immunity (+0x02=0x4D): [28,100,28]
 *  [86] price $2EA92(item 23, mod 0): no merchant, att 100, att 0 (3 words)
 *       expected [350,225,475] (item 23: w=86 -> v=(86-16)*5=350;
 *       att100: 350-50*350/140=225; att0: 350+50*350/140=475).
 *       NOTE: merchant-none is $FF02A0 = 0x00FF ($2EA92 compares the
 *       merchant word against 0xFF, not 0xFFFF). Item 2 was used first
 *       and returns 2 in all cases (its v is 0 -> floor clamp), so it
 *       does not discriminate the merchant paths; item 23 does.
 *  [89] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 *
 * Environment note: the harness runs at the attract loop, before any
 * new game — several game subsystems are uninitialized there. The XP
 * test initializes the message-queue header $FF0E18 to (0,0,7) first:
 * the level-up path calls $26B58 -> $1E3B0, which divides by
 * $FF0E18[2]; cold RAM holds 0 there, and the divide-by-zero (no fault
 * handlers in this ROM) freezes the machine. The header is saved and
 * restored around the test, and the message records the test queued
 * are scrubbed back to zero afterwards — otherwise the game's message
 * pump ($FF009A pending flag -> $26CCA -> $1E426, same divide-by-zero)
 * freezes the machine right after the harness returns. See
 * docs/logic.md for the full analysis.
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    bne run_tests
    /* already ran: displaced instruction, back to attract loop */
    move.w 0xC00004, %d1
    jmp 0x362
run_tests:
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE
    lea 0xFFD004, %a5

    /* ---- save char slots 0,1,2 (52 bytes each) ---- */
    lea 0xFF02B4, %a0
    lea 0xFFD100, %a1
    moveq #38, %d7              /* 39 longwords = 156 bytes (3 slots) */
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
    /* ---- zero party array (hermetic XP test) ---- */
    lea 0xFF0E82, %a0
    moveq #2, %d7
zero_party:
    clr.l (%a0)+
    dbra %d7, zero_party
    /* ---- pin party leader to slot 0 (gold/XP path needs -$6==leader) ---- */
    move.w 0xFF02B2, 0xFFD1A8
    move.w #0, 0xFF02B2
    /* ---- save msg-queue header $FF0E18 (24 bytes) + queue index $FFC324 ---- */
    lea 0xFF0E18, %a0
    lea 0xFFD1AA, %a1
    moveq #5, %d7
save_q:
    move.l (%a0)+, (%a1)+
    dbra %d7, save_q
    move.w 0xFFC324, 0xFFD1C2
    /* ---- save misc globals the tests clobber ---- */
    move.w 0xFF009A, 0xFFD1C4
    move.w 0xFFC37C, 0xFFD1C6
    move.w 0xFFC380, 0xFFD1C8
    move.w 0xFF02A0, 0xFFD1CA

    /* ---- 1. $2F030 XP -> level (table-driven) ---- */
    lea xp_table(%pc), %a0
    moveq #17, %d7              /* 18 entries */
xp_loop:
    move.w (%a0)+, -(%sp)
    jsr 0x2F030
    addq.w #2, %sp
    move.w %d0, (%a5)+
    dbra %d7, xp_loop

    /* ---- 2. $31958 max HP, level 0..8 ---- */
    moveq #0, %d6
hp_loop:
    move.w %d6, -(%sp)
    jsr 0x31958
    addq.w #2, %sp
    move.w %d0, (%a5)+
    addq.w #1, %d6
    cmpi.w #9, %d6
    bne hp_loop

    /* ---- 3. $31946 max Power, level 0..7 ---- */
    moveq #0, %d6
pw_loop:
    move.w %d6, -(%sp)
    jsr 0x31946
    addq.w #2, %sp
    move.w %d0, (%a5)+
    addq.w #1, %d6
    cmpi.w #8, %d6
    bne pw_loop

    /* ---- 4. $377FE isqrt (table-driven) ---- */
    lea sqrt_table(%pc), %a0
    moveq #11, %d7              /* 12 entries */
sqrt_loop:
    move.w (%a0)+, -(%sp)
    jsr 0x377FE
    addq.w #2, %sp
    move.w %d0, (%a5)+
    dbra %d7, sqrt_loop

    /* ---- setup damage structs (slots 0,1) ---- */
    /* attacker slot 0 at $FF02B4 */
    move.w #4, 0xFF02B4         /* +0x00 type 4 */
    move.w #0, 0xFF02B6         /* +0x02 = 0 (not immune) */
    move.w #100, 0xFF02D0       /* +0x1C cur HP */
    move.w #60, 0xFF02D4        /* +0x20 max HP */
    move.w #1000, 0xFF02D6      /* +0x22 max Power */
    move.w #0x0500, 0xFF02DC    /* +0x28: atk bits 6-10 = 20 */
    move.w #0x0200, 0xFF02E0    /* +0x2C: bits 8-9 = 2 */
    move.w #0, 0xFF02C0         /* +0x0C pos x */
    move.w #0, 0xFF02C2         /* +0x0E pos y */
    move.b #0, 0xFF02DB         /* +0x27 byte = 0 */
    /* target slot 1 at $FF02E8 */
    move.w #4, 0xFF02E8         /* +0x00 type 4 */
    move.w #0, 0xFF02EA         /* +0x02 = 0 */
    move.w #100, 0xFF0304       /* +0x1C cur HP */
    move.w #100, 0xFF0308       /* +0x20 max HP */
    move.w #1000, 0xFF030A      /* +0x22 max Power */
    move.w #0x5000, 0xFF0310    /* +0x28: def bits 11-15 = 10 */
    move.w #0x0100, 0xFF0314    /* +0x2C: bits 8-9 = 1 */
    move.w #3, 0xFF02F4         /* +0x0C pos x */
    move.w #4, 0xFF02F6         /* +0x0E pos y */
    move.b #0, 0xFF030F         /* +0x27 byte = 0 */

    /* ---- 5. $3778E distance (0,0)-(3,4) = 5 ---- */
    move.w #1, -(%sp)
    move.w #0, -(%sp)
    jsr 0x3778E
    addq.w #4, %sp
    move.w %d0, (%a5)+

    /* ---- 6. RNG from seed 0 ---- */
    clr.w 0xFF0072
    move.w #19, -(%sp)
    jsr 0x12B82
    addq.w #2, %sp
    move.w %d0, (%a5)+
    move.w #19, -(%sp)
    jsr 0x12B82
    addq.w #2, %sp
    move.w %d0, (%a5)+
    move.w #19, -(%sp)
    jsr 0x12B82
    addq.w #2, %sp
    move.w %d0, (%a5)+
    move.w #7, -(%sp)
    jsr 0x12B82
    addq.w #2, %sp
    move.w %d0, (%a5)+
    move.w #7, -(%sp)
    jsr 0x12B82
    addq.w #2, %sp
    move.w %d0, (%a5)+
    move.w #7, -(%sp)
    jsr 0x12B82
    addq.w #2, %sp
    move.w %d0, (%a5)+

    /* ---- 7. gold via $2BBD2 (slot 0, type 4, +0x27=0) ---- */
    move.w #1000, 0xFF02DE      /* +0x2A gold = 1000 */
    move.w #1, -(%sp)           /* flag */
    move.w #500, -(%sp)         /* value */
    move.w #0x400, -(%sp)       /* code gold */
    move.w #0, -(%sp)           /* char 0 */
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02DE, (%a5)+     /* expect 1500 */
    move.w #1, -(%sp)
    move.w #20000, -(%sp)
    move.w #0x400, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02DE, (%a5)+     /* expect 15000 (cap) */
    move.w #1, -(%sp)
    move.w #-20000, -(%sp)
    move.w #0x400, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02DE, (%a5)+     /* expect 0 (floor) */

    /* ---- 8. XP via $2BBD2 (slot 0) ---- */
    /* init msg-queue header $FF0E18 = (0,0,7): the level-up path calls
     * $26B58 -> $1E3B0, which DIVIDES BY $FF0E18[2]; cold RAM has 0 there
     * -> divide-by-zero -> exception with no handler -> machine freeze
     * (BlastEm reports a write to 0xDFFFFE). 7 makes $1E3B0 succeed
     * (q=2, writes stay inside $FF0E18+16). In real gameplay this header
     * is initialized before any XP grant can happen. */
    move.b #0, 0xFF0E18
    move.b #0, 0xFF0E19
    move.b #7, 0xFF0E1A
    move.w #0, 0xFF02CE         /* +0x1A XP = 0 */
    move.w #0, 0xFF02CC         /* +0x18 order = 0 */
    move.w #20, 0xFF02D4        /* +0x20 max HP = 20 */
    move.w #1000, 0xFF02D6      /* +0x22 max Power = 1000 */
    move.w #1, -(%sp)
    move.w #150, -(%sp)
    move.w #0x401, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02CE, (%a5)+     /* XP: expect 150 */
    move.w 0xFF02CC, %d0
    lsr.w #4, %d0
    andi.w #0xF, %d0
    move.w %d0, (%a5)+          /* level (order high): expect 1 */
    move.w 0xFF02D4, (%a5)+     /* max HP: expect 35 */
    move.w 0xFF02D6, (%a5)+     /* max Power: expect 2000 */
    move.w #1, -(%sp)
    move.w #13000, -(%sp)
    move.w #0x401, -(%sp)
    move.w #0, -(%sp)
    jsr 0x2BBD2
    addq.w #8, %sp
    move.w 0xFF02CE, (%a5)+     /* XP: expect 13000 (cap) */
    move.w 0xFF02CC, %d0
    lsr.w #4, %d0
    andi.w #0xF, %d0
    move.w %d0, (%a5)+          /* level: expect 7 */
    move.w 0xFF02D4, (%a5)+     /* max HP: expect 125 */
    move.w 0xFF02D6, (%a5)+     /* max Power: expect 8000 */

    /* ---- restore msg-queue header + index ---- */
    lea 0xFFD1AA, %a0
    lea 0xFF0E18, %a1
    moveq #5, %d7
restore_q:
    move.l (%a0)+, (%a1)+
    dbra %d7, restore_q
    move.w 0xFFD1C2, 0xFFC324

    /* ---- scrub the level-up message records the XP test queued ---- */
    /* $26B58 wrote record 1 (and maybe 2) at $FFBC94+210*n and set
     * $FF009A (message pending); the game's message pump would then call
     * $26CCA -> $1E426, which divides by $FF0E18[2] = 0 on cold RAM ->
     * freeze. Records were all zero before the test, so zero records 1
     * and 2 back (210 bytes each). */
    lea 0xFFBC94+210, %a0
    moveq #104, %d7
scrub1:
    clr.w (%a0)+
    dbra %d7, scrub1
    lea 0xFFBC94+420, %a0
    moveq #104, %d7
scrub2:
    clr.w (%a0)+
    dbra %d7, scrub2

    /* ---- 9. damage via $3B1EE ---- */
    /* D1: normal, order 0x00, base 60. expect d0=28, HP 72, $FFC380=28 */
    move.w #0, 0xFF02CC         /* att order = 0x00 */
    move.w #0, 0xFF012C         /* event code normal */
    bsr dmg_case
    /* D2: order low 7 (0x27): expect d0=(2+1)*2=6 */
    move.w #0x27, 0xFF02CC
    bsr dmg_case
    /* D3: order low 8 (0x38): expect d0=(3+1)*2=8 */
    move.w #0x38, 0xFF02CC
    bsr dmg_case
    /* D4: order low 9 (0x49): expect d0=4+1=5 */
    move.w #0x49, 0xFF02CC
    bsr dmg_case
    /* D5: special code 0x8E: expect d0=70 */
    move.w #0, 0xFF02CC
    move.w #0x8E, 0xFF012C
    bsr dmg_case
    /* D6: special code 0x97: expect d0=5 */
    move.w #0x97, 0xFF012C
    bsr dmg_case
    /* D7: immunity (att +0x27=0 -> struct[0].+0x02 = 0x4D): d0=28, HP stays */
    move.w #0, 0xFF012C
    move.w #0x4D, 0xFF02B6      /* struct[0].+0x02 = 0x4D */
    bsr dmg_case
    move.w #0, 0xFF02B6         /* clear immunity again */

    /* ---- 10. price via $2EA92 (item 23, modifier 0) ---- */
    /* item 23: w=86 -> scaled 350; att100 -> 225; att0 -> 475.
     * merchant-none is $FF02A0 = 0x00FF (code compares against 0xFF). */
    move.w #0x00FF, 0xFF02A0    /* no merchant */
    move.w #0, -(%sp)           /* modifier */
    move.w #23, -(%sp)          /* item */
    jsr 0x2EA92
    addq.w #4, %sp
    move.w %d0, (%a5)+
    /* merchant slot 2 at $FF031C, attitude 100 */
    move.w #0, 0xFF033C         /* +0x20 = 0 */
    move.w #100, 0xFF033E       /* +0x22 = 100 */
    move.w #2, 0xFF02A0         /* merchant = slot 2 */
    move.w #0, -(%sp)
    move.w #23, -(%sp)
    jsr 0x2EA92
    addq.w #4, %sp
    move.w %d0, (%a5)+
    /* merchant attitude 0 */
    move.w #0, 0xFF033E         /* +0x22 = 0 */
    move.w #0, -(%sp)
    move.w #23, -(%sp)
    jsr 0x2EA92
    addq.w #4, %sp
    move.w %d0, (%a5)+
    move.w #0x00FF, 0xFF02A0    /* clear merchant */

    /* ---- restore char slots 0,1,2 ---- */
    lea 0xFFD100, %a0
    lea 0xFF02B4, %a1
    moveq #38, %d7
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
    move.w 0xFFD1C4, 0xFF009A
    move.w 0xFFD1C6, 0xFFC37C
    move.w 0xFFD1C8, 0xFFC380
    move.w 0xFFD1CA, 0xFF02A0

    /* ---- canary check ---- */
    cmpi.w #0x5A5A, 0xFFD0FE
    beq canary_ok
    move.w #0xDEAD, (%a5)+
    bra done
canary_ok:
    move.w #0xA5A5, (%a5)+
done:
    /* displaced instruction, back to attract loop */
    move.w 0xC00004, %d1
    jmp 0x362

/* One damage case: reset target HP=100, $FFC37C=-1, $FFC380=0,
 * call $3B1EE(0, 1, 60), store d0, target HP, $FFC380. */
dmg_case:
    move.w #100, 0xFF0304       /* tgt +0x1C HP = 100 */
    move.w #-1, 0xFFC37C
    clr.w 0xFFC380
    move.w #60, -(%sp)
    move.w #1, -(%sp)
    move.w #0, -(%sp)
    jsr 0x3B1EE
    addq.w #6, %sp
    move.w %d0, (%a5)+
    move.w 0xFF0304, (%a5)+
    move.w 0xFFC380, (%a5)+
    rts

xp_table:
    .word 0, 99, 100, 199, 200, 399, 400, 799, 800
    .word 1599, 1600, 3199, 3200, 6399, 6400, 12799, 12800, 13000
sqrt_table:
    .word 0, 1, 2, 3, 4, 5, 20, 25, 30, 100, 10000, 65025
