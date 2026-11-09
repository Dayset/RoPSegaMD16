#!/usr/bin/env python3
"""Decode Sega Genesis / Mega Drive Game Genie codes (issue #021).

A Genesis Game Genie code is 8 symbols (XXXX-XXXX) over the 32-symbol
alphabet ABCDEFGHJKLMNPRSTVWXYZ0123456789 (note: digits 0 and 1 ARE
used; the letters I, O, Q, U are not). The 8 symbols carry 40 bits:
a 24-bit ROM address and a 16-bit replacement word, with their bits
scrambled across the code. The unscramble below is the published
algorithm (see e.g. Tony Hedstrom's "How to make Sega Genesis Game
Genie codes", codehut.gshi.org, and the many decoder implementations
derived from it):

  Pack the symbols big-endian into a 40-bit integer v (symbol 0 in
  the top 5 bits). Then each address/data bit b comes from one
  absolute bit position p of v:

    address bit b : from v-bit APOS[b]
    data    bit b : from v-bit DPOS[b]

  APOS = address bits 0-7 from v-bits 0-7 (the low bits of the last
         symbol), bits 8-15 from v-bits 24-31, bits 16-23 from
         v-bits 16-23.
  DPOS = data bits 0-7 (low byte) from v-bits 32-39, data bits 8-15
         with a 3-bit rotation: bits 8-12 from v-bits 11-15, bits
         13-15 from v-bits 8-10.

Verified test vectors (from the codehut guide, an independent
worked example for a different game, Shining in the Darkness):
    97JT-EVSG <-> address 0x0251E6, word 0xA8FF
    AFJT-EVSG <-> address 0x0251E6, word 0xA801
Both are asserted by --selftest.

Usage:
    decode_gamegenie.py <CODE> [<CODE> ...]
    decode_gamegenie.py --selftest
    decode_gamegenie.py --rop        # decode the full #033 RoP table

Genesis codes patch ROM (file offset == 68000 address, word-aligned),
unlike the RAM (PAR/Gens) codes in the same fan page.
"""
import sys

ALPHABET = "ABCDEFGHJKLMNPRSTVWXYZ0123456789"
APOS = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7,
        8: 24, 9: 25, 10: 26, 11: 27, 12: 28, 13: 29, 14: 30, 15: 31,
        16: 16, 17: 17, 18: 18, 19: 19, 20: 20, 21: 21, 22: 22, 23: 23}
DPOS = {0: 32, 1: 33, 2: 34, 3: 35, 4: 36, 5: 37, 6: 38, 7: 39,
        8: 11, 9: 12, 10: 13, 11: 14, 12: 15, 13: 8, 14: 9, 15: 10}


def decode(code):
    """Return (address, word) for an 8-symbol Genesis Game Genie code."""
    text = code.strip().upper().replace("-", "").replace(" ", "")
    if len(text) != 8:
        raise ValueError(f"{code!r}: {len(text)} symbols, expected 8")
    bad = [c for c in text if c not in ALPHABET]
    if bad:
        raise ValueError(f"{code!r}: symbols {bad} not in the Genesis "
                         f"Game Genie alphabet {ALPHABET}")
    v = 0
    for c in text:
        v = (v << 5) | ALPHABET.index(c)
    address = sum(((v >> p) & 1) << b for b, p in APOS.items())
    data = sum(((v >> p) & 1) << b for b, p in DPOS.items())
    return address, data


def encode(address, data):
    """Inverse of decode() — used by the self-test round-trip."""
    v = 0
    for b, p in APOS.items():
        v |= ((address >> b) & 1) << p
    for b, p in DPOS.items():
        v |= ((data >> b) & 1) << p
    chars = []
    for shift in (35, 30, 25, 20, 15, 10, 5, 0):
        chars.append(ALPHABET[(v >> shift) & 0x1F])
    return "".join(chars[:4]) + "-" + "".join(chars[4:])


