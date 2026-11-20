# D report — tick governor + chunk loading (INCREMENTAL — updated as work lands)

Worktree: `~/workspace/rop-work/big-rework-full/` (main tip `3d9dff5` after
the M7 landing; the big-rework line is untouched by it).
Base: `rop-big-rework-full-c.rom` (MD5 `385fa655a5a060ac6b66de8b9de795dd`,
asserted 2026-11-20). Original ROM untouched (MD5
`30c18fdbe2183f64702ae9f1a45d63f9`, re-verified at start).
Previous D agent (92fab78d) died silently 2026-11-13 with nothing
delivered; this is a FRESH start, not a resume.
Dayset is the tester — minimal build checks only, no live probes,
no screenshots, no cadence measurements. One phase only: governor +
chunk loading. Nothing on main.

## 0. Milestone 1 — ground facts + design (2026-11-20)

### 0.1 Docs read
- `BLOB_MAP.md` (B1/B2/C findings, free-space map, governor + chunk
  design pointers), DESIGN.md §5.5 (tick governor), §7.1/§7.2 (chunk
  loading), §7.3/§7.4 (strip / Scheme B fallback).
- `.scratch-big-rework-full/c-sprites/REPORT.md` (§1–§2: blob
  $FD400–$FE6C5, hooks, sprite state $FFD000–$FFD2FF, slide rates,
  trailing-lag limitation) + `patches/c-sprites/source.s` (vbl_entry,
  scene/mapclose, sprite_init call sites).
- `.scratch-big-rework-full/b2-strip/REPORT.md` (§4–§5: camera-driven
  scroll, gate, blob $FD900, room-156-only scroll).
- `patches/interp-fix3/pace.s` (pacing gate v2: turn check + phase
  gate, proven in interp-fix3/fix4 playtests).

### 0.2 Tick structure (verified in disasm/src/rop.s, not assumed)
- Main loop `main_loop` $00D28E: calls `world_tick` at $00D2E0 and
  `combat_turn_run` at $00D97E once per iteration, under IDENTICAL
  guards (`$FF00AC==0` or `$FF0030>$32`; menu-open goes to a busy-wait
  at $00D986). One iteration = one "tick".
