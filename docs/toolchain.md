# Toolchain

Set up 2026-11-09 under issue #001. All versions verified by running the
commands below on this VM (Ubuntu 24.04.5 LTS, x86_64, Python 3.12.3).
The original ROM is never an input to any of these tools except read-only
(`verify`, `disassemble`); patches always work on copies.

## Capstone (disassembly)

- Version: pip package `capstone-5.0.9` (reports library version 5.0.7),
  m68k big-endian support confirmed.
- Location: venv `tools/.venv` — system pip is PEP 668-blocked, do not use
  `--break-system-packages`.
- Install:
  ```
  python3 -m venv tools/.venv
  tools/.venv/bin/pip install capstone
  tools/.venv/bin/python -c "import capstone; print(capstone.__version__)"
  ```
- Gotcha found during #002: Capstone's `disasm()` **stops at the first
  undecodable word** unless skipdata is on. `tools/disassemble.py` sets
  `md.skipdata = True` and coalesces skipped bytes into `.dc.b` runs.

## Ghidra (recursive disassembly / decompilation)

- Version: **Ghidra 11.4.2** (`ghidra_11.4.2_PUBLIC_20250826.zip`, 436 MB),
  from https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_11.4.2_build
- Location: `tools/ghidra/ghidra_11.4.2_PUBLIC/` (git-ignored toolchain
  download, not repo content). Headless project lives in
  `tools/ghidra/projects/` (`rop` project, 68000).
- Java: **OpenJDK 21.0.12.1** (`openjdk-21-jdk-headless`, Ubuntu noble).
  The JRE alone is **not** enough — Ghidra rejects it with
  "JAVA_HOME environment specifies unsupported java version" and
  "Unable to prompt user for JDK path". Install the full JDK:
  ```
  sudo apt-get install -y openjdk-21-jdk-headless
  export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
  ```
- First download attempt failed with a transient `504 Gateway Time-out`
  from the egress proxy; a retry with `curl -L --retry 2` succeeded
  (436 MB in ~20 s).
- Language: `68000:BE:32:default` (processor `68000`, big-endian, 32-bit).
  Verified present in `Ghidra/Processors/68000/data/languages/68000.ldefs`.
- Headless import + auto-analysis (verified 2026-11-09: import +
  analysis succeeded in 33 s, EXIT 0):
  ```
  export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
  cp rop-original.gen /tmp/rop-ghidra.bin   # import a copy, never the original
  ./tools/ghidra/ghidra_11.4.2_PUBLIC/support/analyzeHeadless \
      tools/ghidra/projects rop \
      -import /tmp/rop-ghidra.bin -processor 68000:BE:32:default
  ```
  Note: the language is passed as `-processor 68000:BE:32:default`;
  there is no `-language` flag (`Bad argument: -language` if you try).
  Project saved as `tools/ghidra/projects/rop.gpr` + `rop.rep/`.

## Assembler

- **GNU as, binutils 2.42** (`binutils-m68k-linux-gnu`, Ubuntu noble):
  `m68k-linux-gnu-as` / `m68k-linux-gnu-objdump`. Verified assembling a
  test file (`move.l #0x53454741,%d0` → `203c 5345 4741`,
  `move.w #0x2700,%sr` → `46fc 2700`, `tst.l 0xA10008`, `rts`).
  ```
  sudo apt-get install -y binutils-m68k-linux-gnu
  ```
- **vasm: not installed.** Not in Ubuntu apt; the upstream tarball URL
  (`sun.hasenbraten.de/vasm/release/vasm.tar.gz`) returned 404 on
  2026-11-09. GNU as covers reassembly for now; vasm is nicer for
  Genesis-style sources (Motorola syntax, `org`, binary output), so
  retrying vasm from source is a follow-up for #009, not a blocker.
- **Syntax trap (verified):** GAS m68k wants `0x` hex (`#0x53454741`).
  The vasm-style `$53454741` is silently assembled as `#0` — no error,
  wrong code. Always verify assembled output with objdump.

## Emulator

- **BlastEm 0.6.3.4-1build1** (Ubuntu noble universe), binary at
  `/usr/games/blastem` (not on the default non-login PATH):
  ```
  sudo apt-get install -y blastem
  /usr/games/blastem <rom>
  ```
- BlastEm smoke test (2026-11-09, verified): with no display it fails
  (`Unable to create SDL window` under the dummy driver), and with a
  real audio device missing it exits 1 silently right after creating
  the window — the ALSA failure is fatal. Working headless recipe
  (Xvfb is pre-installed on this VM):
  ```
  SDL_AUDIODRIVER=dummy timeout 8 xvfb-run -a /usr/games/blastem <rom>
  ```
  The original ROM boots and runs under it (exit 124 = still running
  at timeout). With `-l`, BlastEm writes `/tmp/address.log`, a log of
  branch-target addresses: in an 8 s run execution starts at `0x200`,
  reaches the checksum routine `0xFD07C`, game init `0x4323C`, and
  main-loop code in `0x010000–0x040000` and `0xEB000`, with the VBlank
  handler `0x1272` firing — i.e. the game passes its own checksum and
  runs. (Caveat: the log records branch targets, not every instruction
  — the lone `0xFD0A0` entry is the checksum-fail branch target being
  logged, not a failure: had the check failed, execution would have
  stopped at `0xFD0CA` and never reached `0x4323C`.)
- RetroArch 1.18.0 is also in apt (`retroarch`) but was not installed —
  BlastEm is the more accurate Genesis-only choice. Install only if
  BlastEm proves unusable headless.

## Checksums

- `tools/checksum.py` — see its docstring. Two checksums matter:
  1. **Header checksum** at `0x18E`: sum of 16-bit words `0x200..end`.
     Original: `0x8B9F`.
  2. **Runtime self-check** at `0xFD07C` (found in #002): the game sums
     32-bit words `0x000000..0xFD07B` (skipping the longword at `0x18C`)
     and compares against the `cmpi.l` immediate at `0xFD098`
     (original `0x8F33608C`). Mismatch → VDP setup + infinite loop at
     `0xFD0CA` (game hangs at boot). **Both** must be fixed after any
     mod — `checksum.py fix-all` does that, runtime first, header last
     (the runtime immediate at `0xFD098` is inside the header checksum's
     range, so the order matters).
- Proven 2026-11-09: flip one byte in a copy → both checksums mismatch;
  `fix-all` → both verify OK; only bytes `0x18E` and `0xFD098` differ
  from the modded input; original MD5 unchanged
  (`30c18fdbe2183f64702ae9f1a45d63f9`).

## Commands recap (fresh machine)

```
sudo apt-get update
sudo apt-get install -y openjdk-21-jdk-headless binutils-m68k-linux-gnu blastem
python3 -m venv tools/.venv && tools/.venv/bin/pip install capstone
# Ghidra: download 11.4.2 zip from GitHub releases, unzip under tools/ghidra/
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
```