# The RoP table from docs/research/ringsofpower-co-uk-remaining.md
# (cheats.htm, contributed by Xavier Whipon).
ROP_CODES = [
    ("R1JA-86Y6", "master code (required to boot)"),
    ("1NTB-AEL8", "food/water low; health/power never decrease"),
    ("KWVA-AA7W", "unlimited money"),
    ("RWVT-AAC4", "unlimited water"),
    ("AWVT-AA8C", "unlimited food"),
    ("HWRA-AA2Y", "Buc unlimited health"),
    ("HWRA-AA3L", "Buc unlimited power"),
    ("AWRA-ABVN", "Buc unlimited exp"),
    ("RWRA-AA5W", "Slash unlimited health"),
    ("TWRA-AA5L", "Slash unlimited power"),
    ("DWRA-AAA8", "Slash unlimited exp"),
    ("PWWA-AA22", "Feather unlimited health"),
    ("AWWA-AAC4", "Feather unlimited power"),
    ("PWWA-AAAC", "Feather unlimited exp"),
    ("KWVA-AACG", "Obliki unlimited health"),
    ("EWVA-AACW", "Obliki unlimited power"),
    ("KWVA-AADT", "Obliki unlimited exp"),
    ("AWVA-AAD8", "Mortimer unlimited health"),
    ("TWVA-AADM", "Mortimer unlimited power"),
    ("DWVA-AA3Y", "Mortimer unlimited exp"),
    ("KWVA-AAA8", "Alexi unlimited health"),
    ("TWVA-AABW", "Alexi unlimited power"),
    ("KWVA-AABG", "Alexi unlimited exp"),
]


def selftest():
    # Published worked examples (codehut guide, Shining in the Darkness).
    assert decode("97JT-EVSG") == (0x0251E6, 0xA8FF), decode("97JT-EVSG")
    assert decode("AFJT-EVSG") == (0x0251E6, 0xA801), decode("AFJT-EVSG")
    assert encode(0x0251E6, 0xA8FF) == "97JT-EVSG"
    assert encode(0x0251E6, 0xA801) == "AFJT-EVSG"
    odd = []
    for code, _ in ROP_CODES:
        a, d = decode(code)
        assert encode(a, d) == code, (code, a, d)
        if a % 2:
            odd.append(code)
    # Known anomaly in the fan-published table: TWVA-AADM decodes to
    # an ODD address (0x00A26B), impossible for a word patch — a
    # one-symbol transcription error in the source list (changing
    # the last symbol M -> L would give 0x00A26A with the same word
    # 0x0084 as its sibling codes; that correction is a CONJECTURE,
    # see docs/research/game-genie-decoded.md). Pin it so a decoder
    # regression can't silently move it.
    assert odd == ["TWVA-AADM"], odd
    assert decode("TWVA-AADM") == (0x00A26B, 0x0084)
    # Cross-check against repo knowledge: the master code must land
    # on the runtime-checksum routine (#001/#002: 0xFD07C block).
    assert decode("R1JA-86Y6") == (0x0FD09C, 0x4E75), decode("R1JA-86Y6")
    print("decode_gamegenie selftest: PASS "
          "(2 published vectors + encode round-trip on all "
          f"{len(ROP_CODES)} RoP codes; master code -> 0xFD09C:0x4E75 "
          "as expected; TWVA-AADM odd-address anomaly pinned)")


def main(argv):
    if argv[1:] == ["--selftest"]:
        selftest()
        return 0
    if argv[1:] == ["--rop"]:
        for code, desc in ROP_CODES:
            a, d = decode(code)
            print(f"{code}  -> 0x{a:06X}: 0x{d:04X}   {desc}")
        return 0
    if len(argv) < 2:
        print(__doc__)
        return 2
    for code in argv[1:]:
        try:
            a, d = decode(code)
        except ValueError as exc:
            print(f"{code}: ERROR {exc}")
            return 1
        print(f"{code}  -> address 0x{a:06X}, word 0x{d:04X}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
