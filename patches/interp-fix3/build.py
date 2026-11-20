#!/usr/bin/env python3
"""Build the interp-fix3 ROM: no camera yoink on a direction change, and a
single short press rotates Buc's face after a stop.

Base: rop-interp-fix2.rom (MD5 30233662e411ecf0046ffc43c734c971) — flat
checkerboard (mode 2), feet fix, subcell template override, pacing gate
(1 cell / 4 ticks), interpolation slide (room-relative, via
map_promote_record), camera mode-6 with a 3-cell dead zone. Dayset's
playtest: holding a direction walks beautifully (smooth, subcell), but
(1) the camera YOINKS on a direction change, and (2) after stopping it
takes 3-4 short presses just to rotate his face.

One fix only (two halves of the same direction-change problem):
A. CAMERA: hook world_reposition_leader's L025294 dead-zone block at
   $02529C (sub.w $FF0E8E,d0, 6 bytes) -> jsr $FDE00.l. The new blob
   makes the snap PER-AXIS: an axis that has not crossed the 3-cell
   dead zone keeps the current camera on that axis; only the axis that
   crossed moves to Buc's cell. A north turn after walking east now
   moves the camera purely north instead of diagonally. Gated to mode 2
   AND no script, so the cutscene keeps the original snap. The blob
   jumps to the clamp at $025300; the clamp + leader_spawn(mode 6)
   call run exactly as before on the per-axis target.
B. FACE: replace the v1 pacing blob at $FD900 in place (same address;
   the $0228CC hook already points there, no hook-site change). The v2
   blob adds a turn check BEFORE the phase gate: if the popped
   direction (-$E(a6)) differs from Buc's heading ($FF02F2), the move
   goes through immediately (turn), no phase check. Same-direction
   moves keep the v1 phase gate, so the walk pace (1 cell / 4 ticks)
   and the slide are unchanged. The dir==4 stop sentinel still works
   (it takes the allow path, the displaced cmpi sets the flags, Path
   A's beq skips the move).

The flat / checkerboard, feet fix, subcell override, interp slide, and
map_promote_record hook are byte-identical to the base. Big world stays
textured. Cell rate unchanged (1 cell / 4 ticks). Cutscene unchanged
(the camera blob is gated off while a script runs; the pacing turn
check never fires during a script because the movement block is
skipped while $FF0110 != 0). Fixes both checksums, emits the .ips
(round-trip verified) + changed-bytes.txt.

Blob addresses are parsed from the vasm listings — never hardcoded.
The base ROM and the original ROM are never modified (read-only here).
No live probes / screenshots / cadence measurements were run for this
build (Dayset's rule: he tests it himself).
"""
import hashlib, struct, re, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-interp-fix3')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-interp-fix2.rom'))
BASE_MD5 = '30233662e411ecf0046ffc43c734c971'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-interp-fix3.rom'))
PATCHDIR = DIR
PACE_BASE = 0xFD900
PACE_END = 0xFDA00      # exclusive; the interp blob starts at $FDA00
CAM_BASE = 0xFDE00
CAM_END = 0xFDE7C        # exclusive; 124 bytes (the old camdelay region)
HOOK_CAM = 0x02529C      # L025294 dead-zone block: sub.w $FF0E8E,d0
HOOK_PACE = 0x0228CC     # Path A pacing gate (already jsr $FD900.l)
VASM = os.environ.get('ROP_VASM', os.path.join(REPO, 'tools', 'vasm', 'vasmm68k_mot'))

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

def assemble(src, binp, lst):
    r = subprocess.run([VASM, '-Fbin', '-L', lst, '-o', binp, src],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip())
        sys.exit(f'vasm failed for {src} (rc {r.returncode})')
    return open(binp, 'rb').read()

def parse_addrs(lst, names):
    lstxt = open(lst, errors='replace').read()
    addrs = {}
    for m in re.finditer(r'^(\w+)\s+A:([0-9A-Fa-f]{8})\s*$', lstxt, re.M):
        addrs[m.group(1)] = int(m.group(2), 16)
    for n in names:
        assert n in addrs, f'{n} not found in the vasm listing {lst}'
    return addrs

# --- assemble both blobs ---
pace_blob = assemble(f'{PATCHDIR}/pace.s', f'{SCRATCH}/pace.bin',
                     f'{SCRATCH}/pace.lst')
