#!/usr/bin/env python3
"""tools/decode_44000.py — decoder for the 0x044000 block's data archive
(issue #017, session #5).

The block 0x044000-0x05FFFF is NOT an unknown codec. Its layout:

  0x043850-0x044227  descriptor table: 252 records x 10 bytes in the
                     $13654 dispatcher format (u32 BE offset, u32 BE
                     decompressed size, u16 type; type 1 = $DD5C).
                     The table straddles the 0x044000 block boundary:
                     records 197-251 are the "55-entry index" at the
                     block head that earlier sessions read misaligned.
  0x044228-0x05EDC3  the archive: 252 $DD5C streams packed back to
                     back, in descriptor order. Sizes: 77 records of
                     2048 bytes, then 153 of 242, then 22 of 2048.
  0x05F524-0x0603E3  the $E358 pointer table (tail, see decode_e358.py).

Decompressed content is VDP nametable data: the 2048-byte records are
32x32 u16 tilemap words, the 242-byte records are 11x11 u16 tilemap
words (tile index in bits 0-10, palette/flip bits above).

Consumer (verified statically): FUN_00019692 (called via the thunk
FUN_0001C802) pushes (dest, index, $43850, $44228) and calls the
record dispatcher $13654, whose type-1 path jsr's $DD5C. The loader
keeps a 4-slot rotating cache of 2048-byte buffers at $FF868C.

Usage:
  decode_44000.py              summary + verification of all 252 records
  decode_44000.py INDEX        dump record INDEX as a word grid
  decode_44000.py INDEX --bin  write the decompressed record to stdout
"""
import struct
import sys

sys.path.insert(0, 'tools')
from extract_text import dd5c_decompress

ROM_PATH = 'rop-original.gen'
TABLE = 0x43850           # descriptor table (252 x 10 bytes)
ARCHIVE = 0x44228         # first stream; table ends exactly here
COUNT = (ARCHIVE - TABLE) // 10

rom = open(ROM_PATH, 'rb').read()


def descriptor(i):
    off, size, typ = struct.unpack_from('>IIH', rom, TABLE + i * 10)
    return off, size, typ


def record(i):
    off, size, typ = descriptor(i)
    if typ != 1:
        raise ValueError(f'record {i}: type {typ} != 1 (not $DD5C)')
    out = dd5c_decompress(rom, ARCHIVE + off)
    if out is None:
        raise ValueError(f'record {i}: $DD5C decode failed')
    data, _consumed = out
    if len(data) != size:
        raise ValueError(f'record {i}: decoded {len(data)} != descriptor {size}')
    return data


def main():
    if len(sys.argv) > 1:
        i = int(sys.argv[1], 0)
        data = record(i)
        if '--bin' in sys.argv:
            sys.stdout.buffer.write(data)
            return
        words = struct.unpack(f'>{len(data) // 2}H', data)
        width = 32 if len(data) == 2048 else 11
        print(f'record {i}: {len(data)} bytes, {width}x{len(words) // width} u16 grid')
        for r in range(0, len(words), width):
            print(' '.join(f'{w:5d}' for w in words[r:r + width]))
        return
    sizes = {}
    total = 0
    for i in range(COUNT):
        data = record(i)
        sizes[len(data)] = sizes.get(len(data), 0) + 1
        total += len(data)
    print(f'{COUNT}/{COUNT} descriptor records decode byte-exactly '
          f'($DD5C, sizes verified against descriptors)')
    print(f'decompressed total: {total} bytes; size histogram: '
          f'{dict(sorted(sizes.items()))}')


if __name__ == '__main__':
    main()
