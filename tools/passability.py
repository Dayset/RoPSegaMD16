#!/usr/bin/env python3
"""Overworld passability grid + path search for Rings of Power.

Session #10 tool. Builds the 352x224 overworld tile grid from the
$DD5C map archive (records 0..76 = 11x7 chunks of 32x32, row-major),
derives each tile's terrain class from the 512-word property table at
$5EDC4 (with the bit-12 remap through $1A5C0), and applies the
mode-1 (on-foot) passability rules read out of the terrain query
FUN_0001C892:

  prop  = word at $5EDC4 + 2*(tile & 0x1FF)
  class = (prop >> 10) & 0x3F        (remapped via $1A5C0 if tile bit 12 set)
  H     = 2*(((tile>>13)&7) + ((prop>>7)&1)) + ((prop>>8)&1)
  step blocked if |H_cur - H_dst| (-1 if both props have bit 8) >= 4

Mode-1 passable classes: 5,6,7,9,17,18,19,25,26,27,28 and any >= 0x23;
class 10 only for E/W steps, class 11 only for N/S steps; all other
classes 0..0x22 block a walker. (Class dispatch table at $1D73E,
handlers read individually; see docs/logic-audit.md session #10 and
docs/route-to-mind.md.)

Usage: passability.py [route]   -- prints class histogram + spawn
       area render, or BFS route stats for spawn -> (171,110) and
       teleport landing (171,125) -> (171,110).
Requires rop-original.gen in the repo root (git-ignored).
"""
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_text import dd5c_decompress

ROM_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        '..', 'rop-original.gen')
rom = open(ROM_PATH, 'rb').read()
TABLE, ARCHIVE = 0x43850, 0x44228

def record(i):
    off, size, typ = struct.unpack_from('>IIH', rom, TABLE + i * 10)
    data, _ = dd5c_decompress(rom, ARCHIVE + off)
    assert len(data) == size, (i, len(data), size)
    return data

W, H, CS = 352, 224, 32
world = [[0] * W for _ in range(H)]
for cy in range(7):
    for cx in range(11):
        words = struct.unpack('>1024H', record(cy * 11 + cx))
        for r in range(32):
            for c in range(32):
                world[cy * 32 + r][cx * 32 + c] = words[r * 32 + c]

props = struct.unpack('>512H', rom[0x5EDC4:0x5EDC4 + 1024])
remap = struct.unpack('>64H', rom[0x1A5C0:0x1A5C0 + 128])

def cell(x, y):
    t = world[y][x]
    p = props[t & 0x1FF]
    cls = (p >> 10) & 0x3F
    if t & 0x1000:
        cls = remap[cls] & 0x3F
    h = 2 * (((t >> 13) & 7) + ((p >> 7) & 1)) + ((p >> 8) & 1)
    return t, p, cls, h

PASS_ALWAYS = {5, 6, 7, 9, 17, 18, 19, 25, 26, 27, 28}

def class_ok(cls, dx, dy):
    if cls in PASS_ALWAYS or cls >= 0x23:
        return True
    if cls == 10:
        return dy == 0
    if cls == 11:
        return dx == 0
    return False

def edge_ok(x, y, dx, dy):
    nx, ny = x + dx, y + dy
    if not (0 <= nx < W and 0 <= ny < H):
        return False
    _t2, p2, c2, h2 = cell(nx, ny)
    if not class_ok(c2, dx, dy):
        return False
    _t1, p1, _c1, h1 = cell(x, y)
    d = abs(h1 - h2)
    if (p1 >> 8) & 1 and (p2 >> 8) & 1:
        d -= 1
    return d < 4

def bfs(src):
    from collections import deque
    seen = {src: 0}
    dq = deque([src])
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in seen and edge_ok(x, y, dx, dy):
                seen[(x + dx, y + dy)] = seen[(x, y)] + 1
                dq.append((x + dx, y + dy))
    return seen

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'route':
        s = bfs((109, 130))
        print('spawn (109,130): reachable', len(s),
              'cells; dist to east-cluster entry (171,110):',
              s.get((171, 110)))
        s2 = bfs((171, 125))
        print('teleport landing (171,125): reachable', len(s2),
              'cells; dist to (171,110):', s2.get((171, 110)),
              '; to (164,119):', s2.get((164, 119)))
    else:
        from collections import Counter
        cnt = Counter()
        for y in range(H):
            for x in range(W):
                cnt[cell(x, y)[2]] += 1
        print('class histogram:', dict(sorted(cnt.items())))
        print('spawn cell (109,130):', cell(109, 130))
        print('pond-village entry (109,124):', cell(109, 124))
        print('teleport landing (171,125):', cell(171, 125))
