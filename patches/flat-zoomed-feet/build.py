#!/usr/bin/env python3
"""Build the flat-zoomed-feet ROM: draw figures AFTER all terrain fills, so
Buc's feet are not covered by the flat fill.

Base: the re-gated flat ROM (rop-flat-zoomed.rom, MD5
4ee66e521ac9a636d2167c0d55409d92) — flat only on mode 2. Reads it, writes
the new blob at $FD600, repoints the 8 figure-draw call sites in
map_chunk_pos to the new record stubs, hooks the end of map_chunk_pos
($01C0D6) to the replay routine, fixes both checksums, and emits the .ips
(round-trip verified) + changed-bytes.txt.

Stub addresses are parsed from the vasm listing — never hardcoded.
The base ROM and the original ROM are never modified (read-only here).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-flat-zoomed-feet')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-flat-zoomed.rom'))
BASE_MD5 = '4ee66e521ac9a636d2167c0d55409d92'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-flat-zoomed-feet.rom'))
PATCHDIR = DIR
BLOB_BASE = 0xFD600
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble ---
src = f'{PATCHDIR}/source.s'
binp = f'{SCRATCH}/feet.bin'
lst = f'{SCRATCH}/feet.lst'
r = subprocess.run([VASM, '-Fbin', '-L', lst, '-o', binp, src],
                   capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())
    sys.exit(f'vasm failed (rc {r.returncode})')
blob = open(binp, 'rb').read()
print(f'blob: {len(blob)} bytes')

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
assert all(b == 0xFF for b in rom[BLOB_BASE:]), 'padding at $FD600 is not 0xFF'
assert BLOB_BASE + len(blob) <= 0x100000, 'blob overflows the ROM'

# --- parse stub addresses from the vasm listing ---
lstxt = open(lst, errors='replace').read()
addrs = {}
for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
    addrs[m.group(1)] = int(m.group(2), 16)
for name in ('fig_hero', 'fig_promote', 'fig_tile', 'fig_anim', 'fig_replay'):
    assert name in addrs, f'{name} not found in the vasm listing'
    assert BLOB_BASE <= addrs[name] < BLOB_BASE + len(blob), \
        f'{name} ${addrs[name]:05X} outside the blob'
    print(f'{name} ${addrs[name]:05X}')
HERO = addrs['fig_hero']
PROMOTE = addrs['fig_promote']
TILE = addrs['fig_tile']
ANIM = addrs['fig_anim']
REPLAY = addrs['fig_replay']

# --- verify the sites to patch (exact base-ROM bytes) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

# end of map_chunk_pos: tst.w $FF013C.l (6 bytes)
expect(0x01C0D6, '4a7900ff013c', 'map_chunk_pos tail ($01C0D6 tst.w $FF013C.l)')
# figure call sites: currently jsr to the flat-zoomed blob stubs
# ($FD560 hero, $FD574 promote, $FD588 tile, $FD59C anim)
expect(0x01BD98, '4eb9000fd560', 'hero_track call site $01BD98')
expect(0x01BF14, '4eb9000fd560', 'hero_track call site $01BF14')
expect(0x01BDE4, '4eb9000fd574', 'map_promote_record call site $01BDE4')
expect(0x01C006, '4eb9000fd574', 'map_promote_record call site $01C006')
expect(0x01BE30, '4eb9000fd588', 'map_tile_at_offset call site $01BE30')
expect(0x01C052, '4eb9000fd588', 'map_tile_at_offset call site $01C052')
expect(0x01BE7A, '4eb9000fd59c', 'map_animated_tile call site $01BE7A')
expect(0x01C09C, '4eb9000fd59c', 'map_animated_tile call site $01C09C')

# --- write the blob ---
rom[BLOB_BASE:BLOB_BASE+len(blob)] = blob

# --- patch the sites (jsr <stub>.l, 6 bytes each) ---
def jsr(addr, target):
    rom[addr:addr+6] = b'\x4e\xb9' + struct.pack('>I', target)

jsr(0x01C0D6, REPLAY)  # end of map_chunk_pos -> replay figures, then tst
jsr(0x01BD98, HERO)
jsr(0x01BF14, HERO)
jsr(0x01BDE4, PROMOTE)
jsr(0x01C006, PROMOTE)
jsr(0x01BE30, TILE)
jsr(0x01C052, TILE)
jsr(0x01BE7A, ANIM)
jsr(0x01C09C, ANIM)

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
assert fixed[0x01C0D6:0x01C0DC] == b'\x4e\xb9' + struct.pack('>I', REPLAY)
for site, t in ((0x01BD98, HERO), (0x01BF14, HERO),
                (0x01BDE4, PROMOTE), (0x01C006, PROMOTE),
                (0x01BE30, TILE), (0x01C052, TILE),
                (0x01BE7A, ANIM), (0x01C09C, ANIM)):
    assert fixed[site:site+6] == b'\x4e\xb9' + struct.pack('>I', t), f'site ${site:05X}'
assert fixed[BLOB_BASE:BLOB_BASE+len(blob)] == blob
# the flat-zoomed terrain stubs + blob must be untouched
base = open(BASE, 'rb').read()
assert fixed[0xFD400:0xFD600] == base[0xFD400:0xFD600], 'flat-zoomed blob changed!'
assert fixed[0x01BC1A:0x01BC20] == base[0x01BC1A:0x01BC20]
assert fixed[0x01BC3C:0x01BC42] == base[0x01BC3C:0x01BC42]
assert fixed[0x01BC84:0x01BC8A] == base[0x01BC84:0x01BC8A]
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'flat-zoomed-feet: {len(diff)} bytes differ from rop-flat-zoomed.rom\n')
    f.write(f'fig_hero ${HERO:05X}, fig_promote ${PROMOTE:05X}, '
            f'fig_tile ${TILE:05X}, fig_anim ${ANIM:05X}, '
            f'fig_replay ${REPLAY:05X}, '
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

ips = f'{PATCHDIR}/flat-zoomed-feet.ips'
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
