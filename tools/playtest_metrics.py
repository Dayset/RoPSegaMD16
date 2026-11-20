#!/usr/bin/env python3
"""Deterministic playtest harness (issue #240).

Drives a ROM with the input-replay overlay under BlastEm's debugger,
dumps per-frame state, and reports the metrics that turn Dayset's
words ("teleport", "yoink", "laggy") into numbers:

  cadence          frames between background changes (room DMA uploads)
                   — mean and max, in-game only
  bg_jump_px       largest background displacement between two
                   consecutive displayed frames (from the camera-cell
                   delta at consecutive redraws; validated once
                   against screenshots)
  leader_jitter_px largest frame-to-frame change of Buc's on-screen
                   position (cell-relative; the sub-cell walk-template
                   wobble is NOT in v1)
  walk_speed       cells per second along the scripted walk
  stall_frames     frames with a direction held that produced no
                   movement (held frames - steps * tick period)

Usage:
  playtest_metrics.py trace --rom <rom> --frames N --out <trace.json>
  playtest_metrics.py metrics --trace <trace.json> [--route <route.txt>]
  playtest_metrics.py table [--roms original,flat-zoomed,walk-unused-frames]
                            [--frames N] [--out <table.md>]
  playtest_metrics.py determinism --rom <rom> --route <route.txt> --frames N

The trace driver sets two breakpoints (VBlank $1272 and the room DMA
upload $1B9E8) and registers `di` displays for the RAM values below;
each hit prints them, the driver sends `c`, and the records are
parsed from the debugger stream. The emulator runs at real-time
60 fps under Xvfb, so a 3000-frame run is ~50 s wall; emulated time
is exact regardless of round-trip latency (the CPU is stopped
between hits). The vsync dialog blocks emulation after `c`; the
driver clicks OK at (510,315) + Return and retries if no hit
arrives. BlastEm is killed by PID (SIGKILL) at the end.

RAM sampled per VBlank hit (all words, hex):
  $FF0012 frame counter (low word)      $FF00AE mode (1 overworld, 2 room)
  $FF0E8E/$FF0E90 camera cell           $FF02C0/$FF02C2 leader cell
  $FF02C6/$FF02C8 leader cell (alt)     $FF02BE leader heading
  $FF0E14 last popped pad byte          $FF0018 live pad byte (VBlank)
  $FF0E98 location                      $FFB096/$FFB0A6/$FFB0B6/$FFB0C6 grid+$A
"""
import argparse, json, os, pty, re, select, signal, subprocess, sys, time

BLASTEM = "/usr/games/blastem"
ENV_EXTRA = {"DISPLAY": ":99", "SDL_AUDIODRIVER": "dummy"}

VBL_BP = 0x1272
DMA_BP = 0x1B9E8

# (name, address, width) in di registration order. di/x reads a WORD;
# byte fields (pad, livepad, heading) live in the HIGH byte of that
# word (big-endian: byte at the even address); word fields are the
# whole word. Verified on the smoke trace: pad $FF0E14 reads 0x4000
# (A = $40 in the high byte), livepad $FF0018 reads 0x00C7 (pad byte
# $00, no controller attached).
DI = [
    ("frame", 0xFF0012, "w"),
    ("mode", 0xFF00AE, "w"),
    ("camx", 0xFF0E8E, "w"),
    ("camy", 0xFF0E90, "w"),
    ("lx", 0xFF02C0, "w"),
    ("ly", 0xFF02C2, "w"),
    ("lx2", 0xFF02C6, "w"),
    ("ly2", 0xFF02C8, "w"),
    ("heading", 0xFF02BE, "b"),
    ("pad", 0xFF0E14, "b"),
    ("livepad", 0xFF0018, "b"),
    ("loc", 0xFF0E98, "w"),
    ("pha0", 0xFFB096, "w"),
    ("pha1", 0xFFB0A6, "w"),
    ("pha2", 0xFFB0B6, "w"),
    ("pha3", 0xFFB0C6, "w"),
    # Room leader = entity 1 (stride 0x34 from $FF02B4, cell at +$C/+$E):
    # $FF02F4/$FF02F6. Entity 0 ($FF02C0/$FF02C2) is the overworld leader
    # and freezes at the entrance cell once Buc is inside a room.
    ("e1x", 0xFF02F4, "w"),
    ("e1y", 0xFF02F6, "w"),
]
DI_ADDR = {name: addr for name, addr, _ in DI}
DI_WIDTH = {name: w for name, _, w in DI}

