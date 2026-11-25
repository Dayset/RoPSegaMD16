#!/usr/bin/env python3
"""Feature build — `make rom FEATURES=a,b,c` (issue #239).

A feature is a directory `patches/<name>/` holding:

  feature.s  — 68000 source for the patch's new code (the blob). It must
                start with `org ORGVAL`; the build supplies ORGVAL as the
                allocator-chosen address, so the source never hardcodes
                where it lands. All in-blob branches must be PC-relative
                (labels); absolute-long references to fixed game addresses
                are fine. Labels used as hook targets are exported from
                the vasm listing.
  hooks.csv  — one hook per line: `addr,len,kind,target` (header row).
                addr/len are hex (0x prefix or bare hex); kind is
                `jsr` (writes `jsr <target>.l`, len must be 6),
                `jmp` (writes `jmp <target>.l`, len must be 6) or
                `bytes` (writes the hex byte string in target verbatim,
                len must equal its byte count). For jsr/jmp, target is a
                label defined in feature.s.

The build:
  1. Builds the byte-identical base (`make build`) and refuses to
     continue unless its MD5 is the original ROM's.
  2. Assembles each feature.s with vasm into a free-space allocator.
     Free regions come from `disasm/regions.csv` (any class starting
     with `padding`, plus `zero-fill`; ends in that file are inclusive).
     Blobs are first-fit, lowest address first, 2-byte aligned, and the
     build verifies the base bytes under a blob are the region's fill
     byte before writing.
  3. Applies the hooks. The build FAILS if two hooks overlap, a hook
     splits an instruction (checked against the `; $ADDR` instruction
     boundaries in `disasm/src/rop.s`), a hook target label is not
     inside its feature's blob, or a blob collides with a hook or
     another blob.
  4. Fixes both checksums (`tools/checksum.py fix-all` order: runtime
     immediate first, header last) and writes
     `build/rop-<features>.rom`, `build/rop-<features>.ips` and
     `build/rop-<features>.manifest.json` (features, hooks, blob
     addresses, MD5).

`FEATURES=` (empty) writes `build/rop-base.rom`, which must be
byte-identical to the original ROM (MD5
30c18fdbe2183f64702ae9f1a45d63f9).

2 MB ROMs (issue #252 step 3): `--size 2m` appends a second
megabyte (`$100000-$1FFFFF`, `0xFF`-filled, 1,048,576 usable
bytes) for offline-made tile data, and sets the header ROM-end
field at `0x1A4` to `0x001FFFFF`. The base 1 MB is unchanged.
Features assemble with `SIZE2M=1` defined; a blob that no longer fits
the first megabyte's padding goes to the code room `$1F0000-$1FFFFF`
(payloads must end below it). A feature may bring its own payload:
`patches/<name>/data2m.py` with `OFFSET` and `build(base_rom)`
(generated from the ROM's own data, so nothing extra is committed).
The save moves to header-declared SRAM at `$200001-$2000FF`
(feature `sram-save`, added automatically, #284) so any emulator or
board maps it from the header; `--eeprom` keeps the original serial
EEPROM, which BlastEm maps for a 2 MB ROM only with its rom.db edited.
`--data FILE[@0xOFFSET]` (repeatable) places a payload binary in
the second megabyte (default offset `$100000`); offsets must lie
inside the second megabyte. Checksums: the runtime self-check
sums only `0x000000-0xFD07B`, so it is unaffected by the second
megabyte; the header checksum sums `0x200` to end of file, so it
covers the full 2 MB. Output is `build/rop-<features>-2m.rom`.

Usage:
    python3 tools/build_rom.py FEATURES=music-off
    python3 tools/build_rom.py --features music-off,flat-zoomed
    python3 tools/build_rom.py --base build/rop-rebuilt.gen --features music-off
    python3 tools/build_rom.py --size 2m
    python3 tools/build_rom.py --size 2m --data tiles/atlas.bin
    python3 tools/build_rom.py --size 2m --data tiles/atlas.bin@0x180000
    make rom FEATURES=music-off
    make rom SIZE=2m

The original ROM is never written; the base is rebuilt from source.
`--base` only skips the `make build` step (a test seam); the given ROM
is still MD5-checked against the original.
"""

