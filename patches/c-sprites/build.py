#!/usr/bin/env python3
"""Build phase C of the full big rework (patches/c-sprites/).

Figures as sprites with per-frame interpolation (see
.scratch-big-rework-full/c-sprites/REPORT.md section 2).

The B2 blob is replaced wholesale: one contiguous blob at $FD400
(4782 bytes, to $FE6BE), covering the 0xFF padding $FD400-$FD8FF
plus B2's old blob region $FD900-$FDE30 plus the padding
$FDE30-$FE6BE. The original ROM is 0xFF from $FDE30 to the end
of the 1 MB ROM, so the blob may extend past $FE000; the build
asserts the padding before overwriting.

Base: rop-big-rework-full-b2.rom (MD5 ec7bcffe9c45fd851a6752dec5bcf788).
Output: rop-big-rework-full-c.rom + IPS (base -> C) + changed-bytes.txt.

Changes (all asserting the base ROM's bytes first):
  Blob at $FD400 (assembled from source.s with vasm, 6 entries
  via the listing file):
    vbl_entry      VBlank hook ($1272): B2's camera-target scroll
                   (UNCHANGED) + the sprite update at .vdone
                   (guarded by installed==1)
    redraw_entry   redraw_check hook ($1B918): B2's gate/install,
                   plus the jsr-wrap of the body (jsr $1B922, the
                   body returns to the blob) and the figure decode
                   after the DMA (up to K=3 figures)
    scene_entry    world_map_draw hook ($12C20): reset install state,
                   UNCHANGED from B2 (instruction-stream check)
    mapclose_entry world_map_redraw hook ($16302): reset on map close,
                   UNCHANGED from B2 (instruction-stream check)
    skip_hero      hero_track hook ($0231D8): skip figure draws
                   during the body's terrain decode
    skip_promote   map_promote_record hook ($02343A): same, + nop
  The new blob covers the entire old B2 blob, so there is no stale
  tail to clear; past the new blob end is already 0xFF (asserted).
  Statics and allocator: UNCHANGED from B2 (asserted, not touched).
  Checksums fixed with tools/checksum.py fix-all (no code is
  shifted, so the stock tool's runtime-immediate address stays valid).

Usage: python3 patches/c-sprites/build.py
"""
import hashlib
import os
import re
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
SCRATCH = os.path.join(REPO, 'build', 'scratch-c-sprites')
os.makedirs(SCRATCH, exist_ok=True)
WORKTREE = os.path.dirname(os.path.dirname(DIR))
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-big-rework-full-b2.rom'))
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
OUT_ROM = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-big-rework-full-c.rom'))
MAIN = REPO
CHECKSUM = os.path.join(MAIN, "tools", "checksum.py")
VENV_PY = os.environ.get('ROP_VENV_PY', os.path.join(REPO, 'tools', '.venv', 'bin', 'python'))
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

PAD_BASE = 0xFD400
B2_BLOB_BASE = 0xFD900
B2_BLOB_LEN = 1328
BASE_MD5 = "ec7bcffe9c45fd851a6752dec5bcf788"
ORIG_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"

VBL_SITE = 0x1272
REDRAW_SITE = 0x1B918
SCENE_SITE = 0x12C20
MAPCLOSE_SITE = 0x16302
HERO_SITE = 0x0231D8
PROMOTE_SITE = 0x02343A
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
    """Parse vasm -L listing for the six entry label addresses."""
    offs = {}
    pat = re.compile(r"^(vbl_entry|redraw_entry|scene_entry|mapclose_entry|skip_hero|skip_promote)\s+A:([0-9A-Fa-f]+)")
    for line in open(lst_path):
        m = pat.match(line)
        if m:
            offs[m.group(1)] = int(m.group(2), 16)
    missing = {"vbl_entry", "redraw_entry", "scene_entry", "mapclose_entry",
               "skip_hero", "skip_promote"} - set(offs)
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


