# sram-save — save in header SRAM for ROMs larger than 1 MB (#284)

Added by `tools/build_rom.py` to every `SIZE=2m` build (opt out with
`--eeprom`). The original cart saves to a 128-byte serial EEPROM that
emulators only find through a per-game database keyed on the product
ID `T-50176`; BlastEm's entry also maps only 1 MB of ROM, so a larger
ROM failed there without a `rom.db` edit. This feature makes the
header describe everything instead:

- product ID `GM ROPMD16 -00` (no database matches it),
- `RA $F8 $20`, `$200001–$2000FF`: 128 bytes of battery SRAM, odd bytes,
- the EEPROM block read `$43012` and byte write `$430F4` replaced by
  SRAM copies, the bit-bang delay `$42FD8` (reached from
  `eeprom_init`) returns at once. The game's save format and its
  callers (`$17706`/`$177B4`) are unchanged.

`$A130F1` is set to 1 around each access (interrupts held), which a
board larger than 2 MB needs to map SRAM over ROM; a 2 MB board
ignores it. A save from the 1 MB EEPROM cart does not carry over.

Verified 2026-11-23 with `tools/md_save_check.py` (the #019 save
harness, 21 result words) on `make rom FEATURES=topdown SIZE=2m`:
stock BlastEm 0.6.3.4 (no `rom.db` edit: "Product ID: ROPMD16, Not
found in ROM DB, examining header") and Genesis Plus GX both give
save `0x48`, load `0x49`, re-read magic `0x2A`, parity `0x1B`, error
count 0 — the same words as the 1 MB EEPROM run — and BlastEm writes
`save.sram` (128 bytes, `2A 1B …`). The topdown code in the second
megabyte (`td_tick` at `$1F0000`) runs in stock BlastEm.
