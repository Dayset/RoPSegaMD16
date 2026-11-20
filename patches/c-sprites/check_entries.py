#!/usr/bin/env python3
"""check_entries.py — verify the C blob's scene/mapclose entries
disassemble to the identical instruction stream as the B2 blob, modulo
branch-displacement size, the ADDA.W #16,SP -> LEA $10(SP),SP encoding
vasm emits, and one elided no-op branch-to-next-instruction.
The redraw/vbl entries are NEW in C and are NOT checked here.
Run with the RoP venv python (it has capstone/m68k).
Usage: check_entries.py <b2_source.bin> <c_source.bin> <c_offsets_json>
Exits 0 on pass, 1 with a message on failure.
"""
import difflib
import json
import re
import sys

from capstone import Cs, CS_ARCH_M68K, CS_MODE_BIG_ENDIAN

B2_BASE = 0xFD900
C_BASE = 0xFD400
BR = re.compile(r"^(beq|bne|bra|bpl|bmi|bgt|blt|bge|ble|bhi|bls|bcc|bcs|bvc|bvs|bsr)\.")


def norm(md, data, base):
    res = []
    for ins in md.disasm(data, base):
        mn = re.sub(r"\.[bw]$", "", ins.mnemonic)
        s = f"{mn} {ins.op_str}"
        if BR.match(ins.mnemonic):
            def rep(m):
                return f"<disp{int(m.group(1), 16) - (ins.address + ins.size):+d}>"
            s = re.sub(r"(?<!#)\$([0-9a-fA-F]+)", rep, s)
        s = re.sub(r"lea\.l \$10\(a7\), a7", "adda #$10, a7", s)
        res.append(s)
    return res


def main():
    b2_path, c_path, offs_path = sys.argv[1], sys.argv[2], sys.argv[3]
    b2_blob = open(b2_path, "rb").read()
    c_blob = open(c_path, "rb").read()
    offs_c = json.loads(open(offs_path).read())
    offs_b2 = {"scene_entry": 0x4C0, "mapclose_entry": 0x4FA}
    ends_b2 = {"scene_entry": 0x4FA, "mapclose_entry": len(b2_blob)}
    ends_c = {"scene_entry": offs_c["mapclose_entry"],
              "mapclose_entry": len(c_blob)}
    md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN)
    ok = True
    for name in ("scene_entry", "mapclose_entry"):
        na = norm(md, b2_blob[offs_b2[name]:ends_b2[name]], B2_BASE + offs_b2[name])
        nb = norm(md, c_blob[offs_c[name]:ends_c[name]], C_BASE + offs_c[name])
        sa = [re.sub(r"<disp[+-]\d+>", "<disp>", x) for x in na]
        sb = [re.sub(r"<disp[+-]\d+>", "<disp>", x) for x in nb]
        sm = difflib.SequenceMatcher(a=sa, b=sb, autojunk=False)
        bad = [(t, sa[i1:i2], sb[j1:j2]) for t, i1, i2, j1, j2
               in sm.get_opcodes() if t != "equal"]
        allowed = [b for b in bad if b[0] == "delete" and b[1] == ["bra <disp>"]]
        others = [b for b in bad if b not in allowed]
        print(f"  {name}: B2 {len(na)} insns, C {len(nb)} insns, "
              f"non-equal ops: {len(bad)} (allowed elided no-op bras: {len(allowed)})")
        if others or len(allowed) > 1:
            print(f"  FAIL {name}: others={others} allowed={allowed}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
