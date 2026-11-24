#!/usr/bin/env python3
"""Build probe ROMs for RoP issue #273 (NPC locations), scratch only.

Probe hooks VBlank ($1272) like the blind-spot cutscene probes, waits 120
frames for the game (slot_0 state) to settle, then runs one test:

  MODE 0 (recon):   snapshot the 56 char structs once, spin. No forge/call.
  MODE 1 (enter):   forge $FF0E92/$FF0E98/$FF0E16, clear seen ring, set the
                    event bitmap, snapshot before, JSR world_enter_location
                    ($03090A), snapshot after, spin.
  MODE 2 (timing):  log (frame, $FF0E16, $FF00AC, $FF02A2) every 10 frames
                    for 600 frames, spin.

Log layout at $FFD800 (words):
  +0x00 magic 0x5A31 | +0x02 start frame | +0x04 phase | +0x06 done
  +0x08 test_id | +0x0A frame at test | +0x0C mode $FF00AE | +0x0E $FF0E92
  +0x10 $FF0E98 | +0x12 $FF0E16 (after) | +0x14 $FFC408 (after)
  +0x16 before_count | +0x18 after_count (mode 2: timing record count)
  records at $FFD820: mode 0/1: 16 words each
    [slot, +0x00, +0x02, +0x06, +0x0A, +0x0C, +0x0E, +0x14, +0x16, +0x18,
     +0x1C, +0x1E, +0x20, +0x22, +0x24, +0x26]
  mode 2: 4 words each [frame, $FF0E16, $FF00AC, $FF02A2]

Usage: build_probe_273.py <name> <mode> <anchor> <nibble> <dest> <time16>
  e.g. build_probe_273.py t170 1 170 3 29 0
  e.g. build_probe_273.py recon 0 0 0 0 0
  e.g. build_probe_273.py tclock 2 0 0 0 0
"""
import hashlib, os, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(HERE, "scratch-273")
ORIG = os.path.join(HERE, "rop-original.gen")
CHECKSUM = os.path.join(HERE, "tools", "checksum.py")
PAD_BASE = 0xFD400
HOOK_SITE = 0x1272
HOOK_ORIG = bytes.fromhex("33fc000000ff0016")

ASM_TEMPLATE = r"""
    .text
    .globl _start
_start:
    move.w #0, 0xFF0016
    movem.l %d0-%d7/%a0-%a6, -(%sp)
    bsr probe_tick
    movem.l (%sp)+, %d0-%d7/%a0-%a6
    jmp 0x00127A

    .equ LOG, 0xFFD800
    .equ TEST_ID, {test_id}
    .equ MODE, {mode}
    .equ LOCWORD, {locword}
    .equ NIBBLE, {nibble}
    .equ DEST, {dest}
    .equ TIME16, {time16}

probe_tick:
    cmpi.w #0x5A31, LOG
    beq .pt_valid
    move.w #0x5A31, LOG
    move.w 0xFF0012, LOG+2
    clr.w LOG+4
    clr.w LOG+6
    move.w #TEST_ID, LOG+8
    clr.w LOG+0x0A
    clr.w LOG+0x0C
    clr.w LOG+0x0E
    clr.w LOG+0x10
    clr.w LOG+0x12
    clr.w LOG+0x14
    clr.w LOG+0x16
    clr.w LOG+0x18
    move.w #MODE, LOG+0x1A
    rts
.pt_valid:
    move.w LOG+6, %d0
    cmpi.w #1, %d0
    beq test_spin
    cmpi.w #2, %d0
    bne .pt_cont
    move.w 0xFF0012, %d0
    sub.w LOG+0x1C, %d0
    cmpi.w #90, %d0
    bge test_spin
    rts
.pt_cont:
    move.w 0xFF0012, %d0
    sub.w LOG+2, %d0
    cmpi.w #120, %d0
    blt .pt_done
    .if MODE == 2
    bra .pt_timing
    .endif
    tst.w LOG+4
    bne .pt_done
    move.w #1, LOG+4
    move.w 0xFF0012, LOG+0x0A
    move.w 0xFF00AE, LOG+0x0C
    .if MODE == 1
    /* MODE 1: snapshot before, forge, call, snapshot after */
    lea.l LOG+0x20, %a3
    bsr snapshot
    move.w %d7, LOG+0x16
    move.w #LOCWORD, 0xFF0E92
    move.w #DEST, 0xFF0E98
    move.w #TIME16, 0xFF0E16
    lea.l 0xFFC388, %a0
    moveq #0, %d0
    move.w #63, %d1
.pt_clr:
    move.w %d0, (%a0)+
    dbra %d1, .pt_clr
    lea.l 0xFFC326, %a0
    move.w #22, %d1
.pt_set:
    move.b #0xFF, (%a0)+
    dbra %d1, .pt_set
    jsr 0x03090A
    bsr snapshot
    move.w %d7, LOG+0x18
    bra .pt_finish
    .else
.pt_recon:
    lea.l LOG+0x20, %a3
    bsr snapshot
    move.w %d7, LOG+0x16
    bra .pt_finish
    .endif
.pt_timing:
    /* log every 10 frames; stop at 600 frames after settle */
    move.w 0xFF0012, %d0
    sub.w LOG+2, %d0
    sub.w #120, %d0
    cmpi.w #600, %d0
    bge .pt_finish
    move.w %d0, %d1
    divu.w #10, %d1
    swap %d1
    tst.w %d1
    bne .pt_done
    move.w LOG+0x16, %d2
    cmpi.w #61, %d2
    bge .pt_finish
    muls.w #8, %d2
    lea.l LOG+0x20, %a0
    adda.w %d2, %a0
    move.w 0xFF0012, (%a0)+
    move.w 0xFF0E16, (%a0)+
    move.w 0xFF00AC, (%a0)+
    move.w 0xFF02A2, (%a0)+
    addq.w #1, LOG+0x16
    rts
.pt_finish:
    move.w 0xFF0E92, LOG+0x0E
    move.w 0xFF0E98, LOG+0x10
    move.w 0xFF0E16, LOG+0x12
    move.w 0xFFC408, LOG+0x14
    move.w 0xFF0012, LOG+0x1C
    move.w #2, LOG+6
    rts
.pt_done:
    rts

/* snapshot: log all non-empty char slots (mode nibble != 0) at %a3 (updated).
   16 words per slot. Count returned in %d7. */
snapshot:
    movem.l %d0-%d3/%a0-%a2, -(%sp)
    moveq #0, %d2
    moveq #0, %d7
.snap_loop:
    move.w %d2, %d0
    muls.w #52, %d0
    lea.l 0xFF02B4, %a0
    move.w (%a0,%d0.l), %d1
    move.w %d1, %d3
    andi.w #0xF, %d3
    beq .snap_next
    move.w %d2, (%a3)+
    move.w (%a0,%d0.l), (%a3)+
    move.w 2(%a0,%d0.l), (%a3)+
    move.w 6(%a0,%d0.l), (%a3)+
    move.w 10(%a0,%d0.l), (%a3)+
    move.w 12(%a0,%d0.l), (%a3)+
    move.w 14(%a0,%d0.l), (%a3)+
    move.w 20(%a0,%d0.l), (%a3)+
    move.w 22(%a0,%d0.l), (%a3)+
    move.w 24(%a0,%d0.l), (%a3)+
    move.w 28(%a0,%d0.l), (%a3)+
    move.w 30(%a0,%d0.l), (%a3)+
    move.w 32(%a0,%d0.l), (%a3)+
    move.w 34(%a0,%d0.l), (%a3)+
    move.w 36(%a0,%d0.l), (%a3)+
    move.w 38(%a0,%d0.l), (%a3)+
    addq.w #1, %d7
.snap_next:
    addq.w #1, %d2
    cmpi.w #56, %d2
    blt .snap_loop
    movem.l (%sp)+, %d0-%d3/%a0-%a2
    rts

test_spin:
    bra test_spin
"""

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError("command failed: %s\n%s\n%s" % (" ".join(cmd), r.stdout, r.stderr))
    return r

