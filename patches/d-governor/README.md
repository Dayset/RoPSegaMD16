# Phase D — tick governor + chunk loading

Base: `rop-big-rework-full-c.rom` (MD5 `385fa655a5a060ac6b66de8b9de795dd`).
Output: `rop-big-rework-full-d.rom`, MD5 `208371be216d3182303c3af64cbc9eab`
(header checksum $47E8, runtime checksum $34DEADF6 — both verified by
`tools/checksum.py verify-all`).

Build: `python3 patches/d-governor/build.py` (assembles `source.s` with
the in-worktree vasm, patches the six hook sites, fixes checksums,
writes the IPS + `changed-bytes.txt`, verifies the round-trip).

## What it does

### (1) Tick governor — the pace fix

The world tick now runs once per GOV_K VBlanks (default 5, 12 Hz),
counted off the frame counter `$FF0010` (which increments once per
VBlank at $127A — no VBlank hook needed). The leader's cell commits
once per 4 ticks (phase gate, turn check first), so 1 cell / 4 ticks
≈ 20–24 fr/cell ≈ original ~22 fr/cell. NPCs and event scripts run
once per GOV_NPCDIV phase-0 ticks (default 4, i.e. every 16th
governor-tick ≈ 80–96 fr ≈ original ~88 fr).

Six hook sites (all 6-byte replacements, base bytes asserted first):

| Site | Was | Now |
| --- | --- | --- |
| $00D2E0 (main loop) | `jsr world_tick` | `jsr gov_world_tick` |
| $00D97E (main loop) | `jsr combat_turn_run` | `jsr gov_combat_turn` |
| $0228CC (Path A) | `cmpi.w #$4,-$E(a6)` | `jsr gov_path_a` |
| $022778 (combat_turn_run) | `jsr sys_event_run` | `jsr gov_sys_event` |
| $022B54 (NPC loop) | `bne.b $022B64` + `move.w -$E(a6),-(a7)` | `jmp gov_npc` |
| $12C20 (world_map_draw) | `jsr $FE656` (C scene_entry) | `jsr gov_scene` |

Blob: 472 bytes at $FE6C6–$FE89D (free 0xFF padding; C blob
$FD400–$FE6C5 untouched). State: $FFD300–$FFD31F (GOV_MAGIC $9C07,
GOV_K=5, GOV_NPCDIV=4, GOV_NPC, GOV_LAST, GOV_RUN).

Why this should close C's trailing lag: Buc was walking 1 cell / ~8 fr
while the scroll moves 1 cell / ~14 fr, so the sprite TARGET updated
faster than the scroll could follow and the sprite trailed by up to
~2 cells mid-walk. Under the governor Buc steps 1 cell / ~20–24 fr —
slower than the scroll (1 cell / ~14–15 fr) and slower than the sprite
slide (~7 fr/cell) — so the scroll catches up before the next step
(the B2 gate stays seamless) and the sprite reaches its TARGET well
before the next step. The re-install hitch (~16 fr) sits inside one
iteration and does not multiply: per cell ≈ 3 normal ticks + 1
re-install iteration ≈ 25–30 fr, in the same ballpark as the original
22 fr/cell. **This is arithmetic, not a measurement** — the lag-closure
claim is verified by Dayset's playtest, not by a probe (no live
testing by the builder, per the test-ROM rule).

Walk pace: built at the ORIGINAL pace by default. GOV_K and
GOV_NPCDIV live in RAM, so the walk-pace decision (Dayset's — original
pace vs a touch faster) is a one-word change later.

### (2) Chunk loading

The data-chunk load is unchanged (DESIGN §7.2): `map_chunk_cache_read`
+ 4-slot cache + `$DD5C`, ~1.2 fr on a miss; location doors are the
chunk-edge-with-transition (`world_location_transition`). Pre-loading
the adjacent data chunk is not needed. B2's Scheme B (full re-install
per cell step) is the documented fallback and is already built.

The one concrete gap found by code reading is fixed here: sprite
slots were NOT invalidated on a location change. A stale slot whose
recIdx coincides with a new room's figure kept its old pattern and
TARGET until round-robin re-decoded it (up to ~3 ticks of a
wrong-pattern figure at a wrong position after every door). `gov_scene`
(H6) clears the sprite magic on scene setup, so `sprite_init` drops
all slots and the figures pop in freshly decoded. (C's scene_entry
never returns — it jmps into `world_map_draw` — so `gov_scene`
tail-calls it with `jmp $FE656` after clearing the magic.)

## Verification (build checks only)

- Base MD5 asserted; C blob ($FD400–$FE6C5) byte-identical to
  `patches/c-sprites/source.bin`; all six C hooks asserted unchanged.
- Blob disassembled with capstone and eyeballed entry by entry
  (branch targets, stack balance, register saves).
- Checksums: `verify-all` exit 0 (header $47E8, runtime $34DEADF6).
- IPS round-trip exact (709 bytes, 48 records; base + IPS == ROM).
- Independent diff audit: 461 bytes differ base→D, all inside the six
  hook sites + the blob + the two checksums; nothing else.
- Original ROM untouched (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`,
  re-verified). Nothing landed on main.

## Not verified (Dayset is the tester)

- Whether the sprite trailing lag is gone in play (the arithmetic
  says it should be; the feel is his call).
- The walk pace at 1 cell / ~20–24 fr (original pace by default;
  the pace knob is his decision).
- Cutscene cadence (script steps every 16th tick ≈ 80–96 fr — close
  to the original ~88 fr, but the cutscene feel is his call).
- Chunk-boundary behaviour (doors, overworld chunk edges, sprite
  pop-in after a door).
- Menu/teleport/other rooms.
