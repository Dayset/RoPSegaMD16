# Rings of Power — Mega Drive ROM work
Source ROM (user upload, do not redistribute): `~/workspace/user/files/Rings_of_Power__USA__Europe.zip`
- File: `Rings of Power (USA, Europe).gen`, 1,048,576 bytes (1 MB)
- Header: SEGA GENESIS, (C)T-50 1992.JAN, GM T-50176 -00
- MD5: 30c18fdbe2183f64702ae9f1a45d63f9
- SHA1: 84851ce4527761b8d74ce581c19e15d0dd17f368
- Header checksum 0x8B9F — matches computed checksum (verified 2026-11-09). Good dump.
- Entry: 0x200, RAM 0xFF0000-0xFFFFFF, region U
- Credits in ROM: A NAUGHTY DOG INC. PRODUCTION, design A. Gavin / J. Rubin / V. Pande, programming Andy Gavin / Vijay Pande, music Alexander Hinds.
- Text: mostly plain uncompressed ASCII dialogue blob (e.g. Void death message, guild dialogue, shop text) — easy to find/edit by string search. Graphics/code are 68000 + compressed data elsewhere.
- Rule: after ANY byte change, recompute + fix header checksum at 0x18E or real hardware/emulators may reject it. Keep original untouched; work on copies/patches.
- Toolchain to set up when we start: Ghidra (m68k) or m68k disassembler (Capstone via venv, --break-system-packages needed), vasm/as68k for rebuild, an emulator (BlastEm/Gens/RetroArch) to test.
- No change target picked yet (2026-11-09).

- Repo set up 2026-11-09 as a full-scale project: README, PROGRESS.md,
  issues #001–#010, docs/, tools/, disasm/, patches/. Local git only for now
  — `gh` is not logged in, so no GitHub repo yet.
