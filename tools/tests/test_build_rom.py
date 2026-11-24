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
  - `--size 2m` builds the 2 MB container (issue #252): first MB
    byte-identical, second MB 0xFF-filled, header ROM end
    0x001FFFFF, both checksums verify, `--data` places payloads
    in the second megabyte, and the IPS covers the full 2 MB.

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
                       build, check_hooks, find_vasm, md5_hex, write_ips)
from checksum import (compute_checksum, compute_runtime_checksum,  # noqa: E402
                      stored_checksum, stored_runtime_checksum)

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
    # catch this. 
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


def test_long_jmp_hook_pads_with_nops():
    from build_rom import hook_bytes
    h = _hook(0x173C0, 10, kind="jmp", target_addr=0xFD0CC)
    check_hooks([h], STARTS, _blobs())
    assert hook_bytes(h) == bytes.fromhex("4EF9000FD0CC4E714E71")


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


def test_ips_round_trip_longer_patched():
    """A 2 MB patched ROM (1 MB original + 0xFF second MB with a
    marker) round-trips through write_ips/apply_ips: the IPS must
    cover the second megabyte, not just the first."""
    import tempfile
    orig = bytes([0x00]) * 0x100000
    patched = bytearray(bytes([0xFF]) * 0x200000)
    patched[:0x100000] = orig
    patched[0x100000:0x100008] = b"ROM2MB!!"
    patched[0x1FFFF0:0x200000] = b"END-OF-ROM-2MB!!"
    with tempfile.TemporaryDirectory() as td:
        ips = Path(td) / "test.ips"
        write_ips(orig, bytes(patched), ips)
        assert apply_ips(orig, ips) == bytes(patched)
        # And the IPS really carries the second megabyte: applying
        # it to the 1 MB original must yield a 2 MB image.
        assert len(apply_ips(orig, ips)) == 0x200000


def test_ips_apply_extends_short_input():
    """apply_ips pads a short input up to a record's offset instead
    of inserting the record at the wrong place."""
    import tempfile
    orig = bytes([0x00]) * 0x10
    with tempfile.TemporaryDirectory() as td:
        ips = Path(td) / "gap.ips"
        raw = bytearray(b"PATCH")
        raw += (0x100).to_bytes(3, "big") + (4).to_bytes(2, "big")
        raw += b"ABCD"
        raw += b"EOF"
        ips.write_bytes(bytes(raw))
        out = apply_ips(orig, ips)
        assert len(out) == 0x104, len(out)
        assert out[0x100:0x104] == b"ABCD"
        assert out[0x10:0x100] == bytes(0xF0)


def test_two_mb_build_layout():
    """--size 2m: 2,097,152 bytes; first MB byte-identical to the
    original; second MB all 0xFF; header ROM end 0x001FFFFF; both
    checksums verify."""
    if _skip_if_no_toolchain():
        return
    orig = find_rom().read_bytes()
    with tempfile.TemporaryDirectory() as td:
        manifest = build([], REPO, base_override=find_rom(),
                         out_dir=Path(td) / "build", size="2m",
                         eeprom=True)
        assert manifest["size"] == 0x200000, manifest["size"]
        assert manifest["rom_size"] == "2m"
        assert manifest["rom_end"] == "0x001FFFFF"
        assert manifest["second_mb"]["usable_bytes"] == 0x100000
        assert manifest["second_mb"]["fill"] == "0xFF"
        rom = (Path(td) / "build" / "rop-base-2m.rom").read_bytes()
        assert len(rom) == 0x200000
        # The first MB is the original except the three fields the
        # 2 MB container itself changes: header ROM end (0x1A4),
        # header checksum (0x18E) and runtime immediate (0xFD098).
        first = bytearray(rom[:0x100000])
        expect = bytearray(orig)
        for start, end in ((0x18E, 0x190), (0x1A4, 0x1A8),
                           (0xFD098, 0xFD09C)):
            first[start:end] = b"\x00" * (end - start)
            expect[start:end] = b"\x00" * (end - start)
        assert bytes(first) == bytes(expect), "first MB differs from original"
        assert rom[0x100000:] == bytes([0xFF]) * 0x100000
        assert rom[0x1A4:0x1A8] == (0x1FFFFF).to_bytes(4, "big")
        assert stored_checksum(rom) == compute_checksum(rom)
        assert stored_runtime_checksum(rom) == compute_runtime_checksum(rom)
        # The IPS for the 2 MB build rebuilds it from the 1 MB base.
        assert apply_ips(orig, Path(td) / "build" / "rop-base-2m.ips") == rom


