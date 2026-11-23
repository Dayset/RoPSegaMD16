#!/usr/bin/env python3
"""Tests for the $E358 terrain-decoder port (tools/e358.py, #252 Track A).

Pure tests (no ROM) exercise the fingerprint, the sweep case list,
the handler decoder on hand-built byte sequences, and the per-cell
call list on a zero ROM. Integration tests need rop-original.gen and
skip gracefully when it is absent (CI has no ROM):

  - the handler decoder matches the disassembly: all 112 live
    handlers decode, and each handler's stream-byte read count equals
    its dispatch byte's hi nibble;
  - call_buffer smoke counts (stream 0 path A: 22 dispatches,
    stream 288 path A: 30);
  - golden fingerprints: the port's fingerprint for sweep cases 0-4,
    1152, 3777 and 4286 equals the value the hardware harness
    measured live (build/e358-capture.json, 4298/4298 match).

pytest-style (test_* functions, plain asserts). pytest is not installed
in this repo, so the file also runs standalone:
  python3 tools/tests/test_e358.py
"""

import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from e358 import (E358, N_STREAMS, N_SWEEP, UnknownOpcode, fingerprint,  # noqa: E402
                  sweep_cases)
from e358_atlas import AtlasBuilder  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
LOOP_A = 0xE3E2
LOOP_B = 0xE43C

FAKE_ROM = bytes(0x100000)

# Golden fingerprints, measured live by the $E358 harness ROM
# (tools/e358_capture.py --chunks 150, 4298/4298 fingerprint matches).
GOLDEN = {
    0: (195906139, 173380815),
    1: (3763948448, 3879494615),
    2: (3231837757, 2343533447),
    3: (3734109696, 4207777284),
    4: (3492747115, 4068455938),
    1152: (193078738, 3032823714),
    3777: (407088197, 4110586759),
    4286: (3480307285, 2320824394),
}


def find_rom():
    cands = []
    if os.environ.get("ROP_ROM"):
        cands.append(Path(os.environ["ROP_ROM"]))
    cands.append(REPO / "rop-original.gen")
    cands.append(Path.cwd() / "rop-original.gen")
    for c in cands:
        if c.is_file():
            return c
    return None


# --- pure tests ---

def test_fingerprint_zero_buffer():
    assert fingerprint(bytes(26496)) == (3597762821, 347197295)


def test_fingerprint_deterministic_and_sensitive():
    buf = bytearray(26496)
    a = fingerprint(bytes(buf))
    assert fingerprint(bytes(buf)) == a
    buf[0] = 1
    assert fingerprint(bytes(buf)) != a
    buf[-1] = 0xFF
    assert fingerprint(bytes(buf)) != a


def test_sweep_cases_shape():
    cases = sweep_cases()
    assert len(cases) == 4298 == N_SWEEP
    assert cases[0] == (0, 0x40, 0, 0)
    assert cases[3] == (0, 0x42, 0, 1)
    assert cases[4] == (1, 0x40, 0, 0)
    assert cases[3775] == (943, 0x42, 0, 1)
    assert cases[3776] == (0, 0x54, 27, 0)
    assert cases[4285] == (943, 0xE0, -5, 1)
    assert cases[4286] == (0, 0x40, -21, 0)
    assert cases[4297] == (0, 0x40, 0, 0)
    for s, _d0, _d1, _d3 in cases:
        assert 0 <= s < N_STREAMS


def test_fake_rom_call_skeleton():
    e = E358(FAKE_ROM)
    ram = bytearray(65536)
    buf, st = e.call_buffer(0, 0x40, 0, 0)
    assert st["dispatches"] == 0 and st["exited"] == "terminator"
    assert buf == bytes(26496)
    st = e.call(0, 0x40, -22, 0, ram)
    assert st["exited"] == "d1-lt--21" and st["dispatches"] == 0
    st = e.call(0, 0x40, -1, 0, ram)
    assert st["exited"] == "skip-zero"
    for bad in (-1, N_STREAMS, 944):
        try:
            e.call(bad, 0x40, 0, 0, ram)
        except ValueError:
            pass
        else:
            raise AssertionError("stream %d did not fail" % bad)


def _fake_rom_with_handler(words, at=0x1000):
    rom = bytearray(FAKE_ROM)
    for i, w in enumerate(words):
        struct.pack_into(">H", rom, at + 2 * i, w)
    return bytes(rom)


def _bra_to_loop(at):
    # bra.w from `at` to LOOP_A: disp = dest - (at + 2).
    return 0x6000, (LOOP_A - (at + 2)) & 0xFFFF