pace_addrs = parse_addrs(f'{SCRATCH}/pace.lst', ('pace_gate',))
GATE = pace_addrs['pace_gate']
print(f'pace_gate ${GATE:05X}, pace blob: {len(pace_blob)} bytes')
assert GATE == PACE_BASE, f'pace_gate ${GATE:05X} != ${PACE_BASE:05X}'
assert PACE_BASE + len(pace_blob) <= PACE_END, \
    f'pace blob ${PACE_BASE:05X}-{PACE_BASE+len(pace_blob)-1:05X} overflows ${PACE_END:05X}'
# the displaced cmpi.w #$4,-$E(a6) (0c6e 0004 fff2) must be in the blob
assert bytes.fromhex('0c6e0004fff2') in pace_blob, \
    'displaced cmpi.w not found in the pace blob'
# the skip target must be the $022960 block exit
assert bytes.fromhex('4ef900022960') in pace_blob, \
    'jmp $022960 not found in the pace blob'
# the turn check must read Buc's heading ($FF02F2)
assert bytes.fromhex('323900ff02f2') in pace_blob, \
    'move.w $FF02F2,d1 (Buc heading) not found in the pace blob'

cam_blob = assemble(f'{PATCHDIR}/camsnap.s', f'{SCRATCH}/camsnap.bin',
                    f'{SCRATCH}/camsnap.lst')
cam_addrs = parse_addrs(f'{SCRATCH}/camsnap.lst', ('cam_snap',))
SNAP = cam_addrs['cam_snap']
print(f'cam_snap ${SNAP:05X}, cam blob: {len(cam_blob)} bytes')
assert SNAP == CAM_BASE, f'cam_snap ${SNAP:05X} != ${CAM_BASE:05X}'
assert CAM_BASE + len(cam_blob) <= CAM_END, \
    f'cam blob ${CAM_BASE:05X}-{CAM_BASE+len(cam_blob)-1:05X} overflows ${CAM_END:05X}'
# the blob must jump to the clamp ($025300) and execute the displaced
# sub.w $FF0E8E,d0 (9079 00ff0e8e) on its gated-out path
assert bytes.fromhex('4ef900025300') in cam_blob, \
    'jmp $025300 (clamp) not found in the cam blob'
assert bytes.fromhex('907900ff0e8e') in cam_blob, \
    'displaced sub.w $FF0E8E,d0 not found in the cam blob'
# the blob must read the camera ($FF0E8E/$FF0E90) and gate on mode 2
assert bytes.fromhex('0c79000200ff00ae') in cam_blob, \
    'cmpi.w #2,$FF00AE (mode gate) not found in the cam blob'

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'
# the cam blob region must be free 0xFF padding in the base (the old
# camdelay region, restored by interp-fix2)
assert all(b == 0xFF for b in rom[CAM_BASE:CAM_BASE + len(cam_blob)]), \
    'cam blob region is not free 0xFF padding in the base'
# the pace blob region past the v1 blob's end ($FD922+) must be free
# 0xFF padding (the v1 blob is 34 bytes, $FD900-$FD921)
assert all(b == 0xFF for b in rom[0xFD922:PACE_BASE + len(pace_blob)]), \
    'pace blob extension region is not free 0xFF padding in the base'

# --- verify the hook sites (exact base-ROM bytes) ---
def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

expect(HOOK_CAM, '907900ff0e8e',
       'L025294 sub.w $FF0E8E,d0 ($02529C)')
expect(0x0252A2, '4a406c0e', 'tst.w d0; bge.b L0252B4 ($0252A2, next insn)')
expect(HOOK_PACE, '4eb9000fd900',
       'Path A pacing gate hook ($0228CC, jsr $FD900)')
# the v1 pacing blob must be intact (its entry: movem.l a0,-(a7))
assert bytes(rom[PACE_BASE:PACE_BASE+4]) == bytes.fromhex('48e70080'), \
    'v1 pacing blob entry (movem.l a0,-(a7)) not found at $FD900'
# the interp blob and its hooks must be intact
assert bytes(rom[0xFDA00:0xFDA00+4]) == bytes.fromhex('48e770e0'), \
    'interp blob entry not found at $FDA00'
expect(0x023480, '4eb9000fda00',
       'map_promote_record interp hook ($023480, jsr $FDA00)')
expect(0x023202, '4eb9000fda00',
       'hero_track interp hook ($023202, jsr $FDA00)')
# the mode-6 camera writes are unhooked (original moves)
expect(0x01C242, '33c000ff0e8e',
       'leader_spawn mode-6 cam X write ($01C242)')