def test_two_mb_build_sram_save():
    """A 2 MB build gets sram-save by default (#284): own product ID,
    SRAM header at $1B0, the three EEPROM entry points hooked."""
    if _skip_if_no_toolchain():
        return
    with tempfile.TemporaryDirectory() as td:
        manifest = build([], REPO, base_override=find_rom(),
                         out_dir=Path(td) / "build", size="2m")
        rom = (Path(td) / "build" / "rop-base-2m.rom").read_bytes()
        assert manifest["features"] == ["sram-save"]
        assert b"T-50176" not in rom[0x180:0x190]
        assert rom[0x1B0:0x1BC] == bytes.fromhex("5241F82000200001002000FF")
        assert {h["addr"] for h in manifest["hooks"]} == {
            "0x42FD8", "0x43012", "0x430F4"}
        assert stored_checksum(rom) == compute_checksum(rom)
        assert stored_runtime_checksum(rom) == compute_runtime_checksum(rom)


def test_two_mb_build_with_data():
    """--data places a payload in the second megabyte (default
    offset $100000, or the @offset given) and records it in the
    manifest; the rest of the second MB stays 0xFF."""
    if _skip_if_no_toolchain():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        payload = bytes(range(256)) * 4  # 1024 bytes
        (tmp / "atlas.bin").write_bytes(payload)
        manifest = build([], REPO, base_override=find_rom(),
                         out_dir=tmp / "build", size="2m",
                         data=[(tmp / "atlas.bin", 0x100000),
                               (tmp / "atlas.bin", 0x180000)])
        rom = (tmp / "build" / "rop-base-2m.rom").read_bytes()
        assert rom[0x100000:0x100400] == payload
        assert rom[0x180000:0x180400] == payload
        assert rom[0x100400:0x180000] == bytes([0xFF]) * (0x80000 - 0x400)
        assert stored_checksum(rom) == compute_checksum(rom)
        placed = manifest["second_mb"]["data"]
        assert [d["offset"] for d in placed] == ["0x100000", "0x180000"]
        assert all(d["size"] == 1024 for d in placed)


def test_two_mb_data_rejected():
    """--data outside the second megabyte, overflowing it, or given
    with a 1 MB build all fail."""
    if _skip_if_no_toolchain():
        return
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "x.bin").write_bytes(b"ABCD")
        for kwargs in ({"size": "2m", "data": [(tmp / "x.bin", 0x80000)]},
                       {"size": "2m", "data": [(tmp / "x.bin", 0x100001)]},
                       {"size": "2m", "data": [(tmp / "x.bin", 0x1FFFFE)]},
                       {"size": "1m", "data": [(tmp / "x.bin", 0x100000)]}):
            try:
                build([], REPO, base_override=find_rom(),
                      out_dir=tmp / "build", **kwargs)
            except BuildError:
                pass
            else:
                raise AssertionError(f"bad --data accepted: {kwargs}")
        try:
            build([], REPO, base_override=find_rom(),
                  out_dir=tmp / "build", size="3m")
        except BuildError as e:
            assert "unknown size" in str(e), str(e)
        else:
            raise AssertionError("unknown size accepted")


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
             test_ips_round_trip_longer_patched,
             test_ips_apply_extends_short_input,
             test_overlapping_hook_feature_fails_end_to_end,
             test_long_jmp_hook_pads_with_nops,
             test_music_off_build_matches_existing_ips,
             test_empty_build_is_original,
             test_two_mb_build_layout,
             test_two_mb_build_sram_save,
             test_two_mb_build_with_data,
             test_two_mb_data_rejected]
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
