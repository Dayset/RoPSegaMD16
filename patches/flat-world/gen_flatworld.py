#!/usr/bin/env python3
"""Generate flatworld.s: $E358 dispatch-hook flat plane for the OVERWORLD.

Reads the 112 $E358 paint handlers from disasm/src/rop.s and emits a flat
version of each (same addressing, pixel byte replaced by the flat byte F,
which the dispatch hook loads into d5 from RAM $FF00B0 before jumping in).

Transformation per handler (verified: handlers are straight-line, only
6 mnemonics, first instruction always `move.b (a0)+,d5`):
  move.b (a0)+,d5   -> addq.l #1,a0        (advance stream, keep d5=F)
  move.b (a6,d5.w),d5 -> OMIT              (path-B nibble remap; F has equal nibbles)
  bra.w L00E3E2/L00E43C -> jmp $E3E2.l / $E43C.l
  everything else   -> copied verbatim

Also emits:
  flat_table: 248 dc.l, indexed by d2 (the $E358 table index, 0..0x3DC step 4).
              Entry = flat stub label, or 0 for re-loop/invalid.
  water_tbl:  64 dc.b, indexed by terrain type (props bits 10-15). 1=water, 0=land.
              Water types: 0,2,3,10,11,15,21,22,23.
  dispatch_hook: the $E358 dispatch hook (see source).
  callsite_stub: sets RAM flat byte from the tile's terrain type, tail-calls $E358.

Constants (grounded in stream data):
  LAND_K  = 3  (pure green (0,144,0) in the overworld palette $CCB18 idx 3;
                 tiles 16/17 but renders BLUE in the overworld palette,
                 so the first flat build came out a blue plane. Nibble 2
                 is the green in the grass tile data {4:135, 2:94, 0:33}.)
  WATER_K = 1  (dominant palette index in sea tiles 28/29)
  FLAT_RAM = $FF00B0 (zero references in the original ROM; not used by v3/glide/flat-zoom)
"""
import os, struct, re, bisect, sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
ROM = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
ROPS = os.path.join(REPO, 'disasm', 'src', 'rop.s')
OUT = os.path.join(DIR, 'source.s')

LAND_K = 3
WATER_K = 1
LAND_F = (LAND_K << 4) | LAND_K      # 0x33
WATER_F = (WATER_K << 4) | WATER_K   # 0x11
WATER_TYPES = {0, 2, 3, 10, 11, 15, 21, 22, 23}

rom = open(ROM, 'rb').read()

# ---- parse rop.s into addr -> instruction text ----
lines = open(ROPS, errors='replace').read().split('\n')
addr2ins = {}
for ln in lines:
    m = re.search(r'; \$(0[0-9A-Fa-f]{5})\s*$', ln)
    if m:
        addr2ins[int(m.group(1), 16)] = ln.split(';')[0].strip()
addrs_sorted = sorted(addr2ins.keys())
def next_addr(a):
    i = bisect.bisect_right(addrs_sorted, a)
    return addrs_sorted[i] if i < len(addrs_sorted) else None

# ---- handler addresses from the $DF58 dispatch table ----
entries = {}   # (H, lb) -> handler addr
for H in range(0x00, 0x100, 0x10):
    for lb in range(8):
        off = (H | lb) * 4
        v = struct.unpack('>I', rom[0xDF58+off:0xDF58+off+4])[0]
        if v not in (0xE3E2, 0xE43C):
            entries[(H, lb)] = v
assert len(entries) == 112, f'expected 112 paint entries, got {len(entries)}'

# ---- parse each handler, transform, collect ----
def parse_handler(start):
    insns = []
    a = start
    guard = 0
    while guard < 300:
        guard += 1
        ins = addr2ins.get(a)
        if ins is None:
            raise SystemExit(f'handler ${start:05X}: missing instruction at ${a:05X}')
        insns.append((a, ins))
        if re.match(r'bra\.w\s+L00(E3E2|E43C)\s*$', ins):
            return insns
        na = next_addr(a)
        if na is None:
            raise SystemExit(f'handler ${start:05X}: ran off the end at ${a:05X}')
        a = na
    raise SystemExit(f'handler ${start:05X}: too long / no terminator')

