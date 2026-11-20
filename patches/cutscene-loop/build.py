#!/usr/bin/env python3
"""Build the cutscene-loop ROM: drive Buc in a loop during the Buc cutscene
(script $1A228, location 156) so Dayset can see the walk from all four
directions.

Base: rop-flat-zoomed-feet.rom (MD5 9373c0d01cf08c20f28e256daa9ea142) —
flat only on mode 2, feet fix. Reads it, writes the new blob at $FD800,
hooks sys_event_run ($02D56E) to the loop driver and the op-5 handler
($02D7F6) to the Buc-move suppressor, fixes both checksums, and emits
the .ips (round-trip verified) + changed-bytes.txt.

The room (chunk 233) is a 32x32 maze: a 20x20 square loop from Buc's
start (6,17) does NOT fit (south runs out of bounds at Y=37; the largest
fitting rectangle is 7x2). So the driver walks up to 20 cells per leg in
the order S,E,N,W and turns when blocked (wall/student) or after 20
steps; the loop repeats while the cutscene is active.

Entry addresses are parsed from the vasm listing — never hardcoded.
The base ROM and the original ROM are never modified (read-only here).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-cutscene-loop')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-flat-zoomed-feet.rom'))
BASE_MD5 = '9373c0d01cf08c20f28e256daa9ea142'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-cutscene-loop.rom'))
PATCHDIR = DIR
BLOB_BASE = 0xFD800
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- assemble ---
src = f'{PATCHDIR}/source.s'
binp = f'{SCRATCH}/loop.bin'
lst = f'{SCRATCH}/loop.lst'
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
assert all(b == 0xFF for b in rom[BLOB_BASE:BLOB_BASE + 0x800]), \
    'padding at $FD800 is not 0xFF'
assert BLOB_BASE + len(blob) <= 0x100000, 'blob overflows the ROM'

# --- parse entry addresses from the vasm listing ---
lstxt = open(lst, errors='replace').read()
addrs = {}
for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
    addrs[m.group(1)] = int(m.group(2), 16)
for name in ('loop_drive', 'loop_op5'):
    assert name in addrs, f'{name} not found in the vasm listing'
    assert BLOB_BASE <= addrs[name] < BLOB_BASE + len(blob), \
        f'{name} ${addrs[name]:05X} outside the blob'
    print(f'{name} ${addrs[name]:05X}')
DRIVE = addrs['loop_drive']
OP5 = addrs['loop_op5']

# --- verify the sites to patch (exact base-ROM bytes) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

# sys_event_run $02D56E: tst.w $FF010A.l (6 bytes; opcode 0x4A79, abs long)
expect(0x02D56E, '4a7900ff010a', 'sys_event_run $02D56E tst.w $FF010A.l')
# op-5 handler $02D7F6: jsr combat_move_unit.l (6 bytes)
expect(0x02D7F6, '4eb900024984', 'op-5 handler $02D7F6 jsr combat_move_unit.l')

# --- write the blob ---
rom[BLOB_BASE:BLOB_BASE+len(blob)] = blob

# --- patch the sites (jsr <entry>.l, 6 bytes each) ---
def jsr(addr, target):
    rom[addr:addr+6] = b'\x4e\xb9' + struct.pack('>I', target)

jsr(0x02D56E, DRIVE)  # sys_event_run entry -> loop driver, then tst
jsr(0x02D7F6, OP5)    # op-5 handler -> suppress Buc's scripted moves

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
assert fixed[BLOB_BASE:BLOB_BASE+len(blob)] == blob
# the flat + feet-fix blobs and their hook sites must be untouched
base = open(BASE, 'rb').read()
assert fixed[0xFD400:0xFD800] == base[0xFD400:0xFD800], \
    'flat-zoomed / feet-fix blob changed!'
assert fixed[0x01C0D6:0x01C0DC] == base[0x01C0D6:0x01C0DC]
assert fixed[0x01BD98:0x01BD9E] == base[0x01BD98:0x01BD9E]
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'cutscene-loop: {len(diff)} bytes differ from rop-flat-zoomed-feet.rom\n')
    f.write(f'loop_drive ${DRIVE:05X}, loop_op5 ${OP5:05X}, '
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

ips = f'{PATCHDIR}/cutscene-loop.ips'
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
