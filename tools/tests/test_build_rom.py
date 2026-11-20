#!/usr/bin/env python3
"""Tests for the feature build (tools/build_rom.py, issue #239).

Pure tests (no ROM, no vasm) exercise the collision checks directly:
hook overlap, hook splitting an instruction, hook off a boundary,
bad kind/length, target outside the blob, and the free-space allocator.

Integration tests run the real build in a temp dir (with --base, so no
`make build` is needed) and skip gracefully when the original ROM or
vasm is absent:

  - a test feature with two overlapping hooks makes the build fail
    with both hook addresses named;
  - `music-off` builds byte-identical to applying the existing
    patches/music-off IPS;
  - an empty feature list builds the byte-identical original ROM.

pytest-style (test_* functions, plain asserts). pytest is not installed
in this repo, so the file also runs standalone:
  python3 tools/tests/test_build_rom.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build_rom import (Allocator, BuildError, ORIGINAL_MD5, apply_ips,  # noqa: E402
                       build, check_hooks, find_vasm, md5_hex)

REPO = Path(__file__).resolve().parent.parent.parent

# Instruction boundaries around $173C0, from disasm/src/rop.s:
#   $173C0 move.w $FF012E,d0 (6) | $173C6 cmp.w $8(a6),d0 (4) |
#   $173CA bne.b (2) | $173CC jsr snd_is_song_playing.l (6) | $173D2 ...
STARTS = {0x173C0, 0x173C6, 0x173CA, 0x173CC, 0x173D2, 0x173D4, 0x173D6,
          0x173D8, 0x173DA}

MUSIC_OFF_MD5 = "513228feab8e82ea17422695c11d5504"  # existing IPS applied

TEST_FEATURE_S = """\torg ORGVAL\ntest_target:\n\trts\n"""


def _hook(addr, length, kind="jsr", target="test_target",
          target_addr=0xFD0CC, feature="f"):
    return {"addr": addr, "len": length, "kind": kind, "target": target,
            "target_addr": target_addr, "feature": feature,
            "source": "<test>"}


def _blobs():
    return {"f": {"start": 0xFD0CC, "end": 0xFD0D0, "size": 4,
                   "labels": {"test_target": 0xFD0CC}},
            "g": {"start": 0xFD0D0, "end": 0xFD0D4, "size": 4,
                   "labels": {"test_target": 0xFD0D0}}}


def test_hook_overlap_names_both_addresses():
    # A is a 12-byte `bytes` hook covering $173C0-$173CC (three whole
    # instructions); B is a jsr hook inside it at $173C6. Both are
    # individually boundary-valid, so only the overlap check can
    # catch this. (A jsr/jmp hook is always len 6, so a long hook
    # must be kind=bytes.)
    hooks = [_hook(0x173C0, 12, kind="bytes",
                   target="4E71" * 6, target_addr=None),
             _hook(0x173C6, 6, feature="g", target_addr=0xFD0D0)]
    try:
        check_hooks(hooks, STARTS, _blobs())
    except BuildError as e:
        assert "173C0" in str(e) and "173C6" in str(e), str(e)
    else:
        raise AssertionError("overlapping hooks did not fail")


def test_hook_split_fails():
    # $173C0 len 4 ends at $173C4, mid-instruction.
    try:
        check_hooks([_hook(0x173C0, 4)], STARTS, _blobs())
    except BuildError as e:
        assert "splits an instruction" in str(e), str(e)
    else:
        raise AssertionError("split hook did not fail")


def test_hook_off_boundary_fails():
    try:
        check_hooks([_hook(0x173C2, 6)], STARTS, _blobs())
    except BuildError as e:
        assert "not on an instruction boundary" in str(e), str(e)
    else:
        raise AssertionError("off-boundary hook did not fail")


def test_bytes_hook_length_mismatch():
    h = _hook(0x173C0, 6, kind="bytes", target="4E71")
    try:
        check_hooks([h], STARTS, _blobs())
    except BuildError as e:
        assert "2 bytes but len is 6" in str(e), str(e)
    else:
        raise AssertionError("bytes/len mismatch did not fail")


def test_unknown_kind_fails():
    try:
        check_hooks([_hook(0x173C0, 6, kind="nop")], STARTS, _blobs())
    except BuildError as e:
        assert "unknown kind" in str(e), str(e)
    else:
        raise AssertionError("unknown hook kind did not fail")


def test_target_outside_blob_fails():
    h = _hook(0x173C0, 6, target_addr=0x1234)
    try:
        check_hooks([h], STARTS, _blobs())
    except BuildError as e:
        assert "not inside the feature's blob" in str(e), str(e)
    else:
        raise AssertionError("out-of-blob target did not fail")


def test_non_overlapping_hooks_pass():
    hooks = [_hook(0x173C0, 6), _hook(0x173CC, 6, feature="g",
                     target_addr=0xFD0D0)]
    blobs = {"f": {"start": 0xFD0CC, "end": 0xFD0D0, "size": 4,
                    "labels": {"test_target": 0xFD0CC}},
             "g": {"start": 0xFD0D0, "end": 0xFD0D4, "size": 4,
                    "labels": {"test_target": 0xFD0D0}}}
    check_hooks(hooks, STARTS, blobs)  # must not raise


def test_allocator_first_fit_no_collision():
    base = bytes([0xFF]) * 0x100000
    regions = [{"start": 0xFD0CC, "end": 0x100000, "fill": 0xFF,
                "cls": "padding-ff"}]
    alloc = Allocator(regions, base)
    a1 = alloc.alloc(4, "f")
    a2 = alloc.alloc(4, "g")
    assert a1 == 0xFD0CC, hex(a1)
    assert a2 == 0xFD0D0, hex(a2)
    assert a1 + 4 <= a2


def test_allocator_refuses_non_fill():
    base = bytearray([0xFF]) * 0x100000
    base[0xFD0CC] = 0x00  # the "free" space is not actually free
    regions = [{"start": 0xFD0CC, "end": 0x100000, "fill": 0xFF,
                "cls": "padding-ff"}]
    try:
        Allocator(regions, bytes(base)).alloc(4, "f")
    except BuildError as e:
        assert "not 0xFF-filled" in str(e), str(e)
    else:
        raise AssertionError("allocator wrote over non-fill bytes")


def test_allocator_out_of_space_fails():
    base = bytes([0xFF]) * 0x100000
    regions = [{"start": 0xFD0CC, "end": 0xFD0D0, "fill": 0xFF,
                "cls": "padding-ff"}]
    try:
        Allocator(regions, base).alloc(0x100, "f")
    except BuildError as e:
        assert "no free space" in str(e), str(e)
    else:
        raise AssertionError("oversized blob did not fail")


def find_rom():
    """Locate rop-original.gen (repo root, $ROP_ROM, or cwd)."""
    cands = []
    if os.environ.get("ROP_ROM"):
        cands.append(Path(os.environ["ROP_ROM"]))
    cands.append(REPO / "rop-original.gen")
    cands.append(Path.cwd() / "rop-original.gen")
    for c in cands:
        if c.is_file():
            return c
    return None


def _skip_if_no_toolchain():
    if find_rom() is None:
        print("SKIP integration tests: rop-original.gen not found")
        return True
    try:
        find_vasm(REPO)
    except BuildError:
        print("SKIP integration tests: vasmm68k_mot not found")
        return True
    return False


def _temp_repo(tmp: Path, feature_name: str, hooks_csv: str):
    """A minimal repo in tmp: the test feature + symlinks to the real
    disasm/regions.csv and disasm/src/rop.s."""
    fdir = tmp / "patches" / feature_name
    fdir.mkdir(parents=True)
    (fdir / "feature.s").write_text(TEST_FEATURE_S)
    (fdir / "hooks.csv").write_text(hooks_csv)
    d = tmp / "disasm" / "src"
    d.mkdir(parents=True)
    (tmp / "disasm" / "regions.csv").symlink_to(
        REPO / "disasm" / "regions.csv")
    (d / "rop.s").symlink_to(REPO / "disasm" / "src" / "rop.s")
    return tmp


def test_overlapping_hook_feature_fails_end_to_end():
    if _skip_if_no_toolchain():
        return
    hooks_csv = ("addr,len,kind,target\n"
                 "0x173C0,12,bytes,4E714E714E714E714E714E71\n"
                 "0x173C6,6,jsr,test_target\n")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _temp_repo(tmp, "test-overlap", hooks_csv)
        try:
            build(["test-overlap"], tmp,
                  base_override=find_rom(), out_dir=tmp / "build")
        except BuildError as e:
            assert "173C0" in str(e) and "173C6" in str(e), str(e)
        else:
            raise AssertionError(
                "build with overlapping hooks did not fail")


def test_music_off_build_matches_existing_ips():
    if _skip_if_no_toolchain():
        return
    orig = find_rom().read_bytes()
    expect = md5_hex(apply_ips(
        orig, REPO / "patches" / "music-off"
        / "rings-of-power-music-off.ips"))
    assert expect == MUSIC_OFF_MD5, expect
    with tempfile.TemporaryDirectory() as td:
        manifest = build(["music-off"], REPO,
                         base_override=find_rom(),
                         out_dir=Path(td) / "build")
        assert manifest["md5"] == MUSIC_OFF_MD5, manifest["md5"]


def test_empty_build_is_original():
    if _skip_if_no_toolchain():
        return
    with tempfile.TemporaryDirectory() as td:
        manifest = build([], REPO, base_override=find_rom(),
                         out_dir=Path(td) / "build")
        assert manifest["md5"] == ORIGINAL_MD5, manifest["md5"]


def main():
    tests = [test_hook_overlap_names_both_addresses,
             test_hook_split_fails,
             test_hook_off_boundary_fails,
             test_bytes_hook_length_mismatch,
             test_unknown_kind_fails,
             test_target_outside_blob_fails,
             test_non_overlapping_hooks_pass,
             test_allocator_first_fit_no_collision,
             test_allocator_refuses_non_fill,
             test_allocator_out_of_space_fails,
             test_overlapping_hook_feature_fails_end_to_end,
             test_music_off_build_matches_existing_ips,
             test_empty_build_is_original]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