stubs = {}   # (H, lb) -> list of vasm source lines
for (H, lb), start in sorted(entries.items()):
    insns = parse_handler(start)
    # verify first instruction is a read (so d5=F from the hook is valid)
    assert insns[0][1] == 'move.b (a0)+,d5', f'handler ${start:05X} first ins not a read: {insns[0][1]}'
    out_lines = []
    for a, ins in insns:
        if ins == 'move.b (a0)+,d5':
            out_lines.append('\taddq.l #1,a0')
        elif ins == 'move.b (a6,d5.w),d5':
            continue  # omit remap; F has equal nibbles so the swap is a no-op
        elif re.match(r'bra\.w\s+L00E3E2\s*$', ins):
            out_lines.append('\tjmp $E3E2.l')
        elif re.match(r'bra\.w\s+L00E43C\s*$', ins):
            out_lines.append('\tjmp $E43C.l')
        else:
            # copy verbatim (only adda/suba #imm, and/or, mask remain)
            assert re.match(r'^(adda\.w|suba\.w|and\.b|or\.b|move\.b) ', ins), \
                f'handler ${start:05X}: unexpected instruction: {ins!r}'
            out_lines.append('\t' + ins)
    stubs[(H, lb)] = out_lines

# ---- sanity: total flat stub size (estimate: original bytes - 4*remaps + 2*terminators) ----
# (reads->addq is size-neutral; remaps omitted save 4B each; jmp is +2B vs bra)
total_orig = 0
total_flat_est = 0
for (H, lb), start in sorted(entries.items()):
    insns = parse_handler(start)
    # original byte length = last addr + last ins size - start; approximate via next handler/start
    # simpler: sum instruction sizes from the listing addresses
    addrs = [a for a, _ in insns]
    # last instruction size: bra.w = 4
    orig_len = (addrs[-1] + 4) - start
    nremap = sum(1 for _, ins in insns if ins == 'move.b (a6,d5.w),d5')
    total_orig += orig_len
    total_flat_est += orig_len - 4 * nremap + 2  # +2 for jmp vs bra
print(f'handlers: {len(stubs)}, original bytes: {total_orig}, flat est: {total_flat_est}', file=sys.stderr)

# ---- emit the vasm source ----
# Layout order is deliberate: the dispatch hook and call-site stub use
# PC-relative indexed addressing (brief extension word, +/-127 displacement),
# so each table is placed immediately after the code that references it.
#   dispatch_hook -> flat_table (next) -> callsite_stub -> water_tbl -> flat stubs
L = []
L.append('; flatworld.s — $E358 dispatch-hook flat plane for the OVERWORLD (mode 1).')
L.append('; Generated by gen_flatworld.py — do not hand-edit the stubs or the tables.')
L.append('; Blob base is set by build.py (org $FD0CC, start of the free 0xFF padding).')
L.append(';')
L.append(f'; LAND_K={LAND_K} (grass-dominant index), WATER_K={WATER_K} (sea-dominant index).')
L.append('; FLAT_RAM $FF00B0 holds the current flat byte F (set by callsite_stub).')
L.append('')
L.append('\torg $FD0CC')
L.append('')