def check_unchanged_entries(b2_blob, c_blob, offs_c):
    """The scene/mapclose entries must disassemble to the identical
    instruction stream as the B2 blob (see check_entries.py).
    Runs under the RoP venv python, which has capstone/m68k."""
    import json
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(offs_c, f)
        offs_path = f.name
    b2_path = os.path.join(SCRATCH, "b2.bin")
    open(b2_path, "wb").write(b2_blob)
    c_path = os.path.join(SCRATCH, "c.bin")
    open(c_path, "wb").write(c_blob)
    r = run([VENV_PY, os.path.join(DIR, "check_entries.py"),
             b2_path, c_path, offs_path])
    print(r.stdout, end="")
    os.remove(offs_path)


def main():
    base = open(BASE, "rb").read()
    assert len(base) == 0x100000, f"base size {len(base)}"
    assert hashlib.md5(base).hexdigest() == BASE_MD5, "base MD5 mismatch"
    assert hashlib.md5(open(ORIG, "rb").read()).hexdigest() == ORIG_MD5, \
        "original MD5 mismatch"
    assert all(b == 0xFF for b in base[PAD_BASE:B2_BLOB_BASE]), \
        "padding not 0xFF at $FD400-$FD900"
    assert all(b == 0xFF for b in base[B2_BLOB_BASE + B2_BLOB_LEN:]), \
        "padding not 0xFF after B2 blob end $FDE30"
    # B2 blob extracted from the base ROM (was: ../b2-strip/source.bin;
    # source.bin is a vasm output and is not committed). The base ROM's
    # MD5 is asserted above, so these bytes are the B2 blob.
    b2_blob = bytes(base[B2_BLOB_BASE:B2_BLOB_BASE + B2_BLOB_LEN])
    assert len(b2_blob) == B2_BLOB_LEN, f"B2 blob size {len(b2_blob)}"

    src = os.path.join(DIR, "source.s")
    binp = os.path.join(SCRATCH, "source.bin")
    lstp = os.path.join(SCRATCH, "source.lst")
    run([VASM, "-m68000", "-Fbin", "-o", binp, "-L", lstp, src])
    offs = listing_offsets(lstp)
    blob = open(binp, "rb").read()
    print(f"blob: {len(blob)} bytes at 0x{PAD_BASE:05X} "
          f"(vbl +0x{offs['vbl_entry']:X}, redraw +0x{offs['redraw_entry']:X}, "
          f"scene +0x{offs['scene_entry']:X}, "
          f"mapclose +0x{offs['mapclose_entry']:X}, "
          f"skip_hero +0x{offs['skip_hero']:X}, "
          f"skip_promote +0x{offs['skip_promote']:X})")
    assert offs["vbl_entry"] == 0, "vbl_entry must be first in the blob"
    assert PAD_BASE + len(blob) <= 0x100000, "blob overruns the end of the ROM"
    assert PAD_BASE > 0xFD07B, "blob must stay past the runtime checksum range"
    # the pad-byte read must be gone from vbl (camera-driven scroll, as B2)
    assert b"\x10\x39\x00\xff\x00\x18" not in blob, \
        "blob still reads the pad byte $FF0018"
    # camera-target immediates present: +-224 ($E0/$FF20), +-128 ($80/$FF80)
    for pat in (b"\x34\x3c\x00\xe0", b"\x34\x3c\xff\x20",
                b"\x36\x3c\x00\x80", b"\x36\x3c\xff\x80"):
        assert pat in blob, f"camera-target immediate {pat.hex()} missing"
    # figure-skip hook immediates: the displaced prologues must be
    # present in the skip entries (link a6,#0 + move.l a3,-(sp) /
    # movem.l d4-d5/a3,-(sp))
    assert b"\x4e\x56\x00\x00\x2f\x0b" in blob, "hero prologue missing from blob"
    assert b"\x4e\x56\x00\x00\x48\xe7\x0c\x10" in blob, "promote prologue missing"

    print("unchanged-entry disassembly check vs B2 blob:")
    check_unchanged_entries(b2_blob, blob, offs)

    vbl_addr = PAD_BASE + offs["vbl_entry"]
    redraw_addr = PAD_BASE + offs["redraw_entry"]
    scene_addr = PAD_BASE + offs["scene_entry"]
    mapclose_addr = PAD_BASE + offs["mapclose_entry"]
    skip_hero_addr = PAD_BASE + offs["skip_hero"]
    skip_promote_addr = PAD_BASE + offs["skip_promote"]

    rom = bytearray(base)
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob
    blob_end = PAD_BASE + len(blob)
    # no stale tail: the new blob covers the whole old B2 blob, and
    # everything past the new blob end is already 0xFF
    assert all(b == 0xFF for b in rom[blob_end:]), \
        "bytes past the new blob end are not 0xFF"
    print(f"blob covers 0x{PAD_BASE:05X}-0x{blob_end - 1:05X}; "
          f"past the end is 0xFF to the end of the ROM")

    def patch(off, expected, new, what):
        got = bytes(rom[off:off + len(expected)])
        assert got == expected, f"{what} 0x{off:05X}: expected {expected.hex()}, got {got.hex()}"
        rom[off:off + len(new)] = new
        print(f"patched {what}: 0x{off:05X} {expected.hex()} -> {new.hex()}")

    # VBlank hook: jmp $FD900 -> jmp $FD400 (nop unchanged)
    patch(VBL_SITE,
          bytes.fromhex("4ef9") + B2_BLOB_BASE.to_bytes(4, "big") + bytes.fromhex("4e71"),
          bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71"),
          "vblank hook $1272")
    # redraw_check hook: jsr $FDB54 -> jsr redraw_entry
    patch(REDRAW_SITE,
          bytes.fromhex("4eb9") + (B2_BLOB_BASE + 0x254).to_bytes(4, "big"),
          bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big"),
          "redraw_check hook $1B918")
    # world_map_draw hook: jsr $FDDC0 -> jsr scene_entry
    patch(SCENE_SITE,
          bytes.fromhex("4eb9") + (B2_BLOB_BASE + 0x4C0).to_bytes(4, "big"),
          bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big"),
          "world_map_draw hook $12C20")
    # world_map_redraw hook: jsr $FDDFA -> jsr mapclose_entry
    patch(MAPCLOSE_SITE,
          bytes.fromhex("4eb9") + (B2_BLOB_BASE + 0x4FA).to_bytes(4, "big"),
          bytes.fromhex("4eb9") + mapclose_addr.to_bytes(4, "big"),
          "world_map_redraw hook $16302")
    # hero_track hook: link a6,#0 ; move.l a3,-(sp) -> jsr skip_hero
    patch(HERO_SITE,
          bytes.fromhex("4e5600002f0b"),
          bytes.fromhex("4eb9") + skip_hero_addr.to_bytes(4, "big"),
          "hero_track hook $0231D8")
    # map_promote_record hook: link a6,#0 ; movem.l d4-d5/a3,-(sp)
    #   -> jsr skip_promote ; nop
    patch(PROMOTE_SITE,
          bytes.fromhex("4e56000048e70c10"),
          bytes.fromhex("4eb9") + skip_promote_addr.to_bytes(4, "big") + bytes.fromhex("4e71"),
          "map_promote_record hook $02343A")
    # Statics + allocator: UNCHANGED from B2, assert only
    assert bytes(rom[STATIC_R4:STATIC_R4 + 4]) == bytes.fromhex("3f3c8407"), \
        "R4 static $12C9A is not $8407"
    assert bytes(rom[STATIC_DRAW:STATIC_DRAW + 4]) == bytes.fromhex("4878e000"), \
        "room draw dest $12E68 is not pea $E000"
    assert bytes(rom[STATIC_REDRAW:STATIC_REDRAW + 4]) == bytes.fromhex("4878e000"), \
        "redraw draw dest $16326 is not pea $E000"
    assert bytes(rom[0x12CDE:0x12CE2]) == bytes.fromhex("3f3c9001"), \
        "R16 site $12CDE is not $9001"
    print("statics verified unchanged from B2 (R4 $8407, pea $E000 x2, R16 $9001)")
    assert bytes(rom[ALLOC_START:ALLOC_END]) == base[ALLOC_START:ALLOC_END], \
        "allocator region changed (must stay B2's)"
    print("allocator region verified unchanged from B2")

    tmp = os.path.join(SCRATCH, "rop-big-rework-full-c.gen.tmp")
    open(tmp, "wb").write(rom)
    run([VENV_PY, CHECKSUM, "fix-all", tmp, OUT_ROM])
    os.remove(tmp)
    v = run([VENV_PY, CHECKSUM, "verify-all", OUT_ROM]).stdout.strip()
    print(f"patched ROM: {OUT_ROM} — {v}")

    chk = open(OUT_ROM, "rb").read()
    assert chk[PAD_BASE:PAD_BASE + len(blob)] == blob
    assert all(b == 0xFF for b in chk[blob_end:]), \
        "bytes past the blob end are not 0xFF in the output ROM"
    assert chk[VBL_SITE:VBL_SITE + 8] == bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71")
    assert chk[REDRAW_SITE:REDRAW_SITE + 6] == bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big")
    assert chk[SCENE_SITE:SCENE_SITE + 6] == bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big")
    assert chk[MAPCLOSE_SITE:MAPCLOSE_SITE + 6] == bytes.fromhex("4eb9") + mapclose_addr.to_bytes(4, "big")
    assert chk[HERO_SITE:HERO_SITE + 6] == bytes.fromhex("4eb9") + skip_hero_addr.to_bytes(4, "big")
    assert chk[PROMOTE_SITE:PROMOTE_SITE + 8] == bytes.fromhex("4eb9") + skip_promote_addr.to_bytes(4, "big") + bytes.fromhex("4e71")
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
    ips_path = os.path.join(DIR, "rings-of-power-big-rework-full-c.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} — {len(ips)} bytes, {len(records)} records")

    # ---- IPS round-trip: applying the IPS to the base must reproduce the ROM ----
    rt = apply_ips(base, bytes(ips))
    assert rt == chk, "IPS round-trip FAILED: applied IPS != patched ROM"
    print("IPS round-trip verified: base + IPS == ROM exactly")

    # ---- changed-bytes.txt ----
    lines = [
        "Changed bytes: rop-big-rework-full-b2.rom (MD5 ec7bcffe9c45fd851a6752dec5bcf788)"
        " -> rop-big-rework-full-c.rom (big-rework-full phase C: figures as sprites"
        " with per-frame interpolation -- see .scratch-big-rework-full/c-sprites/REPORT.md)",
        "IPS applies to rop-big-rework-full-b2.rom, NOT to the original ROM.",
        "All addresses are 68000 ROM offsets (= file offsets). Values are hex bytes.",
        "",
        f"Trampoline blob: 0x{PAD_BASE:05X}-0x{blob_end - 1:05X} "
        f"({len(blob)} bytes, source.s assembled with vasm; B2 blob was 1328 bytes to $FDE30)",
        f"  vbl_entry      0x{vbl_addr:05X} (VBlank hook: B2 camera-target scroll + sprite update)",
        f"  redraw_entry   0x{redraw_addr:05X} (redraw_check hook: B2 gate/install + jsr wrap + figure decode)",
        f"  scene_entry    0x{scene_addr:05X} (world_map_draw hook: reset install state, unchanged from B2)",
        f"  mapclose_entry 0x{mapclose_addr:05X} (world_map_redraw hook: reset on map close, unchanged from B2)",
        f"  skip_hero      0x{skip_hero_addr:05X} (hero_track hook: skip figure draws in body decode)",
        f"  skip_promote   0x{skip_promote_addr:05X} (map_promote_record hook: same, + nop)",
        "Hooks:",
        f"  0x{VBL_SITE:05X} jmp $FD900.l ; nop -> jmp ${vbl_addr:05X}.l ; nop",
        f"  0x{REDRAW_SITE:05X} jsr $FDB54.l -> jsr ${redraw_addr:05X}.l",
        f"  0x{SCENE_SITE:05X} jsr $FDDC0.l -> jsr ${scene_addr:05X}.l",
        f"  0x{MAPCLOSE_SITE:05X} jsr $FDDFA.l -> jsr ${mapclose_addr:05X}.l",
        f"  0x{HERO_SITE:05X} link a6,#0 ; move.l a3,-(sp) -> jsr ${skip_hero_addr:05X}.l",
        f"  0x{PROMOTE_SITE:05X} link a6,#0 ; movem.l d4-d5/a3,-(sp) -> jsr ${skip_promote_addr:05X}.l ; nop",
        "Statics / allocator: unchanged from B2 (R4 $8407, pea $E000 x2, R16 $9001,",
        "  allocator $12D00-$12DE7 as B2) -- asserted, not touched.",
        "No stale blob tail: the new blob covers the whole old B2 blob and the",
        "  bytes past the new blob end are 0xFF to the end of the ROM.",
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
