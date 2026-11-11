#!/usr/bin/env python3
"""Drive the BlastEm debugger (pty) to read back harness results.
Usage: python3 tools/read_harness.py <rom> [break_addr_hex]
Sets a breakpoint at break_addr (default 0x362, the jsr return), continues,
then reads $FFD000..$FFD00E and dumps $FFD100..$FFD127 (rec0 text) and
$FFD140..$FFD16F (rec1 text) as bytes.
"""
import os, pty, re, select, sys, time

ROM = sys.argv[1]
BREAK = sys.argv[2] if len(sys.argv) > 2 else "0x362"

env = dict(os.environ)
env["DISPLAY"] = ":99"
env["SDL_AUDIODRIVER"] = "dummy"

pid, fd = pty.fork()
if pid == 0:
    os.execve("/usr/games/blastem", ["/usr/games/blastem", "-d", ROM], env)

buf = b""
def drain(timeout=3.0):
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
    return buf

def send(cmd, timeout=3.0):
    global buf
    buf = b""
    os.write(fd, (cmd + "\n").encode())
    drain(timeout)
    return buf.decode(errors="replace")

# wait for the initial debugger prompt
drain(5.0)
out = send("b " + BREAK, 3.0)
print("--- break set ---")
print(out[-2000:])
out = send("c", 8.0)
print("--- after continue ---")
print(out[-3000:])

# now read the results
for addr in ["$FFD000", "$FFD002", "$FFD004", "$FFD006", "$FFD008",
             "$FFD00A", "$FFD00C", "$FFD00E", "$FFD0FE"]:
    out = send("p/x " + addr, 2.0)
    # print only the last line(s) that mention the value
    lines = [l for l in out.splitlines() if l.strip()]
    print(addr, "->", lines[-1] if lines else "(no output)")

# dump the rendered text: read 35 bytes at $FFD100 as words, then rec1 at $FFD140
def read_bytes(base, n):
    bs = bytearray()
    for off in range(0, n, 2):
        out = send("p/x $%X" % (base + off), 1.5)
        m = None
        for l in out.splitlines():
            mm = re.search(r"=\s*\$?([0-9a-fA-F]+)", l)
            if mm:
                m = mm.group(1)
        if m is None:
            bs += b"??"
        else:
            v = int(m, 16)
            bs += bytes([(v >> 8) & 0xFF, v & 0xFF])
    return bytes(bs[:n])

print("rec0 bytes @ $FFD100:", read_bytes(0xFFD100, 35))
print("rec1 bytes @ $FFD140:", read_bytes(0xFFD140, 48))

# quit the debugger / kill blastem
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