- Frame counter `$FF0010` (long, `ram_sys_field_0010`) increments once
  per VBlank (`addq.l #1` at $00127A in `vblank_handler` $001272; the
  C blob's vbl hook returns via `jmp $127A`, so it still increments).
  The governor reads it in the main-loop hooks — NO VBlank hook needed.
- `world_tick` $02155E: `grid+$A = (grid+$A+1) mod 4`; `$FF0092 =
  ($FF0092+1) mod 2` (shimmer); `$FF0094 = grid+$A mod grid+$8`.
  In rooms grid+$8==1 so `$FF0094==0` always (movement every tick).
- `combat_turn_run` $0226BC: `$FF0094!=0` skips the movement block
  ($022790→$022F3E); `sys_event_run` runs only when `$FF0110!=0` AND
  `grid+$A==0` ($022764–$022778, once per 4 ticks); the movement loop
  runs when `$FF0094==0`; the per-char loop at $0227FC pops the
  leader's queued direction (Path A, $0228CC `cmpi.w #$4,-$e(a6)`)
  and NPC directions ($022B50 phase test / $022B56 move call).
- Heading: written by `combat_move_unit`'s epilogue at $024D76 to
  `$FF02BE + char*$34` (`ram_sys_field_02be` array); char 1 (Buc) =
  `$FF02F2` — confirming pace.s's address. The turn check below uses
  the LEADER's heading computed from `ram_party_leader` ($FF02B2):
  `$FF02BE + leader*$34`, so it stays correct even if the leader
  is not Buc.

### 0.3 Governor design (6 hook sites, all 6-byte replacements)
State in free RAM `$FFD300–$FFD31F` (no `$FFD3xx`–`$FFD7xx` refs in
rop.s; sprite state is $FFD000–$FFD2FF, untouched):
`$FFD300` GOV_MAGIC ($9C07), `$FFD302` GOV_K (default 5 VBlanks/tick),
`$FFD304` GOV_NPCDIV (default 4 phase-0 ticks per NPC/script step),
`$FFD306` GOV_NPC (phase-0 counter, init GOV_NPCDIV−1 = 3),
`$FFD308` GOV_LAST (long, `$FF0010` at last tick), `$FFD30C` GOV_RUN.
K and the NPC divisor live in RAM (not immediates) so Dayset's
walk-pace decision is a one-word change later. Built at the ORIGINAL
pace by default; the pace decision is Dayset's, not this phase's.

- H1 `$00D2E0` `jsr world_tick` → `jsr gov_world_tick`: if
  (`$FF0010` − GOV_LAST) ≥ GOV_K → GOV_LAST = `$FF0010`,
  GOV_RUN = 1, `jsr world_tick`, then if the new `grid+$A == 0`
  bump GOV_NPC = (GOV_NPC+1) mod GOV_NPCDIV; else GOV_RUN = 0,
  skip world_tick. (Init-on-first-use via GOV_MAGIC in every entry.)
- H2 `$00D97E` `jsr combat_turn_run` → `jsr gov_combat_turn`:
  if GOV_RUN==1 → clear it, `jsr combat_turn_run`; else skip.
  The two hooks stay in lockstep (one world_tick + one
  combat_turn_run per governor-tick); the game's menu guards are
  untouched (the hooks only fire when the game calls the routines).
- H3 `$0228CC` Path A `cmpi.w #$4,-$e(a6)` → `jsr gov_path_a`
  (pace.s v2, leader-heading version): if the popped direction
  differs from the leader's heading → allow immediately (face
  turns in one press); same direction → allow only when
  `grid+$A==0` (1 cell per 4 ticks); skip path discards the jsr
  return and `jmp $022960` (Path A's standard skip exit).
  Dir 4 (stop sentinel) takes the allow path; the displaced cmpi
  sets the flags and Path A's `beq` skips exactly as before.
- H4 `$022778` `jsr sys_event_run` → `jsr gov_sys_event`: run the
  script step only when GOV_NPC==0 (every 4th phase-0 tick =
  every 16th governor-tick ≈ 80–96 fr ≈ original ~88 fr);
  else skip. GOV_NPC only advances on phase-0 ticks, so
  GOV_NPC==0 always coincides with a phase-0 tick (no deadlock
  from counter misalignment); init GOV_NPC = GOV_NPCDIV−1 so the
  first phase-0 tick is allowed (no startup delay).
- H5 `$022B54–$022B59` (`bne.b $022B64` + `move.w -$e(a6),-(a7)`,
  6 bytes) → `jmp gov_npc`: re-tests `grid+$A` (the phase gate
  for destination NPCs: 1 step per 4 ticks ≈ 20–24 fr ≈ original
  ~22 fr), then tests `$FF02B8 + char*$34` — wandering NPCs
  (`== $FFFF`) additionally need GOV_NPC==0 (80–96 fr ≈ original
  ~88 fr); allow path re-executes the displaced `move.w` and
  `jmp $022B5A`; skip path `jmp $022B64`. (A 4-byte `bra.w`
  cannot reach the blob from here; the 6-byte window covering the
  branch + the move is the hook.)
- H6 `$12C20` `jsr scene_entry` → `jsr gov_scene`: chains to C's
  scene_entry (`$FE656`), then clears the sprite magic (`$FFD000`)
  so `sprite_init` re-runs on the next decode/update and the stale
  slots are dropped (see §0.5). Called on every scene setup
  (`world_map_draw` callers $015008/$01552C/$0195C4).

Pace arithmetic (the lag-closure claim, to be verified by the
measurements in §0.4): governor tick ≈ 5–6 fr (quantised by the
~3 fr loop iteration) → leader 1 cell per 4 ticks ≈ 20–24 fr/cell
(original ~22 fr/cell). The C sprite slide takes ~7 fr/cell
(±2 px/fr horiz, ±1.125 px/fr vert over a 14×8 px cell) and the
B2 scroll ~14–15 fr/cell — both FASTER than the step rate, so the
scroll catches up before the next step (gate stays seamless) and
the sprite reaches its TARGET (~7 fr after the step) well before
the next step (~20–24 fr later). The trailing lag should close.
The re-install hitch (~16 fr) sits inside one iteration and does
not multiply: per cell ≈ 3 normal ticks + 1 re-install iteration
≈ 25–30 fr, in the same ballpark as the original 22 fr/cell.
Dayset judges the feel by playtest; the pace knob (GOV_K) is his.

### 0.4 What still needs measuring (before calling the lag closed)
- The governor's effective tick cadence under the loop's ~3 fr
  iteration quantum (predicted ~6 fr/tick standing still).
- That TARGET updates track the leader's steps (decode on the
  install tick) and the slide finishes before the next step.
  (Static reasoning above; a diagnostic BlastEm run is a
  measurement, not a playtest, and is allowed if the static case
  is inconclusive — prefer the static case first.)

### 0.5 Chunk loading — what the design says + the one concrete gap
DESIGN §7.2: the data-chunk load is UNCHANGED (`map_chunk_cache_read`
+ 4-slot cache + `$DD5C`, ~1.2 fr on miss); location doors
(tile 0x11a/0x11b) are the chunk-edge-with-transition
(`world_location_transition` $01DA6C → full load path); pre-loading
the adjacent data chunk is NOT needed. B2's Scheme B (full
re-install per cell step) IS the documented fallback, already built.
So part 2 is verification + concrete gaps, not a new streamer.

