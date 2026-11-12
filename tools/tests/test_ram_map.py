#!/usr/bin/env python3
"""Tests for tools/ram_map.py (playbook T-70). Fixture-only: no ROM needed.

Checks that both operand forms are counted: literal $ffxxxx.w/.l and the
symbolic names from ram.csv (ram_<subsys>_<thing>.l), and that the routine
credited is the nearest non-local label.

pytest-style. Also runs standalone:
  python3 tools/tests/test_ram_map.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ram_map  # noqa: E402

ROP = """\
verb_exec:
\tmove.w $ff0134.w,d0\t; $00AAAA
\tmove.w ram_sys_field_0134.l,d1\t; named, same address
L00AB00:
\tclr.w ram_sys_field_0134.l\t; local label, still verb_exec
menu_format:
\tmove.l ram_sys_field_0134.l,d2\t; $00BBBB
\tcmp.w #$ff0134,d3\t; immediate, not an operand
"""
NAMES = {'ram_sys_field_0134': 0xFF0134}


def test_counts_both_operand_forms():
    refs = ram_map.count(ROP, NAMES)
    r = refs[0xFF0134]
    assert r['count'] == 4, r['count']


def test_credits_nearest_routine():
    refs = ram_map.count(ROP, NAMES)
    assert refs[0xFF0134]['users'] == ['verb_exec', 'menu_format'], refs[0xFF0134]['users']


def test_unknown_symbol_ignored():
    refs = ram_map.count('foo:\n\tmove.w ram_nope.l,d0\n', NAMES)
    assert refs == {} or sum(r['count'] for r in refs.values()) == 0


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print('ok', name)
