# Interp-fix — diagnosis + one-step camera delay

Worktree: `~/workspace/rop-work/interp-fix/`
Base ROM: `rop-interp.rom` (MD5 `309d87c5a97cdbc5c2066f11a2f98399`)
Deliverable ROM: `rop-interp-fix.rom` (MD5 `44353892c7a006300bfae2535ad6eaf8`)
Patch: `patches/interp-fix/` (`source.s`, `build.py`, `README.md`,
`changed-bytes.txt`, `interp-fix.ips` — IPS round-trip verified)
Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## 1. Diagnosis

### 1a. Why the slide is not visible — camera cancellation (CONFIRMED)

The interp slide is room-relative: the figure's drawn cell interpolates
old → new over phases 0–3 (0, ¼, ½, ¾, then the commit). But the camera
(`$FF0E8E/$FF0E90`) tracks the figure's committed cell exactly, so each
new cell's screen position is the centre, and the figure's on-screen
position = centre + slide_offset. The slide offset oscillates in
[−step, −step/4] across phases 0–3 and jumps back to −step at the next
commit. **Net on-screen progress over a full step cycle is ZERO.** The
figure never travels across the screen; it shuffles ~10 px behind the
centre, then the room jumps. That reads as "no subcell movement" /
"standing then teleporting" — exactly Dayset's playtest on the interp ROM.

Probe v2 (per-tick VBlank sampling, cutscene room, 90 records) confirms
the camera follows the cell: at 6 of 9 commits cam == Buc's cell in the
commit tick; at the other 3 the camera catches up by phase 1 (one tick
later — see §1d). The hunt had already live-proved cam == Buc's cell
every row in the cutscene room. The mechanism is the same in the B-zoom
room (the camera follows the leader's cell via `world_reposition_leader`
→ `leader_spawn` on every `combat_move_unit`).

The interp hook itself is sound (verified instruction by instruction in
`source.s`: gate, latch, template 36+dir, slide table, X/Y writes to
12(a6)/14(a6) before `hero_track` reads them, register discipline, `rts`
exit). The failure is not in the hook — it is in the interaction: a
room-relative slide under a cell-tracking camera cancels on screen.
**A visible on-screen slide requires the camera NOT to jump with the
cell — i.e. a camera delay (this fix) or a smooth-scrolling (fractional)
camera (the big rework).**

Dayset's loop-walk playtest confirms the split: Buc CAN walk in all
directions (the loop works), but the world shift is still jumpy. The
remaining jumpiness is the world/camera shift (the integer-cell camera
jumping a whole cell at each commit), NOT the figure's slide. This fix
makes the figure slide visible; the room still jumps once per cell at
the commit (see §3).

The feet-fix replay does NOT bypass the interp hook (it calls
`hero_track`, and the hook inside it still fires). The slide condition
(`$FF0110 == 0`) is correct for the walk — it is false during a script
by design, so the cutscene keeps the walk template + wobble.

### 1b. Why it is "even slower" — the pacing gate, not the hook

The interp hook adds ~100 instructions per `hero_track` call for Buc
(once per render) — negligible against an ~9-frame render. It does not
touch Path A, the pacing gate, `grid+$A`, or the phase counting.