Verified by code reading (no change needed):
- Location change: the C VBlank location-change block
  (`$FF0E98 != $FF00B4`) clears installed/armed/scroll and sets
  installCam = $FFFF; scene_entry resets the install state too.
  The first redraw after the transition installs the new room.
  Stale sprites are hidden while installed==0 (VBlank sprite
  update is guarded by installed==1).
- Data-chunk boundary (overworld): the window spans data chunks
  and `map_chunk_cache_read` loads on demand; the gate re-installs
  per camera move from the current camera, so the new chunk's
  cells decode through the cache. No image-layer event exists or
  is needed (§7.1).
- Sprite anchors / install camera: anchors are per-decode, TARGET
  is in world diamond-px (recomputed on decode); `screen = CUR −
  installCam + scroll` is invariant under re-install (C §1.6), so
  a re-install does not disturb a sliding sprite. CUR snaps when
  TARGET jumps > 1 cell, so a transition does not smear.
- Overworld scroll is 0 by design (B2 `.vnotroom`: disarm, keep
  installed, scroll 0); the overworld moves by re-install, not
  slide. Unchanged.

CONCRETE GAP FOUND (fix in this phase, hook H6 above): the sprite
slots are NOT invalidated on a location change. The decode scan
frees slots whose recIdx is absent — but a stale slot whose recIdx
COINCIDES with a new-location figure's recIdx (byte-map indices
0–55, reused per room) keeps its old pattern/anchor/TARGET until
round-robin re-decodes it (leader + 2 per tick, so up to ~3 ticks
≈ 15–18 fr of a wrong-pattern figure at a wrong position after
every door). Fix: H6 clears the sprite magic on scene setup, so
`sprite_init` (called from `sprite_update` and `decode_figures`
when the magic is not $9C07) drops all slots and the figures pop
in freshly decoded over the next 2–3 ticks instead of showing
stale ones.

