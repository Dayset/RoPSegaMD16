/* Test harness for Rings of Power issue #019 (save/SRAM validation).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called once from a
 * hook at 0x35C (attract loop top, replaces `move.w $C00004,d1`).
 * Runs the game's own save/load routines in the cold attract context
 * and stores every result as a word at $FFD004 onwards (results
 * pointer a5). Scratch: $FFD000-$FFD1FF and $FFD200-$FFD27F
 * (EEPROM re-read image, 128 bytes); canary-checked.
 * The game then continues to the title screen; results are read back
 * with the BlastEm debugger (`p/x $FFD0xx`).
 *
 * Build: m68k-linux-gnu-as -m68000 -o harness019.o test_save_harness.s
 *        m68k-linux-gnu-objcopy -O binary harness019.o harness019.bin
 * Inject: copy rop-original.gen to /tmp/ropre/test019.gen, write
 *        harness019.bin at 0xFD0CC, write jsr $FD0CC.l
 *        (4E B9 00 0F D0 CC) at 0x35C, then
 *        `python3 tools/checksum.py fix-all` (runtime first,
 *        header last) and verify with `verify-all`.
 *
 * NOTE: GNU as (m68k-linux-gnu-as 2.42) wants %-prefixed registers
 * (%d0, %a5, %sp), no .l on absolute addresses, and no .s on branches
 * (it picks branch sizes itself; several are >8-bit range).
 *
 * What it proves (static findings from the #019 trace):
 *  - $4323C's byte-sum check (byte[127]==sum, byte[126]==~sum, where
 *    sum is over bytes[0..125]) is INCOMPATIBLE with the real save
 *    format ($17706/$177B4: EEPROM[0]=0x2A magic, EEPROM[1]=parity,
 *    EEPROM[2..127]=$FFA800[0..125] bit-packed game state). A real,
 *    loadable save should FAIL $4323C's check while $FF0168 stays 0.
 *  - $2F11A (save) returns 0x48 on success; $2F896 (load) returns
 *    0x49 on success (both are $17706/$177B4 codes).
 *  - The packed tail: $FFA800[124]/[125] are the last $FF00C0 4-bit
 *    values (+0x80) plus spare bits; in the cold attract context
 *    ($FF00C0 all zero) the predicted tail is 0x11 / 0x80.
 *
 * Result layout (words, in order), base $FFD004:
 *  [ 0] $FF0168 at boot (pre-save): expect 0 (invalid checksum, no $B0)
 *  [ 1] boot $FF016A[0]: expect 0 (fresh EEPROM reads as zeros in BlastEm)
 *  [ 2] boot $FF016A[1]: expect 0
 *  [ 3] boot $FF016A[126]: expect 0
 *  [ 4] boot $FF016A[127]: expect 0
 *  [ 5] $2F11A return: expect 0x48 (72, success)
 *  [ 6] $FFA800[124]: expect 0x11 (predicted cold-attract tail)
 *  [ 7] $FFA800[125]: measured 0x00 (field math predicts 0x80; see
 *       docs/save.md §8.5 — the $FF00C0 table's attract contents vary)
 *  [ 8] $FFA800[0]: expect 0x00
 *  [ 9] $FFA800[1]: expect 0x00
 *  [10] $2F896 return: expect 0x49 (73, success)
 *  [11] EEPROM[0] re-read via $43012: expect 0x2A (magic)
 *  [12] EEPROM[1] re-read: parity byte (actual value recorded)
 *  [13] EEPROM[126] re-read: expect same as [6]
 *  [14] EEPROM[127] re-read: expect same as [7]
 *  [15] $4323C checksum-error count over the re-read EEPROM image:
 *       expect 3 (the valid save fails ALL THREE checks — the headline
 *       proof; docs/save.md §5)
 *  [16] $FF014E after the EEPROM writes/reads: expect 0
 *  [17] $FF0168 final: expect 0 (boot's value, untouched by save/load)
 *  [18] canary flag: 0xA5A5 if $FFD0FE canary intact else 0xDEAD
 * $FFD000 = 0xBEEF (harness ran). $FFD002 = 0xA5A5 (canary 1).
 *
 * Safety: the ran flag is set FIRST, before the long EEPROM writes,
 * so the hook (hit hundreds of times per frame on the attract VBlank
 * spin) cannot re-enter. The save/load calls run with $FF00AE forced
 * to 1 (both $2F11A and $2F896 require it, else 0x4C/0x4D). Slot 0
 * (the leader) is pinned to type 1 before $2F11A: $2C8F2 (which
 * $2F11A calls for the spell counts) errors via $12FA0(0x32) on any
 * other type, and $12FA0 calls $12072, which never returns in the
 * attract context. The leader/party state in cold attract is
 * otherwise all zeros, so the packed buffer is deterministic.
 * A minimal location record is fabricated for $2F896's $1C21A call
 * (see the note at the load): without it $1C83E divides by the word
 * at address 4 (0x0000) and the 68000 divide-by-zero exception
 * faults at PC=0 (no fault handlers in ROM).
 * $2F896's $25456 call cannot take the $12FA0(0x1C)->$12072 hang
 * path: the leader it creates via $23B84 has +0x00 low nibble != 0.
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    bne run_tests
    /* already ran: displaced instruction, back to attract loop.
     * rts, NOT jmp 0x362: the hook is `jsr $FD0CC`, which pushed 0x362
     * as the return address; jmp would leak 4 stack bytes per hook hit
     * (#021 Q13). rts returns to 0x362 and pops the address. */
    move.w 0xC00004, %d1
    rts
