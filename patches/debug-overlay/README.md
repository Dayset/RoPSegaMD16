# Debug overlay — live song-state readout

A small on-screen overlay for a playthrough check of the Life sting
(song 8) audibility. It shows the live song state in the Window plane,
row 0, columns 14–33, re-drawn every VBlank:

```
S02 0F363E 0F373E FF
```

| cells | content | source |
|---|---|---|
| 1 | `S` | literal label |
| 2–3 | `08` | song index, low byte of `$FF012E`, 2 hex digits (`$FF` = none yet) |
| 4 | ` ` | literal space |
| 5–10 | `0F363E` | song start `$FF022C`, low 24 bits, 6 hex digits |
| 11 | ` ` | literal space |
| 12–17 | `0F373E` | song end `$FF0230`, low 24 bits, 6 hex digits |
| 18 | ` ` | literal space |
| 19–20 | `FF` | sound-on `$FF021E`, 2 hex digits (`FF` = on, `00` = off) |

## How to read it (song 8)

The Life path calls the `$173EC` dispatch **directly**, bypassing the
`$173C0` wrapper that is the only place `$FF012E` is set. So when Life
revives someone, **`$FF012E` does NOT change** (it keeps the previous
song's index, e.g. `02`), but **`$FF022C` becomes `$000F363E`** and
`$FF0230` becomes `$000F373E`. Song 8 therefore shows as:

```
S02 0F363E 0F373E FF     <- song 8 playing via Life (index still 02)
```

while the location song looks like:

```
S02 0ED4FE 0EDDFE FF     <- song 2 (map theme) playing normally
```

Watch the **start address flip to `0F363E`** (and the index stay put)
to see song 8 start, and watch it flip back (to the location song's
start, or to song 0's `0ED0E8` after the watchdog replay) to see it
finish. The sting is ~1.2 s (~72 frames), so the `0F363E` readout is
visible for about a second, then changes. That is the audibility
question this overlay is for: is the sting actually heard in real
gameplay, or only visible as a readout?

## Mechanism

- **Hook:** `$1272` (VBlank handler entry). Replaces the 8-byte
  `move.w #$0,$FF0016` with `jmp $FD200.l` + `nop` (the proven
  `.scratch026` pattern). The trampoline replicates the replaced
  instruction, then `jmp $00127A` (resume handler).
- **Draw:** Window plane, VRAM `$1000` (Layout G). Row 0, col 14 =
  `$101C`. Row 0 is stride-independent (works in both Layout G
  variants, R16 64-wide and 128-wide). Re-drawn every VBlank — the
  game clears/redraws the window on scroll and menu/message actions,
  so a write-once overlay would vanish.
- **Font:** base read from `$FF8640` at runtime (scene-dependent);
  tile = base + (ASCII − `$20`). Digits `'0'`–`'9'` = base+`$10`+v,
  `'A'`–`'F'` = base+`$21`+(v−10), `'S'` = base+`$33`,
  `' '` = base+`$00`. Name-table word = bare tile index (pal 0,
  no flip, priority 0), matching the game's own window text.
- **Layout G check:** only draws when `$FF8644 == $2400` (sprite-table
  base). In Layout L (intro/story/location pictures) the window is
  `$F000` and `$101C` would scribble Plane B, so the overlay is
  absent there. That is intentional.
- **Trampoline:** `$FD200–$FD3FF` (512 bytes allocated, 208 used),
  in the free `0xFF` padding. Clear of the music-off patch
  (`$FD0CC–$FD137`).
- **No PC/SP snapshot** (the `.scratch027` bisection proved that
  corrupts boot/title). The hook saves/restores `d0-d4/a0-a1` only.

## Known hazards / limits

- **VDP writes from interrupt context:** the main loop writes to the
  VDP and VBlank interrupts are enabled with no VBlank sync in the
  `$D28E` loop tail, so a VBlank can land mid-VDP-write and interleave
  the overlay's writes into the main loop's sequence. The hit rate is
  low and the glitch is transient (a few misplaced tiles,
  self-correcting on the next redraw). For a debug tool that is
  acceptable. If it shows up, the fallback is the two-hook variant in
  `.scratch028/overlay-investigation.md` §3.6 (VBlank hook samples to
  RAM only; a `$1B918` main-loop hook draws).
- **R17 drift:** the map-scroll routine writes R17 computed from the
  scroll offset, so the overlay's screen column may drift as the
  player scrolls. The overlay is re-drawn every frame into the same
  window cells, so it stays visible; only its screen column may move.
  Confirm it stays put on a playthrough.
- **Row 0, cols 14–33** are clear of the game's menu/message
  fills/draws as decoded, but a full audit of every `$11A1A`/`$118C8`
  call site (notably combat routines) was not done. If a combat or
  town UI element draws at row 0, cols 14+, the overlay will fight
  it (flicker). The per-frame redraw means the overlay wins on the
  next VBlank.
- **Layout L:** the overlay is absent on location pictures and the
  intro (by design — see above).

## Verification (live, BlastEm)

`.scratch029/` — the harness sets Layout G state (`$FF8644=$2400`,
`$FF8640=$134`) and a fake song-8 state (`$FF012E=2`,
`$FF022C=$000F363E`, `$FF0230=$000F373E`, `$FF021E=$FF`), lets the
overlay hook run, then reads back VRAM `$101C` (20 words) via the
VDP data port and exfiltrates via EEPROM. Result: **PASS** — the
VRAM row reads exactly `S02 0F363E 0F373E FF` (all 20 words match),
and the VBlank frame counter `$FF0010` reached `0xA8` (168 VBlanks),
proving the hook runs every frame. (One harness lesson: the attract
loop runs with interrupts masked, so the harness must set SR=`$2000`
for the VBlank hook to fire at all.)

## Files

- `overlay.s` — the overlay (GAS, `m68k-linux-gnu-as -m68000`).
- `build.py` — assembles, patches a copy of `rop-original.gen`,
  fixes both checksums (`tools/checksum.py fix-all`), writes the
  IPS and the patched ROM.
- `rings-of-power-debug-overlay.ips` — apply to a clean original ROM.
- `rop-debug-overlay.gen` — patched ROM for Dayset (git-ignored).
- `changed-bytes.txt` — original → patched, for review.

## Build

```
python3 patches/debug-overlay/build.py
```

The original ROM is never edited; the overlay goes in a copy.
After patching, `tools/checksum.py fix-all` fixes the runtime
checksum immediate at `0xFD098` first, then the header checksum at
`0x18E`. (Fixing only the header checksum will NOT boot: the runtime
self-test at `0xFD07C` hangs at `0xFD0CA` on mismatch.)
