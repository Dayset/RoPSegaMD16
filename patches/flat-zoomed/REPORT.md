# flat-zoomed: re-gate the flat ground plane to the ZOOMED view only

Date: 2026-11-12. Worktree `~/workspace/rop-work/flat-zoomed/` (at main
78028bf, detached HEAD). Original ROM untouched (MD5 re-verified at
every build).

## Deliverable

- **ROM:** `~/workspace/rop-work/flat-zoomed/rop-flat-zoomed.rom`,
  MD5 **`4ee66e521ac9a636d2167c0d55409d92`** (header 0x686D, runtime
  0x9EBD3873). Base: the ORIGINAL ROM (MD5
  30c18fdbe2183f64702ae9f1a45d63f9) + the flat patch, re-gated.
- **Patch:** `patches/flat-zoomed/` (source.s, build.py, README.md,
  changed-bytes.txt — 519 bytes differ, flat-zoomed.ips 677 B,
  round-trip verified: original + IPS == ROM).
- Dayset is the tester (per his 2026-11-12 test-ROM rule); minimal build
  checks only, no extensive live verification by the lead.

## Headline: $FF0E98 is NOT the discriminator — the mode is

The brief hypothesised the zoomed view is (mode 1 + overworld grid
`$FFB08C` + `$FF0E98==$FFFF`), and the corrected gate should add the
`$FF0E98==$FFFF` check. **Two probe runs refute that.**

- `$FF0E98` is **always `$FFFF` in the overworld** (mode 1, grid
  `$FFB08C`) — in every mode-1 observation across both probe runs,
  including after walking and after exiting a room back to the
  overworld. It is a location number only in a room (mode 2:
  `$FF0E98` = 30, 156, ...). The post-cutscene mode-0 transition
  sets it to `$FFFF` and it stays there for the whole overworld.
- So a gate of (mode 1 + grid `$FFB08C` + `$FF0E98==$FFFF`) is
  **identical** to the flat-ground-plane gate (mode 1 + grid
  `$FFB08C`): it would still flatten the big world and change
  nothing. Building it as briefed would have delivered a ROM
  behaviourally identical to the one Dayset already rejected.
- **B in the overworld ENTERS a room** (confirmed in both runs): mode
  flips 1 -> 2, grid `$FFB08C` -> `$FFB09C`, `$FF0E98` `$FFFF` ->
  `$001E` (location 30). Walking Right out of the room flips it back
  (mode 1, `$FF0E98` `$FFFF`). B = ENTER / "zoom in on the current
  location" — **the zoomed view IS the room (mode 2)**.
- The real discriminator is the **mode**: mode 1 = big world
  (textured), mode 2 = zoomed view / room (flat). This ROM gates on
  `$FF00AE==2` only (mode 2 implies a room grid:
  `$FFB09C`/`$FFB0AC`/`$FFB0BC`).

