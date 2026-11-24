# Rendering patches — index

Every rendering patch source landed by #238 (Smooth v2 · 1), plus the
big-rework chain. Each `patches/<name>/` holds the patch source
(`source.s`, `build.py`, `changed-bytes.txt`, `.ips`, `README.md`),
the build report (`REPORT.md`, copied from the original worktree's
`.scratch-<name>/REPORT.md`), and `BASE` (one line: the base patch
name, or `original`).

The original ROM is NEVER edited or committed: `Rings of Power (USA,
Europe).gen`, 1,048,576 B, MD5 `30c18fdbe2183f64702ae9f1a45d63f9`. Each
build reads it (as `rop-original.gen` at the repo root — user-supplied,
git-ignored) and writes the patched ROM to `build/` (also git-ignored).

Verdicts in §1 are copied from issue #234 ("Current rendering state
(2026-11-12)"), which is the snapshot the landing was taken from.
States: **approved** · **current-best** · **parked** · **rejected** ·
**intermediate** (an in-chain link, superseded by its successor
without a Dayset rejection) · **awaiting-test** · **superseded**.

## 1. The #234 chain (flat line, in build order)

| Patch | Base | MD5 of the ROM it builds | Dayset's playtest verdict (#234 wording) | State |
|---|---|---|---|---|
| flat-zoom | original | `d9139010ac84119d6dc0feba5086b8a5` | Speed met (~21.5 -> ~9.80 f/tick, 2.4x) but look NOT clean (dark blue dashes, Thalmus invisible); flattened the ROOM, not the overworld he meant. Speed-test artifact only. | rejected |
| flat-world | original | `c362a4595cb550dcb7047357b85e3fd9` | Flattened the normal world view, "World Zoomed" unchanged, NO speed benefit, "feels laggy as default one". | rejected |
| flat-ground-plane | original | `992465cc0a8dd958febcadf3eede430e` | Overworld 22.5 -> 8.44 f/render (2.67x). "thats very fast but no subcell movement and flat plane is applied to the world" -> correction: "No - world = big world shouldn't be flat". | rejected |
| flat-zoomed | original | `4ee66e521ac9a636d2167c0d55409d92` | **APPROVED** — "this one is done right, zoomed world is fast no textures". Zoomed view (room) 15.71 -> 7.86 f/render (2.00x); menu open 18.71 -> 9.35. Big world unchanged. | approved |
| flat-zoomed-feet | flat-zoomed | `9373c0d01cf08c20f28e256daa9ea142` | **APPROVED** — "wow great, cutscene was superb, very fast, legs are present." Defers figure draws to a post-pass (`fig_replay`) so the flat fill no longer overwrites the figure's feet. | approved |
| subcell | flat-zoomed-feet | `fa3255df47fe90efc6cb1c36c2e495db` | "Can't see subcell movement here" (21:31 EST) — hooks only in `hero_track`, never fired for Buc (he is drawn via `map_promote_record`). | intermediate |
| dither | subcell | `09d74baa339314b40e02344545f67f66` | **APPROVED** — "It's not that ugly as before, no textures at all in the checkerboard pattern, still very fast 100% as without the checkerboard." | approved |
| pacing | dither | `6abeec0bea66365f223c75760983df8b` | Stand 4 ticks, cape moving, feet dead, then teleport 1 cell (21:57 EST); ~half speed held, cutscene "fast as rocket" (21:59 EST). Cell commits once per 4 ticks. | intermediate |
| interp | pacing | `309d87c5a97cdbc5c2066f11a2f98399` | "Even slower, no subcell movement" (22:28 EST); "barely able to navigate through the academy, cutscene went okay fast" — camera cancellation (slide is room-relative, camera tracks the committed cell). | intermediate |
| interp-fix | interp | `44353892c7a006300bfae2535ad6eaf8` | "Legs not moving at all in zoom view, walking speed like default or slightly worse, BUC can run behind the screen, sometimes zigzag. Cutscene fast normal walking" (23:12 EST) — camera delay fundamentally flawed for the room. | intermediate |
| interp-fix2 | interp-fix | `30233662e411ecf0046ffc43c734c971` | "Walking smoother with subcell wow" (23:33 EST) — **WORKS**. Then: "camera yoinks on direction change, 3-4 short presses to rotate face after stop. If you hold direction he will walk beautifully" (23:34 EST). | intermediate |
| cutscene-loop | flat-zoomed-feet | `79bccdcd927707802332f64f38faa641` | "He walks a bit more, at least ive seen other directions, still jumpy on world shift" (22:56 EST) — loop works, world shift jumpy (integer-cell camera). Separate line from the interp chain. | intermediate |
| walk-frames | cutscene-loop | `a698a2f697939fd8a5b11b94837f32f7` | "Cutscene BUC slower than before, smooth but after 2 steps standing still longer, additional Y values did worse" (23:29 EST) — Y-shift hook never fired (hero_track only); slowness from 8-tick doubling. | intermediate |
| walk-frames-fix | walk-frames | `9ba279759436b96a732d11d9a3f6be0d` | "Walks even better than previous, no yoinks, movement begins with 1-2 press (rarely from 2nd) but cutscene Y completely off. 2 steps then waiting longer than usual and jumps screen, repeat" (23:38 EST) — zoom walk very good, cutscene Y off. | intermediate |
| walk-unused-frames | walk-frames-fix | `6764e6ee86976e1a3607388f4cb5faa3` | **CURRENT BEST** — "BUC walks very good here, no stalls on direction, no funky camera, cutscene is smooth but nothing extra on top" (23:50 EST). | current-best |
| noise | dither | `b35a634181a99271af6e9c829beb7339` | Delivered, awaiting Dayset's test. See tall-objects shading issue. | awaiting-test |
| tall-objects | noise | `9846c168f559bb8acf4a14aca46623b7` | "no tall objects observed" (00:04 EST) — tall top blends with the land. See tall-objects shading issue. | rejected |
| tall-objects-diag | tall-objects | `9ea6aa19c407bca7d8f5df4d2e480827` | Delivered, awaiting Dayset's test. See tall-objects shading issue.¹ | approved¹ |
| interp-fix3 | interp-fix2 | `8ada8b985aad8ae6c3929ae6d39d4139` | "Subcell even more beautiful but turns wonky, zigzag worst, cutscene jumps forward; previous cutscene better (smooth normal)" (23:54 EST) — **PARKED**. | parked |

