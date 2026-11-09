# disasm/src/ — planned layout (issue #012)

Decided 2026-11-09 (agent session) from `disasm/map.md` ranges and
the #011 seed map in `disasm/ghidra/function_map.csv`. **No .s files
exist yet** — emission is blocked on #011 (verified function
boundaries) and on the ROM being present (incbin slices must be
copied verbatim, never hand-typed: #012 acceptance).

| File | ROM range | Contents |
|---|---|---|
| `main.s` | — | `org 0`, `.include` chain in address order, nothing else |
| `vectors.s` | `0x000000–0x0001FF` | Vector table (only SSP/reset/L4/L6 non-zero — keep the zeros, they are behaviour) + header (checksum field left for `checksum.py fix-all`) |
| `entry.s` | `0x000200–0x0012FF` | Verified entry, `$28E` VDP table as data, VBlank `0x1272`, HBlank `0x1270`, `$1350`, `$3AA` |
| `game_a.s` … | `0x001300–0x043FFF` | Labelled code, split per #011 function map (one file per subsystem once boundaries are proven: menu/verbs, shops, combat, spells) |
| `data_044000.inc` | `0x044000–0x05FFFF` | incbin — high-entropy block; prime suspect for the terrain-decoder stream (#020); NOT decoded |
| `data_060000.inc` | `0x060000–0x093FFF` | incbin — start of the `$96120` compressed streams (`0x09638C–…` sources begin in the next range; this range is compressed data, **not** raw tiles — #005 correction) |
| `gfx_tables.s` | `0x094000–0x0CBFFF` | `$96120` (62 recs) + `$B86AE` (90 recs) tables as labelled incbin slices so record labels survive |
| `tables_cc000.s` | `0x0CC000–0x0D7FFF` | incbin — palettes `0x0CC9D8`, verb table `0xCCDB8`, names `$CD431`, price tables `$D66A6`/`$D6768`, rank tables `$D6B6C…` (labels as equates in `labels.s`) |
| `text.s` | `0x0D6EBA–0x0DC0C0` + streams | Dictionary blob incbin + `$DDBD8` records incbin |
| `game_b.s` … | `0x0E0000–0x0FBFFF` | Mixed code/data per #011; sound cluster `$EB772…` labelled first (verified, #003) |
| `checksum.s` | `0x0FC000–0x0FD0CB` | Tail code + runtime checksum `$FD07C` (immediate at `0xFD098` left for fix-all) |
| `padding.inc` | `0x0FD0CC–0x0FFFFF` | 12,084 bytes of `0xFF` — `.fill`, not incbin (it is also where patches/harnesses live) |
| `labels.s` | — | RAM (`$FFxxxx`) and hardware (`$Axxxxx`/`$Cxxxxx`) equates only |

Rules carried from the issues: data = incbin with start/end recorded
in a comment on the directive line; labels for every vector-reached
routine in `function_map.csv`; the linear sweep `disasm/rop.s` is
never copied into this tree. `tools/split_disasm.py` prints this
split from `disasm/map.md` and refuses to emit files until the
#011 map + ROM are present.
