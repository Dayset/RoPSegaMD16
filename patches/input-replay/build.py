#!/usr/bin/env python3
"""Build an input-replay overlay ROM (issue #240).

Takes a base ROM (original, flat-zoomed, or walk-unused-frames) and a
route file, and produces a ROM with the input-replay feature: the
joypad_queue_pop hook ($1350) feeds pad bytes from a script table,
so the same ROM + the same script = the same run, every time.

Usage:
  build.py --base <base.rom> --route <route.txt> --out <out.rom>
           [--patchdir <dir>] [--scratch <dir>]

Route file format (one step per line; `#` = comment):
    <frames> <pad>
  <frames> = hold duration in frames (from reset, 60 fps).
  <pad>    = buttons held, as letters (U D L R B C A S, combinable,
             e.g. UR) or `.`/`0` for none, or a hex byte (0x40).
  Steps are durations; the builder accumulates frames and emits a
  table entry (frame_count, pad1) at each change, plus a trailing
  release at the end of the script. Pad byte format: bit=1 pressed
  (01 U, 02 D, 04 L, 08 R, 10 B, 20 C, 40 A, 80 S).

The blob lives at $FE000 (free 0xFF padding in all three base ROMs;
highest non-FF past $FD000 is $FDAC3 in walk-unused-frames). The
hook site is $1350 (joypad_queue_pop prologue, 8 bytes). Both
checksums are fixed with tools/checksum.py fix-all (runtime first,
header last). The base ROM and the original ROM are never modified.
"""
import argparse, hashlib, os, re, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKTREE = os.path.dirname(os.path.dirname(HERE))
# vasm is git-ignored, so a fresh worktree has no tools/vasm; fall back
# to the main checkout's copy, then PATH.
def _find_vasm():
    for cand in (os.path.join(WORKTREE, "tools", "vasm", "vasmm68k_mot"),
                 "/home/hatch/workspace/rings-of-power/tools/vasm/vasmm68k_mot",
                 "vasmm68k_mot"):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None
VASM = _find_vasm()
if VASM is None:
    sys.exit("vasm not found (tools/vasm/vasmm68k_mot); run `make vasm` in the main checkout")
CHECKSUM = os.path.join(WORKTREE, "tools", "checksum.py")

BLOB_BASE = 0xFE000
HOOK_SITE = 0x1350
HOOK_ORIG = bytes.fromhex("7000720046fc2700")  # moveq #0,d0; moveq #0,d1; move.w #$2700,sr
POP_BODY = 0x1358  # joypad_queue_pop body, right after the hook site
MAGIC = 0x9C07

# Known base ROMs (MD5 -> name). The overlay works on any base whose
# hook-site bytes match and whose $FE000.. region is 0xFF padding for
# the blob length; the MD5 check is a safety net, not a whitelist.
KNOWN_BASES = {
    "30c18fdbe2183f64702ae9f1a45d63f9": "original",
    "4ee66e521ac9a636d2167c0d55409d92": "flat-zoomed",
    "6764e6ee86976e1a3607388f4cb5faa3": "walk-unused-frames",
}

PAD_BITS = {"U": 0x01, "D": 0x02, "L": 0x04, "R": 0x08,
            "B": 0x10, "C": 0x20, "A": 0x40, "S": 0x80}


def parse_pad(tok):
    tok = tok.strip()
    if tok in (".", "0", "-", ""):
        return 0
    if tok.lower().startswith("0x"):
        v = int(tok, 16)
        assert 0 <= v <= 0xFF, f"pad byte out of range: {tok}"
        return v
    v = 0
    for ch in tok.upper():
        assert ch in PAD_BITS, f"unknown pad button: {ch!r} in {tok!r}"
        v |= PAD_BITS[ch]
    return v


