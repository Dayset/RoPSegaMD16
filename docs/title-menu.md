# Title menu and start screen — resolved (#272)

The start screen is fully mapped: attract → Naughty Dog logo → crawl →
title menu → story screens / new game / demo mode. The title menu
**exists** (it was undocumented before this work). All addresses are ROM
offsets unless marked `$FF…` (RAM). ROM under test: `rop-original.gen`,
MD5 `30c18fdbe2183f64702ae9f1a45d63f9`.

Evidence: live stable-retro probes in `scratch-272/` (uncommitted scratch;
`probe272.py`, `out-o1a/`, `out-o1b/`, `out-o2/`, `out-o3/`, `out-o4/`,
`out-o4b/`), the blind-spot hunt report in
`~/workspace/rop-work/blind-spots/` (not in this repo), and ROM
disassembly (`mdis.py` reads cited inline).

## Player-visible flow

```
boot → attract (title logo + shimmer, $4E6)
  → $119E → $14FB6 → $123B0 (Naughty Dog logo screen)
  → $15012 (crawl + title menu)
    ├─ press during crawl counter 200–1999 → title menu
    │    ├─ Continue → LOAD $2F896 (EEPROM save)
    │    ├─ Start    → new game
    │    ├─ Intro / Citizens / Credits → $147D0 story screens
    │    └─ after Continue/Start confirm → fade loop → "The Adventure Begins" card → world
    └─ wait out the crawl (counter 3000) → Intro screen (fast) → DEMO mode (no menu)
```

The attract loop (`0x35C–0x390`) exits on any button press **or on its
own**: `$4E6` sets `$FFC000` when its countdown (`$FFC002`) expires, and
the loop falls through to `$119E`. Observed: after a demo-mode reset the
attract runs ~490 frames before `$119E` clears RAM (O1a: exit f15638 →
RAM clear f16131; O1b: exit ~f9520 → RAM clear f10008).

## The title menu ($15012)

`$15012` draws the menu on the night-landscape backdrop (tileset rec 37
via `$1383C(0x24A, 0x25)` → `$FF8642`, tilemap rec 40) and writes the
five words from ROM `0x15BB8` with `text_glyph_draw $1113C` at rows
`0x0D–0x11`:

- Continue / Start / Intro / Citizens / Credits

Menu poll loop at `0x1591E`; cursor redrawn at row `0xE8 + sel*8`.
Confirm paths:

- **Continue** → LOAD `$2F896` (EEPROM). Returns `0x4D` if mode
  (`$FF00AE`) != 1; else `$177B4(2)` — `0x49`/`0x4E` proceed to load,
  anything else is returned as the result code.
- **Start** → new game (`$1B5D6`).
- **Intro / Citizens / Credits** → `$147D0` story screens, recs
  32 / 61 / 59, flag 0 (slow scroll).
- The confirm is followed by the fade loop (below) for Continue/Start.

### Reachability gate (O6)

The menu is only reachable by pressing a button while the crawl counter
is in **200–1999**. Mashing before the window opens confirms nothing
(hunt: mashing f300–600, window opens ~f680). Waiting out the crawl
(counter 3000, ~8300 frames) skips the menu entirely: the timeout path
(`0x154EA`) plays song 1, shows the Intro screen **fast**
(`$147D0` record 32, flag 1 — the fast path's only known caller),
sets `$FF0128 = -1`, and starts a **demo game** (below).

**Constraint for the input-flush fix:** any flush must preserve a way
to reach the menu. The flush hook is placed at `$15916` — after the
crawl's jump decision (crawl poll at `0x1537A`), so the press that
opens the menu is not eaten, and at the last palette load before the
menu loop's first poll at `0x1591E` (menu-entry setup takes many
frames; flushing earlier would let a still-held button re-queue
before the first poll). Live V2 evidence: a deliberate A press at
f1300 confirmed Continue at f1316 after the menu waited 500 frames.
The flush patch itself is **not in this repo** (input-flush V4, hook at
`$01DE64` with a mode==2 guard; awaiting Dayset's playtest — mash
during logo, mash during battles).

## Demo / attract mode ($FF0128) — O1 CLOSED

