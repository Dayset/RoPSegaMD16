# Create functions Ghidra's recursive analysis missed (RoP issue #011).
# Targets (all verified real code by Capstone clean decode + #003/#021 traces):
#   0xEBA00 music streamer, jsr-called from $EB772 (0xEB7BE) but never followed
#   0xEB7C8 stop-sound, zero callers (dead code in the original; revived by music-off patch)
#   0x2B2B2 combatant-setup wrapper 2 (falls through into the $2B3B0 field-write block)
#   0x2B502 combatant-setup wrapper 4 (falls through into the $2B5B0 field-write block)
# Note: $2B3B0/$2B5B0 are NOT entries - they are mid-routine labels reached only by
# fall-through from their wrappers ($2B2B2/$2B502). Do not create functions there.
#@author Muse
#@description Create missed functions for RoP issue #011
#@category Analysis

from ghidra.app.cmd.disassemble import DisassembleCommand
from ghidra.app.cmd.function import CreateFunctionCmd
from ghidra.program.model.address import AddressSet
from ghidra.program.model.symbol import SourceType

targets = [
    (0xEBA00, 0xEBA7D, "EBA00"),
    (0xEB7C8, 0xEB806, "EB7C8"),
    (0x2B2B2, 0x2B401, "FUN_2b2b2"),
    (0x2B502, 0x2B5F3, "FUN_2b502"),
]

fm = currentProgram.getFunctionManager()
af = currentProgram.getAddressFactory()

for entry, end, name in targets:
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
