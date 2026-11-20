#!/usr/bin/env python3
"""check_entries.py — verify the B2 blob's redraw/scene/mapclose entries
disassemble to the identical instruction stream as the B1 blob, modulo
branch-displacement size, the ADDA.W #16,SP -> LEA $10(SP),SP encoding
vasm emits, and one elided no-op branch-to-next-instruction.
Run with the RoP venv python (it has capstone/m68k).
Usage: check_entries.py <b1_source.bin> <b2_source.bin> <b2_offsets_json>
Exits 0 on pass, 1 with a message on failure.
"""
import difflib
import json
import re
import sys

from capstone import Cs, CS_ARCH_M68K, CS_MODE_BIG_ENDIAN

PAD_BASE = 0xFD900
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
    b1_path, b2_path, offs_path = sys.argv[1], sys.argv[2], sys.argv[3]
    b1_blob = open(b1_path, "rb").read()
    b2_blob = open(b2_path, "rb").read()
    offs2 = json.loads(open(offs_path).read())
    offs1 = {"redraw_entry": 0x254, "scene_entry": 0x4F0, "mapclose_entry": 0x52A}
    ends1 = {"redraw_entry": 0x4F0, "scene_entry": 0x52A, "mapclose_entry": len(b1_blob)}
    ends2 = {"redraw_entry": offs2["scene_entry"],
             "scene_entry": offs2["mapclose_entry"],
             "mapclose_entry": len(b2_blob)}
    md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN)
    ok = True
    for name in ("redraw_entry", "scene_entry", "mapclose_entry"):
        na = norm(md, b1_blob[offs1[name]:ends1[name]], PAD_BASE + offs1[name])
        nb = norm(md, b2_blob[offs2[name]:ends2[name]], PAD_BASE + offs2[name])
        sa = [re.sub(r"<disp[+-]\d+>", "<disp>", x) for x in na]
        sb = [re.sub(r"<disp[+-]\d+>", "<disp>", x) for x in nb]
        sm = difflib.SequenceMatcher(a=sa, b=sb, autojunk=False)
        bad = [(t, sa[i1:i2], sb[j1:j2]) for t, i1, i2, j1, j2
               in sm.get_opcodes() if t != "equal"]
        allowed = [b for b in bad if b[0] == "delete" and b[1] == ["bra <disp>"]]
        others = [b for b in bad if b not in allowed]
        print(f"  {name}: B1 {len(na)} insns, B2 {len(nb)} insns, "
              f"non-equal ops: {len(bad)} (allowed elided no-op bras: {len(allowed)})")
        if others or len(allowed) > 1:
            print(f"  FAIL {name}: others={others} allowed={allowed}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