expect(0x01C264, '33c000ff0e90',
       'leader_spawn mode-6 cam Y write ($01C264)')
# the original ROM must be untouched
orig = open(ORIG, 'rb').read()
assert hashlib.md5(orig).hexdigest() == ORIG_MD5, 'original ROM MD5 mismatch'
assert orig[HOOK_CAM:HOOK_CAM+6] == bytes.fromhex('907900ff0e8e'), \
    'original sub.w $FF0E8E,d0 not found in the original ROM'

# --- write the blobs and the cam hook ---
# A. camera: blob at $FDE00 + hook at $02529C
rom[CAM_BASE:CAM_BASE+len(cam_blob)] = cam_blob
rom[HOOK_CAM:HOOK_CAM+6] = b'\x4e\xb9' + struct.pack('>I', SNAP)  # jsr cam_snap.l
# B. face: replace the v1 pacing blob in place at $FD900 (the hook
#    already points there; the rest of the region past the new blob's
#    end up to $FD921 stays as the v1 blob's tail bytes only if the new
#    blob is shorter — it is longer (58 > 34), so overwrite fully, and
#    the bytes between the new blob's end and $FDA00 stay 0xFF).
rom[PACE_BASE:PACE_BASE+len(pace_blob)] = pace_blob

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
assert fixed[CAM_BASE:CAM_BASE+len(cam_blob)] == cam_blob
assert fixed[PACE_BASE:PACE_BASE+len(pace_blob)] == pace_blob
assert fixed[HOOK_CAM:HOOK_CAM+6] == b'\x4e\xb9' + struct.pack('>I', SNAP)
assert fixed[HOOK_PACE:HOOK_PACE+6] == b'\x4e\xb9' + struct.pack('>I', GATE)
# checksums verify
r = subprocess.run([sys.executable, CHECKSUM,
                    'verify-all', OUT], check=True, capture_output=True, text=True)
print(r.stdout.strip())
# all differing bytes must be inside the two blobs, the cam hook site,
# or the two checksum locations (header 0x18E, runtime 0xFD098)
base = open(BASE, 'rb').read()
diff_idx = [i for i in range(len(base)) if base[i] != fixed[i]]
bad = [i for i in diff_idx
       if not (PACE_BASE <= i < PACE_BASE + len(pace_blob)
               or CAM_BASE <= i < CAM_BASE + len(cam_blob)
               or HOOK_CAM <= i < HOOK_CAM + 6
               or i in (0x18E, 0x18F)
               or 0xFD098 <= i < 0xFD09C)]
assert not bad, f'bytes changed outside the blobs/hook/checksums: {[hex(i) for i in bad[:10]]}'
# every earlier blob is byte-identical to the base (flat/dither $FD400,
# feet fix $FD600, subcell $FD800, interp $FDA00-$FDBED)
assert fixed[0xFD400:0xFD800] == base[0xFD400:0xFD800], \
    'the flat/dither, feet-fix, or subcell blob changed!'
assert fixed[0xFDA00:0xFDBEE] == base[0xFDA00:0xFDBEE], \
    'the interp blob changed!'
# the other hook sites are untouched
assert fixed[0x023202:0x023208] == base[0x023202:0x023208], \
    'hero_track interp hook site changed!'
assert fixed[0x023480:0x023486] == base[0x023480:0x023486], \
    'map_promote_record interp hook site changed!'
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
# the pacing hook site still points at $FD900 (unchanged — the blob was
# replaced in place)
assert fixed[HOOK_PACE:HOOK_PACE+6] == base[HOOK_PACE:HOOK_PACE+6], \
    'pacing hook site changed (it should still be jsr $FD900)!'
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'interp-fix3: {len(diff)} bytes differ from rop-interp-fix2.rom\n')
    f.write(f'pace_gate v2 ${GATE:05X}, blob ${PACE_BASE:05X}-'
            f'${PACE_BASE+len(pace_blob)-1:05X} ({len(pace_blob)} bytes, '
            f'replaces the v1 blob in place; hook ${HOOK_PACE:05X} unchanged)\n')
    f.write(f'cam_snap ${SNAP:05X}, blob ${CAM_BASE:05X}-'
            f'${CAM_BASE+len(cam_blob)-1:05X} ({len(cam_blob)} bytes), '
            f'hook site ${HOOK_CAM:05X} (sub.w $FF0E8E,d0 -> jsr $FDE00)\n')
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

ips = f'{PATCHDIR}/interp-fix3.ips'
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
