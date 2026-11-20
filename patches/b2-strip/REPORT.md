# B2 report — strip streaming (Scheme A) for the 36×23 image

Worktree: `~/workspace/rop-work/big-rework-full/` (main tip `416d623`).
Base: `rop-big-rework-full-b1.rom` (MD5 `49530033f2f191d938e9f0ec3f86e845`).
Deliverable: `rop-big-rework-full-b2.rom`
(MD5 `ec7bcffe9c45fd851a6752dec5bcf788`, 1,048,576 bytes).
Patch: `patches/b2-strip/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `rings-of-power-big-rework-full-b2.ips`,
`source.bin`, `check_entries.py`). Original ROM untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`, re-verified after the build).
Dayset is the tester — no live probes, no screenshots, no cadence
measurements. One phase only: strip streaming. No sprites, no governor.

## 1. Docs read (in order, per brief)

- `BLOB_MAP.md` — B1 findings, measurements verdicts, free-space map.
- `DESIGN.md` §7.3 (strip streaming), §4.3 (banded decode), §5.2 (scroll).
- `.scratch-big-rework-full/b1-vram/REPORT.md` — B1 blob, gate, allocator.
- `.scratch-big-rework-full/measurements/REPORT.md` — verdicts only
  (R4 GO sprites, R5 1 sprite/16 tiles, R1 GO Scheme B acceptable,
  R2 NO-GO as specified / GO with corrected remap `(r−k, c−k)`, even
  band boundaries, T436E0 table ends at d1w=366).

## 2. Geometry the strip has to satisfy (verified in sim, not re-derived)

- Window 10×10 cells, camera (cx,cy), cell (r,c) → world
  (cx−5+r, cy−5+c); `d0 = 196+14(r−c)`, `d1 = 18+8(r+c)`;
  buffer tile row = r+c+2, stride 1152 B, buffer 36×23 tiles.
- Camera step (dcx,dcy) shifts every shared cell's decode by
  `Δd0 = −14(dcx−dcy)`, `Δd1 = −8(dcx+dcy)` in buffer px.
  Δd1 is always a whole number of tile rows (0, ±8, ±16);
  Δd0 ∈ {0, ±14, ±28} = whole tiles ± an even sub-tile residual
  (0, ±2, ±4, ±6 px — byte-aligned in 4bpp, 2 px/byte).
- R1 (measurements): shared cells are translation-invariant
  (0 px differ per cell); the 11.6–12.1% whole-image diff on a
  re-centre is 100% new/departed strip content, not flicker.
- `$E358` writes are per-nibble selects (R4): a strip cell decoded
  onto a zeroed buffer does NOT reproduce its bytes in the full
  render where its diamond overlaps shared cells decoded earlier
  in r-major order — the final byte is the ordered composite.
  Consequence: a strip decoded into a *cleared* scratch buffer and
  scatter-uploaded verbatim would clobber shared nibbles in the
  overlap region. The strip must be decoded on top of the shared
  content already in its new position (repack, §3), or uploaded
  with a VRAM read-modify-write. DESIGN §7.3 step 2 as literally
  written (clear scratch → decode strip → scatter-upload) does not
  account for this overlap composite.

## 3. Sim verdict: literal strip streaming is unbuildable for the 36×23 image — Scheme B it is

Script: `.scratch-big-rework-full/b2-strip/sim_strip.py` (uses the
measurements agents' `sim_value.py`/`render.py`, chunk 233, terrain
only, camera (7,7) → all 8 one-cell moves). Three tests:

