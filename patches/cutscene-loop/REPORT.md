# Cutscene loop-walk — report

## Deliverable

- **ROM:** `~/workspace/rop-work/cutscene-loop/rop-cutscene-loop.rom` —
  MD5 `79bccdcd927707802332f64f38faa641` (header `0x1A9D`, runtime
  `0xA15C806B`; both verify, `checksum.py fix-all` exit 0)
- **Patch:** `~/workspace/rop-work/cutscene-loop/patches/cutscene-loop/` —
  `source.s`, `build.py`, `README.md`, `changed-bytes.txt`,
  `cutscene-loop.ips` (406 B, round-trip verified: base + IPS == ROM)
- **Base ROM unchanged** (`rop-flat-zoomed-feet.rom`, MD5
  `9373c0d01cf08c20f28e256daa9ea142`); **original ROM untouched** (MD5
  `30c18fdbe2183f64702ae9f1a45d63f9`).

## Does the full 20-cell loop fit? NO.

The room (location 156, chunk 233) is a 32x32 **maze**, not an open
floor. Chunk 233 was decoded with `tools/decode_chunks.py` (2048 B,
layout verified against the doc's known cells: (6,17) `0x00DA` tile 218,
(9,17) `0x00D5`, (6,25) `0x00B8`, wall (2,26) tile 210) and walkability
mapped per cell (terrain 5/9/18 or tile `$24`, no height stack, no
step-tile bit 10, no hazard bit 11; terrain from the `$5EDC4` table,
bits 10–15). Findings:

- A 20x20 square loop from Buc's start (6,17) is impossible: south
  runs out of bounds at Y=37, and the room's south wall is at Y=29.
- Largest fitting **rectangle** from (6,17) avoiding the students:
  **7x2** (7 south, 2 east, 7 north, 2 west, 18 cells). Ignoring the
  students: 11x2. The largest rectangle anywhere in the room is 4x15
  at (5,4) — not Buc's start.
- Straight runs from (6,17): south 8 cells (to Yoppa at (6,25)),
  east 3 (to Thalmus at (9,17)), north 14, west 0 (wall).

