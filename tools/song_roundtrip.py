#!/usr/bin/env python3
"""song_roundtrip.py — Z80 song-stream round-trip (issue #285, M10).

Parse each song stream with the event grammar in docs/sound.md §6
(imported from tools/song_check.py — the grammar is not reimplemented
here), re-serialize the parsed events, and require the re-serialized
bytes to be byte-identical to the original stream over its full
declared length. This is the `song` class of `make roundtrip`
(tools/roundtrip.py).

Re-serialization rules (docs/sound.md §6):
  * the leading byte < 0x80 (every song starts with $00) is emitted verbatim;
  * $8X/$9X events emit their 4 bytes, $CX events their 3 bytes;
  * `$FC $80` emits its 2 bytes, then the skipped bytes up to the next
    256-byte chunk boundary verbatim — the player never parses them
    (e.g. song 0's skipped tail is real note data that is never played),
    so they carry no events and are reproduced, not interpreted;
  * `$FC <other>` (end of song) emits its 2 bytes, then any trailing
    bytes to the end of the declared length verbatim — the player stops
    there, so the tail is dead space within the song's allocation
    (songs 8 and 16; song 20's tail is song 2's data, which starts
    6 bytes into song 20's declared span).
  * a byte that is none of the above is invalid: the Z80 would hang
    (JP $08C8), so the check fails instead of skipping it.

Songs: the 18 in tools/song_check.py (indices 0–17) plus index 20
($ED4F4, 256 B, ends — the arrival jingle, docs/sound.md §7.1).
Indices 18/19 are no-ops (no data). The parse must also agree with
the documented end behaviour (ends vs loops), as song_check does.

Read only with respect to the ROM; writes nothing.

Usage: python3 tools/song_roundtrip.py [--rom PATH]
Exit 0 only when every song parses as documented and re-serializes
byte-identical.
"""
import argparse
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
from song_check import SONGS as CHECK_SONGS, parse  # noqa: E402

# song_check covers indices 0-17; index 20 is the arrival jingle
# (docs/sound.md section 7.1: $ED4F4, 256 B, ends at offset 4).
SONGS = CHECK_SONGS + [(20, 0x0ED4F4, 256, True)]


def reserialize(rom, start, length):
    """Parse the stream at `start` and re-emit it. Returns bytes.

    Raises ValueError on an invalid event byte or a truncated event.
    The returned bytes must equal rom[start:start+length].
    """
    end = start + length
    out = bytearray()
    i = start
    if rom[i] < 0x80:
        out.append(rom[i])
        i += 1
    while i < end:
        b = rom[i]
        if b & 0x80 == 0:
            raise ValueError(
                f"invalid lead byte 0x{b:02X} at +{i - start}")
        hi = b & 0xF0
        if hi in (0x80, 0x90):
            if i + 4 > end:
                raise ValueError(f"truncated $8X/$9X event at +{i - start}")
            out += rom[i:i + 4]
            i += 4
        elif hi == 0xC0:
            if i + 3 > end:
                raise ValueError(f"truncated $CX event at +{i - start}")
            out += rom[i:i + 3]
            i += 3
        elif b == 0xFC:
            if i + 1 >= end:
                raise ValueError(f"truncated $FC at +{i - start}")
            nxt = rom[i + 1]
            if nxt == 0x80:
                # Skip to the next 256-byte boundary counted from the
                # song start; the bytes in between are skipped by the
                # player and carried verbatim (see module docstring).
                rel = i + 2 - start
                boundary = start + ((rel + 255) // 256) * 256
                boundary = min(boundary, end)
                out += rom[i:boundary]
                i = boundary
            else:
                # End of song: emit the terminator, then the dead
                # trailing bytes verbatim to the declared length.
                out += rom[i:i + 2]
                out += rom[i + 2:end]
                i = end
        else:
            raise ValueError(
                f"invalid event byte 0x{b:02X} at +{i - start}")
    return bytes(out)


def check(rom_path=None):
    """Round-trip every song. Returns a summary string.

    Raises AssertionError / ValueError on the first failure.
    """
    rom = Path(rom_path or "rop-original.gen").read_bytes()
    total = identical = 0
    events = 0
    for idx, start, length, ends in SONGS:
        result, _pos, nev = parse(rom, start, length)
        want = "end" if ends else "loops-to-length"
        assert result == want, (
            f"song {idx}: parses as {result}, doc says {want}")
        events += nev
        rebuilt = reserialize(rom, start, length)
        orig = bytes(rom[start:start + length])
        assert rebuilt == orig, (
            f"song {idx}: re-serialized {len(rebuilt)} bytes differ from "
            f"the original {length} bytes")
        total += 1
        identical += 1
    return (f"{identical}/{total} songs parse as documented and "
            f"re-serialize byte-identical ({events} events)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default="rop-original.gen")
    args = ap.parse_args(argv)
    try:
        summary = check(args.rom)
    except (AssertionError, ValueError, FileNotFoundError) as e:
        print(f"song: FAIL {e}", file=sys.stderr)
        return 1
    print(f"song: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
