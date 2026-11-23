#!/usr/bin/env python3
"""Shift test in Genesis Plus GX (#280).

  md_shift.py build [--shift 0x100] [--out build/shift/shifted.gen]
      Build the shifted ROM exactly as tools/shift_test.sh does:
      SHIFT bytes of padding before the code at $200, both checksums
      fixed. Prints the shifted ROM path and its MD5.
  md_shift.py trace --rom R --route F --out DIR [--frames N]
                    [--state-frames 430,431]
      Run one ROM in GPGX (stable-retro, its own process), one frame
      at a time along the route. Writes DIR/trace.json (per-frame
      screen CRC32 + RAM fields, same shape as tools/md_run.py) and,
      for each --state-frames entry, DIR/state_fNNNNN.bin (the
      emulator savestate, readable by tools/md_vram.py) and
      DIR/ram_fNNNNN.bin (64 KB work RAM).
  md_shift.py compare --route F [--frames N] [--shift 0x100]
                      [--out build/shift]
                      [--orig ROM] [--shifted ROM] [--no-build]
      Build the shifted ROM, trace original and shifted in separate
      processes, and report the first differing frame, how many frames
      differ, and the first differing VRAM/CRAM/VSRAM/regs/RAM bytes
      at the first differing frame. With --orig/--shifted/--no-build
      the two ROMs are compared as given (feature builds).
"""
import argparse, json, os, subprocess, sys, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md_run, md_vram

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_shifted(shift, out):
    tmp = os.path.join(ROOT, "build", "shift")
    os.makedirs(tmp, exist_ok=True)
    src = os.path.join(tmp, "rop-shift.s")
    env = dict(os.environ, SHIFT=hex(shift), ROP_SRC=src)
    subprocess.run([sys.executable, "tools/gen_src.py"],
                   cwd=ROOT, env=env, check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["tools/vasm/vasmz80_oldstyle", "-Fbin", "-o",
                    "build/z80_snd_driver.bin", "disasm/z80/snd_driver.s"],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    inc = os.path.join(ROOT, "build", "checksum.inc")
    open(inc, "w").write("RUNTIME_SUM\tequ\t0\nHEADER_SUM\tequ\t0\n")
    subprocess.run(["tools/vasm/vasmm68k_mot", "-Fbin", "-m68000",
                    "-no-opt", "-o", os.path.join(tmp, "pass1.gen"), src],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "tools/checksum.py", "inc",
                    os.path.join(tmp, "pass1.gen"), "build/checksum.inc",
                    hex(shift)], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["tools/vasm/vasmm68k_mot", "-Fbin", "-m68000",
                    "-no-opt", "-o", out, src],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "tools/checksum.py", "inc",
                    out, "build/checksum.inc", hex(shift)], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL)
    rom = open(out, "rb").read()
    assert len(rom) == 1048576, len(rom)
    return out


def trace(rom, route, frames, state_frames, outdir):
    os.makedirs(outdir, exist_ok=True)
    md = md_run.MD(rom)
    seq = []
    for n, pad in md_run.parse_route(route):
        seq += [pad] * n
    total = frames or len(seq)
    rec = []
    prev = None
    for i in range(total):
        md.step(seq[i] if i < len(seq) else "")
        s = md.screen()
        ram = md.ram()
        row = {k: md_run.w(ram, a) for k, a in md_run.FIELDS.items()}
        row["i"] = i
        row["pad"] = seq[i] if i < len(seq) else ""
        row["crc"] = zlib.crc32(s.tobytes())
        row["chg"] = 0 if prev is None else int((s != prev).any(axis=2).sum())
        rec.append(row)
        if i in state_frames:
            open(os.path.join(outdir, "state_f%05d.bin" % i), "wb").write(
                md.em.get_state())
            open(os.path.join(outdir, "ram_f%05d.bin" % i), "wb").write(
                bytes(ram))
        prev = s
    json.dump(rec, open(os.path.join(outdir, "trace.json"), "w"))
    return rec


def first_diffs(a, b, limit=10):
    """First differing byte offsets between two equal-length buffers."""
    out = []
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            out.append((i, x, y))
            if len(out) >= limit:
                break
    return out


