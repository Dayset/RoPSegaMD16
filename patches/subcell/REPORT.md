# Subcell movement — REPORT

## Deliverable

- **ROM:** `~/workspace/rop-work/subcell/rop-subcell.rom`
  - MD5 `fa3255df47fe90efc6cb1c36c2e495db`
  - Header checksum `0x78CC`, runtime immediate `0xA24C62E7` (both verify)
- **Patch:** `~/workspace/rop-work/subcell/patches/subcell/`
  (`source.s`, `build.py`, `README.md`, `changed-bytes.txt`,
  `subcell.ips` — 356 B)
- **Base ROM:** `rop-flat-zoomed-feet.rom` (MD5
  `9373c0d01cf08c20f28e256daa9ea142`) — flat only on mode 2, feet fix.
  The base ROM and the original ROM (`30c18fdbe2183f64702ae9f1a45d63f9`)
  are untouched (MD5s re-verified after the build).

## What it does

One fix only: the leader figure's movement in the B-zoom view (mode 2,
the room) uses subcell interpolation — the figure moves in small steps
across a cell instead of jumping a whole cell per tick. Same mechanism
as the Buc cutscene walk, which already moves subcell.

## Design

A single hook inside `hero_track` at `$023202` (the `lea.l $197B0,a0`
that loads the template-table base), repointed to a 222-byte blob at
`$FD800` (0xFF padding in the base ROM). The hook overrides the
template index in register `d0` only — it never modifies the draw
record in RAM.

- **Gate: mode 2 + Buc's record.** Only when `$FF00AE == 2` (room /
  B-zoom view) and only for Buc's draw record (char 1; record index at
  `$FF02EC` = char `+0x04`, the index `map_grid_create` assigned — see
  "Static findings" below). Every other figure, and the big world
  (mode 1), uses the original template.
- **Walk template: `36 + facing dir`.** Dir 0=N, 1=E, 2=S, 3=W
  (`world_get_step_delta` `$01E022` pins this order). Template 38 is
  the cutscene walkers' template (Buc walking south); 36/37/39 are its
  siblings (stepcodes 1/2/4 = dirs 0/1/3). Per-phase dx/dy come from the
  `$197B0` table, indexed by the grid+`$A` phase (0–3). The template
  offset is `template*36 + phase*8`, exactly as `hero_track` computes it.
- **Movement latch (RAM `$FFD000`–`$FFD006`, free scratch, no ram.csv
  entry).** Latches ON when Buc's cell changes, OFF at the next phase-0
  render with no cell change. A standing Buc keeps the original static
  template (no idle wobble). Walk-template group 0 has dx/dy (0,0), so
  phase 0 is exact in any case.
- **Safety: the record is never touched.** The `$022F52` record stepper
  still sees the original static template (stepcode 0 = no-op, confirmed
  by dumping the jump table at `$023076`) and never moves the record on
  its own. The flat gate, flat colours, and feet-fix replay are
  untouched (both blobs byte-identical to the base ROM).

## Static findings (supporting the design)