### 0.6 Hook-site bytes asserted in the C ROM (before patching)
- $00D2E0 `4e b9 00 02 15 5e` (jsr world_tick.l)
- $00D97E `4e b9 00 02 26 bc` (jsr combat_turn_run.l)
- $0228CC `0c 6e 00 04 ff f2` (cmpi.w #$4,-$e(a6))
- $022778 `4e b9 00 02 d5 6a` (jsr sys_event_run.l)
- $022B54 `66 0e` (bne.b $022B64 — opcode $66 = BNE, verified) +
  $022B56 `3f 2e ff f2` (move.w -$e(a6),-(a7))
- $12C20 `4e b9 00 0f e6 56` (jsr $FE656, C scene_entry) — VERIFIED
  2026-11-20 before the build. Also re-verified in the same pass:
  $1272 `4e f9 00 0f d4 00` (jmp $FD400, C vbl) and $1B918
  `4e b9 00 0f da 42` (jsr $FDA42, C redraw) — C's hooks intact.
- Free ROM $FE6C6–end: 6,458 bytes, all 0xFF. Blob goes at $FE6C6.
- Free RAM $FFD300–$FFD31F: no refs in rop.s (sprite state ends
  $FFD2FF; B2 state is $FF00A0–$FF00C0, untouched).

## 1. Build + verification (DONE 2026-11-20)

Two corrections found while writing the source, both caught before
the build:

1. **H6 cannot `jsr` C's scene_entry.** Reading the C source: its
   scene_entry does NOT end with rts — it discards the jsr return
   (`addq.w #4,sp`), resets the install state, then
   `link a6,#-4; pea.l $000CCAD8; jmp $012C2A` into world_map_draw.
   It never returns. So gov_scene tail-calls it (`jmp $FE656`)
   after clearing the sprite magic. The build asserts the tail-call
   bytes (`4e f9 00 0f e6 56`) are present in the blob.
2. **Opcode guess for the build assertions was wrong.** `move.w #5,
   $FFD302.l` encodes as `33 fc 00 05 00 ff d3 02`, not `3c 3c ...`.
   Fixed by reading the capstone disassembly; the build asserts the
   real encodings (K=5, NPCDIV=4, magic $9C07, `clr.w $FFD000`,
   `jmp $FE656`).
3. **vasm listing reports absolute addresses with `org $FE6C6`.**
   The source uses `org 0` (C's convention) so the listing values
   are blob offsets and `gov_world_tick` is at offset 0; `gov_init`
   was moved to the end of the blob. `jsr WORLD_TICK` /
   `COMBAT_TURN` / `SYS_EVENT` also needed `equ` definitions
   ($02155E / $0226BC / $02D56A) — vasm has no undefined-symbol
   fallback.

Build: `python3 patches/d-governor/build.py` — exit 0, DONE.
- Blob: 472 bytes at $FE6C6–$FE89D. Entries: gov_world_tick +0x0,
  gov_combat_turn +0x80, gov_path_a +0xB2, gov_sys_event +0x108,
  gov_npc +0x134, gov_scene +0x184, gov_init +0x1A4.
- Blob disassembled with capstone and eyeballed entry by entry
  (branch targets, stack balance, register saves) — all correct.
  The full disassembly is in the build output (not reproduced here).
- Checksums: `verify-all` exit 0 — header $47E8, runtime $34DEADF6.
- IPS: 709 bytes, 48 records; round-trip verified
  (base + IPS == ROM exactly).
- Independent diff audit (separate script, after the build):
  461 bytes differ base→D, 48 runs, ALL inside the six hook sites +
  the blob + the two checksums; NONE outside. C blob region
  $FD400–$FE6C5 byte-identical to `patches/c-sprites/source.bin`;
  past the blob end is 0xFF to the end of the ROM.
- Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`,
  re-verified). Base C ROM untouched. Nothing landed on main.

Deliverables:
- `rop-big-rework-full-d.rom` — MD5 `208371be216d3182303c3af64cbc9eab`
- `patches/d-governor/` — source.s, build.py, README.md,
  changed-bytes.txt, rings-of-power-big-rework-full-d.ips, source.bin,
  source.lst

## 2. Pace / lag-closure arithmetic (what the governor changes)

C's measured mismatch: Buc 1 cell / ~8 fr vs scroll 1 cell / ~14 fr
→ the sprite TARGET updated faster than the scroll could follow and
the sprite trailed by up to ~2 cells mid-walk. Under the governor:
- Leader step rate: 1 cell / 4 ticks ≈ 20–24 fr/cell (tick ≈ 5–6 fr,
  quantised by the ~3 fr loop iteration) ≈ original ~22 fr/cell.
- Scroll: 1 cell / ~14–15 fr — FASTER than the step rate, so it
  catches up before the next step and the B2 gate stays seamless.
- Sprite slide: ~7 fr/cell — the sprite reaches its TARGET well
  before the next step (~20–24 fr later).
- Re-install hitch (~16 fr) sits inside one iteration and does not
  multiply: per cell ≈ 3 normal ticks + 1 re-install iteration ≈
  25–30 fr, in the same ballpark as the original 22 fr/cell.
So the trailing lag should close: the scroll and the sprite both run
faster than the step rate. **This is arithmetic, not a measurement —
no live probe was run (test-ROM rule). The lag-closure claim is
verified by Dayset's playtest, not by me.** If he still sees the
sprite trailing, the numbers above are the first thing to re-check
(the tick quantisation is the softest part: the ~3 fr loop iteration
makes the governor tick 5–6 fr, not exactly 5).

Walk pace: built at the ORIGINAL pace by default (GOV_K=5,
GOV_NPCDIV=4 in RAM). The walk-pace decision (original pace vs a
touch faster) is Dayset's — a one-word change to GOV_K later.

Cutscene cadence: script steps every 16th governor-tick ≈ 80–96 fr
≈ original ~88 fr. Close, but the cutscene feel is his call.

## 3. Chunk loading (what was built, what was not)

Built: the one concrete gap found by code reading — sprite slots are
dropped on scene setup (H6 clears the sprite magic, so `sprite_init`
re-runs and the figures pop in freshly decoded instead of showing a
stale pattern/TARGET for up to ~3 ticks after a door). Everything
else is unchanged by design (DESIGN §7.2): the data-chunk load
(`map_chunk_cache_read` + 4-slot cache) needs no image-layer event;
doors are the chunk-edge-with-transition; B2's Scheme B (full
re-install per cell step) is the documented fallback and is already
built. Install camera / scroll across a transition are already
handled (C VBlank location-change reset + scene_entry).

Not built (not needed): pre-loading the adjacent data chunk, a new
streamer, any change to the B2 gate or the C sprites.

## 4. What Dayset should test (for the parent / delivery)

- Walk Buc around the Academy and the overworld: is the sprite
  trailing lag gone? Is the walk pace right (original pace by
  default — tell him the pace knob is his call)?
- Walk through a door / across a chunk edge: do the figures pop in
  cleanly (no stale figure at a wrong spot for a few ticks)?
- Cutscene: does the Buc scene still play at about the original
  cadence, and does the loop walk still work?
- Menu / teleport / other rooms: anything broken by the governor
  gating world_tick and combat_turn_run?
- The known C limitations still stand (feet pool: a 4th simultaneous
  5-row figure shows 4 rows until its next decode; round-robin
  staleness for non-leader figures with 12 figures).
