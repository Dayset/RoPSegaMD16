#!/usr/bin/env python3
"""Build the interp-fix2 ROM: zoom-view legs + on-screen + straight walk.

Base: rop-interp-fix.rom (MD5 44353892c7a006300bfae2535ad6eaf8) — flat
checkerboard (mode 2), feet fix, subcell template override, pacing gate
(1 cell / 4 ticks), interpolation slide (room-relative, in hero_track),
one-step camera delay (step-mode camera writes in leader_spawn).
One fix only: make the zoom-view (mode 2) walk animate, stay on-screen,
and walk straight.

Diagnosis (static; full read in .scratch-interp-fix2/REPORT.md):
- DEAD LEGS: record+$A selects the figure-draw routine in map_chunk_pos
  (jump table $01BE86): +$A=0 -> hero_track, +$A=1 -> map_promote_record.
  The interp/subcell hooks live ONLY in hero_track ($023202). Buc's
  record+$A = 1 (probe-confirmed in the cutscene room; his +0x06 is the
  same on foot in any room), so Buc is drawn via map_promote_record, NOT
  hero_track. map_promote_record reads the RECORD's own template — the
  static template 6 in the zoom view — so the image never cycles and the
  legs don't move. In the cutscene his record IS a walk template (38),
  so the legs move there. This also explains every earlier "no subcell
  movement" playtest.
- OFF-SCREEN / ZIGZAG: the camera delay is fundamentally flawed for the
  room. It hooks ONLY the step-mode camera writes ($01C2D8/$01C300), but
  in the room grid+$C == 0, so world_reposition_leader calls
  leader_spawn(mode 6) — the absolute set — on every step, writing the
  camera at $01C242/$01C264 (NOT hooked) and NOT clearing PEND_VALID.
  The step-mode hooks fire only unpredictably (via the $0253F2
  leader_spawn($a(a6)) call and other step-mode callers), applying a
  STALE pending camera from a different step/direction — the camera
  jumps to the wrong cell (Buc off-screen) and the offset flips
  (zigzag). The room camera needs NO delay: world_reposition_leader
  only moves it when Buc is 3+ cells from the camera centre (L025294
  dead zone), so the slide IS visible without a delay, and the camera
  follows him exactly as in the original ROM.

The fix (three byte changes, no new code):
A. Hook map_promote_record at $023480 (lea.l $197B0,a0) -> jsr $FDA00.l,
   routing it through the EXISTING interp blob (unchanged; it ends with
   the displaced lea + rts, and the frame layout matches hero_track).
   Fixes the legs (walk template cycles), the slide (position
   interpolates), and the figure zigzag. The slide is gated off while a
   script runs, so the cutscene is unchanged.
B. Revert the camera-delay step-mode hooks to the original moves
   ($01C2D8 -> move.w d0,$FF0E8E.l; $01C300 -> move.w d0,$FF0E90.l).
   The camera returns to the original mode-6 behaviour (3-cell dead
   zone + clamp), which keeps Buc on-screen and the walk straight.
C. Restore the camdelay blob region $FDE00-$FDE7B (124 bytes) to 0xFF
   padding (now unreferenced).

The flat / checkerboard, feet fix, subcell override, pacing gate, and
interp slide are byte-identical to the base. Big world stays textured.
Cell rate unchanged (1 cell / 4 ticks). Fixes both checksums, emits the
.ips (round-trip verified) + changed-bytes.txt.

No live probes / screenshots / cadence measurements were run for this
build (Dayset's rule: he tests it himself). The base ROM and the
original ROM are never modified (read-only here).
"""
import hashlib, struct, subprocess, sys, os

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
CHECKSUM = os.environ.get('ROP_CHECKSUM', os.path.join(REPO, 'tools', 'checksum.py'))
SCRATCH = os.path.join(REPO, 'build', 'scratch-interp-fix2')
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-interp-fix.rom'))
BASE_MD5 = '44353892c7a006300bfae2535ad6eaf8'
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ORIG_MD5 = '30c18fdbe2183f64702ae9f1a45d63f9'
OUT = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-interp-fix2.rom'))
PATCHDIR = DIR