HIT_RE = re.compile(r"68K Breakpoint (\d) hit")
DI_RE = re.compile(r"\$([0-9A-Fa-f]+):\s*([0-9A-Fa-f]+)")
PC_RE = re.compile(r"^([0-9A-Fa-f]+):\s", re.M)


def _click_dialog(env):
    subprocess.run(["xdotool", "mousemove", "510", "315", "click", "1"],
                   env=env, timeout=5)
    time.sleep(0.5)
    subprocess.run(["xdotool", "key", "Return"], env=env, timeout=5)


def run_trace(rom, frames, out_path, label="trace", timeout=600,
              shots=None, extra_di=None):
    """Run rom under the debugger until the frame counter reaches
    `frames`; write the trace JSON to out_path. Returns the trace.
    shots: an optional set of VBlank frame numbers at which to save
    an mss screenshot of the Xvfb display (<out>.f<frame>.png).
    extra_di: an optional list of (name, addr) pairs sampled in
    addition to DI (for address hunting)."""
    if shots:
        os.environ.setdefault("DISPLAY", ":99")
    di_list = list(DI)
    if extra_di:
        di_list.extend((name, addr, "w") for name, addr in extra_di)
    env = dict(os.environ, **ENV_EXTRA)
    master, slave = pty.openpty()
    proc = subprocess.Popen([BLASTEM, "-d", rom],
                            stdin=slave, stdout=slave, stderr=slave,
                            env=env, close_fds=True)
    fd = master
    os.close(slave)
    log_path = out_path + ".dbglog"
    log = open(log_path, "w")
    buf = b""
    hits = []           # parsed hit records: (bp, {name: value}, pc)
    c_sent = 0
    started = False
    last_output = time.time()
    clicked = 0
    t0 = time.time()
    # The whole debugger stream, re-parsed from a checkpoint after
    # each drain (see _parse_hits); the tail holds the still-printing
    # partial hit.
    raw = ""

    def drain(dt):
        """Read output for up to dt seconds. Returns as soon as the
        debugger is waiting at its `>` prompt (a hit is fully
        printed) — no quiet-period wait, or the round-trip caps at
        ~3 frames/s. Falls back to dt on silence."""
        nonlocal buf, last_output
        out = b""
        end = time.time() + dt
        while time.time() < end:
            r, _, _ = select.select([fd], [], [], 0.02)
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
                buf += chunk
                last_output = time.time()
                # Prompt seen: the debugger is waiting for input.
                tail = out.decode(errors="replace")
                if re.search(r"(?:^|\n)>[ \t]*$", tail):
                    break
                end = time.time() + 0.05
        return out.decode(errors="replace")

    def send(cmd):
        nonlocal c_sent
        os.write(fd, cmd.encode())
        if cmd == "c\n":
            c_sent += 1

    try:
        time.sleep(3)
        raw += drain(2.0)
        for cmd in (f"b 0x{VBL_BP:X}\n", f"b 0x{DMA_BP:X}\n"):
            send(cmd)
            time.sleep(0.3)
            raw += drain(0.5)
        for name, addr, _w in di_list:
            send(f"di/x ${addr:05X}\n")
            time.sleep(0.1)
            raw += drain(0.3)
        send("c\n")
        started = True
        time.sleep(1.0)
        raw += drain(1.0)
        # The vsync dialog blocks emulation after `c`; click it.
        _click_dialog(env)
        clicked += 1
        raw += drain(1.0)

        vbl_frames = []
        dma_frames = []
        parsed_upto = 0
        last_status = time.time()
        while time.time() - t0 < timeout:
            chunk = drain(0.5)
            raw += chunk
            # Reparse the whole stream from the last checkpoint.
            new = raw[parsed_upto:]
            recs = _parse_hits(new)
            if recs:
                parsed_upto = len(raw) - len(recs["tail"])
                for bp, di, pc in recs["hits"]:
                    if bp == 0:
                        vbl_frames.append(di)
                    elif bp == 1:
                        dma_frames.append(di)
            # Auto-continue: one `c` per hit, plus the initial one.
            want = len(vbl_frames) + len(dma_frames) + 1
            while c_sent < want:
                send("c\n")
            # Screenshots at requested VBlank frames (the emulator is
            # stopped here, so the display shows that frame).
            if shots and vbl_frames:
                last_f = _di_int(vbl_frames[-1], "frame")
                if last_f in shots:
                    shots.discard(last_f)
                    try:
                        import mss
                        with mss.mss() as sct:
                            sct.shot(output=f"{out_path}.f{last_f}.png")
                        print(f"  shot frame {last_f}", file=sys.stderr)
                    except Exception as e:
                        print(f"  shot frame {last_f} FAILED: {e}",
                              file=sys.stderr)
            if time.time() - last_status > 5:
                last_f = (_di_int(vbl_frames[-1], "frame")
                          if vbl_frames else None)
                print(f"  ... {time.time()-t0:.0f}s wall, "
                      f"{len(vbl_frames)} vbl, {len(dma_frames)} dma, "
                      f"last frame={last_f}, c_sent={c_sent}",
                      file=sys.stderr, flush=True)
                last_status = time.time()
            # Stop when the VBlank frame counter reaches the target.
            if vbl_frames:
                last_f = _di_int(vbl_frames[-1], "frame")
                if last_f is not None and last_f >= frames:
                    break
            if time.time() - last_output > 8 and clicked < 3:
                _click_dialog(env)
                clicked += 1
                last_output = time.time()
            if time.time() - last_output > 30:
                raise RuntimeError("no debugger output for 30 s (stuck?)")
        # Final drain so the last hit's output is captured.
        tail_chunk = drain(1.0)
        raw += tail_chunk
    finally:
        # Log the FULL debugger stream (startup errors live here too).
        try:
            log.write(raw)
        except Exception:
            pass
        try:
            os.write(fd, b"q\n")
        except OSError:
            pass
        time.sleep(0.5)
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        log.close()

    trace = {"rom": rom, "label": label, "frames_target": frames,
             "vbl": vbl_frames, "dma": dma_frames,
             "wall_seconds": round(time.time() - t0, 1),
             "dialog_clicks": clicked}
    with open(out_path, "w") as fh:
        json.dump(trace, fh)
    print(f"trace: {len(vbl_frames)} VBlank hits, {len(dma_frames)} DMA hits, "
          f"{trace['wall_seconds']} s wall -> {out_path}")
    return trace