def test_decoder_handbuilt_handler():
    # Handlers live near the loop heads ($E3E2/$E43C): bra.w range is
    # +/-32 KiB, so the fake handler must sit close to LOOP_A.
    at = 0xE200
    bra, disp = _bra_to_loop(at + 6)  # read(2) + and/or pair(4) -> bra
    rom = _fake_rom_with_handler([0x1A18, 0xCD15, 0x8B15, bra, disp], at)
    e = E358(rom)
    assert e._decode_handler(at) == [("read",), ("write", 0, 0)]


def test_decoder_adda_suba_and_pair_shapes():
    at = 0xE200
    bra, disp = _bra_to_loop(at + 12)
    rom = _fake_rom_with_handler(
        [0xDAFC, 0x0010, 0x9AFC, 0xFFF0, 0xCD25, 0x8B1D, bra, disp], at)
    e = E358(rom)
    assert e._decode_handler(at) == [("adda", 16), ("suba", -16),
                                      ("write", -1, 0)]


def test_decoder_unknown_opcode_raises():
    e = E358(FAKE_ROM)
    try:
        e._decode_handler(0x1000)
    except UnknownOpcode:
        pass
    else:
        raise AssertionError("zero opcode did not fail")
    try:
        e._decode_handler(0xE3E2)  # LOOP_A itself is not a handler
    except UnknownOpcode:
        pass
    else:
        raise AssertionError("loop head did not fail")


def test_cell_calls_fake_rom():
    ab = AtlasBuilder(FAKE_ROM)
    # Flat tile, no height: top call only, d3 = bit12.
    assert ab.cell_calls(0x0000) == [(0, 196, 82, 0)]
    assert ab.cell_calls(0x1000) == [(0, 196, 82, 1)]
    # Height 1, no height-stack flag: top call only, d1 - 7.
    assert ab.cell_calls(0x2000) == [(0, 196, 75, 0)]
    # Height 1, height-stack flag, props 0: filler (0x230) then top.
    assert ab.cell_calls(0x2200) == [(0x230, 196, 82, 0), (0, 196, 75, 0)]
    # Complete cells: the height loop runs whenever height > 0,
    # regardless of the window-position/bit-9 gate.
    assert ab.cell_calls(0x2000, complete=True) == [
        (0x230, 196, 82, 0), (0, 196, 75, 0)]
    assert ab.cell_calls(0x0000, complete=True) == [(0, 196, 82, 0)]


# --- ROM integration tests ---

def _skip_if_no_rom():
    if find_rom() is None:
        print("SKIP integration tests: rop-original.gen not found")
        return True
    return False


def test_live_handlers_match_disassembly():
    if _skip_if_no_rom():
        return
    e = E358(find_rom().read_bytes())
    handlers = e.live_handlers()
    assert len(handlers) == 112, len(handlers)
    # Every live dispatch index's handler reads exactly hi-nibble
    # stream bytes (rop.s: handler stream-byte count == hi nibble).
    checked = 0
    for idx, target in enumerate(e.dispatch):
        if target in (LOOP_A, LOOP_B):
            continue
        ops = handlers[target]
        reads = sum(1 for op in ops if op[0] == "read")
        assert reads == idx >> 4, (idx, target, reads)
        assert ops, (idx, target)
        checked += 1
    assert checked == 112, checked


def test_call_buffer_smoke_counts():
    if _skip_if_no_rom():
        return
    e = E358(find_rom().read_bytes())
    _buf, st = e.call_buffer(0, 0x40, 0, 0)
    assert st["dispatches"] == 22, st
    assert st["exited"] == "terminator", st
    _buf, st = e.call_buffer(288, 0x40, 0, 0)
    assert st["dispatches"] == 30, st
    _buf, st = e.call_buffer(0, 0x40, -1, 0)
    assert st["dispatches"] == 21, st
    _buf, st = e.call_buffer(0, 0x40, -22, 0)
    assert st["dispatches"] == 0 and st["exited"] == "d1-lt--21", st


def test_golden_fingerprints():
    if _skip_if_no_rom():
        return
    e = E358(find_rom().read_bytes())
    cases = sweep_cases()
    for n, want in GOLDEN.items():
        buf, _st = e.call_buffer(*cases[n])
        assert fingerprint(buf) == want, (n, fingerprint(buf), want)


def main():
    tests = [test_fingerprint_zero_buffer,
             test_fingerprint_deterministic_and_sensitive,
             test_sweep_cases_shape,
             test_fake_rom_call_skeleton,
             test_decoder_handbuilt_handler,
             test_decoder_adda_suba_and_pair_shapes,
             test_decoder_unknown_opcode_raises,
             test_cell_calls_fake_rom,
             test_live_handlers_match_disassembly,
             test_call_buffer_smoke_counts,
             test_golden_fingerprints]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as ex:
            failed += 1
            print(f"FAIL {t.__name__}: {ex}")
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
