# RROP — Rings of Power Recompiled (kruzeman/RROP)

**Source:** https://github.com/kruzeman/RROP (found by Dayset, 2026-11-10).
Static recompilation of Rings of Power into a native Linux/Windows executable.
Original RROP code is MIT licensed; extracted from GenesisRecomp
(kruzeman/GenesisRecomp) at commit `5a3207c2` on 2026-10-04.

**Same ROM revision as ours.** RROP validates the ROM by SHA-256 and expects
`36303fc447c433ebc69c3d4df86c783c86b383e0acead1c19595f13269e248f5` —
identical to our `rop-original.gen`. So everything RROP documents about the
game applies directly to our ROM.

## What it is

A Python recompiler (`genesis_recompiler/`: `decode.py`, `discovery.py`,
`callback_discovery.py`, `ram_discovery.py`, `z80.py`, `emit.py`, `build.py`)
translates the 68000 code and the Z80 sound code to C, with a runtime for the
console's memory, video, input and sound hardware (VDP tile/sprite rendering,
palette/VRAM, frame/interrupt timing, ymfm YM2612 + PSG). The generated program
dispatches translated operations; it does not decode opcodes at runtime, and
undiscovered addresses remain execution faults. The original 64 KiB work RAM
is retained; the host does not expand the game's fixed tables or change its
16-bit arithmetic.

Features (README + `docs/settings.md`): widescreen world rendering, viewport
zoom 50–100%, smooth outdoor camera scrolling, live text replacement with an
external TTF/OTF font, mouse movement + native automatic walking, SDL2
gamepads with hotplug, five manual saves + five rotating autosaves (every five
minutes of active play), in-game Settings/save menus, diagnostic reports and
emergency snapshots for native Void errors. Classic presentation remains
selectable; interiors and battles use the original viewport at 100% zoom.

## Why it matters to this project

### 1. Smooth camera — the L037 reference (GitHub #26–#32)

`genesis_recompiler/rings_camera.h` implements smooth scrolling as a
**presentation-layer tween**, not a change to the game's update rate:

- When the game's camera changes to a new "generation", it computes the camera
  delta in presentation pixels (dx, dy) and tweens from the old position to the
  new one over a duration (default 200 ms), with a linear catch-up
  (`left = 1 − elapsed/span`).
- It only tweens when the movement is "continuous": same scene identity,
  generation increased, camera delta ≤ 56 px (x) / ≤ 32 px (y), focus delta
  ≤ 48 px. Otherwise it snaps (no tween).
- No prediction, no pad queue. The console's master clock freezes the tween
  during pause/save selection.

This is the approach the L037 work needs. The settings doc states it plainly:
"Smooth scrolling is a presentation feature; the native game still updates its
decisions at its own rate." Our smooth-move v1 patch tried to change the
game's own scroll and was rejected (teleports, no sub-cell motion); RROP shows
the correct shape is to interpolate the *visual* camera between the game's
discrete ~3 Hz steps, leaving the simulation alone. Directly relevant to the
#26–#32 breakdown (especially #28 sub-cell walking and #29 world-view redraw
cost — RROP sidesteps the redraw cost by not redrawing the game world at all,
only moving the presented camera).

### 2. Void death — the trigger, answered (docs/diagnostics.md)

The "Void has found your party…" message is a **generic internal-error
screen**. The number inserted before `seconds` is an **error code, not
elapsed time**. Confirmed codes:

| Code | Condition |
| --- | --- |
| 22 / `0x16` | No free entry in the 56-slot placement table |
| 26 / `0x1a` | No free entry in the 56-slot actor table |
| 24 / `0x18` | Object absent from the placement cache |

This answers the open Void-death item (text at ROM 0x1215A; trigger/timer
NOT located). The trigger is a **full 56-slot table** (codes 22/26) or a
**missing placement-cache object** (code 24). The error handler is at
`$012FA0`; RROP writes a report + emergency checkpoint on entry to it.

The two 56-entry tables are the ones the terrain-grid work resolved:
`$FFB0CC` (placement, 56 × 12-byte records) and `$197B0` (actor, 56 × 36-byte
records). RROP's diagnostics confirm both layouts: actor entries are occupied
when the header's low nibble is nonzero; placement entries are occupied when
their first word is not 9999 (`$270F`). It records the last 256 slot-header
changes across both tables (writing instruction's PC, frame, execution step)
plus free↔occupied transition counts and peak occupancy.

### 3. Saves — a different system, not the EEPROM loader

`rings_saves.h` handles slots, checksums, atomic replacement and a wall-clock
autosave schedule. Loading a checkpoint restores its RAM; **it does not call
the original EEPROM loader or recreate the game's temporary object tables**.
So RROP's saves bypass the 128-byte serial EEPROM format (#019) rather than
implementing it — useful as a contrast, not as a source for the EEPROM format.

### 4. Widescreen / text / input

- `rings_wide_*`, `rings_zoom.h`, `rings_window.h` build the expanded outdoor
  view from the verified game render routines; `rings_scene.h` identifies fixed
  interiors and battles for native presentation.
- `rings_text_*` captures the game's text and redraws it with an external
  font (no fixed translated-string list).
- `rings_mouse*` submits directional movement and native A + direction
  requests rather than implementing independent pathfinding.

## Notes / cautions

- RROP is a *wrapper*, not a disassembly: it recompiles the game as-is and
  adds presentation features on top. It does not document the game's internal
  routines (no routine names, no logic docs) — its value to us is the
  *behavioural* evidence (smooth-camera shape, Void error codes, table
  occupancy rules) and the confirmed ROM revision.
- **RROP is not compatible with original Sega hardware** (Dayset 2026-11-10).
  It produces a native Linux/Windows executable that runs on a modern PC; it
  does not produce a ROM that runs on a Genesis/Mega Drive. So its
  presentation features (smooth camera, widescreen, saves) cannot be ported
  back to the original hardware as-is — only the *design* (e.g. the
  presentation-layer tween shape for L037) and the *behavioural* findings
  (Void error codes) transfer to the ROM/RE path. This is why the project
  stays on the previous (ROM/RE) path, not the RROP direction.
- The Void error codes are "confirmed calls" per RROP; the docs note they do
  not yet prove which one causes a reported failure after extended gameplay.
- The smooth-camera tween is a host-side presentation feature; it cannot be
  ported to the ROM as-is. Its value is as the design reference for L037:
  interpolate the presented camera, don't change the game's step rate.