¹ #234 lists tall-objects-diag as awaiting-test, but Dayset later
playtested it GOOD (2026-11-13 ~07:25 EST: "rop-tall-objects-diag.rom
- is working good, i can see outlines at least"). State reflects the
later verdict; the verdict column keeps #234's wording.

**Current best of this line:** `walk-unused-frames`
(`6764e6ee86976e1a3607388f4cb5faa3`) — very good walk, no stalls on
direction, no funky camera, cutscene smooth. The world shift is still
jumpy (integer-cell camera) — that is the big rework, not this ROM.

## 2. The big-rework chain (separate line, on the original ROM)

Decode-once into Plane B + hardware scroll + figures as sprites +
tick governor. Base of the chain is the original ROM, not the flat
line. Verdicts per #238 (no #234 table covers this line).

| Patch | Base | MD5 of the ROM it builds | Verdict | State |
|---|---|---|---|---|
| big-rework | original | `64b742edf92cf8b3b2227b8654d550e9` | Partial — the whole-screen scroll IS smooth and game logic/dialogues work, but the room image is small and stuck in the left corner and no actors are visible (Dayset 2026-11-13 ~08:56 EST). | intermediate |
| big-rework-poc-fix2 | big-rework² | `d4fc661f333ca2425987d2407693bce9` | Navigable — the scene can be navigated inside the Academy, but the patch on the left is still present, jumps are big, and there is no smooth Buc movement (Dayset 2026-11-13 ~09:27 EST). | intermediate |
| b1-vram | big-rework-poc-fix2 | `49530033f2f191d938e9f0ec3f86e845` | Intermediate — VRAM layout migration (Plane B at $E000, rec 6 evicted, sprite-pattern cache reserved); the 40×28 image did not fit the ROM tables, fallback 36×23. Not delivered to Dayset. | intermediate |
| b2-strip | b1-vram | `ec7bcffe9c45fd851a6752dec5bcf788` | Intermediate — literal strip streaming sim-proven unbuildable; fallback Scheme B (camera-driven scroll, catch-up within ~15 frames) fixes fix2's cutscene jumps and the patch on the left. Not delivered to Dayset. | intermediate |
| c-sprites | b2-strip | `385fa655a5a060ac6b66de8b9de795dd` | Intermediate — figures as sprites (terrain-only decode + per-frame sprite slide). Verified, never playtested: Dayset chose to wait for D. | intermediate |
| d-governor | c-sprites | `208371be216d3182303c3af64cbc9eab` | Superseded by D-fix — governor at original pace + chunk loading + door stale-slot fix. Froze on Dayset's playtest (write to $DFFFFE on Gameworld boot; root cause in phase C's figure-draw skip hooks). | superseded |
| c-sprites-fix | b2-strip³ | `535288396024b3892d89d74b980436ac` | Intermediate — crash fix (skip-hook return-address) + install camera moved off the merchant-attitude table + gov_npc sentinel fix. Base of D-fix; not delivered standalone. | intermediate |
| d-governor-fix | c-sprites-fix | `a2569bc0c7d93342b8cb1f2d426fbdfe` | **Current best of the big-rework line** — the fixed D: crash fix + both secondaries, lead-verified (IPS round-trips exact, C blob byte-identical). Delivered to Dayset 2026-11-20; playtest verdict pending. | current-best |

