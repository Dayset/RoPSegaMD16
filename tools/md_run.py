#!/usr/bin/env python3
"""Fast frame-stepped Mega Drive runner (Genesis Plus GX via stable-retro).

Unlike tools/playtest_metrics.py (BlastEm debugger, real-time, one
breakpoint round-trip per frame), this steps the emulator as fast as
the host allows, gives exact per-frame RAM and the rendered screen,
and needs no X display. Same route files as the input-replay overlay
(`<frames> <pad letters>` per line, U D L R B C A S, `.` = none).

  md_run.py run --rom R --route F [--frames N] [--shots 100,200] [--out DIR]
      per-frame trace -> DIR/trace.json, screenshots -> DIR/fNNNNN.png
  md_run.py metrics --trace DIR/trace.json [--from F] [--to F]
      smoothness numbers from a trace (see metrics()).

pip install stable-retro (Python >= 3.9). ROM is never written.
"""
import argparse, json, os, sys, warnings, zlib

warnings.filterwarnings("ignore")
import numpy as np

# stable-retro Genesis button order
BTN = ["B", "A", "MODE", "START", "UP", "DOWN", "LEFT", "RIGHT", "C", "Y", "X", "Z"]
LET = {"U": "UP", "D": "DOWN", "L": "LEFT", "R": "RIGHT", "A": "A", "B": "B",
       "C": "C", "S": "START"}

# RAM words sampled every frame (big-endian addresses)
FIELDS = {
    "frame": 0xFF0012, "mode": 0xFF00AE, "camx": 0xFF0E8E, "camy": 0xFF0E90,
    "leader": 0xFF02B2, "loc": 0xFF0E98, "redraw": 0xFF0098,
}


def parse_route(path):
    steps = []
    for line in open(path):
        line = line.split("#")[0].strip()
        if not line:
            continue
        n, pad = line.split()
        steps.append((int(n), "" if pad == "." else pad))
    return steps


def mask_for(pad):
    m = np.zeros(len(BTN), dtype=np.uint8)
    for ch in pad:
        m[BTN.index(LET[ch])] = 1
    return m


class MD:
    def __init__(self, rom):
        import stable_retro as retro
        # stable-retro picks the core by extension
        if not rom.endswith(".md"):
            link = f"/tmp/md_run_{os.getpid()}.md"
            if os.path.lexists(link):
                os.remove(link)
            os.symlink(os.path.abspath(rom), link)
            rom = link
        self.em = retro.RetroEmulator(rom)
        self.data = retro.data.GameData()
        self.em.configure_data(self.data)
        self.n = 0

    def ram(self):
        """64 KB work RAM, big-endian byte order (the core stores
        16-bit words little-endian)."""
        r = np.frombuffer(bytes(self.data.memory.blocks[0xFF0000]), dtype=np.uint8)
        return r.reshape(-1, 2)[:, ::-1].reshape(-1)

    def step(self, pad=""):
        self.em.set_button_mask(mask_for(pad), 0)
        self.em.step()
        self.n += 1

    def screen(self):
        return self.em.get_screen()


def w(ram, addr):
    o = addr - 0xFF0000
    return (int(ram[o]) << 8) | int(ram[o + 1])


def save_png(arr, path):
    from PIL import Image
    Image.fromarray(arr).save(path)


def run(rom, route, frames, shots, outdir, fields=None, keep_screens=False):
    os.makedirs(outdir, exist_ok=True)
    md = MD(rom)
    fields = dict(FIELDS, **(fields or {}))
    seq = []
    for n, pad in parse_route(route):
        seq += [pad] * n
    total = frames or len(seq)
    rec = []
    prev = None
    screens = []
    for i in range(total):
        md.step(seq[i] if i < len(seq) else "")
        s = md.screen()
        ram = md.ram()
        row = {k: w(ram, a) for k, a in fields.items()}
        row["i"] = i
        row["pad"] = seq[i] if i < len(seq) else ""
        row["crc"] = zlib.crc32(s.tobytes())
        row["chg"] = 0 if prev is None else int((s != prev).any(axis=2).sum())
        rec.append(row)
        if keep_screens:
            screens.append(s.copy())
        if i in shots:
            save_png(s, os.path.join(outdir, f"f{i:05d}.png"))
        prev = s
    json.dump(rec, open(os.path.join(outdir, "trace.json"), "w"))
    return rec, screens


def metrics(rec, lo=0, hi=None, thresh=50):
    """Update cadence: frames whose screen differs from the previous
    one by more than `thresh` pixels count as display updates."""
    hi = hi if hi is not None else len(rec)
    ups = [r["i"] for r in rec[lo:hi] if r["chg"] > thresh]
    gaps = [b - a for a, b in zip(ups, ups[1:])]
    out = {"frames": hi - lo, "updates": len(ups),
           "updates_per_s": round(len(ups) * 60 / max(1, hi - lo), 2)}
    if gaps:
        out.update(gap_mean=round(sum(gaps) / len(gaps), 2), gap_max=max(gaps))
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--rom", required=True)
    r.add_argument("--route", required=True)
    r.add_argument("--frames", type=int, default=0)
    r.add_argument("--shots", default="")
    r.add_argument("--out", default="build/md_run")
    m = sub.add_parser("metrics")
    m.add_argument("--trace", required=True)
    m.add_argument("--from", dest="lo", type=int, default=0)
    m.add_argument("--to", dest="hi", type=int, default=None)
    a = ap.parse_args()
    if a.cmd == "run":
        shots = {int(x) for x in a.shots.split(",") if x}
        rec, _ = run(a.rom, a.route, a.frames, shots, a.out)
        print(json.dumps(metrics(rec)))
    else:
        rec = json.load(open(a.trace))
        print(json.dumps(metrics(rec, a.lo, a.hi)))


if __name__ == "__main__":
    main()