run_tests:
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD0FE
    lea 0xFFD004, %a5

    /* ---- save $FF00AE (input-mode flag), force it to 1 ---- */
    move.w 0xFF00AE, 0xFFD1A8
    move.w #1, 0xFF00AE

    /* ---- pin slot 0 (the leader, $FF02B2 = 0) to type 1 ----
     * $2F11A counts the leader's spells via $2C8F2($FF02B2, code).
     * $2C8F2 REQUIRES the slot to be type 1 or type 4: any other
     * type (0 in cold attract RAM) takes the $12FA0(0x32) error
     * path, which calls $12072, which waits on the VBlank flag
     * $FF0016 forever in the attract context (SR=$2700 masks the
     * VBlank interrupt) -- the harness hangs. Type 1 takes the
     * group-list path, which finds slot 0's +0x14..+0x1E words all
     * zero in cold RAM and returns 0 with no recursion. (Type 4
     * would NOT work here: its path requires the slot's rank
     * (+0x18 low nibble) to equal the category being counted, and
     * the save counts six different spell categories 1-6.)
     * Original +0x00 saved at $FFD1AA, restored at the end. */
    move.w 0xFF02B4, 0xFFD1AA
    move.w #1, 0xFF02B4

    /* ---- [0..4] boot state: $FF0168 + $FF016A bytes ---- */
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

    /* ---- [5] save via $2F11A (expects $FF00AE == 1) ---- */
    jsr 0x2F11A
    move.w %d0, (%a5)+

    /* ---- [6..9] packed buffer tail + head ---- */
    moveq #0, %d0
    move.b 0xFFA800+124, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFFA800+125, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFFA800, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFFA800+1, %d0
    move.w %d0, (%a5)+

    /* ---- [10] load back via $2F896 ---- */
    /* $2F896 calls $1C21A(6, X, Y) to place the leader, and $1C21A
     * mode 6 divides by the location record's words ($FFA7FC[0],
     * [2], and $1C83E's [4]/[6]). In real play $FFA7FC points at
     * the loaded location's record (set once at 0x1B74E); in the
     * cold attract context $FFA7FC is NULL, so $1C83E divides by the
     * word at address 4 (0x0000) -- a 68000 divide-by-zero, which
     * vectors through exception 5 at 0x14 (0: no fault handlers) and
     * faults at PC=0. So the harness fabricates a minimal location
     * record in scratch RAM ($FFD280) and points $FFA7FC at it:
     * [0]=[2]=0x100, [4]=[6]=0x10. This is a test fixture supplying
     * the precondition real play guarantees (a loaded location), not
     * a change to the save/load logic under test. Original $FFA7FC
     * saved at $FFD1B0, restored at the end. */
    move.l 0xFFA7FC, 0xFFD1B0
    move.w #0x100, 0xFFD280
    move.w #0x100, 0xFFD282
    move.w #0x10, 0xFFD284
    move.w #0x10, 0xFFD286
    move.w #0, 0xFFD28A
    move.w #0, 0xFFD28C
    lea 0xFFD280, %a0
    move.l %a0, 0xFFA7FC
    /* ---- free slot 0 and pin slot 1 type 1, before the load ----
     * $2F896 creates the leader via $23B84, which takes the first
     * free slot (+0x00 & 0xF == 0). Slot 0 must be free so the
     * leader lands in slot 0, as in real play (new-game init puts
     * the leader in slot 0, $FF02B2 = 0). If the leader landed in
     * slot 1 instead, its name index (+0x14 = 1, template 0 "Man")
     * would equal its own slot index, and $2C8F2's group-list path
     * (which recurses on every nonzero +0x14 word with NO rank
     * guard, unlike $2BBD2's guarded version) would recurse
     * $2C8F2(1) -> $2C8F2(1) -> ... forever. With the leader in
     * slot 0, the group loop follows +0x14 = 1 into slot 1, so slot
     * 1 is pinned to type 1 with +0x14..+0x1E all zero (cold RAM):
     * $2C8F2(1) then returns 0 after one level, and $2BBD2's rank
     * guard (slot 1 rank 0 != category) skips its recursion too.
     * Slot 1's original +0x00 saved at $FFD1B4, restored at the
     * end; slot 0 keeps the loaded leader (not restored). */
    move.w 0xFFD1AA, 0xFF02B4
    move.w 0xFF02E8, 0xFFD1B4
    move.w #1, 0xFF02E8
    /* ---- enable interrupts for the load ----
     * $2F896's tail calls $2EE2A (redraw after load), which waits
     * for a VBlank via $1386A (and $138A8, which also calls $1386A).
     * $1386A polls the VBlank flag $FF0016, which only the VBlank
     * handler clears -- and in the attract context SR=$2700 masks
     * VBlank interrupts, so $1386A spins forever (the same freeze
     * mechanism as $12072 in #008/#021). In real play SR=$2000 and
     * VBlanks fire, so $1386A returns promptly. The harness sets
     * SR=$2000 for the load (the VBlank handler only touches the
     * frame flag, the joypad ring and sound state -- none of the
     * harness results, the save buffer, or the char slots) and
     * restores SR=$2700 right after. */
    move.w #0x2000, %sr
    jsr 0x2F896
    move.w %d0, (%a5)+
    move.w #0x2700, %sr

    /* ---- re-read the EEPROM image via $43012 (d0=addr, d1=count, a0=buf) ---- */
    moveq #0, %d0
    move.l #128, %d1
    lea 0xFFD200, %a0
    jsr 0x43012

    /* ---- [11..14] re-read EEPROM bytes ---- */
    moveq #0, %d0
    move.b 0xFFD200, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFFD200+1, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFFD200+126, %d0
    move.w %d0, (%a5)+
    moveq #0, %d0
    move.b 0xFFD200+127, %d0
    move.w %d0, (%a5)+

    /* ---- [15] $4323C checksum-error count over the re-read image ----
     * Replicates $4323C (0x4327A-0x432A0): sum bytes[0..125] (low byte),
     * +1 if byte[127] != sum, +1 if byte[126] != ~sum, +1 if
     * byte[127] != ~byte[126]. */
    lea 0xFFD200, %a0
    moveq #0, %d0
    moveq #125, %d7
