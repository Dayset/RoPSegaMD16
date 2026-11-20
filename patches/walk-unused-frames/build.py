#!/usr/bin/env python3
"""Build the walk-unused-frames ROM: cutscene Y fix on top of the
walk-frames-fix ROM.

Base: rop-walk-frames-fix.rom (MD5 9ba279759436b96a732d11d9a3f6be0d) —
flat only on mode 2, feet fix, cutscene loop-walk, frame doubling
(one cell per 8 ticks) + Y-shift hook routed through
map_promote_record ($023480) and hero_track ($023202), blob $FDA00.

Dayset's correction: the unused poses (offsets 4, 5, 10, 11, 12, 13)
are NOT walk frames — they are combat moves / a cast. Verified from
the ROM template table $197B0: offsets 4, 5, 10, 11, 12, 13 are used
by templates 16-27 (the combat/cast templates); the walk templates
36-55 use only offsets 0, 1, 6, 7, 8, 9, 14, 15; ALL 16 offsets are
used by some template 0-55. There are no unused walk-frame poses.
The unused-poses idea is dropped; this patch is the cutscene Y fix
only. No combat/cast pose is fitted into the walk routine.

Dayset's playtest of the fix ROM: "cutscene Y is completely off.
He is doing 2 steps and then waiting for longer than usual and
jumps screen, and repeat. Like he is waiting and running after
2 cells." The zoom walk on this ROM is very good (walks even better
than interp-fix2, no yoinks, movement begins with 1-2 presses) and
does not use the loop driver or the Y-shift hook (both are gated to
the cutscene), so this fix cannot break it.

The fix (three byte changes, no new blob):
  1. $023202 (hero_track): jsr $FDA00.l -> lea.l $197B0,a0
     (restore the original figure-draw entry).
  2. $023480 (map_promote_record): jsr $FDA00.l -> lea.l $197B0,a0
     (restore the original figure-draw entry; this is the routine
     Buc is actually drawn through).
     The $FDA00 walk-hook blob becomes dead code (unreferenced).
     Left in place (0xFF padding region, outside the runtime
     checksum range) — harmless, patch stays reversible.
  3. $FD866 (loop_drive): beq.b $FD86A -> bra.b $FD88A
     (always step Buc on every sys_event_run call; the .half
     non-step block becomes dead code, walk_half stays 0).
     Restores the original cutscene-loop cadence: one cell per
     4 ticks instead of one cell per 8 ticks.
After the fix the cutscene walk is the cutscene-loop walk (which
Dayset already saw working): Buc walks the loop S,E,N,W, turning
when blocked or after 20 steps, at 4 ticks/cell, with no Y shift.
The world shift is still jumpy (integer-cell camera) — that is the
big rework, not this fix.

The base ROM and the original ROM are never modified (read-only here).
"""
import hashlib, struct, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-walk-unused-frames')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-walk-frames-fix.rom'))
BASE_MD5 = '9ba279759436b96a732d11d9a3f6be0d'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-walk-unused-frames.rom'))
PATCHDIR = DIR

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- patch bytes (encodings verified with vasm before building) ---
# lea.l $197B0,a0 = 41F9 000197B0 ; bra.b $FD88A from $FD866 = 60 22
LEA = bytes.fromhex('41f9000197b0')
BRA = bytes.fromhex('6022')

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
print(f'base ROM MD5 verified: {md5}')

# --- verify the three sites to patch (exact base-ROM bytes) ---
got = bytes(rom[0x023202:0x023208]).hex()
assert got == '4eb9000fda00', \
    f'hero_track $023202: got {got}, want 4eb9000fda00 (jsr $FDA00.l)'
print('site $023202 verified: jsr $FDA00.l (hero_track hook)')
got = bytes(rom[0x023480:0x023486]).hex()
assert got == '4eb9000fda00', \
    f'map_promote_record $023480: got {got}, want 4eb9000fda00 (jsr $FDA00.l)'
print('site $023480 verified: jsr $FDA00.l (map_promote_record hook)')
got = bytes(rom[0x0FD866:0x0FD868]).hex()
assert got == '6702', \
    f'loop_drive $FD866: got {got}, want 6702 (beq.b $FD86A)'
print('site $FD866 verified: beq.b $FD86A (walk_half non-step branch)')
# the walk_half gating around it must match the disassembly
assert bytes(rom[0x0FD860:0x0FD866]).hex() == '4a7900ffd104', \
    'loop_drive $FD860: tst.w $FFD104.l not found'
assert bytes(rom[0x0FD868:0x0FD86A]).hex() == '6020', \
    'loop_drive $FD868: bra.b $FD88A not found'
assert bytes(rom[0x0FD86A:0x0FD876]).hex() == '33fc000100ffd1046000008e', \
    'loop_drive .half block not found'
print('loop_drive walk_half gating verified ($FD860-$FD875)')

# --- verify the walk-hook blob is intact at $FDA00 (now dead code) ---
blob = bytes(rom[0xFDA00:0xFDA00+196])
assert blob[:4] == bytes.fromhex('48e770e0'), \
    f'blob start: got {blob[:4].hex()}, want 48e770e0 (movem.l d1-d3/a0-a2,-(a7))'
assert blob[170:178] == bytes.fromhex('41f9000197b04e75'), \
    f'blob displaced lea+rts at $FDAAA: got {blob[170:178].hex()}'
print('walk-hook blob intact at $FDA00 (left in place, now unreferenced)')

# --- apply the three changes ---
rom[0x023202:0x023208] = LEA
rom[0x023480:0x023486] = LEA
rom[0x0FD866:0x0FD868] = BRA

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
assert fixed[0x023202:0x023208] == LEA, 'patch did not land at $023202'
assert fixed[0x023480:0x023486] == LEA, 'patch did not land at $023480'
assert fixed[0x0FD866:0x0FD868] == BRA, 'patch did not land at $FD866'
print('all three patch sites verified in the fixed ROM')
# the walk-hook blob, flat, feet-fix, and loop blobs must be
# byte-identical to the base (only the 2-byte branch inside the
# loop blob changes, plus the two hook sites and the checksums)
base = open(BASE, 'rb').read()
assert fixed[0xFDA00:0xFDA00+196] == base[0xFDA00:0xFDA00+196], \
    'walk-hook blob changed!'
assert fixed[0xFD400:0xFD800] == base[0xFD400:0xFD800], \
    'flat / feet-fix blobs changed!'
assert fixed[0xFD800:0xFD866] == base[0xFD800:0xFD866], \
    'loop blob changed before $FD866!'
assert fixed[0xFD868:0xFDA00] == base[0xFD868:0xFDA00], \
    'loop blob changed after $FD868!'
assert fixed[0xFDAC4:0x100000] == base[0xFDAC4:0x100000], \
    'bytes past the hook blob changed!'
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5, \
    'original ROM changed!'
assert hashlib.md5(base).hexdigest() == BASE_MD5, 'base ROM changed!'

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'walk-unused-frames: {len(diff)} bytes differ from rop-walk-frames-fix.rom\n')
    f.write('$023202 (hero_track): jsr $FDA00.l -> lea.l $197B0,a0 '
            '(Y-shift hook off)\n')
    f.write('$023480 (map_promote_record): jsr $FDA00.l -> lea.l $197B0,a0 '
            '(Y-shift hook off)\n')
    f.write('$FD866 (loop_drive): beq.b $FD86A -> bra.b $FD88A '
            '(step every call: one cell per 4 ticks, not 8)\n')
    f.write('The $FDA00 walk-hook blob is left in place, now unreferenced.\n')
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

ips = f'{PATCHDIR}/walk-unused-frames.ips'
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