- **A. Literal DESIGN §7.3 strip** (strip cells decoded alone into a
  cleared buffer, compared against the full new render on the strip
  bytes): **2.7–88.8% of strip bytes wrong**, direction-dependent.
  East/south strips (decoded last in r-major order) are 2.7–4.7%
  wrong; west/north strips (decoded FIRST, later shared cells
  overwrite their nibbles) are **80.6–88.8% wrong**. The strip
  cell's writes are not independent of shared cells' writes — the
  $E358 composite is a per-nibble select over ALL covering cells in
  render order (R4), so a strip decoded alone cannot reproduce the
  final bytes where its diamond overlaps shared cells (median
  neighbour overlap ~50 B, §1.4). Verbatim scatter-upload would
  corrupt those tiles.
- **B. Repack + strip** (shift the old buffer by (Δd0,Δd1), then
  decode the strip onto it in render order): **6.5–16.5% of bytes
  differ** from the full render, all 8 directions. Two causes:
  (i) render-order — a west/north strip decoded last overwrites
  shared nibbles that the true render's later shared calls own;
  (ii) height-status changes — cells at the trailing edge (r=8/c=8)
  lose their edge height-stack calls in the new window, and
  `$E358` can never clear a nibble, so the stale height bytes
  survive the repack. (The repack itself is exact: test C, byte
  repack == pixel shift, True in all 8 directions.)
- **C. Byte-level tile repack == pixel shift: True** (all 8 moves).
  The shift (Δd0 ∈ {0,±14,±28}, Δd1 ∈ {0,±8,±16}) decomposes
  into whole tile rows + an even sub-tile residual, byte-aligned
  in 4bpp. Recorded for any future repack work.

Why no cheap fix: the global shift (every shared cell moves
14 px) means a row-band/halo re-decode (§4.3 method) cannot fix
rows outside the strip band, and the plane-window slide (§7.3
step 3) only re-points whole tiles — it cannot reproduce the
per-nibble overlap composite, which is exactly the §1.4 result
that killed per-tile caching. An exact strip needs strip +
trailing-edge + halo cells decoded in order into cleared scratch
with a verified core-tile upload — ~40–70 `$E358` calls
(6–10 fr) for a saving of ~6–10 fr over a full re-decode, with
per-direction cell/tile lists to verify. That is a design + sim
phase of its own, not this phase. **Per the brief's fallback
clause, B2 builds Scheme B: the fix2 re-install gate, improved
to be seamless for all moves.** R1 verifies the re-centre is
flicker-free (shared interior bit-identical, 0 px differ), so a
full re-decode at the cell boundary is acceptable — its only cost
is the ~16 fr hitch per cell step, already accepted by Dayset
("loading new chunks at the edge is OK").

## 4. Scheme B improvement — what fix2 got wrong

The fix2 gate is seamless ONLY when the D-pad scroll has caught
up to the camera move — but the scroll is pad-driven while the
camera is game-driven, so catch-up is not guaranteed:

- **Cutscene/scripted moves** (`sys_event_run` walks Buc, pad not
  held): scroll stays 0, the gate suppresses, the camera keeps
  moving, dx grows past 1 cell, and the gate fires the ">1 cell"
  branch — a jumpy re-install mid-cutscene (the Buc cutscene
  walks 8 steps south).
- **Short tap / direction change**: the player releases the pad
  mid-slide, the scroll stops short of the extreme, the gate
  suppresses indefinitely, and the picture sits frozen with a
  blank strip on one edge ("patch on the left" in Dayset's
  playtest) until the pad is held again in that direction.
- The dx=dy=0-but-scrolled case has no self-correction at all
  under pad-driven scroll.

