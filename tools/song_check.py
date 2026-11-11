#!/usr/bin/env python3
"""song_check.py — parse each Z80 song stream with the event grammar in docs/sound.md section 6 (read only).

Grammar (docs/sound.md:286):
  leading byte < 0x80 is skipped by the song init
  0x8X / 0x9X  -> 4 bytes  [event][p1][p2][delay]
  0xCX         -> 3 bytes  [event][param][delay]
  0xFC 0x80    -> skip to the next 256-byte boundary counted from the song start (not parsed)
  0xFC other   -> end of song
  anything else -> invalid (the Z80 jumps to $08C8, an infinite loop)
Table: docs/sound.md section 7.1 (index, start, stream length). Songs marked
"ends" in the doc must reach an 0xFC-end event; songs marked "loops" must parse
their whole length with no invalid byte and no early end.
"""
import sys
from pathlib import Path

ROM = Path('rop-original.gen')
# (index, start, stream_len, ends_doc)
SONGS = [
    (0, 0x0ED0E8, 1280, False), (1, 0x0EDDBA, 4608, False), (2, 0x0ED4FE, 2304, False),
    (3, 0x0EEF8C, 3328, False), (4, 0x0EFBC8, 3072, False), (5, 0x0FA926, 5120, False),
    (6, 0x0F0C32, 6912, False), (7, 0x0F26CC, 4096, False), (8, 0x0F363E, 256, True),
    (9, 0x0F36AC, 6912, False), (10, 0x0F5182, 3328, False), (11, 0x00692E, 12800, False),
    (12, 0x0F5DAE, 2816, False), (13, 0x0F6844, 10240, False), (14, 0x0F900A, 3072, False),
    (15, 0x0F9B38, 3584, False), (16, 0x0F075E, 1280, True), (17, 0x0FBC7C, 3840, False),
]


def parse(rom, start, length):
    i = start
    end = start + length
    if rom[i] < 0x80:
        i += 1
    events = 0
    while i < end:
        b = rom[i]
        if b & 0x80 == 0:
            return 'invalid-lead-byte', i - start, events
        hi = b & 0xF0
        if hi in (0x80, 0x90):
            i += 4
        elif hi == 0xC0:
            i += 3
        elif b == 0xFC:
            if i + 1 >= end:
                return 'truncated-fc', i - start, events
            nxt = rom[i + 1]
            if nxt == 0x80:
                # boundary counted from the song start (the stream is read in 256-byte chunks from its base)
                rel = i + 2 - start
                i = start + ((rel + 255) // 256) * 256
                events += 1
                continue
            return 'end', i - start, events
        else:
            return 'invalid', i - start, events
        events += 1
    return 'loops-to-length', end - start, events


def main():
    rom = ROM.read_bytes()
    agree = 0
    for idx, start, length, ends in SONGS:
        result, pos, events = parse(rom, start, length)
        if ends:
            ok = result == 'end'
        else:
            ok = result == 'loops-to-length'
        agree += ok
        print(f'song {idx:2d} start 0x{start:06X} len {length:5d}: {result:18s} at +{pos:5d} events {events:5d} '
              f'{"OK" if ok else "MISMATCH"} (doc: {"ends" if ends else "loops"})')
    print(f'{agree} of {len(SONGS)} songs agree with the documented end behaviour')
    return 0


if __name__ == '__main__':
    sys.exit(main())
