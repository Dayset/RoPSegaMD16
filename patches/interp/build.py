#!/usr/bin/env python3
"""Build the interp ROM: a smooth slide for the leader figure (Buc) in the
B-zoom view (mode 2, the room).

Base: rop-pacing.rom (MD5 6abeec0bea66365f223c75760983df8b) — flat
checkerboard only on mode 2, feet fix, subcell template override
(hero_track hook at $023202 -> $FD800), pacing gate (cell commits once
per 4 ticks). One fix only: in hero_track, for Buc's record in mode 2,
override the drawn X/Y so the figure slides from the old cell to the new
cell over the 4 phases (old + phase/4 * step), with the walk template's
dx/dy wobble subtracted so the motion is monotonic; the image still
cycles per phase (legs step). The slide applies only when no event
script is running ($FF0110 == 0), so the cutscene keeps the walk
template + wobble exactly as before.

The hook site $023202 is repointed from $FD800 (subcell blob) to $FDA00
(this blob, which contains the subcell template-override logic verbatim
plus the slide). The $FD800 blob bytes are left untouched (unreferenced).
The flat/checkerboard, feet fix, subcell override behaviour, and pacing
gate are untouched. Fixes both checksums, and emits the .ips
(round-trip verified) + changed-bytes.txt.

Stub addresses are parsed from the vasm listing — never hardcoded.
The base ROM and the original ROM are never modified (read-only here).
No live probes / screenshots / cadence measurements were run for this
build (Dayset's rule: he tests it himself).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-interp')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-pacing.rom'))
BASE_MD5 = '6abeec0bea66365f223c75760983df8b'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-interp.rom'))
PATCHDIR = DIR
BLOB_BASE = 0xFDA00
BLOB_END = 0xFDC00
HOOK = 0x023202
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble ---
src = f'{PATCHDIR}/source.s'
binp = f'{SCRATCH}/interp.bin'
lst = f'{SCRATCH}/interp.lst'
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
assert 'interp_hook' in addrs, 'interp_hook not found in the vasm listing'
assert 'slide_tab' in addrs, 'slide_tab not found in the vasm listing'
HOOKFN = addrs['interp_hook']
TAB = addrs['slide_tab']
print(f'interp_hook ${HOOKFN:05X}, slide_tab ${TAB:05X}')
assert HOOKFN == BLOB_BASE, f'interp_hook ${HOOKFN:05X} != ${BLOB_BASE:05X}'
assert BLOB_BASE + len(blob) <= BLOB_END, \
    f'blob ${BLOB_BASE:05X}-${BLOB_BASE+len(blob)-1:05X} overflows ${BLOB_END:05X}'
assert TAB == BLOB_BASE + len(blob) - 64, \
    f'slide_tab ${TAB:05X} != expected ${BLOB_BASE+len(blob)-64:05X} (table must be the last 64 bytes)'
# the displaced lea.l $197B0,a0 (41f9 000197b0) must be in the blob
assert bytes.fromhex('41f9000197b0') in blob, \
    'displaced lea.l $197B0,a0 not found in the blob'
# the slide table must be the last 64 bytes, dir-major N/E/S/W
tab = blob[-64:]
exp_tab = struct.pack('>32h',
    -14,8,  -11,6,  -7,4,  -4,2,      # N
    -14,-8, -11,-6, -7,-4, -4,-2,     # E
    14,-8,  11,-6,  7,-4,  4,-2,      # S
    14,8,   11,6,   7,4,   4,2)       # W
assert tab == exp_tab, 'slide table bytes do not match the expected values'

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
# the blob region must be free 0xFF padding in the base
assert all(b == 0xFF for b in rom[BLOB_BASE:BLOB_BASE + len(blob)]), \
    'blob region is not free 0xFF padding in the base'

# --- verify the hook site (exact base-ROM bytes) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

expect(HOOK, '4eb9000fd800',
       'hero_track lea.l $197B0,a0 hook site ($023202, jsr $FD800)')
expect(0x023208, '2640', 'movea.l d0,a3 ($023208)')

# --- write the blob and repoint the hook ---
rom[BLOB_BASE:BLOB_BASE+len(blob)] = blob
rom[HOOK:HOOK+6] = b'\x4e\xb9' + struct.pack('>I', HOOKFN)  # jsr interp_hook.l

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
assert fixed[HOOK:HOOK+6] == b'\x4e\xb9' + struct.pack('>I', HOOKFN)
# all differing bytes must be inside the blob, the hook site, or the two
# checksum locations (header 0x18E, runtime immediate 0xFD098)
base = open(BASE, 'rb').read()
diff_idx = [i for i in range(len(base)) if base[i] != fixed[i]]
bad = [i for i in diff_idx
       if not (BLOB_BASE <= i < BLOB_BASE + len(blob)
               or HOOK <= i < HOOK + 6
               or i in (0x18E, 0x18F)
               or 0xFD098 <= i < 0xFD09C)]
assert not bad, f'bytes changed outside the blob/hook/checksums: {[hex(i) for i in bad[:10]]}'
# every earlier blob is byte-identical to the base (flat/dither $FD400,
# feet fix $FD600, subcell $FD800, pacing $FD900)
assert fixed[0xFD400:0xFDA00] == base[0xFD400:0xFDA00], \
    'an earlier blob changed!'
# the other hook sites are untouched
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
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'interp: {len(diff)} bytes differ from rop-pacing.rom\n')
    f.write(f'interp_hook ${HOOKFN:05X}, blob ${BLOB_BASE:05X}-'
            f'${BLOB_BASE+len(blob)-1:05X} ({len(blob)} bytes), '
            f'hook site ${HOOK:05X} (repointed $FD800 -> $FDA00; '
            f'the $FD800 subcell blob is untouched)\n')
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

ips = f'{PATCHDIR}/interp.ips'
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
