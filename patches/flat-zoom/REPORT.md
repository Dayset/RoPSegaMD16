# REPORT — flat-zoom: flat texture in the zoomed view only

**Worktree:** `~/workspace/rop-work/flat-zoom/` (main 78028bf)
**Date:** 2026-11-12
**Base:** ORIGINAL ROM `~/workspace/rings-of-power/rop-original.gen`
(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`, verified unchanged at the end)
**Status: BUILT, speed goal MET, look NOT clean — see §7 Verdict.**

## 0. Task and scope

Dayset's call (2026-11-12 ~15:39 EST): flat texture instead of terrain on
the zoomed-in block first, with subcell animation, so movement is fluid
there; the outer world view stays jerky as before. Scope change (2026-11-12
~16:34 EST): **subcell movement is a SEPARATE step that comes AFTER the flat
ROM lands — not in this ROM.** This ROM is flat-ONLY.

So this deliverable is: the flat-texture zoomed view on the original ROM, no
subcell-movement change, no glide changes, no skip-hidden-levels, no
scroll-and-patch, no sprite work. The v3 glide is NOT in this ROM (Dayset
compares it directly against the original and against the glide ROM).
Confirmed: `flat.s` contains no movement/subcell references, and `build.py`
patches only the three `map_chunk_pos` call sites plus the blob.

No branch/PR/merge/push. Lead verifies and delivers to Dayset.

## 1. Pin-down (zoomed-view render path)

Read `docs/subcell.md` and the #29 render doc on main first; the pin-down
probe below confirmed them live and pinned the view selection.

**Probe.** Blob at $FD400 (later $FD800 for the flat probe), hooks $1272
(VBlank, `jmp _vbl`) and $01BA4E (`map_chunk_pos` entry, `jsr _render` + nop).
Log at $FFD800, 150 records × 16 B (frame low $FF0012, mode $FF00AE, phase
$FFB0B6, record count $FF0096, leader cell X/Y $FF02C0/$FF02C2, render
counter, script gate $FF0110). Snapshot (once, at render #3) at $FFE400:
draw records $FFB0CC (672 B), $FFAE7A (200 B), $FFAF42 (200 B).

**Probe bugs found and fixed (do not relearn):**

- GAS is NOT installed on this VM. Use vasm (`vasmm68k_mot`, in
  `~/workspace/rings-of-power/tools/vasm/`). vasm mot syntax: `$hex`, no %
  registers.
- vasm `jmp <label>` assembles as absolute SHORT using the section offset
  (e.g. `jmp log_full` → $012A instead of $FD52A). Use PC-relative
  `bra.w <label>` for label jumps.
- BlastEm had been wiped by a restart — restored from cached debs
  (`sudo dpkg -i /var/cache/apt/archives/blastem_0.6.3.4-1build1_amd64.deb`,
  plus `libglew2.2` for the missing libGLEW.so.2.2). NEVER `apt-get install
  -f` — it REMOVES blastem. Xvfb restarted on :99.
- The VBlank handler's first instruction `move.w #0,$FF0016` is **8 bytes**
  (absolute long), so a $1272 hook must return to **$127A, not $1278**.
  Jumping to $1278 lands mid-instruction and kills all further VBlanks after
  the first (confirmed: `_vbl` hit 1× in 6 s, `_render` never hit). This was
  the root cause of the early probe freezes, not the log-full handler.
- Probe `log_full` MUST be a nop that falls through (glide-probe pattern) —
  NEVER an infinite spin inside the VBlank interrupt (it hangs the machine).
- Snapshot overflowed into the stack (copy reached $FFEC30, past live SP
  ~$FFEB42) — cap logs at 180 records, keep logs below ~$FFE800.
- BlastEm shows a "Failed to set vsync to off" dialog on launch that BLOCKS
  emulation (screenshot pairs come out byte-identical). Dismiss it by
  clicking OK at (510,315) with xdotool ~3 s after launch, then Return, then
  wait before screenshotting. mss needs DISPLAY=:99 set in the python
  process itself.

**Pin-down results (original ROM, Buc cutscene state, 150 VBlanks):**

- Mode $FF00AE = 2 throughout (room/zoomed view). Leader cell constant
  (117,113) — the leader is NOT in the room and NOT moving in this state, so
  player-walking cadence cannot be measured from it; nrec = 8 constant;
  script gate $FF0110 = 0 throughout.
- Phase (grid+$A) runs ~21–22 frames per phase; one full 4-phase cycle ≈ 87
  frames. Renders 0 → 7 over 149 frames; render deltas 22,22,24,20,21,20 →
  **cadence ≈ 21.5 frames/tick**, one render per tick/phase. Matches the #29
  measurement (22.13 frames/tick).
- $FFAE7A/$FFAF42 are isometric SCREEN positions, not tile coordinates: X =
  196 + 14·(row−col), Y = 18 + 8·(row+col) (Buc room snapshot); X range
  70–322, Y range 18–162. Tile is a 28×16 diamond on screen.
- View selector is **$FF00AE (1 = overworld/world view, 2 = room/cell/zoomed
  view)**. Writers: $00D29E (=1, main-loop entry, once), $01DC1C (=2, room
  entry in `world_location_transition`), $01DE6A (=1, overworld branch). The
  renderer `map_chunk_pos` $01BA4E is SHARED — it renders whatever grid
  $FFA7FC points to; the mode flag selects the grid at a higher level. So the
  hook checks $FF00AE at render time: ==2 → flat; ==1 → original decode.
- `map_chunk_pos` structure: per window cell (d4,d5 0..9): reads chunk cell
  word via `map_chunk_cache_read` → -$4(a6) = cell word; -$2(a6) = tile index
  (cell & 0x1FF); -$6(a6) = $5EDC4 props; buffer X -$a(a6) from $FFAE7A,
  buffer Y -$c(a6) from $FFAF42 (100 words each, per-window-cell). Height
  loop ($01BBFC–$01BC54): face call $01BC1A (stream a4), hidden call $01BC3C
  (literal $230), top-tile call $01BC84 (stream -$2(a6)). Then figure
  dispatch via b36c/b76c cell→record maps → draw records $FFB0CC (12 bytes
  each, 56 records), dispatch on +$A: 0=hero_track $01BD98,
  1=map_promote_record, 2=map_tile_at_offset, 3=map_animated_tile. Only caller
  is `jsr map_chunk_pos(pc)` at $01B96A (redraw_check).
- **$E358 call convention:** 4 words pushed: flag, Y, X, stream (stream at
  4(a7), X at 6(a7), Y at 8(a7), flag at a(a7)). Face: flag=-$10(a6),
  Y=-$c(a6)−d6·7, X=-$a(a6), stream=a4. Hidden: flag=0, same Y/X,
  stream=$230. Top: flag=(cell rol #4)&1, Y=-$c(a6)−height·7, X=-$a(a6),
  stream=-$2(a6) (tile index). Height = (cell rol #3)&7 (0–7).
- **$E358 is a dispatcher, not the decoder:** reads stream byte, d3=low
  nibble, d3=d3·2+(X−64), d4=col[d3], a5=$FF1EC0+row[Y]+d4, d1+=2 (next row),
  then d3&=6, d2=(byte&$F0)|d3, d2*=4, pushes handler from the $DF58 table
  and rts (computed goto). Path A ($E3B4, flag==0) vs path B ($E412,
  flag!=0). Negative-Y path skips lines above the buffer top.
- Row/col tables (dumped from ROM): $436E0 row: row[Y] = (Y//8)·1152 +
  (Y%8)·4 (tile-row stride 1152 B = 36 tiles × 32 B; 8 sub-rows × 4 B).
  $435C0 col: col[k] = (k//4)·32 + (k%4). Buffer is tile-contiguous: 36×23
  tiles × 32 B = 26,496 B; tile (x,y) at offset y·1152 + x·32; within a tile
  8 sub-rows × 4 B (8 pixels at 4bpp). A flat tile of palette index k = 32
  bytes all equal to ((k<<4)|k).
- **But the decoder does NOT write a tile as a contiguous 32-byte block.**
  Each $E358 call writes 8 lines at a5 = base + row[Y+k] + col[(X−64)/2 +
  lowNibble_k]; the low nibble varies per stream byte, so the bytes scatter
  across up to 2 tile columns and 2 tile rows (row[Y] wraps when Y%8 + k ≥ 8;
  col index (X−64)/2 + lowNibble spans ~4 tile columns). This is the
  and/or composite: the $E47C fragment shows it explicitly —
  `move.b (a0)+,d5; move.b (a3,d5.w),d6; and.b d6,(a5); or.b d5,(a5)+` —
  mask from the $433C0 table, pixel byte d5, AND the mask into the buffer byte
  then OR the pixel byte. The $DF58 handler table holds LONG handler
  addresses (the linear disassembler mis-decodes them as `ori.b`
  instructions); d2 index = (byte&$F0 | (low nibble & 6))·4; entries
  alternate $E3E2/$E43C for d2=0..0x3C, then $F6F8/$1102C, $F714/$11050,
  $F706/$1103E, $F722/$11062, $F694/$10FA8, $F6C4/$10FEC, $F6AC/$10FCC,
  $F6DC/$1100C, etc. $E3E2/$E43C are loop fragments (re-read the next stream
  byte, recompute a5, re-dispatch).
- `hero_track` $0231D8: template = $197B0[(rec+2 + rec+4)·36 + phase·8]; each
  phase group = (d3-add, stream, dx, dy). **Template dump (entries 0–11):
  dx = dy = 0 for ALL phases in every entry** — only `add` (stream-offset
  adder, 0/1/2/3/8) and sometimes the stream vary by phase. So hero_track's
  template does NOT supply a sub-cell position offset (at least for these
  entries); the sub-cell position must come from the record's base X/Y being
  stepped by map_place_record_step, not yet traced. (Relevant to the separate
  subcell step, not this ROM.)
- Record loop $022F52: per draw record, skip if record+0 == $270F; template
  entry = (rec+4 + rec+2)·36 from $197B0; **phase-match: grid+$A compared to
  template+$22 (offset 34)** — record processed only when phase matches
  (once per 4 ticks); type $28 + phase 3 uses template+$20 as a jump-table
  index.
- Movement loop $0227FC (combat_turn_run): iterates 56 chars; at $022826 it
  checks `cmpi.w #$2,$FF00AE` — if !=2 branch to $22A18 (Path B, overworld),
  if ==2 continue Path A (room). So the movement code ALREADY splits by
  view — scoping a subcell movement change to the zoomed view is cleanly
  possible in principle via Path A. (Separate step; not in this ROM.)

## 2. Design (v5, the deliverable)

Hook the three $E358 call sites in `map_chunk_pos` (NOT hero_track's $E358
calls at $023234/$02326C, so figures keep their texture): face $01BC1A and
hidden $01BC3C → `flat_level`; top $01BC84 → `flat_top`. Each stub checks
$FF00AE==2; if not, tail-calls the original $E358 via `jmp $00E358.l`
(absolute long — $E358 > 0x8000 so a short would sign-extend wrong). If room,
fill with byte (k<<4)|k. Preserves d4–d6/a3–a6 (movem save/restore around
the fill); reads X/Y/stream from the $E358 stack args. Blob at $FD400 (free
0xFF padding, 190 bytes). Water tiles 28/29/494 → k=9; land k = level+1
(1–8).

The v5 fill (`flat_fill8`, $FD458) writes the flat colour to the 8 line
positions $E358 computes — row[Y+k] + col[k+(X-64)/2], k=0..7, 4 bytes each
— using the ROM row/col tables, with out-of-range lines skipped. This was
the response to the v1–v4 coverage failure (see §3).

Builder: `patches/flat-zoom/build.py` (reads the ORIGINAL ROM, asserts MD5 +
0xFF padding + the three `jsr $E358` bytes `4EB9 0000E358`, writes the blob,
patches the call sites, then `tools/checksum.py fix-all` fixes the runtime
immediate at 0xFD098 first and the header checksum at 0x18E last).
**Lesson (caught in v3):** build_flat.py originally hardcoded the stub
addresses — when flat.s changed length, flat_top moved ($FD418→$FD416) and
the patch pointed mid-instruction. Fixed: build.py now parses the stub
addresses from the vasm listing symbol table.

## 3. Iterations v1–v5 (what each proved)

- **v1 (per-level colours, fill at Y, contiguous 32-byte tile block):** ROM
  MD5 `357d30e393d13111c5f8c14478ae62e4` (header 0x41A2, runtime
  0x70AA5152, 156 changed bytes vs original). Cadence ~8 frames/tick
  (renders 0→16 over 149 frames; deltas settle at 8). Screenshot
  (flat_room3.png): black diamond with scattered BLUE squares in a grid
  pattern, Thalmus drawn normally (textured, green hood, centre). The
  summary's earlier "flat pink floor" description of v1 is NOT supported by
  the surviving flat_room3.png — the interior is black with blue squares.
  (Noted here so the record is corrected by the file, not the memory.)
- **v2 (face/hidden skipped entirely; top filled at baseY = Y + height·7):**
  ROM MD5 `f680daecef904b5412e5cd330c576901`. Screenshot WORSE — whole
  diamond black + blue squares. (The baseY change did not help.)
- **v3 (DIAGNOSTIC, all fills k=1 pink):** ROM MD5
  `e7caa678ef55add4fdc9c3e45e90c3ad`. Screenshot: interior STILL black with
  blue squares — decisive: the blue squares are NOT (only) a palette
  problem; the fills do not cover the room interior.
- **v4 (DIAGNOSTIC, all fills k=15 white):** ROM MD5
  `6d18ec58444042a2b0ff1aac8f856205`. Screenshot: the blue squares became
  WHITE squares, interior still black — decisive: the fills DO land (colour
  index changes the squares), but only on scattered squares; the rest of the
  interior is never filled. **Coverage problem, not (only) a palette
  problem.**
- **v5 (8-line scattered fill, current deliverable):** ROM MD5
  `d9139010ac84119d6dc0feba5086b8a5` (header 0x2702, runtime 0x70AA5152).
  Screenshot (flat_room_v5.png, confirmed byte-identical on a second run):
  the whole diamond IS now covered — dark blue dashes on black — but
  Thalmus is NOT visible. See §5/§7.

**Root cause (established): the tile's bytes are NOT a contiguous 32-byte
block.** The $E358 writes 8 lines per tile at a5 = base + row[Y+k] +
col[(X−64)/2 + lowNibble_k]; the low nibble varies per stream byte, so the
bytes scatter across up to 2 tile columns and 2 tile rows. A contiguous
32-byte fill at (Y//8, (X−64)//8) only covers the tiles where the scatter
happens to land inside that block (~half the cells → the scattered squares);
the rest stay black (cleared buffer). The v5 fill assumes low nibbles 0..7,
which do not match the stream's actual low nibbles — so it writes to the
wrong columns (the dashes) and onto neighbouring figure pixels.

## 4. Measurements

All measured with the pin-down probe (VBlank logger + render counter, Buc
cutscene state, 150 VBlanks = 149 frames, mode 2, leader (117,113) static,
gate $FF0110 = 0).

| Build | Renders over 149 frames | Render deltas (frames) | Settled cadence |
|---|---|---|---|
| Original | 0 → 7 | 22, 22, 24, 20, 21, 20 | **~21.5 frames/tick** |
| v1 flat | 0 → 16 | 11,11,12,9,10,9,9,8,8,8,8,8,8,8,8 | **~8 frames/tick** |
| **v5 flat** | **0 → 15** | **11,11,11,13,10,10,9,9,9,9,9,9,9,9,9** | **~9 frames/tick (mean 9.80)** |

- **v5: 21.5 → 9 frames/tick, a 2.4× speedup** (v1 was 2.7× at ~8; v5's
  8-line fill does more work per call than v1's contiguous fill). Phase runs
  settle at 9 frames/phase; a full 4-phase cycle ≈ 36 frames settled
  (37.5 measured including partial first runs). The remaining ~9 frames are
  tick logic + DMA + clear + other fixed costs — about the floor for this
  architecture (cf. #29: render 15.98 + DMA 1.00 + tick 2.41 + other 2.74 =
  22.13 on the original).
- **Animation rate (frames per cell-crossing, subcell steps per crossing):
  NOT measured for the player.** The probe state has the leader standing
  still (117,113) in a cutscene — no live walking player exists in it, and
  the subcell movement is the separate next step, not in this ROM. Do not
  claim a measured player crossing rate from this work. Arithmetic only: the
  phase counter runs at 9 frames/phase (vs ~21.5 originally), so a cell
  commit gated to the 3→0 wrap would be ~36 frames/cell vs ~86 originally —
  but that is arithmetic, not a measured walk. A live walking probe (player
  actually walking in a room, logging cell + phase + figure position) is
  still needed before the subcell step, to pin the figure sub-cell offset
  mechanism (hero_track's template dx/dy are 0 for entries 0–11; the offset
  must come from the record's base X/Y being stepped by
  map_place_record_step — not yet traced).
- **Max per-frame scroll/movement delta: not measurable from this state**
  (leader doesn't move; the room doesn't scroll in the cutscene state).

## 5. Live verification

- **(a) Zoomed view flat:** screenshot/pixel check — the whole diamond is
  covered with the flat fill, no terrain texture remains. BUT the look is
  dark blue dashes on black, not distinct per-level colours (see §7).
- **(b) Figures move smoothly with subcell animation:** NOT verified and
  NOT in this ROM (subcell is the separate next step). Worse: **Thalmus is
  INVISIBLE in the v5 screenshots** (confirmed twice, byte-identical
  sha256 `9f5b8866b15e1b2d81aa4253731c877e792f1ea50767c821bb65ef641746f279`
  across two runs). The original at the same state/timing shows him clearly
  (green hood, centre); v1 at the same state/timing also showed him. The
  v5 fill overwrites figure pixels: terrain fill and figure draw are
  interleaved per cell in `map_chunk_pos`, so a later cell's scattered fill
  lands on an earlier cell's figure pixels.
- **(c) World view unchanged:** NOT screenshot-verified in this session (no
  world-view save state available). It rests on the $FF00AE==2 gate, which
  tail-calls the original $E358 for mode 1 (world view) — the three hooked
  call sites are the only behavioural changes, and the gate is a single
  `cmpi.w #2,$FF00AE` + `bne` to the tail-call. Pixel-identity of the world
  view is a stated limit, not a verified fact here.
- **(d) Boot/menu/teleport:** cold boot verified — BlastEm batch 600 frames,
  exit 0, no crash; header checksum 0x2702 and runtime 0x70AA5152 both verify
  OK. Menu/teleport were NOT live-tested in this session (probe state is
  mid-cutscene; no menu/teleport interaction was run). HUD, border, minimap,
  and controller overlay are unchanged in the screenshots.

## 6. Deliverables

- **Final ROM:** `~/workspace/rop-flat-zoom.rom` — MD5
  `d9139010ac84119d6dc0feba5086b8a5` (header 0x2702, runtime 0x70AA5152).
  `.rom` filename per Dayset's 2026-11-12 call. Flat-only, original-ROM base.
- **Patch:** `~/workspace/rop-work/flat-zoom/patches/flat-zoom/` —
  `source.s` (190-byte blob, vasm mot), `build.py` (reproducible builder:
  re-running it reproduces the ROM byte-identically, same MD5),
  `rop-flat-zoom.ips` (259 bytes, 10 records; **round-trip verified:
  original + IPS == patched ROM exactly**), `changed-bytes.txt` (205 bytes
  changed: header checksum, 3 call sites, runtime checksum, 190-byte blob),
  `README.md`, `flat.bin`, `flat.lst`.
- **This report:** `.scratch-flat-zoom/REPORT.md`.
- **Probe + screenshots (scratch):** `.scratch-flat-zoom/` — `probe.s`,
  `build_probe.py`, `run_probe.py`, `probe.gen`, `probe_log.txt`,
  `probe_snap.bin`, `build_flatprobe.py`, `run_flatprobe.py`,
  `flatprobe.gen`, `flatprobe_log.txt`, `flat_room3.png` (v1),
  `flat_room_v2/v3/v4.png`, `flat_room_v5.png` + `flat_room_v5b.png`
  (byte-identical), `orig_room3.png`, `orig_room_v5b.png`, `shot3.py`.
- Original ROM untouched: MD5 `30c18fdbe2183f64702ae9f1a45d63f9` re-verified
  at the end. v3 base ROM (`v3-base.gen`, MD5 662dc6c6…) untouched.

## 7. Verdict — honest

**What is true:**

- The flat texture makes the room tick **2.4× faster** (21.5 → 9
  frames/tick, settled). The speed goal — the reason for doing flat first —
  is MET, and ~9 frames/tick is about the floor for this architecture.
- The whole room is covered by the flat fill; no terrain texture remains.
- The ROM is flat-only (no subcell code), on the original ROM, boots clean,
  checksums verify, IPS round-trips exactly, and the build is reproducible
  byte-identically.

**What is NOT true / failing:**

- **The look is not clean.** The room is dark blue dashes on black, not
  distinct per-level flat colours. The "one fill per floor level, distinct
  colour per level, water its own colour" requirement is NOT met visually —
  the colours do not render as separate levels. Do not judge the flat
  palette from this ROM.
- **Thalmus is invisible.** The fill clobbers figure pixels. The "figures
  are still drawn normally on top" requirement is NOT met. Do not judge
  character-on-flat readability from this ROM.
- **The player animation rate was not measured** (no walking player in the
  probe state; subcell is the next separate step).
- **World-view pixel-identity and menu/teleport were not live-verified**
  in this session (code-gated only / not run).

**Blocker (for a clean flat look):** the decoder's scatter is
stream-dependent — the low nibble that selects the column comes from the
stream data, so no (X, Y)-only fill can place bytes exactly where the
decoder would. v1 (contiguous block) covers ~half the tiles; v5 (assumed
low nibbles 0..7) covers the room but on the wrong columns and over figures.
**Correct next step (not built): hook $E358's handler dispatch ($E40C) and
write flat bytes to the already-computed a5 per line, letting $E358 compute
the positions and advance the stream.** The $DF58/$434C0 dispatch tables
and the $E47C AND/OR copy fragment are mapped in §1; what remains is the
handler's stream-advance behaviour (how many stream bytes each handler
consumes). That is the follow-up if Dayset wants the flat look cleaned up
before or alongside the subcell step.

**Recommendation to the lead:** hand Dayset this ROM for the *speed* test
only, with the two defects stated up front (dashes, not clean levels;
Thalmus invisible). If he wants to judge the flat *look*, it needs the
$E358-dispatch hook first. The subcell step should be built on top of a
flat ROM whose fill does not clobber figures — otherwise the subcell
playtest cannot show the character moving.

## 8. Harness/probe notes worth keeping

- vasm `jmp <label>` → absolute SHORT from section offset; use `bra.w`.
- $1272 VBlank hook must return to **$127A** (first instruction is 8 bytes),
  not $1278.
- `log_full` must be a fall-through nop, never a spin inside VBlank.
- Cap RAM logs at 180 records, below ~$FFE800 (live SP reaches ~$FFEB42).
- BlastEm vsync dialog blocks emulation — click OK at (510,315) via xdotool
  ~3 s after launch, then Return, then wait.
- `build_flat.py` must parse stub addresses from the vasm listing, never
  hardcode them (flat_top moved when flat.s changed length).
- The `flatprobe` builder builds the probe ON TOP of the current
  `flat-zoom.gen` (probe blob at $FD800); rebuild it after any flat rebuild
  before re-measuring.
