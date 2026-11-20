#!/usr/bin/env python3
"""Build the flat-zoom ROM (flat texture, zoomed view only) from the ORIGINAL ROM.

Flat-only: NO subcell-movement change (subcell is a separate step, built on
top of this ROM afterwards). Patches the three map_chunk_pos jsr $E358 sites
to the flat stubs at $FD400:
  $01BC1A (face)   -> jsr flat_level ($FD400)
  $01BC3C (hidden) -> jsr flat_level ($FD400)
  $01BC84 (top)    -> jsr flat_top   ($FD418)
In the room view ($FF00AE==2) each stub writes a flat fill instead of
decoding the terrain stream; in the world view ($FF00AE!=2) it tail-calls
the original $E358, so the world view is byte-identical in behaviour.
Checksums are fixed afterwards with tools/checksum.py fix-all.

Outputs (this directory):
  - build/rop-flat-zoom.rom  (ROM, .rom per Dayset's 2026-11-12 call)
  - rop-flat-zoom.ips  (apply to a clean original ROM)
  - changed-bytes.txt  (original -> patched, for review)

Usage: python3 patches/flat-zoom/build.py
"""
import hashlib
import os
import re
import struct
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"
VENV_PY = os.environ.get('ROP_VENV_PY', os.path.join(REPO, 'tools', '.venv', 'bin', 'python'))
# vasm: repo tools/vasm (make vasm) or ROP_VASM.
SCRATCH = os.path.join(REPO, 'build', 'scratch-flat-zoom')
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-flat-zoom.rom'))
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

PAD_BASE = 0xFD400
JSR_E358 = bytes.fromhex("4eb90000e358")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def main():
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    vasm = VASM
    assert os.path.exists(vasm), "vasmm68k_mot not found: run `make vasm` or set ROP_VASM"
    src = os.path.join(DIR, "source.s")
    binp = os.path.join(SCRATCH, "flat.bin")
    lst = os.path.join(SCRATCH, "flat.lst")
    run([vasm, "-Fbin", "-L", lst, "-o", binp, src])
    blob = open(binp, "rb").read()
    print(f"flat blob: {len(blob)} bytes")
    listing = open(lst).read()

    def _addr(label):
        m = re.search(r"^%s\s+A:([0-9a-fA-F]+)" % label, listing, re.M)
        assert m, label
        return int(m.group(1), 16)

    FLAT_LEVEL = _addr("flat_level")
    FLAT_TOP = _addr("flat_top")
    print(f"flat_level=0x{FLAT_LEVEL:05X} flat_top=0x{FLAT_TOP:05X}")

    rom = bytearray(open(ORIG, "rb").read())
    assert len(rom) == 1048576, len(rom)
    assert hashlib.md5(bytes(rom)).hexdigest() == ORIG_MD5, "original ROM MD5 mismatch"
    assert set(rom[PAD_BASE:PAD_BASE + len(blob)]) == {0xFF}, "blob area not free padding"
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob
    patches = {0x1BC1A: FLAT_LEVEL, 0x1BC3C: FLAT_LEVEL, 0x1BC84: FLAT_TOP}
    for addr, target in patches.items():
        assert rom[addr:addr + 6] == JSR_E358, (hex(addr), rom[addr:addr + 6].hex())
        rom[addr:addr + 6] = b"\x4e\xb9" + struct.pack(">I", target)
    tmp = os.path.join(DIR, "rop-flat-zoom.rom.tmp")
    outp = OUT
    open(tmp, "wb").write(bytes(rom))
    run([VENV_PY, CHECKSUM, "fix-all", tmp, outp])
    os.remove(tmp)
    print(run([VENV_PY, CHECKSUM, "verify-all", outp]).stdout.strip())
    patched = open(outp, "rb").read()
    print(f"patched ROM MD5: {hashlib.md5(patched).hexdigest()}")

    # ---- IPS: diff original -> patched, one record per maximal changed run ----
    orig = open(ORIG, "rb").read()
    assert len(orig) == len(patched)
    records = []
    i = 0
    while i < len(orig):
        if orig[i] != patched[i]:
            j = i
            while j < len(orig) and orig[j] != patched[j] and j - i < 0xFFFF:
                j += 1
            records.append((i, patched[i:j]))
            i = j
        else:
            i += 1
    ips = bytearray(b"PATCH")
    for off, data in records:
        ips += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    ips += b"EOF"
    ips_path = os.path.join(DIR, "rop-flat-zoom.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} — {len(ips)} bytes, {len(records)} records")

    # ---- IPS round-trip verification: original + IPS == patched ROM exactly ----
    out = bytearray(orig)
    p = 5
    while ips[p:p + 3] != b"EOF":
        off = int.from_bytes(ips[p:p + 3], "big")
        ln = int.from_bytes(ips[p + 3:p + 5], "big")
        p += 5
        if ln == 0:  # RLE record (not emitted by this builder)
            rle_len = int.from_bytes(ips[p:p + 2], "big")
            out[off:off + rle_len] = bytes([ips[p + 2]]) * rle_len
            p += 3
        else:
            out[off:off + ln] = ips[p:p + ln]
            p += ln
    assert bytes(out) == patched, "IPS round-trip FAILED"
    print("IPS round-trip verified: original + IPS == patched ROM exactly")

    # ---- changed-bytes.txt ----
    lines = ["Changed bytes: original (MD5 30c18fdbe2183f64702ae9f1a45d63f9) -> flat-zoom ROM",
             "All addresses are 68000 ROM offsets (= file offsets). Values are hex bytes.", ""]
    for off, data in records:
        lines.append(f"0x{off:05X}-0x{off+len(data)-1:05X} ({len(data)} bytes):")
        for k in range(0, len(data), 16):
            chunk_n = data[k:k + 16]
            chunk_o = orig[off + k:off + k + len(chunk_n)]
            lines.append(f"  0x{off+k:05X}: {' '.join(f'{b:02x}' for b in chunk_o)}  ->  {' '.join(f'{b:02x}' for b in chunk_n)}")
        lines.append("")
    open(os.path.join(DIR, "changed-bytes.txt"), "w").write("\n".join(lines))

    print(f"ROM: {outp}  MD5 {hashlib.md5(patched).hexdigest()}")


if __name__ == "__main__":
    main()