def main():
    name, mode, anchor, nibble, dest, time16 = sys.argv[1:7]
    mode, anchor, nibble, dest, time16 = int(mode), int(anchor), int(nibble), int(dest), int(time16)
    test_id = abs(hash(name)) % 60000
    src = os.path.join(SCRATCH, "probe_273_%s.s" % name)
    obj = os.path.join(SCRATCH, "probe_273_%s.o" % name)
    binp = os.path.join(SCRATCH, "probe_273_%s.bin" % name)
    asm = ASM_TEMPLATE.format(test_id=test_id, mode=mode, anchor=anchor,
                              nibble=nibble, dest=dest, time16=time16,
                              locword=(nibble << 12) | anchor)
    open(src, "w").write(asm)
    run(["m68k-linux-gnu-as", "-m68000", "-o", obj, src])
    run(["m68k-linux-gnu-objcopy", "-O", "binary", obj, binp])
    blob = open(binp, "rb").read()
    print("probe blob: %d bytes at 0x%05X (test_id %d)" % (len(blob), PAD_BASE, test_id))
    assert PAD_BASE + len(blob) <= 0x100000
    rom = bytearray(open(ORIG, "rb").read())
    assert len(rom) == 0x100000
    assert hashlib.md5(bytes(rom)).hexdigest() == "30c18fdbe2183f64702ae9f1a45d63f9", "orig MD5 mismatch"
    assert all(x == 0xFF for x in rom[PAD_BASE:PAD_BASE + len(blob)]), "padding not 0xFF"
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob
    assert rom[HOOK_SITE:HOOK_SITE + 8] == HOOK_ORIG, "hook site bytes mismatch: %s" % rom[HOOK_SITE:HOOK_SITE + 8].hex()
    rom[HOOK_SITE:HOOK_SITE + 8] = bytes([0x4E, 0xF9]) + PAD_BASE.to_bytes(4, "big") + bytes([0x4E, 0x71])
    tmp = os.path.join(SCRATCH, "probe_273_%s.rom.tmp" % name)
    outp = os.path.join(SCRATCH, "probe_273_%s.rom" % name)
    open(tmp, "wb").write(rom)
    run([sys.executable, CHECKSUM, "fix-all", tmp, outp])
    os.remove(tmp)
    print(run([sys.executable, CHECKSUM, "verify-all", outp]).stdout.strip())
    chk = open(outp, "rb").read()
    print("probe ROM %s MD5: %s" % (outp, hashlib.md5(chk).hexdigest()))
    r = run(["m68k-linux-gnu-nm", obj])
    for line in r.stdout.splitlines():
        if "test_spin" in line:
            print("  nm:", line.strip())

if __name__ == "__main__":
    main()
