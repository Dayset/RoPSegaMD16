#!/usr/bin/env python3
"""Build the pacing ROM: a pacing gate that makes the subcell movement
visible in the B-zoom view (mode 2, the room).

Base: rop-dither.rom (MD5 09d74baa339314b40e02344545f67f66) — flat
checkerboard only on mode 2, feet fix (figures deferred to a post-pass),
subcell template override (hero_track hook). One fix only: a hook in
combat_turn_run Path A at $0228CC gates the leader-queue move on
grid+$A == 0, so Buc's cell commits once per 4 ticks (phase 3->0 wrap)
instead of every tick. The flat/checkerboard, the feet fix, and the
subcell override are untouched. Fixes both checksums, and emits the .ips
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
SCRATCH = os.path.join(REPO, 'build', 'scratch-pacing')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-dither.rom'))
BASE_MD5 = '09d74baa339314b40e02344545f67f66'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-pacing.rom'))
PATCHDIR = DIR
BLOB_BASE = 0xFD900
BLOB_END = 0xFD980
HOOK = 0x0228CC
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble ---
src = f'{PATCHDIR}/source.s'
binp = f'{SCRATCH}/pacing.bin'
lst = f'{SCRATCH}/pacing.lst'
r = subprocess.run([VASM, '-Fbin', '-L', lst, '-o', binp, src],
                   capture_output=True, text=True)
print(r.stdout.strip())
if r.returncode != 0:
    print(r.stderr.strip())
    sys.exit(f'vasm failed (rc {r.returncode})')
blob = open(binp, 'rb').read()
print(f'blob: {len(blob)} bytes')

# --- parse the blob address from the vasm listing ---
lstxt = open(lst, errors='replace').read()
addrs = {}
for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
    addrs[m.group(1)] = int(m.group(2), 16)
assert 'pace_gate' in addrs, 'pace_gate not found in the vasm listing'
GATE = addrs['pace_gate']
print(f'pace_gate ${GATE:05X}')
assert GATE == BLOB_BASE, f'pace_gate ${GATE:05X} != ${BLOB_BASE:05X}'
assert BLOB_BASE + len(blob) <= BLOB_END, \
    f'blob ${BLOB_BASE:05X}-{BLOB_BASE+len(blob)-1:05X} overflows ${BLOB_END:05X}'
# the displaced cmpi.w #$4,-$E(a6) (0c6e 0004 fff2) must be in the blob
assert bytes.fromhex('0c6e0004fff2') in blob, \
    'displaced cmpi.w not found in the blob'
# the skip target must be the $022960 block exit
assert bytes.fromhex('4ef900022960') in blob, \
    'jmp $022960 not found in the blob'

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

expect(HOOK, '0c6e0004fff2',
       'Path A cmpi.w #$4,-$E(a6) ($0228CC)')
expect(0x0228D2, '6700008c', 'beq.w L022960 ($0228D2)')
expect(0x022960, '6010', 'bra.b L022972 ($022960)')

# --- write the blob and the hook ---
rom[BLOB_BASE:BLOB_BASE+len(blob)] = blob
rom[HOOK:HOOK+6] = b'\x4e\xb9' + struct.pack('>I', GATE)  # jsr pace_gate.l

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
assert fixed[HOOK:HOOK+6] == b'\x4e\xb9' + struct.pack('>I', GATE)
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
# the flat/dither blob ($FD400-$FD600), feet-fix blob ($FD600-$FD800) and
# subcell blob ($FD800-$FD8DE) are byte-identical to the base
assert fixed[0xFD400:0xFD8DE] == base[0xFD400:0xFD8DE], \
    'an earlier blob changed!'
# the other hook sites are untouched
assert fixed[0x023202:0x023208] == base[0x023202:0x023208], \
    'subcell hero_track hook site changed!'
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
    f.write(f'pacing: {len(diff)} bytes differ from rop-dither.rom\n')
    f.write(f'pace_gate ${GATE:05X}, blob ${BLOB_BASE:05X}-'
            f'${BLOB_BASE+len(blob)-1:05X} ({len(blob)} bytes), '
            f'hook site ${HOOK:05X}\n')
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

ips = f'{PATCHDIR}/pacing.ips'
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
