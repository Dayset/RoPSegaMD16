#!/usr/bin/env python3
"""tools/decode_e358.py — reimplementation of the $E358 threaded bitmap
decoder (issue #017 follow-up).

The decoder (entry $E358, dispatch loops $E3E2/$E43C, jump table
$DF58, writer blocks $E47C-$F1xx and $10078-$11062) stamps stream
bytes into the bitmap at $FF1EC0. Streams are NOT in the
0x044000-0x05FFFF block: $E358 takes a record index, reads a u32
offset from the pointer table at $5F524 (944 entries, at the tail
of that block), and decodes the 0-terminated stream at
$603E4 + offset (streams span $0603E4-$096069).

Call: jsr $E358 with four words pushed (68000 C order):
  (variant, row, xbase, index)  -- see $E358 prologue:
  d2 = 4(a7) = index, d0 = 6(a7) = xbase (forced even),
  d1 = 8(a7) = row (negative = skip-records mode in the prologue),
  d3 = 10(a7) = variant (0 -> $E3B4 loop/tables, !=0 -> $E412).

Per command byte b (stream, 0-terminated):
  n = b & 0xF
  variant A: t = 2*n + (xbase - 0x40);  key = (b & 0xF0) | (t & 6)
  variant B: t = (xbase - 0x26) - 2*n;  key = (b & 0xF0) | (t & 6) | 1
  celloff = word[$435C0 + t]           (signed word index)
  a5 = $FF1EC0 + word[$436E0 + d1idx] + celloff;  d1idx += 2
  handler = long[$DF58 + 4*key]        (E3E2/E43C = no-op advance)
  handler stamps k stream bytes at a5-relative offsets:
     A: val = byte;            new = (old & maskA[val]) | val
     B: val = swap_nibbles via $434C0 table;
        new = (old & maskA[val]) | val     (mask table $433C0 both)
Writes extracted symbolically from the handler blocks themselves
(this script disassembles them with Capstone and pattern-matches
the unrolled stamp sequences; unmodelled handlers are reported).

Usage:
  decode_e358.py INDEX [--variant 0|1] [--xbase N] [--row N]
                 [--out PNG] [--ascii]
"""
import struct, sys
from capstone import Cs, CS_ARCH_M68K, CS_MODE_BIG_ENDIAN

ROM_PATH = 'rop-original.gen'
TBL_PTR = 0x5F524      # u32 stream offsets, 944 entries
STREAM_BASE = 0x603E4  # + offset -> stream start
MASK_A = 0x433C0       # 256-byte mask table (both variants)
EXPAND_B = 0x434C0     # 256-byte nibble-swap table (variant B)
CELLOFF = 0x435C0      # word table
ROWOFF = 0x436E0       # word table
JUMPTAB = 0xDF58       # 256 longs
LOOP_A, LOOP_B = 0xE3E2, 0xE43C
EXIT = 0x11074

rom = open(ROM_PATH, 'rb').read()
def lw(a): return struct.unpack('>I', rom[a:a+4])[0]
def sw(a): return struct.unpack('>h', rom[a:a+2])[0]

MASK = rom[MASK_A:MASK_A+256]
EXPAND = rom[EXPAND_B:EXPAND_B+256]
JUMPS = [lw(JUMPTAB + 4*i) for i in range(256)]
STREAM_OFFS = [lw(TBL_PTR + 4*i) for i in range(944)]

# ---------- symbolic extraction of writer blocks ----------
_md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN)

def extract_handler(addr):
    """Return list of (rel_off, expand) stamp ops, or None if the
    block uses an instruction form we do not model.
    rel_off is relative to the handler-entry a5; expand=True means
    the byte passes through the $434C0 table first (variant B)."""
    ops = []
    off = 0
    expand_next = False
    pc = addr
    for _ in range(400):
        insn = next(_md.disasm(rom[pc:pc+16], pc), None)
        if insn is None:
            return None
        m, o = insn.mnemonic, insn.op_str.replace(' ', '')
        if m == 'move.b' and o == '(a0)+,d5':
            pass  # byte consumed; paired with the stamp below
        elif m == 'move.b' and o == '(a6,d5.w),d5':
            expand_next = True
        elif m == 'move.b' and o == '(a3,d5.w),d6':
            pass  # mask fetch, paired with and.b
        elif m == 'and.b' and o in ('d6,(a5)', 'd6,-(a5)', 'd6,(a5)+'):
            if o == 'd6,-(a5)':
                off -= 1
            ops.append([off, expand_next])
            expand_next = False
            if o == 'd6,(a5)+':
                ops[-1].append('postinc')
        elif m == 'or.b' and o in ('d5,(a5)', 'd5,-(a5)', 'd5,(a5)+'):
            pass  # second half of the stamp, already recorded
        elif m in ('adda.w', 'suba.w') and o.endswith(',a5'):
            imm = int(o.split(',')[0].lstrip('#$'), 16)
            off += imm if m == 'adda.w' else -imm
        elif m == 'bra.w' and o in ('$e3e2', '$e43c'):
            return [(x[0], x[1]) for x in ops]
        else:
            return None
        pc += insn.size
    return None

