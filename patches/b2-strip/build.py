#!/usr/bin/env python3
"""Build phase B2 of the full big rework (patches/b2-strip/).

Scheme B improved gate (fallback per the B2 brief: literal strip
streaming, DESIGN 7.3, is unbuildable for the 36x23 image -- see
.scratch-big-rework-full/b2-strip/REPORT.md section 3 and
sim_strip.py. R1 verifies the full re-decode re-centre is
flicker-free, so Scheme B is acceptable).

The ONE change vs B1: vbl_entry's scroll follows the CAMERA, not
the D-pad. Fix2's gate is seamless only once the pad-driven scroll
has caught up to the camera move, but the scroll is pad-driven
while the camera is game-driven, so catch-up is not guaranteed:
cutscene/scripted moves stall the gate until dx grows past 1 cell
and it fires the jumpy ">1 cell" branch; a short tap / direction
change leaves the picture frozen with a blank strip until the pad
is held again. B2 steps the scroll accumulators each VBlank
toward the camera target (clamp(-(dx-dy),-1,+1)*224,
clamp(dx+dy,-1,+1)*128 -- the gate's own expected-value formulas)
at the existing rates (16/16 px horiz, 9/16 px vert per frame).
The redraw/scene/mapclose entries are UNCHANGED from B1 (only
re-assembled: this VM has no m68k GAS, so source.s is vasm
Motorola syntax -- see README.md; build.py verifies the three
unchanged entries disassemble to the identical instruction
stream as the B1 blob, modulo branch-displacement size, one
LEA-for-ADDA encoding, and one elided no-op branch-to-next).

Base: rop-big-rework-full-b1.rom (MD5 49530033f2f191d938e9f0ec3f86e845).
Output: rop-big-rework-full-b2.rom + IPS (base -> B2) + changed-bytes.txt.

Changes (all asserting the base ROM's bytes first):
  Blob at $FD900 (assembled from source.s with vasm, 4 entries
  via the listing file):
    vbl_entry      VBlank hook ($1272): camera-target scroll (B2 NEW;
                   same size as B1's vbl, 0x254 bytes, so redraw
                   stays at +0x254 and its hook is unchanged)
    redraw_entry   redraw_check hook ($1B918): fix2 gate, unchanged
    scene_entry    world_map_draw hook ($12C20): reset install state,
                   unchanged (offset moved +0x4F0 -> +0x4C0: the
                   vasm branch-size savings shrink redraw by 48 B)
    mapclose_entry world_map_redraw hook ($16302): reset on map close,
                   unchanged (offset +0x52A -> +0x4FA)
  The 48 bytes of stale B1 blob tail past the new blob end
  ($FDE30-$FDE60) are overwritten with 0xFF.
  Statics and allocator: UNCHANGED from B1 (asserted, not touched).
  Checksums fixed with tools/checksum.py fix-all (no code is
  shifted, so the stock tool's runtime-immediate address stays valid).

Usage: python3 patches/b2-strip/build.py
"""
import hashlib
import os
import re
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
SCRATCH = os.path.join(REPO, 'build', 'scratch-b2-strip')
os.makedirs(SCRATCH, exist_ok=True)
WORKTREE = os.path.dirname(os.path.dirname(DIR))
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-big-rework-full-b1.rom'))
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
OUT_ROM = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-big-rework-full-b2.rom'))
MAIN = REPO
CHECKSUM = os.path.join(MAIN, "tools", "checksum.py")
VENV_PY = os.environ.get('ROP_VENV_PY', os.path.join(REPO, 'tools', '.venv', 'bin', 'python'))
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

PAD_BASE = 0xFD900
BASE_MD5 = "49530033f2f191d938e9f0ec3f86e845"
ORIG_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"
B1_BLOB_END = 0xFDE60  # $FD900 + 1376

VBL_SITE = 0x1272
REDRAW_SITE = 0x1B918
SCENE_SITE = 0x12C20
MAPCLOSE_SITE = 0x16302
STATIC_R4 = 0x12C9A
STATIC_DRAW = 0x12E68
STATIC_REDRAW = 0x16326
ALLOC_START = 0x12D00
ALLOC_END = 0x12DE8  # exclusive


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def listing_offsets(lst_path):
    """Parse vasm -L listing for the four entry label addresses."""
    offs = {}
    pat = re.compile(r"^(vbl_entry|redraw_entry|scene_entry|mapclose_entry)\s+A:([0-9A-Fa-f]+)")
    for line in open(lst_path):
        m = pat.match(line)
        if m:
            offs[m.group(1)] = int(m.group(2), 16)
    missing = {"vbl_entry", "redraw_entry", "scene_entry", "mapclose_entry"} - set(offs)
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


def check_unchanged_entries(b1_blob, b2_blob, offs2):
    """The redraw/scene/mapclose entries must disassemble to the
    identical instruction stream as the B1 blob (see check_entries.py).
    Runs under the RoP venv python, which has capstone/m68k."""
    import json
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(offs2, f)
        offs_path = f.name
    b1_path = os.path.join(SCRATCH, "b1.bin")
    open(b1_path, "wb").write(b1_blob)
    b2_path = os.path.join(SCRATCH, "b2.bin")
    open(b2_path, "wb").write(b2_blob)
    r = run([VENV_PY, os.path.join(DIR, "check_entries.py"),
             b1_path, b2_path, offs_path])
    print(r.stdout, end="")
    os.remove(offs_path)


