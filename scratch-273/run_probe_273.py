#!/usr/bin/env python3
"""Run a probe_273 ROM under BlastEm debugger with the slot_0 save state;
break on test_spin; dump $FFD800..$FFD800+2*NWORDS to scratch-273/<name>.log.txt.
Usage: run_probe_273.py <name> [nwords]  (default nwords 1400)
"""
import os, pty, re, select, subprocess, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(HERE, "scratch-273")
ROM = os.path.join(SCRATCH, "probe_273_%s.rom" % sys.argv[1])
STATE = "/home/hatch/workspace/user/files/slot_0_1_ou3l.state"
OUT = os.path.join(SCRATCH, "probe_273_%s.log.txt" % sys.argv[1])
NWORDS = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 1400
obj = os.path.join(SCRATCH, "probe_273_%s.o" % sys.argv[1])
nm = subprocess.run(["m68k-linux-gnu-nm", obj], capture_output=True, text=True).stdout
SPIN = None
for line in nm.splitlines():
    if "test_spin" in line:
        SPIN = 0xFD400 + int(line.split()[0], 16)
assert SPIN is not None, "test_spin not found in nm"
print("SPIN = 0x%X" % SPIN)

env = dict(os.environ)
env["DISPLAY"] = ":99"
env["SDL_AUDIODRIVER"] = "dummy"
logf = open(os.path.join(SCRATCH, "probe_273_%s.run.log" % sys.argv[1]), "w", buffering=1)
pid, fd = pty.fork()
if pid == 0:
    os.execve("/usr/games/blastem",
              ["/usr/games/blastem", "-d", "-s", STATE, ROM], env)

buf = b""

def drain_until(pattern, timeout=10.0):
    global buf
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        txt = buf.decode(errors="replace")
        if re.search(pattern, txt):
            return True
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                return False
            if not chunk:
                return False
            buf += chunk
            logf.write(chunk.decode(errors="replace"))
    return False

def drain(timeout=5.0):
    global buf
    end = time.time() + timeout
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.2)
        if r:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            logf.write(chunk.decode(errors="replace"))
    return buf.decode(errors="replace")

def read_words(addrs, timeout=30.0):
    global buf
    out = {}
    for i in range(0, len(addrs), 64):
        chunk_addrs = addrs[i:i + 64]
        buf = b""
        os.write(fd, "".join("p/x $%X\n" % a for a in chunk_addrs).encode())
        end = time.time() + timeout
        while time.time() < end:
            txt = buf.decode(errors="replace")
            if len(re.findall(r"\$[0-9A-Fa-f]+:\s*[0-9a-fA-F]+", txt)) >= len(chunk_addrs):
                break
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                logf.write(chunk.decode(errors="replace"))
        txt = buf.decode(errors="replace")
        for a_hex, v_hex in re.findall(r"\$([0-9A-Fa-f]+):\s*([0-9a-fA-F]+)", txt):
            try:
                out[int(a_hex, 16)] = int(v_hex, 16)
            except ValueError:
                pass
    return [out.get(a) for a in addrs]

txt = drain(10.0)
assert "Loaded" in txt, "state did not load"
os.write(fd, ("b 0x%X\n" % SPIN).encode())
time.sleep(0.5)
drain(2.0)
t0 = time.time()
os.write(fd, b"c\n")
ok = drain_until(r"Breakpoint \d+ hit", timeout=180.0)
print("spin breakpoint hit: %s after %.1fs" % (ok, time.time() - t0), flush=True)
vals = read_words([0xFFD800 + 2 * k for k in range(NWORDS)])
if "--shot" in sys.argv:
    import subprocess as sp
    shot = os.path.join(HERE, "scratch-273", "probe_273_%s.shot.png" % sys.argv[1])
    sp.run(["import", "-window", "root", shot], env=env)
    print("screenshot:", shot)
with open(OUT, "w") as f:
    for k, v in enumerate(vals):
        f.write("0x%04X\n" % v if v is not None else "None\n")
print("wrote", OUT)
try:
    os.write(fd, b"q\n")
    time.sleep(0.5)
except OSError:
    pass
try:
    os.kill(pid, 9)
except OSError:
    pass
try:
    os.waitpid(pid, 0)
except OSError:
    pass
logf.close()
