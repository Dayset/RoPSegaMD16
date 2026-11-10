# Issue #021 — Combat / XP / gold / spell tables + logic-flaw audit

**Epic 2**  
**Milestone:** M4  
**Status:** done (2026-11-09)

## Goal
Map the numbers behind the game and audit them for logic flaws.

## Acceptance
- [x] XP table, level-up, gold/shop, combat damage, spell tables located
- [x] Each `docs/overview.md` audit question answered with an address +
      a trace: proven, or killed with evidence
- [x] Debug mode (`Diags On/Off`, format string `0x023934`) reachability decided
- [x] Audit written to `docs/logic-audit.md` — no claim without evidence

## Notes
- Depends on #007, #008, #020. A suspected flaw is not a finding until
  it is reproduced.


## Result (2026-11-09)
- `docs/logic-audit.md` written. Verdicts: gold overflow PROVEN +
  reproduced (15000+17768 -> 0, boundary at 32768); negative damage
  heals PROVEN + reproduced (HP 100 -> 106); save checksum WEAK and
  its result never read; debug mode IS reachable, format string dead;
  Void trigger NOT located; `$12072` spin loop solved (harness
  artifact); giant-function dispatch mapped; `$2B240` solves the
  +0x1E/+0x22 puzzle; `$1E0A4` = opposite-direction map; `$1F296` +
  `$12FE8` command maps done; **command 23 writer resolved 2026-11-10
  — there is none (dead dispatch case, see below)**; terrain
  decoder source ~0x60400+ (0x044000-0x05FFFF killed); food/water
  routine NOT located (leads killed); DoT drains stack (-10/round +
  1 HP 1/3 chance); `$1350` pop semantics reproduced.
- **Command 23 — resolved 2026-11-10 [static]: there is no writer; the
  `$D28E` switch case 23 is dead code.** The command byte lives at
  `$FF0240`. Its only writer is `$12FE8` (`0x12FE8–0x13650`), which
  builds a 4-byte record in its frame ([byte0 = command at `-$4(a6)`,
  byte1 = selection at `-$3(a6)`, word = -1 at `-$2(a6)`]) and copies
  it to `$FF0240` via `move.l (a1)+,(a0)+` at three exit sites
  (`$013154`, `$0131CC`, `$01363C`), returning `$FF0240` in d0;
  `$D28E` calls it at `$D3C0`, and again at `$D3D8` if the first call
  produced command 0, copying `$FF0240` back into its own frame
  `-$4(a6)`. Exhaustive enumeration of every immediate byte write to
  the command slot `-$4(a6)` in the whole disassembly gives 14
  distinct values — 0 (clr), 10, 20, 21,
  22, 24, 25, 30, 35, 37, 40, 45, 50, 55 — **never 23** (no
  `move.b #$17,-$4(a6)` exists anywhere). No register byte-write to
  `-$4(a6)` exists in `$12FE8`, no arithmetic on `-$4(a6)` exists
  anywhere, and all 6 `$FF0240` references in both disassembly files
  are the reset RAM-clear and the 6 `lea.l $ff0240.l,a0` sites inside
  `$12FE8` (no alternative address computation). `$D28E`'s own frame
  writes are only 10 (`$D328`) and 0 (`$D462`, `$D8BA`). The only
  "23" near the command production is `move.b #$17,-$3(a6)` at
  `$0135CC`, which writes 23 to the *selection* byte (`$FF0241`),
  not the command byte — and only when the selection index `$FFA7F8`
  is already 23 (a verb-table index), producing command 25. The
  handler `$1E5A0` is NOT dead: it reloads the current menu record
  from `$FFA7F8` (via `$FF01EA` offsets into the `$CCDB8` verb table),
  sets `$FFBB82`, and redraws unless the record's A byte is 'I'/'L'/
  'B' — called live from `$1B994` (in `$1B918`, world-map redraw),
  `$209FC` (in `$20884`, command-24 handler), `$20BBE` (in `$20A88`,
  command-25 area), and `$2D4E0` (in `$2D3DC`, called from `$2A188`
  and `$368D8`), all four after the same `$138A8` → `$FFB08A` →
  `$FF00AC` → `$1E5A0` (else `$26DD2`) pattern. So only the
  command-23 dispatch entry is dead, not the routine. No live run:
  the static enumeration covers all code paths exhaustively, so a
  live sample could only confirm a subset of it.
- Q13 SOLVED: post-harness PC=0 fault is a stack leak in the hook
  design (`jsr` + `jmp`, never `rts`) — the hook sits on the attract
  loop's VBlank spin, so the stack plummets into RAM in ~3 s. Fixed
  with `rts` in all three harness sources; fixed #007 harness still
  90/90 and runs 12 s clean. The #008 harness faults identically if
  left running (observation-window artifact, not immunity).
- Audit harness `tools/test_audit_harness.s`: 25/25 PASS.
- Corrections applied: EEPROM `$43012`/`$430F4` labels swapped
  (READ/WRITE), `$12FE8` "only 0 or 37" corrected, `docs/overview.md`
  audit list answered, `docs/logic.md` §7.3 resolved.
- ROM MD5 unchanged (`30c18fdbe2183f64702ae9f1a45d63f9`).
