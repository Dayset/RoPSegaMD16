#!/usr/bin/env python3
"""Save round trip on a built ROM, in Genesis Plus GX and BlastEm (#284).

Overlays the #019 save harness (tools/test_save_harness.s: save $2F11A,
load $2F896, re-read the 128 save bytes, 21 result words at $FFD000)
on a copy of ROM, hooked at $35C, and runs it:

  md_save_check.py ROM [--at 0x1FF000] [--blastem]

GPGX: frame-stepped (tools/md_run.py), result words read from RAM.
BlastEm (--blastem, needs blastem + xvfb-run): the stock emulator, no
rom.db edit, debugger breakpoint at the harness's end, then quit so it
flushes the save file, which is printed (magic $2A at byte 0).
Expect: save 0x0048, load 0x0049, re-read [0] 0x002A, error count 0.
"""
import argparse, os, pty, re, select, shutil, subprocess, sys, tempfile, time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
from checksum import fix_runtime_checksum, fix_checksum  # noqa: E402

NAMES = ["flag", "canary1", "boot_168", "boot_16a0", "boot_16a1",
         "boot_16a126", "boot_16a127", "save", "a800_124", "a800_125",
         "a800_0", "a800_1", "load", "rd0", "rd1", "rd126", "rd127",
         "errsum", "err14e", "final_168", "canary"]


def harness_bin():
    d = Path(tempfile.mkdtemp())
    subprocess.run(["m68k-linux-gnu-as", "-m68000", "-o", d / "h.o",
                    TOOLS / "test_save_harness.s"], check=True)
    subprocess.run(["m68k-linux-gnu-objcopy", "-O", "binary", d / "h.o",
                    d / "h.bin"], check=True)
    return (d / "h.bin").read_bytes()


def overlay(rom_path, at):
    rom = bytearray(Path(rom_path).read_bytes())
    h = harness_bin()
    if at + len(h) > len(rom) or any(b != 0xFF for b in rom[at:at + len(h)]):
        sys.exit(f"${at:X}: no {len(h)} free (0xFF) bytes there")
    rom[at:at + len(h)] = h
    rom[0x35C:0x362] = b"\x4e\xb9" + at.to_bytes(4, "big")
    fix_runtime_checksum(rom)
    fix_checksum(rom)
    out = Path(tempfile.mkdtemp()) / "savecheck.md"
    out.write_bytes(rom)
    # the harness's last instruction pair: move.w $C00004,d1 / rts
    end = at + bytes(h).rfind(b"\x32\x39\x00\xc0\x00\x04")
    return out, end


def words(get):
    return {n: get(0xFFD000 + 2 * i) for i, n in enumerate(NAMES)}


def run_gpgx(rom):
    from md_run import MD, w
    md = MD(str(rom))
    last = 0xFFD000 + 2 * (len(NAMES) - 1)
    for _ in range(3000):     # read before main_init clears RAM
        md.step()
        ram = md.ram()
        if w(ram, 0xFFD000) == 0xBEEF and w(ram, last):
            return words(lambda a: w(ram, a))
    return None


def run_blastem(rom, end):
    home = Path(tempfile.mkdtemp())
    env = dict(os.environ, HOME=str(home), SDL_AUDIODRIVER="dummy")
    m, s = pty.openpty()
    exe = shutil.which("blastem") or "/usr/games/blastem"
    p = subprocess.Popen(["xvfb-run", "-a", exe, "-d", str(rom)],
                         stdin=s, stdout=s, stderr=s, env=env)
    buf = b""

    def talk(cmd, until=rb">", t=60):
        nonlocal buf
        if cmd:
            os.write(m, cmd.encode() + b"\n")
        t0 = time.time()
        while time.time() - t0 < t:
            r, _, _ = select.select([m], [], [], 0.5)
            if r:
                buf += os.read(m, 65536)
                if re.search(until, buf[-400:]):
                    out, buf = buf, b""
                    return out.decode(errors="replace")
        raise TimeoutError(f"blastem: no {until!r} after {cmd!r}")

    info = talk("")
    print("blastem", " | ".join(l.strip() for l in info.splitlines()
                                if re.match(r"(Product|EEPROM|SRAM|Not found)", l.strip())))
    talk(f"b {end:x}")
    talk("c", until=rb"Breakpoint|\n>", t=120)
    res = {}
    for i, n in enumerate(NAMES):
        out = talk(f"p/x ${0xFFD000 + 2 * i:X}")
        mm = re.findall(r"FFD0[0-9A-F]+: (?:0x)?([0-9A-Fa-f]+)", out)
        res[n] = int(mm[-1], 16) if mm else None
    os.write(m, b"q\n")
    try:
        p.wait(20)
    except subprocess.TimeoutExpired:
        p.kill()
    saves = [f for f in home.rglob("*") if f.is_file() and "save" in f.name]
    return res, saves


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--at", type=lambda x: int(x, 0), default=0x1FF000)
    ap.add_argument("--blastem", action="store_true")
    a = ap.parse_args()
    rom, end = overlay(a.rom, a.at)
    g = run_gpgx(rom)
    print("gpgx   ", g and {k: hex(v) for k, v in g.items()})
    if a.blastem:
        res, saves = run_blastem(rom, end)
        print("blastem", {k: (hex(v) if v is not None else None)
                          for k, v in res.items()})
        for f in saves:
            b = f.read_bytes()
            print(f"  {f.name}: {len(b)} bytes, first 4 {b[:4].hex()}")


if __name__ == "__main__":
    main()
