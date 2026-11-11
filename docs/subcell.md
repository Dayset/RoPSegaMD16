# Sub-cell movement reference (#27, #31)

Status: partial. Static findings only. The Buc cutscene offset path is not yet traced.

## Repro (#31)
- `tools/walk_repro.sh ROM STATE KEYS [FRAMES]` runs BlastEm from a state, sends keys, writes `build/walk-repro/events.bin`.
- Route: New Game → `1R 8U 5R 4U 1L 1S` → `4L 10U 17L 1Dn` → `d`, `a`, `a` (Buc cutscene).
- Keys were not verified in this CI VM (xdotool keys did not reach BlastEm here). Confirm bindings on the run machine.
- A 60 fps capture comes from the run machine (ROM not in this repo).

## Scroll writers (static, from disasm/src/rop.s)
- `$DC16` (`vdp_set_scroll`): writes VSRAM 0–1 (vertical) and VRAM `$2000` 0–1 (horizontal). Callers: `$11E06`, `$12C20`, `$1702C`, `$166FA`, `$16D6A` (map scroll, `(v,v,h,h)`).
- `$171D6` (`vdp_write_hscroll_wave`): per-line H-scroll table writer with a wave term. Callers: `$1511C`, `$1544A`, `$1546E` (in the function labelled `intro_helper`), `$161DC`, `$18E08` (in `scene_draw`).
- Per-line H-scroll (R11=`$03`) is set at `$15D6E`, `$17D08`, `$18C40` (docs/graphics.md §6.x).
- `$1C21A` is the position setter (mode 6) and `$1B918` the redraw checker (docs/architecture.md).

## Open
- Which caller the Buc cutscene uses. Needs a `-l` address log from the cutscene state.
- Label conflict: `$161DC` sits inside the function labelled `snd_music_start` in rop.s. Recorded as a question; not resolved here.