**Fix (B2, one change): the VBlank scroll follows the CAMERA,
not the pad** (DESIGN §5.3 in miniature — no fractional camera,
no governor, both out of scope for this phase). Each VBlank, the
hook computes the scroll target from (camera − installCam):
target hAcc = clamp(−(dx−dy),−1,+1)·224,
target vAcc = clamp((dx+dy),−1,+1)·128 (same formulas the gate
uses for its expected values), and steps the accumulators toward
it at the existing rates (16/16 px horiz, 9/16 px vert per
frame ≈ 14–15 fr per cell). Catch-up is now guaranteed within
~15 frames of ANY camera move — walked, scripted, or snapped —
with no pad input, and the scroll self-corrects to 0 whenever
the camera returns to the install camera. The gate itself is
unchanged: exactly-1-cell + caught-up → seamless re-install
(scroll reset, installCam updated); >1 cell (teleport / mode-6
cut) → immediate re-install, which is a cut, not a slide. The
pad still walks Buc (which moves the camera, which moves the
scroll); the PoC's "slide the picture without walking" demo
goes away — the full rework's scroll is camera-driven (§5.3),
and the dead zone still gates when the camera moves.
Cost per cell step stays the fix2 full re-decode (~16 fr) — the
hitch Scheme A would have removed; the picture is seamless
(no flicker per R1, no stall, no frozen offset) rather than
hitch-free.

## 5. Blob / hooks / state

Blob at `$FD900`, **1328 bytes** → `$FD900–$FDE30` (B1: 1376).
Entries (offsets from the vasm listing, never hardcoded):

| Entry | Offset | Address | Notes |
|---|---|---|---|
| `vbl_entry` | +0x0 | `$FD900` | **B2 NEW**: camera-target scroll (see §4) |
| `redraw_entry` | +0x254 | `$FDB54` | fix2 gate, unchanged |
| `scene_entry` | +0x4C0 | `$FDDC0` | reset install state, unchanged (was +0x4F0) |
| `mapclose_entry` | +0x4FA | `$FDDFA` | reset on map close, unchanged (was +0x52A) |

Hooks: `$1272` jmp `$FD900` (unchanged), `$1B918` jsr `$FDB54`
(unchanged — vbl is exactly the same size as B1's, 0x254, so
redraw did not move), `$12C20` jsr `$FDDF0` → jsr `$FDDC0`,
`$16302` jsr `$FDE2A` → jsr `$FDDFA`. Statics and allocator
unchanged from B1 (asserted, not touched: R4 `$8407`, pea
`$E000` ×2, R16 `$9001`, allocator `$12D00–$12DE7`). Stale B1
blob tail `$FDE30–$FDE60` overwritten with `0xFF`.

State: same dead RAM as B1 (`$FF00A0–$FF00C0`; installCam
`$FF00BC`/`$FF00C0`, `$FFFF` = none yet). The VBlank hook now
reads the camera (`$FF0E8E`/`$FF0E90`) and installCam instead
of the pad byte (`$FF0018` — no read of it remains in the blob,
asserted in build.py). It clobbers d0–d5 (was d0–d4; the movem
save/restore was extended to d5). Target/step code verified by
capstone disassembly of the built blob (see §6).

Toolchain note: this VM has **no m68k GAS** (`m68k-linux-gnu-as`
is not installed; B1 was built on a machine that had it), so
`source.s` is written in **vasm Motorola syntax** and assembled
with the in-worktree `vasm/vasmm68k_mot -m68000 -Fbin`
(entry offsets read from the `-L` listing). Vasm's encoding
choices vs GAS, all verified semantically identical:
branch displacements optimised to 8-bit where they fit
(redraw 48 B shorter, scene/mapclose offsets shift);
`adda.w #16,sp` encoded as `lea $10(sp),sp` (same effect,
same length, neither affects flags); one no-op
`bra .rdone` (branch to the next instruction, end of
`.rreset`) elided. The build verifies the three unchanged
entries by capstone disassembly comparison against the B1
blob (`check_entries.py`, run under the RoP venv python):
scene and mapclose identical (10/10 and 9/9 insns),
redraw identical except the three allowed encoding
differences above (145 vs 144 insns — the one elided bra).

## 6. Build checks (all passed)

- Base MD5 asserted `49530033…`; original MD5 asserted and
  re-verified `30c18fdbe2183f64702ae9f1a45d63f9` after the build.
- B1 blob in the base verified byte-identical to
  `patches/b1-vram/source.bin`; padding `$FDE60–$FDFFF` all
  `0xFF` in the base before patching.
