#!/usr/bin/env python3
"""Build phase D of the full big rework (patches/d-governor/).

Tick governor + chunk loading, on the verified C ROM (see
.scratch-big-rework-full/d-governor/REPORT.md).

The C blob ($FD400-$FE6C9) is UNTOUCHED. One new blob at $FE6CA
(free 0xFF padding to the end of the ROM, 6454 bytes), six 6-byte
hook sites:
  H1 $00D2E0 jsr world_tick      -> jsr gov_world_tick (K=5 VBlanks/tick)
  H2 $00D97E jsr combat_turn_run -> jsr gov_combat_turn (runs only on a tick)
  H3 $0228CC cmpi.w #$4,-$E(a6)  -> jsr gov_path_a (pace v2 + leader heading)
  H4 $022778 jsr sys_event_run   -> jsr gov_sys_event (16-tick NPC/script gate)
  H5 $022B36 move.w d4,d0 + muls.w #$34,d0 -> jmp gov_npc (NPC gate;
       dest test first, $00FF sentinel)
  H6 $12C20  jsr $FE65A (C scene_entry) -> jsr gov_scene (sprite-magic clear)

Chunk loading: the data-chunk load is unchanged (DESIGN 7.2); the one
concrete gap is fixed by H6 (sprite slots are dropped on scene setup
so a stale slot cannot survive a location change).

Base: rop-big-rework-full-c-fix.rom (MD5 535288396024b3892d89d74b980436ac).
Output: rop-big-rework-full-d-fix.rom + IPS (base -> D-fix) + changed-bytes.txt.

Usage: python3 patches/d-governor-fix/build.py
"""
import hashlib
import os
import re
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
SCRATCH = os.path.join(REPO, 'build', 'scratch-d-governor-fix')
os.makedirs(SCRATCH, exist_ok=True)
WORKTREE = os.path.dirname(os.path.dirname(DIR))
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-big-rework-full-c-fix.rom'))
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
OUT_ROM = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-big-rework-full-d-fix.rom'))
MAIN = REPO
CHECKSUM = os.path.join(MAIN, "tools", "checksum.py")
VENV_PY = os.environ.get('ROP_VENV_PY', os.path.join(REPO, 'tools', '.venv', 'bin', 'python'))
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

BLOB_BASE = 0xFE6CA
C_BLOB_BASE = 0xFD400
C_BLOB_LEN = 0xFE6CA - 0xFD400  # 4810
BASE_MD5 = "535288396024b3892d89d74b980436ac"
ORIG_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"

# C hook sites: asserted unchanged, not touched
C_VBL = 0x1272
C_REDRAW = 0x1B918
C_SCENE = 0x12C20
C_MAPCLOSE = 0x16302
C_HERO = 0x0231D8
C_PROMOTE = 0x02343A
C_SCENE_TARGET = 0xFE65A

H1 = 0x00D2E0
H2 = 0x00D97E
H3 = 0x0228CC
H4 = 0x022778
H5 = 0x022B36
H6 = 0x12C20


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def listing_offsets(lst_path):
    """Parse vasm -L listing for the entry label addresses."""
    offs = {}
    pat = re.compile(r"^(gov_world_tick|gov_combat_turn|gov_path_a|gov_sys_event|gov_npc|gov_scene|gov_init)\s+A:([0-9A-Fa-f]+)")
    for line in open(lst_path):
        m = pat.match(line)
        if m:
            offs[m.group(1)] = int(m.group(2), 16)
    missing = {"gov_world_tick", "gov_combat_turn", "gov_path_a",
               "gov_sys_event", "gov_npc", "gov_scene", "gov_init"} - set(offs)
    if missing:
        raise RuntimeError(f"listing did not report entries: {missing}")
    return offs


def apply_ips(orig, ips):
    assert ips[:5] == b"PATCH", "bad IPS header"
    out = bytearray(orig)
    i = 5
    while ips[i:i + 3] != b"EOF":
        off = int.from_bytes(ips[i:i + 3], "big")
        ln = int.from_bytes(ips[i + 3:i + 5], "big")
        i += 5
        if ln == 0:  # RLE record (not emitted by this builder)
            rle_len = int.from_bytes(ips[i:i + 2], "big")
            val = ips[i + 2]
            out[off:off + rle_len] = bytes([val]) * rle_len
            i += 3
        else:
            out[off:off + ln] = ips[i:i + ln]
            i += ln
    return bytes(out)


