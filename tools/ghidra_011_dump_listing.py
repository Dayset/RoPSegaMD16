# Dump Ghidra listing for selected address ranges (RoP issue #011).
#@author Muse
#@description Dump listing ranges for RoP issue #011
#@category Analysis

from ghidra.program.model.address import AddressSet

out = open("/tmp/ghidra_011_listing.txt", "w")

listing = currentProgram.getListing()
af = currentProgram.getAddressFactory()

ranges = [(0xEB772, 0xEB7C8, "EB772 sound tick"),
          (0xEBA00, 0xEBA7E, "EBA00 music streamer (missed)"),
          (0xEB7C8, 0xEB806, "EB7C8 stop-sound (dead?)"),
          (0x2B240, 0x2B2B2, "2B240 combatant setup"),
          (0x2B3B0, 0x2B402, "2B3B0 sibling (gap)"),
          (0x2B4B0, 0x2B502, "2B4B0 sibling (in FUN_2b402?)")]

for lo, hi, label in ranges:
    out.write("=== 0x%06X-0x%06X %s ===\n" % (lo, hi, label))
    it = listing.getInstructions(AddressSet(
        af.getAddress("0x%06X" % lo), af.getAddress("0x%06X" % hi)), True)
    n = 0
    while it.hasNext():
        cu = it.next()
        out.write("  0x%06X: %s\n" % (cu.getAddress().getOffset(), cu.toString()))
        n += 1
    if n == 0:
        out.write("  (no instructions defined here)\n")

out.close()
print("wrote /tmp/ghidra_011_listing.txt")