# dispatch hook
L.append('; dispatch_hook: entered via jmp from $E40C (path A) and $E470 (path B).')
L.append('; On entry: d2 = table index (*4), a6 = $DF58, d6 = dead scratch.')
L.append('; Stack top = $E358 return address (map_chunk_pos ret for terrain calls).')
L.append('; Pushes the handler address and rts (computed goto, as the original).')
L.append('dispatch_hook:')
L.append('\tmove.l (a6,d2.w),-(a7)')
L.append('\tbtst #2,d2')
L.append('\tbeq.s .pathA')
L.append('\tlea.l $434C0,a6')
L.append('.pathA:')
L.append('\tcmpi.l #$01BC20,32(a7)')
L.append('\tbeq.s .terrain')
L.append('\tcmpi.l #$01BC42,32(a7)')
L.append('\tbeq.s .terrain')
L.append('\tcmpi.l #$01BC8A,32(a7)')
L.append('\tbne.s .done')
L.append('.terrain:')
L.append('\tcmpi.w #1,$FF00AE')
L.append('\tbne.s .done')
L.append('\t; grid check: only the overworld grid slot $FFB08C. Room grids are')
L.append('\t; $FFB0AC/$FFB09C/$FFB0BC (world_location_transition $01DC00/$01DC0E/')
L.append('\t; $01DFB2); the overworld branch sets $FFB08C ($01DE08) and boot sets')
L.append('\t; it too ($01B74E). Mode flips to 1 (op-10) BEFORE the grid switches')
L.append('\t; in the room->overworld transition, so mode alone flattens the room')
L.append('\t; floor blue in that window; the grid check closes it.')
L.append('\tmove.l $FFA7FC,d6')
L.append('\tcmpi.l #$FFB08C,d6')
L.append('\tbne.s .done')
L.append('\tmove.l (flat_table,pc,d2.w),d6')
L.append('\tbeq.s .done')
L.append('\tmove.l d6,(a7)')
L.append(f'\tmove.b $FF00B0,d5')
L.append('.done:')
L.append('\trts')
L.append('')

# lookup table: indexed by d2 (0..0x3DC step 4). 248 entries.
# NOTE: bit 3 of (d2/4) is NEVER set by the $E358 loop (high nibble is a
# multiple of 0x10, low bits are 0-7), so those slots are unreachable;
# the original $DF58 points them at the re-loop ($E3E2). Mirror that (0).
L.append('flat_table:')
for d2 in range(0, 0x3E0, 4):
    X = d2 >> 2
    H = X & 0xF0
    lb = X & 0x7
    if (X & 0x08) == 0 and (H, lb) in stubs:
        L.append(f'\tdc.l flat_{H:02x}_{lb}')
    else:
        L.append('\tdc.l 0')
L.append('')

# call-site stub
L.append('; callsite_stub: called via jsr from map_chunk_pos $01BC1A/$01BC3C/$01BC84.')
L.append('; Sets RAM flat byte from the tile terrain type, then tail-calls $E358.')
L.append('; a6 = map_chunk_pos frame; props word at -$6(a6), terrain type bits 10-15.')
L.append('callsite_stub:')
L.append('\tmovem.l d6,-(a7)')
L.append('\tmove.w -$6(a6),d6')
L.append('\tlsr.w #8,d6')
L.append('\tlsr.w #2,d6')
L.append('\tmove.b (water_tbl,pc,d6.w),d6')
L.append('\ttst.b d6')
L.append('\tbne.s .water')
L.append(f'\tmove.b #${LAND_F:02X},$FF00B0')
L.append('\tbra.s .go')
L.append('.water:')
L.append(f'\tmove.b #${WATER_F:02X},$FF00B0')
L.append('.go:')
L.append('\tmovem.l (a7)+,d6')
L.append('\tjmp $E358.l')
L.append('')

# water-type table: 64 bytes, indexed by terrain type. 1=water, 0=land.
L.append('water_tbl:')
row = []
for t in range(64):
    row.append('1' if t in WATER_TYPES else '0')
    if len(row) == 16:
        L.append('\tdc.b ' + ','.join(row))
        row = []
if row:
    L.append('\tdc.b ' + ','.join(row))
L.append('')

# flat stubs
for (H, lb) in sorted(stubs):
    L.append(f'flat_{H:02x}_{lb}:')
    L.extend(stubs[(H, lb)])
    L.append('')

open(OUT, 'w').write('\n'.join(L) + '\n')
print(f'wrote {OUT}', file=sys.stderr)
