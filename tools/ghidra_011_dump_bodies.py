# Dump exact function-body address ranges for RoP issue #011.
# Needed because some Ghidra function bodies are non-contiguous
# (e.g. the threaded-code driver $E358): entry/max/size alone
# overstates coverage. Output: one line per body range.
#@author Muse
#@description Dump function body ranges for RoP issue #011
#@category Analysis

out = open("/tmp/ghidra_011_bodies.txt", "w")

fm = currentProgram.getFunctionManager()
funcs = list(fm.getFunctions(True))
funcs.sort(key=lambda f: f.getEntryPoint().getOffset())

out.write("=== BODY RANGES (%d funcs) ===\n" % len(funcs))
for f in funcs:
    e = f.getEntryPoint().getOffset()
    body = f.getBody()
    nranges = 0
    for r in body.getAddressRanges():
        out.write("RANGE 0x%06X 0x%06X 0x%06X\n" % (
            e, r.getMinAddress().getOffset(), r.getMaxAddress().getOffset()))
        nranges += 1
    if nranges != 1:
        out.write("MULTI 0x%06X ranges=%d size=%d\n" % (
            e, nranges, body.getNumAddresses()))

out.close()
print("wrote /tmp/ghidra_011_bodies.txt")
