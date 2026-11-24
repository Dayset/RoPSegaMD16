# Terrain-stream decoding — `$E358` nibble semantics (#276)

All 944 terrain streams are classified and terminate correctly
(`tools/terrain_stream_check.py`: family 1 176/176, family 2
768/768 terminate at `0x00`; the 944-entry `$5F524` offset table
tiles `$603E4–$9611F` exactly, including `0x068300–0x093FFF` and
`0x094000–0x09611F` — 8,480 B, not 8,608 B). This page records what
each nibble of a stream byte means in game terms, traced through
`map_terrain_tile_lookup` (`$E358`, `disasm/src/rop.s` ~lines
2421–2620).

## Stream selection

- A stream is selected by index via the offset table `$5F524`[index]
  + base `$603E4`.
- Callers of `$E358`: `$01BC1A` / `$01BC3C` / `$01BC84` (in `$1BA4E`,
  the map-cell renderer — passes stream index 560 (`$230`) or the
  secondary index 559–590 from `$01BB82`, and a direction flag),
  and `$23234` / `$2326C` / `$2329E` / `$232C6` / `$23346` /
  `$233A6` / `$2342C` (in the `$231D8` dispatch handlers).

## The byte: `[hi:4][lo:4]`

The opcode byte itself is pure control — it is never stamped as
pixels. The handler it dispatches to stamps the *following* stream
bytes as pixel data.

### Hi nibble

- **In the row-skip prologue** (d1 < 0): hi = the number of bytes to
  skip per row.
- **In the draw loop:** hi = the high 4 bits of the `$DF58` dispatch
  index, i.e. the handler group. **Hi = the byte count the handler
  stamps**: hi=1 stamps 1 byte, hi=2 stamps 2, …, hi=E stamps 14.
  hi=0 and hi=F groups are all loop heads — those opcode bytes draw
  nothing (0 bytes stamped).
- Measured census of the 112 `FUN_` handlers in the `$DF58` table
  (bytes stamped, forward variants): hi=1→1, 2→2, 3→3, 4→4, 5→5,
  6→6, 7→7, 8→8, 9→9, A→10, B→11, C→12, D→13, E→14.

### Lo nibble

- `lo*2 + d0` (d0 = caller x-offset bits) indexes the `$435C0`
  word table (144 words, `$435C0–$436DF`; word[i] =
  `(i>>2)*32 + (i&3)`), giving the destination row/col in the
  32-byte-wide output bitmap at `$FF1EC0`.
- Lo bits 0–1 (mixed with the caller x-offset via
  `(2*lo+d0) & 6`) select 1 of 4 draw shapes per hi-group; lo bits
  2–3 shift the `$435C0` lookup (destination row +1/+2).
- The dispatch index is X = `(hi<<4) | ((2*lo+d0)&6) | dir`,
  dir = 0 forward (`$E3E2` loop) / 1 reverse (`$E43C` loop). The
  `$DF58` table is 256 entries (`$DF58–$E354`): 144 loop heads (72×
  `$E3E2`, 72× `$E43C`) + 112 distinct `FUN_` draw handlers. Per
  hi-group, v=0..7 are the 8 real handlers (4 forward + 4 reverse);
  v=8..15 are all loop heads and unreachable (X's low 3 bits max 7).
- Within a hi-group the 4 forward variants differ in how the N
  stamped bytes are laid out across rows (0–4 `adda.w #$1D,a5` row
  jumps; e.g. the hi=E v=0 handler stamps 4+4+4+2 bytes over 4 rows).
  The 4 reverse variants mirror them with `suba.w #$1D,a5` (up rows
  instead of down). For hi=1 the four variants are byte-identical
  code — lo bits 0–1 are functionally inert there (only the
  `$435C0` destination still differs).
- Modal stream byte is `0xDD` (hi=D group, lo=D variant; family-2
  lo-histogram: lo=13 has 25,123 occurrences).

## Pixel stamping

- Mask table `$433C0` (256 B): `0xFF` if the byte == 0
  (transparent), `0xF0` if hi == 0, `0x0F` if lo == 0, `0x00` if
  both nibbles nonzero. Result = `(old & mask) | byte` — each
  stamped byte writes two 4-bpp pixels.
- Reverse path remaps each byte first through `$434C0`, which is a
  nibble-swap table (`$434C0[b] = swap_nibbles(b)`).
- Row offsets `$436E0` (184 words): `t[i] = (i//8)*0x480 + (i%8)*4`
  (verified for all 184).
- Handler shapes: 1×1 (`FUN_00f6f8`), 1×2 (`FUN_00f694`), 2×1
  vertical with `+$1D` stride (`FUN_00f6dc`), 4-row blocks
  (`FUN_00e47c`, 14 bytes), etc.

## Residual unknown

Which hi-group shape corresponds to which visual terrain feature
(grass edge, cliff, waterline, …) — that needs rendering the
decoded bitmaps to images and matching them against the game's
maps, which this trace did not do. The nibble-field mapping above
is complete; the visual labelling is the remaining step.