def _parse_hits(text):
    """Parse hit records out of debugger output text. Returns
    {'hits': [(bp, di, pc)], 'tail': unparsed remainder}."""
    hits = []
    # Split into blocks starting at each hit line.
    parts = HIT_RE.split(text)
    # parts: [pre, bp, block, bp, block, ...]
    tail = parts[0]
    i = 1
    while i + 1 < len(parts):
        bp = int(parts[i])
        block = parts[i + 1]
        di = {}
        for dm in DI_RE.finditer(block):
            di[dm.group(1).upper()] = dm.group(2)
        pm = PC_RE.search(block)
        pc = pm.group(1) if pm else None
        # A block is complete only if it contains a PC line or the
        # prompt; otherwise it is the still-printing tail.
        if pc is None and ">" not in block:
            tail = f"68K Breakpoint {bp} hit" + block
            break
        hits.append((bp, di, pc))
        i += 2
    else:
        tail = ""
    if i + 1 == len(parts):
        # dangling breakpoint number with no block yet
        tail = f"68K Breakpoint {parts[i]} hit"
    return {"hits": hits, "tail": tail}


def _di_int(di, name, base=16, di_list=None):
    table = di_list if di_list is not None else DI
    addr = None
    width = "w"
    for n, a, w in table:
        if n == name:
            addr, width = a, w
            break
    if addr is None:
        return None
    for k, v in di.items():
        try:
            if int(k, 16) == addr:
                val = int(v, base) & 0xFFFF
                if width == "b":
                    val = (val >> 8) & 0xFF
                return val
        except ValueError:
            continue
    return None


