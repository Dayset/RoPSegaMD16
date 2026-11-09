#!/usr/bin/env python3
"""Build the #037 smooth-motion patch (patches/smooth-move/).

Assembles smooth037.s, places it in the 0xFF padding at 0xFD0CC, patches the
$1B918 hook site (asserting the original bytes first), fixes both checksums
with tools/checksum.py fix-all, verifies, and writes:
  - rings-of-power-smooth-move.ips  (committable; apply to a clean original)
  - rop-smooth.gen                  (git-ignored patched ROM for Dayset)
  - changed-bytes.txt               (original -> patched, for review)
Usage: python3 patches/smooth-move/build.py
"""
import os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(REPO, "patches", "smooth-move")
ORIG = os.path.join(REPO, "rop-original.gen")
CHECKSUM = os.path.join(REPO, "tools", "checksum.py")
VENV_PY = os.path.join(REPO, "tools", ".venv", "bin", "python")

PAD_BASE = 0xFD0CC
HOOK_SITE = 0x1B918
HOOK_ORIG = bytes.fromhex("4e56fffe4a79")   # link a6,#-2 ; tst.w $FF009C (first 2 bytes)

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r

def main():
    src = os.path.join(DIR, "smooth037.s")
    obj = os.path.join(DIR, "smooth037.o")
    binp = os.path.join(DIR, "smooth037.bin")
    run(["m68k-linux-gnu-as", "-m68000", "-o", obj, src])
    run(["m68k-linux-gnu-objcopy", "-O", "binary", obj, binp])
    blob = open(binp, "rb").read()
    print(f"harness: {len(blob)} bytes (pad 0xFD0CC-0xFFFFF = 12084 free)")
    assert PAD_BASE + len(blob) <= 0x100000
    rom = bytearray(open(ORIG, "rb").read())
    assert len(rom) == 0x100000
    assert all(x == 0xFF for x in rom[PAD_BASE:PAD_BASE + len(blob)]), \
        "padding not 0xFF under harness"
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob
    assert rom[HOOK_SITE:HOOK_SITE + 6] == HOOK_ORIG, \
        f"hook site 0x{HOOK_SITE:05X}: expected {HOOK_ORIG.hex()}, got {rom[HOOK_SITE:HOOK_SITE+6].hex()}"
    rom[HOOK_SITE:HOOK_SITE + 6] = bytes([0x4E, 0xB9]) + PAD_BASE.to_bytes(4, "big")
    tmp = os.path.join(DIR, "rop-smooth.gen.tmp")
    out = os.path.join(DIR, "rop-smooth.gen")
    open(tmp, "wb").write(rom)
    run([VENV_PY, CHECKSUM, "fix-all", tmp, out])
    os.remove(tmp)
    v = run([VENV_PY, CHECKSUM, "verify-all", out]).stdout.strip()
    print(f"patched ROM: {out} — {v}")
    chk = open(out, "rb").read()
    assert chk[HOOK_SITE:HOOK_SITE + 6] == bytes([0x4E, 0xB9]) + PAD_BASE.to_bytes(4, "big")
    assert chk[PAD_BASE:PAD_BASE + len(blob)] == blob
    print("hook bytes + harness verified in place")

    # ---- IPS: diff original -> patched, one record per maximal changed run ----
    orig = open(ORIG, "rb").read()
    assert len(orig) == len(chk)
    records = []
    i = 0
    while i < len(orig):
        if orig[i] != chk[i]:
            j = i
            while j < len(orig) and orig[j] != chk[j] and j - i < 0xFFFF:
                j += 1
            records.append((i, chk[i:j]))
            i = j
        else:
            i += 1
    ips = bytearray(b"PATCH")
    for off, data in records:
        ips += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    ips += b"EOF"
    ips_path = os.path.join(DIR, "rings-of-power-smooth-move.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} — {len(ips)} bytes, {len(records)} records")

    # ---- changed-bytes.txt ----
    lines = ["Changed bytes: original (MD5 30c18fdbe2183f64702ae9f1a45d63f9) -> patched ROM",
             "All addresses are 68000 ROM offsets (= file offsets). Values are hex bytes.", ""]
    for off, data in records:
        lines.append(f"0x{off:05X}-0x{off+len(data)-1:05X} ({len(data)} bytes):")
        for k in range(0, len(data), 16):
            chunk_o = orig[off+k:off+k+16]
            chunk_n = data[k:k+16]
            lines.append(f"  0x{off+k:05X}: {' '.join(f'{b:02x}' for b in chunk_o)}  ->  {' '.join(f'{b:02x}' for b in chunk_n)}")
        lines.append("")
    open(os.path.join(DIR, "changed-bytes.txt"), "w").write("\n".join(lines))
    print(f"changed-bytes: {len(records)} records")
    print("DONE")

if __name__ == "__main__":
    main()
