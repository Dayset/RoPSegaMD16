/* Ground-truth harness for the $E358 Python port (issue #252, Track A).
 * Assembled for 0xFD0CC (unused 0xFF padding) and called from a hook at
 * 0x35C (attract loop top, replaces `move.w $C00004,d1`). One $E358 call
 * per frame (gated on the frame counter $FF0010), buffer $FF1EC0 zeroed
 * before each call, case index in $FFD002, $FFD000 = $CA5E when done.
 *
 * The game itself clears/uses $FF1EC0 later in the attract frame (the
 * original ROM's buffer reads all-zero during the title), so the live
 * buffer cannot be compared end-of-frame. Instead the harness
 * fingerprints the buffer IMMEDIATELY after the call and stores the
 * fingerprint + the args actually used in $FFD010+; the capture script
 * compares those against tools/e358.py. Fingerprint = two independent
 * 32-bit hashes over the 6,624 longwords (djb2-xor H1, rol/add H2 —
 * 64 bits combined). Full-buffer byte comparison is done separately
 * with the single-case halt variant (START_CASE/END_CASE defsyms),
 * which stops the CPU right after the call so the game never touches
 * the buffer.
 *
 * Build: python3 tools/build_e358_harness.py [--single N]
 *        (assembles with m68k-linux-gnu-as, injects at 0xFD0CC, jsr
 *        hook at 0x35C, checksum.py fix-all; output
 *        build/e358_harness.gen or build/e358_single_N.gen)
 * Run:   python3 tools/e358_capture.py [--single N ...]
 *        (stable-retro, compares each case, reports the exact-match
 *        rate; --single compares full buffers for the given cases)
 *
 * Results (words unless noted), base $FFD000:
 *   $FFD000 done flag ($CA5E when the sweep finished)
 *   $FFD002 case index (next case to run)
 *   $FFD004 last completed index + 1
 *   $FFD006 init flag ($BEEF once START_CASE has been loaded)
 *   $FFD008 last frame counter (long)
 *   $FFD010 H1 fingerprint (long)  $FFD014 H2 fingerprint (long)
 *   $FFD018 stream  $FFD01A d0arg  $FFD01C d1arg  $FFD01E d3arg
 *
 * Case list (4298 cases, index in $FFD002):
 *   Phase A  idx 0..3775:   all 944 streams x (d0,d3) in
 *        {(0x40,0),(0x42,0),(0x40,1),(0x42,1)}, d1=0 (the 2026-11-11
 *        dispatch sweep, regenerated: stream = idx>>2, sub = idx&3).
 *   Phase B  idx 3776..4285: 17 streams x d0 {0x54,0x80,0xE0} x d1
 *        {27,50,98,-1,-5} x d3 {0,1} — natural caller args
 *        (d0 84-224, d1 27-98 live in the Buc room; -1/-5 exercise
 *        the skip walk). Stream table + d0/d1 tables below.
 *   Phase C  idx 4286..4297: explicit edge cases (d1=-21/-22/-100,
 *        d1=200, d3=2/0xFFFF, d0=0/0x02 with LOG_D0 < 0 — the last
 *        two write below $FF0000 / into low RAM on real hardware,
 *        so they run last; see tools/e358.py for the model).
 *
 * Hook exit is `rts`, NOT jmp 0x362 (#021 Q13: jmp leaks the jsr return
 * address every hit and the stack plummets). The displaced instruction
 * `move.w $C00004,d1` runs before rts. The hook starts with
 * `move.w #0x2000,%sr` (maps.md freeze note: with interrupts masked
 * in cold boot the frame counter never advances).
 */
    .text
    .globl _start
    .ifndef START_CASE
    .set START_CASE, 0
    .endif
    .ifndef END_CASE
    .set END_CASE, 4298
    .endif
_start:
    move.w #0x2000, %sr
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    cmpi.w #0xBEEF, 0xFFD006
    beq have_init
    move.w #0xBEEF, 0xFFD006
    move.w #START_CASE, 0xFFD002
    move.l 0xFF0010, 0xFFD008
have_init:
    move.l 0xFF0010, %d0
    cmp.l 0xFFD008, %d0
    beq done_frame
    move.l %d0, 0xFFD008
    move.w 0xFFD002, %d1
    cmpi.w #END_CASE, %d1
    bge finished
    /* ---- compute case args: d2=stream, d3=d0arg, d4=d1arg, d5=d3arg ---- */
    cmpi.w #3776, %d1
    blt phase_a
    cmpi.w #4286, %d1
    blt phase_b
    /* phase C: edge table, 4 words/entry */
    move.w %d1, %d0
    subi.w #4286, %d0
    lsl.w #3, %d0
    lea edge_tab(%pc), %a1
    move.w (%a1,%d0.w), %d2
    move.w 2(%a1,%d0.w), %d3
    move.w 4(%a1,%d0.w), %d4
    move.w 6(%a1,%d0.w), %d5
    bra run_case
