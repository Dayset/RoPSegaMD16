#!/usr/bin/env python3
"""Build the walk-frames ROM: double Buc's cutscene walk animation by
repeating the existing frames (no new art) with a smaller Y shift.

Base: rop-cutscene-loop.rom (MD5 79bccdcd927707802332f64f38faa641) —
flat only on mode 2, feet fix, cutscene loop-walk (Buc walks the loop
in all four directions). Reads it, rebuilds the loop driver blob at
$FD800 (Buc steps every OTHER sys_event_run call: one cell per 8
ticks, walk_half flag $FFD104), writes the hero_track hook blob at
$FDA00 (half-cell slide + wobble subtraction), hooks hero_track
($023202) to the new hook, fixes both checksums, and emits the .ips
(round-trip verified) + changed-bytes.txt.

Dayset's direction: repeat the existing walk frames (do not create new
art) and use a smaller Y coordinate shift — the Y shift goes
8, 12, 16, 20, 24 (step 4) instead of 8, 16, 24 (step 8), same start
(8) and end (24). The 8-tick cell makes the 4-phase template cycle
twice per cell (each frame shown twice); the hook draws Buc half a
cell toward the next cell during the second half (walk_half==1), so
the Y advances 4 px per half-cell.

Entry addresses are parsed from the vasm listings — never hardcoded.
The base ROM and the original ROM are never modified (read-only here).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-walk-frames')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-cutscene-loop.rom'))
BASE_MD5 = '79bccdcd927707802332f64f38faa641'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-walk-frames.rom'))
PATCHDIR = DIR
LOOP_BASE = 0xFD800
HOOK_BASE = 0xFDA00
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

def assemble(src, binp, lst):
    r = subprocess.run([VASM, '-Fbin', '-L', lst, '-o', binp, src],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip())
        sys.exit(f'vasm failed on {src} (rc {r.returncode})')
    return open(binp, 'rb').read()

def parse_addrs(lst, names):
    lstxt = open(lst, errors='replace').read()
    addrs = {}
    for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
        addrs[m.group(1)] = int(m.group(2), 16)
    for name in names:
        assert name in addrs, f'{name} not found in the vasm listing'
    return addrs

# --- assemble both blobs ---
loop_blob = assemble(f'{PATCHDIR}/loop.s', f'{SCRATCH}/loop.bin',
                     f'{SCRATCH}/loop.lst')
print(f'loop blob: {len(loop_blob)} bytes')
hook_blob = assemble(f'{PATCHDIR}/hook.s', f'{SCRATCH}/hook.bin',
                     f'{SCRATCH}/hook.lst')
print(f'hook blob: {len(hook_blob)} bytes')

loop_addrs = parse_addrs(f'{SCRATCH}/loop.lst', ('loop_drive', 'loop_op5'))
DRIVE = loop_addrs['loop_drive']
OP5 = loop_addrs['loop_op5']
assert LOOP_BASE <= DRIVE < LOOP_BASE + len(loop_blob)
assert LOOP_BASE <= OP5 < LOOP_BASE + len(loop_blob)
assert LOOP_BASE + len(loop_blob) <= HOOK_BASE, \
    f'loop blob ${LOOP_BASE + len(loop_blob):05X} overlaps hook blob ${HOOK_BASE:05X}'
print(f'loop_drive ${DRIVE:05X}, loop_op5 ${OP5:05X}')
hook_addrs = parse_addrs(f'{SCRATCH}/hook.lst', ('walk_hook',))
HOOK = hook_addrs['walk_hook']
assert HOOK_BASE <= HOOK < HOOK_BASE + len(hook_blob)
print(f'walk_hook ${HOOK:05X}')

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
assert all(b == 0xFF for b in rom[HOOK_BASE:HOOK_BASE + 0x800]), \
    'padding at $FDA00 is not 0xFF'
assert HOOK_BASE + len(hook_blob) <= 0x100000, 'hook blob overflows the ROM'

# --- verify the sites to patch (exact base-ROM bytes) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

# sys_event_run $02D56E: jsr loop_drive.l (base already hooks it)
expect(0x02D56E, '4eb9000fd800', 'sys_event_run $02D56E jsr loop_drive.l')
# op-5 handler $02D7F6: jsr loop_op5.l (base: $FD8E2; rebuilt blob moves it)
expect(0x02D7F6, '4eb9000fd8e2', 'op-5 handler $02D7F6 jsr loop_op5.l')
# hero_track $023202: lea.l $197B0,a0 (6 bytes; unhooked in the base)
expect(0x023202, '41f9000197b0', 'hero_track $023202 lea.l $197B0,a0')

# --- write the blobs ---
rom[LOOP_BASE:LOOP_BASE+len(loop_blob)] = loop_blob
rom[HOOK_BASE:HOOK_BASE+len(hook_blob)] = hook_blob

# --- patch the sites (jsr <entry>.l, 6 bytes each) ---
def jsr(addr, target):
    rom[addr:addr+6] = b'\x4e\xb9' + struct.pack('>I', target)

jsr(0x02D56E, DRIVE)   # sys_event_run entry -> rebuilt loop driver
jsr(0x02D7F6, OP5)     # op-5 handler -> Buc-move suppressor (moved)
jsr(0x023202, HOOK)    # hero_track -> half-cell slide hook

# --- write the ROM, fix both checksums ---
open(OUT, 'wb').write(bytes(rom))
tmp = OUT + '.tmp'
r = subprocess.run([sys.executable, CHECKSUM,
                    'fix-all', OUT, tmp], check=True, capture_output=True, text=True)
print(r.stdout.strip())
os.replace(tmp, OUT)

fixed = open(OUT, 'rb').read()
print(f'fixed ROM MD5: {hashlib.md5(fixed).hexdigest()}')
print(f'header checksum @0x18E: ${struct.unpack(">H", fixed[0x18E:0x190])[0]:04X}')
print(f'runtime immediate @0xFD098: ${struct.unpack(">I", fixed[0xFD098:0xFD09C])[0]:08X}')

# --- verify the patches landed (re-read the fixed ROM) ---
assert fixed[0x02D56E:0x02D574] == b'\x4e\xb9' + struct.pack('>I', DRIVE)
assert fixed[0x02D7F6:0x02D7FC] == b'\x4e\xb9' + struct.pack('>I', OP5)
assert fixed[0x023202:0x023208] == b'\x4e\xb9' + struct.pack('>I', HOOK)
assert fixed[LOOP_BASE:LOOP_BASE+len(loop_blob)] == loop_blob
assert fixed[HOOK_BASE:HOOK_BASE+len(hook_blob)] == hook_blob
# the flat + feet-fix blobs and their hook sites must be untouched
base = open(BASE, 'rb').read()
assert fixed[0xFD400:0xFD800] == base[0xFD400:0xFD800], \
    'flat-zoomed / feet-fix blob changed!'
assert fixed[0x01C0D6:0x01C0DC] == base[0x01C0D6:0x01C0DC]
assert fixed[0x01BD98:0x01BD9E] == base[0x01BD98:0x01BD9E]
# the loop blob region beyond the rebuilt blob must be 0xFF (old blob tail)
assert all(b == 0xFF for b in fixed[LOOP_BASE+len(loop_blob):HOOK_BASE]), \
    'stale loop-blob tail between the rebuilt blob and $FDA00'
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'walk-frames: {len(diff)} bytes differ from rop-cutscene-loop.rom\n')
    f.write(f'loop_drive ${DRIVE:05X}, loop_op5 ${OP5:05X}, '
            f'loop blob ${LOOP_BASE:05X}-{LOOP_BASE+len(loop_blob)-1:05X} ({len(loop_blob)} bytes)\n')
    f.write(f'walk_hook ${HOOK:05X}, '
            f'hook blob ${HOOK_BASE:05X}-{HOOK_BASE+len(hook_blob)-1:05X} ({len(hook_blob)} bytes)\n')
    ranges = []
    for i, o, n in diff:
        if ranges and ranges[-1][1] == i:
            ranges[-1][1] = i + 1
        else:
            ranges.append([i, i + 1])
    for a, b in ranges:
        f.write(f'  ${a:05X}-${b-1:05X} ({b-a} bytes)\n')
print(f'{len(diff)} bytes differ; ranges written to changed-bytes.txt')

# --- .ips (against the base ROM) ---
def write_ips(orig_b, fixed_b, path):
    out = bytearray(b'PATCH')
    i, n = 0, len(orig_b)
    while i < n:
        if orig_b[i] == fixed_b[i]:
            i += 1
            continue
        j = i
        while j < n and orig_b[j] != fixed_b[j] and j - i < 0xFFFF:
            j += 1
        chunk = fixed_b[i:j]
        out += struct.pack('>I', i)[1:] + struct.pack('>H', len(chunk)) + chunk
        i = j
    out += b'EOF'
    open(path, 'wb').write(bytes(out))
    return path

ips = f'{PATCHDIR}/walk-frames.ips'
write_ips(base, fixed, ips)
print(f'wrote {ips} ({os.path.getsize(ips)} bytes)')

# --- IPS round-trip: base + IPS == fixed ROM exactly ---
def apply_ips(orig_b, path):
    d = bytearray(orig_b)
    data = open(path, 'rb').read()
    assert data[:5] == b'PATCH', 'bad IPS header'
    p = 5
    while data[p:p+3] != b'EOF':
        off = int.from_bytes(data[p:p+3], 'big')
        ln = int.from_bytes(data[p+3:p+5], 'big')
        p += 5
        if ln == 0:  # RLE
            rlen = int.from_bytes(data[p:p+2], 'big')
            d[off:off+rlen] = bytes([data[p+2]]) * rlen
            p += 3
        else:
            d[off:off+ln] = data[p:p+ln]
            p += ln
    return bytes(d)

rt = apply_ips(base, ips)
assert rt == fixed, 'IPS round-trip mismatch'
print('IPS round-trip verified: base + IPS == fixed ROM')
print(f'ROM: {OUT}')
