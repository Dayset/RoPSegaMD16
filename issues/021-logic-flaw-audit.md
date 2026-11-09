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



## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/logic-audit.md — the full audit: all tables located (§1); every docs/overview.md audit question answered or explicitly left open with its owed experiment (§2: save-sum weak-by-design, XP/gold overflow verdicts, joypad drop/debounce mechanism proven, the PROVEN divide-by-zero hazard via $FF0E18[2], dead-code inventory); debug-mode evidence assembled (§3); ten proven flaws F1-F10 tabled (§4).
- **Acceptance:** MET: tables item; audit written to docs/logic-audit.md; most overview questions answered with address + repo evidence. PARTIAL: debug-mode reachability NOT decided (no xref traced; verb menus contain no Diags entry); live-combat path, save corruption matrix, Bribe action, food/water routine, Void-message trigger remain open — each needs ROM/BlastEm traces itemised in the doc §5. No claim was closed on inference.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation)

- PAR/Gens RAM codes from #033 cross-verified against the repo
  struct: all six per-character blocks land exactly on the
  $FF02B4/0x34 grid at +0x1A/+0x1C/+0x1E (docs/logic-audit.md §6).
  Mortimer vs Obliky assignment NOT resolved — hypothesis
  (FF05DA=Mortimer) recorded as low-confidence with the decisive
  live experiment named. Money code = slot-0 +0x2A with the exact
  gold-cap value; Food/Water at $FFC364/366 unverified.
- Game Genie codes decoded (new tools/decode_gamegenie.py):
  master code R1JA-86Y6 = 0xFD09C:0x4E75, replacing the checksum
  routine's `bne` with `rts` — the bypass, verified against the
  ROM. All other codes land in the unmapped 0x9C00-0xA500 block;
  two fan-list anomalies pinned (docs/research/game-genie-decoded.md).

## Update 2026-11-09 (continuation) — BRIBE + FOOD/WATER TRACED

- **Bribe: LOCATED.** Executor case at 0x20466–0x204C6 in
  $1F296: gate $1E49A($FF0E18)==0, gold ≥ 10 check, −10 gold
  via $2BBD2(1, −10, 0x400, leader), attitude effect via
  $2A22A(8, 0, leader) + $298D2. Full trace in
  docs/logic-audit.md §7.1. (docs/logic.md's "not located"
  note is superseded.)
- **Food/water: honest negative for the named sites.**
  $FF0E16 is the world clock (mod-2400 tick counter in
  world_tick), not a provisions store; none of
  $2F1F0/$2FA2A/$302F0/$2EC80 consume food/water, and the
  $32C56 call in $2155E is a position lookup. Trace in
  docs/logic-audit.md §7.2. Remaining candidate named: the
  Camp verb case in $1F296 (not yet traced).
**Status stays in progress** — debug-mode reachability and
the live-combat/save-corruption items from §5 remain open.

## Update 2026-11-09 (session #3, ROM + BlastEm debugger) — CAMP, DEBUG MODE, SAVE MATRIX CLOSED

Full traces in docs/logic-audit.md §8.

- **Camp verb: TRACED.** Executor C-code dispatch (at
  $2068E) enumerated — Camp is C=$1C → case 0x204CE →
  $3019A(0). Camp: 1/3-chance random encounter spawn
  ($32D4C), $FF00C0 table pass, world clock set to the
  next 540/0 boundary, **Food −100 / Water −100**, party
  heal ¼ of missing HP/Power. The $2BBD2 item path calls
  $3019A(1): message + ½ heal, no provisions/clock cost.
- **Food/water: RESOLVED (the §5 item-4 lead was Camp).**
  The consumption routine is in $3019A at
  0x30346–0x303B4, decrementing $FFC364/$FFC366 by 100
  per Camp, clamped [1, 30000] — the fan PAR addresses
  and their 0x7530 value are confirmed as the live
  stores/clamp max. §7.2's 0x302F0 "clamp pass" is Camp's
  own clock-set block (corrected in §8.1).
- **Debug mode: REACHABILITY DECIDED.** The Diags toggle
  is executor case C=$37 at 0x205BC (flag $FF0134); the
  options panel $26E44 draws "Diags On/Off" from it
  (state 8, strings $27548/$27551 — the $2752A xref the
  audit owed is the pea at 0x26F28 and siblings); the flag
  changes input decoding in $12FE8 (rejected pad nibbles
  decode as directions only when ON) and persists via
  $2F11A/$2F896. Live value at a fresh boot: $FFFF (ON by
  default, from the ROM RAM-init image). The $26E44 call
  branch was observed live in the attract loop
  (advance-to 0x1B9AA stop). The format string $023934
  has NO reference anywhere in the ROM — the sprintf
  overlay is not evidenced in shipped code. Verdict:
  **the setting is reachable and functional; the overlay
  is inert.** (Forcing the state-8 page under the debugger
  was blocked by a tool limit — BlastEm 0.6.3.4's `se`
  rejects memory destinations; recorded in §8.4.)
