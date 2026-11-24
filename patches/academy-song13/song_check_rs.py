#!/usr/bin/env python3
"""song_check_rs.py — RS-aware song parser, mirroring the Z80 driver.

The strict grammar in tools/song_check.py does not model running-status,
but the real parser ($08F8) does: at event-fetch time, if the next stream
byte is < $80, it re-dispatches the last event byte held in $00E7 instead
of consuming a new event byte (hand-verified in the driver code at
$0936-$0940: `ld a,(iy+0); and a; jp m,$0942; ld a,($00E7)`).
Delay 0 fetches the next event immediately ($0957: `jr z,$0932` when
$00E8==0) — no wait, no underflow.

Grammar (docs/sound.md section 6 + $08F8/$084C):
  leading byte < 0x80 is skipped by the song init ($0804)
  fetch byte: >= 0x80 -> new event byte (saved as last_ev), pointer advances
              < 0x80 -> re-dispatch last_ev; the byte is p1, pointer NOT advanced
  0x8X / 0x9X  -> [p1][p2][delay] (4 B full, 3 B running-status)
  0xCX         -> [param][delay] (3 B full, 2 B running-status)
  0xFC 0x80    -> skip to next 256-byte boundary counted from the song start
  0xFC other   -> end of song
  anything else -> invalid (Z80 jp $08C8, infinite loop)

Usage:
  song_check_rs.py <rom>              # check all songs' end behaviour
  song_check_rs.py <rom> --diff-orig  # also diff song 11's event sequence
                                      # against rop-original.gen (strict
                                      # parse): expect only inserted $94 bass
                                      # events + scaled ch3 $9X p2 values.
"""
import struct
import sys
from pathlib import Path

SONGS = [
    (0, 0x0ED0E8, 1280, False), (1, 0x0EDDBA, 4608, False), (2, 0x0ED4FE, 2304, False),
    (3, 0x0EEF8C, 3328, False), (4, 0x0EFBC8, 3072, False), (5, 0x0FA926, 5120, False),
    (6, 0x0F0C32, 6912, False), (7, 0x0F26CC, 4096, False), (8, 0x0F363E, 256, True),
    (9, 0x0F36AC, 6912, False), (10, 0x0F5182, 3328, False), (11, 0x00692E, 12800, False),
    (12, 0x0F5DAE, 2816, False), (13, 0x0F6844, 10240, False), (14, 0x0F900A, 3072, False),
    (15, 0x0F9B38, 3584, False), (16, 0x0F075E, 1280, True), (17, 0x0FBC7C, 3840, False),
]


