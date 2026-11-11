"""Static simulator for map_terrain_tile_lookup ($E358) dispatch.
CORRECTED 2026-11-11: streams tile the $603E4-$9611F region exactly;
a stream's length is (next offset - this offset), terminator = last byte (0x00).
0x00 bytes INSIDE a stream are pattern data, not terminators (first-0 model was wrong:
493/944 streams have first-0 != tiling end; with tiling, all 3776 decode combos land
exactly on the terminator, 0 overruns)."""
# Run from the repo root; needs disasm/src/rop.s generated (tools/gen_src.py) for handler sizes.
import struct
from collections import Counter
rom = open('rop-original.gen','rb').read()
tbl = [struct.unpack('>I', rom[0xDF58+4*i:0xDF58+4*i+4])[0] for i in range(256)]
import re
lines = open('disasm/src/rop.s').read().splitlines()
addr2idx = {}
for n, ln in enumerate(lines):
    m = re.search(r'; \$([0-9A-Fa-f]{5,6})\s*$', ln)
    if m: addr2idx[int(m.group(1), 16)] = n
def hsize(tgt):
    if tgt not in addr2idx: return None
    n = addr2idx[tgt]; reads = 0
    for ln in lines[n:n+120]:
        if re.match(r'^\s*bra\.w L00E3E2', ln) or re.match(r'^\s*bra\.w L00E43C', ln): return reads
        if re.match(r'^\s*rts', ln): return reads
        if 'move.b (a0)+,d5' in ln: reads += 1
    return None
HSIZE = {t: hsize(t) for t in set(tbl)}
offs = [struct.unpack('>I', rom[0x5F524+4*i:0x5F524+4*i+4])[0] for i in range(944)]
END = 0x96120 - 0x603E4  # last stream ends at $96120
lens = [(offs[i+1] if i < 943 else END) - offs[i] for i in range(944)]
def get_stream(i):
    return rom[0x603E4+offs[i]:0x603E4+offs[i]+lens[i]]
def idxA(b, d0): return ((b>>4)<<4) | ((2*(b&0xF)+d0)&6)
def idxB(b, d0): return ((b>>4)<<4) | (((-2*(b&0xF)+d0)&6)|1)
def simulate(s, d0, path):
    """Returns (dispatches, stop_pos, stopped_at_terminator). dispatches = list of (byte, idx, target, hsize)."""
    idxf = idxA if path==0 else idxB
    i = 0; out=[]
    while i < len(s):
        b = s[i]
        if b == 0:
            return out, i, (i == len(s)-1)
        idx = idxf(b, d0); hs = HSIZE[tbl[idx]]
        out.append((b, idx, tbl[idx], hs))
        i += 1+hs
        if i > len(s):
            return out, i, False
    return out, i, False
if __name__ == '__main__':
    over=0; exact=0; early=0
    lo_cnt={0:Counter(),1:Counter()}; tot=0
    for si in range(944):
        s = get_stream(si)
        for d0 in (0,2):
            for path in (0,1):
                disp, pos, ok = simulate(s, d0, path)
                tot += len(disp)
                if ok: exact+=1
                elif pos > len(s): over+=1
                else: early+=1
                for (b,idx,t,hs) in disp: lo_cnt[path][b&0xF]+=1
    print(f"total tiling bytes: {sum(lens)}; streams: 944")
    print(f"decode combos: 3776; exact-terminator: {exact}; early-0: {early}; overrun: {over}")
    print(f"total dispatches: {tot}")
    print("lo counts pathA:", [lo_cnt[0][i] for i in range(16)])
    print("lo counts pathB:", [lo_cnt[1][i] for i in range(16)])
    print("stream lens: min", min(lens), "max", max(lens))
    print("distinct byte values:", len(set().union(*[set(get_stream(i)) for i in range(944)])))