- **Template table `$197B0`** (dumped from the ROM, 36 bytes per
  template: 4 groups × (stream, param, dx, dy) + tail (stepcode at
  +0x20, stepphase at +0x22)). Templates 0, 4, 5, 6, 7, 29 are static
  (all dx/dy 0,0). Templates 36–55 are walk templates with per-phase
  dx/dy and stepcode 1–4, stepphase 1–2. Template 38 (the cutscene
  walkers', draw records with +2=2, +4=$24): groups (0,0,0,0),
  (6,0,−4,2), (1,0,6,−4), (7,0,2,−2), tail stepcode 3, stepphase 2.
- **Direction mapping:** `world_get_step_delta` table `$01E086`:
  dir 0 → (0,−1) North, dir 1 → (+1,0) East, dir 2 → (0,+1) South,
  dir 3 → (−1,0) West. Stepcode = dir + 1 (stepper table `$023076`:
  stepcode 1→`$64` (dir 0), 2→`$65`, 3→`$66`, 4→`$67`, 5→SFX/spawn,
  0→`$23094` fall-through = no-op). So template 38 (stepcode 3) = dir 2
  = South, matching Buc's south walk. Walk template = 36 + dir.
- **char.+0x04 is the draw-record index.** `map_grid_create` writes the
  assigned record id to char.+0x04 (`$024632`, `$024878`), and
  `$0245C0` uses char.+0x04 as the record index to write record+10.
  Buc (char 1, `$FF02E8`) → record index at `$FF02EC`, heading at
  `$FF02F2`, grid X/Y at `$FF02F4`/`$FF02F6`.
- **`hero_track` template computation** (`$0231E6`–`$023200`):
  `d0 = (record+4 + record+2) * 36 + phase*8`, then `a3 =
  $197B0 + d0`. The hook at `$023202` replaces the `lea` that loads the
  table base, so it runs after the frame is linked (a6 is the frame
  pointer; the record is the stack arg at 8(a6)) and after d0 holds the
  original offset. It returns via `rts` to `$023208`
  (`movea.l d0,a3; adda.l a0,a3`).
- **Record stepper gate:** the `$022F52` loop only steps records whose
  template stepphase matches the phase; static templates have stepcode
  0, which the jump table routes to a fall-through no-op. Since the hook
  never writes the record, the stepper is unaffected.
- **The room figure is Buc (char 1).** In the room, Path A resolves the
  leader's queue direction to the leader scaffold's figure (Buc), and
  the leader scaffold stays off-map at (117,113). So animating char 1
  in mode 2 covers the B-zoom view.

## Build checks (minimal only — no live tests, per Dayset's rule)

- `vasm` assembled the 222-byte blob cleanly; `subcell_hook` parsed
  from the listing at `$FD800` (== blob base).
- Hook-site bytes verified before patching: `$023202` was
  `41F9 000197B0` (`lea.l $197B0,a0`); after patching it is
  `4EB9 000FD800` (`jsr $FD800.l`).
- Blob region `$FD800`–`$FD8DD` was 0xFF padding in the base ROM.
- `checksum.py verify-all` on the built ROM: header `0x78CC` OK,
  runtime `0xA24C62E7` OK (exit 0).
- Changed bytes: **208**, confined to the header checksum (2 B), the
  hook site (5 B — one byte coincides), the runtime immediate (3 B),
  and the blob (`$FD800`–`$FD8DD`). Full ranges in `changed-bytes.txt`.
- Flat blob (`$FD400`–`$FD600`) and feet-fix blob (`$FD600`–`$FD780`)
  byte-identical to the base ROM; the flat/feet-fix hook sites
  (`$01BD98`, `$01C0D6`, terrain `$E358` sites) untouched.
- IPS round-trip verified: base ROM + `subcell.ips` == built ROM exactly.
- The vasm listing was read in full and every branch target re-checked
  by hand against the symbol table (68000 branch displacement is
  relative to instr+2); the displaced `lea.l $197B0,a0` is byte-identical
  to the original, and the movem save/restore masks are consistent
  (`d1-d2/a0-a2`; d0 is the intentionally-overridden offset, a6/a3
  untouched).

## What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification were run on this ROM (Dayset's 2026-11-12 ~21:08 EST
restatement: he tests it himself). In particular NOT verified:

- Whether the movement actually looks smooth in real play (the open
  pacing question below).
- The look in any room, the Buc cutscene room, or the overworld.
- Menu / teleport on this ROM (code-gated only).
- The 128-entry figure-list cap, multi-level rooms, room water.
- Speed / cadence before vs after (no measurement was taken; the hook
  adds a few dozen cycles per `hero_track` call, negligible against
  ~8 frames/render, but that is an estimate, not a measurement).

## Open question — the pacing (Dayset's playtest is the check)

The template override gives Buc the cutscene walk animation, but
whether the movement is smooth depends on when the leader figure's
cell commits:

- If the cell commits every 4 ticks (phase 3→0 wrap, as
  `docs/subcell.md` says), the walk-template offsets interpolate
  across the 3 in-between ticks and the movement should read as smooth
  as the cutscene.
- If the cell commits every tick, the figure will still jump a full
  cell per tick with a ±6 px wobble on top — visibly jumpy, not smooth.

The static link tying grid+`$A` to the leader's committed-cell step is
still open (cutscene-open hunt, item 2 §9: the gate is inside
`combat_move_unit` or the move queue). No live probe was run to close
it, per the no-tests rule.

**Playtest asks (for Dayset):**
1. In the B-zoom view, walk Buc in a straight line. Does he glide
   smoothly across cells (like the cutscene walk), or does he still
   jump a whole cell per step with a small wobble?
2. Stand still. Buc should be perfectly still (no jitter) — the latch
   reverts to the static template when he is not stepping. Report any
   idle shifting.
3. Walk in all four directions (N/E/S/W). Each should use its own walk
   template; report if any direction looks wrong (e.g. sliding
   sideways, or a facing that does not match the movement).
4. Menu dismiss + teleport still work; the room stays flat green; the
   big world stays textured; Buc's feet stay visible.

If case 1 still jumps, the follow-up is a pacing gate in the movement
block (force the cell commit to the phase 3→0 wrap) — a separate fix,
not in this ROM.
