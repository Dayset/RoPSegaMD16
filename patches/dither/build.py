#!/usr/bin/env python3
"""Build the dither ROM: a checkerboard (dithered) pattern on the flat
ground plane, ZOOMED view (mode 2, the room) only.

Base: rop-subcell.rom (MD5 fa3255df47fe90efc6cb1c36c2e495db) — flat only
on mode 2, figures deferred to a post-pass (feet fix), subcell template
override (hero_track hook). Rebuilds the $FD400 flat blob with the
checkerboard fill (same entry points flat_skip $FD400 / flat_top $FD412,
so the existing call sites still land); the feet-fix blob ($FD600) and
subcell blob ($FD800) are untouched. Fixes both checksums, and emits the
.ips (round-trip verified) + changed-bytes.txt.

Stub addresses are parsed from the vasm listing — never hardcoded.
The base ROM and the original ROM are never modified (read-only here).
No live probes / screenshots / cadence measurements were run for this
build (Dayset's rule: he tests it himself).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-dither')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-subcell.rom'))
BASE_MD5 = 'fa3255df47fe90efc6cb1c36c2e495db'
FLATZOOMED = os.environ.get('ROP_FLATZOOMED', os.path.join(REPO, 'build', 'rop-flat-zoomed.rom'))
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-dither.rom'))
PATCHDIR = DIR
BLOB_BASE = 0xFD400
BLOB_END = 0xFD600
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble ---
src = f'{PATCHDIR}/source.s'
binp = f'{SCRATCH}/dither.bin'
lst = f'{SCRATCH}/dither.lst'
r = subprocess.run([VASM, '-Fbin', '-L', lst, '-o', binp, src],
                   capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())
    sys.exit(f'vasm failed (rc {r.returncode})')
blob = open(binp, 'rb').read()
print(f'blob: {len(blob)} bytes')

# --- parse stub addresses from the vasm listing ---
lstxt = open(lst, errors='replace').read()
addrs = {}
for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
    addrs[m.group(1)] = int(m.group(2), 16)
for name in ('flat_skip', 'flat_top', 'fig_hero', 'fig_promote',
             'fig_tile', 'fig_anim', 'water_tbl'):
    assert name in addrs, f'{name} not found in the vasm listing'
    assert BLOB_BASE <= addrs[name] < BLOB_BASE + len(blob), \
        f'{name} ${addrs[name]:05X} outside the blob'
    print(f'{name} ${addrs[name]:05X}')
SKIP = addrs['flat_skip']
TOP = addrs['flat_top']
# Entry points must be unchanged so the existing call sites still land.
assert SKIP == 0xFD400, f'flat_skip ${SKIP:05X} != $FD400'
assert TOP == 0xFD412, f'flat_top ${TOP:05X} != $FD412'
assert BLOB_BASE + len(blob) <= BLOB_END, \
    f'blob ${BLOB_BASE:05X}-{BLOB_BASE+len(blob)-1:05X} overflows into $FD600'

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
# the $FD400 blob in the base must be the flat-zoomed blob
fz = open(FLATZOOMED, 'rb').read()
assert rom[BLOB_BASE:BLOB_END] == fz[BLOB_BASE:BLOB_END], \
    'base $FD400 blob is not the flat-zoomed blob'
# the new blob extends 12 bytes past the old 496-byte blob; that region
# ($FD5F0-$FD600) must be free 0xFF padding in the base
assert all(b == 0xFF for b in rom[BLOB_BASE+496:BLOB_END]), \
    'padding after the old blob is not 0xFF'

# --- verify the sites to patch (exact base-ROM bytes) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

expect(0x01BC1A, '4eb9000fd400', 'face call site ($01BC1A jsr flat_skip)')
expect(0x01BC3C, '4eb9000fd400', 'hidden call site ($01BC3C jsr flat_skip)')
expect(0x01BC84, '4eb9000fd412', 'top call site ($01BC84 jsr flat_top)')

# --- write the blob (overwrites the old $FD400 blob in place) ---
rom[BLOB_BASE:BLOB_BASE+len(blob)] = blob

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
assert fixed[0x01BC1A:0x01BC20] == b'\x4e\xb9' + struct.pack('>I', SKIP)
assert fixed[0x01BC3C:0x01BC42] == b'\x4e\xb9' + struct.pack('>I', SKIP)
assert fixed[0x01BC84:0x01BC8A] == b'\x4e\xb9' + struct.pack('>I', TOP)
# the feet-fix blob ($FD600), subcell blob ($FD800) and everything else
# must be untouched: all differing bytes must be inside $FD400-$FD600
# or the two checksum locations (header 0x18E, runtime immediate 0xFD098)
base = open(BASE, 'rb').read()
diff_idx = [i for i in range(len(base)) if base[i] != fixed[i]]
bad = [i for i in diff_idx
       if not (BLOB_BASE <= i < BLOB_END or i in (0x18E, 0x18F)
               or 0xFD098 <= i < 0xFD09C)]
assert not bad, f'bytes changed outside the blob/checksums: {[hex(i) for i in bad[:10]]}'
# the feet-fix and subcell blobs are byte-identical to the base
assert fixed[0xFD600:0xFD800] == base[0xFD600:0xFD800], 'feet-fix blob changed!'
assert fixed[0xFD800:0xFD900] == base[0xFD800:0xFD900], 'subcell blob changed!'
# the hero_track subcell hook site is untouched
assert fixed[0x023202:0x023208] == base[0x023202:0x023208]
assert fixed[0x01C0D6:0x01C0DC] == base[0x01C0D6:0x01C0DC]  # fig_replay hook
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'dither: {len(diff)} bytes differ from rop-subcell.rom\n')
    f.write(f'flat_skip ${SKIP:05X}, flat_top ${TOP:05X}, '
            f'blob ${BLOB_BASE:05X}-{BLOB_BASE+len(blob)-1:05X} ({len(blob)} bytes)\n')
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

ips = f'{PATCHDIR}/dither.ips'
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