def normalize_trace(trace, extra_di=None):
    """Convert the raw di dicts to ints; fix up the frame counter
    (di/x may read a long — mask to the low word)."""
    di_list = list(DI)
    if extra_di:
        di_list.extend((name, addr, "w") for name, addr in extra_di)
    vbl = []
    for rec in trace["vbl"]:
        row = {}
        for name, addr, _w in di_list:
            row[name] = _di_int(rec, name, di_list=di_list)
        vbl.append(row)
    dma = []
    for rec in trace["dma"]:
        row = {}
        for name, addr, _w in di_list:
            row[name] = _di_int(rec, name, di_list=di_list)
        dma.append(row)
    return vbl, dma


def compute_metrics(trace, route_path=None):
    vbl, dma = normalize_trace(trace)
    if not vbl:
        raise RuntimeError("trace has no VBlank samples")
    # Frame numbers must be consecutive; if the di/x read gave a long
    # or a byte, the sequence breaks — detect and report.
    frames = [r["frame"] for r in vbl if r["frame"] is not None]
    if len(frames) >= 2:
        diffs = [b - a for a, b in zip(frames, frames[1:])]
        bad = [d for d in diffs if d != 1]
        if bad:
            raise RuntimeError(
                f"frame counter is not consecutive (diffs {sorted(set(bad))[:5]}); "
                "the di/x width assumption is wrong — see the trace log")
    # In-game mask: mode 1 (overworld) or 2 (room).
    ingame = [i for i, r in enumerate(vbl) if r["mode"] in (1, 2)]
    # --- cadence: frames between DMA (room redraw) hits, in-game ---
    dma_f = sorted(r["frame"] for r in dma if r["frame"] is not None)
    # Per-phase cadence: split DMA intervals by the mode at the earlier
    # hit, so the overworld and room ticks are not blended into one
    # number. The #26 ~19-22 figure is the room/cutscene cadence.
    by_frame = {r["frame"]: r for r in vbl}

    def cad_for(mode):
        fs = [f for f in dma_f
              if (by_frame.get(f) or {}).get("mode") == mode]
        iv = [b - a for a, b in zip(fs, fs[1:]) if 0 < b - a <= 120]
        return {"mean": round(sum(iv) / len(iv), 2) if iv else None,
                "max": max(iv) if iv else None, "n": len(iv)}

    cad_all = [b - a for a, b in zip(dma_f, dma_f[1:]) if 0 < b - a <= 120]
    cadence = {"mean": round(sum(cad_all) / len(cad_all), 2) if cad_all else None,
               "max": max(cad_all) if cad_all else None,
               "n": len(cad_all),
               "overworld": cad_for(1),
               "room": cad_for(2)}
    # --- camera per DMA frame (nearest VBlank sample at/before it) ---
    cam_at = {}
    for f in dma_f:
        cands = [r for r in vbl if r["frame"] is not None and r["frame"] <= f]
        if cands:
            cam_at[f] = cands[-1]
    # --- bg_jump_px: camera-cell delta between consecutive redraws ---
    # A real scroll is 1 cell (~16 px). Exclude teleports/scene changes
    # (|delta| > 2 cells in either axis: spawn, room entry, mode change).
    jumps = []
    prev = None
    for f in dma_f:
        r = cam_at.get(f)
        if r is None or r["camx"] is None or r["camy"] is None:
            prev = None
            continue
        if prev is not None:
            dc = r["camx"] - prev["camx"]
            dr = r["camy"] - prev["camy"]
            if (dc or dr) and abs(dc) <= 2 and abs(dr) <= 2:
                jumps.append(((14 * dc - 14 * dr) ** 2 +
                              (8 * dc + 8 * dr) ** 2) ** 0.5)
        prev = r
    bg_jump = {"max": round(max(jumps), 1) if jumps else 0.0,
               "mean_nonzero": round(sum(jumps) / len(jumps), 1) if jumps else 0.0,
               "n_jumps": len(jumps)}
    # Leader cell: entity 0 ($FF02C0/$FF02C2) in the overworld, entity 1
    # ($FF02F4/$FF02F6) in a room. Entity 0 freezes at the entrance cell
    # once Buc is inside, so mode selects which entity is the leader.
    def leader_xy(r):
        if r["mode"] == 2:
            return (r["e1x"], r["e1y"])
        return (r["lx"], r["ly"])

    # --- leader screen position (cell-relative, px) per VBlank ---
    # Skip pairs that straddle a mode change (room entry/exit is a scene
    # change, not a frame-to-frame position change).
    pos = []
    for r in vbl:
        lx, ly = leader_xy(r)
        if None in (lx, ly, r["camx"], r["camy"]):
            pos.append(None)
            continue
        dc = lx - r["camx"]
        dr = ly - r["camy"]
        pos.append((14 * dc - 14 * dr, 8 * dc + 8 * dr))
    jitter = 0.0
    for (ra, a), (rb, b) in zip(zip(vbl, pos), zip(vbl[1:], pos[1:])):
        if a is None or b is None or ra["mode"] != rb["mode"]:
            continue
        d = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        jitter = max(jitter, d)
    # --- walk: cells moved during the scripted direction holds ---
    # Scripted pad per frame, from the route file if given. The walk
    # window is the first-to-last scripted direction hold; this excludes
    # the boot spawn teleport and the scripted auto-walk (which runs
    # while the script feeds $00). Only +-1 cell steps count, so a
    # teleport inside the window cannot inflate the total.
    script_pad = {}
    if route_path:
        script_pad = route_to_pad_by_frame(route_path)
    dir_frames = sorted(f for f, p in script_pad.items() if p & 0x0F)
    win_lo = dir_frames[0] if dir_frames else None
    win_hi = dir_frames[-1] if dir_frames else None
    cells = 0
    cells_ow = 0
    cells_room = 0
    first_move = None
    last_move = None
    prev_xy = None
    for r in vbl:
        if r["mode"] not in (1, 2):
            prev_xy = None
            continue
        if win_lo is not None and not (win_lo <= r["frame"] <= win_hi):
            prev_xy = None
            continue
        lx, ly = leader_xy(r)
        if lx is None or ly is None:
            prev_xy = None
            continue
        xy = (lx, ly)
        if prev_xy is not None and xy != prev_xy:
            step = abs(xy[0] - prev_xy[0]) + abs(xy[1] - prev_xy[1])
            # Only a step taken while a direction is held counts: the
            # scripted auto-walk after New Game moves Buc while the
            # script feeds $00, and must not inflate the walk.
            p_now = script_pad.get(r["frame"])
            p_prev = script_pad.get(r["frame"] - 1)
            held_dir = ((p_now is not None and p_now & 0x0F) or
                        (p_prev is not None and p_prev & 0x0F))
            if step == 1 and held_dir:
                cells += 1
                if r["mode"] == 1:
                    cells_ow += 1
                else:
                    cells_room += 1
                if first_move is None:
                    first_move = r["frame"]
                last_move = r["frame"]
        prev_xy = xy
    walk_seconds = ((last_move - first_move) / 60.0
                    if first_move is not None and last_move is not None
                    and last_move > first_move else None)
    walk_speed = (round(cells / walk_seconds, 2)
                  if walk_seconds else None)
    # --- stall_frames: direction held but no movement ---
    # Held frames in the walk window, in-game with the leader spawned
    # (leader (0,0) means boot/menu, not a walk), minus the frames the
    # observed steps account for at the phase-appropriate cadence. A
    # hold that produces no step at all is pure stall; excess hold time
    # beyond one tick per step also counts.
    held = 0
    for r in vbl:
        if r["mode"] not in (1, 2):
            continue
        if win_lo is not None and not (win_lo <= r["frame"] <= win_hi):
            continue
        lx, ly = leader_xy(r)
        if lx is None or ly is None or (lx, ly) == (0, 0):
            continue
        p = script_pad.get(r["frame"])
        if p is not None and p & 0x0F:
            held += 1
    cad_ow = cadence["overworld"]["mean"] or cadence["mean"] or 22.0
    cad_room = cadence["room"]["mean"] or cadence["mean"] or 22.0
    expected = cells_ow * cad_ow + cells_room * cad_room
    stall = max(0, round(held - expected))
    return {
        "cadence": cadence,
        "bg_jump_px": bg_jump,
        "leader_jitter_px": round(jitter, 1),
        "walk_speed_cells_per_s": walk_speed,
        "walk_cells": cells,
        "walk_cells_overworld": cells_ow,
        "walk_cells_room": cells_room,
        "walk_seconds": walk_seconds,
        "stall_frames": stall,
        "held_frames": held,
        "vbl_samples": len(vbl),
        "dma_hits": len(dma_f),
    }


