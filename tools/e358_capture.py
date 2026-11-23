#!/usr/bin/env python3
"""Ground-truth capture for the $E358 port (issue #252, Track A).

Full sweep (default): runs build/e358_harness.gen under stable-retro
(Genesis Plus GX) with no input. The harness makes one $E358 call per
frame into a zeroed $FF1EC0 buffer and fingerprints it immediately
(the game clears/uses $FF1EC0 later in the attract frame, so the live
buffer cannot be compared end-of-frame — the original ROM's buffer
reads all-zero during the title). After each frame this script reads
the live fingerprint + the args actually used from $FFD010+ and
compares them against tools/e358.py for the same case (see
e358.sweep_cases() / e358.fingerprint()). Writes
build/e358-capture.json (per-case match, plus the totals).

Single-case mode (--single N [N ...]): builds/runs one halt ROM per
case (tools/build_e358_harness.py --single N), which stops the CPU
right after the call so the game never touches the buffer, and
compares the FULL live buffer byte-for-byte against the port. This
is the byte-exact proof; the sweep is the coverage proof. Writes
build/e358-single.json. Full buffers for any mismatch are saved
under build/e358-mismatch/.

  python3 tools/e358_capture.py [--frames N] [--rom build/e358_harness.gen]
  python3 tools/e358_capture.py --single 0 1 3776 4286 4287 4295 4296
"""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import md_run  # noqa: E402
from e358 import BUF_BASE, BUF_LEN, N_SWEEP, E358, fingerprint, sweep_cases  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
RAM_BASE = 0xFF0000


def _lw(ram, addr):
    return struct.unpack_from(">I", bytes(ram), addr - RAM_BASE)[0]


def _read_case(ram):
    return {"idx": md_run.w(ram, 0xFFD002),
            "h1": _lw(ram, 0xFFD010), "h2": _lw(ram, 0xFFD014),
            "args_live": (md_run.w(ram, 0xFFD018), md_run.w(ram, 0xFFD01A),
                          md_run.w(ram, 0xFFD01C), md_run.w(ram, 0xFFD01E))}


