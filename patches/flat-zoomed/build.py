#!/usr/bin/env python3
"""Build the flat-zoomed ROM: ONE flat ground plane for the ZOOMED view (room, mode 2) ONLY. The big world (overworld, mode 1) stays textured.

Reads the original ROM, writes the blob at $FD400, patches the 3
map_chunk_pos terrain call sites + the 8 figure-draw call sites, fixes
both checksums, and emits the .ips (round-trip verified) + changed-bytes.txt.

Stub addresses are parsed from the vasm listing — never hardcoded.
The original ROM is never modified (read-only here).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-flat-zoomed')
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-flat-zoomed.rom'))
PATCHDIR = DIR
BLOB_BASE = 0xFD400
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble ---
src = f'{PATCHDIR}/source.s'
binp = f'{SCRATCH}/flatground.bin'
lst = f'{SCRATCH}/flatground.lst'
r = subprocess.run([VASM, '-Fbin', '-L', lst, '-o', binp, src],
                   capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())
    sys.exit(f'vasm failed (rc {r.returncode})')
blob = open(binp, 'rb').read()
print(f'blob: {len(blob)} bytes')

# --- read and verify the original ROM ---
rom = bytearray(open(ORIG, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == '30c18fdbe2183f64702ae9f1a45d63f9', f'original MD5 mismatch: {md5}'
assert all(b == 0xFF for b in rom[BLOB_BASE:]), 'padding at $FD400 is not 0xFF'
assert BLOB_BASE + len(blob) <= 0x100000, 'blob overflows the ROM'

# --- parse stub addresses from the vasm listing ---
lstxt = open(lst, errors='replace').read()
addrs = {}
for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
    addrs[m.group(1)] = int(m.group(2), 16)
for name in ('flat_skip', 'flat_top', 'fig_hero', 'fig_promote',
             'fig_tile', 'fig_anim'):
    assert name in addrs, f'{name} not found in the vasm listing'
    assert BLOB_BASE <= addrs[name] < BLOB_BASE + len(blob), \
        f'{name} ${addrs[name]:05X} outside the blob'
    print(f'{name} ${addrs[name]:05X}')
SKIP = addrs['flat_skip']
TOP = addrs['flat_top']
FIG = {'hero': addrs['fig_hero'], 'promote': addrs['fig_promote'],
       'tile': addrs['fig_tile'], 'anim': addrs['fig_anim']}

# --- verify the sites to patch (exact ROM bytes, as in the original) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

expect(0x01BC1A, '4eb90000e358', 'face call site ($01BC1A jsr $E358)')
expect(0x01BC3C, '4eb90000e358', 'hidden call site ($01BC3C jsr $E358)')
expect(0x01BC84, '4eb90000e358', 'top call site ($01BC84 jsr $E358)')
expect(0x01BD98, '4eb9000231d8', 'hero_track call site $01BD98')
expect(0x01BF14, '4eb9000231d8', 'hero_track call site $01BF14')
expect(0x01BDE4, '4eb90002343a', 'map_promote_record call site $01BDE4')
expect(0x01C006, '4eb90002343a', 'map_promote_record call site $01C006')
expect(0x01BE30, '4eb9000232ac', 'map_tile_at_offset call site $01BE30')
expect(0x01C052, '4eb9000232ac', 'map_tile_at_offset call site $01C052')
expect(0x01BE7A, '4eb9000232d2', 'map_animated_tile call site $01BE7A')
expect(0x01C09C, '4eb9000232d2', 'map_animated_tile call site $01C09C')

# --- write the blob ---
rom[BLOB_BASE:BLOB_BASE+len(blob)] = blob

# --- patch the sites (jsr <stub>.l, 6 bytes each) ---
def jsr(addr, target):
    rom[addr:addr+6] = b'\x4e\xb9' + struct.pack('>I', target)

jsr(0x01BC1A, SKIP)   # face -> skip when gated
jsr(0x01BC3C, SKIP)   # hidden -> skip when gated
jsr(0x01BC84, TOP)   # top -> block fill when gated
jsr(0x01BD98, FIG['hero'])
jsr(0x01BF14, FIG['hero'])
jsr(0x01BDE4, FIG['promote'])
jsr(0x01C006, FIG['promote'])
jsr(0x01BE30, FIG['tile'])
jsr(0x01C052, FIG['tile'])
jsr(0x01BE7A, FIG['anim'])
jsr(0x01C09C, FIG['anim'])

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
assert fixed[0x01BC1A:0x01BC20] == b'\x4e\xb9' + struct.pack('>I', SKIP)
assert fixed[0x01BC3C:0x01BC42] == b'\x4e\xb9' + struct.pack('>I', SKIP)
assert fixed[0x01BC84:0x01BC8A] == b'\x4e\xb9' + struct.pack('>I', TOP)
for site, t in ((0x01BD98, FIG['hero']), (0x01BF14, FIG['hero']),
                (0x01BDE4, FIG['promote']), (0x01C006, FIG['promote']),
                (0x01BE30, FIG['tile']), (0x01C052, FIG['tile']),
                (0x01BE7A, FIG['anim']), (0x01C09C, FIG['anim'])):
    assert fixed[site:site+6] == b'\x4e\xb9' + struct.pack('>I', t), f'site ${site:05X}'
assert fixed[BLOB_BASE:BLOB_BASE+len(blob)] == blob
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == '30c18fdbe2183f64702ae9f1a45d63f9'

# --- changed-bytes.txt ---
orig = open(ORIG, 'rb').read()
diff = [(i, orig[i], fixed[i]) for i in range(len(orig)) if orig[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'flat-zoomed: {len(diff)} bytes differ from the original ROM\n')
    f.write(f'flat_skip ${SKIP:05X}, flat_top ${TOP:05X}, '
            f'fig_hero ${FIG["hero"]:05X}, fig_promote ${FIG["promote"]:05X}, '
            f'fig_tile ${FIG["tile"]:05X}, fig_anim ${FIG["anim"]:05X}, '
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

# --- .ips ---
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

ips = f'{PATCHDIR}/flat-zoomed.ips'
write_ips(orig, fixed, ips)
print(f'wrote {ips} ({os.path.getsize(ips)} bytes)')

# --- IPS round-trip: original + IPS == fixed ROM exactly ---
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

rt = apply_ips(orig, ips)
assert rt == fixed, 'IPS round-trip mismatch'
print('IPS round-trip verified: original + IPS == fixed ROM')
print(f'ROM: {OUT}')
