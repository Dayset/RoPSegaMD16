#!/usr/bin/env python3
"""z80_carve.py — carve the Z80 sound driver blob to labelled Z80 source (#78).

Linear-sweep Z80 decoder (official opcodes, CB/DD/ED/FD/DDCB/FDCB), emits
vasm oldstyle source. Each instruction is re-assembled and compared; any
instruction that does not reproduce the ROM bytes is emitted as `db` instead,
so the output is always byte-identical.

Usage:
  tools/z80_carve.py <rom> <start> <end> <out.s> [--vasm tools/vasm/vasmz80_oldstyle]
  <start>/<end> are ROM addresses (end exclusive). Z80 addresses are blob offsets.
"""
import os
import subprocess
import sys
import tempfile

R = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
RP = ['bc', 'de', 'hl', 'sp']
RP2 = ['bc', 'de', 'hl', 'af']
CC = ['nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm']
ALU = ['add a,', 'adc a,', 'sub ', 'sbc a,', 'and ', 'xor ', 'or ', 'cp ']
ROT = ['rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'sll', 'srl']
IM = [0, 0, 1, 2, 0, 1, 2, 3]


class Bad(Exception):
    pass


class Cur:
    def __init__(self, buf, pc):
        self.buf = buf
        self.pc = pc          # Z80 address of the opcode's first byte
        self.i = 0            # bytes consumed

    def byte(self):
        if self.i >= len(self.buf):
            raise Bad()
        v = self.buf[self.i]
        self.i += 1
        return v

    def word(self):
        lo = self.byte()
        return lo | (self.byte() << 8)

    def disp(self):
        d = self.byte()
        return d - 256 if d >= 128 else d


def hx(v, w=2):
    return '$%0*x' % (w, v & ((1 << (4 * w)) - 1))


def sdisp(d):
    return '+%s' % hx(d) if d >= 0 else '-%s' % hx(-d)


def rname(idx, p, c):
    """Operand for 8-bit register index; p = None | 'ix' | 'iy'. Reads disp lazily."""
    if idx == 6 and p:
        return '(%s%s)' % (p, sdisp(c.disp()))
    if p and idx in (4, 5):
        return p + ('h' if idx == 4 else 'l')
    return R[idx]


def decode(buf, pc):
    """Return (size, text, target) for the instruction at buf[0]; target = abs jump target or None."""
    c = Cur(buf, pc)
    op = c.byte()
    if op == 0xCB:
        return _cb(c, None)
    if op in (0xDD, 0xFD):
        p = 'ix' if op == 0xDD else 'iy'
        op2 = c.byte()
        if op2 == 0xCB:
            return _cb(c, p)
        if op2 in (0xDD, 0xFD, 0xED):
            raise Bad()
        return _main(c, op2, p)
    if op == 0xED:
        return _ed(c)
    return _main(c, op, None)


def _cb(c, p):
    if p:
        d = c.disp()
        op = c.byte()
        target = '(%s%s)' % (p, sdisp(d))
    else:
        op = c.byte()
        target = None
    x, y, z = op >> 6, (op >> 3) & 7, op & 7
    if p:
        # DDCB/FDCB: result also copied to reg z when z != 6 (undocumented); only z == 6 accepted
        if z != 6:
            raise Bad()
        dst = target
    else:
        dst = R[z]
    if x == 0:
        txt = '%s %s' % (ROT[y], dst)
    elif x == 1:
        txt = 'bit %d,%s' % (y, dst)
    elif x == 2:
        txt = 'res %d,%s' % (y, dst)
    else:
        txt = 'set %d,%s' % (y, dst)
    return c.i, txt, None


def _ed(c):
    op = c.byte()
    x, y, z = op >> 6, (op >> 3) & 7, op & 7
    p, q = y >> 1, y & 1
    if x == 1:
        if z == 0:
            return c.i, 'in %s,(c)' % ('f' if y == 6 else R[y]), None
        if z == 1:
            return c.i, 'out (c),%s' % ('0' if y == 6 else R[y]), None
        if z == 2:
            return c.i, ('adc' if q else 'sbc') + ' hl,' + RP[p], None
        if z == 3:
            a = c.word()
            return c.i, ('ld (%s),%s' if not q else 'ld %s,(%s)') % ((hx(a, 4), RP[p]) if not q else (RP[p], hx(a, 4))), None
        if z == 4:
            return c.i, 'neg', None
        if z == 5:
            return c.i, 'reti' if y == 1 else 'retn', None
        if z == 6:
            return c.i, 'im %d' % IM[y], None
        return c.i, ['ld i,a', 'ld r,a', 'ld a,i', 'ld a,r', 'rrd', 'rld', 'nop', 'nop'][y], None
    if x == 2 and y >= 4 and z <= 3:
        names = [['ldi', 'ldd', 'ldir', 'lddr'], ['cpi', 'cpd', 'cpir', 'cpdr'],
                 ['ini', 'ind', 'inir', 'indr'], ['outi', 'outd', 'otir', 'otdr']][z]
        return c.i, names[y - 4], None
    raise Bad()


def _main(c, op, p):
    x, y, z = op >> 6, (op >> 3) & 7, op & 7
    pp, q = y >> 1, y & 1
    HL = p if p else 'hl'

    def rp_name(i):
        return p if (p and i == 2) else RP[i]

    if x == 0:
        if z == 0:
            if y == 0:
                return c.i, 'nop', None
            if y == 1:
                return c.i, "ex af,af'", None
            if y == 2:
                e = c.disp()
                t = (c.pc + c.i + e) & 0xFFFF
                return c.i, 'djnz', t
            if y == 3:
                e = c.disp()
                return c.i, 'jr', (c.pc + c.i + e) & 0xFFFF
            e = c.disp()
            return c.i, 'jr %s' % CC[y - 4], (c.pc + c.i + e) & 0xFFFF
        if z == 1:
            if q == 0:
                n = c.word()
                return c.i, 'ld %s,%s' % (rp_name(pp), hx(n, 4)), None
            return c.i, 'add %s,%s' % (HL, rp_name(pp)), None
        if z == 2:
            if q == 0:
                if pp == 0:
                    return c.i, 'ld (bc),a', None
                if pp == 1:
                    return c.i, 'ld (de),a', None
                a = c.word()
                if pp == 2:
                    return c.i, 'ld (%s),%s' % (hx(a, 4), HL), None
                return c.i, 'ld (%s),a' % hx(a, 4), None
            if pp == 0:
                return c.i, 'ld a,(bc)', None
            if pp == 1:
                return c.i, 'ld a,(de)', None
            a = c.word()
            if pp == 2:
                return c.i, 'ld %s,(%s)' % (HL, hx(a, 4)), None
            return c.i, 'ld a,(%s)' % hx(a, 4), None
        if z == 3:
            return c.i, ('dec ' if q else 'inc ') + rp_name(pp), None
        if z == 4 or z == 5:
            # INC/DEC r: disp read before we know operand; rname reads it lazily
            opnd = rname(y, p, c)
            return c.i, ('inc ' if z == 4 else 'dec ') + opnd, None
        if z == 6:
            opnd = rname(y, p, c)
            n = c.byte()
            return c.i, 'ld %s,%s' % (opnd, hx(n)), None
        return c.i, ['rlca', 'rrca', 'rla', 'rra', 'daa', 'cpl', 'scf', 'ccf'][y], None

    if x == 1:
        if op == 0x76:
            return c.i, 'halt', None
        # memory operand (HL)->(IX+d) only; the register side stays plain H/L
        mem = (y == 6 or z == 6)
        dst = R[y] if (mem and y != 6) else rname(y, p, c)
        src = R[z] if (mem and z != 6) else rname(z, p, c)
        return c.i, 'ld %s,%s' % (dst, src), None

    if x == 2:
        src = rname(z, p, c)
        return c.i, ALU[y] + src, None

    # x == 3
    if z == 0:
        return c.i, 'ret %s' % CC[y], None
    if z == 1:
        if q == 0:
            return c.i, 'pop %s' % (p if (p and pp == 2) else RP2[pp]), None
        if pp == 0:
            return c.i, 'ret', None
        if pp == 1:
            return c.i, 'exx', None
        if pp == 2:
            return c.i, 'jp (%s)' % HL, None
        return c.i, 'ld sp,%s' % HL, None
    if z == 2:
        a = c.word()
        return c.i, 'jp %s' % CC[y], ('abs', a)
    if z == 3:
        if y == 0:
            a = c.word()
            return c.i, 'jp', ('abs', a)
        if y == 2:
            n = c.byte()
            return c.i, 'out (%s),a' % hx(n), None
        if y == 3:
            n = c.byte()
            return c.i, 'in a,(%s)' % hx(n), None
        if y == 4:
            return c.i, 'ex (sp),%s' % HL, None
        if y == 5:
            return c.i, 'ex de,hl', None
        if y == 6:
            return c.i, 'di', None
        if y == 7:
            return c.i, 'ei', None
        raise Bad()  # y == 1: CB prefix, handled earlier
    if z == 4:
        a = c.word()
        return c.i, 'call %s' % CC[y], ('abs', a)
    if z == 5:
        if q == 0:
            return c.i, 'push %s' % (p if (p and pp == 2) else RP2[pp]), None
        if pp == 0:
            a = c.word()
            return c.i, 'call', ('abs', a)
        raise Bad()  # DD/ED/FD handled earlier
    if z == 6:
        n = c.byte()
        return c.i, ALU[y] + hx(n), None
    return c.i, 'rst %s' % hx(y * 8), None


def assemble(vasm, src_text):
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR', None)) as td:
        s = os.path.join(td, 'd.s')
        b = os.path.join(td, 'd.bin')
        with open(s, 'w') as f:
            f.write(src_text)
        r = subprocess.run([vasm, '-Fbin', '-o', b, s], capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(b):
            raise RuntimeError('vasm failed: ' + r.stderr[-400:])
        with open(b, 'rb') as f:
            return f.read()


def build_listing(blob, base_pc, sizes_db, labels_ok):
    """Render listing from the decode map. sizes_db: set of instruction start offsets forced to db."""
    # first pass: linear sweep to find instruction starts
    items = []  # (off, size, text, target, kind)
    off = 0
    while off < len(blob):
        if off in sizes_db:
            items.append((off, 1, None, None, 'db'))
            off += 1
            continue
        try:
            size, text, target = decode(blob[off:off + 4], base_pc + off)
            if off + size > len(blob):
                raise Bad()
            items.append((off, size, text, target, 'op'))
            off += size
        except Bad:
            items.append((off, 1, None, None, 'db'))
            off += 1
    starts = {it[0] for it in items}
    labels = {}
    for off_, size, text, target, kind in items:
        if kind == 'op' and target is not None:
            t = target[1] if isinstance(target, tuple) else target
            if t in starts and labels_ok(t):
                labels[t] = 'z80_%04x' % t
    lines = []
    for off_, size, text, target, kind in items:
        if off_ in labels:
            lines.append('%s:' % labels[off_])
        if kind == 'db':
            lines.append('\tdb %s\t; %s' % (hx(blob[off_]), hx(off_, 4)))
            continue
        if target is not None:
            body = fmt_jump(text, target, labels)
        else:
            body = text
        lines.append('\t%s\t; %s' % (body, hx(off_, 4)))
    return '\n'.join(lines) + '\n', items


def fmt_jump(text, target, labels):
    t = target[1] if isinstance(target, tuple) else target
    dest = labels.get(t, hx(t, 4))
    head = text.rstrip()
    if ' ' in head:
        return '%s,%s' % (head, dest)   # conditional: "jr nz,dest"
    return '%s %s' % (head, dest)


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    rom_path, s_addr, e_addr, out_path = sys.argv[1:5]
    vasm = sys.argv[sys.argv.index('--vasm') + 1] if '--vasm' in sys.argv else 'tools/vasm/vasmz80_oldstyle'
    start, end = int(s_addr, 0), int(e_addr, 0)
    with open(rom_path, 'rb') as f:
        f.seek(start)
        blob = f.read(end - start)
    base_pc = 0
    forced = set()
    for attempt in range(5000):
        listing, items = build_listing(blob, base_pc, forced, lambda t: True)
        got = assemble(vasm, listing)
        if got == blob:
            break
        # find first differing byte; force the instruction containing it to db
        n = min(len(got), len(blob))
        first = next((i for i in range(n) if got[i] != blob[i]), n)
        owner = None
        for off_, size, text, target, kind in items:
            if off_ <= first < off_ + size:
                owner = off_
                break
        if owner is None or owner in forced:
            print('no progress at 0x%04x' % first)
            return 1
        forced.add(owner)
        print('attempt %d: mismatch at offset %s; forcing %s to db' % (attempt, hx(first, 4), hx(owner, 4)))
    else:
        print('did not converge')
        return 1
    with open(out_path, 'w') as f:
        f.write('; Z80 sound driver, carved from ROM %s-%s (blob offset = Z80 address)\n' % (s_addr, e_addr))
        f.write('; Generated by tools/z80_carve.py. Assembles to the ROM bytes with vasmz80_oldstyle -Fbin.\n')
        f.write(listing)
    n_db = sum(1 for it in items if it[4] == 'db')
    print('ok: %d bytes, %d items, %d db, forced %d' % (len(blob), len(items), n_db, len(forced)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
