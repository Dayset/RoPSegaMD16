# Probe current Ghidra project state for RoP issue #011 (fast, no analysis).
#@author Muse
#@description Probe function state for RoP issue #011
#@category Analysis

out = open("/tmp/ghidra_011_probe.txt", "w")

fm = currentProgram.getFunctionManager()
funcs = list(fm.getFunctions(True))
out.write("FUNC_COUNT %d\n" % len(funcs))

targets = [0x200, 0x1270, 0x1272, 0xEB772, 0x4323C, 0xD25C, 0xD28E,
           0xEB806, 0x3AA, 0xA14, 0x119E, 0xFD07C, 0x1350]
for t in targets:
    f = fm.getFunctionAt(currentProgram.getAddressFactory().getAddress("0x%06X" % t))
    out.write("HAS_FUNC 0x%06X %s\n" % (t, "yes" if f is not None else "no"))

# functions whose entry lies in the two boundary ranges of interest
for lo, hi in [(0x010000, 0x043FFF), (0x0E0000, 0x0FBFFF)]:
    n = sum(1 for f in funcs if lo <= f.getEntryPoint().getOffset() <= hi)
    out.write("RANGE 0x%06X-0x%06X funcs=%d\n" % (lo, hi, n))

# functions anywhere in the high-entropy blocks (should be ~none if data)
for lo, hi in [(0x044000, 0x05FFFF), (0x094000, 0x0CBFFF)]:
    n = sum(1 for f in funcs if lo <= f.getEntryPoint().getOffset() <= hi)
    out.write("RANGE 0x%06X-0x%06X funcs=%d\n" % (lo, hi, n))

out.close()
print("wrote /tmp/ghidra_011_probe.txt")
