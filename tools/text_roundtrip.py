#!/usr/bin/env python3
"""text_roundtrip.py — export the dialogue records to editable text and re-encode to identical bytes (issue #18).

Export format (assets/text/dialogue.txt), one line per record:
  rec N | tok|tok|...
  tok = dictionary word, plus {s} when the entry's separator selector s (1..3) is non-zero.
  Selector 0 has no tag. Words come from disasm/text/dictionary.txt (1-based, unique).
Re-encode: each token -> (index from the dictionary, selector) -> u16 -> the record's array bytes.
The check passes when every record's re-encoded bytes equal the ROM bytes at 0x0E0A18 + offset.
Read only with respect to the ROM; writes assets/text/dialogue.txt.
"""
import re
import struct
import sys
from pathlib import Path

ROM = Path('rop-original.gen')
DICT = Path('disasm/text/dictionary.txt')
OUT = Path('assets/text/dialogue.txt')
REC, N, ARR = 0x0DDBD8, 1184, 0x0E0A18
SEL = re.compile(r'\{([123])\}')
IDX = re.compile(r'@(\d+)$')


def load_dict():
    words = []
    for line in DICT.read_text().splitlines():
        if line.strip():
            words.append(line.split("'", 1)[1].rsplit("'", 1)[0])
    index = {}
    for i, w in enumerate(words, 1):
        index.setdefault(w, i)
    return words, index


def export(rom, words):
    first = {}
    for i, w in enumerate(words, 1):
        first.setdefault(w, i)
    lines = []
    for k in range(N):
        off, length, typ = struct.unpack('>IIH', rom[REC + 10 * k:REC + 10 * k + 10])
        base = ARR + off
        toks = []
        for j in range((length >> 1) + 1):
            e = struct.unpack('>H', rom[base + 2 * j:base + 2 * j + 2])[0]
            idx, sel = e & 0x3FFF, e >> 14
            w = words[idx - 1] if 1 <= idx <= len(words) else f'<idx{idx}>'
            # the dictionary has repeated words; a non-first occurrence keeps its index as @N
            tag = f'@{idx}' if (w in first and first[w] != idx) else ''
            toks.append(w + (f'{{{sel}}}' if sel else '') + tag)
        lines.append(f'rec {k} | ' + '|'.join(toks))
    return lines


def reencode(lines, index):
    out = {}
    for line in lines:
        head, toks = line.split(' | ', 1)
        k = int(head.split()[1])
        vals = []
        for t in toks.split('|'):
            idx_tag = None
            m = IDX.search(t)
            if m:
                idx_tag = int(m.group(1))
                t = t[:m.start()]
            m = SEL.search(t)
            sel = int(m.group(1)) if m else 0
            word = t[:m.start()] if m else t
            if idx_tag is not None:
                idx = idx_tag
            elif word.startswith('<idx') and word.endswith('>'):
                idx = int(word[4:-1])          # out-of-dictionary entry, kept as its raw index (record 1183)
            else:
                idx = index[word]
            vals.append((idx & 0x3FFF) | (sel << 14))
        out[k] = struct.pack('>' + 'H' * len(vals), *vals)
    return out


def main():
    rom = ROM.read_bytes()
    words, index = load_dict()
    lines = export(rom, words)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines) + '\n')
    rebuilt = reencode(OUT.read_text().splitlines(), index)
    same = 0
    diff = []
    for k in range(N):
        off, length, typ = struct.unpack('>IIH', rom[REC + 10 * k:REC + 10 * k + 10])
        base = ARR + off
        n = (length >> 1) + 1
        orig = rom[base:base + 2 * n]
        if rebuilt.get(k) == orig:
            same += 1
        else:
            diff.append(k)
    print(f'exported {N} records to {OUT}; re-encoded identical: {same} of {N}; differing: {diff[:5]}')
    return 0 if not diff else 1


if __name__ == '__main__':
    sys.exit(main())