def route_to_pad_by_frame(route_path):
    """Route file (durations) -> {frame: pad} for every frame the
    route covers."""
    pad_bits = {"U": 0x01, "D": 0x02, "L": 0x04, "R": 0x08,
                "B": 0x10, "C": 0x20, "A": 0x40, "S": 0x80}
    out = {}
    frame = 0
    for line in open(route_path):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        dur_s, tok = line.split()
        dur = int(dur_s)
        tok = tok.strip()
        if tok in (".", "0", "-", ""):
            pad = 0
        elif tok.lower().startswith("0x"):
            pad = int(tok, 16)
        else:
            pad = 0
            for ch in tok.upper():
                pad |= pad_bits[ch]
        for _ in range(dur):
            out[frame] = pad
            frame += 1
    return out


def print_table(rows):
    print(f"{'rom':<20} {'cadence':>14} {'bg_jump':>8} {'jitter':>7} "
          f"{'walk':>8} {'stall':>6}")
    print(f"{'':<20} {'mean/max':>14} {'px max':>8} {'px max':>7} "
          f"{'cells/s':>8} {'frames':>6}")
    for name, m in rows:
        c = m["cadence"]
        print(f"{name:<20} {str(c['mean']) + '/' + str(c['max']):>14} "
              f"{m['bg_jump_px']['max']:>8} {m['leader_jitter_px']:>7} "
              f"{str(m['walk_speed_cells_per_s']):>8} {m['stall_frames']:>6}")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _md5(path):
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# Frozen per-ROM playtest: base ROM, route file, frame count. The
# base ROMs live outside this worktree (original in the main
# checkout, the other two in sibling worktrees); the routes are the
# frozen per-ROM files in tools/.
ROM_REGISTRY = {
    "original": {
        "base": "/home/hatch/workspace/rings-of-power/rop-original.gen",
        "route": "tools/playtest_route_orig.txt",
        "frames": 5300,
    },
    "flat-zoomed": {
        "base": "/home/hatch/workspace/rop-work/flat-zoomed/rop-flat-zoomed.rom",
        "route": "tools/playtest_route_flat.txt",
        "frames": 5200,
    },
    "walk-unused-frames": {
        "base": "/home/hatch/workspace/rop-work/walk-unused-frames/rop-walk-unused-frames.rom",
        "route": "tools/playtest_route_walk.txt",
        "frames": 5200,
    },
}