- Every hook site's original (B1) bytes asserted before
  patching (`$1272`, `$1B918`, `$12C20`, `$16302`).
- Blob placement asserted in free `0xFF` padding; blob 1328 B
  ≤ `$FD900–$FDFFF`; stale tail cleared to `0xFF` and verified.
- New vbl_entry disassembled and reviewed instruction by
  instruction (capstone): init/validation/location-change
  blocks as B1; target clamp ±224/±128 with the gate's
  formulas; step-16/step-9 with not-past-target clamping;
  `asr #4` scroll extraction; write-if-changed; `.vnotroom`
  disarm + scroll-0 restore; `movem (sp)+,d0-d5/a0-a1` +
  `jmp $127A` tail. No `$FF0018` read anywhere in the blob.
- Checksums: `tools/checksum.py fix-all` then `verify-all`:
  size stored `0x42EA` = computed, runtime stored
  `0x52F08B13` = computed.
- IPS: 1858 bytes, 150 records, base → B2. **Round-trip
  verified: base + IPS == ROM exactly.** 1100 bytes differ
  base → B2 (header checksum `$18E`, runtime checksum
  `$FD098`, 2 hook targets, blob `$FD900–$FDE5F` — nothing
  else; verified by an independent diff after the build).
- `changed-bytes.txt`: full byte diff (150 records).

## 7. What Dayset should test

Walk the Academy (and other rooms) in `rop-big-rework-full-b2.rom`:

1. **Walk normally in all four directions** (and diagonally):
   the room should slide smoothly ~15 frames as the camera
   commits each cell, then re-install seamlessly — no frozen
   picture, no blank strip on any edge, no jump. This is the
   fix the B2 gate is for: B1 could stall after a short tap
   or a direction change.
2. **The Buc cutscene** (or any scripted walk): the camera
   moves with no pad held — the room must still slide and
   follow smoothly, with no mid-cutscene jumps (B1 jumped
   here: the gate's ">1 cell" branch fired because the
   pad-driven scroll never caught up).
3. **Walk back the way you came** (camera returns to the
   install camera): the scroll must self-correct to 0 and
   the picture sit exactly right — no leftover offset strip.
4. **Teleport / fast move / map open+close**: map close must
   still restore the room fully (B1 `mapclose_entry`
   behaviour, unchanged); a teleport is a cut (immediate
   re-install), not a slide — expected, not a bug.
5. **The PoC "hold the D-pad, room slides without walking"
   demo is GONE by design** — the scroll is now camera-driven,
   so the room slides when Buc walks (after the 3-cell dead
   zone), not when the pad is held while standing still.

Expected unchanged from B1: 36×23 image, black background, no
pink decoration or HUD (accepted side effect); ~16 fr hitch
per cell step at the re-install (the strip-streaming saving —
Scheme A — is NOT in this ROM, see §3/§8); figures frozen
(baked in at install, phase C work).

## 8. Open / queued items

- **Strip streaming, exact form (future design + sim phase,
  not B2):** the viable shape is strip + trailing-edge
  (height-status-changed) + halo cells decoded in render order
  into cleared scratch, uploading only the core tiles whose
  contributor set is complete — the banded-build halo method
  applied to a diagonal band, with the plane-window slide
  handling the global 14 px shift. Open questions: the
  per-direction cell lists and core tile sets (sim must verify
  byte-identity for all 8 moves, all rooms, figures included),
  and whether ~40–70 `$E358` calls (6–10 fr) is worth it over
  Scheme B's ~16 fr. The repack result (test C: byte repack
  == pixel shift, all 8 moves) and the (r−k,c−k) remap
  (measurements R2) are the verified pieces it builds on.
- **C sprites, D governor:** not built (one phase only).
- **40×28 image:** still blocked on custom `$E358` tables
  (B1 §2/§8).