def disasm_blob(blob, offs):
    """Disassemble the blob with capstone (venv python) and print the
    entry disassembly for a human eyeball check."""
    script = os.path.join(SCRATCH, "disasm_blob.py")
    with open(script, "w") as f:
        f.write(
            "import sys\n"
            "from capstone import Cs, CS_ARCH_M68K, CS_MODE_BIG_ENDIAN\n"
            "blob = open(sys.argv[1], 'rb').read()\n"
            "base = int(sys.argv[2], 16)\n"
            "md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN)\n"
            "for ins in md.disasm(blob, base):\n"
            "    b = blob[ins.address - base: ins.address - base + ins.size]\n"
            "    print('  %05X  %-24s %s %s' % (ins.address, b.hex(), ins.mnemonic, ins.op_str))\n"
        )
    r = run([VENV_PY, script, os.path.join(SCRATCH, "source.bin"), hex(BLOB_BASE)])
    print(r.stdout, end="")
    os.remove(script)


def main():
    base = open(BASE, "rb").read()
    assert len(base) == 0x100000, f"base size {len(base)}"
    assert hashlib.md5(base).hexdigest() == BASE_MD5, "base MD5 mismatch"
    assert hashlib.md5(open(ORIG, "rb").read()).hexdigest() == ORIG_MD5, \
        "original MD5 mismatch"
    assert all(b == 0xFF for b in base[BLOB_BASE:]), \
        "padding not 0xFF at $FE6CA-end"
    # C blob extracted from the base ROM (was: ../c-sprites-fix/source.bin;
    # source.bin is a vasm output and is not committed). The base ROM's
    # MD5 is asserted above, so these bytes are the C blob.
    c_blob = bytes(base[C_BLOB_BASE:C_BLOB_BASE + C_BLOB_LEN])
    assert len(c_blob) == C_BLOB_LEN, f"C blob size {len(c_blob)}"
    print(f"C blob verified unchanged ({C_BLOB_LEN} bytes at $FD400)")

    # C hooks: asserted unchanged, not touched
    def expect(off, want, what):
        got = bytes(base[off:off + len(want)])
        assert got == want, f"C hook {what} 0x{off:05X}: expected {want.hex()}, got {got.hex()}"
    expect(C_VBL, bytes.fromhex("4ef9000fd4004e71"), "VBlank $1272 jmp $FD400;nop")
    expect(C_REDRAW, bytes.fromhex("4eb9000fda42"), "redraw $1B918 jsr $FDA42")
    expect(C_SCENE, bytes.fromhex("4eb9000fe65a"), "scene $12C20 jsr $FE65A")
    expect(C_MAPCLOSE, bytes.fromhex("4eb9000fe694"), "mapclose $16302 jsr $FE694")
    expect(C_HERO, bytes.fromhex("4eb9000fe610"), "hero_track $0231D8 jsr $FE610")
    expect(C_PROMOTE, bytes.fromhex("4eb9000fe6344e71"), "promote $02343A jsr $FE634;nop")
    print("C hooks verified unchanged (vbl/redraw/scene/mapclose/hero/promote)")

    src = os.path.join(DIR, "source.s")
    binp = os.path.join(SCRATCH, "source.bin")
    lstp = os.path.join(SCRATCH, "source.lst")
    run([VASM, "-m68000", "-Fbin", "-o", binp, "-L", lstp, src])
    offs = listing_offsets(lstp)
    blob = open(binp, "rb").read()
    print(f"blob: {len(blob)} bytes at 0x{BLOB_BASE:05X} "
          f"(world_tick +0x{offs['gov_world_tick']:X}, combat +0x{offs['gov_combat_turn']:X}, "
          f"path_a +0x{offs['gov_path_a']:X}, sys_event +0x{offs['gov_sys_event']:X}, "
          f"npc +0x{offs['gov_npc']:X}, scene +0x{offs['gov_scene']:X}, "
          f"init +0x{offs['gov_init']:X})")
    assert offs["gov_world_tick"] == 0, "gov_world_tick must be first in the blob"
    assert BLOB_BASE + len(blob) <= 0x100000, "blob overruns the end of the ROM"
    assert BLOB_BASE > 0xFD07B, "blob must stay past the runtime checksum range"
    # governor immediates present: K=5, NPCDIV=4, magic $9C07
    # (move.w #imm, $FFD30x.l encodes as 33 fc <imm> 00 ff d3 0x)
    assert b"\x33\xfc\x00\x05\x00\xff\xd3\x02" in blob, "GOV_K init (move.w #5) missing"
    assert b"\x33\xfc\x00\x04\x00\xff\xd3\x04" in blob, "GOV_NPCDIV init (move.w #4) missing"
    assert b"\x33\xfc\x9c\x07\x00\xff\xd3\x00" in blob, "magic $9C07 init missing"
    # sprite-magic clear present in gov_scene (clr.w $FFD000)
    assert b"\x42\x79\x00\xff\xd0\x00" in blob, "clr.w $FFD000 missing"
    # tail-call to C scene_entry present (jmp $FE65A.l)
    assert b"\x4e\xf9\x00\x0f\xe6\x5a" in blob, "jmp $FE65A missing"

    print("blob disassembly:")
    disasm_blob(blob, offs)

    wt = BLOB_BASE + offs["gov_world_tick"]
    ct = BLOB_BASE + offs["gov_combat_turn"]
    pa = BLOB_BASE + offs["gov_path_a"]
    se = BLOB_BASE + offs["gov_sys_event"]
    np_ = BLOB_BASE + offs["gov_npc"]
    sc = BLOB_BASE + offs["gov_scene"]

    rom = bytearray(base)
    rom[BLOB_BASE:BLOB_BASE + len(blob)] = blob
    blob_end = BLOB_BASE + len(blob)
    assert all(b == 0xFF for b in rom[blob_end:]), \
        "bytes past the new blob end are not 0xFF"
    print(f"blob covers 0x{BLOB_BASE:05X}-0x{blob_end - 1:05X}; "
          f"past the end is 0xFF to the end of the ROM")

    def patch(off, expected, new, what):
        got = bytes(rom[off:off + len(expected)])
        assert got == expected, f"{what} 0x{off:05X}: expected {expected.hex()}, got {got.hex()}"
        rom[off:off + len(new)] = new
        print(f"patched {what}: 0x{off:05X} {expected.hex()} -> {new.hex()}")

    patch(H1, bytes.fromhex("4eb90002155e"),
          bytes.fromhex("4eb9") + wt.to_bytes(4, "big"),
          "main loop $00D2E0 jsr world_tick -> jsr gov_world_tick")
    patch(H2, bytes.fromhex("4eb9000226bc"),
          bytes.fromhex("4eb9") + ct.to_bytes(4, "big"),
          "main loop $00D97E jsr combat_turn_run -> jsr gov_combat_turn")
    patch(H3, bytes.fromhex("0c6e0004fff2"),
          bytes.fromhex("4eb9") + pa.to_bytes(4, "big"),
          "Path A $0228CC cmpi.w #$4,-$E(a6) -> jsr gov_path_a")
    patch(H4, bytes.fromhex("4eb90002d56a"),
          bytes.fromhex("4eb9") + se.to_bytes(4, "big"),
          "script $022778 jsr sys_event_run -> jsr gov_sys_event")
    patch(H5, bytes.fromhex("3004c1fc0034"),
          bytes.fromhex("4ef9") + np_.to_bytes(4, "big"),
          "NPC $022B36 move.w d4,d0;muls.w #$34,d0 -> jmp gov_npc")
    patch(H6, bytes.fromhex("4eb9000fe65a"),
          bytes.fromhex("4eb9") + sc.to_bytes(4, "big"),
          "scene $12C20 jsr $FE65A -> jsr gov_scene")

    tmp = os.path.join(SCRATCH, "rop-big-rework-full-d.gen.tmp")
    open(tmp, "wb").write(rom)
    run([VENV_PY, CHECKSUM, "fix-all", tmp, OUT_ROM])
    os.remove(tmp)
    v = run([VENV_PY, CHECKSUM, "verify-all", OUT_ROM]).stdout.strip()
    print(f"patched ROM: {OUT_ROM} — {v}")

    chk = open(OUT_ROM, "rb").read()
    assert chk[BLOB_BASE:BLOB_BASE + len(blob)] == blob
    assert all(b == 0xFF for b in chk[blob_end:]), \
        "bytes past the blob end are not 0xFF in the output ROM"
    assert chk[H1:H1 + 6] == bytes.fromhex("4eb9") + wt.to_bytes(4, "big")
    assert chk[H2:H2 + 6] == bytes.fromhex("4eb9") + ct.to_bytes(4, "big")
    assert chk[H3:H3 + 6] == bytes.fromhex("4eb9") + pa.to_bytes(4, "big")
    assert chk[H4:H4 + 6] == bytes.fromhex("4eb9") + se.to_bytes(4, "big")
    assert chk[H5:H5 + 6] == bytes.fromhex("4ef9") + np_.to_bytes(4, "big")
    assert chk[H6:H6 + 6] == bytes.fromhex("4eb9") + sc.to_bytes(4, "big")
    print("hook bytes + blob verified in place")

    # ---- IPS: diff base -> patched, one record per maximal changed run ----
    records = []
    i = 0
    n = len(base)
    while i < n:
        if base[i] != chk[i]:
            j = i
            while j < n and base[j] != chk[j] and j - i < 0xFFFF:
                j += 1
            records.append((i, chk[i:j]))
            i = j
        else:
            i += 1
    ips = bytearray(b"PATCH")
    for off, data in records:
        ips += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    ips += b"EOF"
    ips_path = os.path.join(DIR, "rings-of-power-big-rework-full-d-fix.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} — {len(ips)} bytes, {len(records)} records")

    # ---- IPS round-trip: applying the IPS to the base must reproduce the ROM ----
    rt = apply_ips(base, bytes(ips))
    assert rt == chk, "IPS round-trip FAILED: applied IPS != patched ROM"
    print("IPS round-trip verified: base + IPS == ROM exactly")

    # ---- changed-bytes.txt ----
    lines = [
        "Changed bytes: rop-big-rework-full-c-fix.rom (MD5 535288396024b3892d89d74b980436ac)"
        " -> rop-big-rework-full-d-fix.rom (big-rework-full phase D: tick governor +"
        " chunk loading -- see .scratch-big-rework-full/d-crash-fix/REPORT.md)",
        "IPS applies to rop-big-rework-full-c-fix.rom, NOT to the original ROM.",
        "All addresses are 68000 ROM offsets (= file offsets). Values are hex bytes.",
        "",
        f"Trampoline blob: 0x{BLOB_BASE:05X}-0x{blob_end - 1:05X} "
        f"({len(blob)} bytes, source.s assembled with vasm; C blob $FD400-$FE6C9 untouched)",
        f"  gov_world_tick 0x{wt:05X} (main-loop tick gate, K=5 VBlanks/tick)",
        f"  gov_combat_turn 0x{ct:05X} (runs combat_turn_run only on a governor-tick)",
        f"  gov_path_a     0x{pa:05X} (leader step gate, pace v2 + leader heading)",
        f"  gov_sys_event  0x{se:05X} (script-step gate, every 16th governor-tick)",
        f"  gov_npc        0x{np_:05X} (NPC step gate, dest-first $00FF sentinel, wandering phase + 16-tick gate)",
        f"  gov_scene      0x{sc:05X} (scene setup: clear sprite magic, tail-call C $FE65A)",
        f"  gov_init       0x{BLOB_BASE + offs['gov_init']:05X} (initialise governor state)",
        "Hooks:",
        f"  0x{H1:05X} jsr world_tick.l -> jsr ${wt:05X}.l",
        f"  0x{H2:05X} jsr combat_turn_run.l -> jsr ${ct:05X}.l",
        f"  0x{H3:05X} cmpi.w #$4,-$E(a6) -> jsr ${pa:05X}.l",
        f"  0x{H4:05X} jsr sys_event_run.l -> jsr ${se:05X}.l",
        f"  0x{H5:05X} move.w d4,d0 ; muls.w #$34,d0 -> jmp ${np_:05X}.l",
        f"  0x{H6:05X} jsr $FE65A.l -> jsr ${sc:05X}.l",
        "C blob ($FD400-$FE6C9) and C hooks ($1272/$1B918/$12C20/$16302/$0231D8/$02343A)",
        "  are unchanged -- asserted, not touched.",
        "No stale blob tail: the new blob is the only D content and the bytes past",
        "  its end are 0xFF to the end of the ROM.",
        "Checksums: fixed with tools/checksum.py fix-all (no code shifted)",
        "",
    ]
    for off, data in records:
        lines.append(f"0x{off:05X}-0x{off + len(data) - 1:05X} ({len(data)} bytes):")
        for k in range(0, len(data), 16):
            chunk_o = base[off + k:off + k + 16]
            chunk_n = data[k:k + 16]
            lines.append(f"  0x{off + k:05X}: {' '.join(f'{b:02x}' for b in chunk_o)}  -> "
                         f"{' '.join(f'{b:02x}' for b in chunk_n)}")
        lines.append("")
    open(os.path.join(DIR, "changed-bytes.txt"), "w").write("\n".join(lines))
    print(f"changed-bytes: {len(records)} records")

    # ---- original + base untouched ----
    assert hashlib.md5(open(ORIG, "rb").read()).hexdigest() == ORIG_MD5
    assert hashlib.md5(open(BASE, "rb").read()).hexdigest() == BASE_MD5
    print("original ROM untouched (MD5 re-verified); base ROM untouched")
    print("DONE")


if __name__ == "__main__":
    main()
