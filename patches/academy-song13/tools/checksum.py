#!/usr/bin/env python3
"""Genesis / Mega Drive header checksum tool — issue #001.

The checksum is stored big-endian at 0x18E and is the sum of all 16-bit
big-endian words from 0x200 to the end of the ROM, truncated to 16 bits.

Usage:
    checksum.py verify <rom>            # header checksum only, exit 0 if match
    checksum.py verify-all <rom>        # header + in-game runtime checksum
    checksum.py fix <rom> <out>         # write a copy with the header checksum fixed
    checksum.py fix --in-place <rom>    # fix the file in place (never use on the original!)
    checksum.py fix-all <rom> <out> [shift]  # fix header checksum AND runtime constant
    checksum.py inc <image> <out.inc> [shift]  # build-time: RUNTIME_SUM / HEADER_SUM (#16)

Runtime checksum (found 2026-11-09, issue #002): the game self-checks at
boot — jsr $FD07C from the entry code at 0x300 sums 32-bit big-endian words
from 0x000000 to 0xFD07B, skipping the longword at 0x18C (which holds the
header checksum), 0x3F41F iterations, and compares the sum against the
hardcoded cmpi.l immediate at 0xFD098 (original value 0x8F33608C). On
mismatch it sets up the VDP and hangs in an infinite loop at 0xFD0CA, so
a mod that only fixes the header checksum will NOT boot. The fix is to
patch the immediate at 0xFD098 to the new sum — it sits at 0xFD096, past
the end of the summed range, so patching it does not change the sum.
"""
import struct
import sys
from pathlib import Path

CHECKSUM_OFFSET = 0x18E
CHECKSUM_START = 0x200

# Runtime self-check at 0xFD07C (see module docstring).
RT_CMPI_ADDR = 0xFD096       # cmpi.l #imm,d0 — opcode bytes 0C 80
RT_IMM_ADDR = 0xFD098        # the 32-bit expected sum, big-endian
RT_ITERATIONS = 0x3F41F
RT_SKIP_ADDR = 0x18C         # longword skipped by the sum loop


def compute_runtime_checksum(data: bytes) -> int:
    """Replicate the 0xFD07C loop exactly (verified: == 0x8F33608C on original)."""
    total = 0
    a0 = 0
    d1 = RT_ITERATIONS
    while True:
        if a0 == RT_SKIP_ADDR:
            a0 += 4
        else:
            total = (total + struct.unpack_from(">I", data, a0)[0]) & 0xFFFFFFFF
            a0 += 4
        d1 -= 1
        if d1 <= 0:
            break
    return total


def stored_runtime_checksum(data: bytes, shift: int = 0) -> int:
    cmp_at, imm_at = RT_CMPI_ADDR + shift, RT_IMM_ADDR + shift
    if data[cmp_at:cmp_at + 2] != b"\x0c\x80":
        raise ValueError(f"expected cmpi.l opcode 0C 80 at 0x{cmp_at:06X}, "
                         f"found {data[cmp_at:cmp_at + 2].hex()} — "
                         f"ROM is not the known Rings of Power dump (or shift is wrong)")
    return struct.unpack_from(">I", data, imm_at)[0]


def fix_runtime_checksum(data: bytearray, shift: int = 0) -> int:
    value = compute_runtime_checksum(bytes(data))
    stored_runtime_checksum(bytes(data), shift)  # guard: refuse if not the known code
    struct.pack_into(">I", data, RT_IMM_ADDR + shift, value)
    return value


def compute_checksum(data: bytes) -> int:
    """Sum of 16-bit big-endian words from 0x200 to end, mod 0x10000."""
    body = data[CHECKSUM_START:]
    if len(body) % 2:
        body += b"\x00"
    total = 0
    for i in range(0, len(body), 2):
        total += (body[i] << 8) | body[i + 1]
    return total & 0xFFFF


