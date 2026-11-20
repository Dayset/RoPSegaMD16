#!/usr/bin/env python3
"""Build rop-tall-objects-diag.rom: solid-white tall top on top of the
tall-objects ROM. Diagnosis: .blocked IS taken (43 tall calls/render)
and tall patterns survive (129 top + 31 base tiles), but the tall top
blended with land (avg lum 145.5, inside land's 127-173 range), so no
tall objects were visible. Fix: noise_tbl[8]/[9] (tall top pair) from
$BBBBBBBB/$99999999 to $FFFFFFFF/$FFFFFFFF (solid palette idx 15,
brightest in day pal 10 lum 255 and night pal 19 lum 117, never used
by land/water). The dark base is unchanged.
Base: rop-tall-objects.rom. Fixes both checksums. Emits the .ips
(round-trip verified) + changed-bytes.txt.
"""
import hashlib, os, struct, subprocess, sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
WORKTREE = REPO
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-tall-objects.rom'))
BASE_MD5 = '9846c168f559bb8acf4a14aca46623b7'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-tall-objects-diag.rom'))
PATCHDIR = DIR

os.makedirs(os.path.dirname(OUT), exist_ok=True)
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000
assert hashlib.md5(bytes(rom)).hexdigest() == BASE_MD5, 'base MD5 mismatch'
# verify the bytes we are about to change (noise_tbl[8]/[9] at $FD5D6/$FD5DA)
assert bytes(rom[0xFD5D6:0xFD5DA]) == bytes.fromhex('bbbbbbbb'), \
    f'tall top-even mismatch: {bytes(rom[0xFD5D6:0xFD5DA]).hex()}'
assert bytes(rom[0xFD5DA:0xFD5DE]) == bytes.fromhex('99999999'), \
    f'tall top-odd mismatch: {bytes(rom[0xFD5DA:0xFD5DE]).hex()}'
# the dark base must be untouched
assert bytes(rom[0xFD5DE:0xFD5E2]) == bytes.fromhex('77777777')
assert bytes(rom[0xFD5E2:0xFD5E6]) == bytes.fromhex('00000000')

rom[0xFD5D6:0xFD5DA] = bytes.fromhex('ffffffff')
rom[0xFD5DA:0xFD5DE] = bytes.fromhex('ffffffff')

open(OUT, 'wb').write(bytes(rom))
tmp = OUT + '.tmp'
r = subprocess.run([sys.executable, CHECKSUM,
                    'fix-all', OUT, tmp], check=True, capture_output=True, text=True)
print(r.stdout.strip())
os.replace(tmp, OUT)
fixed = open(OUT, 'rb').read()
print(f'diag ROM MD5: {hashlib.md5(fixed).hexdigest()}')
print(f'header checksum @0x18E: ${struct.unpack(">H", fixed[0x18E:0x190])[0]:04X}')

# --- changed bytes vs the base ROM ---
base = open(BASE, 'rb').read()
diff = [i for i in range(len(base)) if base[i] != fixed[i]]
ranges = []
for i in diff:
    if ranges and ranges[-1][1] == i:
        ranges[-1][1] = i + 1
    else:
        ranges.append([i, i + 1])
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'tall-objects-diag: {len(diff)} bytes differ from rop-tall-objects.rom\n')
    f.write('noise_tbl[8] $FD5D6 $BBBBBBBB->$FFFFFFFF, noise_tbl[9] $FD5DA $99999999->$FFFFFFFF (solid white tall top)\n')
    for a, b in ranges:
        f.write(f'  ${a:05X}-${b - 1:05X} ({b - a} bytes)\n')
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

ips = f'{PATCHDIR}/tall-objects-diag.ips'
write_ips(base, fixed, ips)
print(f'wrote {ips} ({os.path.getsize(ips)} bytes)')

# --- IPS round-trip: base + IPS == fixed ROM exactly ---
def apply_ips(orig_b, path):
    d = bytearray(orig_b)
    data = open(path, 'rb').read()
    assert data[:5] == b'PATCH', 'bad IPS header'
    p = 5
    while data[p:p + 3] != b'EOF':
        off = int.from_bytes(data[p:p + 3], 'big')
        ln = int.from_bytes(data[p + 3:p + 5], 'big')
        p += 5
        if ln == 0:  # RLE
            rlen = int.from_bytes(data[p:p + 2], 'big')
            d[off:off + rlen] = bytes([data[p + 2]]) * rlen
            p += 3
        else:
            d[off:off + ln] = data[p:p + ln]
            p += ln
    return bytes(d)

rt = apply_ips(base, ips)
assert rt == fixed, 'IPS round-trip mismatch'
print('IPS round-trip verified: base + IPS == fixed ROM')
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
print(f'ROM: {OUT}')
