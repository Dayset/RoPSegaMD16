# Ghidra recursive analysis (issue #011, 2026-11-09)

Ghidra 11.4.2, project `tools/ghidra/projects/rop` (program
`rop-ghidra.bin`), full auto-analysis re-run, then manual creation of
the functions the analyser missed. Full OpenJDK 21 required
(`JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`).

## Results

- **446 functions, 1,449 direct call edges.** The auto-analysis found
  435; **11 were created manually** in this issue (see below).
- **405 functions (91%) are reachable from entry `0x200`** by direct
  call edges. The other 41 are vector targets, the VBlank/sound
  cluster, or functions reached only via computed dispatch
  (`not_reachable_from_entry.txt`).
- Coverage is measured on **exact function-body addresses**
  (`function_bodies.txt`), not spans — 54 functions have
  non-contiguous bodies (jump tables and shared tails split them),
  so span-based coverage would overstate it.

## Coverage by region (exact body addresses)

| Range | Code bytes | % | Verdict |
|---|---|---|---|
| `0x000000–0x00FFFF` | 6,890 / 65,536 | 10.5% | Code in `0x000200–0x001393` + `0x00D25C–0x00FFFF` (47 functions); the `0x001394–0x00D25B` gap (48,840 B) is binary tables — 156 data references from code, no call targets |
| `0x010000–0x043FFF` | 193,264 / 212,992 | 90.7% | Code, with 16 gaps ≥64 B (18,612 B) — all data except the `$1E022` case blocks (see below) |
| `0x044000–0x05FFFF` | 0 | 0.0% | Data (compressed block) |
| `0x060000–0x093FFF` | 0 | 0.0% | Data (compressed streams, #005/#006) |
| `0x094000–0x0CBFFF` | 0 | 0.0% | Data (compressed block) |
| `0x0CC000–0x0D7FFF` | 0 | 0.0% | Data (tables + dialogue blob) |
| `0x0D8000–0x0DFFFF` | 0 | 0.0% | Data (dialogue blob + tables) |
| `0x0E0000–0x0FBFFF` | 984 / 114,688 | 0.9% | Sound cluster only; the rest is data (see below) |
| `0x0FC000–0x0FFFFF` | 80 / 16,384 | 0.5% | Checksum routine (`$FD07C`, 80 B) + `0xFF` padding |

## Gaps in `0x010000–0x043FFF` (16, ≥64 B) — every one classified

All have **zero** direct call/branch targets from real code
(Capstone target cross-check — the only genuine missed target in the
whole ROM was `$EBA00`, fixed below). Data references are literal
immediates (`lea`/`pea`/`move.l #`) in real (Ghidra-covered) code.

| Gap | Size | Verdict | Evidence |
|---|---|---|---|
| `0x010000–0x011073` | 4,212 B | Data (table, unclassified) | Regular 8-byte repeating records; the one apparent reference (`move.l #$10000,d1` at `0x16D48`) is arithmetic (`d1 = 0x10000 − d0`), not a pointer |
| `0x01215E–0x01225B` | 254 B | Data (Void string) | Void death message text; `pea $1215E(pc)` from `$12072`'s tail at `0x120F2` |
| `0x015BB8–0x015C07` | 80 B | Data (menu words) | `Continue`/`Start`/`Intro`/`Citizens`/`Credits`; 6 data references |
| `0x0197B0–0x01B5D5` | 7,718 B | Data (string/table block) | Class names (`Sorcerer`, `Knight`, …), `0x1A71C+` strings, `0x1B324` credits; 48 data references |
| `0x01D73E–0x01D783` | 70 B | Data (binary table) | 1 data reference |
| `0x01E02E–0x01E075` | 72 B | **Code** — `$1E022` jump-table case blocks | Four regular 18-byte blocks (`movea.l $A(a6),a0` + word write + `bra $1E0A0`); disassembled in this issue, not function entries (no `link` prologue; reached via the jump table) |
| `0x023938–0x023A9D` | 358 B | Format strings + **code** | `"Sp:%i …"` string ($023938–$023957) and `"%02i"`/`"\n"` strings ($023A90–$023A9D); the middle 312 B ($023958–$023A8F) are the carved `map_grid_dump` routine (two nested 32×32 loops dumping the $FFB36C/$FFB76C cell grids via `$01107A`), uncalled. The "Data (format strings)" label was stale — corrected 2026-11-11. |
| `0x027522–0x0275AF` | 142 B | Data (menu strings) | `Help On/Off`, `Direct:`, `Lefty`/`Righty`, `Diags On/Off`; 21 data references |
| `0x029370–0x029799` | 1,066 B | Data (message strings) | XP/gold/shop/spell-effect messages; 98 data references |
| `0x0317E2–0x0318C5` | 228 B | Data (message strings) | `Search report sir:` etc.; 37 data references |
| `0x033396–0x0334D5` | 320 B | Data (binary table) | 1 data reference |
| `0x038A40–0x038A87` | 72 B | Data (binary table) | 1 data reference |
| `0x03A062–0x03A227` | 454 B | Data (word table) | Table base `$3A220`, read by `move.w $3A220(pc,d0.w),d0` at `0x3A232` |
| `0x03A2E4–0x03A35B` | 120 B | Data (word table) | Table base `$3A354`, read at `0x3A366` |
| `0x03A4A2–0x03A5D7` | 310 B | Data (word table) | Table base `$3A5D0`, read at `0x3A5E2` |
| `0x0433C0–0x043FFF` | 3,136 B | Data (terrain-decoder tables) | `$433C0` masks, `$435C0` nibble expansion, `$436E0` tile offsets (#020); 5 data references incl. the decoder's own `lea` |

Smaller gaps (<64 B) are jump tables and data words Ghidra correctly
excludes from function bodies — e.g. `$12FE8`'s tables at
`0x13052`/`0x13078`/`0x130D8`/`0x130FE`, `$1E0A4`'s table at `0x1E0C6`,
`$3B51E`'s table at `0x3B6A0` — plus two more missed case blocks
disassembled here (not entries): `0x38850–0x38889` (spell-area case
block, branches to `$387F6`/`$3884A`) and `0xEB9A0–0xEB9C3`
(sound-cluster blocks, branch to `$EB972`/`$EB978`).

## Gaps in `0x0E0000–0x0FBFFF` (2)

| Gap | Size | Verdict | Evidence |
|---|---|---|---|
| `0x0E0000–0x0EB771` | 46,962 B | Data (structured table, unclassified) | Regular 8-byte records (`0x8Bxx` offsets + small lengths); one interior address (`0xE0A18`) pushed as a pointer by `pea.l $E0A18.l` at `0x32EBE`; Capstone decode is incoherent (repetitive `ori.b` garbage); no call targets. Song/SFX data is the leading hypothesis — #018's work, not claimed here |
| `0x0EBB6E–0x0FBFFF` | 66,706 B | Data (Z80 driver blob + rest) | Z80 driver blob `0xEBB6E–0xED0E4` (`$1576` bytes, 19 data references incl. the `$EB806` upload); the remaining `0xED0E4–0xFBFFF` is unclassified ROM data (no functions, no call targets); `SHayes1991` signature string inside |

## Functions Ghidra missed (created manually in this issue)

Recursive analysis only follows direct calls and vector targets. Code
reached only via computed dispatch (jump tables, `$2BBD2` dispatch,
function pointers) or with no callers at all is invisible to it.
Eleven functions were created by hand (disassemble + create, same
pattern as `tools/ghidra_011_create_funcs_*.py`):

| Address | Size | Why missed | Evidence it is code |
|---|---|---|---|
| `0x1270` | 2 B | Vector target, no call sites | HBlank handler, single `rte` |
| `0x1272` | 216 B | Vector target, no call sites | VBlank handler; matches the verified trace `0x1272–0x134E` |
| `0xEB772` | 86 B | No call sites (called only from the VBlank handler) | Sound tick; matches the verified trace `0xEB772–0xEB7C6`, `rts` at `0xEB7C6` |
| `0xEBA00` | 126 B | `jsr $EBA00` at `0xEB7BE` was in Ghidra's listing but the analyser never followed it to create the callee | Music streamer; clean decode ending `rts` at `0xEBA7C`; matches the #003 trace (called every 16 frames from `$EB772`) |
| `0xEB7C8` | 62 B | Zero callers (dead code in the original) | Stop-sound; clean decode ending `rts` at `0xEB804`; revived by the music-off patch |
| `0xEB8E0` | 18 B | No callers | 3-byte store helper, ends `rts` at `0xEB8F0` |
| `0x2B2B2` | 336 B | No direct callers | Combatant-setup wrapper 2 (`link` prologue, calls `$243D6`/`$258EE`/`$23B84`, falls through into the `$2B3B0` field-write block) |
| `0x2B502` | 242 B | No direct callers | Combatant-setup wrapper 4 (same shape; calls `$243D6`/`$1E022`/`$258EE`/`$23B84`, falls through into the `$2B5B0` block) |
| `0x2988E` | 68 B | No direct callers | Counter loop calling `$2979A`; `link`/`unlk`/`rts` |
| `0x3536C` | 46 B | No direct callers (computed dispatch) | Predicate routine (compares args>>2, returns 0/1); `link`/`unlk`/`rts` |
| `0x3539A` | 266 B | No direct callers (computed dispatch) | Calls `$1E022`, reads struct tables `$FF02C0`/`$FF02C2`; `link` prologue |

Note: `$2B3B0`/`$2B5B0` are **not** entries — they are mid-routine
labels reached only by fall-through from the `$2B2B2`/`$2B502`
wrappers (the `$2B240` family shares one frame). No function was
created there; the wrappers cover them. The same applies to the
`$1E022`/`$38850`/`$EB9A0` case blocks above (disassembled, not
functions).

Ghidra also **merges** distinct routines into one function where flow
connects them: `$2B240` lives inside `FUN_0002b190` (its wrapper),
`$2B4B0` inside `FUN_0002b402`, `$35600` inside `FUN_000354a4`.
Those are flow-correct merges, not errors — the linear sweep's
labels (`$2B240`, `$35600`, …) are entry points inside the merged
bodies.

## Cross-check: Capstone direct targets vs Ghidra

All 289 distinct absolute-`jsr` targets in the linear sweep
(`disasm/rop.s`, 3,143 absolute `jsr` sites) were compared against
the Ghidra bodies: **all 289 are function entries**, and all 289
appear among Ghidra's 413 distinct callees (1,449 edges, whose
callees are all entries too — the PC-relative `jsr` forms resolve
to the same entries). The one genuine missed target was `$EBA00`
(`jsr $EBA00(pc)` at `0xEB7BE`, inside `$EB772`'s body) — created
manually above, so the count is now 289/289. The linear sweep also
decodes garbage `jsr`-looking instructions in the compressed blocks
(`0x044000–0x0CBFFF`), but those use register-indirect or
displacement forms (`jsr $55E50(pc)`, `jsr $AB08C(pc,d0.l)`), not
absolute targets, and contribute no absolute targets to the count.
**Where Ghidra and the linear sweep disagree, Ghidra wins** — except
for the computed-dispatch code above, where the Capstone decode +
the #007/#008/#020/#021 traces are the evidence and Ghidra's
silence is the limitation.

## Call trees (`call_trees.txt`)

- **Entry `0x200`: 405 functions.** Depth 1 is exactly the verified
  trace: `$3AA`, `$4E6`, `$A14`, `$119E`, `$4323C`, `$FD07C`. Depth 3
  holds the seven `$D25C` callees (`$11E06`, `$14FB6`, `$1B5D6`,
  `$32D0E`, `$173BC`, `$D28E`, `$179B6`) — agreeing with #020.
- **VBlank `0x1272`: 10 functions.** `0x1272 → $EB772 → {$EBA00,
  $EBAC6} → {$EB922, $EB92A, $EBAFE, $EBB04} → {$EB806, $EB920}` —
  agreeing with the verified trace (sound tick + music streamer every
  16 frames + command-queue dispatcher).
- **Save `$4323C`: 14 functions.** `$4323C → {$DCE2, $42FC8,
  $43012, $430F4} → {$DCCA, $42E34, $42E76, $42EBA, $42EEE, $42F26,
  $42F5E, $42F96, $42FD8}` — agreeing with docs/architecture.md; the
  four depth-2 helpers `$DCCA`/`$42F26`/`$42F5E`/`$42FD8` are in
  Ghidra's tree but not named in the doc.
- **Sound `$EB772`: 9 functions** (the VBlank tree minus the handler).

## Files

- `functions.txt` — 446 functions: entry, end, name.
- `call_edges.txt` — 1,449 direct call edges.
- `function_bodies.txt` — exact body address ranges (one `RANGE`
  line per contiguous range; `MULTI` lines flag non-contiguous
  bodies).
- `call_trees.txt` — the four BFS trees above.
- `not_reachable_from_entry.txt` — the 41 functions no direct call
  edge reaches from entry (vectors, sound cluster, computed dispatch).

## Reproducing

Headless runs (from the repo root, full JDK 21):

```
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
tools/ghidra/ghidra_11.4.2_PUBLIC/support/analyzeHeadless \
  tools/ghidra/projects rop -process rop-ghidra.bin \
  -scriptPath tools/ghidra -postScript "DumpFunctions011.py"
```

Scripts (preserved copies under `tools/`):
`tools/ghidra_011_dump_functions.py`, `tools/ghidra_011_dump_bodies.py`,
`tools/ghidra_011_dump_listing.py`, `tools/ghidra_011_create_funcs_b.py`,
`tools/ghidra_011_create_funcs_c.py`, `tools/ghidra_011_create_funcs_d.py`,
`tools/ghidra_011_probe.py`. (`tools/ghidra/` itself is git-ignored —
it holds the Ghidra install — so the scripts live in `tools/` and the
exports live here.)

Note: the VM was replaced mid-issue (2026-11-09) and `/tmp` was wiped
along with the system JDK. The JDK was reinstalled (`openjdk-21-jdk`,
21.0.12.1) and all dumps re-generated from the project after the
wipe; the project itself (`tools/ghidra/projects/rop`) survived in
the workspace with all 11 manual functions intact.
