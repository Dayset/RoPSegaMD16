#!/usr/bin/env python3
"""Build the big-rework proof-of-concept FIX 2 patch
(patches/big-rework-poc-fix2/).

Fixes the PoC (patches/big-rework): the redraw gate now re-installs
when the camera moves from the install camera, so the Plane B image
and the baked figures follow the camera instead of freezing at the
install view. See .scratch-big-rework-poc-fix2/REPORT.md and the
header comment in source.s. Built from the original ROM in the
worktree; the original stays untouched.

Assembles source.s (three trampolines in one blob), places it in the
0xFF padding at 0xFD900 (past the runtime checksum's summed range
0x000000-0xFD07B), patches three hook sites + three static sites
(asserting the original bytes first), fixes both checksums with
tools/checksum.py fix-all, verifies, and writes:
  - rings-of-power-big-rework-poc-fix2.ips (committable; apply to a
    clean original)
  - build/rop-big-rework-poc-fix2.rom     (patched ROM for Dayset)
  - changed-bytes.txt                     (original -> patched, for review)
Usage: python3 patches/big-rework-poc-fix2/build.py
"""
import hashlib
import os
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
SCRATCH = os.path.join(REPO, 'build', 'scratch-big-rework-poc-fix2')
os.makedirs(SCRATCH, exist_ok=True)
WORKTREE = os.path.dirname(os.path.dirname(DIR))
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
OUT_ROM = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-big-rework-poc-fix2.rom'))
# Main repo, for tools/checksum.py (this worktree is not a git repo).
MAIN = REPO
CHECKSUM = os.path.join(MAIN, "tools", "checksum.py")
VENV_PY = os.environ.get('ROP_VENV_PY', os.path.join(REPO, 'tools', '.venv', 'bin', 'python'))
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable

PAD_BASE = 0xFD900
ORIG_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"

# (offset, original bytes, new bytes or builder)
VBL_SITE = 0x1272
VBL_ORIG = bytes.fromhex("33fc000000ff0016")          # move.w #$0,$FF0016
REDRAW_SITE = 0x1B918
REDRAW_ORIG = bytes.fromhex("4e56fffe4a79")           # link a6,#-2 ; tst.w $FF009C (opcode)
SCENE_SITE = 0x12C20
SCENE_ORIG = bytes.fromhex("4e56fffc4879")            # link a6,#-4 ; pea.l (opcode)
STATIC_R4 = 0x12C9A
STATIC_R4_ORIG = bytes.fromhex("3f3c8400")            # move.w #$8400,-(a7)
STATIC_R4_NEW = bytes.fromhex("3f3c8402")             # move.w #$8402,-(a7) (R4: Plane B $4000)
STATIC_DRAW = 0x12E68
STATIC_REDRAW = 0x16326
PEA_ORIG = bytes.fromhex("48781000")                  # pea $001000.w (window $1000)
PEA_NEW = bytes.fromhex("48784000")                   # pea $004000.w (Plane B $4000)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def nm_offsets(obj):
    out = run(["m68k-linux-gnu-nm", obj]).stdout
    offs = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in ("vbl_entry", "redraw_entry", "scene_entry"):
            offs[parts[2]] = int(parts[0], 16)
    missing = {"vbl_entry", "redraw_entry", "scene_entry"} - set(offs)
    if missing:
        raise RuntimeError(f"nm did not report entries: {missing}\n{out}")
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


