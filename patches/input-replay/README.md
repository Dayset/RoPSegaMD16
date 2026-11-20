# input-replay — deterministic input replay overlay (issue #240)

Feeds pad bytes from a script table into `joypad_queue_pop` ($1350),
so the same ROM + the same script = the same run, every time. No
xdotool, no save state, no live input. This is a TEST-ONLY overlay:
it is applied to a base ROM by `build.py` and never lands in the
main build (input-replay is off unless selected).

## Why this hook

Issue #240's default design hooks `pad_latch_11bb8` ($11BB8). That
routine is DEAD CODE in the shipped ROM (`not_reachable_from_entry.txt`:
"0x11BB8 called-by-direct: none") — a hook there would feed nothing.
The live path is VBlank ($1272) -> $FF0018 -> 16-byte ring at $FF001C
-> `joypad_queue_pop` ($1350) -> $FF0E14/$FF8646. Every consumer
(main loop, menus, `sys_wait_button_press`) reads through the pop,
so hooking the pop covers all of them.

## Layout

- Blob at $FE000 (free 0xFF padding in the original, flat-zoomed, and
  walk-unused-frames ROMs). `REPLAY_MAGIC` ($9C07) is the first word;
  `replay_pop` follows at $FE002.
- Hook site $1350 (8 bytes: `moveq #0,d0; moveq #0,d1; move.w
  #$2700,sr`) -> `jsr replay_pop.l` + `nop`.
- Table: 4-byte entries (`dc.w frame_count, dc.b pad1, dc.b 0`),
  sorted ascending, terminated by `dc.w $FFFF`. The pad in force at
  frame F is the last entry with frame_count <= F; before the first
  entry the pad is $00. Frame = low word of the frame counter at
  $FF0012 (+1 every VBlank). Runs are < 65536 frames.
- Pad byte: bit=1 pressed (01 U, 02 D, 04 L, 08 R, 10 B, 20 C, 40 A,
  80 S).

## Stack discipline (the D-crash rule)

Both paths in `replay_pop` discard the hook jsr's return with
`addq.w #4,sp` FIRST — the replay path before `rts`, the
passthrough path before `jmp $1358`. Without the discard, the pop
body's `rts` would return to the hook site and run the body a
second time (the exact bug that collapsed the stack in the
big-rework C blob; see `.scratch-big-rework-full/d-crash/REPORT.md`
§6 in the big-rework-full worktree).

## Build

```
python3 patches/input-replay/build.py --base <base.rom> \
    --route <route.txt> --out <out.rom>
```

Route file: one step per line, `<frames> <pad>` (durations; `#` =
comment). See `tools/playtest_route_*.txt`. The builder converts
durations to change entries, assembles the blob with vasm, verifies
the hook-site bytes and the 0xFF padding, applies blob + hook, fixes
both checksums (`checksum.py fix-all`, runtime first, header last),
and emits `.ips` + `changed-bytes.txt` next to the output ROM
(IPS round-trip verified). Per-run intermediates go to
`<out-dir>/scratch-input-replay/`; only `replay_table.bin`
(git-ignored) is written into this directory, because vasm resolves
the `incbin` relative to it.