- **Save corruption matrix: RUN (Q1 closed).** $4323C's
  check fully decoded (S = sum of bytes 0..125 mod 256;
  stored pair must be S / ~S). Debugger d1 readbacks on
  crafted EEPROM images (scratch files only): blank = 3
  (rejected), forged pair = **0 (accepted)**, 1-byte
  flip = 2 (detected), compensating pair = **0 (NOT
  detected)**. The checksum is proven forgeable.
- **Live combat: attract negative.** Breakpoints at
  $3A842/$3B094/$3B1EE/$40880 armed power-on → intro →
  main loop: zero hits. F9's live half still needs driven
  gameplay (no input driver in this setup).

**Status stays in progress.** Remaining: Q5 (Void-message
trigger), live-combat items (F5/F9 live halves), F2's
either/or, F7's caller proof, Doggonia fee, item-record
+4..+9 bytes, $FF012C live mapping, party-name writes,
the (A,B,grp) executor-dispatch half, post-harness PC=0.
All need driven gameplay or deeper static work — itemised
in docs/logic-audit.md §5.

## Update 2026-11-09 (session #4, LIVE GAMEPLAY — input driver built)

Full write-up: docs/logic-audit.md §9; screenshots in
docs/logic-audit-evidence/; driver recipe in
docs/toolchain-vm.md (BlastEm input-driver section).

- **Input driver: BUILT (route (a)).** xdotool under Xvfb
  drove the full game twice (title → new game → overworld →
  town/menus/dialogue → Camps → two battles). Route (b)
  (RAM pad injection) was not needed; the debugger was used
  alongside via the `u` key on the same PTY.
- **Live combat: CLOSED (§5 item 1).** Breakpoint stops at
  $3B1EE in the Evin fight read return address 0x3A846
  three times running — **the live caller is $3A842 in
  $3A62E**; $3B094 and $40880 never fired. Battle won:
  +6 XP, +20 gold (all values debugger/HUD-verified).
- **F5: REFUTED for non-level-up grants** — Buc ended at
  HP 7/20 after the +6 XP grant. Level-up half untested.
- **F9: dispatch half answered** (path above; args
  3, 1, 0xB, $FFFF, a0 = slot 5 recorded). Field-writing
  half still open.
- **Debug mode: runtime-closed** — SYSTEM panel drawn
  live ("DIAGS: ON"), toggled OFF/ON via the menu with
  $FF0134 reading 0 then 1 in the debugger (the §8.2
  set-1), HELP toggled too.
- **Camp: live-confirmed §8.1** — controlled Camp measured
  Food/Water at exactly −100 each; clock set to the 0/540
  boundaries exactly. NEW sub-item: provisions also drain
  outside Camp over travel/time (totals exceed Camp's
  accounting in both long intervals); mechanism unfound.
