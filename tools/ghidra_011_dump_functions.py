# Full function map for RoP issue #011: create the missing vector/sound
# functions, then dump functions, call edges, and xrefs.
# Run: analyzeHeadless tools/ghidra/projects rop -process rop-ghidra.bin
#      -scriptPath tools/ghidra -postScript "DumpFunctions011.py"
#      (with full auto-analysis; ~minutes, run in background)
#@author Muse
#@description Dump full function map for RoP issue #011
#@category Analysis

out = open("/tmp/ghidra_011.txt", "w")

fm = currentProgram.getFunctionManager()
af = currentProgram.getAddressFactory()

def addr(x):
    return af.getAddress("0x%06X" % x)

# --- 1. Create functions the analyser missed (vector targets, no call sites)
for target, name in [(0x1270, "HBlank_handler"),
                     (0x1272, "VBlank_handler"),
                     (0xEB772, "FUN_EB772_sound_tick")]:
    a = addr(target)
    existing = fm.getFunctionAt(a)
    container = fm.getFunctionContaining(a)
    if existing is not None:
        out.write("CREATE 0x%06X already a function (%s)\n" % (target, existing.getName()))
    else:
        if container is not None:
            out.write("CREATE 0x%06X WARNING inside %s (0x%06X)\n" % (
                target, container.getName(), container.getEntryPoint().getOffset()))
        try:
            f = fm.createFunction(a, name, monitor)
            out.write("CREATE 0x%06X created %s body=%d\n" % (
                target, f.getName(), f.getBody().getNumAddresses()))
        except Exception as e:
            out.write("CREATE 0x%06X FAILED %s\n" % (target, e))

# --- 2. Function list
funcs = list(fm.getFunctions(True))
funcs.sort(key=lambda f: f.getEntryPoint().getOffset())
out.write("=== FUNCTIONS (%d) ===\n" % len(funcs))
for f in funcs:
    e = f.getEntryPoint().getOffset()
    body = f.getBody()
    out.write("FUNC 0x%06X 0x%06X size=%d %s\n" % (
        e, body.getMaxAddress().getOffset(), body.getNumAddresses(), f.getName()))

# --- 3. Call edges
out.write("\n=== CALL EDGES ===\n")
for f in funcs:
    e = f.getEntryPoint().getOffset()
    try:
        called = f.getCalledFunctions(monitor)
    except Exception as ex:
        out.write("CALL 0x%06X ERROR %s\n" % (e, ex))
        continue
    for c in called:
        out.write("CALL 0x%06X -> 0x%06X %s\n" % (
            e, c.getEntryPoint().getOffset(), c.getName()))

# --- 4. Xrefs to key addresses (call trees for entry / VBlank / $4323C / $EB772)
targets = [0x200, 0x1270, 0x1272, 0xEB772, 0x4323C, 0xD25C, 0xD28E,
           0xEB806, 0xEB88A, 0xEBA00, 0xEBAC6, 0xEBA7E, 0xEB7C8,
           0x42FC8, 0x43012, 0x430F4, 0xDCE2, 0x42EBA, 0x42F96,
           0x42E34, 0x42E76, 0x42EEE, 0x3AA, 0xA14, 0x119E, 0xFD07C,
           0x1350, 0x12B82, 0x12FE8, 0x1B5D6, 0x2155E, 0x23B84,
           0x1386A, 0x138A8, 0x12072]
rm = currentProgram.getReferenceManager()
out.write("\n=== XREFS ===\n")
for t in targets:
    refs = rm.getReferencesTo(addr(t))
    lst = sorted(set(r.getFromAddress().getOffset() for r in refs))
    out.write("XREF 0x%06X: %s\n" % (t, " ".join("0x%06X" % x for x in lst)))

out.close()
print("wrote /tmp/ghidra_011.txt")