So the driver does **not** run a fixed 20x20 square. Buc walks **up to
20 cells per leg** in the order S,E,N,W (Dayset's "20 down, 20 right,
20 up, 20 left") and **turns to the next direction when blocked**
(wall/student) or after 20 steps. He walks each direction as far as
the room allows, keeps moving (no long stands on blocked legs), and
the loop repeats while the cutscene is active. The 20-cell leg length
is kept as the per-leg maximum.

## Mechanism (one fix only, on top of the feet-fix ROM)

Two hooks, one 266-byte blob at `$FD800` (free 0xFF padding, after the
feet blob ending at `$FD780`). The flat gate (mode 2 only) and the feet
fix are byte-identical to the base; the big world stays textured.

### Hook 1 — loop driver, `sys_event_run $02D56E`

Replaces `tst.w $FF010A.l` (6 bytes, `4a79 00ff010a`) with
`jsr loop_drive` (`$FD800`). While the Buc cutscene is active, steps
Buc one cell along the loop via `combat_move_unit(1, dir)`, once per
`sys_event_run` call (one cell per 4 ticks, the script's pace). It sits
**before** `sys_event_run`'s `$FF010A==0` early return (read in rop.s:
`$02D56E tst.w $FF010A; bne L02D592; ... rts`), so Buc keeps walking
even while a dialog message is on screen. The displaced `tst.w`
is re-executed last, so the `bne` at `$02D574` reads the correct flags.
All registers saved/restored (`movem.l d0-d7/a0-a6`).

Gate: `$FF0110 != 0` AND script pointer `$FFC384` in `[$1A228, $1A390]`.
On the first call (pointer == `$1A228`) the state is reset (dir=S,
step=0) and the move is skipped (the op-1 teleport runs in the same
call, placing Buc at (6,17)). Invalid state (garbage RAM) also resets
to S/0.

A leg ends after 20 steps OR when Buc is blocked (his X/Y unchanged
by `combat_move_unit` — the position is only written when cost > 0).
Next direction = (dir+3) mod 4, giving S(2),E(1),N(0),W(3). The
camera follows Buc through `combat_move_unit`'s epilogue
(`world_reposition_leader` → `leader_spawn`); Buc passes the camera
gate (`(type>>4)&0x3F == 0`).

### Hook 2 — suppress the script's Buc moves, op-5 handler `$02D7F6`

Replaces `jsr combat_move_unit.l` (6 bytes, `4eb9 00024984`) with
`jsr loop_op5` (`$FD8E2`). The op-5 handler (`$02D7D6`, read in rop.s)
pushes dir (record b3) then the resolved char (`npc_attitude_raise_by_id`
of record w4) and calls `combat_move_unit(char, dir)`. If the char is
Buc (1) and the Buc cutscene is active, the blob returns without
moving (the handler pops its args and advances the script pointer via
`L02DBEA` normally). Otherwise it tail-calls the real
`combat_move_unit` with `jmp` (the stack already holds ret/char/dir
exactly as a direct `jsr` would). This keeps the loop's step count in
sync with Buc's position — without it the script would move Buc a
second cell in the same tick. Thalmus's moves (char 3) and other
scripts are unaffected. Only d0 is used (scratch).

### Loop state (RAM)

- `$FFD100`: loop_dir (word) 0=N,1=E,2=S,3=W. Start 2 (S).
- `$FFD102`: loop_step (word) steps in the current leg (0..19).
- Free: not in `disasm/symbols/ram.csv` (only `$FFD2EA` is used in
  that range); not the feet-fix list `$FFD800/$FFD802`; not the
  subcell latch `$FFD000-$FFD006`.

### Why `combat_move_unit` and not a direct X/Y write

Writing Buc's struct X/Y directly would not update the grid
cell→record maps (the render would draw him at the old cell) and
would not move the camera. `combat_move_unit` does all three
(record step, `world_reposition_leader` camera step, facing) in one
call, and it is the routine the script itself uses for Buc (via op-5),
so the move is the same kind the cutscene already performs. Its
walkability check (`move_cost_calc` cost 0 = blocked) is what makes
the turn-on-block work.

## Build checks (minimal only)

vasm assembled the 266-byte blob cleanly; `loop_drive` parsed from
the listing at `$FD800`, `loop_op5` at `$FD8E2`. Listing hand-verified
instruction by instruction (all branch displacements land exactly —
e.g. `beq.w .done` +202 → `$FD8D6`, `bhi.s .reset` +14 → `$FD85C`;
the movem masks `0xFFFE`/`0x7FFF` are the correct complementary
encodings for predecrement/postincrement; the displaced `tst.w
$FF010A.l` is byte-identical to the original). Hook-site bytes
verified before patching (`$02D56E` was `4a79 00ff010a`, `$02D7F6`
was `4eb9 00024984`). **258 bytes differ**, confined to the header
checksum, the two hook sites, the runtime immediate, and the blob.
IPS round-trip verified. Flat blob (`$FD400-$FD600`) and feet blob
(`$FD600-$FD780`) byte-identical to the base (asserted in build.py).

## What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification (per Dayset's rule). In particular not verified:
whether Buc actually walks the loop in real play; whether the camera
follows him around the loop; whether the dialog and Thalmus's moves
still run; whether Buc stepping onto a student's cell "picks up" that
student as a follower (the `combat_move_unit` pickup path — a student
would then trail Buc); how far Buc gets before the script ends (the
loop repeats, but the script's ~22 record-executing calls plus dialog
stalls set how many cells he covers — lingering at the dialogs lets
him cover more; mashing A may end the cutscene partway through a
loop); or the walk in other rooms. The flat gate and feet fix are
byte-identical to the base, so the render path is unchanged.