sum_loop:
    add.b (%a0)+, %d0
    dbra %d7, sum_loop
    moveq #0, %d1
    cmp.b 0xFFD200+127, %d0
    beq chk1ok
    addq.w #1, %d1
chk1ok:
    not.b %d0
    cmp.b 0xFFD200+126, %d0
    beq chk2ok
    addq.w #1, %d1
chk2ok:
    move.b 0xFFD200+126, %d2
    not.b %d2
    cmp.b 0xFFD200+127, %d2
    beq chk3ok
    addq.w #1, %d1
chk3ok:
    move.w %d1, (%a5)+

    /* ---- [16..17] $FF014E and final $FF0168 ---- */
    move.w 0xFF014E, (%a5)+
    move.w 0xFF0168, (%a5)+

    /* ---- restore $FF00AE, $FFA7FC, and slot 1's type ----
     * (slot 0 keeps the loaded leader, so it is NOT restored) */
    move.w 0xFFD1A8, 0xFF00AE
    move.l 0xFFD1B0, 0xFFA7FC
    move.w 0xFFD1B4, 0xFF02E8

    /* ---- canary check ---- */
    cmpi.w #0x5A5A, 0xFFD0FE
    beq canary_ok
    move.w #0xDEAD, (%a5)+
    bra done
canary_ok:
    move.w #0xA5A5, (%a5)+
done:
    /* displaced instruction, back to attract loop (rts, not jmp 0x362:
     * see the note at the "already ran" branch). */
    move.w 0xC00004, %d1
    rts
