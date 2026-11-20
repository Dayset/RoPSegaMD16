#!/usr/bin/env python3
"""Build the interp-fix ROM: a one-step camera delay for the B-zoom room
walk (mode 2), so the interpolation slide is visible on screen.

Base: rop-interp.rom (MD5 309d87c5a97cdbc5c2066f11a2f98399) — flat
checkerboard (mode 2), feet fix, subcell template override, pacing gate
(1 cell / 4 ticks), interpolation slide (room-relative, in hero_track).
One fix only: delay the camera by one step during the walk.

Diagnosis (probe v2/v3/v4 + static read + Dayset's loop-walk playtest):
- The interp slide is room-relative, but the camera tracks the figure's
  committed cell exactly (probe v2: cam == Buc's cell at most commits),
  so on screen the figure stays centred and the slide just oscillates
  ~10 px behind the centre — net on-screen progress zero. That reads as
  "no subcell movement" / "standing then teleporting".
- The cutscene lag is a separate confirmed mechanism: Buc's cutscene
  record has +10 == 1 (probe v3/v4: rec10 = 1), so the record steps at
  phase 2 while the camera moves at phase 0. The world jumps first,
  then Buc catches up. This fix does NOT touch the cutscene (gated off
  while a script runs).
- Speed: the interp hook adds ~100 instructions per hero_track call
  (negligible). The walk is slow because the pacing gate commits 1 cell
  / 4 ticks (~36 frames/cell on the flat ROM vs ~22 on the original).
  Restoring original walk speed needs a pacing change (Dayset's call).

The fix: hook the two step-mode camera writes in leader_spawn ($01C21A):
$01C2D8 (move.w d0,$FF0E8E, cam X) and $01C300 (move.w d0,$FF0E90,
cam Y). Mode 6 (absolute set, teleports) is NOT hooked and snaps
immediately. Gate: delay ONLY when no event script runs ($FF0110 == 0)
AND mode == 2 (room / B-zoom view). When leader_spawn computes a new
camera during a walk, the hook stores it as the pending camera and
leaves $FF0E8E/$FF0E90 at the old cell; on the NEXT step-mode camera
write (the next commit, 4 ticks later) it first writes the pending
camera, then stores the new one. So the camera is always one step
behind the figure's committed cell, and the figure slides visibly
across a static room (centre -> centre+step over phases 0-3) before
the room jumps one cell at the next commit. The room still jumps once
per cell at the commit — fully smoothing the world shift needs a
fractional (smooth-scrolling) camera, which is the big rework, NOT
this fix. Cell rate is unchanged (1 cell / 4 ticks). The flat /
checkerboard, feet fix, subcell override, pacing gate, and interp
slide are untouched. Fixes both checksums, and emits the .ips
(round-trip verified) + changed-bytes.txt.

Hook addresses are parsed from the vasm listing — never hardcoded.
The base ROM and the original ROM are never modified (read-only here).
No live probes / screenshots / cadence measurements were run for this
build (Dayset's rule: he tests it himself).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-interp-fix')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-interp.rom'))
BASE_MD5 = '309d87c5a97cdbc5c2066f11a2f98399'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-interp-fix.rom'))
PATCHDIR = DIR
BLOB_BASE = 0xFDE00
BLOB_END = 0xFE000
HOOK_X = 0x01C2D8
HOOK_Y = 0x01C300
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble ---
src = f'{PATCHDIR}/source.s'
binp = f'{SCRATCH}/camdelay.bin'
lst = f'{SCRATCH}/camdelay.lst'
r = subprocess.run([VASM, '-Fbin', '-L', lst, '-o', binp, src],
                   capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())
    sys.exit(f'vasm failed (rc {r.returncode})')
blob = open(binp, 'rb').read()
print(f'blob: {len(blob)} bytes')

# --- parse addresses from the vasm listing ---
lstxt = open(lst, errors='replace').read()
addrs = {}
for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
    addrs[m.group(1)] = int(m.group(2), 16)
assert 'camdelay_x' in addrs, 'camdelay_x not found in the vasm listing'
assert 'camdelay_y' in addrs, 'camdelay_y not found in the vasm listing'
HOOKFN_X = addrs['camdelay_x']
HOOKFN_Y = addrs['camdelay_y']
print(f'camdelay_x ${HOOKFN_X:05X}, camdelay_y ${HOOKFN_Y:05X}')
assert HOOKFN_X == BLOB_BASE, f'camdelay_x ${HOOKFN_X:05X} != ${BLOB_BASE:05X}'
assert BLOB_BASE + len(blob) <= BLOB_END, \
    f'blob ${BLOB_BASE:05X}-${BLOB_BASE+len(blob)-1:05X} overflows ${BLOB_END:05X}'
# the displaced camera writes must be in the blob (immediate paths)
assert bytes.fromhex('33c000ff0e8e') in blob, \
    'displaced move.w d0,$FF0E8E not found in the blob'
assert bytes.fromhex('33c000ff0e90') in blob, \
    'displaced move.w d0,$FF0E90 not found in the blob'
# the blob must reference the pending-camera RAM ($FFD010/$FFD012/$FFD014)
assert bytes.fromhex('00ffd010') in blob, 'PEND_X $FFD010 not found in the blob'
assert bytes.fromhex('00ffd012') in blob, 'PEND_Y $FFD012 not found in the blob'
assert bytes.fromhex('00ffd014') in blob, 'PEND_VALID $FFD014 not found in the blob'
# the blob must gate on $FF0110 (script) and $FF00AE (mode 2)
assert bytes.fromhex('00ff0110') in blob, 'SCRIPT $FF0110 not found in the blob'
assert bytes.fromhex('00ff00ae') in blob, 'MODE $FF00AE not found in the blob'

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
# the blob region must be free 0xFF padding in the base
assert all(b == 0xFF for b in rom[BLOB_BASE:BLOB_BASE + len(blob)]), \
    'blob region is not free 0xFF padding in the base'

# --- verify the hook sites (exact base-ROM bytes) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

expect(HOOK_X, '33c000ff0e8e',
       'leader_spawn step-mode cam X write ($01C2D8, move.w d0,$FF0E8E)')
expect(HOOK_Y, '33c000ff0e90',
       'leader_spawn step-mode cam Y write ($01C300, move.w d0,$FF0E90)')
expect(0x01C242, '33c000ff0e8e',
       'leader_spawn mode-6 cam X write ($01C242, must stay unhooked)')
expect(0x01C264, '33c000ff0e90',
       'leader_spawn mode-6 cam Y write ($01C264, must stay unhooked)')

# --- write the blob and install the hooks ---
rom[BLOB_BASE:BLOB_BASE+len(blob)] = blob
rom[HOOK_X:HOOK_X+6] = b'\x4e\xb9' + struct.pack('>I', HOOKFN_X)  # jsr camdelay_x.l
rom[HOOK_Y:HOOK_Y+6] = b'\x4e\xb9' + struct.pack('>I', HOOKFN_Y)  # jsr camdelay_y.l

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

# --- verify the patch landed (re-read the fixed ROM) ---
assert fixed[BLOB_BASE:BLOB_BASE+len(blob)] == blob
assert fixed[HOOK_X:HOOK_X+6] == b'\x4e\xb9' + struct.pack('>I', HOOKFN_X)
assert fixed[HOOK_Y:HOOK_Y+6] == b'\x4e\xb9' + struct.pack('>I', HOOKFN_Y)
# all differing bytes must be inside the blob, the hook sites, or the two
# checksum locations (header 0x18E, runtime immediate 0xFD098)
base = open(BASE, 'rb').read()
diff_idx = [i for i in range(len(base)) if base[i] != fixed[i]]
bad = [i for i in diff_idx
       if not (BLOB_BASE <= i < BLOB_BASE + len(blob)
               or HOOK_X <= i < HOOK_X + 6
               or HOOK_Y <= i < HOOK_Y + 6
               or i in (0x18E, 0x18F)
               or 0xFD098 <= i < 0xFD09C)]
assert not bad, f'bytes changed outside the blob/hooks/checksums: {[hex(i) for i in bad[:10]]}'
# every earlier blob is byte-identical to the base (flat/dither $FD400,
# feet fix $FD600, subcell $FD800, pacing $FD900, interp $FDA00)
assert fixed[0xFD400:0xFDE00] == base[0xFD400:0xFDE00], \
    'an earlier blob changed!'
# the other hook sites are untouched
assert fixed[0x023202:0x023208] == base[0x023202:0x023208], \
    'hero_track interp hook site changed!'
assert fixed[0x0228CC:0x0228D2] == base[0x0228CC:0x0228D2], \
    'pacing gate hook site changed!'
assert fixed[0x01C0D6:0x01C0DC] == base[0x01C0D6:0x01C0DC], \
    'fig_replay hook changed!'
assert fixed[0x01BC1A:0x01BC20] == base[0x01BC1A:0x01BC20], \
    'flat face call site changed!'
assert fixed[0x01BC3C:0x01BC42] == base[0x01BC3C:0x01BC42], \
    'flat hidden call site changed!'
assert fixed[0x01BC84:0x01BC8A] == base[0x01BC84:0x01BC8A], \
    'flat top call site changed!'
# mode-6 camera writes are untouched (teleports snap immediately)
assert fixed[0x01C242:0x01C248] == base[0x01C242:0x01C248], \
    'mode-6 cam X write changed!'
assert fixed[0x01C264:0x01C26A] == base[0x01C264:0x01C26A], \
    'mode-6 cam Y write changed!'
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'interp-fix: {len(diff)} bytes differ from rop-interp.rom\n')
    f.write(f'camdelay_x ${HOOKFN_X:05X}, camdelay_y ${HOOKFN_Y:05X}, '
            f'blob ${BLOB_BASE:05X}-${BLOB_BASE+len(blob)-1:05X} '
            f'({len(blob)} bytes), hook sites ${HOOK_X:05X} and '
            f'${HOOK_Y:05X} (step-mode camera writes in leader_spawn; '
            f'mode-6 writes untouched)\n')
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

ips = f'{PATCHDIR}/interp-fix.ips'
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
