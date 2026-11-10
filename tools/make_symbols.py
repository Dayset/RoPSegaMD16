#!/usr/bin/env python3
"""make_symbols.py — one symbol source, three outputs (GitHub issue #20).

Input:  disasm/names.txt   lines "0xADDR name  # source"  (the only naming source)
Outputs (written to disasm/symbols/):
  names.csv      address,name,source         — Ghidra import / spreadsheets
  emu.sym        "ADDR name" per line        — emulator/debugger symbol file
  asm-labels.txt "name: ; $ADDR" per line    — reference list for the asm source
Fails loudly on a duplicate name or duplicate address.
Usage: python3 tools/make_symbols.py
"""
import re
import sys
from pathlib import Path

LINE = re.compile(r'^(0x[0-9A-Fa-f]{1,8})\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:#\s*(.*))?$')


def main():
    names = Path('disasm/names.txt')
    seen_addr, seen_name, rows = {}, {}, []
    for n, raw in enumerate(names.read_text().splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        m = LINE.match(s)
        if not m:
            sys.exit(f'{names}:{n}: cannot parse: {raw!r}')
        addr, name, src = int(m.group(1), 16), m.group(2), (m.group(3) or '').strip()
        if addr in seen_addr:
            sys.exit(f'{names}:{n}: address 0x{addr:06X} already named {seen_addr[addr]}')
        if name in seen_name:
            sys.exit(f'{names}:{n}: name {name} already used at 0x{seen_name[name]:06X}')
        seen_addr[addr] = name
        seen_name[name] = addr
        rows.append((addr, name, src))
    rows.sort()
    out = Path('disasm/symbols')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'names.csv').write_text(
        'address,name,source\n' + ''.join(f'0x{a:06X},{nm},"{s}"\n' for a, nm, s in rows))
    (out / 'emu.sym').write_text(''.join(f'{a:06X} {nm}\n' for a, nm, _ in rows))
    (out / 'asm-labels.txt').write_text(''.join(f'{nm}: ; ${a:06X}\n' for a, nm, _ in rows))
    print(f'symbols: {len(rows)} names (unique addresses and names)')


if __name__ == '__main__':
    main()
