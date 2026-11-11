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
    data positions get `Lxxxxxx` labels too, as do immediates (`#$hex`) that load
    a ROM address into an address register (step 1, #16); other immediates,
    displacements, pc-relative operands, and RAM/hardware addresses stay numeric.
  * The whole file is then checked by tools/verify_rebuild.py (byte-identity gate).
"""
import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import capstone

ROM = Path("rop-original.gen")
TABLES_CSV = Path("disasm/tables.csv")  # structured data tables (#14): start,end,prefix,words_per_record
BODIES = Path("disasm/ghidra/function_bodies.txt")
OUT = Path(os.environ.get("ROP_SRC", "disasm/src/rop.s"))  # shift test writes elsewhere (#16 item 3)
VASM = Path("tools/vasm/vasmm68k_mot")
ROM_SIZE = 0x100000
Z80_START, Z80_END = 0x0EBB6E, 0x0ED0E4  # sound driver blob, end exclusive (#78)
EQUATES = Path("disasm/src/equates.s")  # generated: RAM/hardware equates (#16 item 2)
RAM_CSV = Path("disasm/symbols/ram.csv")  # docs-named RAM rows; the rest get ram_sys_<addr>
# Mega Drive hardware registers (standard map). Z80 RAM window $A00000+ is the 68k<->Z80 mailbox (docs/sound.md §13).
HW_NAMES = {
    0xA10001: "sys_version", 0xA10003: "pad_port1_data", 0xA10005: "pad_port2_data",
    0xA10007: "pad_ext_data", 0xA10009: "pad_port1_ctrl", 0xA1000B: "pad_port2_ctrl",
    0xA1000D: "pad_ext_ctrl", 0xA11100: "z80_busreq", 0xA11200: "z80_reset",
    0xC00000: "vdp_data", 0xC00004: "vdp_ctrl", 0xC00008: "vdp_hvcounter",
    0xA000DA: "z80_mailbox_da", 0xA000E6: "z80_mailbox_e6",  # docs/sound.md §13 (tier 0 names)
    0xA10008: "pad_port1_reg08", 0xA1000C: "pad_port2_reg0c",  # IO registers, role not read (tier 0)
}
# Vector-table entries that hold code addresses (#16 item 1). Each is emitted as a label, so a shift moves it.
VEC_PTR = {0x4: 0x200, 0x70: 0x1270, 0x78: 0x1272}  # reset PC; HBlank; VBlank handler
SHIFT = int(os.environ.get("SHIFT", "0"), 0)  # shift test (#16 item 3): padding inserted before the code at $200
SHIFT_AT = 0x200
HDR_SUM = 0x18E    # header checksum word, a symbol set by build/checksum.inc (#16)
RUNTIME_IMM = 0xFD098  # runtime self-check immediate, a symbol too (#16)
RUNTIME_CMP = 0xFD096  # the cmpi.l instruction itself (its listing comment)
RUNTIME_ORIG = 0x8F33608C  # value in the original ROM; the generator only needs to find it once
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


IMM_OP_RE = re.compile(r"^#\$([0-9a-fA-F]+)$")
IMM_PTR_MNEMS = {"movea", "adda", "suba", "cmpa"}  # address-register operations


def imm_pointer_operands(mnem, op):
    """Immediate operands `#$hex` that are ROM addresses: {operand index: value}.

    Only immediates that load/compute a ROM address into an address register
    count (step 1, #16): movea/adda/suba/cmpa, or `move` with an a0-a7
    destination. Two exclusions keep constants numeric:
      * values < $1000 are struct offsets / small counts, not addresses
        (e.g. `adda.l #$2c,a0`, `movea.w #$4,a3`);
      * immediates into data registers are values, not pointers
        (e.g. `move.l #$10000,d1` — a 65536 size, not an address).
    The caller applies the same ROM/not-in-code filter as for abs_operands.
    """
    base = mnem.split(".")[0]
    parts = split_operands(op)
    if len(parts) != 2:
        return {}
    refs = {}
    for idx, operand in enumerate(parts):
        if idx != 0 or not operand.startswith("#"):
            continue
        m = IMM_OP_RE.match(operand)
        if not m:
            continue
        v = int(m.group(1), 16)
        if v < 0x1000:
            continue
        dest = parts[-1]
        if base in IMM_PTR_MNEMS or (base == "move" and re.match(r"^a[0-7]$", dest)):
            refs[idx] = v
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


ABS_LONG = re.compile(r"\$([0-9a-f]{6})\.l\b")


def apply_equates(text):
    """Name every RAM/hardware absolute long operand (#16 item 2). Writes disasm/src/equates.s."""
    named = {}
    if RAM_CSV.exists():
        with RAM_CSV.open(newline="") as fh:
            for r in csv.DictReader(fh):
                named[int(r["addr"], 16)] = r["name"]
    code_lines = [l.split(";", 1)[0] for l in text.splitlines() if l.startswith("\t") and not l.startswith(("\t;", "\tincbin", "\tdc.", "\tdcb", "\tinclude", "\tsection", "\txdef"))]
    used = {int(m.group(1), 16) for l in code_lines for m in ABS_LONG.finditer(l) if int(m.group(1), 16) >= 0xA00000 or int(m.group(1), 16) >= 0xFF0000}
    table = {}
    for a in used:
        if a >= 0xFF0000:
            table[a] = named.get(a, f"ram_sys_{a:06x}")
        elif a in HW_NAMES:
            table[a] = HW_NAMES[a]
    EQUATES.write_text("\n".join(f"{n}\tequ\t${a:06X}" for a, n in sorted(table.items())) + "\n")
    def sub(m):
        v = int(m.group(1), 16)
        return f"{table[v]}.l" if v in table else m.group(0)
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("\t") and not l.startswith(("\t;", "\tincbin", "\tdc.", "\tdcb", "\tinclude", "\tsection", "\txdef")):
            code, sep, com = l.partition(";")
            lines[i] = ABS_LONG.sub(sub, code) + sep + com
    return "\n".join(lines) + "\n"


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
                # immediates that are ROM addresses (step 1, #16): pointer loads
                # into address registers; small offsets / data-register values
                # stay numeric (see imm_pointer_operands).
                for i, t in imm_pointer_operands(mnem, op).items():
                    if t < ROM_SIZE and not any(s <= t <= e for s, e, *_ in code):
                        refs[i] = t
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
            if parts[idx].startswith("#"):
                # immediate: #$hex -> #Label (the '#' prefix is kept)
                parts[idx] = f"#{lab(t)}"
            else:
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
        "\tinclude \"disasm/src/equates.s\"\t; RAM and hardware equates (#16 item 2)",
        "\tinclude \"build/checksum.inc\"\t; RUNTIME_SUM, HEADER_SUM (tools/checksum.py inc, #16)",
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
    label_addrs = targets | entry_names | set(NAMES) | set(VEC_PTR.values())  # every named address gets a label
    labelled = set()

    tables = []
    if TABLES_CSV.exists():
        import csv as _csv
        with TABLES_CSV.open(newline="") as fh:
            for r in _csv.DictReader(fh):
                tables.append((int(r["start"], 16), int(r["end"], 16), r["prefix"], int(r["words_per_record"]), r.get("note") or ""))
    tables.sort()

    def emit_table(ts, te, prefix, wpr):
        """Structured table: one labelled record per wpr words. Lines are dc.w, or dc.b for
        odd bytes and bytes next to a label; a line is cut wherever code refers into the table."""
        rec = wpr * 2
        assert (te - ts) % rec == 0, f"table {ts:#x}-{te:#x} not a whole number of {rec}-byte records"
        out.append(f"\t; table ${ts:06X}-${te - 1:06X}: {(te - ts) // rec} records x {wpr} words")

        def rom_word(a):
            return rom[a] << 8 | rom[a + 1]

        for k in range((te - ts) // rec):
            base = ts + k * rec
            end_rec = base + rec
            out.append(f"{prefix}{k:02d}:")
            if base in label_addrs:  # code refers to this record start by its L label too
                out.append(f"{lab(base)}:")
            addr, kind, vals, line_at = base, None, [], base

            def flush():
                if vals:
                    if kind == "w":
                        out.append(f"\tdc.w {','.join(vals)}\t; table ${line_at:06X}")
                    else:
                        out.append(f"\tdc.b {','.join(vals)}\t; table ${line_at:06X}")

            while addr < end_rec:
                if addr != base and addr in label_addrs:
                    flush()
                    vals = []
                    out.append(f"{lab(addr)}:")
                    line_at = addr
                byte_mode = (addr % 2 == 1) or (addr + 1 in label_addrs and addr + 1 < end_rec)
                want = "b" if byte_mode else "w"
                if vals and want != kind:
                    flush()
                    vals = []
                    line_at = addr
                if not vals:
                    line_at = addr
                kind = want
                if byte_mode:
                    vals.append(f"${rom[addr]:02X}")
                    addr += 1
                else:
                    vals.append(f"${rom_word(addr):04X}")
                    addr += 2
            flush()
            vals = []

    def emit_raw(ts, te, prefix, note):
        """Raw byte blob (words_per_record 0): dc.b lines, cut at code labels; one name label at ts."""
        if note:
            out.append(f"\t; {note}")
        out.append(f"{prefix}:")
        if ts in label_addrs:
            out.append(f"{lab(ts)}:")
        line, line_at = [], ts
        for addr in range(ts, te):
            if addr != ts and addr in label_addrs:
                if line:
                    out.append(f"\tdc.b {','.join(line)}\t; table ${line_at:06X}")
                line, line_at = [], addr
                out.append(f"{lab(addr)}:")
            line.append(f"${rom[addr]:02X}")
            if len(line) == 16:
                out.append(f"\tdc.b {','.join(line)}\t; table ${line_at:06X}")
                line, line_at = [], addr + 1
        if line:
            out.append(f"\tdc.b {','.join(line)}\t; table ${line_at:06X}")

    def emit_data(a, b):
        """Emit data [a,b), splitting it at label addresses; a label at a is emitted too."""
        for k in sorted(VEC_PTR):
            if a <= k < b:
                emit_data(a, k)
                out.append(f"\tdc.l {lab(VEC_PTR[k])}\t; ${k:06X} vector")
                labelled.add(k)
                emit_data(k + 4, b)
                return
        if a < HDR_SUM < b:  # header checksum word is a symbol (#16)
            assert not any(HDR_SUM < t < HDR_SUM + 2 for t in label_addrs), "label inside header word"
            emit_data(a, HDR_SUM)
            out.append(f"\tdc.w HEADER_SUM\t; ${HDR_SUM:06X}")
            emit_data(HDR_SUM + 2, b)
            return
        for ts, te, prefix, wpr, note in tables:
            if a < te and b > ts:
                if a < ts:
                    emit_data(a, ts)
                assert a <= ts and te <= b, f"table {ts:#x}-{te:#x} straddles a data piece"
                if wpr == 0:
                    emit_raw(ts, te, prefix, note)
                else:
                    emit_table(ts, te, prefix, wpr)
                if te < b:
                    emit_data(te, b)
                return
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
            out.append(f'\tincbin "build/z80_snd_driver.bin"\t; ${Z80_START:06X}')
            if b > Z80_END:
                emit_data(Z80_END, b)
            return
        cur = a
        for t in sorted(t for t in label_addrs if a <= t < b):
            if t > cur:
                out.append(f"\t; data ${cur:06X}-${t - 1:06X}")
                emit_bytes(cur, t)
                cur = t
            if t not in labelled:
                out.append(f"{lab(t)}:")
                labelled.add(t)
        if b > cur:
            out.append(f"\t; data ${cur:06X}-${b - 1:06X}")
            emit_bytes(cur, b)

    def emit_bytes(a, b):
        """All-$FF slices become `dcb.b` padding source; everything else stays an incbin slice."""
        if rom[a:b] == b"\xff" * (b - a):
            out.append(f"\tdcb.b ${b - a:X},$FF\t; ${a:06X}")
        else:
            out.append(f'\tincbin "rop-original.gen",${a:06X},${b - a:X}')

    for start, kind, payload in pieces:
        if start > pos:
            emit_data(pos, start)
        if SHIFT and start == SHIFT_AT:
            out.append(f"\tdcb.b ${SHIFT:X},$FF\t; shift test padding (SHIFT={SHIFT:#x})")
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
    tail_end = ROM_SIZE - SHIFT  # padding shifts the image; the last SHIFT bytes are $FF and are dropped
    if SHIFT:
        assert all(b == 0xFF for b in ROM.read_bytes()[tail_end:]), "shift would drop non-padding bytes"
    if pos < tail_end:
        emit_data(pos, tail_end)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(out) + "\n"
    text = apply_equates(text)
    cmp_old = f"cmpi.l #${RUNTIME_ORIG:08x},d0\t; ${RUNTIME_CMP:06X}"
    assert text.count(cmp_old) == 1, "runtime self-check compare not found"
    text = text.replace(cmp_old, f"cmpi.l #RUNTIME_SUM,d0\t; ${RUNTIME_CMP:06X}")
    OUT.write_text(text)
    n_conv = sum(1 for v in converted.values() if v)
    print(f"wrote {OUT}: {len(code)} code ranges, {n_conv} mnemonic instructions, "
          f"{len(targets)} targets labelled ({n_abs_labelled} non-flow absolute operands)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
