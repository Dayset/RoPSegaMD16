/* Test harness #4 for Rings of Power issue #016 (packed-vs-planar paradox).
 * Snapshots AFTER the L-installers have run ($FF8640 != 0 means $147D0 or
 * $123B0 has done its first $11A7C tile upload), capturing the VRAM
 * tiles those installers load ($96120 rec 36/12 at cursor 564/834,
 * or rec 0 at 564) plus the Plane A name table rows under the logo.
 * This catches the $DD5C record tiles in VRAM in the intro/story phase
 * (the attract-phase snapshot in harness #1/#3 was too early: the name
 * table was still blank and only the generated sprite tiles were up).
 *
 * Hook at 0x1272 (VBlank handler entry, `move.w #$0,$FF0016`),
 * harness at 0xFD0CC. Snapshot once when $FF8640 != 0, flag 0xBEEF
 * at $FFD000, canaries 0xA5A5/0x5A5A.
 *
 * Why VBlank ($1272) and not the attract loop (0x35C, the original
 * hook) or main_loop ($D28E, the first redesign):
 * - 0x35C: the trigger ($FF8640 != 0) and the attract loop are
 *   mutually exclusive. $FF8640 is written only inside window_down
 *   ($01245E), called from intro_story_driver, called from
 *   game_dispatch -- i.e. AFTER the attract loop is exited (frame
 *   ~230). The 0x35C hook stops firing at exactly the moment the
 *   trigger becomes true, so the harness as written could never
 *   snapshot on either build (#112 batch 3).
 * - $D28E (first redesign): main_loop is entered after
 *   intro_story_driver, so $FF8640 is set when it first fires -- but
 *   the game NEVER REACHES main_loop in debugger mode without input
 *   (verified: original ROM, no hook, $D292 breakpoint never fires
 *   in 150 s; the shift-test reach check proves it only in batch
 *   mode). The $D292 hook is dead in the debugger. The intro waits
 *   for input (or a long timeout) and main_loop is never entered.
 * - $1272 (this redesign): the VBlank handler fires EVERY frame in
 *   every phase (attract, intro, gameplay) -- verified live: a $1272
 *   breakpoint fires once per frame for 400+ frames, and $FF8640
 *   flips 0000 -> 0234 at step ~267, after which the handler keeps
 *   firing. The harness checks $FF8640 on every VBlank and snapshots
 *   on the first VBlank after the write. The logo tiles are in VRAM
 *   by frame 81 (tiles2), so they are present at frame ~268.
 *
 * Interrupt-context note: $1272 is entered via the VBlank interrupt,
 * so the trampoline must NOT use `rts` (that is for jsr hooks, #021
 * Q13). It replicates the hooked `move.w #$0,$FF0016`, does the
 * snapshot check, and jumps back into the handler at $127A, which
 * continues normally and returns via `rte` at the handler's end.
 * This is the debug overlay's proven $1272 hook pattern. The
 * snapshot does VDP reads from interrupt context (one-shot); a
 * transient VDP-address disturbance is acceptable for a harness.
 * The `jmp $127A` is an absolute ROM address and shifts (+0x100 in
 * the shifted build); build_tiles4.py shifts it (see its header).
 *
 * Result layout (words, base $FFD000):
 *  $FFD000 = 0xBEEF. $FFD002 = 0xA5A5. $FFD00E = 0x5A5A.
 *  $FFD004: $FFC002  $FFD006: $FF0076  $FFD008: $FF8640  $FFD00A: $FF8642
 *  $FFD010: VRAM $4680 (tiles 564-567, 64 words)
 *  $FFD090: VRAM $6680 (tiles 834-837, 64 words)
 *  $FFD110: name table $A240 (Plane A rows 9-12, 128 words)
 *  (ends $FFD210, below the $4E6 zero buffer at $FFD2EA.)
 */
    .text
    .globl _start
_start:
    /* replicate the hooked instruction first (clears $FF0016) */
    move.w #0, 0xFF0016
    cmpi.w #0xBEEF, 0xFFD000
    beq done
    /* snapshot once the installers have run */
    tst.w 0xFF8640
    beq done
    movem.l %d0-%d3/%a0-%a1, -(%sp)
    move.w #0xBEEF, 0xFFD000
    move.w #0xA5A5, 0xFFD002
    move.w #0x5A5A, 0xFFD00E
    move.w #0x8F02, 0xC00004
    lea 0xFFD004, %a0
    move.w 0xFFC002, (%a0)+
    move.w 0xFF0076, (%a0)+
    move.w 0xFF8640, (%a0)+
    move.w 0xFF8642, (%a0)+
    lea 0xFFD010, %a0
    /* VRAM $4680 (tiles 564-567), 64 words */
    move.l #0x4680, %d0
    moveq #63, %d1
    bsr vram_read
    /* VRAM $6680 (tiles 834-837), 64 words */
    move.l #0x6680, %d0
    moveq #63, %d1
    bsr vram_read
    /* name table $A240 (rows 9-12), 128 words */
    move.l #0xA240, %d0
    move.w #127, %d1
    bsr vram_read
    movem.l (%sp)+, %d0-%d3/%a0-%a1
done:
    jmp 0x127A

/* vram_read: a0 = dest (words), d0 = VRAM byte address, d1 = count-1.
 * First read after setting the address returns the word AT that address
 * (verified live in #015) -- no dummy word. Clobbers d0/d2. */
vram_read:
    move.w %d0, %d2
    andi.w #0x3FFF, %d0
    move.w %d0, 0xC00004
    move.w %d2, %d0
    rol.w #2, %d0
    andi.w #3, %d0
    move.w %d0, 0xC00004
vr_loop:
    move.w 0xC00000, (%a0)+
    dbra %d1, vr_loop
    rts