import argparse
import csv
import hashlib
import json
import re
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from checksum import fix_checksum, fix_runtime_checksum  # noqa: E402

ORIGINAL_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"
BASE_SIZE = 0x100000
SIZES = {"1m": 0x100000, "2m": 0x200000, "8m": 0x800000, "10m": 0xA00000, "12m": 0xC00000}
BIG = ("8m", "10m", "12m")   # Sega mapper builds (#307)
CODE2M_START = 0x1F0000   # 2 MB builds: blobs may go here (last 64 KB)
SECOND_MB_START = 0x100000
SECOND_MB_FILL = 0xFF
HEADER_CHECKSUM_ADDR = 0x18E
HEADER_ROM_END_ADDR = 0x1A4  # ROM end address (last byte), big-endian


class BuildError(Exception):
    """Fatal build failure: print the message, exit 1."""


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def find_vasm(repo: Path) -> Path:
    """Locate vasmm68k_mot: the repo's tools/vasm first, then the shared
    built copy, then PATH."""
    candidates = [
        repo / "tools" / "vasm" / "vasmm68k_mot",
        Path.home() / "workspace" / "rings-of-power" / "tools" / "vasm"
        / "vasmm68k_mot",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    which = shutil.which("vasmm68k_mot")
    if which:
        return Path(which)
    raise BuildError(
        "vasmm68k_mot not found (looked in tools/vasm/, "
        "~/workspace/rings-of-power/tools/vasm/, PATH). Run `make vasm`.")


def build_base(repo: Path, base_override: Path | None) -> bytes:
    """Return the byte-identical base ROM, building it unless --base is
    given. Either way the MD5 must be the original's."""
    if base_override is not None:
        data = base_override.read_bytes()
    else:
        r = subprocess.run(["make", "build"], cwd=repo,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise BuildError(f"`make build` failed:\n{r.stdout}\n{r.stderr}")
        data = (repo / "build" / "rop-rebuilt.gen").read_bytes()
    if len(data) != BASE_SIZE:
        raise BuildError(f"base ROM is {len(data)} bytes, want {BASE_SIZE}")
    digest = md5_hex(data)
    if digest != ORIGINAL_MD5:
        raise BuildError(
            f"base ROM MD5 {digest} != original {ORIGINAL_MD5}; "
            "the base is not byte-identical, refusing to build on it")
    return data


def parse_regions(repo: Path):
    """Free-space regions from disasm/regions.csv.

    Returns a list of dicts {start, end, fill, cls} with end EXCLUSIVE
    (the CSV's ends are inclusive). Allocatable classes: anything
    starting with `padding` (fill 0xFF) and `zero-fill` (fill 0x00).
    """
    regions = []
    with open(repo / "disasm" / "regions.csv", newline="") as f:
        for row in csv.DictReader(f):
            cls = (row.get("class") or "").strip()
            if cls.startswith("padding"):
                fill = 0xFF
            elif cls == "zero-fill":
                fill = 0x00
            else:
                continue
            start = int(row["start"], 0)
            end = int(row["end"], 0) + 1  # CSV ends are inclusive
            regions.append({"start": start, "end": end, "fill": fill,
                            "cls": cls})
    regions.sort(key=lambda r: r["start"])
    if not regions:
        raise BuildError("no allocatable regions in disasm/regions.csv")
    return regions


class Allocator:
    """First-fit bump allocator over the free regions, lowest address
    first. Allocations are 2-byte aligned (68k)."""

    def __init__(self, regions, base: bytes):
        self.regions = regions
        self.base = base
        self.allocations = []  # (start, end, feature)

    def peek(self):
        """Lowest currently-free address (first region with any space),
        2-byte aligned, or None."""
        for region in self.regions:
            ptr = region["start"]
            for (s, e, _f) in self.allocations:
                if region["start"] <= s < region["end"]:
                    ptr = max(ptr, e)
            ptr = (ptr + 1) & ~1
            if ptr < region["end"]:
                return ptr
        return None

    def alloc(self, size: int, feature: str) -> int:
        if size <= 0:
            raise BuildError(f"feature {feature}: empty blob")
        size = (size + 1) & ~1  # align up to even
        for region in self.regions:
            # Free pointer: end of the last allocation in this region,
            # else the region start.
            ptr = region["start"]
            for (s, e, _f) in self.allocations:
                if region["start"] <= s < region["end"]:
                    ptr = max(ptr, e)
            ptr = (ptr + 1) & ~1
            if ptr + size <= region["end"]:
                if ptr + size > len(self.base):
                    raise BuildError(
                        f"feature {feature}: free space at "
                        f"${ptr:05X}-${ptr + size - 1:05X} is past the "
                        f"end of the {len(self.base)}-byte base ROM")
                chunk = self.base[ptr:ptr + size]
                if any(b != region["fill"] for b in chunk):
                    raise BuildError(
                        f"feature {feature}: free space at "
                        f"${ptr:05X}-${ptr + size - 1:05X} is not "
                        f"0x{region['fill']:02X}-filled "
                        f"({region['cls']}); regions.csv disagrees "
                        "with the base ROM")
                self.allocations.append((ptr, ptr + size, feature))
                return ptr
        raise BuildError(
            f"feature {feature}: no free space for {size} bytes in "
            "the padding regions")


def parse_instruction_starts(repo: Path) -> set:
    """Instruction-boundary addresses from the `; $ADDR` comments in
    disasm/src/rop.s (one per instruction line)."""
    starts = set()
    pat = re.compile(r"; \$([0-9A-Fa-f]+)\s*$")
    with open(repo / "disasm" / "src" / "rop.s", errors="replace") as f:
        for line in f:
            m = pat.search(line)
            if m:
                starts.add(int(m.group(1), 16))
    if not starts:
        raise BuildError("no instruction addresses found in disasm/src/rop.s")
    return starts


def parse_hooks(path: Path):
    """hooks.csv rows: addr,len,kind,target (header row; blank lines
    and `#` comments skipped)."""
    hooks = []
    with open(path, newline="") as f:
        reader = csv.DictReader(
            (ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")))
        for row in reader:
            try:
                addr = int(row["addr"].strip(), 0)
            except ValueError:
                addr = int(row["addr"].strip(), 16)
            length = int(row["len"].strip(), 0)
            hooks.append({
                "addr": addr,
                "len": length,
                "kind": row["kind"].strip().lower(),
                "target": row["target"].strip(),
                "source": str(path),
            })
    return hooks


def assemble(vasm: Path, src: Path, org: int, workdir: Path,
             defines: tuple = ()):
    """Assemble feature.s at org (via -DORGVAL; the source must start
    with `org ORGVAL`). Returns (blob bytes, {label: addr}). defines:
    extra NAME=VALUE symbols (2 MB builds: SIZE2M=1)."""
    workdir.mkdir(parents=True, exist_ok=True)
    binp = workdir / "feature.bin"
    lstp = workdir / "feature.lst"
    # patches/<name>/vasm-opt: the feature takes vasm's optimisations
    opt = [] if (src.parent / "vasm-opt").is_file() else ["-no-opt"]
    r = subprocess.run(
        [str(vasm), "-Fbin", "-m68000", *opt,
         f"-DORGVAL=${org:X}", *[f"-D{d}" for d in defines],
         "-L", str(lstp), "-o", str(binp), str(src)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise BuildError(f"vasm failed for {src}:\n{r.stdout}\n{r.stderr}")
    blob = binp.read_bytes()
    labels = {}
    pat = re.compile(r"^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$")
    for line in lstp.read_text(errors="replace").splitlines():
        m = pat.match(line)
        if m:
            labels[m.group(1)] = int(m.group(2), 16)
    return blob, labels


def check_hooks(hooks, instr_starts, blobs):
    """Fail on: hook splitting an instruction, hook/target length
    mismatch, overlapping hooks, blob/hook or blob/blob collision,
    hook target outside its feature's blob."""
    # Length / boundary / target checks, per hook.
    for h in hooks:
        addr, length, kind = h["addr"], h["len"], h["kind"]
        if kind not in ("jsr", "jmp", "bytes"):
            raise BuildError(
                f"hook at ${addr:05X} ({h['source']}): unknown kind "
                f"'{kind}' (want jsr|jmp|bytes)")
        if addr not in instr_starts:
            raise BuildError(
                f"hook at ${addr:05X} ({h['source']}): not on an "
                "instruction boundary (no `; $ADDR` for it in "
                "disasm/src/rop.s)")
        if addr + length not in instr_starts:
            raise BuildError(
                f"hook at ${addr:05X} len {length} ({h['source']}): "
                f"splits an instruction (end ${addr + length:05X} is "
                "not an instruction boundary in disasm/src/rop.s)")
        if kind in ("jsr", "jmp") and (length < 6 or length % 2):
            raise BuildError(
                f"hook at ${addr:05X} ({h['source']}): kind {kind} "
                f"needs an even len >= 6 (jsr.l/jmp.l + nops), got {length}")
        if kind == "bytes":
            try:
                raw = bytes.fromhex(h["target"])
            except ValueError:
                raise BuildError(
                    f"hook at ${addr:05X} ({h['source']}): kind bytes "
                    f"needs a hex byte string as target, got "
                    f"'{h['target']}'")
            if len(raw) != length:
                raise BuildError(
                    f"hook at ${addr:05X} ({h['source']}): kind bytes "
                    f"target is {len(raw)} bytes but len is {length}")
            h["bytes"] = raw
        # The resolved target (for jsr/jmp) must lie in the feature's blob.
        if kind in ("jsr", "jmp"):
            tgt = h.get("target_addr")
            if h["feature"] not in blobs:
                raise BuildError(
                    f"hook at ${addr:05X} ({h['source']}): feature "
                    f"'{h['feature']}' has no blob (no feature.s was "
                    "assembled for it)")
            blob = blobs[h["feature"]]
            if tgt is None or not (blob["start"] <= tgt < blob["end"]):
                raise BuildError(
                    f"hook at ${addr:05X} ({h['source']}): target "
                    f"'{h['target']}' resolved to "
                    f"${tgt if tgt is None else format(tgt, '05X')} "
                    "which is not inside the feature's blob "
                    f"${blob['start']:05X}-${blob['end'] - 1:05X} "
                    "(is `org ORGVAL` missing from feature.s?)")
    # Overlap: hooks vs hooks.
    ordered = sorted(hooks, key=lambda h: h["addr"])
    for a, b in zip(ordered, ordered[1:]):
        if b["addr"] < a["addr"] + a["len"]:
            raise BuildError(
                f"hook collision: ${a['addr']:05X} "
                f"(feature {a['feature']}, {a['kind']} "
                f"{a['target']}, len {a['len']}) overlaps "
                f"${b['addr']:05X} (feature {b['feature']}, "
                f"{b['kind']} {b['target']}, len {b['len']})")
    # Overlap: blobs vs hooks and blobs vs blobs.
    for name, blob in blobs.items():
        for h in hooks:
            if (h["addr"] < blob["end"]
                    and blob["start"] < h["addr"] + h["len"]):
                raise BuildError(
                    f"blob collision: feature {name} blob "
                    f"${blob['start']:05X}-${blob['end'] - 1:05X} "
                    f"overlaps hook at ${h['addr']:05X}")
    items = sorted(blobs.items(), key=lambda kv: kv[1]["start"])
    for (n1, b1), (n2, b2) in zip(items, items[1:]):
        if b2["start"] < b1["end"]:
            raise BuildError(
                f"blob collision: feature {n1} blob "
                f"${b1['start']:05X}-${b1['end'] - 1:05X} overlaps "
                f"feature {n2} blob "
                f"${b2['start']:05X}-${b2['end'] - 1:05X}")


def hook_bytes(h) -> bytes:
    """The bytes a hook writes into the ROM."""
    pad = b"\x4e\x71" * ((h["len"] - 6) // 2)  # nops after a long hook
    if h["kind"] == "jsr":
        return b"\x4e\xb9" + h["target_addr"].to_bytes(4, "big") + pad
    if h["kind"] == "jmp":
        return b"\x4e\xf9" + h["target_addr"].to_bytes(4, "big") + pad
    return h["bytes"]


def write_ips(orig: bytes, patched: bytes, path: Path):
    """Minimal IPS writer: raw records for each run of changed bytes
    (no RLE; an unchanged ROM gives a valid empty IPS). Works when
    the patched ROM is longer than the original (a 2 MB build):
    bytes past the end of the original count as changed."""
    out = bytearray(b"PATCH")
    n = max(len(orig), len(patched))

    def _byte(data: bytes, i: int):
        return data[i] if i < len(data) else None

    i = 0
    while i < n:
        if _byte(orig, i) == _byte(patched, i):
            i += 1
            continue
        j = i
        while j < n and _byte(orig, j) != _byte(patched, j):
            j += 1
        # One record per <= 0xFFFF-byte chunk of the changed run.
        while i < j:
            chunk = min(j - i, 0xFFFF)
            out += i.to_bytes(3, "big") + chunk.to_bytes(2, "big")
            out += patched[i:i + chunk]
            i += chunk
    out += b"EOF"
    path.write_bytes(bytes(out))


def apply_ips(data: bytes, ips_path: Path) -> bytes:
    """Apply an IPS file to a ROM image (used by the tests to check a
    build against an existing IPS). Records past the end of the input
    extend it (zero-padded up to the record offset), so a 2 MB IPS
    applied to the 1 MB original yields the 2 MB ROM."""
    raw = ips_path.read_bytes()
    if raw[:5] != b"PATCH" or raw[-3:] != b"EOF":
        raise BuildError(f"{ips_path}: not an IPS file")
    out = bytearray(data)
    i = 5
    while i < len(raw) - 3:
        off = int.from_bytes(raw[i:i + 3], "big")
        ln = int.from_bytes(raw[i + 3:i + 5], "big")
        i += 5
        if off > len(out):
            out += bytes(off - len(out))
        if ln == 0:  # RLE record
            count = int.from_bytes(raw[i:i + 2], "big")
            val = raw[i + 2]
            i += 3
            if off + count > len(out):
                out += bytes(off + count - len(out))
            out[off:off + count] = bytes([val]) * count
        else:
            if off + ln > len(out):
                out += bytes(off + ln - len(out))
            out[off:off + ln] = raw[i:i + ln]
            i += ln
    return bytes(out)


def parse_data_spec(spec: str) -> tuple:
    """`--data FILE[@0xOFFSET]`: payload file + where it lands in the
    ROM (default: the start of the second megabyte). Returns
    (Path, offset)."""
    if "@" in spec:
        path_s, off_s = spec.rsplit("@", 1)
        try:
            offset = int(off_s, 0)
        except ValueError:
            raise BuildError(f"--data {spec}: bad offset '{off_s}'")
    else:
        path_s, offset = spec, SECOND_MB_START
    return Path(path_s), offset


def build(features, repo: Path, base_override: Path | None = None,
          out_dir: Path | None = None, size: str = "1m",
          data: tuple = (), eeprom: bool = False) -> dict:
    """Build the feature ROM. Returns the manifest dict. Raises
    BuildError on any failure (including all collision checks).

    size is "1m" (the original 1 MB container) or "2m" (the 1 MB
    base + a second, 0xFF-filled megabyte at $100000-$1FFFFF for
    tile data). data is a tuple of (Path, offset) payloads to place
    in the second megabyte; it requires size "2m". A ROM larger than
    1 MB gets the sram-save feature first (save in header SRAM, own
    product ID, #284) unless eeprom is set."""
    requested = list(features)
    if size != "1m" and not eeprom and "sram-save" not in features:
        features = ["sram-save"] + requested
    if size not in SIZES:
        raise BuildError(f"unknown size '{size}' (want 1m, 2m, 8m, 10m or 12m)")
    target_size = SIZES[size]
    repo = Path(repo)
    out_dir = Path(out_dir) if out_dir else repo / "build"
    out_dir.mkdir(parents=True, exist_ok=True)
    vasm = find_vasm(repo)
    base = build_base(repo, base_override)
    regions = parse_regions(repo)
    instr_starts = parse_instruction_starts(repo)
    defines = ()
    alloc_base = base
    if size != "1m":
        # 2 MB builds assemble with SIZE2M=1 (code that needs the second
        # megabyte's data) and may place blobs in its last 64 KB when
        # the first megabyte's padding is full; payloads start at
        # $100000 and must end below CODE2M_START.
        defines = ("SIZE2M=1",) + (("SIZE8M=1",) if size in BIG else ())
        regions = regions + [{"start": CODE2M_START, "end": SIZES["2m"],
                              "fill": SECOND_MB_FILL,
                              "cls": "second-mb-code"}]
        alloc_base = base + bytes([SECOND_MB_FILL]) * (SIZES["2m"] - BASE_SIZE)
    # debug builds: ROP_DEFINES="NAME=1 ..." adds assembler symbols
    # (e.g. VERIFY283, patches/topdown). Never set for a release ROM.
    defines += tuple(os.environ.get("ROP_DEFINES", "").split())
    allocator = Allocator(regions, alloc_base)

    rom = bytearray(base)
    blobs = {}
    hooks = []
    workroot = out_dir / ".build-rom"
    for name in features:
        fdir = repo / "patches" / name
        src = fdir / "feature.s"
        hcsv = fdir / "hooks.csv"
        if not src.is_file():
            raise BuildError(f"feature {name}: no {src}")
        if not hcsv.is_file():
            raise BuildError(f"feature {name}: no {hcsv}")
        workdir = workroot / name
        # Pass 1 at the current free pointer gives the size; allocate;
        # pass 2 at the final address must be identical (guards
        # against origin-dependent code).
        cand = allocator.peek()
        if cand is None:
            raise BuildError(f"feature {name}: no free space left")
        blob1, labels1 = assemble(vasm, src, cand, workdir, defines)
        addr = allocator.alloc(len(blob1), name)
        if addr != cand:
            blob1, labels1 = assemble(vasm, src, addr, workdir, defines)
        blob, labels = assemble(vasm, src, addr, workdir, defines)
        if blob != blob1 or labels != labels1:
            raise BuildError(
                f"feature {name}: assembly is origin-dependent "
                "(second pass at the allocated address differs)")
        blobs[name] = {"start": addr, "end": addr + len(blob),
                       "size": len(blob), "labels": labels}
        if addr + len(blob) > len(rom):
            rom += bytes([SECOND_MB_FILL]) * (addr + len(blob) - len(rom))
        rom[addr:addr + len(blob)] = blob
        for h in parse_hooks(hcsv):
            h["feature"] = name
            if h["kind"] in ("jsr", "jmp"):
                if h["target"] not in labels:
                    raise BuildError(
                        f"feature {name}: hook at ${h['addr']:05X} "
                        f"targets label '{h['target']}' which is not "
                        "defined in feature.s")
                h["target_addr"] = labels[h["target"]]
            hooks.append(h)

    check_hooks(hooks, instr_starts, blobs)
    for h in hooks:
        rom[h["addr"]:h["addr"] + h["len"]] = hook_bytes(h)

    # Second megabyte (size "2m" only): the 1 MB base above is
    # untouched; append 0xFF-filled space at $100000-$1FFFFF and set
    # the header ROM-end field to its last byte. The feature
    # allocator never touches this region — it is the tile-data
    # room, managed here (via --data) or by a later step, not by
    # first-fit allocation. The EEPROM window at $200000 follows
    # immediately after it, so the save mapping is unchanged.
    data_placed = []
    if size != "1m":
        if len(rom) < BASE_SIZE:
            raise BuildError("internal error: 1 MB base is not 1 MB")
        rom += bytes([SECOND_MB_FILL]) * (target_size - len(rom))
        rom[HEADER_ROM_END_ADDR:HEADER_ROM_END_ADDR + 4] = (
            target_size - 1).to_bytes(4, "big")
        # Features may bring their own payload: patches/<name>/data2m.py
        # with OFFSET and build(base_rom) -> bytes (generated from the
        # original ROM's own data, so nothing extra is committed).
        gen = []
        for name in features:
            dpy = repo / "patches" / name / "data2m.py"
            if dpy.is_file():
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"data2m_{name}", dpy)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                gpath = out_dir / f"{name}-data2m.bin"
                gpath.write_bytes(mod.build(bytes(base)))
                gen.append((gpath, mod.OFFSET))
            # 8 MB builds (#307): patches/<name>/data8m.py, above 2 MB
            dpy = repo / "patches" / name / "data8m.py"
            if size in BIG and dpy.is_file():
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"data8m_{name}", dpy)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                gpath = out_dir / f"{name}-data8m.bin"
                gpath.write_bytes(mod.build(bytes(base)))
                rom[mod.OFFSET:mod.OFFSET + gpath.stat().st_size] = \
                    gpath.read_bytes()
                data_placed.append({"file": str(gpath),
                                    "offset": f"0x{mod.OFFSET:06X}",
                                    "size": gpath.stat().st_size,
                                    "md5": md5_hex(gpath.read_bytes())})
        for dpath, offset in list(gen) + list(data):
            payload = dpath.read_bytes() if dpath.is_file() else None
            if payload is None:
                raise BuildError(f"--data file not found: {dpath}")
            if offset < SECOND_MB_START or offset % 2:
                raise BuildError(
                    f"--data {dpath}: offset ${offset:X} is outside "
                    "the second megabyte (want an even address "
                    ">= $100000)")
            if offset + len(payload) > CODE2M_START:
                raise BuildError(
                    f"--data {dpath}: {len(payload)} bytes at "
                    f"${offset:X} reach the code room at "
                    f"${CODE2M_START:X}")
            if offset + len(payload) > target_size:
                raise BuildError(
                    f"--data {dpath}: {len(payload)} bytes at "
                    f"${offset:X} overflows the {target_size}-byte ROM")
            rom[offset:offset + len(payload)] = payload
            data_placed.append(
                {"file": str(dpath), "offset": f"0x{offset:05X}",
                 "size": len(payload), "md5": md5_hex(payload)})
        if size in BIG:
            # Sega mapper (512 KB banks at $A130F3-$A130FF): emulators
            # and flash carts enable it from the console name
            rom[0x100:0x110] = b"SEGA SSF        "
    elif data:
        raise BuildError("--data needs --size 2m (no second megabyte "
                         "in a 1 MB build)")

    # Header bytes a feature brings (patches/<name>/header.py, HEADER =
    # {addr: bytes}), before the checksums.
    for name in features:
        hpy = repo / "patches" / name / "header.py"
        if hpy.is_file():
            ns = {}
            exec(hpy.read_text(), ns)
            for addr, raw in ns["HEADER"].items():
                rom[addr:addr + len(raw)] = raw

    # Checksums: runtime immediate first (it is inside the header
    # checksum's range), header last — same order as checksum.py fix-all.
    # The runtime sum covers only 0x000000-0xFD07B, so the second
    # megabyte does not change it; the header sum covers 0x200 to
    # end of file, so it covers the full 2 MB.
    fix_runtime_checksum(rom)
    fix_checksum(rom)
    rom = bytes(rom)

    tag = "-".join(requested) if requested else "base"
    if size != "1m":
        tag += "-" + size
    rom_path = out_dir / f"rop-{tag}.rom"
    ips_path = out_dir / f"rop-{tag}.ips"
    manifest_path = out_dir / f"rop-{tag}.manifest.json"
    rom_path.write_bytes(rom)
    write_ips(base, rom, ips_path)
    manifest = {
        "base_md5": ORIGINAL_MD5,
        "features": list(features),
        "size": len(rom),
        "rom_size": size,
        "rom_end": f"0x{len(rom) - 1:08X}",
        "md5": md5_hex(rom),
        "rom": f"build/rop-{tag}.rom",
        "hooks": [
            {"feature": h["feature"], "addr": f"0x{h['addr']:05X}",
             "len": h["len"], "kind": h["kind"], "target": h["target"],
             "target_addr": (f"0x{h['target_addr']:05X}"
                             if "target_addr" in h else None)}
            for h in sorted(hooks, key=lambda x: x["addr"])],
        "blobs": [
            {"feature": name, "start": f"0x{b['start']:05X}",
             "end": f"0x{b['end'] - 1:05X}", "size": b["size"],
             "labels": {k: f"0x{v:05X}" for k, v in b["labels"].items()}}
            for name, b in sorted(blobs.items(),
                                  key=lambda kv: kv[1]["start"])],
    }
    if size != "1m":
        manifest["second_mb"] = {
            "start": f"0x{SECOND_MB_START:05X}",
            "end": f"0x{target_size - 1:05X}",
            "usable_bytes": target_size - BASE_SIZE,
            "fill": f"0x{SECOND_MB_FILL:02X}",
            "data": data_placed,
        }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("features_arg", nargs="?", default="",
                    help="FEATURES=a,b,c (or a bare comma list)")
    ap.add_argument("--features", default="",
                    help="comma-separated feature list")
    ap.add_argument("--base", default=None,
                    help="use this ROM as the base instead of `make build`")
    ap.add_argument("--size", default="1m", choices=["1m", "2m", "8m", "10m", "12m"],
                    help="ROM container size: 1m (default) or 2m "
                    "(1 MB base + a second, 0xFF-filled megabyte "
                    "at $100000-$1FFFFF for tile data)")
    ap.add_argument("--data", default=[], action="append",
                    help="payload binary to place in the second megabyte: "
                    "FILE[@0xOFFSET] (default offset $100000; "
                    "repeatable; needs --size 2m)")
    ap.add_argument("--eeprom", action="store_true",
                    help="keep the original EEPROM save in a ROM larger "
                    "than 1 MB (no sram-save; BlastEm then needs its "
                    "rom.db edited)")
    ap.add_argument("--repo", default=None,
                    help="repo root (default: parent of tools/)")
    ap.add_argument("--out-dir", default=None,
                    help="output directory (default: <repo>/build)")
    args = ap.parse_args(argv)
    features = []
    for raw in (args.features_arg, args.features):
        if not raw:
            continue
        if raw.startswith("FEATURES="):
            raw = raw[len("FEATURES="):]
        features += [f for f in raw.split(",") if f]
    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parent.parent
    try:
        manifest = build(features, repo,
                         base_override=Path(args.base) if args.base else None,
                         out_dir=Path(args.out_dir) if args.out_dir else None,
                         size=args.size, eeprom=args.eeprom,
                         data=tuple(parse_data_spec(s)
                                    for s in args.data))
    except BuildError as e:
        print(f"build_rom: FAILED: {e}", file=sys.stderr)
        return 1
    print(f"build_rom: wrote {manifest['rom']} "
          f"size={manifest['size']} "
          f"features={','.join(features) or '(none)'} "
          f"MD5={manifest['md5']}")
    if "second_mb" in manifest:
        smb = manifest["second_mb"]
        print(f"  second MB ${smb['start'][2:]}-${smb['end'][2:]} "
              f"({smb['usable_bytes']} usable bytes, "
              f"fill {smb['fill']})")
        for d in smb["data"]:
            print(f"  data {d['file']}: ${d['offset'][2:]} "
                  f"({d['size']} bytes, MD5={d['md5']})")
    for b in manifest["blobs"]:
        print(f"  blob {b['feature']}: ${b['start'][2:]}-${b['end'][2:]} "
              f"({b['size']} bytes)")
    for h in manifest["hooks"]:
        print(f"  hook ${h['addr'][2:]}: {h['kind']} "
              f"{h['target']} ({h['target_addr']}) [{h['feature']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