def parse_route(path):
    """Route file -> list of (frame_count, pad) change entries."""
    steps = []
    for lineno, line in enumerate(open(path), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        assert len(parts) == 2, f"{path}:{lineno}: want '<frames> <pad>', got {line!r}"
        frames = int(parts[0])
        assert frames > 0, f"{path}:{lineno}: frames must be > 0"
        steps.append((frames, parse_pad(parts[1])))
    assert steps, "empty route file"
    # durations -> change entries
    entries = []
    frame = 0
    cur = 0
    for dur, pad in steps:
        if pad != cur:
            entries.append((frame, pad))
            cur = pad
        frame += dur
    if cur != 0:
        entries.append((frame, 0))  # release at the end of the script
    if entries:
        assert entries[-1][0] < 0xFFFF, "route runs past 65535 frames"
        assert all(entries[i][0] < entries[i + 1][0]
                   for i in range(len(entries) - 1)), \
            "table entries out of order"
    # An all-zero route leaves entries empty: the table is just the
    # $FFFF terminator and replay_pop feeds $00 forever. That is fine.
    return entries, frame


def write_table(entries):
    out = bytearray()
    for frame, pad in entries:
        out += struct.pack(">HBB", frame, pad, 0)
    out += struct.pack(">H", 0xFFFF)  # terminator
    return bytes(out)


def write_ips(orig_b, fixed_b, path):
    out = bytearray(b"PATCH")
    i, n = 0, len(orig_b)
    while i < n:
        if orig_b[i] == fixed_b[i]:
            i += 1
            continue
        j = i
        while j < n and orig_b[j] != fixed_b[j] and j - i < 0xFFFF:
            j += 1
        chunk = fixed_b[i:j]
        out += struct.pack(">I", i)[1:] + struct.pack(">H", len(chunk)) + chunk
        i = j
    out += b"EOF"
    open(path, "wb").write(bytes(out))
    return path


def apply_ips(orig_b, path):
    d = bytearray(orig_b)
    data = open(path, "rb").read()
    assert data[:5] == b"PATCH", "bad IPS header"
    p = 5
    while data[p:p + 3] != b"EOF":
        off = int.from_bytes(data[p:p + 3], "big")
        p += 3
        ln = int.from_bytes(data[p:p + 2], "big")
        p += 2
        if ln == 0:
            rle = int.from_bytes(data[p:p + 2], "big")
            p += 2
            d[off:off + rle] = bytes([data[p]]) * rle
            p += 1
        else:
            d[off:off + ln] = data[p:p + ln]
            p += ln
    return bytes(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--patchdir", default=HERE)
    ap.add_argument("--scratch", default=None,
                    help="default: <out-dir>/scratch-input-replay")
    args = ap.parse_args()
    # Per-run outputs (.ips, changed-bytes.txt, vasm intermediates) go
    # next to --out, never into patches/: the .ips files under patches/
    # are tracked by git (!patches/**/*.ips), so writing them into the
    # patch dir would pollute every checkout that runs the builder.
    out_dir = os.path.dirname(os.path.abspath(args.out))
    if args.scratch is None:
        args.scratch = os.path.join(out_dir, "scratch-input-replay")
    os.makedirs(args.scratch, exist_ok=True)
    os.makedirs(args.patchdir, exist_ok=True)

    entries, total_frames = parse_route(args.route)
    print(f"route: {len(entries)} change entries, {total_frames} frames")
    table = write_table(entries)
    open(os.path.join(args.patchdir, "replay_table.bin"), "wb").write(table)

    # --- assemble (CWD = patchdir so vasm finds replay_table.bin) ---
    src = os.path.join(args.patchdir, "source.s")
    binp = os.path.join(args.scratch, "input_replay.bin")
    lst = os.path.join(args.scratch, "input_replay.lst")
    r = subprocess.run([VASM, "-Fbin", "-L", lst, "-o", binp, src],
                       capture_output=True, text=True, cwd=args.patchdir)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip())
        sys.exit(f"vasm failed (rc {r.returncode})")
    blob = open(binp, "rb").read()
    print(f"blob: {len(blob)} bytes (code + {len(table)}-byte table)")

    # --- parse entry addresses from the listing (never hardcoded) ---
    lstxt = open(lst, errors="replace").read()
    addrs = {}
    for m in re.finditer(r"^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$", lstxt, re.M):
        addrs[m.group(1)] = int(m.group(2), 16)
    for name in ("replay_pop", "TABLE"):
        assert name in addrs, f"{name} not found in the vasm listing"
    assert addrs["replay_pop"] == BLOB_BASE + 2, \
        f"replay_pop ${addrs['replay_pop']:05X}, want ${BLOB_BASE + 2:05X} (magic word first)"
    assert BLOB_BASE <= addrs["TABLE"] < BLOB_BASE + len(blob)
    print(f"replay_pop ${addrs['replay_pop']:05X}, TABLE ${addrs['TABLE']:05X}")

    # --- read and verify the base ROM ---
    orig = open(args.base, "rb").read()
    assert len(orig) == 0x100000, f"base ROM size {len(orig)}"
    md5 = hashlib.md5(orig).hexdigest()
    base_name = KNOWN_BASES.get(md5, f"unknown ({md5})")
    print(f"base: {args.base} ({base_name})")
    assert orig[HOOK_SITE:HOOK_SITE + 8] == HOOK_ORIG, \
        f"hook site bytes mismatch: {orig[HOOK_SITE:HOOK_SITE + 8].hex()} (want {HOOK_ORIG.hex()})"
    assert all(b == 0xFF for b in orig[BLOB_BASE:BLOB_BASE + len(blob)]), \
        "blob region is not 0xFF padding in the base ROM"
    assert BLOB_BASE + len(blob) <= 0x100000, "blob overflows the ROM"

    # --- apply: blob + hook ---
    fixed = bytearray(orig)
    fixed[BLOB_BASE:BLOB_BASE + len(blob)] = blob
    fixed[HOOK_SITE:HOOK_SITE + 8] = struct.pack(">H", 0x4EB9) + \
        struct.pack(">I", addrs["replay_pop"]) + struct.pack(">H", 0x4E71)
    assert fixed[HOOK_SITE:HOOK_SITE + 6] == bytes.fromhex("4eb9") + \
        struct.pack(">I", addrs["replay_pop"]), "hook jsr malformed"
    assert fixed[HOOK_SITE + 6:HOOK_SITE + 8] == bytes.fromhex("4e71"), "hook nop missing"

    # --- checksums: runtime first (blob is past $FD07B, hook is inside),
    #     header last (header sum covers the whole ROM) ---
    tmp = os.path.join(args.scratch, "tmp_fixed.rom")
    open(tmp, "wb").write(bytes(fixed))
    r = subprocess.run([sys.executable, CHECKSUM, "fix-all", tmp, args.out],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip())
        sys.exit(f"checksum fix-all failed (rc {r.returncode})")
    fixed = open(args.out, "rb").read()

    # --- verify: checksums, IPS round-trip, changed bytes ---
    r = subprocess.run([sys.executable, CHECKSUM, "verify-all", args.out],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    assert r.returncode == 0, "checksum verify-all failed on the output ROM"
    ips = os.path.join(out_dir, os.path.basename(args.out).replace(".rom", ".ips"))
    write_ips(orig, fixed, ips)
    print(f"wrote {ips} ({os.path.getsize(ips)} bytes)")
    assert apply_ips(orig, ips) == fixed, "IPS round-trip mismatch"
    print("IPS round-trip exact")

    changed = [(i, orig[i], fixed[i]) for i in range(len(orig)) if orig[i] != fixed[i]]
    runs = []
    for i, o, f in changed:
        if runs and i == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], i, runs[-1][2] + 1)
        else:
            runs.append((i, i, 1))
    cb = os.path.join(out_dir, "changed-bytes.txt")
    with open(cb, "w") as fh:
        fh.write(f"base: {args.base} ({base_name})\n")
        fh.write(f"route: {args.route} ({len(entries)} entries, {total_frames} frames)\n")
        fh.write(f"blob: {len(blob)} bytes at ${BLOB_BASE:05X}\n")
        fh.write(f"changed bytes: {len(changed)} in {len(runs)} runs\n")
        for a, b, n in runs:
            fh.write(f"  ${a:05X}-${b:05X} ({n} bytes)\n")
    print(f"changed: {len(changed)} bytes in {len(runs)} runs -> {cb}")
    print(f"output: {args.out}  MD5 {hashlib.md5(fixed).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
