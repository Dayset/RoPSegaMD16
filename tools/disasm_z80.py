#!/usr/bin/env python3
"""disasm_z80.py — disassemble the Z80 sound-driver blob (issue #018).

Extracts the blob the 68K uploads at $EB806 (ROM $EBB6E, 0x1576
bytes) and disassembles it with z80dis (pip install z80dis into
tools/.venv). The blob loads at Z80 address 0x0000.
Usage: tools/.venv/bin/python tools/disasm_z80.py [rom] > listing.txt
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOB_OFF, BLOB_LEN = 0xEBB6E, 0x1576


def main():
    from z80dis import z80
    rom = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "rop-original.gen").read_bytes()
    blob = rom[BLOB_OFF:BLOB_OFF + BLOB_LEN]
    addr = 0
    while addr < len(blob):
        try:
            d = z80.decode(blob[addr:], addr)
            text = z80.decoded2str(d)
            size = d.len
        except Exception:
            text, size = "db 0x%02X" % blob[addr], 1
        raw = blob[addr:addr + size]
        print("%04X: %-14s %s" % (addr, raw.hex(" "), text))
        addr += size
    return 0


if __name__ == "__main__":
    sys.exit(main())
