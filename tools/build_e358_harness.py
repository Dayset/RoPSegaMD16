#!/usr/bin/env python3
"""Build the $E358 ground-truth harness ROM (issue #252, Track A).

Assembles tools/e358_harness.s with m68k-linux-gnu-as (the prior
harness toolchain), injects the blob at 0xFD0CC, writes the 6-byte
`jsr $FD0CC.l` hook at 0x35C, fixes both checksums, writes
build/e358_harness.gen. Never touches rop-original.gen.
"""
import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK_ADDR = 0x35C
BLOB_ADDR = 0xFD0CC
HOOK_BYTES = bytes([0x4E, 0xB9, 0x00, 0x0F, 0xD0, 0xCC])  # jsr $FD0CC.l


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", type=int, default=-1,
                    help="build a single-case halt ROM for case N")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=4298)
    a = ap.parse_args()
    if a.single >= 0:
        out_rom = REPO / "build" / ("e358_single_%d.gen" % a.single)
        start, end = a.single, a.single + 1
    elif a.start != 0 or a.end != 4298:
        out_rom = REPO / "build" / ("e358_chunk_%d_%d.gen" % (a.start, a.end))
        start, end = a.start, a.end
    else:
        out_rom = REPO / "build" / "e358_harness.gen"
        start, end = 0, 4298
    out_rom.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPO / "build" / "e358_harness.o"
    blob = REPO / "build" / "e358_harness.bin"
    src = REPO / "tools" / "e358_harness.s"
    subprocess.run(["m68k-linux-gnu-as", "-m68000",
                    "--defsym", "START_CASE=%d" % start,
                    "--defsym", "END_CASE=%d" % end,
                    "-o", str(tmp), str(src)],
                   check=True)
    subprocess.run(["m68k-linux-gnu-objcopy", "-O", "binary", str(tmp), str(blob)],
                   check=True)
    data = bytearray((REPO / "rop-original.gen").read_bytes())
    code = blob.read_bytes()
    print("harness blob: %d bytes at $%X" % (len(code), BLOB_ADDR))
    if BLOB_ADDR + len(code) > 0x100000:
        raise SystemExit("harness blob overruns the ROM")
    if any(b != 0xFF for b in data[BLOB_ADDR:BLOB_ADDR + len(code)]):
        raise SystemExit("blob region is not free ($FF padding)")
    data[BLOB_ADDR:BLOB_ADDR + len(code)] = code
    orig_hook = bytes(data[HOOK_ADDR:HOOK_ADDR + 6])
    print("hook site $35C was: %s" % orig_hook.hex())
    data[HOOK_ADDR:HOOK_ADDR + 6] = HOOK_BYTES
    raw = REPO / "build" / "e358_harness.raw.gen"
    raw.write_bytes(bytes(data))
    subprocess.run([sys.executable, str(REPO / "tools" / "checksum.py"),
                    "fix-all", str(raw), str(out_rom)], check=True)
    print("wrote %s" % out_rom)
    subprocess.run([sys.executable, str(REPO / "tools" / "checksum.py"),
                    "verify-all", str(out_rom)], check=True)
    print("checksums verify OK")


if __name__ == "__main__":
    main()
