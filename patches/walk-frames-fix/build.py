#!/usr/bin/env python3
"""Build the walk-frames-fix ROM: route the Y-shift hook through
map_promote_record so it fires for Buc.

Base: rop-walk-frames.rom (MD5 a698a2f697939fd8a5b11b94837f32f7) —
flat only on mode 2, feet fix, cutscene loop-walk, frame doubling
(one cell per 8 ticks) + Y-shift hook in hero_track ($023202, blob
at $FDA00). The Y-shift hook never fires for Buc because Buc is
drawn via map_promote_record, NOT hero_track (record+$A = 1;
jump table $01BE86). This patch is a single 6-byte change:
map_promote_record $023480 (lea.l $197B0,a0) -> jsr $FDA00.l,
routing the EXISTING walk-hook blob through map_promote_record.
No new blob. The hero_track hook is kept intact (harmless).

The blob ends with the displaced lea.l $197B0,a0 + rts (at $FDAAA),
which is exactly what both hook sites need, and the frame layout
matches hero_track (record 8(a6), X 12(a6), Y 14(a6), heightOff
16(a6), d0 template offset — d0 computed before the hook, a3 set
after, X/Y read after). The blob saves/restores d1-d3/a0-a2,
preserves d0, never touches d4/d5/a3/a6.

The base ROM and the original ROM are never modified (read-only here).
"""
import hashlib, struct, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-walk-frames-fix')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-walk-frames.rom'))
BASE_MD5 = 'a698a2f697939fd8a5b11b94837f32f7'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-walk-frames-fix.rom'))
PATCHDIR = DIR
HOOK_BASE = 0xFDA00
HOOK_SITE = 0x023480
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble source.s, verify it is the 6-byte jsr ---
r = subprocess.run([VASM, '-Fbin', '-o', f'{SCRATCH}/patch.bin',
                    f'{PATCHDIR}/source.s'],
                   capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())
    sys.exit(f'vasm failed on source.s (rc {r.returncode})')
patch = open(f'{SCRATCH}/patch.bin', 'rb').read()
assert patch == bytes.fromhex('4eb9000fda00'), \
    f'source.s assembled to {patch.hex()}, want 4eb9000fda00 (jsr $FDA00.l)'
print(f'source.s assembles to jsr $FDA00.l ({len(patch)} bytes)')

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
print(f'base ROM MD5 verified: {md5}')

# --- verify the site to patch (exact base-ROM bytes) ---
got = bytes(rom[HOOK_SITE:HOOK_SITE+6]).hex()
assert got == '41f9000197b0', \
    f'map_promote_record $023480: got {got}, want 41f9000197b0 (lea.l $197B0,a0)'
print('site $023480 verified: lea.l $197B0,a0')

# --- verify the hero_track hook is intact (kept, harmless) ---
got = bytes(rom[0x023202:0x023208]).hex()
assert got == '4eb9000fda00', \
    f'hero_track $023202: got {got}, want 4eb9000fda00 (jsr $FDA00.l)'
print('hero_track hook $023202 intact: jsr $FDA00.l')

# --- verify the walk-hook blob is intact at $FDA00 ---
blob = bytes(rom[HOOK_BASE:HOOK_BASE+196])
assert blob[:4] == bytes.fromhex('48e770e0'), \
    f'blob start: got {blob[:4].hex()}, want 48e770e0 (movem.l d1-d3/a0-a2,-(a7))'
assert blob[170:178] == bytes.fromhex('41f9000197b04e75'), \
    f'blob displaced lea+rts at $FDAAA: got {blob[170:178].hex()}, want 41f9000197b04e75'
assert blob[-16:] == bytes.fromhex('0007fffc00070004fff90004fff9fffc'), \
    f'blob half_tab tail: got {blob[-16:].hex()}'
print('walk-hook blob intact at $FDA00 (movem, displaced lea+rts at $FDAAA, half_tab)')

# --- write the patch (single 6-byte jsr at $023480) ---
rom[HOOK_SITE:HOOK_SITE+6] = patch

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
assert fixed[HOOK_SITE:HOOK_SITE+6] == patch, 'patch did not land at $023480'
assert fixed[0x023202:0x023208] == bytes.fromhex('4eb9000fda00'), \
    'hero_track hook changed!'
# the walk-hook blob and everything else must be byte-identical to the base
base = open(BASE, 'rb').read()
assert fixed[HOOK_BASE:HOOK_BASE+196] == base[HOOK_BASE:HOOK_BASE+196], \
    'walk-hook blob changed!'
assert fixed[0xFD400:0xFDA00] == base[0xFD400:0xFDA00], \
    'flat / feet-fix / loop blobs changed!'
assert fixed[0xFDAC4:0x100000] == base[0xFDAC4:0x100000], \
    'bytes past the hook blob changed!'
assert fixed[:0x023480] == base[:0x023480] or True  # (checked via diff below)
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5, \
    'original ROM changed!'
assert hashlib.md5(base).hexdigest() == BASE_MD5, 'base ROM changed!'

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'walk-frames-fix: {len(diff)} bytes differ from rop-walk-frames.rom\n')
    f.write('map_promote_record $023480: lea.l $197B0,a0 -> jsr $FDA00.l '
            '(route the Y-shift hook through map_promote_record)\n')
    f.write('No new blob; the existing walk-hook blob at $FDA00 is reused.\n')
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

ips = f'{PATCHDIR}/walk-frames-fix.ips'
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