def diff_states(orig_dir, shift_dir, frame):
    o = md_vram.vdp_from_state(
        open(os.path.join(orig_dir, "state_f%05d.bin" % frame), "rb").read())
    s = md_vram.vdp_from_state(
        open(os.path.join(shift_dir, "state_f%05d.bin" % frame), "rb").read())
    rep = {}
    for key in ("vram", "cram", "vsram"):
        d = first_diffs(o[key], s[key])
        rep[key] = {"ndiff_bytes": sum(1 for x, y in zip(o[key], s[key]) if x != y),
                    "first": [(hex(i), hex(x), hex(y)) for i, x, y in d]}
    rep["regs"] = {"ndiff": sum(1 for x, y in zip(o["regs"], s["regs"]) if x != y),
                   "first": [(i, int(x), int(y)) for i, (x, y)
                             in enumerate(zip(o["regs"], s["regs"])) if x != y][:10]}
    oram = open(os.path.join(orig_dir, "ram_f%05d.bin" % frame), "rb").read()
    sram = open(os.path.join(shift_dir, "ram_f%05d.bin" % frame), "rb").read()
    d = first_diffs(oram, sram)
    rep["ram"] = {"ndiff_bytes": sum(1 for x, y in zip(oram, sram) if x != y),
                  "first": [(hex(0xFF0000 + i), hex(x), hex(y)) for i, x, y in d]}
    return rep


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--shift", type=lambda x: int(x, 0), default=0x100)
    b.add_argument("--out", default="build/shift/shifted.gen")
    t = sub.add_parser("trace")
    t.add_argument("--rom", required=True)
    t.add_argument("--route", required=True)
    t.add_argument("--frames", type=int, default=0)
    t.add_argument("--state-frames", default="")
    t.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--route", required=True)
    c.add_argument("--frames", type=int, default=0)
    c.add_argument("--shift", type=lambda x: int(x, 0), default=0x100)
    c.add_argument("--orig", default="rop-original.gen",
                   help="first ROM (default: the original)")
    c.add_argument("--shifted", default="",
                   help="second ROM (default: freshly built shifted ROM)")
    c.add_argument("--no-build", action="store_true",
                   help="do not rebuild the shifted ROM; --shifted required")
    c.add_argument("--out", default="build/shift")
    a = ap.parse_args()

    if a.cmd == "build":
        out = build_shifted(a.shift, a.out)
        import hashlib
        print(json.dumps({"shifted": out,
                          "md5": hashlib.md5(open(out, "rb").read()).hexdigest()}))
        return

    if a.cmd == "trace":
        sf = {int(x) for x in a.state_frames.split(",") if x}
        rec = trace(a.rom, a.route, a.frames, sf, a.out)
        print(json.dumps(md_run.metrics(rec)))
        return

    # compare
    outdir = a.out
    if a.no_build:
        if not a.shifted:
            ap.error("--no-build needs --shifted")
        shifted = a.shifted
    else:
        shifted = build_shifted(a.shift,
                                a.shifted or os.path.join(outdir, "shifted.gen"))
    orig_dir = os.path.join(outdir, "orig")
    shift_dir = os.path.join(outdir, "shift")
    here = os.path.abspath(__file__)
    for rom, d in ((a.orig, orig_dir), (shifted, shift_dir)):
        subprocess.run([sys.executable, here, "trace", "--rom", rom,
                        "--route", a.route, "--frames", str(a.frames),
                        "--out", d], cwd=ROOT, check=True)
    ot = json.load(open(os.path.join(orig_dir, "trace.json")))
    st = json.load(open(os.path.join(shift_dir, "trace.json")))
    diffs = [i for i, (x, y) in enumerate(zip(ot, st)) if x["crc"] != y["crc"]]
    rep = {"frames": len(ot), "ndiff": len(diffs),
           "first_diff": diffs[0] if diffs else None,
           "diff_frames": diffs[:20]}
    print(json.dumps(rep, indent=2))
    if diffs:
        f = diffs[0]
        # state capture goes to separate dirs: re-running trace into
        # orig_dir/shift_dir would overwrite the full trace.json
        for rom, d in ((a.orig, orig_dir + "_state"),
                       (shifted, shift_dir + "_state")):
            subprocess.run([sys.executable, here, "trace", "--rom", rom,
                            "--route", a.route, "--frames", str(f + 1),
                            "--state-frames", str(f), "--out", d],
                           cwd=ROOT, check=True)
        print(json.dumps({"frame": f, "state_diff": diff_states(orig_dir + "_state", shift_dir + "_state", f)},
                         indent=2))


if __name__ == "__main__":
    main()