This also explains the flat-world contradiction: the dispatch-hook
flat gated on mode 1 + grid `$FFB08C`, so it flattened the world and
left the zoomed view (the room, mode 2) unchanged — exactly what
Dayset reported ("World Zoomed is unchanged - default, but world is
flat no textures").

## Probe infrastructure

`.scratch-zoomed-gate/` — `zoom_probe.s` / `zoom_probe2.s` (vasm mot
syntax, blob at `$FFBC8`), `build_zoom_probe*.py` /
`build_zoom_probe*_rz.py` (the `_rz` variants build on the re-gated
ROM), `run_zoom_probe.py` (pty debugger driver; loads
`~/workspace/user/files/slot_0_1_ou3l.state`; clicks vsync OK at
(510,315); reads the RAM log via pipelined p/x reads).

Hooks: `$1272` VBlank (jmp `$127A` exit, re-executes `move.w #0,
$FF0016` first) + `map_chunk_pos` `$01BA4E` entry (JMP pattern, render
counter). Log: every 20 frames, one 16-byte record at `$FFD800` (max
180 records, count in `$FFD7F0`; ends `$FFE340`, below `$FFE800`):
frame, phase, mode `$FF00AE`, grid LOW `$FFA7FE`, `$FF0E98`, `$FF0E92`,
`$FF00AC`, renders. State words `$FFD7E0`–`$FFD7F0` (phase,
phase_frame, ow_stable, trig, renders, zoomed_seen, result, pad_hold,
logcount).

Pad injection (proven pattern, from cutskip probe_v2.s): write the pad
byte to `$FF0018` AND `$FF002C` every VBlank + force the joypad ring
empty (`move.b $FF001B,$FF001A`) so `joypad_queue_pop` returns `$FF002C`
unchanged. Pad byte: A bit 6 ($40), B bit 4 ($10), C bit 5 ($20), START
bit 7 ($80); D-pad low nibble (Down $02, Right $08).

Button/verb decoding (read from rop.s): `menu_verb_input` `$012FE8`
-> `$01333A` B handling: B tap (press+release, no direction, mode
`$FF00AE`==1) -> verb `$1E` (30) on RELEASE; B+direction -> verb `$1E`
(mode 1) / `$23` (35, mode 2) on press; if a menu is open
(`$FF00AC`!=0) B -> verb `$15` (21). START (bit 7) at `$013542`:
newly pressed -> verb `$14` (20) -> `$00D4F2` -> `menu_set_mode(1)`;
B+START -> verb `$19` (25) -> `$00D59C` -> `cmd25_handler` `$020A36`
-> `cmd24_handler` + `verb_exec`. Command switch `$00D740`: 30 ->
`$00D612` (B), 25 -> `$00D59C` (map/cmd25). Verb `$1E` handler
`$00D612` pushes the verb's direction arg + party leader ->
`sys_struct52_flag_test` `$0265BE`. In `sys_struct52_flag_test`:
`$026800` branch (direction==4, location d6!=0, d7==0/2) ->
`world_location_transition(1, loc, -1)` — ENTER a location; `$026876`
branch -> `$02692A` `world_location_transition(1, d6, d5)` ->
`npc_location_greet` -> `npc_show_greeting` `$026A8C` -> mode-0
transition `$026ADA` (`world_location_transition(0,0,$FFFF)`) ONLY if
mode != 1 AND combat flag bit 0 == 0. **world_map_draw `$012C20` has
3 callers, ALL intro/title (`$015008` intro_story_driver, `$01552C`
new-game flow, `$0195C4` scene code) — it is NOT the in-game map
screen.** The in-game map (verb `$19`) goes through
`cmd25_handler`/`verb_exec`, not `world_map_draw`.

## Probe runs on the ORIGINAL ROM (the discriminator test)

### Run 1 — zoom_probe_orig.rom, MD5 d9382907539a34c65b1801ddc1326181

LOG_FULL after 51.1 s, 148 records, phase 11, renders 141,
zoomed_seen=1. Drive: P0 trigger Buc script -> P1 auto-advance, wait
overworld stable 120f -> P2 B tap (press 40f, release 40f) -> P3
observe 240f -> P4 B+START (press 60f, release 60f) -> P5 observe 240f
-> P6 B tap -> P7 observe 600f.

- Phase 1 (frames 2460–4040): the Buc room (mode 2, grid `$B0AC`,
  `$FF0E98`=$009C/156, `$FF0E92`=$301E, renders 0→75); frame 3940 mode
  flips to 1, grid `$B08C`, **`$FF0E98`=$FFFF, `$FF0E92`=$33FF** (the
  op-10 mode-0 transition, mid-scene). Phase 1 frames 3940–4040 =
  mode 1, `$FF0E98`=$FFFF (9 records, renders 76→80, cadence 26.67 —
  cutscene-tail cadence, not steady-state).
- **Phase 2 B tap: at frame 4120 the mode flipped to 2, grid `$B09C`,
  `$FF0E98`=$001E (30), `$FF0E92` unchanged $33FF — B in the overworld
  ENTERS a room (location 30), it does NOT toggle a zoom.**
- Phases 3–7 stayed in that room (mode 2, grid `$B09C`,
  `$FF0E98`=30). B+START in the room (phase 4) set `$FF00AC`=1 at
  frame 4380 (a menu opened) and renders stalled at 102 during phase 5
  (frames 4500–4720), resuming slowly in phase 7 (109→140 over 600f,
  ~19f/render). Last record: frame 5400, phase 7, mode 2,
  `$FF0E98`=30, `$FF00AC`=1, renders 140.
- Room cadence (phase 7, menu open): **18.71 f/render** (30 records,
  frames 4820–5400, renders 109→140).

### Run 2 — zoom_probe2_orig.rom, MD5 1f59419d21c0416700504d6fe88ce615

LOG_FULL after 54.8 s, 159 records, phase 11, renders 151,
zoomed_seen=1. Drive changed: P2 B+START FIRST (no B tap before it)
-> P3 observe -> P4 B tap -> P5 observe -> P6 WALK Right (hold $08,
600f) -> P7 observe 300f.

- Phase 1 same as run 1 (80 records, frames 2460–4040, room then
  mode 1/`$FF0E98`=$FFFF).
- **Phase 2 B+START in the overworld: NO change — stayed mode 1, grid
  `$B08C`, `$FF0E98`=$FFFF, `$FF00AC`=0 (renders 80→85). B+START did
  NOT open a map screen or a menu in the overworld.** (`$FF00AC` is 0
  in ALL 159 records of run 2 — no menu ever opened.)
- Phase 3 observe: still mode 1, `$FF0E98`=$FFFF (renders 85→95).
- **Phase 4 B tap: again entered the room (mode 2, grid `$B09C`,
  `$FF0E98`=30).**
- Phase 5 observe: stayed in the room.
- **Phase 6 walk Right: the leader exited the room back to the
  overworld (mode 1, grid `$B08C`, `$FF0E98`=$FFFF) at frame 4800
  (phase 6 states include both mode 2/`$FF0E98`=30 and mode
  1/`$FF0E98`=$FFFF).**
- Phase 7 observe: ended in the overworld (mode 1, `$FF0E98`=$FFFF,
  renders 139→150).
- Zoomed (mode 1, grid `$B08C`, `$FF0E98`=$FFFF) records: 69, frames
  span 1680, renders span 74, cadence **22.70** — essentially identical
  to the measure probe's 22.5 overworld cadence. The `$FF0E98`=$FFFF
  view renders through `map_chunk_pos` at the SAME cadence as the
  overworld — it IS the overworld, not a distinct zoomed view.
- `$FF0E92` ended at 12324 ($3024) vs $33FF after the cutscene — it
  changed during the walk (location/depth word updated as the leader
  moved).
- Room cadence (phase 5, no menu): **15.71 f/render** (12 records,
  frames 4500–4720, renders 99→113).
- Clean mode-1 (overworld) windows: phase 2: 20.0 f/render; phase 3:
  22.0 f/render; phase 7: 25.45 f/render.

## The re-gated ROM

Design: the flat-ground-plane mechanism (3x2 block fill, skip the
decoder's face/hidden calls, figure height-offset zeroed; land 0x33
green, water 0x11 dark blue; blob 496 bytes at `$FD400`), re-gated
from (mode 1 + grid `$FFB08C`) to **`$FF00AE`==2 only**. 11 patch
sites (same as flat-ground-plane: `$01BC1A` face, `$01BC3C` hidden,
`$01BC84` top, 8 figure sites). The gate check is a single `cmpi.w
#2,$FF00AE` — no data register needed (the old grid compare used d6/d0;
`cmpi.l #imm,An` is not valid 68000, which is why the old gate needed
a Dn). When not gated, every stub tail-calls the original `$E358` /
routine. Debug counters kept: `$FFD7F6` gated calls, `$FFD7F8` bounds
skips, `$FFD7FA` fills. Build: `python3 build.py` in
`patches/flat-zoomed/` (vasm, MD5-asserted original base, both
checksums fixed, IPS round-trip verified).

## Probe runs on the RE-GATED ROM (the verification)

### Probe 1 on the re-gated base — zoom_probe_rz.rom, MD5 c77c14f7cedd99257b3a08a413925fac

LOG_FULL after 39.8 s, 111 records, phase 11, renders 201,
zoomed_seen=1. Flat debug: gated calls **19,410**, bounds skips **0**,
fills **19,409**.

- Phase 1 (frames 2460–3300): the cutscene room is now flat, so the
  script races through faster — mode flips to 1 at ~frame 3300 (vs
  3940 on the original); 43 records vs 80.
- Phase 2 B tap enters the room (mode 2, `$FF0E98`=30) as before.
- **Phase 7 room cadence (menu open): 9.35 f/render** (30 records,
  frames 4080–4660, renders 137→199) vs **18.71 on the original —
  2.00x faster.**
- Phase 1 mode-1 (overworld) cadence: 26.67, identical to the original
  (9 records) — the overworld is not flattened.
- Screenshot `zoom_probe_rz_zoom.png`: the room is a **flat green
  plane** with the figure standing on it; the menu panel and message
  bar are intact; the barrels (terrain) are gone. The original
  `zoom_probe_orig_zoom.png` shows the same room fully textured (grey
  stone + brown wood + detailed barrels). Room pixels differ: 115,387
  of 1,310,720 (8.8% — the room area).

### Probe 2 on the re-gated base — zoom_probe2_rz.rom, MD5 a17b4feddafba98c7c9413ca7e6d740b

LOG_FULL after 42.9 s, 122 records, phase 11, renders 168,
zoomed_seen=1. Flat debug: gated calls **11,085**, bounds skips **0**,
fills **11,085**.

- **Phase 5 room cadence (no menu): 7.86 f/render** (12 records,
  frames 3760–3980, renders 100→128) vs **15.71 on the original —
  2.00x faster.**
- Clean mode-1 (overworld) windows: phase 2: **20.0**; phase 3:
  **22.0**; phase 7: **25.45** — **identical to the original ROM on
  all three**. The overworld render rate is unchanged.
- (Caution: the driver's aggregate "zoomed records cadence" on the
  re-gated run is 18.46 vs 22.70 on the original — that is a CONFOUND,
  not an overworld speedup. The renders span across the interleaved
  mode-2 intervals includes the faster room renders; the clean
  contiguous mode-1 windows above are the valid comparison.)
- Screenshot `zoom_probe2_rz_zoom.png`: the overworld (City of
  Division) is **fully textured** — buildings with brown roofs, green
  trees, grey stone paths, blue fountain, the figure visible,
  "SOMEONE'S HOME." Pixel comparison vs the original
  `zoom_probe2_orig_zoom.png`: 2,584 of 1,310,720 pixels differ
  (0.20% — animated tiles / figure position only, not a flat).

## Speed before/after (zoomed view = room, location 30)

| condition | original ROM | this ROM | speedup |
|---|---|---|---|
| room, no menu | 15.71 f/render | 7.86 f/render | 2.00x |
| room, menu open | 18.71 f/render | 9.35 f/render | 2.00x |
| big world (overworld) | 20.0 / 22.0 / 25.45 f/render | 20.0 / 22.0 / 25.45 f/render | 1.00x (unchanged) |

(The overworld flat was 2.67x; the room flat is 2.00x — the room's
fixed costs (tick logic + DMA + clear + the fill itself) are a larger
share of a shorter render. The remaining ~8–9 frames are that floor.)

## Known defects (same as the flat-ground-plane family)

- Small black gap at the diamond's bottom edge (a few tiles;
  scatter-only edge tiles the fill does not reach; interior solid).
