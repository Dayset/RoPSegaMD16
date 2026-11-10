#!/usr/bin/env python3
"""Build the debug overlay patch (patches/debug-overlay/).

Assembles overlay.s, places it in the 0xFF padding at 0xFD200, patches the
$1272 VBlank hook site (asserting the original bytes first), fixes both
checksums with tools/checksum.py fix-all, verifies, and writes:
  - rings-of-power-debug-overlay.ips  (committable; apply to a clean original)
  - rop-debug-overlay.gen            (git-ignored patched ROM for Dayset)
  - changed-bytes.txt                (original -> patched, for review)
Usage: python3 patches/debug-overlay/build.py
"""
import os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(REPO, "patches", "debug-overlay")
ORIG = os.path.join(REPO, "rop-original.gen")
CHECKSUM = os.path.join(REPO, "tools", "checksum.py")
VENV_PY = os.path.join(REPO, "tools", ".venv", "bin", "python")

PAD_BASE = 0xFD200
PAD_LEN = 0x200            # 512 bytes allocated ($FD200-$FD3FF)
HOOK_SITE = 0x1272
HOOK_ORIG = bytes.fromhex("33fc000000ff0016")   # move.w #$0,$FF0016 (8 bytes)
HOOK_NEW = bytes.fromhex("4ef9000fd2004e71")    # jmp $FD200.l ; nop

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r

def main():
    src = os.path.join(DIR, "overlay.s")
    obj = os.path.join(DIR, "overlay.o")
    binp = os.path.join(DIR, "overlay.bin")
    run(["m68k-linux-gnu-as", "-m68000", "-o", obj, src])
    run(["m68k-linux-gnu-objcopy", "-O", "binary", obj, binp])
    blob = open(binp, "rb").read()
    print(f"overlay: {len(blob)} bytes (pad 0xFD200-0xFD3FF = {PAD_LEN} allocated)")
    assert len(blob) <= PAD_LEN, f"overlay too big: {len(blob)} > {PAD_LEN}"
    rom = bytearray(open(ORIG, "rb").read())
    assert len(rom) == 0x100000
    assert all(x == 0xFF for x in rom[PAD_BASE:PAD_BASE + len(blob)]), \
        "padding not 0xFF under overlay"
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob
    assert rom[HOOK_SITE:HOOK_SITE + 8] == HOOK_ORIG, \
        f"hook site 0x{HOOK_SITE:05X}: expected {HOOK_ORIG.hex()}, got {rom[HOOK_SITE:HOOK_SITE+8].hex()}"
    rom[HOOK_SITE:HOOK_SITE + 8] = HOOK_NEW
    tmp = os.path.join(DIR, "rop-debug-overlay.gen.tmp")
    out = os.path.join(DIR, "rop-debug-overlay.gen")
    open(tmp, "wb").write(rom)
    run([VENV_PY, CHECKSUM, "fix-all", tmp, out])
    os.remove(tmp)
    v = run([VENV_PY, CHECKSUM, "verify-all", out]).stdout.strip()
    print(f"patched ROM: {out} — {v}")
    chk = open(out, "rb").read()
    assert chk[HOOK_SITE:HOOK_SITE + 8] == HOOK_NEW
    assert chk[PAD_BASE:PAD_BASE + len(blob)] == blob
    print("hook bytes + overlay verified in place")

    # ---- IPS: diff original -> patched, one record per maximal changed run ----
    orig = open(ORIG, "rb").read()
    patched = open(out, "rb").read()
    records = []
    i = 0
    n = len(orig)
    while i < n:
        if orig[i] != patched[i]:
            j = i
            while j < n and orig[j] != patched[j] and j - i < 0xFFFF:
                j += 1
            records.append((i, patched[i:j]))
            i = j
        else:
            i += 1
    ips = bytearray(b"PATCH")
    for off, data in records:
        ips += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    ips += b"EOF"
    ips_path = os.path.join(DIR, "rings-of-power-debug-overlay.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} ({len(ips)} bytes, {len(records)} records)")

    # ---- changed-bytes.txt ----
    cb = os.path.join(DIR, "changed-bytes.txt")
    with open(cb, "w") as f:
        f.write("debug overlay: original -> patched ROM (rop-debug-overlay.gen)\n")
        f.write(f"hook: 0x{HOOK_SITE:05X} {HOOK_ORIG.hex()} -> {HOOK_NEW.hex()} (jmp $FD200.l ; nop)\n")
        f.write(f"trampoline: 0x{PAD_BASE:05X}-0x{PAD_BASE+len(blob)-1:05X} ({len(blob)} bytes, overlay.s)\n")
        f.write("checksums: fixed with tools/checksum.py fix-all (runtime 0xFD098, header 0x18E)\n")
        for off, data in records:
            f.write(f"0x{off:05X}: {len(data)} bytes changed\n")
    print(f"changed-bytes: {cb}")

if __name__ == "__main__":
    main()
