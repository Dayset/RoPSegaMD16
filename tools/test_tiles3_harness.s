/* Test harness #3 for Rings of Power issue #016 (packed-vs-planar paradox).
 * Snapshots the Plane A name table rows that hold the attract logo plus
 * the VRAM tiles the $147D0 installer would load for the logo ($96120
 * rec 12 at cursor 834), to identify which tiles the on-screen logo
 * actually uses and whether they match the $DD5C records (packed) or
 * their planar conversions.
 *
 * Hook at 0x35C, harness at 0xFD0CC. Snapshot once while 60 <= $FFC002
 * <= 70, flag 0xBEEF at $FFD000, canaries 0xA5A5/0x5A5A. Hook exit is
 * `rts` (never jmp -- #021 Q13).
 *
 * Result layout (words, base $FFD000):
 *  $FFD000 = 0xBEEF. $FFD002 = 0xA5A5. $FFD00E = 0x5A5A.
 *  $FFD004: $FFC002  $FFD006: $FF0076  $FFD008: $FF8640  $FFD00A: $FF8642
 *  $FFD010: name table $A240 (Plane A rows 9-17, 9*32=288 words)
 *  $FFD250: VRAM $6680 (tiles 834-835, 32 words)
 *  (ends $FFD290, below the $4E6 zero buffer at $FFD2EA.)
 */
    .text
    .globl _start
_start:
    cmpi.w #0xBEEF, 0xFFD000
    beq already_done
    move.w 0xFFC002, %d0
    cmpi.w #60, %d0
    blt not_yet
    cmpi.w #70, %d0
    bgt not_yet
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
    /* name table $A240 (rows 9-17), 288 words */
    move.l #0xA240, %d0
    move.w #287, %d1
    bsr vram_read
    /* VRAM $6680 (tiles 834-835), 32 words */
    move.l #0x6680, %d0
    move.w #31, %d1
    bsr vram_read
    movem.l (%sp)+, %d0-%d3/%a0-%a1
already_done:
    move.w 0xC00004, %d1
    rts
not_yet:
    move.w 0xC00004, %d1
    rts

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
