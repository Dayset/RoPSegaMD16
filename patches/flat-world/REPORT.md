# Flat overworld plane — REPORT (short)

Worktree `~/workspace/rop-work/flat-world/`, main `78028bf`. One fix only, on
the ORIGINAL ROM. No branch/PR/merge/push. Dayset is the tester; my live
verification was stopped on his call (2026-11-12 ~18:09 EST).

## Deliverable

- ROM: `~/workspace/rop-work/flat-world/rop-flat-world.rom`
- **MD5 `c362a4595cb550dcb7047357b85e3fd9`**, header checksum `0x013C`,
  runtime checksum `0xD0F760DB`.
- Patch: `patches/flat-world/` — `source.s`, `gen_flatworld.py`,
  `build.py`, `README.md`, `changed-bytes.txt`, `flat-world.ips` (11,471 B;
  round-trip verified: original + IPS == fixed ROM exactly).
- Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Design

`$E358` dispatch hook. The three `map_chunk_pos` (`$01BA4E`) call sites
(face `$01BC1A`, hidden `$01BC3C`, top `$01BC84`) go through a call-site stub
that sets the flat byte in RAM `$FF00B0` from the cell terrain type (props
word at `-$6(a6)`, bits 10–15), then tail-calls `$E358`. `$E358` computes
the buffer position and advances the stream as the original; the dispatch
hook (`$E40C` / `$E470`) swaps in a mechanically generated flat handler
(stream read → `addq.l #1,a0`; path-B nibble-swap omitted). 112 handlers,
blob 10,990 bytes at `$FD0CC`–`$FFBC2`.

The hook fires only for `map_chunk_pos` terrain calls, mode `$FF00AE` == 1,
and grid base `$FFA7FC` == `$FFB08C` (overworld slot). Land flat byte `0x33`
(palette idx 3, green `(0,144,0)` in palette `$CCB18`); water flat byte
`0x11` (palette idx 1, dark blue `(0,0,180)`); water = terrain types
`{0,2,3,10,11,15,21,22,23}`. The room (mode 2) never satisfies the gate.

Colour history: first build used land nibble 4 — it rendered BLUE
(`$CCB18` idx 4 = light blue). Green is idx 3, so land is now `0x33`.
Change `LAND_K` / `WATER_K` in `gen_flatworld.py` to retune.

## What was checked

- Build: checksums verify, IPS round-trips, blob fits the padding.
- One diagnostic probe screenshot of this final ROM (reached the overworld
  via the Buc cutscene): the City of Division renders as one flat green
  plane with two dark-blue water patches; Thalmus (the party leader) is
  visible in the centre; no texture, no dashes. The room was pixel-identical
  to the original on an earlier build of this same design (352/1,310,720 px
  differ, all character-animation timing).

## What was NOT verified (Dayset is the tester)

- **Cadence not measured.** No frames/tick number for the overworld,
  original vs flat. (The room flat-zoom measured 21.5 → ~9.8 frames/tick,
  2.4×, but that is the room, not this overworld ROM.)
- **Look not live-verified.** No full playtest of this ROM: the overworld
  in real play, the world view outside the City of Division, the room, the
  menu, and teleport were **not** re-checked on the final ROM.
- **Buildings/trees flatten with the ground.** They are terrain tiles, so
  the town becomes a flat green plane; its buildings/trees are not
  separately preserved. Figures stay visible. This is by design, but it is
  the thing most likely to surprise on sight.
- The cadence probe crashed the game (`machine freeze`, write to `$DFFFFE`)
  and was abandoned when testing was stopped; do not reuse it as-is.
