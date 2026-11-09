# Fix the 1-address stub functions from CreateFuncs011.py: remove them,
# disassemble the regions with flow-following, then re-create as real
# functions. Run with -noanalysis, followed by DumpFunctions011.py.
#@author Muse
#@description Disassemble and create interrupt/sound functions for RoP issue #011
#@category Analysis

from ghidra.app.cmd.function import CreateFunctionCmd
from ghidra.app.cmd.disassemble import DisassembleCommand
from ghidra.program.model.address import AddressSet
from ghidra.program.model.symbol import SourceType

out = open("/tmp/ghidra_011_create2.txt", "w")

fm = currentProgram.getFunctionManager()
af = currentProgram.getAddressFactory()

# (entry, name, disasm set end) - ends are generous; followFlow stops at rte/rts
jobs = [(0x1270, "HBlank_handler", 0x1270),
        (0x1272, "VBlank_handler", 0x1400),
        (0xEB772, "FUN_EB772_sound_tick", 0xEB800)]

for target, name, end in jobs:
    a = af.getAddress("0x%06X" % target)
    e = af.getAddress("0x%06X" % end)
    f = fm.getFunctionAt(a)
    if f is not None:
        try:
            fm.removeFunction(a)
            out.write("REMOVE 0x%06X ok (was body=%d)\n" % (target, f.getBody().getNumAddresses()))
        except Exception as ex:
            out.write("REMOVE 0x%06X FAILED %s\n" % (target, ex))
    dcmd = DisassembleCommand(a, AddressSet(a, e), True)
    okd = dcmd.applyTo(currentProgram, monitor)
    out.write("DISASM 0x%06X ok=%s\n" % (target, okd))
    cmd = CreateFunctionCmd(a)
    okc = cmd.applyTo(currentProgram, monitor)
    f = fm.getFunctionAt(a)
    if f is not None:
        f.setName(name, SourceType.USER_DEFINED)
        out.write("CREATE 0x%06X ok=%s body=%d end=0x%06X\n" % (
            target, okc, f.getBody().getNumAddresses(),
            f.getBody().getMaxAddress().getOffset()))
    else:
        out.write("CREATE 0x%06X FAILED ok=%s %s\n" % (target, okc, cmd.getStatusMsg()))

out.close()
print("wrote /tmp/ghidra_011_create2.txt")