def main():
    base = open(BASE, "rb").read()
    assert len(base) == 0x100000, f"base size {len(base)}"
    assert hashlib.md5(base).hexdigest() == BASE_MD5, "base MD5 mismatch"
    assert hashlib.md5(open(ORIG, "rb").read()).hexdigest() == ORIG_MD5, \
        "original MD5 mismatch"
    assert all(b == 0xFF for b in base[B1_BLOB_END:0xFE000]), \
        "padding not 0xFF after B1 blob end $FDE60"
    # B1 blob extracted from the base ROM (was: ../b1-vram/source.bin;
    # source.bin is a vasm output and is not committed). The base ROM's
    # MD5 is asserted above, so these bytes are the B1 blob.
    b1_blob = bytes(base[PAD_BASE:PAD_BASE + 1376])
    assert len(b1_blob) == 1376, f"B1 blob size {len(b1_blob)}"

    src = os.path.join(DIR, "source.s")
    binp = os.path.join(SCRATCH, "source.bin")
    lstp = os.path.join(SCRATCH, "source.lst")
    run([VASM, "-m68000", "-Fbin", "-o", binp, "-L", lstp, src])
    offs = listing_offsets(lstp)
    blob = open(binp, "rb").read()
    print(f"blob: {len(blob)} bytes at 0x{PAD_BASE:05X} "
          f"(vbl +0x{offs['vbl_entry']:X}, redraw +0x{offs['redraw_entry']:X}, "
          f"scene +0x{offs['scene_entry']:X}, "
          f"mapclose +0x{offs['mapclose_entry']:X})")
    assert offs["vbl_entry"] == 0, "vbl_entry must be first in the blob"
    assert offs["redraw_entry"] == 0x254, \
        f"redraw_entry moved (vbl size changed): +0x{offs['redraw_entry']:X}"
    assert PAD_BASE + len(blob) <= 0xFE000, "blob overruns $FDFFF"
    assert PAD_BASE > 0xFD07B, "blob must stay past the runtime checksum range"
    # the pad-byte read must be gone from vbl (camera-driven scroll)
    assert b"\x10\x39\x00\xff\x00\x18" not in blob, \
        "blob still reads the pad byte $FF0018"
    # camera-target immediates present: +-224 ($E0/$FF20), +-128 ($80/$FF80)
    for pat in (b"\x34\x3c\x00\xe0", b"\x34\x3c\xff\x20",
                b"\x36\x3c\x00\x80", b"\x36\x3c\xff\x80"):
        assert pat in blob, f"camera-target immediate {pat.hex()} missing"

    print("unchanged-entry disassembly check vs B1 blob:")
    check_unchanged_entries(b1_blob, blob, offs)

    vbl_addr = PAD_BASE + offs["vbl_entry"]
    redraw_addr = PAD_BASE + offs["redraw_entry"]
    scene_addr = PAD_BASE + offs["scene_entry"]
    mapclose_addr = PAD_BASE + offs["mapclose_entry"]

    rom = bytearray(base)
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob
    # clear the stale B1 blob tail past the new blob end
    tail_start = PAD_BASE + len(blob)
    assert all(b == 0xFF for b in rom[B1_BLOB_END:0xFE000])
    rom[tail_start:B1_BLOB_END] = b"\xFF" * (B1_BLOB_END - tail_start)
    print(f"cleared stale B1 tail 0x{tail_start:05X}-0x{B1_BLOB_END - 1:05X} to 0xFF")

    def patch(off, expected, new, what):
        got = bytes(rom[off:off + len(expected)])
        assert got == expected, f"{what} 0x{off:05X}: expected {expected.hex()}, got {got.hex()}"
        rom[off:off + len(new)] = new
        print(f"patched {what}: 0x{off:05X} {expected.hex()} -> {new.hex()}")

    # VBlank hook: vbl still at +0 -> bytes unchanged, verify only
    patch(VBL_SITE,
          bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71"),
          bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71"),
          "vblank hook $1272 (verify unchanged)")
    # redraw_check hook: redraw still at +0x254 -> bytes unchanged, verify only
    patch(REDRAW_SITE,
          bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big"),
          bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big"),
          "redraw_check hook $1B918 (verify unchanged)")
    # world_map_draw hook: scene moved $FDDF0 -> new scene_addr
    patch(SCENE_SITE,
          bytes.fromhex("4eb9") + (PAD_BASE + 0x4F0).to_bytes(4, "big"),
          bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big"),
          "world_map_draw hook $12C20")
    # world_map_redraw hook: mapclose moved $FDE2A -> new mapclose_addr
    patch(MAPCLOSE_SITE,
          bytes.fromhex("4eb9") + (PAD_BASE + 0x52A).to_bytes(4, "big"),
          bytes.fromhex("4eb9") + mapclose_addr.to_bytes(4, "big"),
          "world_map_redraw hook $16302")
    # Statics + allocator: UNCHANGED from B1, assert only
    assert bytes(rom[STATIC_R4:STATIC_R4 + 4]) == bytes.fromhex("3f3c8407"), \
        "R4 static $12C9A is not $8407"
    assert bytes(rom[STATIC_DRAW:STATIC_DRAW + 4]) == bytes.fromhex("4878e000"), \
        "room draw dest $12E68 is not pea $E000"
    assert bytes(rom[STATIC_REDRAW:STATIC_REDRAW + 4]) == bytes.fromhex("4878e000"), \
        "redraw draw dest $16326 is not pea $E000"
    assert bytes(rom[0x12CDE:0x12CE2]) == bytes.fromhex("3f3c9001"), \
        "R16 site $12CDE is not $9001"
    print("statics verified unchanged from B1 (R4 $8407, pea $E000 x2, R16 $9001)")
    assert bytes(rom[ALLOC_START:ALLOC_END]) == base[ALLOC_START:ALLOC_END], \
        "allocator region changed (must stay B1's)"
    print("allocator region verified unchanged from B1")

    tmp = os.path.join(SCRATCH, "rop-big-rework-full-b2.gen.tmp")
    open(tmp, "wb").write(rom)
    run([VENV_PY, CHECKSUM, "fix-all", tmp, OUT_ROM])
    os.remove(tmp)
    v = run([VENV_PY, CHECKSUM, "verify-all", OUT_ROM]).stdout.strip()
    print(f"patched ROM: {OUT_ROM} — {v}")

    chk = open(OUT_ROM, "rb").read()
    assert chk[PAD_BASE:PAD_BASE + len(blob)] == blob
    assert all(b == 0xFF for b in chk[tail_start:B1_BLOB_END]), \
        "stale blob tail not cleared in output ROM"
    assert chk[VBL_SITE:VBL_SITE + 8] == bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71")
    assert chk[REDRAW_SITE:REDRAW_SITE + 6] == bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big")
    assert chk[SCENE_SITE:SCENE_SITE + 6] == bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big")
    assert chk[MAPCLOSE_SITE:MAPCLOSE_SITE + 6] == bytes.fromhex("4eb9") + mapclose_addr.to_bytes(4, "big")
    print("hook bytes + blob + statics + allocator verified in place")

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
    ips_path = os.path.join(DIR, "rings-of-power-big-rework-full-b2.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} — {len(ips)} bytes, {len(records)} records")

    # ---- IPS round-trip: applying the IPS to the base must reproduce the ROM ----
    rt = apply_ips(base, bytes(ips))
    assert rt == chk, "IPS round-trip FAILED: applied IPS != patched ROM"
    print("IPS round-trip verified: base + IPS == ROM exactly")

    # ---- changed-bytes.txt ----
    lines = [
        "Changed bytes: rop-big-rework-full-b1.rom (MD5 49530033f2f191d938e9f0ec3f86e845)"
        " -> rop-big-rework-full-b2.rom (big-rework-full phase B2: Scheme B improved"
        " gate, camera-driven scroll -- see .scratch-big-rework-full/b2-strip/REPORT.md)",
        "IPS applies to rop-big-rework-full-b1.rom, NOT to the original ROM.",
        "All addresses are 68000 ROM offsets (= file offsets). Values are hex bytes.",
        "",
        f"Trampoline blob: 0x{PAD_BASE:05X}-0x{PAD_BASE + len(blob) - 1:05X} "
        f"({len(blob)} bytes, source.s assembled with vasm; B1 blob was 1376 bytes to $FDE60)",
        f"  vbl_entry      0x{vbl_addr:05X} (VBlank hook: CAMERA-target scroll, B2 NEW)",
        f"  redraw_entry   0x{redraw_addr:05X} (redraw_check hook: fix2 gate, unchanged)",
        f"  scene_entry    0x{scene_addr:05X} (world_map_draw hook: reset install state, unchanged)",
        f"  mapclose_entry 0x{mapclose_addr:05X} (world_map_redraw hook: reset on map close, unchanged)",
        "Hooks:",
        f"  0x{VBL_SITE:05X} jmp ${vbl_addr:05X}.l ; nop (unchanged)",
        f"  0x{REDRAW_SITE:05X} jsr ${redraw_addr:05X}.l (unchanged)",
        f"  0x{SCENE_SITE:05X} jsr $FDDF0.l -> jsr ${scene_addr:05X}.l",
        f"  0x{MAPCLOSE_SITE:05X} jsr $FDE2A.l -> jsr ${mapclose_addr:05X}.l",
        "Statics / allocator: unchanged from B1 (R4 $8407, pea $E000 x2, R16 $9001,",
        "  allocator $12D00-$12DE7 as B1) -- asserted, not touched.",
        f"Stale B1 blob tail 0x{tail_start:05X}-0x{B1_BLOB_END - 1:05X} overwritten with 0xFF.",
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
