"""Header bytes for the sram-save feature (#284): applied by
tools/build_rom.py before the checksums are fixed.

- $183: own product ID. BlastEm keys its rom.db on the characters at
  $183 up to the first space ("T-50176" matches the 1 MB EEPROM cart);
  Genesis Plus GX looks the product field up for its EEPROM table. Any
  ID without "T-50176" makes both fall back to the header below.
- $1B0: "RA", $F8 $20 (battery-backed, odd bytes), $200001-$2000FF
  (128 bytes)."""
HEADER = {
    0x180: b"GM ROPMD16 -00",
    0x1B0: b"RA\xf8\x20" + (0x200001).to_bytes(4, "big")
           + (0x2000FF).to_bytes(4, "big"),
}
