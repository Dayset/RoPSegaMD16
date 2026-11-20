# walk-unused-frames — cutscene Y fix

Base: `rop-walk-frames-fix.rom` (MD5 `9ba279759436b96a732d11d9a3f6be0d`).
Deliverable: `rop-walk-unused-frames.rom`
(MD5 `6764e6ee86976e1a3607388f4cb5faa3`, header 0x639F, runtime
0xA15C8097). Original ROM untouched
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## Dayset's correction (applied)

The unused poses (offsets 4, 5, 10, 11, 12, 13) are NOT walk
frames — they are combat moves / a cast. Verified from the ROM
template table $197B0: offsets 4, 5, 10, 11, 12, 13 are used by
templates 16–27 (the combat/cast templates); the walk templates
36–55 use only offsets 0, 1, 6, 7, 8, 9, 14, 15; ALL 16 offsets
are used by some template 0–55. There are no unused walk-frame
poses. **The unused-poses idea is dropped.** No combat/cast pose
is fitted into the walk routine. (The walk-frames report's claim
that 4, 5, 10, 11, 12, 13 are "never used by any template 0–55"
is wrong — its scan missed templates 16–27.)

## The cutscene Y problem (Dayset's playtest of the fix ROM)

"cutscene Y is completely off. He is doing 2 steps and then waiting
for longer than usual and jumps screen, and repeat. Like he is
waiting and running after 2 cells." The zoom walk on that ROM is
very good (walks even better than interp-fix2, no yoinks, movement
begins with 1–2 presses) and does not use the loop driver or the
Y-shift hook (both are gated to the cutscene), so this fix cannot
break it.

## The fix (three byte changes, no new blob)

1. `$023202` (hero_track): `jsr $FDA00.l` → `lea.l $197B0,a0`
   (Y-shift hook off).
2. `$023480` (map_promote_record): `jsr $FDA00.l` → `lea.l $197B0,a0`
   (Y-shift hook off; this is the routine Buc is drawn through).
   The `$FDA00` walk-hook blob is left in place, now unreferenced
   (0xFF padding region, outside the runtime checksum range).
3. `$FD866` (loop_drive): `beq.b $FD86A` → `bra.b $FD88A`
   (step Buc on every `sys_event_run` call; the `.half` non-step
   block is dead code, `walk_half` stays 0). Restores the original
   cutscene-loop cadence: one cell per 4 ticks, not 8.

After the fix the cutscene walk is the cutscene-loop walk (which
Dayset already saw working): Buc walks the loop S,E,N,W, turning
when blocked or after 20 steps, at 4 ticks/cell, with no Y shift.
The world shift is still jumpy (integer-cell camera) — that is
the big rework, not this fix. The flat, feet fix, loop driver
(except the cadence), and cutscene dialog/script are otherwise
unchanged. The big world stays textured.

## Build

`python3 build.py` — verifies the base MD5 and the three site
bytes, applies the patch, fixes both checksums
(`checksum.py fix-all`), writes `changed-bytes.txt` (18 bytes)
and `walk-unused-frames.ips` (61 B, round-trip verified:
base + IPS == ROM exactly). `checksum.py verify-all` exit 0.
The patched sites were re-disassembled with Capstone:
`$023202`/`$023480` decode as `lea.l $197b0.l,a0`,
`$FD866` decodes as `bra.b $fd88a`.

## Not verified (Dayset is the tester)

No live probes, screenshots, cadence measurements, or playtest
verification. In particular not verified: whether the cutscene
walk now reads as smooth (no long waits, no screen jumps);
whether the 2-step legs still read as stuttery (they are short
because the room is crowded — Buc turns when blocked); the
zoom walk still very good; standing still; menu/teleport;
other rooms; the cutscene dialog and Thalmus's moves still
running.
