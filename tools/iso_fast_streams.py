#!/usr/bin/env python3
"""Fast terrain streams for the smooth iso view (#266 item 1).

Converts the 944 terrain streams of $E358 (both paths: d3 = 0 and
d3 != 0) into a record form that a short 68k loop draws ~3x faster,
into a LINEAR 144-byte-per-line copy of the $FF1EC0 bitmap (no 8x8
tile layout, so a run of bytes never crosses a tile boundary).

Why it is exact (checked by `verify`): every stream's writes are
translation-invariant in (line - d1, column - d0/2) for all even d0
and all d1 (tools/e358.py port, all 944 x 2 streams), each byte is
written at most once per call, and the masks are only $00 (opaque),
$F0 / $0F (one transparent nibble) and $FF (value 0: no-op).

Block layout (placed at $100000 of the 2 MB ROM):
  +0      'ISOF'
  +4      long: offset of the stub code (from the block start)
  +8      long: offset of the pattern lengths
  +12     1888 x (dat.l, rec.l) offsets, entry = stream * 2 + (d3 != 0)
  stubs   144 x 24 bytes of 68k code, then 3 opaque tails (see below)
  lens    144 bytes: data bytes used by pattern P (for clipped calls)
  per entry at rec: base.w (column of the record origin minus d0/2),
          maxl.w (last line + 1), then records, then $FFFFFFFF
          record = disp.w (line * 144 + column - origin, >= 0),
                   P * 24 (stub offset; P = (h * 3 + t) * 16 + m)
  data: the record bytes in order (h masked, m opaque, t masked)

Record = one run of a line: h (0-2) bytes with a transparent nibble,
m (0-15) opaque bytes, t (0-2) masked bytes; empty bytes ($00) split
runs. Stub P: h x {move.b (a0)+,d5; move.b (a3,d5.w),d6; and.b
d6,(a5); or.b d5,(a5)+}, then bra.w into opaque tail t at 15 - m
(tail t = 15 x move.b (a0)+,(a5)+, t masked bytes, jmp (a6)).

  iso_fast_streams.py build --rom R --out F
  iso_fast_streams.py verify --rom R [--snapdir D]
"""
import argparse, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e358 import BUF_BASE, E358, N_STREAMS, TABLE_MASK

LINE = 144
NLINES = 184
STUB = 24
REF_D0, REF_D1 = 0x80, 0
OP_MASKED = [0x1A18, 0x1C33, 0x5000, 0xCD15, 0x8B1D]   # 10 bytes
OP_OPQ = 0x1AD8                                         # move.b (a0)+,(a5)+
OP_JMPA6 = 0x4ED6


def tiled_lc(addr):
    o = addr - BUF_BASE
    tr, r = divmod(o, 0x480)
    tc, r2 = divmod(r, 32)
    return tr * 8 + r2 // 4, tc * 4 + r2 % 4


