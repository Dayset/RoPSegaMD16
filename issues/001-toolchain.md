# Issue #001 — Toolchain: Ghidra + Capstone + assembler + emulator

**Milestone:** M1
**Epic 1**  
**Status:** done (2026-11-09)

## Goal
A repeatable toolchain on this machine that can disassemble, reassemble,
patch, and test the ROM.

## Acceptance
- [x] Capstone (m68k) usable from a venv in `tools/` — pip `capstone-5.0.9`
      (lib 5.0.7) in `tools/.venv`
- [x] Ghidra with m68k language installed — Ghidra 11.4.2, language
      `68000:BE:32:default`; headless import + auto-analysis of the ROM
      succeeded in 33 s (project `tools/ghidra/projects/rop`)
- [x] An m68k assembler that can assemble a test file — GNU as 2.42
      (`binutils-m68k-linux-gnu`); test file verified via objdump.
      vasm NOT installed (see below) — GNU as covers it for now
- [x] An emulator available for smoke tests — BlastEm 0.6.3.4 at
      `/usr/games/blastem`; original ROM boots and runs under it
      (headless recipe in `docs/toolchain.md`)
- [x] `tools/checksum.py` fixes the header checksum and verifies it —
      plus the in-game runtime checksum (see below)
- [x] All of the above documented in `docs/toolchain.md`

## Notes
- Java: the JRE alone is NOT enough for Ghidra — it needs the full JDK
  (`openjdk-21-jdk-headless`, 21.0.12.1). JRE-only gives "unsupported
  java version". First Ghidra download failed with a transient proxy
  504; retry succeeded.
- `pip install capstone` is blocked system-wide (PEP 668) — venv used.
- Original ROM is never an input to the assembler; patches only.
- **vasm not installed:** not in Ubuntu apt; upstream tarball URL
  returned 404 on 2026-11-09. Follow-up for #009, not a blocker.
  GAS syntax trap (verified): vasm-style `$53454741` hex is silently
  assembled as `#0` by GNU as — use `0x` hex and verify with objdump.
- **BlastEm headless gotchas:** needs a display (Xvfb, pre-installed)
  and dies silently (exit 1) if ALSA audio can't open — use
  `SDL_AUDIODRIVER=dummy`.
- **Two checksums, not one:** `checksum.py fix-all` fixes the header
  checksum (`0x18E`, `0x8B9F`) AND the game's runtime self-check
  constant (`cmpi.l` immediate at `0xFD098`, `0x8F33608C`) — a mod
  that fixes only the header hangs at boot. Proven on a copy with a
  flipped byte; original MD5 unchanged.

## Result
Done. One deliberate gap: vasm (deferred to #009).
