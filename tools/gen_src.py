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
  * Non-flow absolute operands (`$hex` with a `.l`/`.w` suffix) that point at ROM
    data positions get `Lxxxxxx` labels too; immediates, displacements,
    pc-relative operands, and RAM/hardware addresses stay numeric.
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
Z80_START, Z80_END = 0x0EBB6E, 0x0ED0E4  # sound driver blob, end exclusive (#78)
TARGET_RE = re.compile(r"\$([0-9a-fA-F]+)")
ABS_OP_RE = re.compile(r"^\$([0-9a-fA-F]+)(\.[lwb])?$")


def split_operands(op):
    """Split an op_str on top-level commas (commas inside parentheses don't split)."""
    parts, cur, depth = [], "", 0
    for ch in op:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return [p.strip() for p in parts]


def abs_operands(op):
    """Absolute-address operands of a non-flow instruction: {operand index: value}.

    Only a bare `$hex` operand (with an optional `.l`/`.w` size suffix) counts.
    Immediates (`#$..`), displacements (`$xx(An)`), and pc-relative operands are
    excluded — those must stay numeric. The caller decides which values are
    labellable (ROM data positions); the rest stay numeric.
    """
    refs = {}
    for idx, operand in enumerate(split_operands(op)):
        if operand.startswith("#") or "(pc" in operand or "(" in operand:
            continue
        m = ABS_OP_RE.match(operand)
        if m:
            refs[idx] = int(m.group(1), 16)
    return refs




def load_names():
    """Routine names from disasm/symbols/*.csv (addr,name,tier,note). Names must be unique."""
    import csv
    names = {}
    for path in sorted([*Path('disasm/symbols').glob('code_*.csv'), Path('disasm/symbols/extra.csv'), Path('disasm/symbols/auto.csv')]):
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                addr = int(row["addr"], 16)
                name = row["name"]
                if name in names.values():
                    raise SystemExit(f"duplicate routine name {name} ({path})")
                if addr in names:
                    raise SystemExit(f"duplicate address 0x{addr:06X} ({path})")
                names[addr] = name
    return names


EXTRA_RANGES = Path("disasm/ghidra/extra_ranges.txt")


def load_ranges():
    rows = []
    sources = [BODIES] + ([EXTRA_RANGES] if EXTRA_RANGES.exists() else [])
    for src in sources:
        for line in src.read_text().splitlines():
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


BRANCHES = {"bra", "bsr", "bhi", "bls", "bcc", "bcs", "bhs", "blo", "bne", "beq", "bvc", "bvs",
            "bpl", "bmi", "bge", "blt", "bgt", "ble", "jmp", "jsr"}
DBRANCHES = {"dbt", "dbf", "dbra", "dbhi", "dbls", "dbcc", "dbcs", "dbne", "dbeq", "dbvc", "dbvs",
             "dbpl", "dbmi", "dbge", "dblt", "dbgt", "dble"}


def is_flow(mnem, op):
    """Branch, jump, or pc-relative operand: the only operands whose hex may become a label.

    Capstone's mnemonic carries the size suffix (bne.b, bra.w, bsr.b), while the
    BRANCHES/DBRANCHES sets hold bare names, so strip the suffix before matching;
    otherwise every suffixed conditional branch is missed and its target stays raw.
    """
    base = mnem.split(".")[0]
    return base in BRANCHES or base in DBRANCHES or "(pc" in op


BITOPS = {"btst", "bset", "bclr", "bchg"}


