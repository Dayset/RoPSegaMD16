# Hardware limits checklist (issue #014)

Every build and every mod ticks this list before it lands. Values come
from `docs/overview.md` (hardware facts) and the ROM itself.

## Checklist

- [ ] **ROM size** ≤ 1,048,576 bytes (1 MB, `0x000000–0x0FFFFF`). Free space
      today: `0x0FD0CC–0x0FFFFF` (12,084 bytes of `0xFF`). Growing past 1 MB
      needs a new header end address and new checksums.
- [ ] **Header checksum** at `0x18E` recomputed after any byte change
      (`tools/checksum.py fix-all`; runtime checksum at `0xFD098` first).
- [ ] **Work RAM** ≤ 64 KB (`0xFF0000–0xFFFFFF`). Stack starts at `0x00FFEC1E`.
      New variables must not collide with the save buffer (`$DCE2`, `$42FC8`).
- [ ] **VRAM** ≤ 64 KB. Tile/pattern writes fit the layout in #015.
- [ ] **CRAM** ≤ 128 bytes (64 colours, 4 palettes × 16). Colour 0 of each
      palette is transparent.
- [ ] **Sprites**: ≤ 80 per frame and ≤ 20 per scanline.
- [ ] **Display** 320×224 or 256×224; planes A/B + window only.
- [ ] **VDP writes** only through `$C00000` (data) / `$C00004` (control);
      VRAM bulk writes happen in blanking (VBlank handler), not mid-frame.
- [ ] **Z80 bus**: the 68000 requests and releases the bus (`$A11100`)
      around any access to Z80 RAM.
- [ ] **CPU budget**: per-frame work fits in one frame of a 68000 at
      7.67 MHz after the VBlank sound tick (`$EB772`).
- [ ] **DMA**: VRAM DMA lengths fit blanking time or they tear.
- [ ] **No fault tolerance**: an out-of-range write has no recovery path, so
      every new table index is bounds-checked.

## Known emulator-vs-hardware gaps

These are the places an emulator run can pass where real hardware would not.
Not yet tested against a real console; listed so mods are not signed off on
emulator results alone.

- Timing: emulators do not model VDP access-slot blocking exactly; a VRAM
  write that fits the emulator's blanking window can tear on hardware.
- Bus contention: Z80/68000 bus handoff timing is approximate in most
  emulators; a missing bus request is hard to see in emulation.
- Unmapped reads: emulators often return the last bus value or open-bus
  data; real hardware differs by region and console revision.
- Save hardware: the game's EEPROM save (`$42FC8`, `$43012`, `$430F4`) is
  modelled from the code, not from a real EEPROM chip's timing.

## Harness status

- Boot-test harness (`tools/test_harness.sh`, BlastEm headless) is **not yet
  present in this repository**. BlastEm is not installed in the current
  environment and no apt package was found, so the harness step cannot be
  run here. The #014 acceptance item for the harness is therefore **blocked**
  until the harness script and BlastEm are in place.
