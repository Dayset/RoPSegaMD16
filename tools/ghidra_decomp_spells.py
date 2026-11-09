# Ghidra headless decompile for issue #008 (spells). Copy of tools/ghidra/DecompSpells.py
# (kept here because tools/ghidra/ is git-ignored -- it holds the Ghidra install).
# Run from the repo dir (needs the Ghidra project tools/ghidra/projects/rop,
# program name rop-ghidra.bin; ~5 min):
#   tools/ghidra/ghidra_11.4.2_PUBLIC/support/analyzeHeadless tools/ghidra/projects \
#     rop -process rop-ghidra.bin -scriptPath tools/ghidra -postScript "DecompSpells.py"
# Output: /tmp/ghidra_spells_decomp.txt
#
# Decompile selected functions for issue #008.
#@author Muse
#@description Decompile spell-related functions for RoP issue #008
#@category Analysis

from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

out = open("/tmp/ghidra_spells_decomp.txt", "w")

addrs = ["0x36e2e","0x398e0","0x3b408","0x37b82","0x25de4","0x2140a","0x3b51e","0x387ae","0x3a62e","0x3b1ee"]
decomp = DecompInterface()
decomp.openProgram(currentProgram)
for a in addrs:
    addr = toAddr(a)
    func = getFunctionAt(addr)
    if func is None:
        out.write("=== %s : NO FUNCTION ===\n" % a)
        continue
    res = decomp.decompileFunction(func, 60, ConsoleTaskMonitor())
    out.write("=== %s : %s ===\n" % (a, func.getName()))
    if res is None or not res.decompileCompleted():
        out.write("DECOMPILE FAILED: %s\n" % (res.getErrorMessage() if res else "null"))
    else:
        out.write(res.getDecompiledFunction().getC())
        out.write("\n")
decomp.dispose()
out.close()
print("wrote /tmp/ghidra_spells_decomp.txt")