phase_a:
    move.w %d1, %d2
    lsr.w #2, %d2
    move.w %d1, %d6
    andi.w #3, %d6
    move.w %d6, %d5
    lsr.w #1, %d5
    move.w #0x40, %d3
    andi.w #1, %d6
    lsl.w #1, %d6
    add.w %d6, %d3
    moveq #0, %d4
    bra run_case
phase_b:
    moveq #0, %d0
    move.w %d1, %d0
    subi.w #3776, %d0
    divu.w #30, %d0
    move.w %d0, %d6
    lsl.w #1, %d6
    lea streams_b(%pc), %a1
    move.w (%a1,%d6.w), %d2
    swap %d0
    move.w %d0, %d6
    /* d0arg: (k//10) -> d0_tab */
    moveq #0, %d0
    move.w %d6, %d0
    divu.w #10, %d0
    move.w %d0, %d3
    lsl.w #1, %d3
    lea d0_tab(%pc), %a1
    move.w (%a1,%d3.w), %d3
    /* d1arg: ((k//2)%5) -> d1_tab */
    moveq #0, %d0
    move.w %d6, %d0
    lsr.w #1, %d0
    divu.w #5, %d0
    swap %d0
    move.w %d0, %d4
    lsl.w #1, %d4
    lea d1_tab(%pc), %a1
    move.w (%a1,%d4.w), %d4
    /* d3arg: k&1 */
    move.w %d6, %d5
    andi.w #1, %d5
run_case:
    /* record the args actually used (BEFORE the call: $E358 clobbers d2-d5) */
    move.w %d2, 0xFFD018
    move.w %d3, 0xFFD01A
    move.w %d4, 0xFFD01C
    move.w %d5, 0xFFD01E
    /* zero the decode buffer: 6624 longwords at $FF1EC0 */
    lea 0xFF1EC0, %a0
    moveq #0, %d0
    move.w #6623, %d7
zero_loop:
    move.l %d0, (%a0)+
    dbra %d7, zero_loop
    /* $E358(stream, d0, d1, d3): push d3, d1, d0, stream (stream last) */
    move.w %d5, -(%sp)
    move.w %d4, -(%sp)
    move.w %d3, -(%sp)
    move.w %d2, -(%sp)
    jsr 0xE358
    addq.w #8, %sp
    /* fingerprint the buffer now (H1 djb2-xor, H2 rol/add, over words) */
    lea 0xFF1EC0, %a0
    move.l #5381, %d1
    moveq #0, %d3
    move.w #6623, %d7
hash_loop:
    move.l (%a0)+, %d0
    move.l %d1, %d2
    lsl.l #5, %d2
    add.l %d2, %d1
    eor.l %d0, %d1
    rol.l #7, %d3
    eor.l %d0, %d3
    add.l #0x9E3779B9, %d3
    dbra %d7, hash_loop
    move.l %d1, 0xFFD010
    move.l %d3, 0xFFD014
    move.w 0xFFD002, %d0
    addq.w #1, %d0
    move.w %d0, 0xFFD002
    move.w %d0, 0xFFD004
    .if START_CASE + 1 == END_CASE
    /* single-case variant: halt here so the game never touches $FF1EC0 */
    move.w #0xCA5E, 0xFFD000
halt_loop:
    bra halt_loop
    .endif
    bra done_frame
finished:
    move.w #0xCA5E, 0xFFD000
done_frame:
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    move.w 0xC00004, %d1
    rts

streams_b:
    .dc.w 0, 1, 2, 5, 17, 100, 175, 176, 200, 288, 400, 500, 600, 700, 800, 900, 943
d0_tab:
    .dc.w 0x54, 0x80, 0xE0
d1_tab:
    .dc.w 27, 50, 98, -1, -5
edge_tab:
    .dc.w 0, 0x40, -21, 0
    .dc.w 0, 0x40, -22, 0
    .dc.w 0, 0x40, -100, 0
    .dc.w 0, 0x40, 200, 0
    .dc.w 0, 0x40, 200, 1
    .dc.w 943, 0x40, 0, 0
    .dc.w 943, 0x40, -1, 1
    .dc.w 500, 0x40, 0, 2
    .dc.w 500, 0x40, 0, 0xFFFF
    .dc.w 0, 0x00, 0, 0
    .dc.w 0, 0x02, 0, 1
    .dc.w 0, 0x40, 0, 0