HANDLERS = {}
def handler_ops(addr):
    if addr not in HANDLERS:
        HANDLERS[addr] = extract_handler(addr)
    return HANDLERS[addr]

# ---------- the decoder ----------
def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v

def decode(index, variant=0, xbase=0x40, row=0, bitmap_size=0x10000):
    """Run one $E358 call. Returns (bitmap, base_guard, stats)."""
    GUARD = 0x1000
    bmp = bytearray(bitmap_size + GUARD)
    start = STREAM_BASE + STREAM_OFFS[index]
    # prologue record-skip mode for negative row
    pos = start
    r = row
    if r < 0:
        skip = -r - 1
        for _ in range(skip + 1):
            b = rom[pos]; pos += 1
            if b == 0:
                return bmp, GUARD, {'commands': 0, 'end': 'skip-exit'}
            pos += (b >> 4)
        r = 0
    d0 = (xbase - (0x40 if variant == 0 else 0x26)) & 0xFFFF
    d1idx = (r * 2) & 0xFFFF
    stats = {'commands': 0, 'stamps': 0, 'unmodelled': []}
    maxoff = 0
    while True:
        b = rom[pos]; pos += 1
        if b == 0:
            break
        n = b & 0xF
        if variant == 0:
            t = (2*n + d0) & 0xFFFF
            key = (b & 0xF0) | (s16(t) & 6)
        else:
            t = (d0 - 2*n) & 0xFFFF
            key = (b & 0xF0) | (s16(t) & 6) | 1
        celloff = sw(CELLOFF + s16(t))
        rowoff = sw(ROWOFF + s16(d1idx))
        d1idx = (d1idx + 2) & 0xFFFF
        a5 = rowoff + celloff
        handler = JUMPS[key]
        stats['commands'] += 1
        if handler in (LOOP_A, LOOP_B):
            continue
        ops = handler_ops(handler)
        if ops is None:
            stats['unmodelled'].append(hex(handler))
            continue
        for rel, expand in ops:
            v = rom[pos]; pos += 1
            if expand:
                v = EXPAND[v]
            tgt = GUARD + a5 + rel
            bmp[tgt] = (bmp[tgt] & MASK[v]) | v
            stats['stamps'] += 1
            if a5 + rel > maxoff:
                maxoff = a5 + rel
    stats['maxoff'] = maxoff
    stats['stream_bytes'] = pos - start
    return bmp, GUARD, stats

def render_ascii(bmp, guard, width=33, rows=64):
    lines = []
    for r in range(rows):
        row = bmp[guard + r*width: guard + (r+1)*width]
        lines.append(''.join('#' if c else ('+' if False else '.')
                             for c in row))
    return '\n'.join(lines)

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('index', type=lambda x: int(x, 0))
    ap.add_argument('--variant', type=int, default=0)
    ap.add_argument('--xbase', type=lambda x: int(x, 0), default=0x40)
    ap.add_argument('--row', type=lambda x: int(x, 0), default=0)
    ap.add_argument('--ascii', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args()
    bmp, guard, stats = decode(a.index, a.variant, a.xbase, a.row)
    print(f"record {a.index}: stream @ 0x{STREAM_BASE + STREAM_OFFS[a.index]:06X} "
          f"variant {a.variant} xbase 0x{a.xbase:X} row {a.row}")
    print(f"stats: {stats}")
    bad = [h for h in set(JUMPS) if h not in (LOOP_A, LOOP_B)
           and handler_ops(h) is None]
    print(f"unmodelled handler blocks overall: {[hex(x) for x in bad]}")
    if a.ascii:
        print(render_ascii(bmp, guard))
    if a.out:
        try:
            from PIL import Image
            W, H = 33*8, 256
            img = Image.new('1', (W, H))
            px = img.load()
            for y in range(H):
                for bx in range(33):
                    v = bmp[guard + y*33 + bx]
                    for bit in range(8):
                        if v & (0x80 >> bit):
                            px[bx*8 + bit, y] = 1
            img = img.resize((W*2, H*2), Image.NEAREST)
            img.save(a.out)
            print(f"wrote {a.out}")
        except ImportError:
            print("PIL not available; PNG skipped")
