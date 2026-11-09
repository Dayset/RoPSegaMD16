# Toolchain in the agent VM (2026-11-09 continuation)

This VM is **not** Dayset's #001 machine (`docs/toolchain.md`).
It started with only Python 3.12 — no Capstone venv, no assembler,
no emulator, no ROM. On 2026-11-09 the ROM was supplied (verified
MD5 `30c18fdbe2183f64702ae9f1a45d63f9`, git-ignored) and the
toolchain below was installed/tested. Ghidra was **not** installed
(large download; #011 still needs it or Dayset's machine).

## Installed

| Tool | Version | How | Status |
|---|---|---|---|
| Capstone | pip capstone 5.0.9 (lib 5.0.7) | `python3 -m venv tools/.venv` + pip | ✅ works |
| GNU as / objcopy (m68k) | **2.42** (binutils-m68k-linux-gnu 2.42-4ubuntu2.10) | direct .deb from the Ubuntu pool (see note) | ✅ works |
| BlastEm | **0.6.3.4** at `/usr/games/blastem` | Ubuntu package 0.6.3.4-1build1 (.deb) + libglew2.2 | ✅ boots the ROM headless |
| Xvfb | system | pre-installed | ✅ |

Note on the assembler install: `apt-get update` in this VM is
extremely slow through the proxy (>15 min for full lists, killed
unfinished). The .deb was fetched directly from
`pool/universe/b/binutils/` on the Ubuntu archive (filename taken
from the already-downloaded Packages index; the host's
binutils-common was already the matching 2.42-4ubuntu2.10).
BlastEm's tarball URLs on retrodev.com 404'd for every guessed
filename; the Ubuntu package is the same upstream 0.6.3.4.

Versions now match the #001 machine exactly (Capstone 5.0.9,
GNU as 2.42, BlastEm 0.6.3.4) — deliberate, so results transfer.

## Tool test results (all run 2026-11-09, with the real ROM)

- `tools/checksum.py` — synthetic 1 MB buffer (0C 80 planted at
  0xFD096): verify → MISMATCH (exit 1) as expected; fix-all →
  verify-all **OK** (header + runtime round-trip). Header-only
  fix → verify OK. Real ROM: verify-all **OK** (header 0x8B9F,
  runtime 0x8F33608C). No bugs found.
- `tools/verify_rebuild.py` — `--selftest` PASS; ROM vs itself PASS.
- `tools/split_disasm.py` — dry-run parses 16 ranges; now that
  `disasm/ghidra/function_map.csv` and the ROM both exist it
  reports "prerequisites present — emission is the next #012
  item" (exit 0). Observation (not changed): its CODE/DATA label
  is purely confidence-based, so the dictionary blob
  (0x0D6EBA, "likely") and the 0xFF padding (0xFD0CC, "verified")
  print as CODE — emission must use the #011 map, not this label.
- `tools/disassemble.py` — regenerated the disassembly to a temp
  file: **273,209 instructions, 196,448 gap bytes — exactly the
  #002 numbers.** Byte-regenerable claim holds.
- `tools/extract_text.py` — all five outputs (dictionary,
  records, dd5c streams, spaced strings, inventory.json)
  **byte-identical** to the committed `disasm/text/` files.
- `tools/decode_map.py` — list/stats work; `draw 9 --scale 3`
  output is **pixel-identical** to the committed
  `disasm/maps/world_map_rec09_pal11.png`.
- `tools/render_tiles.py` — record and sprite modes render
  (font rec 0, portrait sprite 0) without errors.
- `tools/extract_assets.py` — with the ROM present it runs:
  exports 31 palettes × 16 colours to
  `tribute/assets/palettes.json` (valid JSON, spot-checked).
  The generated file was removed after the test (it is a build
  product, not a source). Tiles/sprites/maps/text exporters
  remain the next #024 step, as the script itself says.
- `patches/distance-fix/build_patch.py` — guards verified with
  system python (verifies ROM, then correctly demands the
  Capstone venv) and with the venv (locate disassembles
  $3B1EE–$3B408 and flags the division sites). Not modified —
  the parent session owns #022.
- `tools/build.sh` / `tools/test_harness.sh` — `bash -n` clean.
  **Bug found & fixed in test_harness.sh:** it invoked
  `checksum.py fix-all` with a single argument (the CLI requires
  `<src> <dst>`) and hid the failure behind `|| true`, so the
  harness would have run BlastEm on an un-fixed ROM and reported
  a misleading checksum hang. Now calls
  `fix-all build/rop-rebuilt.gen build/rop-test.gen` directly.
- **Harness assembly:** `m68k-linux-gnu-as -m68000` assembles
  both `tools/test_logic_harness.s` and
  `tools/test_spells_harness.s` **cleanly, zero errors** — no
  syntax fixes needed.
- **BlastEm boot smoke test:** original ROM under
  `SDL_AUDIODRIVER=dummy xvfb-run blastem` runs past boot and is
  still running at the 10 s timeout (exit 124) — the same
  signature #001 recorded for a successful boot.

## Still missing in this VM

- Ghidra (for #011 recursive analysis) — not attempted; the
  0x9C00–0xA500 block behind the Game Genie table
  (`docs/research/game-genie-decoded.md`) is a concrete first
  target when it lands.
- A full #013 rebuild gate run — still blocked on #012 emission
  (disasm/src/ doesn't exist), not on tooling any more.