def _build_overlay(base, route, out_rom):
    """Apply the input-replay overlay; returns the overlay ROM MD5."""
    build_py = os.path.join(_repo_root(), "patches", "input-replay",
                            "build.py")
    r = subprocess.run([sys.executable, build_py, "--base", base,
                        "--route", route, "--out", out_rom],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"input-replay build failed for {base}:\n"
                           f"{r.stdout}\n{r.stderr}")
    return _md5(out_rom)


def _trace_cached(rom_path, route, frames, workdir, name, force=False):
    """Run the trace for one ROM, reusing a cached trace when the
    overlay ROM + route + frame count are unchanged. Returns the
    trace path."""
    os.makedirs(workdir, exist_ok=True)
    overlay = os.path.join(workdir, f"{name}.rom")
    rom_md5 = _build_overlay(rom_path, route, overlay)
    trace_path = os.path.join(workdir, f"{name}.trace.json")
    meta_path = os.path.join(workdir, f"{name}.trace.meta")
    meta = {"rom_md5": rom_md5, "route_md5": _md5(route),
            "frames": frames}
    if not force and os.path.exists(trace_path) and os.path.exists(meta_path):
        try:
            if json.load(open(meta_path)) == meta:
                print(f"[{name}] reusing cached trace {trace_path}")
                return trace_path
        except (ValueError, OSError):
            pass
    run_trace(overlay, frames, trace_path, label=name)
    json.dump(meta, open(meta_path, "w"))
    return trace_path


