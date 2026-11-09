# Rings of Power — Mega Drive disassembly & modding

Disassembly and modding project for **Rings of Power** (Sega Mega Drive / Genesis,
USA/Europe, 1992, Naughty Dog — GM T-50176).

Repo: https://github.com/Dayset/RoPSegaMD16

Goal: a **rebuildable disassembly** of the game — labelled 68000 assembly that
reassembles byte-identical to the original ROM — plus a patch workflow so
changes (text, stats, spells, balance, fixes) can be made, verified, and
tested in an emulator.

Bigger goal (Dayset, 2026-11-09): the disassembly is the spec for a
**tribute remake** — recreate the same environment in the open-source
Esenthel C++ Titan Engine, playable in classic (isometric) and modern
(3D) style, with the broken original combat switchable against a fixed
one. Design: [docs/tribute-remake.md](docs/tribute-remake.md), issues
#023–#031.

Status: **M1 done 2026-11-09** (toolchain + first disassembly).
Project overview — epics, rebuild contract, hardware limits, structure,
graphics pipeline: [docs/overview.md](docs/overview.md).
See [PROGRESS.md](PROGRESS.md) and [issues/](issues/).

## The ROM (you supply your own dump)

This repo does **not** contain the ROM. Bring your own dump of
`Rings of Power (USA, Europe)` and verify it against:

- Size: 1,048,576 bytes (1 MB)
- MD5: `30c18fdbe2183f64702ae9f1a45d63f9`
- SHA1: `84851ce4527761b8d74ce581c19e15d0dd17f368`
- Header checksum: `0x8B9F` (must match the computed checksum — see `tools/`)
- Header: `SEGA GENESIS`, `(C)T-50 1992.JAN`, `GM T-50176 -00`, region `U`

Place it as `rop-original.gen` in the repo root (git-ignored). Never edit
that file — all work happens on copies / patches.

## Layout

| Path | What lives there |
|---|---|
| `disasm/` | Disassembly output: `.s` sources, labels, code/data map |
| `tools/` | Checksum fixer, string extractor, disassembler scripts, build script |
| `docs/` | Architecture, memory map, findings as they are proven |
| `patches/` | Patch files (`.ips`/diffs + descriptions), never full ROMs |
| `issues/` | Local issue tracker — one file per issue, see `issues/README.md` |
| `PROGRESS.md` | Milestones, status board, what is done / next |
| `NOTES.md` | Verified ROM facts from day one |

## Workflow

1. Pick an issue in `issues/` (or file a new one).
2. Work on a branch named after it, e.g. `issue-002-first-disasm`.
3. Every change must be verifiable: rebuild → byte-compare vs original
   (except the intentional patch bytes) → checksum fixed → emulator smoke test.
4. No change lands without its issue updated in `PROGRESS.md`.

## Rules

- Original ROM untouched, always. Patches only.
- After **any** byte change, recompute the header checksum at `0x18E`.
- A claim about what code does needs evidence: address, bytes, and (once
  we have it) an emulator trace / test — not a guess from the disassembly.
- Text is mostly plain ASCII — the easy entry point. Code is Motorola 68000.