def run_sweep(rom_path, frames):
    rom = (REPO / "rop-original.gen").read_bytes()
    e = E358(rom)
    cases = sweep_cases()
    md = md_run.MD(rom_path)
    results = []
    mismatches = []
    arg_mismatches = []
    last_idx = 0
    frames_per_case = []
    last_frame = 0
    t0 = time.time()
    done = False
    summary_reset = False
    for i in range(frames):
        md.step("")
        ram = md.ram()
        idx = md_run.w(ram, 0xFFD002)
        if idx < last_idx:
            # The attract cycle ended (soft reset clears RAM; the hook
            # re-inits to START_CASE when the title loop resumes).
            # Stop: the caller re-runs the missing cases as a new chunk.
            print("  attract reset at frame %d (idx %d -> %d)" % (i, last_idx, idx))
            summary_reset = True
            break
        if idx != last_idx:
            if idx == last_idx + 1 and idx > 0:
                case_no = idx - 1
                frames_per_case.append(i - last_frame)
                last_frame = i
                got = _read_case(ram)
                want, _st = e.call_buffer(*cases[case_no])
                wh1, wh2 = fingerprint(want)
                # args are words; d1 is signed in the case list
                args_live = (got["args_live"][0], got["args_live"][1],
                             s16(got["args_live"][2]), got["args_live"][3])
                rec = {"case": case_no, "args": cases[case_no],
                       "args_live": args_live,
                       "match": (got["h1"], got["h2"]) == (wh1, wh2),
                       "live_fp": [got["h1"], got["h2"]],
                       "port_fp": [wh1, wh2]}
                if args_live != cases[case_no]:
                    arg_mismatches.append(case_no)
                if not rec["match"]:
                    mismatches.append(case_no)
                results.append(rec)
                if len(results) % 500 == 0:
                    print("  %d/%d cases, %d mismatches, %d frames (%.1fs)"
                          % (len(results), N_SWEEP, len(mismatches), i, time.time() - t0),
                          flush=True)
            # else: idx jumped (harness init to START_CASE, or a reset
            # re-init) — resync without recording a case.
            last_idx = idx
        if md_run.w(ram, 0xFFD000) == 0xCA5E:
            done = True
            print("harness finished at frame %d" % i)
            break
    n = len(results)
    matched = sum(1 for r in results if r["match"])
    fps = sorted(frames_per_case)
    summary = {
        "mode": "sweep",
        "cases_run": n, "cases_total": N_SWEEP,
        "matched": matched,
        "exact_match_rate": (matched / n if n else 0),
        "mismatches": mismatches,
        "arg_mismatches": arg_mismatches,
        "harness_done": done,
        "attract_reset": summary_reset,
        "frames": i + 1, "wall_s": round(time.time() - t0, 1),
        "frames_per_case_median": fps[len(fps) // 2] if fps else None,
        "frames_per_case_max": max(fps) if fps else None,
        "cases": results,
    }
    return summary


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


def run_single(case_no, frames=3000):
    rom = (REPO / "rop-original.gen").read_bytes()
    e = E358(rom)
    cases = sweep_cases()
    gen = REPO / "build" / ("e358_single_%d.gen" % case_no)
    if not gen.exists():
        subprocess.run([sys.executable, str(REPO / "tools" / "build_e358_harness.py"),
                        "--single", str(case_no)], check=True,
                       capture_output=True)
    md = md_run.MD(str(gen))
    live = None
    for i in range(frames):
        md.step("")
        ram = md.ram()
        if md_run.w(ram, 0xFFD000) == 0xCA5E:
            live = bytes(ram[BUF_BASE - RAM_BASE:BUF_BASE - RAM_BASE + BUF_LEN])
            break
    if live is None:
        return {"case": case_no, "args": cases[case_no], "match": False,
                "error": "harness did not halt within %d frames" % frames}
    want, _st = e.call_buffer(*cases[case_no])
    match = live == want
    rec = {"case": case_no, "args": cases[case_no], "match": match,
           "live_sha": hashlib.sha256(live).hexdigest(),
           "port_sha": hashlib.sha256(want).hexdigest()}
    if not match:
        diffs = [j for j in range(BUF_LEN) if live[j] != want[j]]
        rec["n_diff"] = len(diffs)
        rec["first_diff"] = diffs[0]
        rec["first_diff_ctx"] = {
            "live": live[max(0, diffs[0] - 4):diffs[0] + 5].hex(),
            "port": want[max(0, diffs[0] - 4):diffs[0] + 5].hex()}
        d = REPO / "build" / "e358-mismatch"
        d.mkdir(parents=True, exist_ok=True)
        (d / ("case_%04d_live.bin" % case_no)).write_bytes(live)
        (d / ("case_%04d_port.bin" % case_no)).write_bytes(want)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(REPO / "build" / "e358_harness.gen"))
    ap.add_argument("--frames", type=int, default=60000)
    ap.add_argument("--out", default="")
    ap.add_argument("--single", type=int, nargs="*", default=None)
    ap.add_argument("--chunks", type=int, default=0,
                    help="run the full sweep as chunk ROMs of N cases each "
                         "(one emulator process per chunk: the attract cycle "
                         "ends after ~230 cases, so chunks must be smaller)")
    a = ap.parse_args()
    t0 = time.time()
    if a.chunks:
        all_cases = []
        mismatches = []
        arg_mismatches = []
        incomplete = []
        for s in range(0, N_SWEEP, a.chunks):
            e = min(s + a.chunks, N_SWEEP)
            gen = REPO / "build" / ("e358_chunk_%d_%d.gen" % (s, e))
            if not gen.exists():
                subprocess.run([sys.executable,
                                str(REPO / "tools" / "build_e358_harness.py"),
                                "--start", str(s), "--end", str(e)],
                               check=True, capture_output=True)
            out = REPO / "build" / ("e358-chunk-%d.json" % s)
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                "--rom", str(gen), "--frames", "6000",
                                "--out", str(out)], capture_output=True, text=True)
            print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else
                  "(chunk %d-%d: no output)" % (s, e), flush=True)
            if r.returncode != 0:
                print("chunk %d-%d FAILED:\n%s" % (s, e, r.stderr[-2000:]))
            chunk = json.loads(out.read_text())
            all_cases.extend(chunk["cases"])
            mismatches.extend(chunk["mismatches"])
            arg_mismatches.extend(chunk["arg_mismatches"])
            if chunk["cases_run"] != e - s:
                incomplete.append((s, e, chunk["cases_run"]))
        matched = sum(1 for c in all_cases if c["match"])
        summary = {"mode": "sweep-chunks", "chunk_size": a.chunks,
                   "cases_run": len(all_cases), "cases_total": N_SWEEP,
                   "matched": matched,
                   "exact_match_rate": (matched / len(all_cases) if all_cases else 0),
                   "mismatches": mismatches, "arg_mismatches": arg_mismatches,
                   "incomplete_chunks": incomplete,
                   "wall_s": round(time.time() - t0, 1), "cases": all_cases}
        out = a.out or str(REPO / "build" / "e358-capture.json")
        Path(out).write_text(json.dumps(summary, indent=1))
        print("chunks: cases %d/%d, matched %d, rate %.4f, mismatches %s, "
              "arg_mismatches %s, incomplete %s"
              % (len(all_cases), N_SWEEP, matched, summary["exact_match_rate"],
                 mismatches, arg_mismatches, incomplete))
        print("wrote %s" % out)
        return 0 if (len(all_cases) == N_SWEEP and matched == N_SWEEP
                     and not mismatches and not arg_mismatches
                     and not incomplete) else 1
    if a.single is not None:
        results = [run_single(n, a.frames if a.frames != 60000 else 3000)
                   for n in a.single]
        matched = sum(1 for r in results if r["match"])
        summary = {"mode": "single", "cases_run": len(results),
                   "matched": matched,
                   "exact_match_rate": (matched / len(results) if results else 0),
                   "wall_s": round(time.time() - t0, 1), "cases": results}
        out = a.out or str(REPO / "build" / "e358-single.json")
        Path(out).write_text(json.dumps(summary, indent=1))
        print("single: %d/%d full-buffer exact, mismatches %s"
              % (matched, len(results),
                 [r["case"] for r in results if not r["match"]]))
        print("wrote %s" % out)
        return 0 if matched == len(results) else 1
    summary = run_sweep(a.rom, a.frames)
    out = a.out or str(REPO / "build" / "e358-capture.json")
    Path(out).write_text(json.dumps(summary, indent=1))
    print("sweep: cases %d/%d, matched %d, exact-match rate %.4f, "
          "mismatches %s, arg_mismatches %s"
          % (summary["cases_run"], N_SWEEP, summary["matched"],
             summary["exact_match_rate"], summary["mismatches"],
             summary["arg_mismatches"]))
    print("wrote %s" % out)
    return 0 if (summary["cases_run"] == N_SWEEP
                 and summary["matched"] == N_SWEEP
                 and not summary["arg_mismatches"]) else 1


if __name__ == "__main__":
    sys.exit(main())
