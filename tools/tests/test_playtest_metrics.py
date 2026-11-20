#!/usr/bin/env python3
"""Tests for the deterministic playtest harness (issue #240).

Covers compute_metrics on a synthetic trace (no emulator needed)
and the route-file parser. pytest-style (test_* functions, plain
asserts); also runs standalone:
  python3 tools/tests/test_playtest_metrics.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playtest_metrics import compute_metrics, route_to_pad_by_frame  # noqa: E402


def _row(frame, mode=2, camx=6, camy=5, e1x=8, e1y=5, lx=117, ly=112):
    """One raw VBlank/DMA di dict (address-keyed hex strings)."""
    return {
        "FF0012": f"{frame:04X}",
        "FF00AE": f"{mode:04X}",
        "FF0E8E": f"{camx:04X}",
        "FF0E90": f"{camy:04X}",
        "FF02C0": f"{lx:04X}",
        "FF02C2": f"{ly:04X}",
        "FF02C6": "0000",
        "FF02C8": "0000",
        "FF02BE": "0000",
        "FF0E14": "0000",
        "FF0018": "0000",
        "FF0E98": "001E",
        "FFB096": "0000",
        "FFB0A6": "0000",
        "FFB0B6": "0000",
        "FFB0C6": "0000",
        "FF02F4": f"{e1x:04X}",
        "FF02F6": f"{e1y:04X}",
    }


def _synthetic_trace():
    """100 frames in the room, DMA every 17 f, two L steps."""
    vbl = []
    for f in range(100):
        e1x = 8
        if f >= 28:
            e1x = 7
        if f >= 45:
            e1x = 6
        vbl.append(_row(f, e1x=e1x))
    dma = [_row(f) for f in (10, 27, 44, 61, 78, 95)]
    return {"vbl": vbl, "dma": dma}


def test_route_parser():
    with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                     delete=False) as fh:
        fh.write("# comment\n10 .\n5 L\n3 UR\n2 0x40\n")
        path = fh.name
    try:
        pad = route_to_pad_by_frame(path)
        assert pad[0] == 0 and pad[9] == 0
        assert pad[10] == 0x04 and pad[14] == 0x04  # L
        assert pad[15] == 0x09 and pad[17] == 0x09  # U+R = 0x01|0x08
        assert pad[18] == 0x40 and pad[19] == 0x40  # A
        assert len(pad) == 20
    finally:
        os.unlink(path)


def test_cadence_and_jitter():
    m = compute_metrics(_synthetic_trace())
    # DMA at 10,27,44,61,78,95 -> intervals of 17
    assert m["cadence"]["mean"] == 17.0, m["cadence"]
    assert m["cadence"]["max"] == 17
    assert m["cadence"]["room"]["mean"] == 17.0
    # Camera never moves -> no background jump
    assert m["bg_jump_px"]["max"] == 0.0
    # Leader (8,5)->(7,5)->(6,5) vs cam (6,5): screen (28,16)->(14,8)
    # ->(0,0); each step is one cell vector, magnitude ~16.1
    assert m["leader_jitter_px"] == 16.1, m["leader_jitter_px"]


def test_walk_counts_only_held_steps():
    # Route holds L from frame 20 to 49; the two steps (28, 45) fall
    # inside it, so both count. A step outside a hold must not.
    with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                     delete=False) as fh:
        fh.write("20 .\n30 L\n50 .\n")
        path = fh.name
    try:
        m = compute_metrics(_synthetic_trace(), route_path=path)
    finally:
        os.unlink(path)
    assert m["walk_cells"] == 2, m["walk_cells"]
    assert m["walk_cells_room"] == 2
    assert m["walk_cells_overworld"] == 0
    # First step frame 28, last 45 -> 17 frames = 0.2833 s
    assert abs(m["walk_seconds"] - 17 / 60.0) < 1e-9
    assert abs(m["walk_speed_cells_per_s"] - 2 / (17 / 60.0)) < 0.01


def test_bg_jump_uses_camera_delta():
    # Camera scrolls one cell east between two DMA hits: the room
    # image shifts by one cell vector (14,8) -> ~16.1 px.
    vbl = []
    for f in range(60):
        camx = 6 if f < 30 else 7
        vbl.append(_row(f, camx=camx))
    dma = [_row(f) for f in (10, 27, 44)]
    m = compute_metrics({"vbl": vbl, "dma": dma})
    assert m["bg_jump_px"]["max"] == 16.1, m["bg_jump_px"]
    assert m["bg_jump_px"]["n_jumps"] == 1


def test_spawn_teleport_excluded_from_bg_jump():
    # Camera (0,0) -> (111,125) at spawn is a scene change, not a
    # scroll; it must not count as a background jump.
    vbl = [_row(f, camx=0, camy=0) for f in range(10)]
    vbl += [_row(f, camx=111, camy=125) for f in range(10, 20)]
    dma = [_row(f) for f in (5, 15)]
    m = compute_metrics({"vbl": vbl, "dma": dma})
    assert m["bg_jump_px"]["max"] == 0.0, m["bg_jump_px"]
    assert m["bg_jump_px"]["n_jumps"] == 0


if __name__ == "__main__":
    test_route_parser()
    test_cadence_and_jitter()
    test_walk_counts_only_held_steps()
    test_bg_jump_uses_camera_delta()
    test_spawn_teleport_excluded_from_bg_jump()
    print("PASS test_playtest_metrics (5 tests)")