def parse(rom, start, length):
    """RS-aware parse. Returns (events, result, pos).
    events: list of dicts {ev, kind, ch, p1, p2, delay, rs, off}."""
    end = start + length
    i = start
    if rom[i] < 0x80:
        i += 1  # leading byte skipped by $0804
    last_ev = None
    events = []
    ticks = 0
    while i < end:
        b = rom[i]
        if b & 0x80:
            last_ev = b
            i += 1
            rs = False
        else:
            if last_ev is None:
                return events, 'invalid-no-last-ev', i - start, ticks
            rs = True  # re-dispatch last_ev; b is p1, pointer NOT advanced
        ev = last_ev
        hi = ev & 0xF0
        ch = ev & 0x0F
        off = i - start if rs else i - 1 - start
        if hi in (0x80, 0x90):
            p1, p2, d = rom[i], rom[i + 1], rom[i + 2]
            events.append({'ev': ev, 'kind': 'note', 'ch': ch, 'p1': p1,
                           'p2': p2, 'delay': d, 'rs': rs, 'off': off})
            ticks += d
            i += 3
        elif hi == 0xC0:
            param, d = rom[i], rom[i + 1]
            events.append({'ev': ev, 'kind': 'setup', 'ch': ch, 'p1': param,
                           'p2': None, 'delay': d, 'rs': rs, 'off': off})
            ticks += d
            i += 2
        elif ev == 0xFC:
            # p1 slot holds the byte after $FC (read by the $FC handler)
            nxt = rom[i]
            if nxt == 0x80:
                rel = i + 1 - start
                i = start + ((rel + 255) // 256) * 256
                events.append({'ev': ev, 'kind': 'seek', 'ch': None, 'p1': 0x80,
                               'p2': None, 'delay': 0, 'rs': rs, 'off': off})
                continue
            return events, 'end', i - start, ticks
        else:
            return events, 'invalid', i - start, ticks
    return events, 'loops-to-length', end - start, ticks


def main():
    rom_path = sys.argv[1]
    rom = Path(rom_path).read_bytes()
    agree = 0
    song11 = None
    for idx, start, length, ends in SONGS:
        events, result, pos, ticks = parse(rom, start, length)
        if idx == 11:
            song11 = (events, ticks)
        ok = (result == 'end') if ends else (result == 'loops-to-length')
        agree += ok
        rs_n = sum(1 for e in events if e['rs'])
        print(f'song {idx:2d} start 0x{start:06X} len {length:5d}: {result:18s} at +{pos:5d} '
              f'events {len(events):5d} rs {rs_n:4d} ticks {ticks:6d} '
              f'{"OK" if ok else "MISMATCH"} (doc: {"ends" if ends else "loops"})')
    print(f'{agree} of {len(SONGS)} songs agree with the documented end behaviour')

    if '--diff-orig' in sys.argv:
        orig = Path('rop-original.gen').read_bytes()
        # strict parse of original song 11 (no RS in the original)
        o_start, o_len = 0x00692E, 12800
        oi = o_start
        if orig[oi] < 0x80:
            oi += 1
        o_events = []
        o_end = o_start + o_len
        while oi < o_end:
            b = orig[oi]
            hi = b & 0xF0
            ch = b & 0x0F
            if hi in (0x80, 0x90):
                o_events.append((b, 'note', ch, orig[oi + 1], orig[oi + 2], orig[oi + 3]))
                oi += 4
            elif hi == 0xC0:
                o_events.append((b, 'setup', ch, orig[oi + 1], None, orig[oi + 2]))
                oi += 3
            elif b == 0xFC and orig[oi + 1] == 0x80:
                rel = oi + 2 - o_start
                oi = o_start + ((rel + 255) // 256) * 256
            else:
                break
        n_events, n_ticks = song11
        # walk both sequences: patched events must be the original sequence
        # with $94 bass inserts + scaled ch3 $9X p2, nothing else changed
        j = 0
        bass = 0
        scaled = 0
        bad = []
        for e in n_events:
            if e['kind'] == 'seek':
                continue
            if e['ev'] == 0x94 and e['ch'] == 4:
                bass += 1
                continue
            if j >= len(o_events):
                bad.append(f'extra event past original end: {e}')
                continue
            ob = o_events[j]
            j += 1
            exp_p2 = ob[4]
            if ob[1] == 'note' and ob[2] == 3 and (ob[0] >> 4) == 9:
                exp_p2 = max(1, round(ob[4] * 80 / 124))
                if e['p2'] == exp_p2:
                    scaled += 1
            if (e['ev'], e['kind'], e['ch'], e['p1'], e['p2'], e['delay']) != \
               (ob[0], ob[1], ob[2], ob[3], exp_p2, ob[5]):
                bad.append(f'mismatch at orig #{j}: patched {e} vs orig {ob}')
        print(f'diff vs original: bass inserts {bass}, ch3 $9X scaled {scaled}, '
              f'orig events consumed {j}/{len(o_events)}, mismatches {len(bad)}')
        for b in bad[:10]:
            print('  BAD:', b)
        print(f'song 11 ticks patched {n_ticks} vs original '
              f'{sum(e[5] for e in o_events)}')
        return 0 if (agree == len(SONGS) and not bad and j == len(o_events)) else 1
    return 0 if agree == len(SONGS) else 1


if __name__ == '__main__':
    sys.exit(main())
