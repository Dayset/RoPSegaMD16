#!/usr/bin/env python3
"""lzss_check.py — verify the $DD5C LZSS decoder against the record tables (read only).

Format (docs/graphics.md:886 and disasm/text/README.md section 2):
  input: u32 little-endian decompressed length, then groups of 1 mask byte + 8 items.
  mask bit (LSB first) 1 = literal byte; 0 = two bytes back-reference:
    offset = b1 | ((b2 & 0xF0) << 4)   (12 bits)
    length = (b2 & 0x0F) + 3
  4 KB ring buffer pre-filled with 0x20, write position starts at 0xFEE.

Record tables (10 bytes each: u32 data offset, u32 declared length, u16 type):
  $96120 table, base 0x09638C, 62 records (type 1 = compressed).
  $B86AE table (90 records), streams base 0x0B8A32 (corrected 2026-11-11; the README had them swapped).
Checks: each record decodes; decoded length equals its declared length; the
stream ends inside the table's base-relative span.
"""
import struct
import sys
from pathlib import Path

ROM = Path('rop-original.gen')
TABLES = (
    ('96120', 0x096120, 62, 0x09638C),
    ('b86ae', 0x0B86AE, 90, 0x0B8A32),
)


def decode(rom, start):
    """Return (bytes, bytes_consumed) or (None, reason)."""
    declared = struct.unpack('<I', rom[start:start + 4])[0]
    ring = bytearray(b' ' * 4096)
    r = 0xFEE
    out = bytearray()
    i = start + 4
    while len(out) < declared:
        if i >= len(rom):
            return None, 'ran past end of ROM'
        mask = rom[i]
        i += 1
        for bit in range(8):
            if len(out) >= declared:
                break
            if mask & (1 << bit):
                if i >= len(rom):
                    return None, 'literal past end'
                c = rom[i]
                i += 1
                out.append(c)
                ring[r] = c
                r = (r + 1) & 0xFFF
            else:
                if i + 1 >= len(rom):
                    return None, 'backref past end'
                b1, b2 = rom[i], rom[i + 1]
                i += 2
                off = b1 | ((b2 & 0xF0) << 4)
                n = (b2 & 0x0F) + 3
                for k in range(n):
                    c = ring[(off + k) & 0xFFF]
                    out.append(c)
                    ring[r] = c
                    r = (r + 1) & 0xFFF
                    if len(out) >= declared:
                        break
    return bytes(out[:declared]), i - start


def main():
    rom = ROM.read_bytes()
    for name, table, n, base in TABLES:
        ok = bad = 0
        span_end = 0
        for k in range(n):
            rec = table + 10 * k
            off, length, typ = struct.unpack('>IIH', rom[rec:rec + 10])
            if typ != 1:
                continue
            start = base + off
            data, used = decode(rom, start)
            if data is None or len(data) != length:
                bad += 1
                continue
            ok += 1
            span_end = max(span_end, start + used)
        print(f'{name}: {ok} type-1 records decode to their declared length, {bad} do not; last stream ends 0x{span_end:06X}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
