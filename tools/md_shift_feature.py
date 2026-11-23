#!/usr/bin/env python3
"""Shifted feature build (#280, step 3): build the topdown feature ROM
on the shifted base and compare it with the unshifted feature ROM over
the topdown route.

A feature build cannot reuse the unshifted build: every absolute
base-ROM address in it moves +SHIFT. The driver therefore rebuilds the
feature from source with all three shifted inputs:
  - feature.s: every 5-6 digit hex literal in [0x200, 0x100000) in the
    code part of each line is +SHIFT (base-ROM code/data refs: equates,
    dc.l tables, jsr/jmp targets). 4-digit literals (VRAM/VDP/
    immediates), RAM ($FFxxxx) and $100000 (second MB) are untouched;
    comments are untouched. Immediates (#$10000, a 16.16 fixed-point
    1.0) are untouched.
  - hooks.csv: every hook addr +SHIFT.
  - regions.csv free space + instruction boundaries: +SHIFT for
    addresses >= 0x200 (the allocator checks fill at the shifted
    addresses; check_hooks checks the shifted boundaries). A region's
    end is CLAMPED to $100000: the shift drops the ROM's last $100
    bytes, so the tail padding genuinely ends at $FFFFF in the
    shifted ROM.
build_rom.build_base's MD5 gate is bypassed (the shifted base is not
the original by design); the manifest's base_md5 is corrected to the
shifted base's MD5 afterwards so the record stays honest.

The build is 2 MB, not 1 MB: the 1 MB shifted topdown build does NOT
fit — the topdown blob is $2E7C bytes, the shifted tail padding is
only $2E34 (the shift eats $100 of tail room), short by $48. In the
2 MB container the blob goes to the second MB's code room ($1F0000).
The second-MB payload (fast terrain streams) is generated from the
UNSHIFTED base: iso_fast_streams reads the $E358 tables at fixed ROM
addresses, so building it from the shifted base would read the wrong
bytes; the streams are position-independent record data (offsets are
relative to the block start), and the terrain tables are byte-identical
in both ROMs, so the unshifted-derived payload is the correct payload
for the shifted ROM too.

The shifted base is the songfix-patched shifted ROM
(build/shift/shifted_songfix.gen, test-only): the song-end prefixes
are #281's fix, and using the patched base keeps the feature-build
shift check from being confounded by the known music-phase diffs.

Usage:
  md_shift_feature.py --dry-run   # print every rewrite, build nothing
  md_shift_feature.py             # build both ROMs, compare the route
"""
import argparse, csv, hashlib, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_rom

SHIFT = 0x100
WORK = ROOT / "build" / "shift-topdown"
FEATURE = "topdown"
# 5-6 digit hex literals that are NOT immediates (no preceding '#'):
# immediates such as #$10000 (a 16.16 fixed-point 1.0) are values, not
# ROM addresses, and must stay. The genuine refs are equates, dc.l
# tables and jsr/jmp/lea absolute-long operands.
HEX56 = re.compile(r"(?<!#)\$([0-9A-Fa-f]{5,6})\b")


def md5(b):
    return hashlib.md5(b).hexdigest()