- **Q5: trigger ANSWERED** — the Void dream ("You DREAM
  OF THE DEMON VOID…") is a Camp rest event; fired once
  (first sleep-until-dawn camp), absent in 3 other camps.
  The message-id xref / timer half remains static work.
- **Beggar event (incidental):** YES = −50 gold exactly
  (observed twice, 1000→900); NO = the beggar (Evin)
  attacks. Buc = slot 1 verified from the live side
  (XP landed at $FF0302 — §6's fan-PAR slot).
- **Pad-2 teleport: inconclusive** (combo sent via
  config bindings; no relocation observed; bindings
  themselves unverified).

**Status stays in progress.** Remaining: F2, F7 caller,
Doggonia fee, $FF012C live, Bribe live, F5 level-up half,
extra provision drain, Q5 xref, party-name writes,
(A,B,grp) dispatch, post-harness PC=0.

## Update 2026-11-09 (session #5, LIVE GAMEPLAY II) — drain solved, F5 closed, pad-2/teleport proven in code

Full write-up: docs/logic-audit.md §10; evidence:
docs/logic-audit-evidence/s5-*.png.

- **Extra provision drain (§9.2 unknown): SOLVED.** It is a
  per-step movement cost in the entity step handler
  FUN_00024984 (store at 0x24F78, gated $FF00AE==1):
  measured Food −3 / Water −1 per step on grassland
  (breakpoint-caught, amounts = the step record's
  +0x26/+0x28 locals exactly, clamps [1, 30000]); 60 s
  idle moved the clock +300 ticks with zero drain — not
  clock-driven, not per-member.
- **F5 level-up half: DECIDED — refuted.** A real Evin
  victory (6 XP) with the stored total raised to 101 at
  the $2C4E2 store (one register edit, method stated in
  §10.2): max HP recomputed 20 → 35, current HP 4 → 4.
  No grant of either kind heals current HP/Power; F5 is
  closed as refuted, maxima-recompute is the true half.
- **Pad-2 teleport: mechanism proven, bindings proven,
  execution conditions not met.** Bit encoding derived
  from $DCE2 (bit7 Start, bit6 A, bit5 C, bit4 B — the
  save-validation.md §2 A/B labels are swapped; erratum
  in §10.3). Bindings runtime-proven three ways ($FF8646
  latched $E0; boot hold → $FF0168=1 clear-save path;
  over-long hold → 0x4333A blackout). The cheat itself
  is code-located: Map verb → FUN_0002DCCE (gate: Map
  item + outside — refusal message observed live) →
  map screen FUN_0001664E cmp $FF8646 #$E0 at 0x16C72 →
  $3081A with the highlight's coordinates. No Map item
  was obtained in-session (Mind reached, no shop
  transaction completed), so the final keypress is
  still unexecuted — "conditions not met", not false.
  Bonus code finds: map-screen $A5 combo (Start+C+Left+
  Up → leader HP/Power maxima 140/9000) and the intro
  $FA combo (Down+Right+A+B+C+Start, FUN_000123B0) =
  the fan "Topples Lady" cheat.

**Status stays in progress.** Remaining: F2, F7 caller,
Doggonia fee, $FF012C live, Bribe live, Q5 xref,
party-name writes, (A,B,grp) dispatch, post-harness
PC=0, teleport/$A5 live execution.

## Update 2026-11-09 (session #6, LIVE GAMEPLAY III) — PAD-2 TELEPORT EXECUTED

Full write-up: docs/logic-audit.md §11; evidence:
docs/logic-audit-evidence/s6-*.png.

- **Pad-2 teleport: EXECUTED end-to-end — the fan
  cheat is TRUE.** Map screen (FUN_0001664E) open with
  its conditions satisfied, highlight panned to the
  east coast, pad-2 A+C+Start held: the debugger
  stopped at the armed **$3081A breakpoint** with
  return address **$16CAE** (the map screen's own
  `jsr $3081A` at 0x16CA8) and stack arguments
  **X=171, Y=125**; the leader's position moved
  **(111, 125) → (171, 125)** via $2570A, and exiting
  the map screen showed the east-coast shore in the
  overworld. §10.3's "execution outstanding" is
  closed.
- **The Map was GRANTED, not shop-bought — labelled
  plainly.** The purchase was attempted in earnest
  first (two fresh drives into Mind; Academy, harbour,
  warehouse and residential districts explored; no
  BUY menu ever reached; three deaths). The shop
  category rule was pinned statically meanwhile (NPC
  +0x17 byte vs item-record code at $D66A2+i·10, gated
  on +0x25 > 0, init at 0x2A48A; Map = category 13,
  slot 6). Because this BlastEm build's debugger
  cannot write RAM at all (§8.4), the grant was made
  in the scratch ROM copy only: init immediate at
  0x2CE3D $01 → $41 (`move.b #$41, $FFC340` — bit 6 =
  Map, alongside the stock bit 0 = So Sym), checksums
  re-fixed on the scratch copy; live RAM read back
  $FFC340 = $4100 and INVEN lists the Map. The repo
  ROM is byte-untouched. A genuine shop purchase of
  the Map remains uncompleted and is recorded as an
  open sub-item, not smoothed over.
- **$A5 god-mode combo: still not live-verified**
  (Buc died to a destination encounter — Scourge +
  Knight + Priest — before a second map-screen visit).

**Status stays in progress.** Remaining: F2, F7 caller,
Doggonia fee, $FF012C live, Bribe live, Q5 xref,
party-name writes, (A,B,grp) dispatch, post-harness
PC=0, $A5 live, a genuine Map shop purchase.
## Result (2026-11-09)
- `docs/logic-audit.md` written. Verdicts: gold overflow PROVEN +
  reproduced (15000+17768 -> 0, boundary at 32768); negative damage
  heals PROVEN + reproduced (HP 100 -> 106); save checksum WEAK and
  its result never read; debug mode IS reachable, format string dead;
  Void trigger NOT located; `$12072` spin loop solved (harness
  artifact); giant-function dispatch mapped; `$2B240` solves the
  +0x1E/+0x22 puzzle; `$1E0A4` = opposite-direction map; `$1F296` +
  `$12FE8` command maps done (command 23 writer not found); terrain
  decoder source ~0x60400+ (0x044000-0x05FFFF killed); food/water
  routine NOT located (leads killed); DoT drains stack (-10/round +
  1 HP 1/3 chance); `$1350` pop semantics reproduced.
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