def cmd_table(roms, workdir, out_path=None):
    rows = []
    for name in roms:
        spec = ROM_REGISTRY[name]
        route = os.path.join(_repo_root(), spec["route"])
        trace_path = _trace_cached(spec["base"], route, spec["frames"],
                                   workdir, name)
        with open(trace_path) as fh:
            trace = json.load(fh)
        rows.append((name, compute_metrics(trace, route)))
    print_table(rows)
    if out_path:
        with open(out_path, "w") as fh:
            fh.write("| rom | cadence mean/max | bg_jump px | jitter px | "
                     "walk cells/s | stall frames |\n")
            fh.write("|---|---|---|---|---|---|\n")
            for name, m in rows:
                c = m["cadence"]
                fh.write(f"| {name} | {c['mean']}/{c['max']} | "
                         f"{m['bg_jump_px']['max']} | "
                         f"{m['leader_jitter_px']} | "
                         f"{m['walk_speed_cells_per_s']} | "
                         f"{m['stall_frames']} |\n")
    return rows


def cmd_determinism(rom, route, frames, workdir):
    """Two fresh runs of the same build + script; the metric output
    must be identical. Returns True when deterministic."""
    os.makedirs(workdir, exist_ok=True)
    overlay = os.path.join(workdir, "determinism.rom")
    _build_overlay(rom, route, overlay)
    metrics = []
    for i in (1, 2):
        trace_path = os.path.join(workdir, f"determinism.{i}.trace.json")
        run_trace(overlay, frames, trace_path, label=f"determinism.{i}")
        with open(trace_path) as fh:
            metrics.append(compute_metrics(json.load(fh), route))
    same = metrics[0] == metrics[1]
    print("determinism:", "IDENTICAL" if same else "DIFFERENT")
    if not same:
        for key in metrics[0]:
            if metrics[0][key] != metrics[1][key]:
                print(f"  {key}: run1={metrics[0][key]} "
                      f"run2={metrics[1][key]}")
    else:
        print(json.dumps(metrics[0], indent=2))
    return same


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("trace")
    p.add_argument("--rom", required=True)
    p.add_argument("--frames", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--label", default="trace")
    p.add_argument("--shots", default="",
                   help="comma-separated VBlank frames to screenshot")
    p.add_argument("--extra-di", default="",
                   help="extra di addresses as NAME=0xADDR,NAME=0xADDR")
    p = sub.add_parser("metrics")
    p.add_argument("--trace", required=True)
    p.add_argument("--route")
    p = sub.add_parser("table")
    p.add_argument("--roms", default="original,flat-zoomed,walk-unused-frames")
    p.add_argument("--out")
    p.add_argument("--workdir", default=None,
                   help="default: <repo>/.scratch-smooth240")
    p = sub.add_parser("determinism")
    p.add_argument("--rom", required=True)
    p.add_argument("--route", required=True)
    p.add_argument("--frames", type=int, required=True)
    p.add_argument("--workdir", default=None,
                   help="default: <repo>/.scratch-smooth240")
    args = ap.parse_args()

    if args.cmd == "trace":
        shots = ({int(x) for x in args.shots.split(",") if x.strip()}
                 if args.shots else None)
        extra_di = []
        if args.extra_di:
            for item in args.extra_di.split(","):
                name, addr = item.split("=")
                extra_di.append((name.strip(), int(addr.strip(), 0)))
        run_trace(args.rom, args.frames, args.out, args.label,
                  shots=shots, extra_di=extra_di or None)
    elif args.cmd == "metrics":
        with open(args.trace) as fh:
            trace = json.load(fh)
        m = compute_metrics(trace, args.route)
        print(json.dumps(m, indent=2))
    elif args.cmd == "table":
        roms = [r.strip() for r in args.roms.split(",") if r.strip()]
        workdir = (args.workdir or
                   os.path.join(_repo_root(), ".scratch-smooth240"))
        cmd_table(roms, workdir, args.out)
    elif args.cmd == "determinism":
        workdir = (args.workdir or
                   os.path.join(_repo_root(), ".scratch-smooth240"))
        ok = cmd_determinism(args.rom, args.route, args.frames, workdir)
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
