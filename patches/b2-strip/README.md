# B2 patch — Scheme B improved gate (camera-driven scroll)

Base: `rop-big-rework-full-b1.rom` (MD5 `49530033f2f191d938e9f0ec3f86e845`).
Output: `rop-big-rework-full-b2.rom`
(MD5 `ec7bcffe9c45fd851a6752dec5bcf788`).
IPS: `rings-of-power-big-rework-full-b2.ips` (applies to the B1
ROM, not the original). Full record:
`.scratch-big-rework-full/b2-strip/REPORT.md`.

## What B2 is

The brief's fallback, built deliberately: literal strip
streaming (DESIGN §7.3) is **unbuildable** for the 36×23 image
— proven in sim (`sim_strip.py` in the scratch dir). A strip
decoded alone into a cleared buffer is 2.7–88.8% wrong vs the
full render (the `$E358` composite is a per-nibble select over
all covering cells in render order, so a strip alone cannot
reproduce the overlap bytes); repack + strip is 6.5–16.5%
wrong (render order + height-stack status changes at the
trailing edge). R1 verifies the full re-decode re-centre is
flicker-free, so Scheme B (full re-install at the cell
boundary) is acceptable.

The one change vs B1: the VBlank scroll follows the **camera**,
not the D-pad. Fix2's gate is seamless only once the pad-driven
scroll has caught up to the camera move, but the scroll is
pad-driven while the camera is game-driven: cutscene/scripted
moves stall the gate until it fires the jumpy ">1 cell" branch,
and a short tap / direction change leaves the picture frozen
with a blank strip until the pad is held again. B2 steps the
scroll each VBlank toward the camera target
(clamp(−(dx−dy),−1,+1)·224, clamp(dx+dy,−1,+1)·128 — the
gate's own expected-value formulas) at 16/16 px horiz,
9/16 px vert per frame, so catch-up completes within ~15
frames of any camera move, with no pad input. The gate itself
is unchanged. Cost per cell step stays the ~16 fr full
re-decode; the picture is seamless rather than hitch-free.

## Files

- `source.s` — the blob (vasm Motorola syntax; see below).
- `build.py` — assembles, patches, checksums, emits the IPS
  and `changed-bytes.txt`. Run: `python3 patches/b2-strip/build.py`
- `check_entries.py` — capstone disassembly comparison proving
  the three unchanged entries match the B1 blob (run by
  build.py under the RoP venv python).
- `source.bin` / `source.lst` — assembled blob + vasm listing.
- `rings-of-power-big-rework-full-b2.ips` — base → B2
  (round-trip verified).
- `changed-bytes.txt` — full byte diff (150 records).

## Toolchain note (important for the next agent)

This VM has **no m68k GAS** (`m68k-linux-gnu-as` is not
installed), so `source.s` is vasm Motorola syntax, assembled
with the in-worktree `vasm/vasmm68k_mot -m68000 -Fbin`
(entry offsets from the `-L` listing, never hardcoded).
Vasm vs GAS encoding differences, all verified semantically
identical by the disassembly check in `build.py`:
branch displacements optimised to 8-bit where they fit
(redraw 48 B shorter, so scene is at +0x4C0 not +0x4F0 and
mapclose at +0x4FA not +0x52A); `adda.w #16,sp` encoded as
`lea $10(sp),sp`; one no-op `bra .rdone` (branch to the next
instruction) elided. The new `vbl_entry` is exactly the same
size as B1's (0x254), so `redraw_entry` stays at +0x254 and
the `$1B918` hook is byte-unchanged.

## Hooks (B1 → B2)

- `$1272` jmp `$FD900` — unchanged.
- `$1B918` jsr `$FDB54` — unchanged.
- `$12C20` jsr `$FDDF0` → jsr `$FDDC0` (scene moved).
- `$16302` jsr `$FDE2A` → jsr `$FDDFA` (mapclose moved).

Statics and allocator unchanged from B1 (asserted, not
touched). Stale B1 blob tail `$FDE30–$FDE60` cleared to `0xFF`.
Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).
Nothing landed on main.