def main():
    orig = open(ORIG, "rb").read()
    assert len(orig) == 0x100000, f"original size {len(orig)}"
    assert hashlib.md5(orig).hexdigest() == ORIG_MD5, "original MD5 mismatch"
    assert all(b == 0xFF for b in orig[PAD_BASE:]), "padding not 0xFF from PAD_BASE"

    src = os.path.join(DIR, "source.s")
    obj = os.path.join(SCRATCH, "source.o")
    binp = os.path.join(SCRATCH, "source.bin")
    run(["m68k-linux-gnu-as", "-m68000", "-o", obj, src])
    run(["m68k-linux-gnu-objcopy", "-O", "binary", obj, binp])
    offs = nm_offsets(obj)
    blob = open(binp, "rb").read()
    os.remove(obj)
    print(f"blob: {len(blob)} bytes at 0x{PAD_BASE:05X} "
          f"(vbl +0x{offs['vbl_entry']:X}, redraw +0x{offs['redraw_entry']:X}, "
          f"scene +0x{offs['scene_entry']:X})")
    assert offs["vbl_entry"] == 0, "vbl_entry must be first in the blob"
    assert PAD_BASE + len(blob) <= 0x100000
    assert PAD_BASE > 0xFD07B, "blob must stay past the runtime checksum range"

    vbl_addr = PAD_BASE + offs["vbl_entry"]
    redraw_addr = PAD_BASE + offs["redraw_entry"]
    scene_addr = PAD_BASE + offs["scene_entry"]

    rom = bytearray(orig)
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob

    def patch(off, expected, new, what):
        got = bytes(rom[off:off + len(expected)])
        assert got == expected, f"{what} 0x{off:05X}: expected {expected.hex()}, got {got.hex()}"
        rom[off:off + len(new)] = new
        print(f"patched {what}: 0x{off:05X} {expected.hex()} -> {new.hex()}")

    # VBlank hook: jmp $FD900.l ; nop (8 bytes, overlay pattern)
    patch(VBL_SITE, VBL_ORIG,
          bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71"),
          "vblank hook $1272")
    # redraw_check hook: jsr $FDA00+.l (6 bytes, smooth-move pattern)
    patch(REDRAW_SITE, REDRAW_ORIG,
          bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big"),
          "redraw_check hook $1B918")
    # world_map_draw hook: jsr $FDB00+.l (6 bytes)
    patch(SCENE_SITE, SCENE_ORIG,
          bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big"),
          "world_map_draw hook $12C20")
    # Static: R4 $8400 -> $8402 (Plane B $4000)
    patch(STATIC_R4, STATIC_R4_ORIG, STATIC_R4_NEW, "R4 Plane B $12C9A")
    # Static: room draws window $1000 -> Plane B $4000
    patch(STATIC_DRAW, PEA_ORIG, PEA_NEW, "room draw dest $12E68")
    patch(STATIC_REDRAW, PEA_ORIG, PEA_NEW, "redraw draw dest $16326")

    tmp = os.path.join(SCRATCH, "rop-big-rework-poc.gen.tmp")
    open(tmp, "wb").write(rom)
    run([VENV_PY, CHECKSUM, "fix-all", tmp, OUT_ROM])
    os.remove(tmp)
    v = run([VENV_PY, CHECKSUM, "verify-all", OUT_ROM]).stdout.strip()
    print(f"patched ROM: {OUT_ROM} — {v}")

    chk = open(OUT_ROM, "rb").read()
    assert chk[PAD_BASE:PAD_BASE + len(blob)] == blob
    assert chk[VBL_SITE:VBL_SITE + 8] == bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71")
    assert chk[REDRAW_SITE:REDRAW_SITE + 6] == bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big")
    assert chk[SCENE_SITE:SCENE_SITE + 6] == bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big")
    assert chk[STATIC_R4:STATIC_R4 + 4] == STATIC_R4_NEW
    assert chk[STATIC_DRAW:STATIC_DRAW + 4] == PEA_NEW
    assert chk[STATIC_REDRAW:STATIC_REDRAW + 4] == PEA_NEW
    print("hook bytes + blob + statics verified in place")

    # ---- IPS: diff original -> patched, one record per maximal changed run ----
    records = []
    i = 0
    n = len(orig)
    while i < n:
        if orig[i] != chk[i]:
            j = i
            while j < n and orig[j] != chk[j] and j - i < 0xFFFF:
                j += 1
            records.append((i, chk[i:j]))
            i = j
        else:
            i += 1
    ips = bytearray(b"PATCH")
    for off, data in records:
        ips += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    ips += b"EOF"
    ips_path = os.path.join(DIR, "rings-of-power-big-rework-poc-fix2.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} — {len(ips)} bytes, {len(records)} records")

    # ---- IPS round-trip: applying the IPS to the original must reproduce the ROM ----
    rt = apply_ips(orig, bytes(ips))
    assert rt == chk, "IPS round-trip FAILED: applied IPS != patched ROM"
    print("IPS round-trip verified: base + IPS == ROM exactly")

    # ---- changed-bytes.txt ----
    lines = [
        "Changed bytes: original (MD5 30c18fdbe2183f64702ae9f1a45d63f9) -> "
        "rop-big-rework-poc-fix2.rom (big-rework PoC fix2: camera-aware "
        "re-decode gate, DESIGN.md §8 + fix2 REPORT.md)",
        "All addresses are 68000 ROM offsets (= file offsets). Values are hex bytes.",
        "",
        f"Trampoline blob: 0x{PAD_BASE:05X}-0x{PAD_BASE + len(blob) - 1:05X} "
        f"({len(blob)} bytes, source.s)",
        f"  vbl_entry    0x{vbl_addr:05X} (VBlank hook: D-pad scroll)",
        f"  redraw_entry 0x{redraw_addr:05X} (redraw_check hook: Plane B install + re-decode gate)",
        f"  scene_entry  0x{scene_addr:05X} (world_map_draw hook: reset install state)",
        "Hooks:",
        f"  0x{VBL_SITE:05X} move.w #$0,$FF0016 -> jmp ${vbl_addr:05X}.l ; nop",
        f"  0x{REDRAW_SITE:05X} link a6,#-2 ; tst.w $FF009C -> jsr ${redraw_addr:05X}.l",
        f"  0x{SCENE_SITE:05X} link a6,#-4 ; pea.l -> jsr ${scene_addr:05X}.l",
        "Statics:",
        "  0x12C9A move.w #$8400,-(a7) -> #$8402 (R4: Plane B $4000)",
        "  0x12E68 pea $001000.w -> pea $004000.w (world_map_draw room -> Plane B)",
        "  0x16326 pea $001000.w -> pea $004000.w (world_map_redraw room -> Plane B)",
        "Checksums: fixed with tools/checksum.py fix-all (runtime 0xFD098, header 0x18E)",
        "",
    ]
    for off, data in records:
        lines.append(f"0x{off:05X}-0x{off + len(data) - 1:05X} ({len(data)} bytes):")
        for k in range(0, len(data), 16):
            chunk_o = orig[off + k:off + k + 16]
            chunk_n = data[k:k + 16]
            lines.append(f"  0x{off + k:05X}: {' '.join(f'{b:02x}' for b in chunk_o)}  -> "
                         f"{' '.join(f'{b:02x}' for b in chunk_n)}")
        lines.append("")
    open(os.path.join(DIR, "changed-bytes.txt"), "w").write("\n".join(lines))
    print(f"changed-bytes: {len(records)} records")

    # ---- original untouched ----
    assert hashlib.md5(open(ORIG, "rb").read()).hexdigest() == ORIG_MD5
    print("original ROM untouched (MD5 re-verified)")
    print("DONE")


if __name__ == "__main__":
    main()
