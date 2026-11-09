#!/usr/bin/env python3
"""Distance-fix patch builder — issue #022, candidate A.

Evidence-first, two-step workflow (see README.md in this folder):

  1. locate:  verify the ROM (size + MD5), disassemble the damage
              routine $3B1EE-$3B408 with Capstone, and print every
              divs/divu and every load of the constant 1, with file
              offsets and raw bytes. REVIEW THIS OUTPUT. The repo's
              docs (docs/logic.md SS5.1) prove the semantics of the
              dead distance term -- d1 = 1; divs (dist+2), d1 -> 0 --
              but do NOT record the exact bytes of that block, so
              this script refuses to guess a patch site.

  2. apply:   NOT implemented as a blind patch. Once `locate` has
              pinned the site and the fix encoding is confirmed
              (inline operand change, or a >=6-byte jsr hook to a
              trampoline at 0xFD138+, after the music-off
              trampolines), implement the byte change in the
              `apply_confirmed()` function below, reusing
              tools/checksum.py fix-all for both checksums and
              emitting the IPS + changed-bytes.txt next to this
              script. Until then `apply` exits with an explanation.

Usage:
    build_patch.py locate <rop-original.gen>
    build_patch.py apply  <rop-original.gen>   # guarded, see above

Requires: capstone (the tools/.venv from issue #001) for `locate`.
The ROM itself is never modified: all work happens on a copy.
"""
import hashlib
import struct
import sys

EXPECTED_SIZE = 1_048_576
EXPECTED_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"
ROUTINE_START = 0x3B1EE
ROUTINE_END = 0x3B408  # exclusive


def load_verified_rom(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) != EXPECTED_SIZE:
        sys.exit(f"REFUSING: size {len(data)} != {EXPECTED_SIZE} "
                 f"(not the known 1 MB dump)")
    md5 = hashlib.md5(data).hexdigest()
    if md5 != EXPECTED_MD5:
        sys.exit(f"REFUSING: MD5 {md5} != {EXPECTED_MD5} "
                 f"(not the verified Rings of Power dump)")
    print(f"ROM verified: {len(data)} bytes, MD5 {md5}")
    return data


def locate(path):
    data = load_verified_rom(path)
    try:
        from capstone import Cs, CS_ARCH_M68K, CS_MODE_BIG_ENDIAN
    except ImportError:
        sys.exit("Capstone not importable. Activate the #001 venv "
                 "(tools/.venv, capstone 5.0.9) and re-run.")
    md = Cs(CS_ARCH_M68K, CS_MODE_BIG_ENDIAN)
    md.detail = False
    blob = data[ROUTINE_START:ROUTINE_END]
    print(f"\nDisassembly of ${ROUTINE_START:05X}-${ROUTINE_END:05X} "
          f"($3B1EE damage routine). Candidate distance-term sites "
          f"are flagged with >>> :\n")
    for insn in md.disasm(blob, ROUTINE_START):
        raw = insn.bytes.hex(" ")
        flag = ""
        text = f"{insn.mnemonic} {insn.op_str}".strip()
        if insn.mnemonic in ("divs", "divu"):
            flag = "  >>> DIVISION"
        if "#1" in insn.op_str.replace(" ", "") and insn.mnemonic.startswith("move"):
            flag = "  >>> LOAD OF CONSTANT 1?"
        print(f"  {insn.address:06X}: {raw:<20} {text}{flag}")
    print("\nNext: confirm which flagged sequence is the distance "
          "term (docs/logic.md SS5.1: the dividend is the constant 1, "
          "the divisor is dist+2, and the product with base is added "
          "to d0). Record the site address + original bytes in "
          "README.md SS2, then implement apply_confirmed().")


def apply_confirmed(data, site_addr, original_bytes, patched_bytes):
    """Guarded byte replacement — call ONLY with a locate-confirmed site."""
    if data[site_addr:site_addr + len(original_bytes)] != original_bytes:
        raise ValueError(
            f"site bytes at 0x{site_addr:06X} do not match the "
            f"locate-confirmed original bytes — refusing to patch")
    out = bytearray(data)
    out[site_addr:site_addr + len(original_bytes)] = patched_bytes
    return bytes(out)


def apply(path):
    load_verified_rom(path)
    sys.exit("apply is intentionally not wired up yet: run `locate`, "
             "review the flagged division site against docs/logic.md "
             "SS5.1, then implement the confirmed byte change in "
             "apply_confirmed() (inline fix, or jsr hook + trampoline "
             "at 0xFD138+), fix both checksums with "
             "tools/checksum.py fix-all, and emit the IPS. "
             "No patch bytes are generated from a guess.")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("locate", "apply"):
        sys.exit(__doc__)
    if sys.argv[1] == "locate":
        locate(sys.argv[2])
    else:
        apply(sys.argv[2])