def stored_checksum(data: bytes) -> int:
    return struct.unpack(">H", data[CHECKSUM_OFFSET:CHECKSUM_OFFSET + 2])[0]


def fix_checksum(data: bytearray) -> int:
    value = compute_checksum(bytes(data))
    struct.pack_into(">H", data, CHECKSUM_OFFSET, value)
    return value


def verify(path: str) -> bool:
    with open(path, "rb") as f:
        data = f.read()
    stored = stored_checksum(data)
    computed = compute_checksum(data)
    ok = stored == computed
    print(f"{path}: size={len(data)} stored=0x{stored:04X} computed=0x{computed:04X} "
          f"{'OK' if ok else 'MISMATCH'}")
    return ok


def verify_all(path: str) -> bool:
    ok = verify(path)
    with open(path, "rb") as f:
        data = f.read()
    stored = stored_runtime_checksum(data)
    computed = compute_runtime_checksum(data)
    rok = stored == computed
    print(f"{path}: runtime stored=0x{stored:08X} computed=0x{computed:08X} "
          f"{'OK' if rok else 'MISMATCH'}")
    return ok and rok


def main(argv):
    if len(argv) < 3 or argv[1] not in ("verify", "verify-all", "fix", "fix-all", "inc"):
        print(__doc__)
        return 2
    if argv[1] == "verify":
        return 0 if verify(argv[2]) else 1
    if argv[1] == "verify-all":
        return 0 if verify_all(argv[2]) else 1
    if argv[1] == "inc":
        # The runtime sum skips 0x18C and never reads 0xFD098, so it comes from the image as-is.
        # The header sum reads 0xFD098, so it is taken after that immediate is set.
        with open(argv[2], "rb") as f:
            data = bytearray(f.read())
        runtime = compute_runtime_checksum(bytes(data))
        imm = RT_IMM_ADDR + (int(argv[4], 0) if len(argv) > 4 else 0)  # shift test moves the immediate
        struct.pack_into(">I", data, imm, runtime)
        header = compute_checksum(bytes(data))
        Path(argv[3]).write_text(
            f"RUNTIME_SUM\tequ\t${runtime:08X}\n"
            f"HEADER_SUM\tequ\t${header:04X}\n")
        print(f"{argv[3]}: runtime ${runtime:08X}, header ${header:04X}")
        return 0
    if argv[1] == "fix-all":
        src, dst = argv[2], argv[3]
        with open(src, "rb") as f:
            data = bytearray(f.read())
        old_h = stored_checksum(bytes(data))
        shift = int(argv[4], 0) if len(argv) > 4 else 0  # shifted builds move the immediate (#16 item 3)
        old_r = stored_runtime_checksum(bytes(data), shift)
        # ORDER MATTERS: patch the runtime immediate FIRST (it lives at
        # 0xFD098, inside the header checksum's range), then fix the header
        # checksum LAST (it only touches 0x18E, which the runtime sum skips).
        new_r = fix_runtime_checksum(data, shift)
        new_h = fix_checksum(data)
        with open(dst, "wb") as f:
            f.write(data)
        print(f"{src} -> {dst}: header 0x{old_h:04X} -> 0x{new_h:04X}, "
              f"runtime 0x{old_r:08X} -> 0x{new_r:08X}")
        return 0
    # fix
    if argv[2] == "--in-place":
        path = argv[3]
        with open(path, "rb") as f:
            data = bytearray(f.read())
        old = stored_checksum(bytes(data))
        new = fix_checksum(data)
        with open(path, "wb") as f:
            f.write(data)
        print(f"{path}: checksum 0x{old:04X} -> 0x{new:04X} (in place)")
        return 0
    src, dst = argv[2], argv[3]
    with open(src, "rb") as f:
        data = bytearray(f.read())
    old = stored_checksum(bytes(data))
    new = fix_checksum(data)
    with open(dst, "wb") as f:
        f.write(data)
    print(f"{src} -> {dst}: checksum 0x{old:04X} -> 0x{new:04X}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