def shift_src_text(text, report):
    """Shift base-ROM refs in feature.s; returns the rewritten text."""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        code, sep, comment = line.partition(";")
        def rep(m):
            v = int(m.group(1), 16)
            if 0x200 <= v < 0x100000:
                report.append((lineno, m.group(0), f"${v + SHIFT:05X}"))
                return f"${v + SHIFT:05X}"
            return m.group(0)
        out.append(HEX56.sub(rep, code) + (sep + comment if sep else ""))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shift", type=lambda x: int(x, 0), default=0x100)
    a = ap.parse_args()
    shift = a.shift
    global SHIFT
    SHIFT = shift
    WORK.mkdir(parents=True, exist_ok=True)

    src = (ROOT / "patches" / FEATURE / "feature.s").read_text()
    report = []
    rewritten = shift_src_text(src, report)
    print(f"feature.s: {len(report)} literals shifted")
    for lineno, old, new in report:
        print(f"  line {lineno}: {old} -> {new}")

    hooks = list(csv.DictReader(
        open(ROOT / "patches" / FEATURE / "hooks.csv")))
    print(f"hooks.csv: {len(hooks)} hooks, all +${shift:X}")
    for h in hooks:
        print(f"  {h['addr']} -> 0x{int(h['addr'], 0) + shift:05X} "
              f"({h['kind']} {h['target']})")

    # regions: which free regions move (end clamps at $100000: the shift
    # drops the ROM's last $100 bytes)
    regs = build_rom.parse_regions(ROOT)
    for r in regs:
        if r["start"] >= 0x200:
            print(f"  region ${r['start']:05X}-${r['end'] - 1:05X} {r['cls']} "
                  f"-> ${r['start'] + shift:05X}-"
                  f"${min(r['end'] + shift, 0x100000) - 1:05X}")
        else:
            print(f"  region ${r['start']:05X}-${r['end'] - 1:05X} {r['cls']} "
                  f"-> UNCHANGED")
    if a.dry_run:
        return 0

    # write the rewritten inputs
    (WORK / "feature.s").write_text(rewritten)
    with open(WORK / "hooks.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["addr", "len", "kind", "target"])
        w.writeheader()
        for h in hooks:
            w.writerow({"addr": f"0x{int(h['addr'], 0) + shift:05X}",
                        "len": h["len"], "kind": h["kind"],
                        "target": h["target"]})

    # unshifted reference ROM (2 MB, same container as the shifted one)
    r = subprocess.run([sys.executable, "tools/build_rom.py",
                        f"FEATURES={FEATURE}", "--size", "2m"],
                       cwd=ROOT, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode:
        print(r.stderr, file=sys.stderr)
        return 1
    ref_rom = ROOT / "build" / f"rop-{FEATURE}-2m.rom"
    print(f"unshifted {FEATURE} 2m ROM MD5: {md5(ref_rom.read_bytes())}")

    # shifted base: the songfix-patched shifted ROM (test-only; see
    # docstring). Its song-end prefixes are #281's fix; using it keeps
    # the feature-build check from being confounded by music-phase diffs.
    shifted_base = ROOT / "build" / "shift" / "shifted_songfix.gen"
    if not shifted_base.is_file():
        print("no songfix shifted base: build/shift/shifted_songfix.gen "
              "missing", file=sys.stderr)
        return 1
    base_bytes = shifted_base.read_bytes()
    print(f"shifted base MD5: {md5(base_bytes)}")

    # second-MB payload, generated from the UNSHIFTED base (see
    # docstring): iso_fast_streams reads the $E358 tables at fixed
    # addresses, so the shifted base would misread them.
    import iso_fast_streams
    payload = iso_fast_streams.build((ROOT / "rop-original.gen").read_bytes())
    print(f"data2m payload from unshifted base: {len(payload)} bytes, "
          f"MD5 {md5(payload)}")
    orig_ifs_build = iso_fast_streams.build
    iso_fast_streams.build = lambda rom: payload

    # build_rom's checksum step assumes an unshifted base: the runtime
    # self-check immediate sits at $FD098+SHIFT in the shifted ROM.
    import checksum as checksum_mod
    orig_fix_rt = build_rom.fix_runtime_checksum
    build_rom.fix_runtime_checksum = (
        lambda rom: checksum_mod.fix_runtime_checksum(rom, shift))

    # monkeypatch build_rom for the shifted build
    orig_regions = build_rom.parse_regions
    orig_starts = build_rom.parse_instruction_starts
    orig_hooks = build_rom.parse_hooks
    orig_assemble = build_rom.assemble
    orig_base = build_rom.build_base

    def shifted_regions_fn(repo):
        out = []
        for r in orig_regions(repo):
            if r["start"] >= 0x200:
                # end clamps at $100000: the shift drops the ROM's last
                # $100 bytes, so the tail padding ends at $FFFFF
                r = dict(r, start=r["start"] + shift,
                         end=min(r["end"] + shift, 0x100000))
            out.append(r)
        return out

    def shifted_starts_fn(repo):
        return {s + shift if s >= 0x200 else s for s in orig_starts(repo)}

    def shifted_hooks_fn(path):
        rows = []
        for row in csv.DictReader(open(WORK / "hooks.csv", newline="")):
            rows.append({"addr": int(row["addr"], 0),
                         "len": int(row["len"], 0),
                         "kind": row["kind"].strip().lower(),
                         "target": row["target"].strip(),
                         "source": str(WORK / "hooks.csv")})
        return rows

    def shifted_assemble(vasm, src_path, org, workdir, defines):
        src_path = Path(src_path)
        if src_path.name == "feature.s" and src_path.parent.name == FEATURE:
            src_path = WORK / "feature.s"
        return orig_assemble(vasm, src_path, org, workdir, defines)

    build_rom.build_base = lambda repo, base_override: base_bytes
    build_rom.parse_regions = shifted_regions_fn
    build_rom.parse_instruction_starts = shifted_starts_fn
    build_rom.parse_hooks = shifted_hooks_fn
    build_rom.assemble = shifted_assemble
    try:
        manifest = build_rom.build([FEATURE], ROOT, out_dir=WORK, size="2m")
    finally:
        build_rom.build_base = orig_base
        build_rom.parse_regions = orig_regions
        build_rom.parse_instruction_starts = orig_starts
        build_rom.parse_hooks = orig_hooks
        build_rom.assemble = orig_assemble
        build_rom.fix_runtime_checksum = orig_fix_rt
        iso_fast_streams.build = orig_ifs_build

    # the manifest hardcodes base_md5 = ORIGINAL_MD5; correct the record
    manifest["base_md5"] = md5(base_bytes)
    manifest["base"] = ("shifted songfix base "
                        "(build/shift/shifted_songfix.gen, test-only)")
    manifest["data2m_source"] = "unshifted base (see driver docstring)"
    (WORK / f"rop-{FEATURE}-2m.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    print(f"shifted {FEATURE} ROM: {manifest['rom']} "
          f"MD5={manifest['md5']}")
    for b in manifest["blobs"]:
        print(f"  blob {b['feature']}: ${b['start'][2:]}-${b['end'][2:]} "
              f"({b['size']} bytes)")
    for h in manifest["hooks"]:
        print(f"  hook {h['addr']}: {h['kind']} {h['target']} "
              f"({h['target_addr']})")

    # compare the topdown route on both feature ROMs
    r = subprocess.run(
        [sys.executable, "tools/md_shift.py", "compare",
         "--route", "tools/playtest_route_topdown_explore.txt",
         "--orig", str(ref_rom),
         "--shifted", str(WORK / f"rop-{FEATURE}-2m.rom"),
         "--out", str(WORK / "compare"), "--no-build"],
        cwd=ROOT, capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode:
        print(r.stderr[-4000:], file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
