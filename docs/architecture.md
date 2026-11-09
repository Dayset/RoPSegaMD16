# Architecture (early notes — verify before trusting)

- CPU: Motorola 68000. Entry point `0x200` (reset vector at `0x004`).
- RAM: `0xFF0000–0xFFFFFF` (64 KB work RAM, per header).
- ROM: `0x000000–0x0FFFFF` (1 MB).
- Header checksum at `0x18E`, covers words `0x200` to end of ROM.
- Credits in ROM: Naughty Dog, design A. Gavin / J. Rubin / V. Pande,
  programming Andy Gavin / Vijay Pande, music Alexander Hinds.

Everything below this line is TBD until #002/#003 land.
