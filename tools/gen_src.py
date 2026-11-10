#!/usr/bin/env python3
"""gen_src.py — generate disasm/src/rop.s from Ghidra's verified body ranges (issue #012).

Inputs:  disasm/ghidra/function_bodies.txt  (RANGE entry start end_inclusive)
         rop-original.gen                    (the user's 1 MB ROM dump)
         tools/vasm/vasmm68k_mot             (tools/install_vasm.sh)
Output:  disasm/src/rop.s                    (generated; do not hand-edit)

Rules:
  * Outside Ghidra body ranges everything is data: `incbin` slices of the ROM.
  * Inside a body range each instruction is either a real mnemonic or a raw `dc.w`
    fallback. A mnemonic is used only if vasm assembles it, placed at its real ROM
    address, to exactly the original bytes (checked for every instruction in one run,
    via the assembler listing).
  * Branch and pc-relative targets that are instruction starts or data positions get
    labels (`FUN_xxxxxx` for function entries, `Lxxxxxx` otherwise); data slices are
    split at them.
  * The whole file is then checked by tools/verify_rebuild.py (byte-identity gate).
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import capstone

ROM = Path("rop-original.gen")
BODIES = Path("disasm/ghidra/function_bodies.txt")
OUT = Path("disasm/src/rop.s")
VASM = Path("tools/vasm/vasmm68k_mot")
ROM_SIZE = 0x100000
TARGET_RE = re.compile(r"\$([0-9a-fA-F]+)")


def load_ranges():
    rows = []
    for line in BODIES.read_text().splitlines():
        if line.startswith("RANGE "):
            _, entry, start, end = line.split()
            rows.append((int(start, 16), int(end, 16), int(entry, 16)))
    rows.sort()
    merged = []
    for start, end, entry in rows:
        if merged and start <= merged[-1][1]:
            prev = merged[-1]
            merged[-1] = (prev[0], max(prev[1], end), prev[2])
        else:
            merged.append((start, end, entry))
    return merged


def decode(md, rom, start, end):
    """Instructions in [start, end] as (addr, size, mnemonic, op_str); tail bytes not decoded."""
    out = []
    pos = start
    for i in md.disasm(bytes(rom[start:end + 1]), start):
        out.append((i.address, i.size, i.mnemonic, i.op_str))
        pos = i.address + i.size
    return out, pos


def is_flow(mnem, op):
    return mnem.startswith(("b", "j", "db")) or "(pc)" in op or "pc)" in op


def abs_text(mnem, op):
    return f"{mnem} {op.replace(', ', ',')}".strip()


def verify_all(cands, rom):
    """cands: {addr: text}. Return addresses whose text assembles, placed at addr, to the ROM bytes.

    One assembler run per instruction: vasm's binary output cannot hold several
    org-placed sections at once. About 2 ms per run.
    """
    ok = set()
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "i.s"
        obj = Path(d) / "i.bin"
        for addr, text in sorted(cands.items()):
            src.write_text(f"\tsection t,code\n\torg ${addr:X}\n\t{text}\n")
            r = subprocess.run([str(VASM), "-Fbin", "-m68000", "-no-opt", "-o", str(obj), str(src)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not obj.exists():
                continue
            # obj holds the section from its origin; compare only the instruction bytes
            data = obj.read_bytes()
            n = len(data)
            if n and data == bytes(rom[addr:addr + n]):
                ok.add(addr)
    return ok


def main():
    rom = ROM.read_bytes()
    assert len(rom) == ROM_SIZE, "rop-original.gen must be the 1 MB dump"
    ranges = load_ranges()
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)

    # 1. decode all code ranges
    code = []   # (start, end, [insns], tail_start)
    insn_starts = set()
    for start, end, entry in ranges:
        insns, tail = decode(md, rom, start, end)
        code.append((start, end, entry, insns, tail))
        insn_starts.update(a for a, _, _, _ in insns)

    # 2. candidate mnemonics (with absolute targets), verified in one assembler run
    cands = {}
    for start, end, entry, insns, tail in code:
        for addr, size, mnem, op in insns:
            if "(pc)" in op or "pc)" in op or is_flow(mnem, op):
                pass
            if size % 2:
                continue
            cands[addr] = abs_text(mnem, op)
    ok = verify_all(cands, rom)

    # 3. label targets for converted instructions that reference another address
    targets = set()
    converted = {}
    for start, end, entry, insns, tail in code:
        for addr, size, mnem, op in insns:
            if addr in ok and is_flow(mnem, op):
                tgt = set(int(m.group(1), 16) for m in TARGET_RE.finditer(op))
                # only label targets we can place: instruction starts or data positions
                if all((t in insn_starts) or (t < ROM_SIZE and not any(s <= t <= e for s, e, *_ in code))
                       for t in tgt):
                    targets |= tgt
                    converted[addr] = True
                else:
                    converted[addr] = False
            elif addr in ok:
                converted[addr] = True
            else:
                converted[addr] = False

    def name(t):
        for _, _, entry, *_ in code:
            pass
        return f"L{t:06X}"

    entry_names = {e for _, _, e, *_ in code}

    # 4. emit
    out = [
        "; Rings of Power (Mega Drive, USA/Europe) — GENERATED by tools/gen_src.py.",
        "; Do not hand-edit. Code: Ghidra function bodies (disasm/ghidra/function_bodies.txt).",
        "; Data: incbin slices of rop-original.gen. Gate: tools/verify_rebuild.py.",
        "\tsection rom,data",
        "\txdef rom_start",
        "rom_start:",
    ]
    # Build a sorted list of (addr, kind, payload) pieces covering 0..ROM_SIZE.
    pieces = []
    for start, end, entry, insns, tail in code:
        pieces.append((start, "code", (end, entry, insns, tail)))
    pieces.sort()
    pos = 0
    label_addrs = targets | entry_names
    labelled = set()

    def emit_data(a, b):
        """Emit data [a,b) split at label addresses."""
        cur = a
        cuts = sorted(t for t in label_addrs if a < t < b)
        for t in cuts + [b]:
            if t > cur:
                out.append(f"\t; data ${cur:06X}-${t - 1:06X}")
                out.append(f'\tincbin "rop-original.gen",${cur:06X},${t - cur:X}')
            if t < b:
                out.append(f"L{t:06X}:")
                labelled.add(t)
            cur = t

    for start, kind, payload in pieces:
        if start > pos:
            emit_data(pos, start)
        end, entry, insns, tail = payload
        out.append(f"\t; code ${start:06X}-${end:06X}")
        for addr, size, mnem, op in insns:
            if addr in label_addrs and addr not in labelled:
                out.append(f"{'FUN_%06x' % addr if addr in entry_names else 'L%06X' % addr}:")
                labelled.add(addr)
            if converted.get(addr):
                text = abs_text(mnem, op)
                # rewrite targets to labels
                text = TARGET_RE.sub(lambda m: f"L{int(m.group(1), 16):06X}"
                                     if int(m.group(1), 16) in label_addrs else m.group(0), text)
                out.append(f"\t{text}\t; ${addr:06X}")
            else:
                w = rom[addr:addr + size]
                raw = ",".join(f"${w[i]:02X}{w[i + 1]:02X}" for i in range(0, len(w) - len(w) % 2, 2))
                if len(w) % 2:
                    raw += (("," if raw else "") + f"${w[-1]:02X}")
                    out.append(f"\tdc.b {raw}\t; {mnem} {op}".rstrip())
                else:
                    out.append(f"\tdc.w {raw}\t; {mnem} {op}".rstrip())
        if tail < end + 1:
            t = rom[tail:end + 1]
            out.append(f"\t; undecoded tail ${tail:06X}-${end:06X}")
            raw = ",".join(f"${t[i]:02X}{t[i + 1]:02X}" for i in range(0, len(t) - len(t) % 2, 2))
            if raw:
                out.append(f"\tdc.w {raw}")
            if len(t) % 2:
                out.append(f"\tdc.b ${t[-1]:02X}")
        pos = end + 1
    if pos < ROM_SIZE:
        emit_data(pos, ROM_SIZE)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n")
    n_conv = sum(1 for v in converted.values() if v)
    print(f"wrote {OUT}: {len(code)} code ranges, {n_conv} mnemonic instructions, "
          f"{len(targets)} branch/pc targets labelled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
