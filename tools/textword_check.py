#!/usr/bin/env python3
"""textword_check.py — check the $DDBD8 dialogue word-array records against the dictionary (read only).

Records: 1184 x (u32 offset, u32 length, u16 type) at 0x0DDBD8, type 5 (docs/text, disasm/text/README.md section 1).
Arrays: base 0x0E0A18 + offset, count = (length >> 1) + 1 u16 entries.
Entry: low 14 bits = 1-based dictionary word index (1..3466); top 2 bits = separator selector.
Expected: every entry in range except record 1183, which the README calls malformed.
"""
import struct
import sys
from pathlib import Path

ROM = Path('rop-original.gen')
REC, N, BASE, DICT_WORDS = 0x0DDBD8, 1184, 0x0E0A18, 3466


def main():
    rom = ROM.read_bytes()
    bad_records = []
    out_of_range = 0
    types = set()
    for k in range(N):
        off, length, typ = struct.unpack('>IIH', rom[REC + 10 * k:REC + 10 * k + 10])
        types.add(typ)
        base = BASE + off
        for j in range((length >> 1) + 1):
            e = struct.unpack('>H', rom[base + 2 * j:base + 2 * j + 2])[0]
            idx = e & 0x3FFF
            if not 1 <= idx <= DICT_WORDS:
                out_of_range += 1
                bad_records.append(k)
    print(f'records {N}, types {sorted(types)}')
    print(f'entries out of dictionary range: {out_of_range}, in records {sorted(set(bad_records))}')
    expected = {1183}
    print('as documented' if set(bad_records) == expected else 'UNEXPECTED: differs from README expectation')
    return 0


if __name__ == '__main__':
    sys.exit(main())
