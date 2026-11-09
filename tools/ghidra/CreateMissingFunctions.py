# CreateMissingFunctions.py - issue #011: vector targets Ghidra misses
# @author agent
# @description Creates functions at 0x1270 (HBlank), 0x1272 (VBlank), 0xEB772 (sound tick)
# @category Export
fm = currentProgram.getFunctionManager()
for addr_str, name in [("00001270", "hblank_handler"), ("00001272", "vblank_handler"), ("000eb772", "sound_tick")]:
    addr = toAddr(addr_str)
    if fm.getFunctionAt(addr) is None:
        disassemble(addr)
        f = createFunction(addr, name)
        print("created %s at %s -> %s" % (name, addr_str, f))
    else:
        print("already exists at %s" % addr_str)
