# Ghidra headless decompile for issue #008, part 2 (status sub-routines + helpers).
# Copy of tools/ghidra/DecompSpells2.py (see tools/ghidra_decomp_spells.py for the run command).
# Output: /tmp/ghidra_spells2_decomp.txt
#
# Decompile the $3B51E status-effect sub-routines + spell helpers.
# Usage: run via Ghidra headless with -postScript "DecompSpells2.py"
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

TARGETS = [0x3B6C0, 0x3B988, 0x3B748, 0x3BA4C, 0x36CFC, 0x36DE8,
           0x3C2C0, 0x37D0E, 0x3B4AC, 0x3AB8C, 0x3BB4E, 0x36A94]

decomp = DecompInterface()
decomp.openProgram(currentProgram)
out = []
for addr in TARGETS:
    fm = currentProgram.getFunctionManager()
    fn = fm.getFunctionAt(toAddr(addr))
    if fn is None:
        out.append("=== %#x : NO FUNCTION ===\n" % addr)
        continue
    res = decomp.decompileFunction(fn, 60, ConsoleTaskMonitor())
    out.append("=== %#x : %s ===\n" % (addr, fn.getName()))
    if res is None or res.getDecompiledFunction() is None:
        out.append("(decompile failed: %s)\n" % (res.getErrorMessage() if res else "null"))
    else:
        out.append(res.getDecompiledFunction().getC())
        out.append("\n")
with open("/tmp/ghidra_spells2_decomp.txt", "w") as f:
    f.write("\n".join(out))
print("wrote /tmp/ghidra_spells2_decomp.txt")