HOOK_PROMOTE = 0x023480   # map_promote_record lea.l $197B0,a0
INTERP_BLOB = 0xFDA00     # existing interp blob (unchanged)
HOOK_CAMX = 0x01C2D8      # leader_spawn step-mode cam X write
HOOK_CAMY = 0x01C300      # leader_spawn step-mode cam Y write
CAMDELAY_BASE = 0xFDE00   # camdelay blob region
CAMDELAY_END = 0xFDE7C    # exclusive (124 bytes)

os.makedirs(SCRATCH, exist_ok=True)
os.makedirs(PATCHDIR, exist_ok=True)

# --- read and verify the base ROM ---
rom = bytearray(open(BASE, 'rb').read())
assert len(rom) == 0x100000, f'ROM size {len(rom)}'
md5 = hashlib.md5(bytes(rom)).hexdigest()
assert md5 == BASE_MD5, f'base MD5 mismatch: {md5}'

def expect(addr, hexbytes, what):
    got = bytes(rom[addr:addr+len(hexbytes)//2]).hex()
    assert got == hexbytes, f'{what} at ${addr:05X}: got {got}, want {hexbytes}'

# hook sites (exact base-ROM bytes)
expect(HOOK_PROMOTE, '41f9000197b0',
       'map_promote_record lea.l $197B0,a0 ($023480)')
expect(HOOK_CAMX, '4eb9000fde00',
       'leader_spawn step-mode cam X hook ($01C2D8, jsr $FDE00)')
expect(HOOK_CAMY, '4eb9000fde3a',
       'leader_spawn step-mode cam Y hook ($01C300, jsr $FDE3A)')
# the interp blob must be intact (its entry + displaced-lea exit)
assert bytes(rom[INTERP_BLOB:INTERP_BLOB+4]) == bytes.fromhex('48e770e0'), \
    'interp blob entry (movem.l d1-d3/a0-a2,-(a7)) not found at $FDA00'
assert bytes.fromhex('41f9000197b0') in bytes(rom[INTERP_BLOB:0xFDE00]), \
    'interp blob displaced lea.l $197B0,a0 not found (blob $FDA00-$FDBED)'
# the camdelay blob must be present (its entry: tst.w $FF0110)
assert bytes(rom[CAMDELAY_BASE:CAMDELAY_BASE+4]) == bytes.fromhex('4a7900ff'), \
    'camdelay blob entry (tst.w $FF0110) not found at $FDE00'
# the hero_track interp hook must be intact (kept, harmless)
expect(0x023202, '4eb9000fda00',
       'hero_track interp hook ($023202, jsr $FDA00)')
# mode-6 camera writes must be unhooked (original moves)
expect(0x01C242, '33c000ff0e8e',
       'leader_spawn mode-6 cam X write ($01C242)')
expect(0x01C264, '33c000ff0e90',
       'leader_spawn mode-6 cam Y write ($01C264)')
# the original bytes to restore at the cam hooks (read from the original ROM)
orig = open(ORIG, 'rb').read()
assert hashlib.md5(orig).hexdigest() == ORIG_MD5, 'original ROM MD5 mismatch'
assert orig[HOOK_CAMX:HOOK_CAMX+6] == bytes.fromhex('33c000ff0e8e'), \
    'original cam X move not found in the original ROM'
assert orig[HOOK_CAMY:HOOK_CAMY+6] == bytes.fromhex('33c000ff0e90'), \
    'original cam Y move not found in the original ROM'

# --- apply the patch ---
# A. hook map_promote_record -> jsr $FDA00.l
rom[HOOK_PROMOTE:HOOK_PROMOTE+6] = b'\x4e\xb9' + struct.pack('>I', INTERP_BLOB)
# B. revert the camera-delay hooks to the original moves
rom[HOOK_CAMX:HOOK_CAMX+6] = bytes.fromhex('33c000ff0e8e')
rom[HOOK_CAMY:HOOK_CAMY+6] = bytes.fromhex('33c000ff0e90')
# C. restore the camdelay blob region to 0xFF padding
rom[CAMDELAY_BASE:CAMDELAY_END] = b'\xff' * (CAMDELAY_END - CAMDELAY_BASE)

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
assert fixed[HOOK_PROMOTE:HOOK_PROMOTE+6] == b'\x4e\xb9' + struct.pack('>I', INTERP_BLOB)
assert fixed[HOOK_CAMX:HOOK_CAMX+6] == bytes.fromhex('33c000ff0e8e')
assert fixed[HOOK_CAMY:HOOK_CAMY+6] == bytes.fromhex('33c000ff0e90')
assert all(b == 0xFF for b in fixed[CAMDELAY_BASE:CAMDELAY_END]), \
    'camdelay blob region not fully restored to 0xFF'
# checksums verify
r = subprocess.run([sys.executable, CHECKSUM,
                    'verify-all', OUT], check=True, capture_output=True, text=True)
print(r.stdout.strip())
# all differing bytes must be inside the hook sites, the camdelay blob
# region, or the two checksum locations (header 0x18E, runtime 0xFD098)
base = open(BASE, 'rb').read()
diff_idx = [i for i in range(len(base)) if base[i] != fixed[i]]
bad = [i for i in diff_idx
       if not (HOOK_PROMOTE <= i < HOOK_PROMOTE + 6
               or HOOK_CAMX <= i < HOOK_CAMX + 6
               or HOOK_CAMY <= i < HOOK_CAMY + 6
               or CAMDELAY_BASE <= i < CAMDELAY_END
               or i in (0x18E, 0x18F)
               or 0xFD098 <= i < 0xFD09C)]
assert not bad, f'bytes changed outside the patch regions: {[hex(i) for i in bad[:10]]}'
# every earlier blob is byte-identical to the base (flat/dither $FD400,
# feet fix $FD600, subcell $FD800, pacing $FD900, interp $FDA00)
assert fixed[0xFD400:0xFDE00] == base[0xFD400:0xFDE00], \
    'an earlier blob changed!'
# the other hook sites are untouched
assert fixed[0x023202:0x023208] == base[0x023202:0x023208], \
    'hero_track interp hook site changed!'
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
# mode-6 camera writes are untouched (teleports snap immediately)
assert fixed[0x01C242:0x01C248] == base[0x01C242:0x01C248], \
    'mode-6 cam X write changed!'
assert fixed[0x01C264:0x01C26A] == base[0x01C264:0x01C26A], \
    'mode-6 cam Y write changed!'
assert hashlib.md5(open(ORIG, 'rb').read()).hexdigest() == ORIG_MD5
assert hashlib.md5(base).hexdigest() == BASE_MD5

# --- changed-bytes.txt (vs the base ROM) ---
diff = [(i, base[i], fixed[i]) for i in range(len(base)) if base[i] != fixed[i]]
with open(f'{PATCHDIR}/changed-bytes.txt', 'w') as f:
    f.write(f'interp-fix2: {len(diff)} bytes differ from rop-interp-fix.rom\n')
    f.write(f'map_promote_record hook ${HOOK_PROMOTE:05X} -> jsr ${INTERP_BLOB:05X}; '
            f'cam hooks ${HOOK_CAMX:05X}/${HOOK_CAMY:05X} reverted to the '
            f'original moves; camdelay blob ${CAMDELAY_BASE:05X}-'
            f'${CAMDELAY_END-1:05X} restored to 0xFF padding\n')
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

ips = f'{PATCHDIR}/interp-fix2.ips'
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