def footprint(e, stream, path):
    """[(line, col, mask, value)] relative to (d1, d0/2), in write order."""
    ram = bytearray(65536)
    tr = []
    e.call(stream, REF_D0, REF_D1, path, ram, trace=tr)
    out = []
    for a, m, v in tr:
        l, c = tiled_lc(a)
        out.append((l - REF_D1, c - REF_D0 // 2, m, v))
    return out


def records(fp):
    """Runs -> (records [(line, col, h, m, t)], data bytes)."""
    rows = {}
    for l, c, m, v in fp:
        rows.setdefault(l, {})[c] = (m, v)
    recs, data = [], []
    for l in sorted(rows):
        r = rows[l]
        cols = sorted(c for c, (m, v) in r.items() if m != 0xFF)
        i = 0
        while i < len(cols):
            # contiguous non-empty run starting at cols[i]
            j = i
            while j + 1 < len(cols) and cols[j + 1] == cols[j] + 1:
                j += 1
            run = cols[i:j + 1]
            k = 0
            while k < len(run):
                start = k
                h = 0
                while k < len(run) and h < 2 and r[run[k]][0] != 0:
                    h += 1
                    k += 1
                m = 0
                while k < len(run) and m < 15 and r[run[k]][0] == 0:
                    m += 1
                    k += 1
                t = 0
                if m:
                    while k < len(run) and t < 2 and r[run[k]][0] != 0:
                        t += 1
                        k += 1
                assert k > start
                recs.append((l, run[start], h, m, t))
                data += [r[c][1] for c in run[start:k]]
            i = j + 1
    return recs, data


def stub_code():
    """144 stubs + 3 tails; returns bytes (stubs start at 0)."""
    tails_at = 144 * STUB
    tail_len = [30 + 10 * t + 2 for t in range(3)]
    tail_off = [tails_at, tails_at + tail_len[0],
                tails_at + tail_len[0] + tail_len[1]]
    code = bytearray()
    for P in range(144):
        ht, m = divmod(P, 16)
        h, t = divmod(ht, 3)
        s = bytearray()
        for _ in range(h):
            for wd in OP_MASKED:
                s += struct.pack(">H", wd)
        target = tail_off[t] + 2 * (15 - m)
        here = len(code) + len(s) + 2          # bra.w disp is from pc+2
        s += struct.pack(">Hh", 0x6000, target - here)
        assert len(s) <= STUB
        s += b"\x4e\x71" * ((STUB - len(s)) // 2)   # nop padding
        code += s
    for t in range(3):
        assert len(code) == tail_off[t]
        code += struct.pack(">H", OP_OPQ) * 15
        for _ in range(t):
            for wd in OP_MASKED:
                code += struct.pack(">H", wd)
        code += struct.pack(">H", OP_JMPA6)
    lens = bytes(((P // 16) // 3) + (P % 16) + ((P // 16) % 3) for P in range(144))
    return bytes(code), lens


def build(rom):
    e = E358(rom)
    entries = []
    for s in range(N_STREAMS):
        for path in (0, 1):
            recs, data = records(footprint(e, s, path))
            entries.append((recs, data))
    code, lens = stub_code()
    head = 12 + 8 * len(entries)
    stub_at = head
    lens_at = stub_at + len(code)
    pos = lens_at + len(lens)
    pos += pos & 1
    recblob = bytearray()
    datblob = bytearray()
    index = []
    for recs, data in entries:
        if recs:
            base = min(c for l, c, h, m, t in recs)
            maxl = max(l for l, c, h, m, t in recs) + 1
        else:
            base, maxl = 0, 0
        rb = struct.pack(">hH", base, maxl)
        for l, c, h, m, t in recs:
            disp = l * LINE + c - base
            assert 0 <= disp < 0x8000
            P = (h * 3 + t) * 16 + m
            rb += struct.pack(">HH", disp, P * STUB)
        rb += b"\xff\xff\xff\xff"
        index.append((len(recblob), len(datblob)))
        recblob += rb
        datblob += bytes(data)
    rec_at = pos
    dat_at = rec_at + len(recblob)
    out = bytearray(b"ISOF" + struct.pack(">II", stub_at, lens_at))
    for r, d in index:
        out += struct.pack(">II", dat_at + d, rec_at + r)
    out += code + lens
    if len(out) & 1:
        out += b"\0"
    assert len(out) == rec_at
    out += recblob + datblob
    if len(out) & 1:
        out += b"\0"
    return bytes(out)


# -- Python model of the 68k fast decoder, for verification --
def fast_call(blob, rom, stream, d0, d1, d3, lin):
    d0 &= 0xFFFE
    d1 &= 0xFFFF
    d1 = d1 - 0x10000 if d1 & 0x8000 else d1
    if d1 < -21:
        return
    ent = 12 + 8 * (stream * 2 + (1 if d3 & 0xFFFF else 0))
    dp, rp = struct.unpack_from(">II", blob, ent)
    base, maxl = struct.unpack_from(">hH", blob, rp)
    rp += 4
    origin = d1 * LINE + d0 // 2 + base
    while True:
        disp, po = struct.unpack_from(">HH", blob, rp)
        rp += 4
        if disp & 0x8000:
            return
        P = po // STUB
        ht, m = divmod(P, 16)
        h, t = divmod(ht, 3)
        a = origin + disp
        n = h + m + t
        vals = blob[dp:dp + n]
        dp += n
        y = d1 + disp // LINE                       # the record's line
        if not 0 <= y < NLINES:
            continue
        for i, v in enumerate(vals):
            masked = i < h or i >= h + m
            mask = rom[TABLE_MASK + v] if masked else 0
            o = a + i
            if 0 <= o < len(lin):
                lin[o] = (lin[o] & mask) | v


def lin_to_tiled(lin):
    out = bytearray(26496)
    for l in range(NLINES):
        for c in range(LINE):
            tr, li = divmod(l, 8)
            tc, b = divmod(c, 4)
            out[tr * 0x480 + tc * 32 + li * 4 + b] = lin[l * LINE + c]
    return out


def verify(rom, snapdir):
    import json
    import e358_map
    blob = build(rom)
    print("block bytes", len(blob))
    R = e358_map.MapReplayer(rom)
    calls = []
    orig = R.e.call

    def rec(s, d0, d1, d3, ram, trace=None):
        calls.append((s, d0, d1, d3))
        return orig(s, d0, d1, d3, ram, trace)
    R.e.call = rec
    man = json.load(open(os.path.join(snapdir, "manifest.json")))
    nf = nbad = 0
    for mm in man:
        if not mm["watch"]:
            continue
        ram = open(os.path.join(snapdir, "ram_f%05d.bin" % mm["frame"]), "rb").read()
        calls.clear()
        try:
            port, written, info = R.replay(ram)
        except Exception:
            continue
        lin = bytearray(NLINES * LINE + 64)
        for c in calls:
            fast_call(blob, rom, *c, lin)
        til = lin_to_tiled(lin)
        # compare every tile column the hole can use: columns 2..33
        diff = 0
        for tr in range(23):
            for tc in range(2, 34):
                o = tr * 0x480 + tc * 32
                if til[o:o + 32] != port[o:o + 32]:
                    diff += 1
        nf += 1
        nbad += diff > 0
        if diff:
            where = [(tr, tc) for tr in range(23) for tc in range(2, 34)
                     if til[tr * 0x480 + tc * 32:tr * 0x480 + tc * 32 + 32]
                     != port[tr * 0x480 + tc * 32:tr * 0x480 + tc * 32 + 32]]
            print("frame", mm["frame"], "tiles differing", diff, where[:6])
    print("renders", nf, "with differences", nbad)
    return nbad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "verify"])
    ap.add_argument("--rom", default="rop-original.gen")
    ap.add_argument("--out", default="build/iso_fast.bin")
    ap.add_argument("--snapdir", default="build/e358-map-ram")
    a = ap.parse_args()
    rom = open(a.rom, "rb").read()
    if a.cmd == "build":
        blob = build(rom)
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        open(a.out, "wb").write(blob)
        print("wrote %s: %d bytes" % (a.out, len(blob)))
    else:
        sys.exit(0 if verify(rom, a.snapdir) else 1)


if __name__ == "__main__":
    main()