def abs_text(mnem, op):
    # vasm rejects a size suffix on bit operations: the size is implied (.b on memory, .l on Dn)
    if mnem.split(".")[0] in BITOPS:
        mnem = mnem.split(".")[0]
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
    global NAMES
    NAMES = load_names()
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
    # Indexed pc-relative jumps jmp d8(pc,Xn): vasm measures a "$addr(pc)" target from the
    # instruction's own address, so the displacement is written explicitly as "*+N", where
    # N = d8 + 2 (* is the instruction address). N comes from the extension word in the ROM.
    alt = {}
    for start, end, entry, insns, tail in code:
        for addr, size, mnem, op in insns:
            if mnem == "jmp" and "(pc," in op and size == 4:
                ext = rom[addr + 2]
                d8 = ext - 256 if ext >= 128 else ext
                index = op.split("(pc,", 1)[1]
                alt[addr] = f"jmp *{d8 + 2:+d}(pc,{index}"
    alt_ok = verify_all(alt, rom)
    texts = {a: alt[a] for a in alt_ok}
    ok |= alt_ok

    # 3. label targets for converted instructions that reference another address
    targets = set()
    converted = {}
    abs_refs = {}   # addr -> {operand index: target} for non-flow absolute operands
    for start, end, entry, insns, tail in code:
        for addr, size, mnem, op in insns:
            if addr in alt_ok:
                converted[addr] = True
            elif addr in ok and is_flow(mnem, op):
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
                # non-flow: absolute operands pointing at ROM data get labels too.
                # Only the collected operands are ever rewritten (step 3b); an
                # instruction with a RAM/hardware operand stays converted and
                # that operand stays numeric.
                refs = {i: t for i, t in abs_operands(op).items()
                        if t < ROM_SIZE and not any(s <= t <= e for s, e, *_ in code)}
                if refs:
                    abs_refs[addr] = refs
            else:
                converted[addr] = False

    # 3a. computed-jump targets (#8): a dispatch is
    #   cmp.l #N,dX ; bcc default ; ... ; move.w T(pc,d0.w),d0 ; jmp *+2(pc,d0.w)
    # with N table entries at T, each a signed word offset from the jmp's extension word
    # (jmp address + 2). Each target that lands on a decoded instruction start is labelled.
    # Entries that do not land on an instruction start are counted and left unlabelled.
    dispatch_ok, dispatch_bad = set(), 0
    for start, end, entry, insns, tail in code:
        for i, (addr, size, mnem, op) in enumerate(insns):
            if not (mnem == "jmp" and "(pc," in op and size == 4):
                continue
            base = count = None
            for j in range(i - 1, max(-1, i - 8), -1):
                pa, ps, pm, po = insns[j]
                pm = pm.split(".")[0]
                po = po.replace(" ", "")
                if base is None and pm == "move" and "(pc,d0.w),d0" in po and ps == 4:
                    m = re.match(r"\$?([0-9A-Fa-f]+)\(pc,d0\.w\),d0", po)
                    if m:
                        base = int(m.group(1), 16)
                elif count is None and pm == "cmp" and po.startswith("#"):
                    m = re.match(r"#\$?([0-9A-Fa-f]+),d0", po)
                    if m:
                        count = int(m.group(1), 16)
                if base is not None and count is not None:
                    break
            if base is None or count is None or count > 256:
                dispatch_bad += 1
                continue
            for k in range(count):
                w = int.from_bytes(rom[base + 2 * k:base + 2 * k + 2], "big", signed=True)
                t = addr + 2 + w
                if t in insn_starts:
                    dispatch_ok.add(t)
                else:
                    dispatch_bad += 1
    targets |= dispatch_ok
    print(f"dispatch targets: {len(dispatch_ok)} labelled, {dispatch_bad} unresolved entries")

    def name(t):
        for _, _, entry, *_ in code:
            pass
        return f"L{t:06X}"

    entry_names = {e for _, _, e, *_ in code}

    def lab(t):
        """One name per address, used for both definitions and references."""
        if t in NAMES:
            return NAMES[t]
        return f"FUN_{t:06x}" if t in entry_names else f"L{t:06X}"

    # 3b. verify the labelled form of each rewritten non-flow instruction assembles
    # to the same bytes (the .l/.w suffix forces the mode; prove it per instruction).
    # A failure reverts that instruction to its numeric operands and drops its
    # targets, so no label is defined that nothing references.
    def verify_labelled(addr, text, size):
        labs = set(re.findall(r"\b(?:FUN_[0-9a-f]{6}|L[0-9A-F]{6})\b", text))
        if not labs:
            return True
        eqs = []
        for lname in sorted(labs):
            v = int(lname[4:] if lname.startswith("FUN_") else lname[1:], 16)
            eqs.append(f"{lname} equ ${v:X}")
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "i.s"
            obj = Path(d) / "i.bin"
            src.write_text("\n".join(eqs) + f"\n\tsection t,code\n\torg ${addr:X}\n\t{text}\n")
            r = subprocess.run([str(VASM), "-Fbin", "-m68000", "-no-opt", "-o", str(obj), str(src)],
                               capture_output=True, text=True)
            if r.returncode != 0 or not obj.exists():
                return False
            data = obj.read_bytes()
            # length must match too: a shorter encoding that happens to share a
            # prefix with the original would otherwise pass the byte compare
            return len(data) == size and data == bytes(rom[addr:addr + size])

    insn_by_addr = {}
    for start, end, entry, insns, tail in code:
        for addr, size, mnem, op in insns:
            insn_by_addr[addr] = (mnem, op, size)

    abs_labelled_text = {}   # addr -> labelled text, for rewrites that verified
    n_abs_labelled = 0
    for addr, refs in list(abs_refs.items()):
        mnem, op, size = insn_by_addr[addr]
        parts = split_operands(op)
        for idx, t in refs.items():
            m = ABS_OP_RE.match(parts[idx])
            parts[idx] = f"{lab(t)}{m.group(2) or ''}"
        text = f"{mnem} {','.join(parts)}".strip()
        if verify_labelled(addr, text, size):
            abs_labelled_text[addr] = text
            targets |= set(refs.values())
            n_abs_labelled += len(refs)
        else:
            del abs_refs[addr]

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
    label_addrs = targets | entry_names | set(NAMES)  # every named address gets a label
    labelled = set()

    def emit_data(a, b):
        """Emit data [a,b), splitting it at label addresses; a label at a is emitted too."""
        if a < Z80_END and b > Z80_START:
            # Z80 sound driver: assembled from disasm/z80/snd_driver.s by tools/build.sh (#78)
            if a < Z80_START:
                emit_data(a, Z80_START)
            inner = [t for t in label_addrs if Z80_START < t < Z80_END]
            assert not inner, f"68000 label inside Z80 blob: {[hex(t) for t in inner]}"
            if Z80_START in label_addrs and Z80_START not in labelled:
                out.append(f"{lab(Z80_START)}:")
                labelled.add(Z80_START)
            out.append("\t; Z80 sound driver: disasm/z80/snd_driver.s -> build/z80_snd_driver.bin (tools/z80_carve.py)")
            out.append('\tincbin "build/z80_snd_driver.bin"')
            if b > Z80_END:
                emit_data(Z80_END, b)
            return
        cur = a
        for t in sorted(t for t in label_addrs if a <= t < b):
            if t > cur:
                out.append(f"\t; data ${cur:06X}-${t - 1:06X}")
                out.append(f'\tincbin "rop-original.gen",${cur:06X},${t - cur:X}')
                cur = t
            if t not in labelled:
                out.append(f"{lab(t)}:")
                labelled.add(t)
        if b > cur:
            out.append(f"\t; data ${cur:06X}-${b - 1:06X}")
            out.append(f'\tincbin "rop-original.gen",${cur:06X},${b - cur:X}')

    for start, kind, payload in pieces:
        if start > pos:
            emit_data(pos, start)
        end, entry, insns, tail = payload
        out.append(f"\t; code ${start:06X}-${end:06X}")
        for addr, size, mnem, op in insns:
            if addr in label_addrs and addr not in labelled:
                out.append(f"{lab(addr)}:")
                labelled.add(addr)
            if converted.get(addr):
                text = texts.get(addr) or abs_text(mnem, op)
                # rewrite targets to labels
                if is_flow(mnem, op):
                    # only branch and pc-relative operands take label targets; immediates stay numeric
                    text = TARGET_RE.sub(lambda m: lab(int(m.group(1), 16))
                                         if int(m.group(1), 16) in label_addrs else m.group(0), text)
                elif addr in abs_labelled_text:
                    # non-flow: only the collected absolute operands were rewritten
                    text = abs_labelled_text[addr]
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
          f"{len(targets)} targets labelled ({n_abs_labelled} non-flow absolute operands)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