Measured (probe v2, cutscene room, flat ROM): **~9.13 frames/tick**
(mostly 9, some 8/10), **1 cell per 4 ticks, ~36 frames/cell**
(commit gaps 34–39 frames). The original ROM is ~22 frames/cell
(1 cell/tick × ~22 frames/tick). So the interp/pacing walk is ~1.6×
slower in frames/cell than the original. The pacing ROM and the interp
ROM have the SAME cell rate (both 1 cell/4 ticks) — the interp ROM is
not slower than the pacing ROM in cell rate. The "even slower" feel is
the gradual slide making the slow pace visible (the figure now crawls
across the cell instead of jumping instantly, so the 4-tick wait reads
as slowness), and Dayset's "barely navigable" is the pacing gate's
1 cell/4 ticks being too slow for navigation. **Restoring original walk
speed needs a pacing change — a separate decision (Dayset's call).**
This fix does not change the cell rate.

### 1c. Walk slowness / navigation (Dayset follow-up)

Confirmed severe: at ~36 frames/cell the walk is ~1.6× slower than the
original in frames/cell, and the slide makes every cell feel like a
crawl. The cutscene is unaffected (fast, as on the feet-fix ROM — the
flat render makes each tick ~2× faster, so `sys_event_run` advances
the script ~1.6× faster; the pacing gate never fires during a script).
The walk-speed question is a pacing decision, not part of this fix.

### 1d. Cutscene lag — world jumps first, then Buc catches up (CONFIRMED)

Dayset: "in a cutscene, the world jumps first, then Buc catches up. In
the normal (original) ROM, Buc and the world jump together."

Mechanism, now probe-confirmed: **Buc's cutscene record has +10 == 1**
(probe v3/v4: `rec10 = 1` in every record). Per the static read of
`combat_move_unit` ($024984), when record+10 == 1 and a script is
running, the record does NOT step in `combat_move_unit` (it goes to
`L024E76` instead) and waits for the record stepper ($022F52), which
steps it at phase == stepphase (2 for template 38). The camera, by
contrast, moves at phase 0 (via `world_reposition_leader` →
`leader_spawn` in `combat_move_unit`'s epilogue). So the world (camera)
jumps at phase 0 and the figure's draw record does not catch up until
phase 2 — a 2-phase lag. That is exactly "the world jumps first, then
Buc catches up".

Probe v2 quantifies the camera-vs-char timing: at 3 of 9 cutscene
commits the camera lagged Buc's char cell by one tick at the phase-0
record (buc=new, cam=old) and caught up by phase 1; at the other 6 it
matched in the same tick. So the camera-vs-char lag is at most 1 tick
(likely a sampling race within the phase-0 tick — the char commit and
the camera update are sequential inside `combat_turn_run`, and the
once-per-tick VBlank sample sometimes lands between them). The FIGURE
lag (what Dayset sees) is the record's 2-phase lag, which is the
record+10 mechanism above — not the camera-vs-char race, and not the
slide (the slide is gated off during a script), not the subcell
template override (it only changes the image, not the record), not the
pacing gate (it never fires during a script), and not the flat render
(the flat render only makes ticks faster; it does not separate the
camera from the record). The original ROM jumps them together because
its record steps in `combat_move_unit` at phase 0 with the camera;
the patched ROMs expose the split because the flat render makes the
2-phase gap visible in real time. Whether the split is pre-existing in
the original ROM (record+10 == 1 is a property of the shipped record,
not something any patch sets) is a static fact — the record+10 value
comes from the shipped data, so the 2-phase record lag exists in the
original too, but at ~22 frames/tick it is less noticeable than at
~9 frames/tick on the flat ROM.

This fix does NOT touch the cutscene (gated off while `$FF0110 != 0`).

## 2. The fix — one-step camera delay

Hooks the two step-mode camera writes in `leader_spawn` ($01C21A):
`$01C2D8` (`move.w d0,$FF0E8E`, cam X) and `$01C300`
(`move.w d0,$FF0E90`, cam Y). Mode 6 (absolute set, teleports) is NOT
hooked and snaps immediately. Only step modes (0–3, 5) are delayed.

Gate: delay ONLY when no event script runs (`$FF0110 == 0`) AND the
world/room mode is 2 (room / B-zoom view). The cutscene
(`$FF0110 != 0`) and the overworld (mode 1) update the camera
immediately, exactly as before. A script starting, or leaving mode 2,
clears any pending camera so no stale cell is ever applied.

Delay: one step. When `leader_spawn` computes a new camera (cell N+1)
during a walk, the hook does NOT write it. It stores it as the pending
camera (`PEND_X/PEND_Y` at `$FFD010/$FFD012`, `PEND_VALID` at
`$FFD014`) and leaves `$FF0E8E/$FF0E90` at the old cell (N). On the NEXT
step-mode camera write (the next commit, 4 ticks later) it FIRST writes
the pending camera (cell N+1) to `$FF0E8E/$FF0E90`, THEN stores the new
camera (cell N+2) as pending. So the camera is always one step behind
the figure's committed cell.

Effect: at a commit the figure is drawn at the screen centre (its slide
offset −step cancels the one-step cell offset), then it slides smoothly
toward centre+step over phases 1–3 while the room stays still. At the
next commit the camera jumps one cell (the room scrolls) and the figure
is back at centre. **The slide IS visible on screen.** The room still
jumps once per cell at the commit — fully smoothing the world shift
needs a fractional (smooth-scrolling) camera, which is the big rework
(scroll-and-patch), NOT this fix. Cell rate is unchanged (1 cell /
4 ticks); speed is not worse than the pacing ROM.

Edge case: if the player stops walking mid-step, the last step's camera
stays pending (never applied) and the figure sits ~14 px off-centre
until the next step, when it corrects. Harmless.

Blob: 124 bytes at `$FDE00` (0xFF padding, above the runtime checksum
range). Hook sites: `$01C2D8` → `jsr camdelay_x` (`$FDE00`),
`$01C300` → `jsr camdelay_y` (`$FDE3A`). Both hooks exit with `rts`.
RAM `$FFD010–$FFD014` (adjacent to the interp RAM `$FFD000–$FFD00E`,
proven safe; well below the feet-fix list `$FFD800+`). The flat /
checkerboard, feet fix, subcell override, pacing gate, and interp slide
are byte-identical to the base; the big world stays textured.

## 3. What was NOT verified

No live probes, screenshots, cadence measurements, or playtest
verification of this ROM (Dayset's rule — he tests it himself).
Minimal build checks only (below). Dayset's playtest asks:
(1) does Buc slide visibly across the room while walking (all four
directions)? (2) does the room still jump once per cell at the commit
(expected — the big-rework item)? (3) is the cutscene unchanged
(fast, world jumps first then Buc catches up — the record+10
mechanism, untouched)? (4) is the overworld walk unchanged?
(5) menu / teleport unchanged? (6) is the walk still ~36 frames/cell
(the pacing gate, unchanged)?

Not probe-verified: whether the interp hook's latch fires in the B-zoom
room walk (the drive never reached room 30 — see §4), the exact
frames/cell in the walk (inferred ~36 from the cutscene, same pacing
gate and tick rate), and the camera-delay behaviour itself (the fix is
new; Dayset's playtest is the verification).

## 4. Probe history (how the diagnosis was reached)

- **v1** (`probe.s`, hero_track hook at `$023208`): logcount 0.
  The hero_track hook never fired (`hero_calls = 0` on both the interp
  and the original ROM), and the breakpoint test showed `hero_track`
  ($0231D8) never runs from this save state in 12 s. Likely cause: in
  the cutscene room Buc is drawn as an NPC figure, not via `hero_track`
  (the hero/leader is the off-map scaffold), so the hook inside
  `hero_track` never sees Buc's record there — and the drive never
  reached room 30, where Buc IS the hero figure. Also: the v1 probe
  state at `$FFD7E0–$FFD7FF` showed an anomaly (`buc_calls = 13285` on
  the interp ROM, 0 on the original), suggesting `$FFD7E0–$FFD7FF` may
  be game RAM — v2 moved the probe state to `$FFDF00` (near the log,
  proven-safe area). The v1 probe was abandoned, not the diagnosis.
- **v2** (`probe2.s`, VBlank per-tick sampling, no hero_track hook):
  90 records, cutscene walk (8,7) → (6,17) → (6,25), phase-0 commits,
  ~9.13 frames/tick, ~36 frames/cell, camera follows the cell (lags by
  at most 1 tick, catches up by phase 1). Log filled during the
  cutscene; the drive never reached room 30.
- **v3/v4** (`probe3.s`/`probe4.s`, logging gated to the room-30 phases,
  `rec10` field): both filled 90 records at the cutscene end position
  (6,25) with the script still running (`$FF0110 = $FFFF`,
  `owstable = 0`). The dialog advance never finished the script:
  `$FF010A = 2` alone (v2) reached the overworld once, but holding A
  (v3) or edge-pressing A (v4) did not — the A-button pad injection
  appears to interfere with the script flow, and the B+START/B map
  navigation to room 30 is unreliable (v2 ended back in the cutscene
  room, loc 156). The drive was not iterated further; the diagnosis
  does not depend on room-30 probe data (the slide mechanism is
  statically verified, and the camera-follow is probe-confirmed in the
  cutscene room, where the same `leader_spawn` path runs).
  **v3/v4 did confirm `rec10 = 1`** for Buc's cutscene record in every
  record — the cutscene-lag mechanism (§1d).

## 5. Build verification (minimal checks only)

- `checksum.py verify-all rop-interp-fix.rom`: header `0xD0E0` OK,
  runtime `0x92B36312` OK, exit 0.
- MD5s: original `30c18fdbe2183f64702ae9f1a45d63f9` (untouched), base
  interp `309d87c5a97cdbc5c2066f11a2f98399` (untouched), fixed
  `44353892c7a006300bfae2535ad6eaf8`.
- 123 bytes differ from the base, confined to the header checksum, the
  two hook sites (`$01C2D8`, `$01C300`), the runtime immediate, and the
  blob (`$FDE00–$FDE7B`). All earlier blobs byte-identical
  (`$FD400–$FDE00`); all other hook sites untouched (hero_track
  `$023202`, pacing gate `$0228CC`, fig_replay `$01C0D6`, flat call
  sites); mode-6 camera writes (`$01C242`, `$01C264`) untouched.
- IPS round-trip verified: base + `interp-fix.ips` == fixed ROM.
- Hook code hand-verified from the vasm listing (gates, branch targets,
  `rts` exits, displaced `move.w` instructions in the immediate paths).

## 6. Open decisions (Dayset's call, not part of this fix)

1. Restoring original walk speed (a pacing change — the walk is
   ~36 frames/cell vs ~22 original; "barely navigable").
2. Slowing the cutscene (a tick-rate change — it runs ~1.6× faster
   on the flat ROM).
3. The big rework (decode-once-and-reuse / scroll-and-patch +
   sprites, starting with the stable-tiles investigation) — the only
   thing that fully smooths the world shift at the commit.
