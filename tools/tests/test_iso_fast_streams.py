#!/usr/bin/env python3
"""Tests for the fast terrain streams of the smooth iso view
(tools/iso_fast_streams.py, #266 item 1).

Pure tests (no ROM): the stub code (144 stubs of 24 bytes, 3 tails,
the byte length table). Integration tests need rop-original.gen and
skip when it is absent: the block layout, and the Python model of the
68k loop against the $E358 port for a sample of calls (both paths,
odd and even x, lines above the top).

Runs standalone: python3 tools/tests/test_iso_fast_streams.py
"""
import random
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import iso_fast_streams as F  # noqa: E402
from e358 import E358  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
ROM = REPO / "rop-original.gen"


def test_stub_code_shape():
    code, lens = F.stub_code()
    assert len(lens) == 144
    assert len(code) == 144 * F.STUB + sum(30 + 10 * t + 2 for t in range(3))
    for P in range(144):           # every stub ends in bra.w into a tail
        stub = code[P * F.STUB:(P + 1) * F.STUB]
        h = (P // 16) // 3
        assert struct.unpack_from(">H", stub, 10 * h)[0] == 0x6000
    assert lens[(2 * 3 + 2) * 16 + 15] == 19


def _rom():
    return ROM.read_bytes() if ROM.is_file() else None


def test_block_layout():
    rom = _rom()
    if rom is None:
        print("SKIP test_block_layout (no ROM)")
        return
    blob = F.build(rom)
    assert blob[:4] == b"ISOF"
    stub_at, lens_at = struct.unpack_from(">II", blob, 4)
    assert stub_at == 12 + 8 * 1888
    assert len(blob) < 0x0F0000      # below the 2 MB code room ($1F0000)


def test_model_matches_port():
    rom = _rom()
    if rom is None:
        print("SKIP test_model_matches_port (no ROM)")
        return
    blob = F.build(rom)
    e = E358(rom)
    rng = random.Random(266)
    for _ in range(400):
        s = rng.randrange(944)
        d0 = rng.randrange(0x60, 0x140)
        d1 = rng.randrange(-21, 150)
        d3 = rng.randrange(2)
        ram = bytearray(65536)
        e.call(s, d0, d1, d3, ram)
        port = bytes(ram[0x1EC0:0x1EC0 + 26496])
        lin = bytearray(F.NLINES * F.LINE + 64)
        F.fast_call(blob, rom, s, d0, d1, d3, lin)
        til = F.lin_to_tiled(lin)
        for tr in range(23):         # columns the hole can use (2..33)
            o = tr * 0x480 + 2 * 32
            assert til[o:o + 32 * 32] == port[o:o + 32 * 32], (s, d0, d1, d3, tr)


if __name__ == "__main__":
    n = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
            n += 1
    print("%d/%d tests passed" % (n, n))
