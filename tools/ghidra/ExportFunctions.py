# ExportFunctions.py - Ghidra headless post-script (issue #011)
# @author agent
# @description Exports function list + call graph stats to CSV
# @category Export

from ghidra.program.model.symbol import RefType

out_path = getScriptArgs()[0] if getScriptArgs() else "/tmp/ghidra_functions.csv"
fm = currentProgram.getFunctionManager()
listing = currentProgram.getListing()
refman = currentProgram.getReferenceManager()

rows = []
funcs = list(fm.getFunctions(True))
for f in funcs:
    entry = int(f.getEntryPoint().getOffset())
    size = int(f.getBody().getNumAddresses())
    callers = set()
    callees = set()
    for ref in refman.getReferencesTo(f.getEntryPoint()):
        src = ref.getFromAddress()
        sf = fm.getFunctionContaining(src)
        if sf is not None and sf != f:
            callers.add(int(sf.getEntryPoint().getOffset()))
    for addr in f.getBody().getAddresses(True):
        ins = listing.getInstructionAt(addr)
        if ins is not None:
            for ref in ins.getReferencesFrom():
                tf = fm.getFunctionContaining(ref.getToAddress())
                if tf is not None and tf != f:
                    callees.add(int(tf.getEntryPoint().getOffset()))
    rows.append((entry, f.getName(), size, len(callers), len(callees),
                 ",".join("0x%06X" % c for c in sorted(callees))))

rows.sort()
edges = sum(r[4] for r in rows)
with open(out_path, "w") as fh:
    fh.write("address,name,size_bytes,caller_count,callee_count,callees\n")
    for entry, name, size, nc, ne, callees in rows:
        fh.write("0x%06X,%s,%d,%d,%d,%s\n" % (entry, name, size, nc, ne, callees))
print("ExportFunctions: %d functions, %d unique-callee edges -> %s" % (len(rows), edges, out_path))