- In the room, the furniture flattens with the ground (barrels are
  terrain tiles — gone on the flat room; the figure, an entity, stays
  detailed and visible).
- The cutscene room (Buc classroom, mode 2) is also flat — the gate is
  mode 2, which covers every interior, not just the B-entered room.
- Blue water patches spread ~1–2 tiles past water cells at land/water
  borders (from the flat-ground-plane report; not re-tested here — no
  water cells in location 30).

## NOT verified

- Cadence / look in real play outside the probe (the probe drives the
  Buc save state, B into location 30, and a short walk).
- **The B+START map screen:** in the overworld probe it produced no
  visible state change (no mode/grid/`$FF00AC` change, renders
  continued) — the map screen itself was not cleanly observed, so
  whether B on the map screen is a different zoom path is still open.
  What IS established is that B (in the overworld) enters the room,
  and that is the zoomed view this ROM flattens.
- Menu / teleport on this ROM (code-gated only, not live-verified).
- The room's water (no water cells in location 30) and multi-level
  rooms.
- The `sys_struct52_flag_test` `$026876` branch (mode-0 transition
  back to the overworld) was not traced end-to-end in this task; the
  room-exit was observed live (walk Right, mode flips back).

## Note for the parent (subcell-agent conflict)

The subcell agent (spawned 2026-11-12 ~20:05 EST) is building subcell
movement on top of the flat ground plane ROM (MD5
992465cc0a8dd958febcadf3eede430e), which flattens the big world — the
view Dayset corrected at ~20:06 EST ("world = big world shouldn't be
flat"). This ROM (`rop-flat-zoomed.rom`) is the corrected base: flat
only on the zoomed view (room, mode 2), big world textured. If subcell
is to go on top of the flat, its base should be THIS ROM (or the
re-gate should be applied to the subcell build), not the flat ground
plane ROM. That redirect is the parent's call — not made here.

## Files

- `~/workspace/rop-work/flat-zoomed/rop-flat-zoomed.rom` (MD5
  4ee66e521ac9a636d2167c0d55409d92)
- `~/workspace/rop-work/flat-zoomed/patches/flat-zoomed/` (source.s,
  build.py, README.md, changed-bytes.txt, flat-zoomed.ips)
- `~/workspace/rop-work/flat-zoomed/.scratch-zoomed-gate/`:
  `zoom_probe.s`, `zoom_probe2.s`, `build_zoom_probe*.py`,
  `build_zoom_probe*_rz.py`, `run_zoom_probe.py`,
  `zoom_probe_orig.rom` / `zoom_probe2_orig.rom` (probe ROMs on the
  original), `zoom_probe_rz.rom` / `zoom_probe2_rz.rom` (probe ROMs on
  the re-gated base), `zoom_probe_orig_zoom.json` /
  `zoom_probe2_orig_zoom.json` / `zoom_probe_rz_zoom.json` /
  `zoom_probe2_rz_zoom.json` (per-record logs), `*_zoom.png`
  (screenshots), `*_run_stdout.log` / `*_run.log` (driver transcripts).
