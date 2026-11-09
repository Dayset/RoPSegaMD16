# Create the second batch of missed functions + disassemble missed case blocks (RoP issue #011).
# Functions (verified real code, link prologue or rts-terminated, no direct callers):
#   0x2988E counter loop calling $2979A (68 B, link/unlk/rts)
#   0x3536C predicate routine, compares args>>2, returns 0/1 (38 B)
#   0x3539A routine calling $1E022, reads struct tables $FF02C0/$FF02C2 (266 B)
#   0xEB8E0 3-byte store helper, ends rts (18 B, shares caller frame like $2B240)
# Case blocks (disassemble only - NOT entries, reached via jump-table dispatch):
#   0x1E02E-0x1E075 four 18-byte case blocks of $1E022 (each ends bra $1E0A0)
#   0x38850-0x38889 case block in the $38xxx spell area (branches to $387F6/$3884A)
#   0xEB9A0-0xEB9C3 two small blocks in the sound cluster (branch to $EB972/$EB978)
#@author Muse
#@description Create second batch of missed functions for RoP issue #011
#@category Analysis

from ghidra.app.cmd.disassemble import DisassembleCommand
from ghidra.app.cmd.function import CreateFunctionCmd
from ghidra.program.model.address import AddressSet
from ghidra.program.model.symbol import SourceType

funcs = [
    (0x2988E, 0x298D1, "FUN_2988e"),
    (0x3536C, 0x35399, "FUN_3536c"),
    (0x3539A, 0x354A3, "FUN_3539a"),
    (0xEB8E0, 0xEB8F1, "FUN_eb8e0"),
]

blocks = [
    (0x1E02E, 0x1E075, "$1E022 case blocks"),
    (0x38850, 0x38889, "spell-area case block"),
    (0xEB9A0, 0xEB9C3, "sound-cluster case blocks"),
]

fm = currentProgram.getFunctionManager()
af = currentProgram.getAddressFactory()

for entry, end, name in funcs:
    a = af.getAddress("0x%06X" % entry)
    e = af.getAddress("0x%06X" % end)
    f = fm.getFunctionAt(a)
    if f is not None:
        print("SKIP 0x%06X already a function (%s)" % (entry, f.getName()))
        continue
    DisassembleCommand(a, AddressSet(a, e), True).applyTo(currentProgram)
    cmd = CreateFunctionCmd(a)
    if not cmd.applyTo(currentProgram):
        print("FAIL 0x%06X %s" % (entry, cmd.getStatusMsg()))
        continue
    f = fm.getFunctionAt(a)
    if f is not None:
        f.setName(name, SourceType.USER_DEFINED)
        print("OK 0x%06X %s body=%d end=0x%06X" % (entry, name, f.getBody().getNumAddresses(), f.getBody().getMaxAddress().getOffset()))
    else:
        print("FAIL 0x%06X no function after create" % entry)

for lo, hi, label in blocks:
    a = af.getAddress("0x%06X" % lo)
    e = af.getAddress("0x%06X" % hi)
    DisassembleCommand(a, AddressSet(a, e), True).applyTo(currentProgram)
    print("DISASM 0x%06X-0x%06X %s" % (lo, hi, label))