`$FF0128` is the **demo-mode flag**, not a loaded-game flag
(corrects `docs/architecture.md`'s earlier guess). It is written at
exactly one site, `0x15512` (`move.w #$FFFF, $FF0128`, in `$15012`'s
crawl-timeout path), and cleared only by the `$119E` RAM clear on the
soft-reset path. There is no missed clearing write.

In `$D28E`, `$FF0128 != 0` takes the `0xD328` branch: command byte 10
(walk) every iteration, direction from the RNG (`$12B82(8)`, else
`$12B82(5)`); D-pad input is ignored. The branch exits the main loop
(`rts` → `$D25C` → `$179B6` soft reset) when:

- any A/B/C/Start press is polled at `0xD366` (`$FF0E14 & $F0 != 0`), or
- the clock `$FF0E16 / 10 == 3` — the clock starts at 2100 (mod 2400),
  so the demo ends when it wraps and reaches 30–39, ~330 world ticks
  after world start.

Live proof (no input after the initial tap, `out-o1a/`, 17500 frames):

- World starts f8755 at the random spawn (step 2100, cam 284,86);
  **539 distinct cam positions** with zero input (`$FF0E14`/`$FF002C`
  max 0) — the leader auto-walks.
- Step hits 30 at f15638; the game resets; attract runs; RAM clears at
  f16131; the crawl restarts (Naughty Dog screen at f16500/f17000).

Live proof, button exit (`out-o1b/`, A pressed f9500–9509):

- Exit ~f9520 (step/cam freeze at 2135 / 341,93); RAM clear f10008.

An earlier claim that "R/D/L walking works" after a crawl-timeout start
is **refuted**: that movement was the demo auto-walk, not player input.

## "The Adventure Begins" card — O2 CLOSED

The card is **not** a text string and **not** the `$35612` load-result
message. It is pre-rendered tiles, drawn by `$15012`'s post-confirm
fade loop (`0x15A86–0x15B9C`):

1. After confirm, the menu words are erased (tilemap clear `$11A1A`).
2. The night-landscape backdrop scrolls down: `$DBCC(0,0,-$2(a6),0)`
   with the offset running 288 → 0, one VBlank per step, a shrinking
   busy-wait (`0x2710` → `0x7D0` counts).
3. At offset 216 (`0xD8`) a tilemap region is drawn from tileset
   rec 38 (`$1383C(0x84, 0x26)` → `$FF867E`, 132 tiles) via `$11820`
   at `0x15AE6` — the gold script **"The Adventure Begins"** — and
   the song-8 sting plays (`$173BC(8)` at `0x15B14`).
4. Palette crossfade when the offset reaches ≤ 32 (`$1225C`), a
   `0x186A0`-count delay, return 0 → `$12C20` → `$1B5D6` → world.

Frame math matches the live run (`out-o2/`): confirm f736, scroll
f745–1166 (~289 iterations), card text visible f800–900, world starts
f1171. The card appears after **both** Continue and Start confirms;
the crawl-timeout path shows **no** card.

Why no text search finds it: the words are tiles, not a string. All 62
`$96120` records decoded — only rec 59 matches "Adventure" ("A Fantasy
Adventure by"); no record contains "The Adventure Begins"; no plain
ASCII in the ROM; absent from the 1184 `$DDBD8` records.

The `$35612` message is something else entirely (live, `out-o2/`):
Continue with no save → LOAD fails → `$FFBB86` holds
`"Sorry! I couldn't restore the game because of media error. Consult
your manual. "` from f1174, shown as a kind-1 text box in the world
from f1179 (`e078=0x51`, screenshot `out-o2/f01200.png`). The
`$35612` Start-path text is `$DDBD8` record 20, "The fabled Sorcerer's
Academy." (via `text_pick_record` → table index 20).

## The $123B0 window-down scene — O3 CLOSED

`$123B0` draws the **Naughty Dog logo screen**: a tropical sunset band
(orange/yellow sky gradient, blue water, green palm fronds hanging from
the top), the cartoon brown dog sliding in from the left to the right
side, and the "NAUGHTY DOG SOFTWARE" logo in stylised green/yellow/red
lettering sliding in from the left. Tilesets recs 0/2/3/4/5 via
`$1383C` + `$11A7C` DMA; sprite grids via `$11C9A`; palette
crossfades via `$1225C`; joypad poll `$1350` at `0x12AC8` skips the
delay loop on a button press (mashing shortens the scene).

Screenshots (`out-o3/`, unskipped run — single tap, no further input):
`f00470.png` sunset band; `f00550.png`/`f00600.png` dog sliding in;
`f00650.png`/`f00700.png` logo sliding in. Same screen replays after
the demo reset (`out-o1a/f16500.png`, `f17000.png`).

`$123B0` returns 1/2/3 (story screens via `$14FB6`) or 0 (world).

## The joypad ring — corrected roles

16-entry ring `$FF001C`, producer VBlank ISR `$1272`, consumer pop
`$1350`. **Corrected index roles** (the earlier head/tail labels were
backwards; read from the disassembly):

- `$FF001A` = **producer/write** index (ISR `$1272` writes
  `ring[$FF001A]` and advances it; full when `(write+1) & $F == read`).
- `$FF001B` = **consumer/read** index (`$1350` reads `ring[$FF001B]`
  and advances it; empty when `read == write`).
- `$FF002C` = last-popped byte. On an empty queue `$1350` returns
  `$FF002C` unchanged — the **echo defect**: a stale byte replays
  until a new byte is queued.
- `$FF0018` = last-read pad byte; `$FF0019` = debounce counter.

ISR `$1272` push rules (read at `0x1272–0x134E`):

- Byte **changed** vs `$FF0018`: store it, `$FF0019 = 3`, no push.
- Byte **unchanged**: `$FF0019--` per VBlank; push when it hits 0 —
  i.e. a byte is pushed **~3 frames after it stabilises**.
- After a push `$FF0019` is 0, so the next decrement wraps it to
  `0xFF`: a **held** button re-pushes once per **256 frames**, not
  every 3 frames (corrects `docs/architecture.md`'s "key-repeat"
  claim). A mash re-queues because each press/release is a byte
  change.
- Observed pad bytes: Start `0x80`, A `0x40`, R+C `0x28`.

Nothing flushes the queue except boot init (`$119E`: `$FF0018` /
`$FF002C` / `$FF001A` / `$FF001B` = 0, `$FF0019` = 3). During attract,
interrupts are masked (`SR=$2700`), so nothing queues during the logo;
buffering starts after `$119E` unmasks (`SR=$2000`).

## Battle → world leak — O4 CLOSED

Live battle→world confirmation exists (scripted playthrough to a real
bear battle, TEST-ONLY RAM boost HP 140 — 1000 HP breaks the battle
menu; battle-start recompute clamps cur HP to 140). Two original-ROM
runs with the input-flush battle harness (`out-o4/`, `out-o4b/`):

- Battle starts f4659; both bears dead f7638; world resumes f7782.
- At resume the queue is **13/16 full** — `$FF001A`(write)=4,
  `$FF001B`(read)=7 → `(4-7) & $F = 13` stale entries (this corrects
  the earlier "3 stale entries" count, which read the indices the
  wrong way round). `$FF002C = 0x28` (R+C), draining to empty by
  ~f8000.
- **No visible phantom action:** the camera stays frozen at
  (117, 115) for 1218 frames after resume with zero input, in both
  runs (RC mash; RC/R alternating mash). One distinct cam position.

Mechanism (inference, consistent with the observations): the victory
screen pops entries while hunting for the C bit that exits it, so the
pure-D-pad entries are consumed there; the entries that survive into
the world all carry the C bit and are absorbed by the `$12FCA`
button-wait loop without producing a walk step. The leak is real at
queue level and invisible at gameplay level through this path.

Two corrections to the issue's premise: `combat_battle_end $3599C`
**never runs** on the win path (victory goes through `combat_turn_run
$0226BC` → kind-6 victory message in `text_event_message $0275B0` →
world resume via `world_location_transition $01DA6C`); and the V4
flush hook sits at `$01DE64` with a mode==2 guard, **not in the repo**,
awaiting Dayset's playtest.

## Small items — O5 CLOSED

- **(a) `$147D0` flag arg.** `$147D0(record, flag)`:
  record = `8(a6)`, flag = `$A(a6)`. Flag 0 → 15000-count (`0x3A98`)
  idle wait per scroll step (slow scroll); nonzero → 6000-count
  (`0x1770`, 2.5× faster). D-pad skips the wait entirely; `$F0`
  exits scrolling. Callers (push order verified in ROM bytes — first
  pushed value lands at `$A(a6)` = flag):

  | Caller | Record | Flag | Scroll |
  |---|---|---|---|
  | `$14FB6` 0x14FD4 | 32 Intro | 0 | slow |
  | `$14FB6` 0x14FE8 | 61 Citizens | 0 | slow |
  | `$14FB6` 0x14FFC | 59 Credits | 0 | slow |
  | `$15012` timeout 0x15504 | 32 Intro | **1** | **fast** |
  | `$17B88` 0x17BA0 | 55 "From the Book of Buc" | 0 | slow |
  | ending routine 0x195B4 | 59 Credits | 0 | slow |

  The fast path's one known caller is the crawl-timeout path.
- **(b) Rec 4 `$1383C` decode failure.** `$96120` rec 4 is an
  8-tile tileset record (len 256 = 8×32 bytes), not a text stream;
  `dd5c_decompress` returning binary garbage is expected — wrong
  decoder, not a corrupt record.
- **(c) Rec 55 "From the Book of Buc"** shown by `$17B88` via
  `$147D0(0, 55)` — already closed in the issue; caller site
  re-confirmed at `0x17B9A–0x17BA0`.
- **(d) `$15C08`'s `$1350` call site past `0x15E00`.** At
  **0x161AA**, in the tail starfield loop `0x16158–0x162FC`: local
  counter starts at `-0x40`, += 4 per iteration; each iteration
  polls `$1350` → `$FF0E14`, VBlank-waits (`$1386A`), writes the
  H-scroll wave (`$171D6`); exits on a button byte (`$F0`) or when
  the counter reaches `0x3E8` (1000) — 266 iterations max.
  `$15C08`'s arg is read at `0x15E8A`: 0 → extra tilemaps recs
  `0x16–0x1A`; 1 → recs `0x30–0x33` (used by the 0x195AE ending
  routine).

## What still blocks closing #272

Nothing in the issue's open items remains open after this work — O1–O6
are all resolved with the evidence above. What remains is outside the
issue's own scope: the input-flush V4 patch is built and live-verified
but **not in the repo and must not land until Dayset's playtest
verdict** (mash during logo, mash during battles). Closing the issue
is a call for the parent agent / Dayset: the patch landing (or an
explicit decision to keep it out) is the only outstanding dependency.