² `big-rework-poc-fix2/BASE` says `big-rework` as lineage, but its
build assembles a complete replacement blob from the ORIGINAL ROM
(the `.ips` is original→fix2, 145 records). Its build input is the
original, not the PoC ROM.

³ `c-sprites-fix/BASE` is `b2-strip`, not `c-sprites`: the fix
rebuilds C from B2 with the fixed `source.s` — its build asserts
`BASE_MD5` = B2's MD5 (`ec7bcffe…`) and its `.ips` is B2→fixed-C,
exactly as the original C build does. `d-governor-fix` then builds
on the fixed C.

**Current best of this line:** `d-governor-fix`
(`a2569bc0c7d93342b8cb1f2d426fbdfe`).

## 2b. Top-down line (#249, separate, on the original ROM)

| Patch | Base | Build | State |
|---|---|---|---|
| topdown | original | `make rom FEATURES=topdown` | Delivered 2026-11-23 for Dayset's playtest. Smooth top-down test view on the original engine: frame-locked tick, per-frame VBlank scroll/sprite updates, ring-buffer streaming, sprite blobs. Measured, not eye-tested: see `patches/topdown/README.md`, `docs/smooth-topdown.md`. |

## 3. Building

```
# from the repo root, with rop-original.gen present (user-supplied, never committed)
python3 patches/<name>/build.py
```

- Chained builds take their base from `build/rop-<base>.rom` by
  default — build the chain in order (e.g. flat-zoomed, then
  flat-zoomed-feet, then subcell, …). Override with `ROP_BASE`,
  `ROP_OUT`, `ROP_ORIGINAL`, `ROP_VASM`, `ROP_VENV_PY`, `ROP_CHECKSUM`.
- `ROP_VENV_PY` should point at a Python with capstone installed
  (needed by `check_entries.py` in b2/c/c-fix and by `disasm_blob`
  in d/d-fix); it falls back to `sys.executable`.
- `ROP_VASM` should point at `vasmm68k_mot` (`make vasm` installs it
  under `tools/vasm/`).
- Intermediates (`.bin`, `.lst`, `.gen.tmp`) go to
  `build/scratch-<name>/`; outputs go to `build/rop-<name>.rom`.
  Nothing is written into `patches/` except the committed
  `.ips`/`changed-bytes.txt` regeneration (the build scripts rewrite
  those two files in place when they run).
- `flat-world`'s `gen_flatworld.py` regenerates `source.s` from
  `disasm/src/rop.s` (reads the 112 `$E358` paint handlers); the
  landed `source.s` is the generated output.
- C-fix and D-fix share one report: the d-crash-fix report covers
  both builds and is copied into both dirs.

## 4. Not landed by #238

- Post-#234 flat-line ROMs (built after #234 was written, not in its
  table and not in #238's task): `combined-walk-tall`
  (`ee271646e0890a677fe0c0f62a9b684f`), `interp-fix4`
  (`fe5621d9de005eca074311d6668c0c13`), `camera-slide`
  (`f6928e632d3ff19a005dd5cdc9de8367`), `textured-slide`
  (`ad5ce04d593114ff1eea97d55362608a`, REJECTED). Sources stay in
  `~/workspace/rop-work/<name>/patches/`; a follow-up issue should
  land them the same way.
- `c-diag-*` diagnostic variants in `big-rework-full/patches/`
  (`c-diag-nodecode/nosprite/novbl/jmpbody/regrestore`): bisection
  artifacts for the D-crash fix, not chain ROMs — not landed.
- `big-rework/.scratch-big-rework/DESIGN.md` (1,277-line design doc,
  PoC spec §8): not in #238's copy list (REPORT.md only). The PoC
  README references it; a follow-up should decide where it lives
  (`docs/` vs `patches/big-rework/`).
- Worktree-level reports, not per-patch: `.scratch-big-rework-full/
  REPORT.md` (final full-build report), `measurements/REPORT.md`
  (phase-1 measurements), `d-crash/REPORT.md` (crash diagnosis).
  Not copied.
- `patches/smooth-move`, `music-off`, `debug-overlay` were already on
  main before #238; untouched by it.

## 5. Music patches (not rendering)

| Patch | Base | MD5 of the ROM it builds | Dayset's verdict | State |
|---|---|---|---|---|
| academy-song13 | original | `97e12dccbbec650a0067190a5aa7cf0c` | **APPROVED 2026-11-24** — v4 (bass + ch5 octave down + FB 7→2 + modulator MULTs to 1); p90 2,355 → 1,048 Hz. | approved |
