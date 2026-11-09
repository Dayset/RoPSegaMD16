# Logic-flaw audit (issue #021)

Written 2026-11-09 (agent session, no ROM in VM) from the verified
findings in `docs/logic.md` (#007), `docs/spells.md` (#008) and
`docs/architecture.md` (#003/#020). **Every verdict cites the doc +
section that proved it.** Questions that still need a live trace are
marked OPEN with the exact experiment owed — they are not filled in
by inference. Tables (acceptance item 1) are in §1; the
`docs/overview.md` audit questions (item 2) in §2; the debug mode
(item 3) in §3; additional proven flaws found by #007/#008 in §4.

## 1. Tables located (acceptance item 1 — MET from #007/#008 evidence)

| System | Location | Form | Evidence |
|---|---|---|---|
| XP / level | `$2F030` + `$2F05A` | **No table — formula:** level = smallest L with XP < 100·2^L; max level **8**; XP cap 13000 (`0x2C4E2`) | logic.md §2.1, harness 90/90 |
| Max HP / Power | `$31958` / `$31946` | min(20+15·L, 140) / (L+1)·1000 | logic.md §2.2, harness |
| Battle-end XP/gold | routine at `0x35600` (`0x354A4`) | XP/person = total/party, clamped [1,50]; gold totals from `(rand19+11)·level`, `(rand7+5)·level` | logic.md §2.4 |
| Gold | struct `+0x2A`, handler `0x2C474` | cap 15000, floor 0 | logic.md §3.1/§3.2, harness |
| Item categories | `$D66A6` | 20 records × 10 B (record +4..+9 bytes still undecoded) | logic.md §3.3 |
| Prices | `$D6768` | 257 records × 4 B; scaling in `$2EA92` | logic.md §3.3/§3.4, harness |
| Combat damage | `$3B1EE` | formula, §2 Q4 / §4 F1 below | logic.md §5.1, harness |
| Spells (shop) | price records 1–120 | 6 blocks × 20, raw tiers 36→100 … 125→2900 | spells.md §1.2 |
| Spell effects | `$D6B6C…$D6DE2` via `$FFA7CC` | 6 distinct tables × 21 records × 6 B (ranks 7–10 reuse rank 2's table) | spells.md §2 |
| Spell cost | `$3C2C0` / `$37D0E` | cost = w4·(modifier+1)·3; out-of-power ⇒ HP −5 | spells.md §3, harness 44/44 |

## 2. The overview audit questions (acceptance item 2)

### Q1. Does the save checksum catch corruption? — PARTIALLY PROVEN
The check is a **byte-sum over 126 of the 128 EEPROM bytes with
NOT/swap variants; error count in d1, `d1==0` = valid**
(`docs/save-validation.md` §4, from architecture.md #003). That is
a weak presence/format check, not an integrity check: a plain sum
cannot detect transpositions or compensating byte pairs, so
*predictable patterns are accepted by construction*. The full
forgeability experiment (corruption matrix on a real save image)
is still owed — **needs ROM + BlastEm on the owner's machine**.
Verdict: **proven weak by design; exploitability OPEN.**
**Update (session #3): the matrix was run — §8.3. Exploitability
PROVEN: a forged image validates (d1=0) and a compensating
byte pair passes undetected. Q1 is closed.**

### Q2. Overflow in XP/gold/stats arithmetic? — PROVEN (mostly safe, two edges)
- XP: capped at 13000, floored at 0 in `0x2C4E2` — but the cap path
  uses `bls` and the floor path `bcc` on the sum, a signed/unsigned
  asymmetry "as written; reproduce exactly" (logic.md §2.3). Edge
  inputs near the sign boundary are **not harness-tested — OPEN**.
- Gold: hard cap 15000 / floor 0 in `0x2C474`, harness-proven at
  +20000/−20000 (logic.md §3.2). **No wrap.**
- Price: `$2EA92` clamps output to [2, 9000] on every path
  (logic.md §3.4). **No wrap reaches the shop.**
- Stats: max HP/Power are clamped formulas (§1). **No wrap found.**
- Spell cost: top spell at modifier 3 costs 12000 Power vs a
  9000 maximum — unreachable-by-design, feeding F4 below
  (spells.md §2.2).

### Q3. Joypad queue drops / debounce eating presses? — PROVEN behaviour, impact OPEN
Mechanism fully traced (architecture.md VBlank section): the
16-entry ring `$FF001C` **silently drops a byte when full**
(head+1 & $F == tail ⇒ not queued), and the 3-frame debounce
re-queues a *held* button once every 3 frames while a *changed*
byte resets the counter to 3. So: under faster-than-3-frame
alternating mashing, changed bytes reset the debounce before any
queue push — **presses can be eaten by design**; under held-button
play the queue receives ~20/s and the consumer (`$1350` pop, 16
call sites) drains per menu read, so overflow needs a stalled
consumer. Whether real play hits either case needs a live input
trace — **impact OPEN, mechanism PROVEN.**

### Q4. Combat/spell divide-by-zero, underflow, 0-stat edge cases? — PROVEN, the audit's biggest catch
- **Divide-by-zero hazard is REAL and proven by a harness freeze:**
  the message queue `$1E3B0`/`$1E426` divides by capacity byte
  `$FF0E18[2]`, which is 0 in cold RAM; the #007 harness froze
  exactly there (logic.md §2.7). #020 later found the initialiser —
  new-game init `$1B5D6` calls `$1E390($FF0E18, 8)` at `0x1B5DA` —
  so in normal flow capacity is 8 before any XP message. The hazard
  remains for any path that queues a message before new-game init,
  and the ROM has **no divide-by-zero handler** (vector 5 = 0).
- Damage formula edge cases: `$FF012C` codes `0x8E–0x92` force flat
  70 and `0x97` forces flat 5 regardless of stats (logic.md §5.1);
  immunity is `+0x02 == 0x4D` on either side; the rank-9/rank-7/8
  branches replace the computed damage with `(level+1)` /
  `(level+1)·2` — a rank-9 level-0 attacker does exactly 1 damage
  by formula. No unsigned underflow found in `$3B1EE` (the
  def-term is subtracted before the /3+1 normalisation).
- 0-HP handling: `$37B82` revives party member 0 with 1 HP when a
  slot 1–5 member is alive — death is **not** uniform across the
  party (logic.md §5.3).

### Q5. The Void death message / timer — OPEN
The Void message string exists (spaced string at `0x01215A`,
`disasm/map.md` text locations) but **no committed doc traces its
trigger or its "N seconds" timer**. #007/#008/#020 did not reach
it. Owed experiment: find the message's xref in the message routine
`0x275B0` region and trace the timer variable. Not guessed here.

### Q6. Unreachable code / dead routines — PROVEN, extensive
- `$EB7C8` stop-sound: **zero callers** in the original ROM
  (byte-search proven; `patches/music-off/README.md`). The music-off
  patch revives it.
- `$3A84C` damage-apply block in `$3A62E`: reachable only when
  attacker max HP (`+0x20`) < 0 — never for valid characters;
  confirmed dead (spells.md §4).
- Rank-table records 19 and 20 are identical in all six tables;
  record 20 is dead weight or a deliberate duplicate (spells.md §2.2).
- HBlank handler exists but can never fire (R0=`$04`); the blitter
  `$1194A`'s base-flip path looks inconsistent/dead (maps.md).
- The `$12B82` RNG sign-fix branch looks unreachable (AND clears
  carry, `bcc` always taken) — observed, not harness-verified
  (logic.md §2.5).
- Debug strings: see §3.

## 3. Debug mode (`Diags On/Off`, format string `0x023934`) — reachability OPEN, evidence assembled

- Strings exist in ROM: debug format `N^NuSp:%i Dir:%i Ac:%i St:%i
  Dr:%i` at `0x023934`; `Help Off` / `Diags On/Off` at `0x02752A`
  (`disasm/map.md`). They sit inside the menu/string region, i.e.
  they were **shipped in a menu or display path**, not stripped.
- The PARTY/MAIN verb tables (`disasm/main-loop/verb_menus.txt`)
  contain **no Diags/Debug entry** among MAIN/FIGHT/MOOD/PARTY/
  TACTIC/BUY/INVEN/USE — so if reachable, it is not via the normal
  verb menus traced in #020.
- No committed doc traces an xref to either string. **Verdict:
  reachability NOT decided.** Owed experiment (owner's machine):
  xref search for `0x023934`/`0x02752A` in the Ghidra project +
  the `$1F296` verb-executor case map (the executor's full switch
  is the other big #021 unknown, architecture.md #020 section).
- **Update (session #3): decided — §8.2.** The $2752A xref exists
  ($26E44 options panel, pea at 0x26F04/0x26F28 and siblings);
  the Diags toggle is executor case C=$37 at 0x205BC; the flag
  ($FF0134) is live in the input decoder and persists in saves.
  The $023934 format string itself has no reference anywhere.

## 4. Additional proven flaws (from #007/#008 — the fix list for #022/#027)

| # | Flaw | Evidence | Classic/New consequence |
|---|---|---|---|
| F1 | **Dead distance term in damage:** `divs` computes `1/(dist+2)` = 0 for all dist ≥ 0, then × base — distance has **zero** effect on damage; division is inverted (should be `base/(dist+2)`) | logic.md §5.1; harness D1: dist 5 → 28 (dead) not 31 (live) | Classic: keep dead. New: use `base/(dist+2)` |
| F2 | **Gems sell price impossible:** guide's 428 implies `$2EA92` = 856 = 4.28× base 200; formula max is 2.72× (doubling × attitude) | logic.md §3.5; `disasm/logic/trading_check.txt` (20/21 goods fit; Gems the outlier) | Guide error **or** an untraced Gems sell path — OPEN which |
| F3 | **Quiet is a no-op (music-off bug):** song index 18 dispatches to `unlk;rts`; stop routine dead; no music-off flag exists | `patches/music-off/README.md` (verified + shipped fix) | Fixed on ROM by the patch; tribute must NOT reproduce it (#030) |
| F4 | **Self-kill casting:** out-of-Power casts drain 5 HP (`$37D0E`, HP > 5 required); top spell costs up to 12000 vs 9000 max Power | spells.md §2.2/§3.2; harness S3c (HP 100→95) | Classic: keep. New: decide (cap cost or block cast) |
| F5 | **Full-party heal on every XP grant:** the `$2C4E2` party loop recomputes every member's max HP and sets current = max | logic.md §2.3 (code-verified, "needs live confirmation") | Live confirmation still owed |
| F6 | **Field dual-use `+0x2A`:** gold outside combat, DoT status word inside combat (bit 11 + duration nibble) | spells.md §7.1 | Tribute: split the fields (fixed) / overlap (classic) |
| F7 | **Merchant-none sentinel is `0x00FF`, not `0xFFFF`:** `$2EA92` compares `cmpi.w #$ff` — a caller passing −1 runs the merchant block with index −1 | logic.md §3.4 (harness caught it) | Latent bug; no in-game caller proven to pass `0xFFFF` — OPEN |
| F8 | **Record-0 dropped "An":** the dialogue blob starts mid-word (`Anunknownbuilding…`); record 0 of `$DDBD8` drops its first word — likely a real 1992 bug | PROGRESS.md #004 entry; `disasm/map.md` | Needs the live check #004 specified |
| F9 | **`+0x1E`/`+0x22` index puzzle:** `$3A62E` melee call passes attacker's current/max Power fields as `$3B1EE`'s (caster, target) indices — coherent only if combat re-purposes those fields | logic.md §5.4; spells.md §4/§9 Q1 | Dispatch proven by harness; field-writing path OPEN (needs live combat) |
| F10 | **Message-queue capacity hazard** (= Q4 div-by-zero) | logic.md §2.7; closed for new-game flow by #020 (`$1B5DA`) | Any pre-init queue write still crashes |

## 5. Still open for #021 (needs ROM/emulator — exact blockers)

**Session #3 update:** items 2, 3 and 4 below were closed in
§8 (corruption matrix §8.3, debug mode §8.2, food/water §8.1);
item 5's Bribe half was closed in §7.1. What remains is
item 1 (live combat — attract run produced zero combat
breakpoint hits, §8.4; still needs driven gameplay), the
undecided halves of item 5, and item 6.

1. Live combat: which damage path fires in a real fight (F9, and
   the giant function `0x3E2D4`'s block selection) — needs a
   save-state/input driver (architecture.md #020: bounded, no
   credible headless path without one).
2. ~~Save corruption matrix (Q1) and `$FF0168` mapping (#019 §5).~~
   **Done at the validation level in §8.3** (d1 matrix run on
   crafted EEPROM images). The $FF016A buffer *layout* remains
   #019/open — a forged buffer's contents were not booted into
   a loaded game state.
3. ~~Debug-mode xrefs (§3) + `$1F296` verb-executor full case map +
   the (A,B,C,grp) → `$D28E` command-code mapping (#020 leftovers).~~
   **Mostly done in §8.1/§8.2:** the C-code switch at $2068E is
   fully enumerated (28 cases); the Diags xref is traced. The
   (A,B,grp) half of the executor dispatch and the $D28E
   command-code mapping remain open.
4. ~~Food/water consumption routine — still unlocated after #020
   (leads: `$FF0E16` readers `$2F1F0`/`$2FA2A`/`$302F0`/`$2EC80`;
   guide rates in logic.md §3.7 remain hypotheses).~~
   **Done in §8.1:** the consumer is Camp ($3019A) — −100
   Food/Water per Camp from $FFC364/$FFC366. The $302F0 lead
   was Camp's own clock-set block. Guide per-step rates stay
   unproven; no per-step decrement site exists in the trace.
5. Bribe/attitude-repair action (attitude itself is proven in
   `$2EA92` + the `$2155E` drift loop +5/−4; the Bribe verb's
   effect is not), Doggonia 1000-gold entry fee, item-record
   +4..+9 bytes, `$FF012C` live mapping for `0x8E–0x92` spells,
   party-name writes of name indices 57–62 into `+0x14`.
   **Bribe itself was traced in §7.1** (−10 gold, $2A22A
   mode 8); the rest of this item remains open.
6. Post-harness PC=0 fault root cause (logic.md §7.3) — the #008
   harness does NOT reproduce it, so it is specific to the #007
   harness's exit state (suspects listed there).

## 6. Cross-verification: fan PAR/Gens RAM codes vs the repo struct (#033 cheats, 2026-11-09 continuation)

The cheats.htm Gens codes (Spiridakis, via #033) give per-character
RAM blocks as Exp/HP/MP triples. The repo struct (logic.md §1,
verified) is 52 bytes (0x34) at base $FF02B4, with XP at +0x1A,
current HP at +0x1C, current Power at +0x1E. Test: for each fan
address A(field), (A − 0xFF02B4 − field_offset) must be a whole
multiple of 0x34. **It is, for all six blocks, exactly:**

| Character (fan label) | Exp | HP | MP | (addr−base−0x1A)/0x34 = slot |
|---|---|---|---|---|
| Buc | FF0302 | FF0304 | FF0306 | 1 |
| (ambiguous B) | FF04A2 | FF04A4 | FF04A6 | 9 |
| Feather | FF04D6 | FF04D8 | FF04DA | 10 |
| Slash | FF05A6 | FF05A8 | FF05AA | 14 |
| (ambiguous A) | FF05DA | FF05DC | FF05DE | 15 |
| Alexi | FF060E | FF0610 | FF0612 | 16 |

This is a strong two-way validation: the fan codes (an independent
1990s/2000s source) land on the repo's struct grid with the repo's
field offsets, and the repo struct predicts exactly the +2/+4
spacing the codes show. Equivalent reading: with a base of
$FF02E8 the same blocks are slots 0/8/9/13/14/15 — the codes alone
fix only the *relative* layout (Buc lowest; then B, Feather; then
Slash, A, Alexi at the top, with gaps = other entities in the
0x38-entry general table); the repo base $FF02B4 (proven from
code, e.g. $FF02DC = slot 0 +0x28) is what pins the absolute slot
numbers above.

Side corroboration: the codes' "max Exp" value for Slash/Feather/
Alexi is 0x32C8 = **13000, exactly the repo-proven XP cap**
(logic.md §2). Buc's reads 0x3A98 (=15000, the gold cap value —
likely a copy slip in the fan list).

### Mortimer vs Obliky — NOT resolved; hypothesis recorded

The two unlabelled blocks are slots 9 (B, just before Feather)
and 15 (A, between Slash and Alexi). Nothing in the repo ties a
name to either slot: party *name* order (57 Buc, 58 Slash,
59 Mortimer, 60 Obliky, 61 Feather, 62 Alexi) does not match the
RAM order (Slash and Feather are swapped relative to it), and
recruitment order doesn't either (Slash joins first but sits at
14, above Feather's 10 — the table is world-entity creation
order, not join order). **Strongest hypothesis (low confidence):
A (FF05DA, slot 15) = Mortimer, B (FF04A2, slot 9) = Obliky** —
from the listing order in one of the two cheats.htm extractions
(which names Mortimer's group first at FF05DA) and Mortimer's
Division-guild association with Slash (slot 14, adjacent).
Decisive experiment (owed): in a live game, recruit one of them
and watch which block's XP/HP move, or breakpoint writes to
FF04A2 vs FF05DA on recruitment.

### Food / Water / Money globals — matches and mismatches

- **Money FF02DE:3A98** — value 0x3A98 = **15000, exactly the
  repo gold cap**. Address: $FF02DE = $FF02B4 + 0x2A = **slot 0's
  +0x2A gold field** under the repo base. Consistent with gold
  living in a character struct's +0x2A (logic.md §1), IF the
  gold-holder occupies slot 0 in the PAR author's game state —
  but note the tension: the fan "Buc" block sits at slot 1 under
  the same base, so either the leader's gold is kept in a
  slot-0 struct, or the author's Buc was in slot 1 while gold
  was read from slot 0. Flagged, not smoothed over. It is NOT
  $FFC40C (that is the *battle* gold-total accumulator, a
  different thing — no conflict).
- **Food FFC364 / Water FFC366 (value 0x7530 = 30000)** — no repo
  doc names a global at $FFC364/366. The nearest mapped
  neighbours are the combat block ($FFC37C message target,
  $FFC380 damage). Food/water as *inventory* are goods slots
  0/1 handled via $2BBD2 codes 0x380/0x381 (logic.md §3.7), so
  $FFC364/366 are plausibly cached current amounts in the
  $FFC3xx state block, **unverified**. The consumption routine
  that would prove it is still unlocated (§5 item 4).
- Xavier's claim that Food/Water/Gold addresses are *stable*
  while other characters' move between games is consistent with
  the above: the stable ones are globals/struct-slot-0, the
  party blocks sit in the general entity table whose occupancy
  depends on spawn order.

## 7. Continuation traces 2026-11-09 (ROM + Ghidra map in VM)

### 7.1 Bribe — LOCATED (executor case in $1F296)

The Bribe action is a case inside the verb executor `$1F296`,
at **0x20466–0x204C6**:

1. Gate: `jsr $1E49A($FF0E18)` must return 0 (an
   interaction-state test on the current target record), else
   the case exits.
2. Funds check: the leader's gold (char struct +0x2A, read via
   the $FF02DE base) is compared with **10** (`cmpi.w #$a`);
   below 10 the case exits silently.
3. Cost: `$2BBD2(1, -10, 0x400, leader)` — exactly **−10 gold**,
   matching the walkthrough claim (10 gold) with code evidence.
4. Effect: `$2A22A(8, 0, leader)` then `$298D2(result)` — the
   attitude/mood adjustment is applied through the same helper
   the neighbouring conversation cases use (sibling cases pass
   9, 0x16, 0x17, 0x18 after the same $1E49A gate). $2A22A walks
   related characters via struct fields +0x14/+0x26 and the RNG
   ($12B82); the final +0x22 attitude write sits inside that
   helper's downstream and was not isolated to a single
   instruction in this trace — the claim stops there.
   The refusal line "How dare you insult my honor by trying to
   bribe me." lives in the dialogue layer; which gate failure
   selects it was not traced.

So: Bribe exists, costs exactly 10 gold, requires ≥10 gold and
a bribable interaction state, and applies its attitude effect
via $2A22A mode 8. The earlier "not located in code" note in
docs/logic.md §3.6 is superseded by this trace.

### 7.2 Food/water — the $FF0E16 complex is the world clock, NOT provisions

All named $FF0E16 readers/writers were traced:

- **world_tick $2155E (0x215B8)**: `$FF0E16 = ($FF0E16 + 1) mod
  2400` once per tick (divs #$960, remainder via swap). It is a
  **tick counter**, initialised by new_game_init to 540
  (0x1B7A2) or 2100 (0x1B812) depending on mode.
- The derived scale `$FF0E16 / 18` drives periodic events:
  world_tick calls $170DA when the quotient is exactly 30
  under state flags ($FF0124/$FF0126), and $170DA itself is a
  calendar/clock routine (formats the counter with the
  $CCB18/$CCC38 tables).
- **0x302F0** is a clamp/normalise pass inside a 36-entry loop:
  values above 540 are cleared to 0 with message 0xD via
  $35612, values at/below are set to 540 with message 0xC —
  clock-field normalisation, not consumption.
- **0x2EC80/0x2EC9C** are threshold classifiers on the same
  quotient (>30 ⟺ counter > 540).
- **0x2FA2A** writes $FF0E16 from the $FFA800 record stream —
  the save/load state copy.
- The $32C56 call inside world_tick (0x21806) passes
  (1, leader struct +0xE, leader struct +0xC) = position
  coordinates; $32C56 is a what's-at-this-position lookup
  (iterates via $269F2), not a provisions routine.

**Verdict:** no per-step Food/Water consumption routine
exists among the $FF0E16 sites — the suspected "step counter"
is the world clock. Food/Water remain ordinary goods in the
$2BBD2 inventory system (records 186/187); no tick-driven
decrement site for them was found in this trace. If the game
consumes them anywhere, the remaining unexamined candidate is
the Camp verb's case in $1F296 — named here as the follow-up,
not claimed.

## 8. Session #3 traces 2026-11-09 (ROM + BlastEm debugger in VM)

### 8.1 Camp — LOCATED, and it is the food/water consumer

The executor's C-code dispatch (third switch in `$1F296`, at
$2068E, on the byte in `$FFBB6C` copied from the verb record's
C field) maps **C=$1C → case at 0x204CE** — Camp's own verb-table
record (`0xCCE0A`, C=0x1C) feeds exactly this. The case is a
single call: `$3019A(0)`. The full C-chain was enumerated this
session (28 cases, $2027E–$20670 + exits); it also pins
Bribe=C=$19→$20466 (confirming §7.1), Diags=C=$37→$205BC (§8.2)
and two bare-exit stubs (C=$18→$20462, C=$1B→$204CA).

`$3019A` (1,166 bytes, callers: the Camp case and `$2BBD2` at
0x2BE58 with argument 1) does, in order:

1. **Random encounter roll** (both argument modes): if
   `$FF00AE==2`, `$26A8C` runs first. Then `RNG(3)` ($12B82):
   nonzero (2/3) → no encounter. Zero (1/3) → spawn via
   `$32D4C(3, 59, template, 0,0,0, $FFBB86, &local)` with
   template ∈ {$5E, $4D, $4C} from a second `RNG(3)`, or $4E
   if a further `RNG(30)` returns 0; the encounter message is
   queued via `$26B58` with a name byte from the
   template×6 record table at `$CECF2`. **Camping can start a
   fight — it is not a safe rest.**
2. **$FF00C0 table pass:** for i in 0..35, entries below 10 are
   raised by 3 (shared clamp idiom, bounds −100..100); entry
   34 is exempt. ($FF00C0 is a 36-word per-entity table also
   written by the entity spawner $23B84 and copied by the
   save-state code $2F896; its exact semantics remain open —
   behaviour recorded, name not invented.)
3. **World clock set:** if `$FF0E16 > 540` → `$FF0E16 = 0`,
   else `$FF0E16 = 540`; message $35612(…, 0xD) / (…, 0xC)
   respectively when the argument is 0. `$FF0124 = −1` (forces
   the time-of-day/palette refresh in the world tick). This
   is the block §7.2 saw at 0x302F0 and read as a standalone
   "clamp pass" — in context it is Camp sleeping to the next
   540/0 clock boundary (morning/midnight on the mod-2400
   clock). §7.2's reading is corrected here.
4. **Food/water consumption (argument 0 only — the verb-menu
   Camp):** `$FFC364 = clamp($FFC364 − 100, 1, 30000)` and
   `$FFC366 = clamp($FFC366 − 100, 1, 30000)` at
   0x30346–0x303B4. **This is the missing consumption
   routine.** It also settles §6: the fan PAR addresses
   $FFC364/$FFC366 ARE the live Food/Water stores, and the
   PAR value 0x7530 = 30000 is exactly this clamp's maximum.
   Consumption is per-Camp (−100 each), not per-step; the
   guide's per-step rates remain unproven and no per-step
   decrement site exists in this trace.
5. **Healing:** argument 0: for up to 6 roster entries
   ($FF0E82 table), HP (+0x1C) and Power (+0x1E) each recover
   **¼ of the deficit** toward their maxima (+0x20/+0x22).
   Argument 1 (the `$2BBD2` item-path call): message 0xF via
   $35612, then the same fields recover **½ of the deficit**
   for 6 entries — and steps 4 (and the step-5 ¼ pass) are
   skipped, while steps 1–3 still run as written.

### 8.2 Debug mode (Diags) — REACHABLE; the setting is live, the overlay string is not referenced

§3's owed xref experiment is done, plus a full flag trace:

- **The toggle is a verb-executor case:** C=$37 → **0x205BC**:
  `tst $FF0134; bne clear; set 1` — a pure toggle of the
  Diags flag `$FF0134`, in the same dispatch chain as Bribe
  (C=$19) and Camp (C=$1C). A sibling case (C=$38 → 0x205D8)
  toggles `$FF013A` the same way.
- **The options panel draws it:** `$26E44` (called from the
  per-frame redraw `$1B918` when `$FF009C` is set, among other
  callers) draws, when `$FF00AC != 0` and menu state
  `$FFA7F8 == 8`: "Help On/Off" (flag `$FF0132`, strings at
  $27522/$2752A), "Direct:" + "Lefty"/"Righty" (flag
  `$FF0116`, $2753B/$27541), and **"Diags On"/"Diags Off"**
  (flag `$FF0134`, $27548/$27551) via the text routine
  $1113C at rows 12–15. The MAIN menu's `System` item carries
  B=8 — matching the state-8 panel. The panel is live UI
  code on the main loop's redraw path, not a leftover.
- **The flag does something:** in the input decoder `$12FE8`,
  pad-nibble values the normal direction tables reject
  (≥ $A on the $FF0116 path at 0x13030; mirrored site
  0x130B6) decode as **neutral (d6=4)** when Diags is OFF,
  but are routed through a second jump table (0x13052 and
  its twin) to direction codes 0–4 when Diags is ON.
- **The flag persists:** `$2F11A` pushes `$FF0134` during
  save serialisation (0x2F256); `$2F896` writes it back on
  load (0x2FA90).
- **The format string is a different story:** `0x023934`
  (`N^NuSp:%i Dir:%i Ac:%i St:%i Dr:%i`) has **no reference
  anywhere** — no lea/pea in the linear sweep, no longword
  pointer in the ROM. The sprintf-style diagnostics overlay
  it implies was either removed before shipping or reached
  by a computed pointer no trace has found; the string
  itself is inert in the shipped ROM.

**Verdict: Diags is reachable and functional as a settings
toggle (menu case + panel + input effect + save
persistence). The debug *overlay* is not evidenced in the
shipped code.** Runtime corroboration of the panel draw in
the live game: §8.4.

### 8.3 Save checksum — corruption matrix RUN (Q1 closed)

$4323C's check, now read instruction by instruction
(0x43272–0x432A6): S = (sum of buffer bytes 0..125) mod 256;
the stored pair must satisfy buf[127] == S, buf[126] == ~S,
buf[127] == ~buf[126]; mismatches count into d1; `d1==0`
accepts. Four crafted EEPROM images were booted in BlastEm
(scratch files in BlastEm's save dir; the repo ROM and the
original blank EEPROM were restored afterwards), reading d1
at the `tst.w d1` site (0x432A6) in the debugger:

| Image | d1 | Verdict |
|---|---|---|
| Blank (all $FF) | 3 | all three checks fail — rejected |
| Forged: bytes 0..125 = 0..125, pair set to S=0xC3 / ~S=0x3C | **0** | **accepted as a valid save** |
| Forged + 1 byte flipped | 2 | detected (sum checks fail, pair check passes) |
| Forged + compensating pair (+1/−1) | **0** | **corruption NOT detected** |

**Q1 is closed: the save checksum is a format check, proven
forgeable, and compensating corruption passes it.** (What a
forged buffer's *contents* would do as a loaded game state
was not tested — that needs the buffer layout, §5 of
docs/save-validation.md; the claim stops at validation.)

### 8.4 Runtime checks (BlastEm debugger, session #3)

- **Combat paths never fire without input:** breakpoints at
  $3A842 and $3B094 ($3B1EE's callers), at $3B1EE itself and
  at the vestigial $40880 were armed from power-on through
  the full intro and the main-loop attract sampling —
  **zero hits**. No combat occurs in attract, so the live
  damage-path question (F9) remains answered only at the
  #008 dispatch level; it needs driven gameplay (input
  driver), which this headless setup cannot do.
- **Diags flag live value:** read at the $D28E stop as
  **$FFFF** — Diags is ON by default in a fresh (no-save)
  boot, matching the ROM RAM-init image at $FCE3C+$134
  ($FF0132 Help is likewise $FFFF by default; both are
  overwritten only by a loaded save via $2F896).
- **Panel routine is called in the live loop:** advancing
  to 0x1B9AA (the `jsr $26E44` site in $1B918) stopped
  during the attract main loop — the game itself sets
  $FF009C and takes the panel branch without any forcing.
- **What could not be forced:** drawing the state-8 options
  page rows (the "Diags On/Off" text) under debugger control
  needs $FFA7F8=8 + $FF00AC=1 written to RAM, and this
  BlastEm build's debugger `se` command **rejects every
  memory-destination form tried** (bare, $-prefixed,
  parenthesised, decimal — all "Invalid destinatino";
  register destinations work, values parsed as decimal).
  The row draw therefore rests on the static chain in §8.2
  (panel code + string sites inside $26E44, which is
  main-loop-called), not on a forced runtime screenshot.
  Driving the real menu with pad input remains the other
  route and needs an input driver.

## 9. Session #4 — LIVE GAMEPLAY (input driver built; combat, Camp, Diags, Void all observed)

Sessions #2/#3 ended at the same wall: no input driver, so no
menus, no combat, no driven gameplay. That wall is down.

### 9.0 The input driver (route (a) worked; route (b) not needed)

- **Stack:** BlastEm 0.6.3.4 windowed (`-g -l`) under Xvfb
  (own display :77 — the VM's pre-existing :99 Xvfb has an
  Xauthority file this session cannot read; that was the only
  launch failure), driven by **xdotool** (3.20160805.1, from
  Ubuntu pool .debs: xdotool + libxdo3 + libxtst6) sending
  XTest keystrokes to the focused window, all orchestrated by
  a small command-file driver (Python, BlastEm on a PTY so
  the debugger stays reachable on the same stdin). Screenshots
  are BlastEm's own `ui.screenshot` key — the frames in
  `docs/logic-audit-evidence/` are the emulator's PNG output,
  not composites.
- **Bindings:** /etc/blastem/default.cfg gives pad 1 to the
  keyboard (arrows = D-pad, a/s/d = A/B/C, enter = Start,
  u = enter debugger, p = screenshot). A scratch-HOME config
  copy added pad-2 keys (i/k/j/l, g/y/t, h = A/B/C/Start).
- **Full path driven, twice:** logos → title → menu
  (CONTINUE/START/INTRO/CITIZENS/CREDITS) → START → Book of
  Nexus intro → overworld (Buc, $1000, F/W display) → town,
  menus, NPC dialogue, four Camps, two battles.
- **Control map (empirical):** Start opens the MAIN verb
  menu; **B confirms** in verb/answer menus; **A advances**
  message pages; **C cancels/closes**. A does nothing in the
  MAIN menu (an early false lead — the run-1 title-menu start
  was B-equivalent behaviour on that screen's own handler).
- **Q3 live colour:** in-game menus consume the $FF001C
  queue, and the 3-frame debounce is *felt*: holds of
  ~110 ms step the cursor 1–3 times (re-queued held bytes
  each count as a step); ~70 ms presses step exactly once;
  sub-40 ms presses are eaten entirely. The "eaten press"
  case of §2 Q3 is a real, reproducible behaviour of the
  shipped input path, not just a mechanism on paper.

### 9.1 Debug mode — runtime corroboration (§8.2's missing half, supplied)

Driven through the real menu (Start → MAIN → SYSTEM), the
options panel draws live: `HELP: ON / DIRECT: RIGHTY /
DIAGS: ON / COMBAT: AUTO` (evidence: diags-panel-on.png).
Selecting DIAGS toggled it: panel redraws `DIAGS: OFF`
(diags-panel-off.png) and the debugger then read
**$FF0134 = 0**; toggling back read **$FF0134 = 1** — the
exact `set 1` of the $205BC executor case (§8.2), against
the $FFFF RAM-init default read in session #3. HELP was
also toggled ON→OFF live the same way ($FF0132). The
address log for the session contains 0x205BC and 0x26E44.
**Debug-mode reachability is now closed at runtime, not
just statically: the setting is reachable, drawn, and
functional; the $023934 overlay string remains unreferenced
(§8.2's verdict stands for the overlay only).**

### 9.2 Camp — live measurements (§8.1 confirmed, plus one new unknown)

Four Camps driven from the MAIN menu:
- Camp #1 (clock 674): message "You make camp until dusk";
  clock read 8 afterwards (674 > 540 → set 0, +ticks). The
  clock-set half of $3019A is live-exact.
- Camp #2 (clock 95, night): **Food $FFC364 1729 → 1629,
  Water $FFC366 1859 → 1759 — exactly −100 each**, clock
  95 → 547 (set 540, +ticks). §8.1's consumption numbers
  are live-confirmed.
- Camps #3/#4 repeated the dusk/dawn messages with the same
  clock behaviour.
- **New unknown:** provisions also drain *outside* Camp.
  Across the baseline→Camp #1 interval (walking + town,
  one Camp) Food fell 268 and Water 140 in total; across
  Camp #2→post-battle (two Camps + walking + a battle)
  Food fell 350 and Water 251. Camp accounts for exactly
  100/100 per use in the controlled measurement, so a
  second drain tied to travel/time exists that the static
  traces (§7.2, §8.1) did not attribute. Recorded as an
  open sub-item; no mechanism is guessed here.

### 9.3 Q5 — the Void message trigger: CAMPING (observed once)

Camp #2 — the first sleep-until-dawn rest — interrupted
the rest with the dream (evidence: void-dream.png): the
grey demon portrait and **"You DREAM OF THE DEMON VOID:
'BETRAYER, DECEIVER, YOUR DEATH SHALL MEAN INFINITE PAIN
FOR MY CONSUMPTION!'"**, MORE prompt, then the normal
"make camp until dawn" message. Camps #1/#3 (until dusk)
and #4 (until dawn) showed no dream. Verdict: **the Void
message is a rest event attached to Camp**, fired once in
four camps (the first dawn rest); it is not a per-camp
fixture. Whether it is one-time-scripted or rare-random
is not decided by four samples. The "N seconds" timer
half of Q5 saw no timer in the live flow (pages advance
by button); a static xref for the string's message id is
still owed — the trigger question itself is answered.

### 9.4 Live combat — the damage path (F9's dispatch half: ANSWERED)

Two battles driven:
1. **Walking encounter (run 1):** a Wyvern fight reached
   by overworld movement: "WYVERN casts SPARK. Buc TOOK 6
   HIT PTS" (evidence: combat-wyvern.png). Run 1's address
   log contains 3B1EE, 3A62E, 3C2C0, 37D0E (the spell-cost
   path for Spark) — and no 35600 (battle not finished).
2. **The beggar Evin (run 2):** wandering/town NPC event —
   "WILL YOU GIVE ME 50 GOLD?" Answering YES cost exactly
   50 gold (twice observed: $FF02DE 1000 → 900 across two
   gifts; HUD agreed). Answering NO turned him hostile:
   "EVIN ADVANCES" → battle. With the $3B1EE breakpoint
   armed, three consecutive damage stops all read, off the
   stack, **return address 0x3A846 — the call site at
   $3A842 inside $3A62E** (bsr.w form) — with a0 = $FF03B8
   (entity slot 5) and pushed arg words 3, 1, 0xB, $FFFF
   at the first stop. The $3B094 site never fired; $40880
   never fired (third session in a row). On screen: "EVIN
   TOOK 5 HIT PTS" (Buc's hit, through the same path) and
   a mid-fight "Buc RETREATS" (Combat: AUTO AI), ending
   **"BATTLE SUCCESSFUL. You earned 6 experience per
   person. You also captured 20 gold pieces."** (evidence:
   battle-victory.png). Gold after: $FF02DE = 0x398 = 920
   (900 + 20), HUD $920. Run 2's address log contains
   2C4E2 (the XP grant ran), 3019A, 205BC, 26E44, 12FE8.
   **So the live physical-damage path is $3A62E → $3A842
   → $3B1EE for both combatants in this fight.** What
   $3B094 serves (spell damage via $37D0E is the standing
   candidate — Spark's damage in run 1 could not be
   breakpoint-isolated) stays open, as does F9's deeper
   half: whether combat writes the +0x1E/+0x22 fields as
   indices before the call was not isolated — the args
   observed are recorded above and the claim stops there.

### 9.5 F5 — live test: NO heal on a plain XP grant

After the Evin victory (+6 XP per person; the grant
routine in the address log), Buc's struct read in the
debugger: **slot 1 — XP $FF0302 = 6, HP $FF0304 = 7,
max HP $FF0308 = 20.** Buc ended the fight at 7/20 HP
and the XP grant did **not** restore him, contradicting
the strong reading of §2.3/F5 ("every XP grant heals the
party to full"). The escape hatch is real: XP 6 < 100 =
no level-up occurred, and the heal may live in the
level-up branch only. Verdict: **F5 refuted for grants
without level-up; level-up half still untested** (needs
100 XP ≈ many more battles). Side confirmation: Buc is
slot 1 and his XP landed exactly at $FF0302 — the fan
PAR layout of §6, verified from the live side this time.

### 9.6 Pad-2 teleport — inconclusive

The #033 combo (pad 2 A+C+Start) was sent via the scratch
config's pad-2 bindings on a clean overworld. Observed:
no relocation; between screenshots 2 s apart the clock
advanced ~3 game hours with a slight camera shift. The
pad-2 bindings themselves have no independent proof (no
pad-2 feedback channel was observed), so this is recorded
as **inconclusive** — neither "cheat works" nor "cheat
false" is claimed.

### 9.7 Still open after session #4

F2 (needs a gem in a SELL list), F7 (a caller passing
$FFFF to $2EA92), Doggonia's 1000-gold fee (town not
reached), $FF012C live mapping (needs the flat-70 /
flat-5 spell codes cast), Bribe live (statically complete
in §7.1; the one merchant conversation found was exited
before its TALK submenus), F5's level-up half, the extra
provision drain (§9.2), Q5's static message-id xref,
party-name writes, the (A,B,grp) dispatch half, and the
post-harness PC=0 fault. §5 item 1 (live combat) is
**closed** by §9.4.

## 10. Session #5 — LIVE GAMEPLAY II (travel drain solved; F5 level-up half decided; pad-2/teleport mechanism proven)

Driver: same stack as §9 (BlastEm 0.6.3.4 reinstalled from
pool .debs on this VM instance; own Xvfb :77; scratch HOME
with pad-2 bindings added — this session's pad-2 keys:
i/k/j/l directions, **g = A, y = B, t = C, h = Start**).
Evidence screenshots: docs/logic-audit-evidence/s5-*.png.
All sessions on scratch EEPROM/ROM copies.

### 10.1 The extra provision drain (§9.2's unknown) — SOLVED: per-step movement cost in FUN_00024984

**Static census first.** Every writer of the Food/Water
stores in the ROM (linear sweep for $FFC364/$FFC366 stores):
new-game init ($2CE60, sets both to 2000), the save/load
copies ($2FB08/$2FB2E), the goods add path ($2C1C0/$2C208,
inside $2BBD2), Camp ($3037A/$303B4, §8.1), and one
parameterised subtract at **0x24F44 in FUN_00024984**:
`Food -= local[-8]`, `Water -= local[-6]`, each clamped to
[1, 30000], gated on `$FF00AE == 1`. world_tick ($2155E)
only *reads* the stores (the ≤500/≤1 warning messages at
0x21714–0x2183E) — it never decrements them.

**Live measurement (breakpoint at the Food store 0x24F78).**
Fresh game (Food 1978 / Water 1988 at first read — the
new-game sequence itself has already charged ~7 steps'
worth), then controlled single steps on the spawn-area
grassland, catching every store:

| Step | Food before→after | cost local [a6−8] | Water cost [a6−6] | Δpos |
|---|---|---|---|---|
| E ×3 | 1978→1975→1972→1969 | 3, 3, 3 | 1 | +1 X each |
| W ×2 | 1968→1965→1962 | 3, 3 | 1 | −1 X each |
| S (no displacement) | 1969→1968 | 1 | 1 | none |

Every delta equals the locals exactly; the d0 chain across
stops has **no unaccounted drops** (no NPC/other drain
fired). **Idle control:** 60 s standing still — clock
$FF0E16 advanced +300 ticks (5 ticks/s) while Food/Water
did not move at all. **Verdict: the travel drain is a
per-step movement cost charged by the entity step handler
FUN_00024984 when the party steps on the overworld
($FF00AE == 1): Food −3 / Water −1 per step on plain
grassland, the amounts taken from fields +0x26/+0x28 of
the step's local record (terrain-dependent in principle —
one no-displacement step charged (1,1)); not per clock
tick and not per party member (party of one throughout).**
This reconciles §9.2's long-interval excesses (e.g. −268
Food over one Camp + travel ≈ −100 Camp + ~56 steps × 3).
The guide's per-step rates (logic.md §3.7) are superseded
by these measured ones for grassland.

### 10.2 F5 level-up half — DECIDED: maxima recompute, current HP/Power NOT healed

Method (stated plainly): a genuine battle victory — the
beggar Evin refused, AUTO combat, won (evidence:
s5-evin-battle.png, s5-evin-victory-6xp.png; the victory
text confirms the real grant, 6 XP / 20 gold). At the XP
store instruction (breakpoint 0x2C566 in $2C4E2) the
about-to-be-stored total was raised from 6 to 101 with one
register edit (`se d0 101`) so the level crossing happened
on this real grant instead of after ~17 identical battles;
the heal question is independent of the amount. Buc's
state at the stop (all debugger-read): slot 1 (d1 = 0x34),
HP **4/20**, Power 1000/1000, XP 0 → 101 stored.

After the grant completed: **XP 101, max HP 20 → 35**
(the $31958 level-1 value), **current HP 4 → 4 —
unchanged**; the game's own announcement (evidence:
s5-levelup-message.png) says "MAXIMUM HEALTH IS NOW 35
POINTS AND MAXIMUM POWER IS 2000 POINTS" — maxima only.

**Verdict: F5 is refuted in both halves.** No XP grant —
plain (§9.5) or level-up (here) — restores current HP or
Power. The true behaviour inside $2C4E2's path is narrower:
on a level crossing the *maxima* are recomputed from the
level formulae; current values are left exactly where the
battle put them (here, 4/35 HP).

### 10.3 Pad-2 — bit encoding derived; bindings runtime-proven; the teleport mechanism found in code

**Encoding (from $DCE2's two-phase read + NOT):** the
pad-2 byte has **bit7 = Start, bit6 = A, bit5 = C,
bit4 = B, bit3 = Right, bit2 = Left, bit1 = Down,
bit0 = Up; 1 = pressed**. *Erratum to docs/save-validation.md
§2:* its "$E0 = B+C+Start / $B0 = A+C+Start" assignment is
swapped against this bit layout — **$E0 is A+C+Start and
$B0 is B+C+Start** ($4323C's first read at 0x4324A tests
$E0; the later reads at 0x432FE/0x43316 test both).

**Bindings verified live (this session's open question in
§9.6).** Three independent runtime proofs that pad-2
input via the scratch bindings reaches the game as the
exact bytes:
1. Holding g+t+h latched **$FF8646 = $E0** (the per-frame
   pad-2 byte refreshed by FUN_00011BB8 via $DCE2).
2. Holding g+t+h **from power-on** made $4323C take its
   combo branch: after boot, **$FF0168 = 1** — the
   clear-save path at 0x432B6 (buffer zeroed) ran on the
   scratch EEPROM, exactly the documented combo effect.
3. Holding the same keys *through* the later boot reads
   drove $4323C to its $F0 return and the 0x4333A
   blackout (solid backdrop screen, evidence:
   s5-pad2-boot-blackout.png; reset required) — the combo
   is timing-sensitive: it must be present at the first
   read and gone by the later ones.

**The teleport itself — mechanism PROVEN in code.** The
Map verb (record C=0x11) dispatches in the verb executor
to **FUN_0002DCCE**, which gates on owning a Map item and
being outside (the game's own refusal, observed live this
session: "YOU MUST HAVE A MAP AND BE OUTSIDE." —
evidence: s5-map-gate-message.png) and calls the map
screen **FUN_0001664E**. In that screen's loop, at
**0x16C72**: `move.b $FF8646, d0; cmp.w #$E0, d0` — on
pad-2 **A+C+Start** it converts the highlight cursor's
coordinates (d6/d7, remainders mod the map dimensions at
$FFA7FC) and calls **$3081A**, the relocate routine
(3 callers). The fan cheat is a faithful description of
this code path.

**Live execution: NOT performed — conditions not met.**
Buc owns no Map (INVEN checked: only "So Sym"); the item
is shop goods (price record 159, §3 tables: 415 gold —
affordable at 1020). Mind town was reached and explored
(Academy district + harbour district) but no shop
transaction was completed in the session, so the map
screen never opened with its conditions satisfied.
**Verdict: cheat mechanism proven in code, pad-2 delivery
proven live, execution outstanding — this is "conditions
not met", not "cheat false".** Session #4's inconclusive
is superseded on every point except the final keypress.
**Superseded by §11 (session #6): the teleport is now
EXECUTED end-to-end; only the item-acquisition half of
this paragraph's story changed (see §11.1 for how the
Map was obtained and §11.2 for the execution itself).**

**Two more pad-2 combos found in code while tracing
(not in the fan lists consulted):**
- Map screen, 0x16CB2: `cmp #$A5` (**Start+C+Left+Up**)
  → the leader's struct gets HP/maxHP = 140 and
  Power/maxPower = 9000 written, plus a flags nibble
  edit at +0x18 — a god-mode cheat on the same screen.
- Intro story (FUN_000123B0, called by intro_story_driver):
  reads pad 2 at 0x12420, `cmp #$FA` (**Down+Right+A+B+C+
  Start**) sets a flag — the fan "Topples Lady" / intro
  cheat (docs/research/sources.md), matching byte $FA
  exactly under the encoding above.

### 10.4 Still open after session #5

F2, F7's caller, Doggonia fee, $FF012C live, Bribe live,
Q5's message-id xref, party-name writes, (A,B,grp)
dispatch, post-harness PC=0 — and now the pad-2
teleport's final execution (needs: buy Map in a shop,
step outside, MAIN → MAP, highlight, pad-2 A+C+Start;
the $A5 god-mode combo can be verified on the same
screen visit). §5 item 4's guide-rate question is closed
by §10.1; F5 is closed by §9.5 + §10.2.

**Session #6 update:** the teleport's final execution is
DONE (§11) — the Map was granted, not shop-bought (§11.1
states exactly how and why). The $A5 combo's live
verification remains open (not attempted in session #6;
Buc died to a destination encounter first). The rest of
this list is unchanged.

## 11. Session #6 — LIVE GAMEPLAY III (pad-2 teleport EXECUTED end-to-end)

Driver: same stack as §9/§10 (BlastEm 0.6.3.4, own Xvfb
:77, scratch HOME with the §10 pad-2 bindings g=A, y=B,
t=C, h=Start; the driver gained a multi-key hold op for
the combo). Evidence screenshots:
docs/logic-audit-evidence/s6-*.png. Scratch ROM/EEPROM
only; the repo ROM is byte-untouched (MD5 re-verified
30c18fdb… after the session).

### 11.1 The Map item — purchase attempted in earnest, then granted (labelled)

The purchase route was worked first, for real: a fresh
game was driven from spawn into the City of the Mind
twice (the city is immediately east of Buc's cottage)
and explored across the Academy, harbour, warehouse
(entered; an indoor encounter there was fought and won,
+48 gold) and residential districts, plus "Someone's
Home" — building banners named every doorstep reached.
No BUY menu was ever reached: no shop transaction was
completed, and no conversation offered one (the two
conversations found were the beggar-type event of §9.4
and a knight post whose captain's question, answered
NO, turned hostile). Buc died three times in the
attempt (gate Wyvern; two bears in a residential
district; the knights). Statically, the missing link
was also pinned down this session: a shop's category is
chosen in the conversation helper's init (0x2A48A–
0x2A532) by matching an NPC struct byte (+0x17) against
each item record's code byte at $D66A2+i·10, gated on
the NPC's +0x25 byte > 0 — the Map sits in category 13
(item record 13, w=153: records 153–185, symbols then
quest items; the Map is slot 6, price record 159, 415
gold). Which Mind NPC carries category 13's code was
not isolated before the fallback was taken.

**The grant (exactly this, nothing more):** this
BlastEm build's debugger cannot write memory at all
(§8.4: `se` rejects every memory destination), so the
fallback agreed for this item — grant the item by an
out-of-game write and label it — was applied one
level down, in the scratch ROM copy only: byte
0x2CE3D — the immediate of new-game init's
`move.b #$1, $FFC340` at 0x2CE3A — was changed
$01 → $41, and the scratch copy's checksums were
re-fixed (`tools/checksum.py fix-all`; verify-all OK).
$FFC340 is the category-13 ownership bitmap (case at
0x2C0BE in $2BBD2's dispatch: $2B68C($FFC340, slot));
init stock $01 is bit 0 = "So Sym" (record 153 — why
every fresh Buc owns one), and $41 adds bit 6 = the
Map (record 159). In the live granted game the
debugger read **$FFC340 = $4100** and INVEN → ITEMS
lists "So Sym / Map" (evidence: s6-inven-map.png).
This is a granted item, NOT a shop purchase; the
purchase itself remains uncompleted and is recorded
as such.

### 11.2 The teleport — EXECUTED

Fresh granted game at spawn (outside: $FF00AE = 1;
evidence: s6-overworld-before-teleport.png). Leader
position (slot 0, struct +0xC/+0xE at $FF02C0/$FF02C2)
read in the debugger before: **(111, 125)** — the
fixed spawn $1B5D6 writes (see the #020 findings). A breakpoint was
armed at $3081A. INVEN → ITEMS → Map opened the map
screen FUN_0001664E (evidence: s6-map-screen-open.png);
holding pad-1 Right panned the window/highlight east
to the coastal city south of the east coast (evidence:
s6-map-screen-destination.png). Pad-2 **A+C+Start**
(g+t+h held 1.5 s) was then held on the map screen:

- The debugger stopped: **"68K Breakpoint 0 hit" at
  $3081A** (`link.w a6, #$FFFFFFFE`).
- Stack at the stop (a7 = $FFEB38): return address
  **$00016CAE** — the instruction after the
  `jsr $3081A` at 0x16CA8 in FUN_0001664E's $E0 branch,
  i.e. the call came from the map screen's pad-2
  compare at 0x16C72, not from any other $3081A caller;
  argument words **X = 171, Y = 125** (the highlight's
  converted coordinates).
- After continuing, the leader's position read
  **(171, 125)** — $2570A wrote the destination into
  +0xC/+0xE exactly as traced in §10.3.
- Exiting the map screen (pad-1 C) put the overworld
  on a forested east-coast shore with a lone hut —
  a different region from spawn (evidence:
  s6-overworld-after-teleport.png); Buc stepped out
  of the hut tile and walked under control
  (s6-destination-step-out.png). Minutes later a
  random encounter there (Scourge + Knight + Priest)
  killed him — east-coast fare, far above the spawn
  area's, incidentally consistent with the relocation
  being real.

**Verdict: the fan pad-2 teleport cheat is EXECUTED
end-to-end and is TRUE** — mechanism (§10.3), pad-2
delivery (§10.3), and now the final keypress, the
$3081A call, and the before/after coordinates
(111, 125) → (171, 125) are all runtime-evidenced.
The only non-standard step in the chain is the Map's
acquisition (§11.1: granted via a one-byte scratch-ROM
init patch because no shop sale was completed and
this debugger cannot write RAM); the gate, the map
screen, the combo and the relocation all ran through
the game's own unmodified code paths in the live
session (the patch touches only the init immediate —
FUN_0002DCCE, FUN_0001664E, $3081A and $2570A are
byte-identical to the shipped ROM).

### 11.3 Still open after session #6

Everything in §10.4 except the teleport execution:
F2, F7's caller, Doggonia fee, $FF012C live, Bribe
live, Q5's message-id xref, party-name writes,
(A,B,grp) dispatch, post-harness PC=0, the $A5
god-mode combo's live verification, and — newly
sharpened — a genuine shop purchase of the Map
(category-13 NPC unidentified; the matching rule is
in §11.1).

## 12. Session #7 — the §11.3 remainder, item by item (2026-11-09)

Session #7 worked the §11.3 list in order. Static verdicts
come from full Capstone reads of the named functions
against `disasm/ghidra/function_map.csv`; live verdicts
from the BlastEm + xdotool driver on the clean ROM
(unless a grant is explicitly labelled). One evidence
note up front: at ~20:27 CST the VM's /tmp was wiped and
its tool install reset mid-session, destroying the
pre-wipe live screenshots (the $A5 check, the Bribe, the
$FF012C reads). The numbers quoted for those three items
are the in-session debugger transcriptions made at the
time; the toolchain was reinstalled from the Ubuntu pool
(same versions) and all later evidence is post-rebuild
(s7f/s7g/s7h/s7i screenshots; the three relied on are
copied into docs/logic-audit-evidence/ with s7- names).

### 12.1 (a) F2 — RESOLVED: the guide is right; no separate path

Full read of $2EA92 (the price function). The merchant
doubling gate at 0x2EB3E is an **OR**, not the AND that
§3.4 recorded: `cmpi.w #$20, -$2(a6)` — merchant type
(m20) == 32 doubles unconditionally; otherwise
loc $FF0E92 & 0x3FF == 367 also doubles. §3.4's "and" is
wrong and is corrected here.

Second, #007 missed a table: the item-14 block carries
TWO modifier-match tables in the word table at $1B298,
indexed by merchant type m20 — the **high byte is the
halve-slot** (byte at $1B298 == item modifier → price/2)
and the **low byte is the double-slot** (byte at $1B299
== modifier → price×2). Merchant type 32's word is
**0xFF02**: double-slot 2 = Gems (types 10, 17, 34 also
double Gems). The guide's number now reproduces exactly:

- Gems base 200 → type-32 doubling **400** → attitude 40:
  400 − (−10·400/140) = 400 + 28 = **428** (divs
  truncates toward zero) → $1B299 match ×2 → $2EA92
  returns **856** → sell price = 856/2 = **428**, the
  guide's figure.
- Sell site verified at 0x1FB88: $2EA92(14, slot), a
  single `divs.w #2` at 0x1FB9E, then $2BBD2(1, price/2,
  0x400, leader); the item is removed via
  $2BBD2(1, −1, item·64 + slot).
- $2EA92 call-site census (jsr + bsr) is exhaustive at
  exactly 6 sites: 0x1E908 ($1E5A0 display), 0x1FB94
  (sell), 0x1FD00 (buy-check), 0x1FDD2 (buy), 0x287A4 /
  0x2897A (displays). There is no seventh path.
- Buy side cross-checks too: type 2's halve-slot is 2,
  attitude 70 → 172/2 = **86** = the guide's buy price.

**Verdict: F2 closed — no flaw and no hidden path; the
guide's 428 is the ordinary output of $2EA92 + the
sell-site halving.**

### 12.2 (b) F7 caller — RESOLVED: latent only; 0x00FF is the designed sentinel

$FF02A0 (the current-conversation/merchant index) has
exactly ONE store instruction in the ROM: 0x2A458 in
$2A454 (`move.w $8(a6), $FF02A0`). All four call sites of
$2A454:

- 0x1B72E and 0x1B8AC (new_game_init) push **#$FF
  (0x00FF)** — the reset value;
- 0x2FA08 ($2F896 save load) pushes #$FF — reset;
- 0x2A3E0 (bsr inside $2A2CA, the conversation-link
  routine) passes a zero-extended entity byte: ≠ 0xFF
  takes the entity path; 0xFF takes the reset branch at
  0x2A378.

0xFFFF can never be stored. The RAM-init image does hold
0xFFFF at $FF02A0, but new-game init resets it to 0x00FF
before any price call can run. Every other reader
(0x21FEE, 0x276FC, 0x33208) also compares against
`#$ff`. #007's 0xFFFF was the harness's own wrong
assumption, not a game state.

**Verdict: F7 closed — the merchant block cannot run
with index −1 in the shipped flow; the "bug" is latent
in a state the game never reaches.**

### 12.3 (c) Doggonia fee — no 1,000-gold fee in code; the live Doggon tax is 150

Static census, exhaustive:

- No `push #-1000` (or equivalent immediate) anywhere.
- All **45 $2BBD2 call sites** are now censused
  (31 jsr.abs + 14 jsr.pc); none passes 1000/−1000 in
  any argument. $2C474 has no callers outside $2BBD2
  internals.
- The mechanism a scripted fee would use exists and is
  data-driven: inside the conversation engine $298D2,
  0x29F28 and 0x2A0E0 execute $2BBD2(1, −(record &
  0xFFF), 0x400, leader) — take gold, amount = low 12
  bits of a conversation record word (the beggar's −50
  flows through exactly this); 0x2A10A is the matching
  give-gold command. A 1,000 fee would be a record word
  carrying 0x3E8 in Doggon XXIV's conversation data; the
  record provenance runs through a helper-filled local
  buffer (−$4(a6) in $298D2, only lea'd, never directly
  stored), so the specific record was not isolated
  statically. "Per room entry" matches no engine
  mechanism at all — charges are conversation commands,
  fired when spoken, not on room entry.

Live (clean ROM, twice): Doggon's tax posts demand,
verbatim, **"HOLT SIR! KING DOGGON DEMANDS A TAX OF 150
GOLD. WILL YOU PAY?"** Paying cost exactly 150 both
times (1000 → 850 at the harbour post, §12.10; 970 → 820
at the field post, evidence s7-tax-demand.png /
s7-tax-paid.png). Refusing means a knight fight. No
1,000-gold charge was ever observed.

**Verdict: the claimed 1,000-gold-per-room-entry fee
(the claim traces to a Genesis Temple retrospective)
does not exist in the code as stated; the real Doggon
charge is the 150-gold tax-post demand. Leaning article
error. The only static residue is the un-isolated
conversation record that would carry a scripted amount —
the engine caps such a command at 0xFFF = 4095, so a
scripted 1,000 is representable but was not found in any
traced path or observed in play.**

### 12.4 (d) Item bytes +4..+9 — RESOLVED: the records start at $D66A0, not $D66A6

#007 anchored the item records on the name field, six
bytes late. The true layout is 20 records × 10 bytes at
**$D66A0–$D6768**, and every byte is now labelled:

- **+0 byte — spawner byte**: $23B84 kind-5 spawn reads
  it as entity +0x6 := 0x200 + byte. Category values
  0–19: [6,7,7,7,7,7,7,7,7,7,2,6,3,4,6,6,5,7,0,6].
- **+1 byte — per-category message id**: the first field
  of the $26B58 records used in shop flows (sites
  0x1FD6A buy-refusal, 0x1F032 shop exit, 0x29B90 /
  0x29BF8 in $298D2). Values [68,72×9,67,68,87,86,68,
  22,86,13,47,68]; goods category 14 = 68, which is the
  literal "sold!" message id.
- **+2 byte — shop code**: matched against NPC struct
  +0x17 in the $2A454 loop at 0x2A4D2 (this is the byte
  §11.1 cited as "$D66A2+i·10"). Spells cats 1–6 =
  8,9,10,11,12,13; services 26; goods-186 = 27; crafts
  28; healing 20; drinks 25; cats 0,7,8,9,10,12,13,17,
  18 = 0 (category 13's code 0 matters in §12.11).
- **+3 byte — price-record count**: getter $2CBEA;
  loops at $2CC14 and $2F11A (0x2F5C8/0x2F5E4). Matches
  the w-column gaps 19/19; price record 124 is an
  unassigned pad between cat 9's single record 123 and
  the rings at 125.
- **+4 word — per-slot count cap**: the clamp inside
  $2BBD2 at 0x2C114; returned by $2D38C (0x2D3CE); the
  UI compare at 0x1EBE6/0x1EC5E in $1E5A0 draws the
  quantity column only when cap > 1. Goods cat 14 = 99,
  healing cat 16 = 9999 (the stacking caps).
- **+6 word — name_idx**; **+8 word — w** (price-table
  base) — as #007 had them.

In #007's $D66A6 framing, "bytes +4..+9 of record i" are
record i+1's [+0][+1][+2][+3][+4 word] — the unlabelled
bytes were the next record's head, which is why they
resisted a per-record reading.

Also from $2A454: $FF02A8 (current category) initialises
to the **0x7530 sentinel**; on a match $FF02AA = NPC
+0x24 byte and $FF02AC = NPC +0x25 byte (gate: +0x25 > 0,
tst at 0x2A4EA). The category loop does **not** break —
the last matching NPC wins (this is why code-0 NPCs land
on category 18, and why categories like 13 are reached
through BUY-menu verbs whose C operand is the category:
Goods 14 / Items 13 / Papers 17, Keys 0x69, Rings 0x66
— see §12.11).

### 12.5 (e) Party-name writes — RESOLVED: fixed template data, no creation or rename

Character names are written at spawn from template data
in $23B84; there is no name-creation or rename UI
anywhere, and save load ($2F896) restores names by block
copy. Two spawn paths write the name words:

- Encounter/character path, 0x23F52: struct +0x14 =
  word at $CECF0 + template·6 (the values 0/1/2 are
  substituted via $32FFA). **Party members are $CECF2
  templates 1–6 = name words 57 Buc, 58 Slash,
  61 Feather, 59 Mortimer, 60 Obliky, 62 Alexi**
  (6-byte template records; template 1 =
  17 04 01 00 00 3a).
- Kind-1 path, 0x23D5A: copies 6 words [+0x14..+0x1E]
  from the 24-byte template records at $CF1AC (record
  pointer = $C(a6)); records whose +0 word is 57–62:
  recs 10/11 = Alexi (62), recs 35/52/53/54 = Buc (57).

The other +0x14 writes in $2595A (0x25A58) are roster /
link slot bookkeeping — a spawned slot number written
into a group entity's +0x14 array, not a name. Name
strings live in $CD431 (16-byte entries): 57 Buc,
58 Slash, 59 Mortimer, 60 Obliky, 61 Feather, 62 Alexi,
93 Doggon XXIV, 101 NEXUS, 102 VOID, 75 Thalmus,
68 Cookie.

**Verdict: names are immutable shipped data; the only
writes are spawn-time template copies and the save-load
block copy.**

### 12.6 (f) (A,B,grp) dispatch — RESOLVED: full parameter semantics

The premise inherited from #020 — that A/B/grp map onto
$D28E codes — was wrong, and is corrected here. Verb
records are 14 bytes at $CCDB8: [10-byte name][A +0x0A]
[B +0x0B][C +0x0C][grp +0x0D]. The executor $1F296 is
entered only by $D28E command 21, and A/B/grp never
become $D28E codes. Semantics:

- **A = action-class selector.** Subtract-and-branch
  chains at $1FE8A (entry; A read from the $FFBB82
  record's +0x0A) and $20148 (after a submenu descent):
  0x42 → $1FCA4/$200D6, 0x43 → $1F9D0/$1FEF4,
  0x46 → $1F92A, 0x49 → $1F2B8/$1FFC6,
  0x4C → $1FB2E/$1FF44, 0x4E → $1F45E, 0x53 → $1F60C.
  An unlisted A descends: $FFBB82 := $CCDB8 +
  word[$FF01EA + $FFA7F8·2] (a menu-offset table held in
  RAM at $FF01EA) and re-dispatches; the final default
  falls into the C-switch.
- **B = menu state.** Copied verbatim into $FFA7F8 at
  0x1F43E, 0x1F590, 0x1F902, 0x1F9B8, 0x1FB16 ($FFA7F8:
  8 = SYSTEM panel; 0x15/0x19 = shop substates; it also
  indexes the descent offset table above).
- **grp = parameter staging class** (dispatch at
  $1F404): grp 1 → C staged to $FFBB6C; grp 3 → C staged
  to $FFBB6D (consumed at 0x20194 with the $FF0E82
  roster); grp 8 → combat verbs (target selection via
  $2CC62/$3C2F4 first). All classes share a common tail:
  selection → $FFBB70 via $2CC62, B → $FFA7F8, a
  menu-stack push via $FFBB80, back to the A-chain.
- **C** feeds the 28-case switch at $2068E on $FFBB6C
  (Bribe C=0x19, Camp C=0x1C, Diags C=0x37 — as §8).

### 12.7 (g) Q5 xref — dream solved; the death string's caller narrowed, still open

The dream texts are $DDBD8 dialogue records: master
dreams 1085–1090, **Void dreams 1091–1095** (the §9.3
line is record 1091, "Betrayer, deceiver…", pointer
0x0A164), Nexus dreams 1096+. The trigger is in Camp
$3019A (0x301AE–0x30226): the 1/3 encounter roll's
second RNG(3) picks a template ∈ {$5E, $4D, $4C} whose
$CECF0+t·6 name words are **Thalmus (75), VOID (102),
NEXUS (101)**; RNG(30)==0 picks template $4E (Cookie,
68). These are dream *visitors*, not monsters, which is
why Camp encounters never fight. P(Void dream) ≈
1/3 × 1/3 = 1/9 per Camp. $35612, once a candidate
printer, is a $32D4C-spawn + $26B58 queue wrapper (spawn
a visitor by template id and queue its greeting).

The original Q5 death string at 0x1215A ("…By a cruel
twist of fate, Void has found your party and
exterminated you in a mere ⟨n⟩ seconds…", with a numeric
placeholder byte) has **no longword/pea xref anywhere in
the ROM** — the census is negative. It sits in the
0x11F000–0x123000 formatted-text block, selected by
index rather than by address.

**Verdict: the dream half of Q5 is closed. The narrowed
remainder: which index, and which caller, selects the
0x1215A death string. Left open, precisely stated.**

### 12.8 (h) Post-harness PC=0 — DIAGNOSED: harness artifact, root cause proven

The anomaly belongs to the #007 logic harness
(tools/test_logic_harness.s; the #008 spells harness
shares the pattern) — not to tools/test_harness.sh,
which is #014's smoke script. The harness hooks 0x35C
with a **jsr** $FD0CC. But 0x35C is inside a VDP
busy-poll loop in the shipped code:

- 0x35C `move.w $C00004, d1` (the displaced instruction)
- 0x362 `btst #3, d1; bne $35C` — loop back
- 0x390 `beq $35C` — also loop back

Both harnesses exit with `jmp 0x362` **without popping
the 4-byte return address the jsr pushed**. The poll
spins at full CPU speed between VDP waits, so the stack
leaks 4 bytes per poll iteration. The numbers in §7.3
fit exactly: boot SSP (vector 0) = 0xFFEC1E; the
fault-time A7 in §7.3 was $FFD3B8 — 0x1866 = 6,246 bytes
≈ 1,561 leaked return addresses below the boot stack
pointer, down into the harness's own scratch region —
after which a corrupted return lands at 0, the CPU
executes the vector table as code, and the run freezes
on the write to 0xDFFFFE. The unmodified ROM never
faults (§7.3: a breakpoint at 0 was never hit in 8 s).
The earlier suspects — the level-up jingle via $173EC(8),
the RNG seed $FF0072, the scrubbed message records — are
exonerated. §7.3's note that the #008 harness "does not
reproduce" the fault is a run-duration/observation-window
artifact: both harnesses carry the identical jmp exit.

**Fix applied this session** (tools commit): `lea
4(%sp),%sp` before every `jmp 0x362` exit in both
harness files (four sites), with the reason recorded in
the file comments. Either that, or hook with jmp instead
of jsr — the pop is the smaller change.

### 12.9 (i) $FF012C live mapping — COMPLETE

Static profile first: $FF012C is the **current combat
action/effect code**. Direct stores at 0x37E56 (= 0x200,
in the $37D0E spell-cost routine), 0x3B4BA (= $3B1EE's
own action-code argument), 0x4283C (= 0x8C, inside the
$3E2D4 spell machine). It is read by $3B1EE's flat-damage
compares (0x8E–0x92 → 70, 0x97 → 5, at 0x3B21A+), by
$28002/$2844C (0x7D/0x7F compares), and throughout the
spell machine.

Live debugger reads (word at the even address),
2026-11-09 19:55–20:35 CST (transcriptions; screenshots
lost in the /tmp wipe, §12 preamble): **0** in the
attract/demo loop, in the starting field close view, on
the overworld, on the map screen, and in NPC
conversation (multiple reads); **0x200** during a live
random-encounter battle (read twice, 20:19:37 and
20:19:46 CST); **0x201** once on the death screen after
a knight fight (20:35:40 CST). Post-rebuild corroboration:
during session #7's later MANUAL battles the value read
**0 at the PICK menu** — it is set while an action
resolves and clears back to 0 at the pick prompt.

**Verdict: $FF012C = 0 outside combat; in combat it
holds the current action/effect code (0x200 set by the
spell system as actions resolve). The §5 question is
answered.**

### 12.10 (j) Bribe live — EXECUTED, exact traced effects

Live on the clean ROM, 2026-11-09 ~20:12 CST (debugger
transcriptions; screenshots lost in the wipe). Partner:
the Doggon tax-post **captain** at the field/gate post
(entity slot 6; $FF02A0 = 6; $FF02A8 = 0x7530 sentinel —
a guard/event NPC, not a shopkeeper). His TALK menu
(Talk/Job/Class/City/Quest/Buy/Sell/Show/**Bribe**/Fight)
was scrolled to Bribe and selected with B (in
conversations A only advances text; B picks).

- Pre-state: gold $FF02DE = **850**; captain attitude
  (slot 6, struct +0x22 at $FF040E) = **64**; +0x20 = 14.
- Buc's scripted line appeared: **"PSSST! HOW ABOUT
  10 GOLD?"**
- Gold **850 → 840** — exactly −10, the traced
  $2BBD2(1, −10, 0x400, leader) (§7.1).
- Attitude **64 → 100** — +36, the $2A22A mode-8 effect.
- +0x20 unchanged at 14. The captain's reply was the
  generic "I HAVE NOTHING MORE TO SAY ON THAT TOPIC."
  Conversation exited cleanly with C (OUT).

The same session's tax payment at that post is the
§12.3 live evidence: demand text verbatim, gold
1000 → 850 (and, post-rebuild, at the field post
970 → 820; evidence s7-tax-demand.png, s7-tax-paid.png).

**Verdict: Bribe confirmed live, gold delta and attitude
effect exactly as statically traced.**

### 12.11 Item 2(a) — the $A5 combo: CONFIRMED

On the map screen, 2026-11-09 ~19:58 CST (transcriptions;
screenshots lost in the wipe). Vehicle, labelled as in
§11: the Map was obtained on a scratch ROM copy via the
session-#6 one-byte init patch (0x2CE3D $01 → $41,
checksums re-fixed on the scratch copy only; debugger
read $FFC340 = 0x4100 confirming the grant). Pad-2
**$A5 = Start+C+Left+Up** held 1,600 ms (driver keys
h+t+j+i). Leader (slot 1) debugger reads, before → after:

- HP current $FF0304: **20 → 140 (0x8C)**
- Power current $FF0306: **1000 → 9000 (0x2328)**
- HP max $FF0308: **20 → 140**
- Power max $FF030A: **1000 → 9000**

Slot-0 fields unchanged (0/1). Exactly the claimed
effect — the fan $A5 god-mode cheat is TRUE. The map
screen was exited cleanly with B; no travel was made.
(Session #6's blocker — dying to a destination encounter
before a second map visit — was avoided by verifying
from the map-screen state directly, as the effect
applies there.)

### 12.12 Item 2(b) — genuine Map purchase: NOT completed; the chain's break is precise

The shop rule is now fully pinned (this session + §11.1):
an NPC is a shopkeeper for category i iff its struct
+0x17 byte equals the item-record shop code at
$D66A0+i·10 +2 and its +0x25 byte > 0 ($2A454 loop
0x2A4BC–0x2A540, last match wins; sets $FF02A8 = category,
$FF02AA = +0x24, $FF02AC = +0x25). **Map = category 13,
slot 6, price record 159, base price 415 gold**
($2EA92(13,6): w = 153 → record 159, raw 99 →
(99−16)·5 = 415; attitude-scaled: att 0 ≈ 563,
att 50 = 415, att 100 ≈ 267). Category 13's shop code is
**0**, so category-13 goods are not vended by a code-13
NPC: they are reached through the **BUY-menu verb
"Items" (C = 13)** inside a conversation with an NPC who
matched *some* category (i.e. any real shopkeeper, whose
conversation carries a Buy verb). The decisive in-game
test for "is this NPC a shopkeeper" is a debugger read
of $FF02A8 ≠ 0x7530 during its conversation.

Session #7 attempts (clean ROM unless noted): the City
of the Mind was reached three times pre-wipe; the tax
was paid; the captain was bribed (§12.10); live entity
slots in the city were surveyed (slots 2/3/4 at
(125,103), (126,112), (124,112); slots 5–7 were the tax
knights); every conversation actually opened — a field
NPC (slot 2) and the captain (slot 6) — read the 0x7530
sentinel, i.e. neither is a shopkeeper. In attempt E
(pre-wipe) the party reached the doorstep of the plaza
stairs-building in Mind at ~(124,110); the entry test
(B while facing the door) was interrupted by the /tmp
wipe. Post-rebuild, the beggar fight was won under
MANUAL combat (+6 XP / +20 gold — matching §9 exactly;
evidence s7-beggar-victory-manual.png), a save/restore
cycle was proven (EEPROM save south of the field:
970 gold; CONTINUE restores it — "GAME RESTORED."), and
the overland route was re-mapped, but solo Buc died
twice more (a riverbank beast hitting ~12/round; a
mutual kill with the knight Davin) before reaching the
city again. Across sessions #4/#6/#7 Buc has died nine
times on this errand; the survival lesson is that solo
Buc cannot fight the route's random encounters (beast
~12/hit, knight ~8/hit vs his 20 HP) and must travel
roads only, in short hops between saves.

**Where the chain breaks, exactly:** not at the shop
rule (fully known), not at gold (970 ≥ 563 worst case),
not at the BUY menu (Items/C=13 identified). It breaks
at *reaching a shopkeeper's conversation inside Mind
and opening it* — the building-entry test at the plaza
stairs-building (~(124,110)) and the $FF02A8 read inside
a Mind shop conversation are the two steps never yet
executed. The EEPROM save left by this session (970
gold, Buc at the field-south overworld, COMBAT = MANUAL)
loads via title CONTINUE and is the resume point.

**Verdict: purchase still open — a genuine attempt is
documented end-to-end except for its final two steps,
which are named precisely.**

### 12.13 Incidental live observations (session #7)

- **Save rule:** SYSTEM → SAVE works only on the
  overworld — inside a location close view the game
  answers "YOU CAN ONLY SAVE THE GAME WHILE OUTSIDE."
- **Battle structure (MANUAL):** a combatant's turn
  opens directly at the PICK (spell) menu; C does not
  back out to a parent verb menu, so there is no
  flee option at that level. "Buc RETREATS" in the log
  is the HOLD mood's repositioning, not flight. Enemy
  panels show truncated two-line class tags (Dunn;
  Davin "KN/KN DED"; the riverbank beast "Co…").
- **F5 footnote (observation, not a re-verdict):** after
  the beggar victory Buc's HP read 5 during the
  battle-end transition and 20 at the first post-tally
  read, and the EEPROM save written minutes later holds
  15 — the tally/XP-grant path ($2C4E2, §10.2) touches
  current HP on ordinary grants in ways the §10.2
  level-up experiment did not exercise. Recorded as an
  observation for whoever next instruments $2C4E2; §10.2's
  verdicts stand on their own experiments.
- **Evin's event is not field-bound:** the beggar event
  also fires inside the house location at overworld
  (114,130), south of the field's mountain band (paid
  50 there post-rebuild: 970 → 920).
- The captain's TALK menu is reachable both before and
  after paying the tax; the 150-gold demand repeats at
  each post independently (field post and harbour post
  are separate posts with separate captains).

### 12.14 #021 status after session #7

Closed this session: (a) F2, (b) F7, (d) item bytes
+4..+9, (e) party-name writes, (f) (A,B,grp) dispatch,
(h) post-harness PC=0 (diagnosed + harness fix applied),
(i) $FF012C live mapping, (j) Bribe live, Item 2(a) $A5
combo. (c) Doggonia fee: answered — no such fee in code;
the live charge is the 150-gold tax. Still open, both
narrowed to single steps: **(g)** the index/caller that
selects the 0x1215A Void death string, and **2(b)** a
genuine Map purchase (enter a Mind shop building; read
$FF02A8 in conversation; BUY → Items → Map). #021 stays
**in progress** on those two sub-items alone.

## 13. Session #8 — (g) SOLVED; 2(b) attempted again, break narrowed further (2026-11-09)

### 13.1 (g) The death string's caller — SOLVED: it is the fatal-error screen; there is no index and no Void timer

The §12.7 premise was wrong in two particulars, and both
errors are instructive:

1. **The string starts at 0x1215E, not 0x1215A.** The
   four bytes at 0x1215A are `4E 5E 4E 75` — FUN_00012072's
   own `unlk a6; rts` epilogue. They are all printable
   ASCII (`N^Nt`), which is why the spaced-string scan
   reported a string start four bytes early. The Russian
   patch note's 0x1215E (§12.7's aside) was correct. The
   message is two strings: part 1 at 0x1215E ("By a cruel
   twist of fate, Void has found your party and
   exterminated you in a mere "), part 2 at 0x121B2
   (" seconds. There was nothing you could do. Please
   try again with a saved game.").
2. **There is no index table and no selecting index.**
   The string's only reference is a direct PC-relative
   `pea $1215E(pc)` at **0x120F2**, inside FUN_00012072
   itself; part 2 is likewise referenced by
   `pea $121B2(pc)` at 0x12122. Every earlier census was
   negative because it searched for an absolute longword
   or `lea` to 0x1215A: wrong address, and PC-relative
   `pea` embeds no absolute address at all. (Census
   re-run this session over the raw ROM: exactly one
   `pea` — absolute or PC-relative — targets 0x1215E,
   and exactly one targets 0x121B2.)

**FUN_00012072 is the fatal-error ("Void") screen.**
`link a6,#-0xF0`; `clr.w $FF0114`; `jsr $138A8`; window /
plane setup ($11820/$11A1A/$11AE4); the message is
composed in the frame buffer — part 1 copied via $DE30
(0x120FA), the decimal of the function's own word
argument appended via $11F3A (itoa) + $DE3E, part 2
appended via $DE3E — drawn via $11624 at
(0x44,0x92,0x136,0xC7); a busy wait in $12FB4 (~40,000
iterations) follows, then a soft reset via $179B6.
Ghidra's body size for the function (236) ends exactly
at 0x1215E, which is why the "string" begins on its
boundary.

**Entry points — exactly two `jsr` sites to $12072 in
the whole ROM** (census re-run this session):

- The pass-through trampoline **$12FA0** (`link`;
  `move.w 8(a6),-(sp)`; `jsr $12072`; unlk/rts). It has
  **36 call sites**, and every single one pushes a
  compile-time constant (`move.w #imm,-(sp)`;
  verified site-by-site this session). Observed codes:
  0x15–0x1E, 0x32, 0x3C, 0x46, 0x6D–0x71, 0xC8,
  0xE6–0xEA, 0x190–0x192. Every site is an internal
  invariant/cap check — 9999 and 200 caps, −1 sentinel
  checks, and $25456's empty-slot check (code 0x1C).
- The **stack guard at 0x1224C**, reached from the
  MANX-magic + stack-range check at 0x12200
  (`cmpi.l #$4D414E58,4(a0)` against $FF000C): on
  failure it resets SP to $FFEC1E−$10, prints the
  "STACK" string at 0x12256, and calls $12072 with
  code 0x64 (100).

**Verdict.** The number displayed between "a mere" and
"seconds" is a decimal **error code**, not a duration;
there is no Void timer and no in-fiction trigger. The
screen fires only when an internal consistency check
fails and should never appear in correct play. This
also retro-explains #008's harness freeze ($25456's
empty-slot fatal path — its $138A8 VBlank wait hung
with interrupts masked) and kills the main-line §7/§21
lead ("search the 0x23000-area encounter tables and
any timer that wipes the party"): the 0x23xxx sites in
the census are invariant checks, not encounters.
(Conversely, the main line's own §8 correctly solved
the related $12072 spin loop as a harness artifact.)

**Live corroboration (negative, stated as such).** Buc
died in battle repeatedly across sessions #7–#8
(knights, the post garrison + caster, bears); every
death showed the ordinary "YOU HAVE BEEN KILLED IN
BATTLE. YOUR QUEST IS OVER. PRESS ANY BUTTON TO RESET
THE GAME." screen and never the Void text (session #8
example: docs/logic-audit-evidence/s8-deadscreen.png).
Ordinary party death therefore does not route through
$12072, consistent with the static verdict. A positive
live trigger would require corrupting internal state,
which this toolchain cannot do (the debugger cannot
write RAM, §8.4); no live confirmation is claimed.

**(g) is CLOSED.**

### 13.2 2(b) Genuine Map purchase — attempted again; still open, break narrowed to survival + one unisolated NPC

Session #7's EEPROM was recovered (BlastEm writes the
file only when the process exits; the surviving copy
materialised at that session's end — MD5
c1899430aabb015afbb79268d734b915). Title CONTINUE
restored it exactly: **970 gold, (109,130),
COMBAT = MANUAL** (evidence:
s8-restored2.png). What session #8 established live:

- **Tax paid again, and the repeat demand does not
  re-charge.** Beggar −50 (970 → 920), then the Doggon
  captain's demand paid: **970 → 820 across the two
  events** (the captain's 150 taken once; walking back
  into him re-displays the demand text but the gold
  word does not move — the per-post paid flag holds,
  refining §12.13's "repeats at each post").
- **The post captain is not a shopkeeper — the §12.12
  decisive test executed on him.** In his TALK menu
  after paying (evidence: s8-taxdone.png), the debugger
  read **$FF02A8 = 0x7530** (the sentinel; his live
  entity slot this run was 4). His BUY verb is inert.
- **Banked-save mechanics.** An in-game SAVE on the
  overworld at (111,128) (gold 870 after a third beggar
  payment, Food 1312 / Water 1728) survived a full
  emulator restart and two deaths: CONTINUE restores
  the last save exactly. BlastEm flushes the EEPROM
  file only at process exit — a SIGTERM flush preserved
  the banked save (MD5 bb04de37dac23f11be78ff213544028c);
  backups of both EEPROM states are kept with the
  session scratch.
- **Travel economy — why the road must be walked in
  close view.** Overworld (zoomed-view) travel drained
  Food 1312 → 472 over ~10 coarse cells while Water
  fell 1728 → 1458: a 3:1 ratio, i.e. each coarse cell
  costs ≈40–90 of §10.1's per-step units (−3 Food /
  −1 Water). Close-view steps cost exactly one unit.
  Also: $FF02C0/$FF02C2 read the location anchor
  (111,128) throughout overworld travel — they track
  the leader in location mode only.
- **Deaths this session (all on the road, none in
  Mind):** a knight pair at night on the y=128 road
  (knight ≈8/hit, §12.12 confirmed); the post's
  garrison (3 knights + a caster whose leader name read
  "Evin" — enemy leader names come from the shared
  name table; not the beggar) after re-approaching the
  captain post-payment; a bear pair on the east road
  (**bear hit = 12**, confirming §12.12) at HP 15 — the
  restore's stored HP. One further attempt was lost to
  a driver fault: X keyboard input to the emulator
  window died mid-battle (a Cockatrice encounter) while
  the CPU kept running (world clock advanced under the
  debugger); the instance was restarted cleanly from
  the banked EEPROM.
- **The seller is still unisolated.** Session #6's Mind
  sweep (§11.1) opened no BUY conversation in the
  Academy, harbour, warehouse or residential districts
  or "Someone's Home"; session #7 read the sentinel on
  a plaza field NPC (slot 2) and a captain (slot 6);
  session #8 adds the field-post captain (slot 4).
  Every conversation actually opened in eight sessions
  has read 0x7530.

**Where the chain breaks now, exactly:** no longer at
the building-entry test in the abstract — Buc has still
not survived the road to Mind in this session's runs
(three fatal random encounters; solo Buc at 15–20 HP vs
8–12 damage/hit pairs is the binding constraint), and
conditional on arrival, the one conversation in Mind
whose $FF02A8 ≠ 0x7530 has not been found among those
opened so far. **Exact resume recipe:** CONTINUE the
970-gold save (or the banked 870 save); Camp at spawn
until dawn first (heals toward full, skips the night
encounter table); walk the road in close view in short
hops, saving on every overworld tile; in Mind, open the
conversations sessions #6–#8 did not (roaming/plaza
NPCs rather than building banners), reading $FF02A8 in
each; the first ≠ 0x7530 is the seller — BUY →
Items (C=13) → Map at 415 base.

**Verdict: 2(b) remains OPEN** — shop rule, price,
gold, and the decisive test are all pinned and twice
executed on non-sellers; the purchase itself awaits a
survived trip and the seller's identity.

### 13.3 #021 session-line status after session #8

Closed this session: (g) — the death string's caller
(§13.1). Still open: **2(b) alone** — the genuine Map
purchase (§13.2). The session-line list is therefore
not yet empty. (The main line marked #021 done on its
own acceptance; the two lines' status/claim differences
are reconciled, with verdicts and evidence, in
docs/reconciliation-2026-11-09.md.)
# Rings of Power — logic-flaw audit (issue #021)

**Date:** 2026-11-09. **Status:** done. **Scope:** consolidate and audit
the game-logic findings of #007 (stats/XP/gold/combat), #008
(spells/skills) and #020 (main loop/state machine) against the audit
questions in `docs/overview.md`. Every question is answered **PROVEN**
or **KILLED** with an address and a trace; a suspected flaw is not a
finding until it is reproduced. Where a claim is reproduced by the
harness, the result words are cited; where it is static-only, it is
labelled as such.

**Method.** Static tracing in `disasm/rop.s` (Capstone) and Ghidra,
plus a new BlastEm harness (`tools/test_audit_harness.s`, hook at
`0x35C`, results at `$FFD004+`, 25 result words) that reproduces the
three live claims: gold overflow, negative-damage heal, `$3B4AC`
install. The #007 harness was rebuilt byte-identical (1,338 bytes,
header `0x169F`, runtime `0x7C7B5FDB`) and re-run to bisect the
post-harness PC=0 fault (Q13). **The original ROM was never modified;
all work is on copies. MD5 re-verified at the end
(`30c18fdbe2183f64702ae9f1a45d63f9`).**

**Confidence labels.** **PROVEN** = traced in the disassembly AND
reproduced by the harness (or by a decisive call-site proof).
**CODE-VERIFIED** = traced end to end in the disassembly, no harness
run (the path is not reachable from the attract hook, or is a
dispatch-level map). **KILLED** = the suspected flaw does not exist,
with the evidence that rules it out. **OPEN** = not located; the
narrowed leads are given, not a claim. Player-observed (fan-site)
claims are labelled as such and never treated as code evidence.

**Deliverables.** This document; `tools/test_audit_harness.s` (25/25);
the `rts` hook-exit fix applied to all three harness sources (Q13);
corrections to `docs/architecture.md` (EEPROM labels, `$12FE8` map),
`docs/overview.md` (audit list, EEPROM labels, debug mode) and
`docs/logic.md` §7.3 (Q13 resolution).

---

## 1. The audit questions — verdicts

| # | Question (docs/overview.md) | Verdict |
|---|---|---|
| 1 | Save checksum: catches corruption, or accepts predictable patterns? | **WEAK, and the result is never used** (§5) |
| 2 | Overflow in XP/gold/stats arithmetic? | **YES — gold** (PROVEN, reproduced §2). XP: no. Negative damage heals (PROVEN, reproduced §3) |
| 3 | Joypad queue drops / 3-frame debounce eats presses? | **Queue semantics PROVEN** (§19). Mashing overflow unmeasured in live play — OPEN |
| 4 | Combat/spell divide-by-zero, unsigned underflow? | **One divide-by-zero hazard PROVEN** (`$1E3B0` / `$FF0E18[2]`, §4); no other found in the traced paths |
| 5 | Void death message: trigger and timer? | **Text located; trigger NOT located** — OPEN (§7) |
| 6 | Unreachable code / dead routines; is debug mode reachable? | **Debug mode IS reachable** (§6). Format string dead; `$EB7C8` dead; `$3A84C` block dead |

---

## 2. Gold overflow — PROVEN, reproduced (audit Q2)

**Finding.** The gold handler `$2C474` (`0x2C474–0x2C4DE`) clamps
with **signed** 16-bit compares. Any `gold + amount` in
`(32767, 65535]` wraps negative, skips the 15000 cap, and is then
zeroed by the floor check. Gold 15000 + 20000 → **0** (not 15000,
not 35000).

**Trace.** `$2C474`: `d1 = gold + amount` (16-bit add, wraps);
`cmp.w #15000, d1; ble skip-cap; d0 = 15000` — the `ble` is taken
when the wrapped sum is negative (the subtraction `d1 − 15000`
overflows, N≠V), so the cap is skipped; then `tst d1; bge keep;
d0 = 0` — the wrapped sum is negative, so gold is set to 0.
Both compares are signed; the code has no unsigned-overflow guard.

**Harness reproduction** (`tools/test_audit_harness.s`, via `$2BBD2`
code `0x400`, slot 0 type 4, +0x27=0):

| gold | +amount | 16-bit sum | result | expected |
|---|---|---|---|---|
| 15000 | 17767 | 32767 (no wrap) | **15000** | 15000 (cap) |
| 15000 | 17768 | 32768 → −32768 | **0** | 0 (overflow) |
| 14000 | 20000 | 34000 → −31536 | **0** | 0 (overflow) |
| 15000 | 20000 | 35000 → −30536 | **0** | 0 (overflow) |

All four match. The boundary is exactly at 32768: 15000+17767 caps
normally, 15000+17768 zeroes. **25/25 harness run, result words
[0..3].**

**Reachability (player-observed vs code).** Likely **unreachable in
normal play**: the largest realistic single gold add is ~4500 (a
high-value sale); battle-end gold is ≤ ~2000; 15000+4500 = 19500 <
32767. No in-game path adds > 17767 gold at once (the biggest single
add the code can produce is bounded by the price table — max scaled
price 9000, and the sell path halves it). So this is a real mechanism
with no known in-game trigger. **Remake note:** clamp with unsigned
compares, or clamp the addend before the add.

**XP cannot overflow.** XP cap 13000, level thresholds ≤ 12800, and
the largest single XP grant is the battle-end per-person share
(clamped [1,50]) — no XP add can push a 16-bit sum past 32767.
**Stat overflow:** attack/defence are 5-bit fields (0–31) in the
+0x28 stat word; the damage formula's intermediate (`atk·base>>5`)
fits in 16 bits for the maxima in the tables (base ≤ 140, atk ≤ 31
→ 31·140 = 4340). No stat overflow found.

---

## 3. Negative damage heals — PROVEN, reproduced (audit Q2)

**Finding.** `$3B1EE` (damage, `0x3B1EE–0x3B3EA`) has **no damage
clamp**. If the computed damage is negative, `sub.w d0, $1C(a0)`
*adds* HP to the target — a weak attack against a heavily-defended,
high-modifier target **heals** it.

**Trace.** `$3B1EE` tail (`0x3B2EC–0x3B3EA`): the rank switch (rank
7/8 → `(level+1)·2` at `$3B30C`, rank 9 → `level+1` at `$3B32E`,
else `dmg/3+1` via `divs #3` at `$3B34E`), then the immunity checks
(both sides `struct[+0x27].+0x02 == 0x4D` → skip), then
`sub.w d0, $1C(a0)` — no `tst`/clamp on d0 before the subtraction.
`divs` truncates toward zero, so −21/3 = −7, and −7+1 = −6.

**Harness reproduction** (`$3B1EE(0, 1, 140)`, attacker atk 0 /
mod 0 / rank 1, target def 31 / mod 3 / HP 100):

```
d0 = atk·base>>5 + base − def·base>>5 + 0 + attmod·base>>4 − tgtmod·base>>4
   = 0·140>>5 + 140 − 31·140>>5 + 0 + 0 − 3·140>>4
   = 0 + 140 − 135 + 0 + 0 − 26 = −21
rank 1 → −21/3+1 = −7+1 = −6
target HP = 100 − (−6) = 106
```

Harness result words [4..6]: d0 = `0xFFFA` (−6), HP = **106**,
`$FFC380` = −6. Control (same, target mod 0): d0 = 2, HP = 98,
`$FFC380` = 2 (words [7..9]). **All match.**

**Reachability.** The minimum-damage case needs atk 0, def 31,
base 140, target modifier 3 — the extremes of the tables. A
low-attack character (atk 0–2) hitting a max-defence (31) target
with a high base (140, the top of the rank tables) and modifier 3
can produce negative damage in real play, but it requires the
attacker to be near the bottom of the attack range *and* the target
near the top of defence. It is a real edge case, not a routine
occurrence. **Remake note:** classic mode must reproduce the
negative-damage heal; fixed mode should clamp damage at 0 (or at 1,
matching the `dmg/3+1` floor the code clearly intended).

---

## 4. `$3B4AC` and the `$FF012C` flat-damage codes (audit Q9)

**Finding.** `$3B4AC` (`0x3B4AC–0x3B4C6`, the action-code setter)
stores the **full word, no masking**: `cmpi.w #7, $FF012C; beq
skip; move.w $8(a6), $FF012C`. So `$FF012C = 0x87D` stays `0x87D`.
`$3B1EE`'s flat-damage checks are **word** compares (`0x8E–0x92` →
70, `0x97` → 5, at `0x3B21A–0x3B25C`). The exact flat codes come
from two sources: +0x24 spell selectors, and rank-table record
`w1>>4` values that are exactly `0x8E`/`0x91`/`0x97` (rank-5 recs
19/20 `w1=0x08E8` → `0x8E`; rank-1 recs 19/20 `w1=0x0918` →
`0x91`; ranks 2/3/4/6 recs 19/20 `w1=0x0978` → `0x97`). Record
values `0x87D`/`0x87E`/`0x87F` do **NOT** trigger flat damage in
`$3B1EE`. `$FF012C` is sticky across turns, so a melee after a
top-spell cast can deal flat 70/5.

**Harness reproduction** (result words [10..12]): `$3B4AC(0x87D)`
→ `$FF012C` = `0x87D` ✓; `$3B4AC(0x08E)` → `0x08E` ✓; guard:
`$FF012C` was 7, `$3B4AC(0x50)` → `$FF012C` stays **7** (refused
while == 7) ✓.

**Message gating.** The message routine at `0x2844C` uses **word**
compares `$FF012C == 0x7D`/`0x7F` for "<name> lost/got <N> max pts"
(strings at `$295CE`/`$295D5`, amount `$FFC380`), gated by
`$FFC380 > 0` — so only the exact `0x7D`/`0x7F` (from +0x24
selectors) print it, not the `0x87D` record codes. `$37D0E`'s tail
sets `$FF012C = record.w1 >> 4` (0 → `0x200`) and `$FFC37C =
$FFC37E = -1` unconditionally.

**`$FF012C` code map (from #008, confirmed here where marked).**

| code | meaning | source |
|---|---|---|
| 0x07 | locked/busy (blocks `$3B4AC` writes; `$3A62E` refuses the spell branch while set) | #008 |
| 0x22 | giant-function state code | #008 |
| 0x50 | "special" (from +0x24 == 0x50) | #008 |
| 0x7D | max-HP loss (message + `$4087E` path) | #008 + §9 |
| 0x7F | max-HP gain (message + `$40A72` path) | #008 + §9 |
| 0x8E–0x92 | flat 70 damage in `$3B1EE` | #007 + this audit (harness) |
| 0x97 | flat 5 damage in `$3B1EE` | #007 + this audit (harness) |
| 0x87D/0x87E/0x87F | rank-table record codes; do NOT trigger flat damage | this audit (harness) |
| 0x200/0x201 | giant-function cases (`$40E22`/`$40EDC`) | §9 |

---

## 5. Save validation — WEAK, and the result is never used (audit Q1)

**Finding (CODE-VERIFIED).** `$4323C` (`0x4323C–0x43338`) validates
the 128-byte buffer at `$FF016A` with a **1-byte sum + complement**:

- `byte[127] == sum(bytes[0..125]) & 0xFF`
- `byte[126] == ~sum & 0xFF`
- `byte[127] == ~byte[126]` (redundant given the first two)

Error count in d1; `d1==0` = valid. So the checksum catches
single-bit corruption, but **any 126 payload bytes + 2 recomputed
check bytes pass** (100% of computed forgeries, 1/65536 random).
This is a forgery-grade weakness, not a robustness issue.

**The result is never used (CODE-VERIFIED, decisive).**
`$FF0168` (the validation result) is **never read by any code** —
only 3 references in the whole ROM, all writes inside `$4323C`
itself (`0x43240` clr, `0x432B6` =1 for the `$E0` clear-path,
`0x432F6` =-1 for failure). Entry at `0x30C` ignores `$4323C`'s
return value and resets the stack (`movea.l #0, a7`). A corrupt
save is **never rejected at boot**; the real Load handler (C=81 →
`0x20652`, calls `$2F896`) never checks `$FF0168` either.
(Corrected in #019: the original text here said "C=14 →
`0x202CC`" — case 14 is the 'Goods' shop verb, not Load; see
`docs/save.md` §6.)

**Pad-2 combos (CODE-VERIFIED).** `$E0` (B+C+Start on pad 2) at
boot → `$FF0168=1`, buffer zeroed, `$FF01E8=$FF`, fill loop via
`$430F4` (the **write** — see the EEPROM correction below). `$B0`
(A+C+Start) is also compared at `0x432AE`/`0x43304`/`0x4331C`;
combo-held paths go to `0x4333A` (SR=`$2700`, VDP display-off writes
`$8004`/`$8104`/`$8200`…).

**EEPROM labels — CORRECTED (this audit).** #003 had `$43012` and
`$430F4` swapped. Full disassembly proves:
- **`$43012` (`0x43012–0x430EC`) = EEPROM READ (block)** — a0=buffer,
  d0=address, d1=count; sends 8 command bits via `$42EBA` with
  `or.w #1` in the command word (the read bit), ACK via `$42F96`,
  then 8× `$42EEE` bit-in loop, `move.b d0, (a0)+`, loops `$FF015C`
  times. **Proof by call site:** boot validation calls
  `$43012(d1=$80, a0=$FF016A)` then validates the buffer — if it
  were WRITE, boot would destroy the save every time.
- **`$430F4` (`0x430F4–0x431D2+`) = EEPROM WRITE (one byte)** —
  a0=src, d0=address; sends command via `$42EBA` without the
  `or #1`, ACK, then `move.b (a0), d0; lsl #8; $42EBA` ×8, then
  write-cycle delay loop (`move.w #$1518, d0; dbra`). **Proof by
  call site:** the clear-save loop calls `$430F4` 128× with a0
  advancing through the zeroed buffer — must be WRITE.

Corrections applied to `docs/architecture.md` (~line 596) and
`docs/overview.md`. Chip identity is still unconfirmed (#019).


## 6. Debug mode — REACHABLE; format string dead (audit Q6)

**Finding (CODE-VERIFIED).** The debug mode **is reachable** from
the SYSTEM menu. The debug format string is **dead data**.

**Reachability trace.** "Diags" strings: `0x27548` ("Diags On"),
`0x27551` ("Diags Off"), `0xCD038` (SYSTEM menu table). Options
renderer `$26F00` (`0x26F00–0x26FDC`) draws Help/Direct/Lefty/Righty/
Diags On/Off/Combat/Manual lines via `$1113C`, reading flags
`$FF0116` and `$FF0134`. System menu (verb table continuation past
`0xCCFF0`, at ~`0xCD000`): SYSTEM header then
Load/Save/Combat/Direct/Diags/Music/Help/Quit. `$1F296` case C=54
(`0x36`, Diags) → `0x205BC` toggles `$FF0134`; C=55 (`0x37`,
Combat) → `0x205D8` toggles `$FF013A` (manual/auto combat mode —
the flag #007 could not locate); C=20 (`0x14`, Direct) → `0x203C6`
toggles `$FF0116`; C=18 (`0x12`, Help) → `0x20370` toggles `$FF0132`.

**`$FF0134` is persisted in the save buffer** (save routines at
`0x2F256` push it, `0x2FA90` restore it, via `$2F082`/`$2F0D0` to
`$FFA800`). Its live effects: D-pad decoder branches at `0x13030`
and `0x130B6` (Diags on → extended selection mapping, d6 up to 4 via
jump tables at `0x13052`/`0x13078`; off → forced d6=4 on one path).
`$FF0134` is read in exactly 6 places (`0x13030`, `0x130B6`, `0x205BC`
toggle, `0x26FB6` renderer, `0x2F256` save, `0x2FA90` load) — **no
per-frame debug-display routine reads it**. So "Diags" is a real,
reachable, persisted toggle whose only live effect is the input
decoder's extended mapping; there is no on-screen debug display.

**Format string dead (high confidence).** The debug format string at
`0x23934` ("N^NuSp:%i Dir:%i Ac:%i St:%i Dr:%i\n") has **no
references**: no longword pointer `0x00023934` anywhere in ROM, no
PC-relative/immediate reference in `disasm/rop.s`. A
computed-address reference cannot be fully excluded statically, but
none was found. It is dead data left from development.

**Other dead code (CODE-VERIFIED).** `$EB7C8` (stop-sound) is dead
code, **zero callers** (it is the routine the music-off patch calls
— the patch revives it). The `$3A84C` damage-apply block in `$3A62E`
is dead (runs only when attacker max HP < 0 — never for valid
chars). The `$3A62E` → `$3B1EE` call at `0x3A842` passes three
separate word args (attacker +0x22/+0x1E/+0x20 as attacker idx,
target idx, base) — the #008 doc's "packed 32-bit pair" claim about
this was wrong and was corrected before the #008 push.

---

## 7. Void death message — text located, trigger NOT located (audit Q5)

**Finding (OPEN).** The spaced string at ROM `0x1215A`
(`disasm/text/spaced_strings.txt`, confirmed in
`disasm/text/README.md`): "By a cruel twist of fate, Void has found
your party and exterminated you in a mere \x00 seconds. There was
nothing you could do. Please try again with a saved game." (The
Russian patch note also cites the Void message at `0x1215E`.)

**What was searched.** No longword pointer to `0x1215A` in ROM and
no `lea $1215a` in `disasm/rop.s` — the reference mechanism is
unknown (likely a 16-bit offset table or a computed address). The
trigger routine and the timer were **not located**. No routine was
found that writes a countdown, compares it to a Void threshold, or
branches to a party-wipe on a timer expiry. **This is an honest open
item, not a finding.** Leads: the `$FF0E16` step-counter readers are
save-serialisation code, not a Void timer (§14); the verb/encounter
tables in the `0x23000` area (which call the terrain decoder,
§13) are the next place to look for a random-encounter timer.

---

## 8. The `$12072` spin loop — SOLVED, harness artifact (audit Q2)

**Finding (CODE-VERIFIED).** `$12072` (`0x12072–0x120F0+`) is **not**
a spin loop: it calls `$138A8` (menu-display formatter), which
calls the VBlank-wait `$1386A` at `0x13CAA` (sets `$FF0016=-1`,
polls `move.w $FF0016, d0; bne $13876` until the VBlank handler
`0x1272` clears `$FF0016`), then `$11820`/`$11A1A`/`$11AE4`
(text/tile/palette draws). `$25456` (`0x25456–0x25576`) calls
`$12FA0(0x1C)` → `$12072` exactly when the slot's type low nibble
is 0 (empty slot: `struct[idx].+0x00 & 0xF == 0`); otherwise it
applies bit-field updates to +0x00 (args `$C`/`$E`/`$10`/`$12` →
bits 4–7, 10–11, 12–13, 14–15).

**Why the harness froze.** The attract loop (`0x35C–0x390`) polls
`$C00004` VDP status bit 3 and joypad `$3AA` directly; SR stays
`$2700` (set at boot `0x308`, no SR=`$2000` before attract) so
VBlank interrupts are masked and `$FF0016` never clears → the
`$1386A` wait inside `$138A8` spins forever **in the harness context**. In real gameplay
interrupts **are** enabled (SR=`$2000` sites at `0x1266`, `0x1382`,
`0x138E`; the VBlank handler fills the joypad queue gameplay depends
on), so the empty-slot branch is benign. **This was a harness-context
artifact, not a game bug.** `$12072`'s only 2 callers: `0x1224C`
and `0x12FA8` (via `$12FA0`).

---

## 9. Giant function `$3E2D4` block selection — MAPPED (audit Q1)

**Finding (CODE-VERIFIED, dispatch level).** Entry (`0x3E2D4`):
clears `$FF010E` bit 13, actor = `struct[$FF0EAA]` → `-0x1C(a6)`,
d0 = `$FF012C` → `bra $42CFE`. **Dispatch at `$42CFE`
(subtract-and-branch chain on `$FF012C`, ~50 cases):**

| `$FF012C` | target | note |
|---|---|---|
| 7 | `$410D2` | locked/busy |
| 24 | `$41230` | |
| 25 | `$415E2` | |
| 26 | `$3E366` (`jsr $38C5A`) | |
| 27 | `$3E370` | |
| 28 | `$3E37A` | |
| 29 | `$3E7CC` | |
| 30 | `$3EA12` | |
| 86 | `$3E398` | |
| 87 | `$3E78A` | |
| 88 | `$3EBDA` | |
| 89 | `$3ED1A` | |
| 90 | `$3EE60` | |
| 91 | `$3EF8A` | |
| 92 | `$3F0B4` | |
| 93 | `$3F208` | |
| 100 | `$3E304` (`$FF012A` step: <4 → ++ else clear) | |
| 101–102 | `$3F352` | |
| 103 | `$3E320` (`$FF012A++`) | |
| 104 | `$3E32A` (`$FF012A=0`) | |
| 105 | `$3F492` | |
| 106–107 | `$3F352` | |
| 110 | `$3F5F4` | |
| 111 | `$3F622` | |
| 112 | `$3F676` | |
| 115 | `$3F6E2` | |
| 116 | `$3F86C` | |
| 117 | `$3FC30` | |
| **124** | **`$40A0E` (revive)** | |
| **125 (0x7D)** | **`$4087E` (max-HP loss — the 0x40880 path)** | |
| 126 | `$40BAA` | |
| **127 (0x7F)** | **`$40A72` (max-HP gain)** | |
| 140 | `$400A0` | |
| 141 | `$4039C` | |
| **142–146 (0x8E–0x92)** | **`$39A34`/`$39BE0`/`$39C8A`/`$39D34`/`$39E9E` (five spell-effect subroutines)** | |
| 149 | `$40DD4` | |
| 150 | `$3E384` | |
| 151 (0x97) | `$3E38E` | |
| 160 | `$40CDC` | |
| 512/513 (0x200/0x201) | `$40E22`/`$40EDC` | |
| fall-through | `$41EB4` (`$FF012C` `$800`/`$1000` compares) | |

Each block ends `bra $42E30` → `bra $3E418` (common tail).
`$FF012A` state compares seen in the effect blocks
(`$39xxx`/`$3Fxxx`): 1, 6, 8, 9, 16, 20, 24, 30, 31, 41, 50, 58, 70
— per-block step values, **not** a single ≥22 threshold (the brief's
"state ≥ 22" was approximate; superseded). The loss/gain/effect
blocks are identified at dispatch level; the per-block internals
(the 0x40880 max-HP path's arithmetic, the five `$39xxx` spell
effects) are **not** fully traced — open, narrowed to the addresses
above.

---

## 10. `$3A62E` and the combatant setup — Q4 SOLVED (audit Q4)

**Finding (CODE-VERIFIED).** `$3A62E` (`0x3A62E–0x3A848`):
attacker = `struct[arg]`; `-$A(a6)` = attacker.+0x1E (target idx;
−1 → exit); if +0x24==`0x50` → `$3B4AC(0x50)`, `$FFC418` = +0x1E,
`$FFC41A` = +0x22, `$FF012A`=1 (spell branch); else target =
`struct[+0x1E]`; enemy-table check
`$FFB0D0[target.+0x04*12]` >= `0x24` → exit; `-$12(a6)` =
`$1E0A4(attacker.+0x0A)`; `-$14(a6)` = +0x20; `-$16(a6)` = +0x24;
if +0x24!=0 and `$FF012C`!=7 and target.+0x2C bit 15 clear →
`$3B4AC(+0x24)`, `$FFC418`/+0x22 as above, `$FF012A`=1; if
target.+0x2C bit 15 set and +0x20>=0 → `$23AE0`, `$25DE4`,
`$2140A` (with the opposite direction); melee path
(attacker.+0x18!=0 and +0x24==0):
**`$3B1EE(attacker.+0x22, attacker.+0x1E, attacker.+0x20)`** —
i.e. arg1 = +0x22 (attacker idx), arg2 = +0x1E (target idx),
arg3 = +0x20 (base). Dead block at `0x3A84C` (only if +0x20 < 0)
confirmed dead.

**The +0x1E/+0x22 puzzle — SOLVED by `$2B240`.** `$2B240`
(`0x2B240–0x2B2AC`) re-initialises a combatant's fields from frame
args, **overwriting** the party-context Power/HP values: +0x14 =
`$C(a6)`, +0x16 = `$C(a6)`, +0x18 = `$E(a6)`, +0x1C = `$A(a6)` (cur
HP), **+0x1E = `$14(a6)` (target idx), +0x20 = `$16(a6)` (damage
base), +0x22 = `$8(a6)` (self char idx)**, +0x24 = `$18(a6)` (spell
selector), +0x26 = `$12(a6)`, +0x28 = 0; if `$12(a6)==0x1F` then
+0x1A = `0x1F`; calls `$243D6(idx)` first. Siblings
`$2B3B0`/`$2B4B0`/`$2B5B0` are the same shape with different arg
mapping (+0x1E = `$A`/`$16`, +0x20 = `$16`/`$18`, +0x22 NOT written
in `$2B3B0` — it writes +0x24 = `$18(a6)`, +0x26 = `$14(a6)`,
+0x28 = 1). **So the 52-byte struct is dual-purpose: party stats
outside combat, combat state during combat — `$2B240`'s overwrite
is what makes `$3A62E`'s index reads safe.**

**Entry mechanism — OPEN.** The `$2B240` family has **no**
jsr/jmp/longword-pointer references anywhere in ROM (byte-searched
for `4E B9`/`4E F9` + address, and struct-packed longwords — none)
and `$2B240` starts without its own `link` (it shares the caller's
frame). `$2BBD2` (`0x2BBD2–0x2C8F2`) dispatches on code/64 (major,
`-2(a6)`) and code%64 (minor, `-4(a6)`); type 4 redirects via +0x27,
type 1 direct; `$2B402` and `$2B5F4` **are** jsr-called (from spell
routines `0x38D9E`/`0x38F6C`/`0x39104`/`0x39396`/`0x396CE`/`0x3FF20`/
`0x3FF76`/`0x3FFCC`/`0x40022`/`0x41070` and new-game init `0x1B75A` /
`0x2F904`). `$2B5F4` loops the `$D601E` table (`0xA1` then `0xB8`
entries) via `$2B68C`. The most likely entry is a computed jump
through the `$2BBD2` dispatch (a jump table whose entries are not
visible as plain longwords) — open, narrowed to the `$2BBD2`
major/minor dispatch and the party-join call sites.

**`$1E0A4` helper — SOLVED (audit Q14).** `0x1E0A4–0x1E0E2`:
jump table at `0x1E0C6`, input d0 (attacker.+0x0A): 0→2, 1→3, 2→0,
3→1, 4→4, ≥5 → returns the input unchanged (no `moveq` runs on
that path — it branches straight to `unlk; rts`). Clean opposite
pairs (0↔2, 1↔3, 4 stays) — a
**direction-reversal lookup** used in `$3A62E`'s pre-check.


## 11. `$1F296` verb executor and the `$12FE8` command map (audit Q8)

**Finding (CODE-VERIFIED).** `$1F296` head reads `$FFBB82`
(current menu record), byte +0xA → `bra $1FE8A`: first switch on A
(`0x42`→`$1FCA4`, `0x43`→`$1F9D0`, `0x46`→`$1F92A`, `0x49`→`$1F2B8`,
`0x4C`→`$1FB2E`, `0x4E`→`$1F45E`, `0x53`→`$1F60C`; else fall to
`0x1FEB8` which reloads the record via `$FFA7F8` index into `$CCDB8`
and takes byte +0xA → `bra $20148`). Second switch at `0x20148` on
the same byte (`0x42`→`$200D6`, `0x43`→`$1FEF4`, `0x49`→`$1FFC6`,
`0x4C`→`$1FF44`; else `0x20162`: d0 = `$FFBB6C` (the C byte) →
`bra $2068E`). **`$2068E` dispatch on C (subtract-and-branch chain,
full map):**

| C | target | note |
|---|---|---|
| 8 | `$2027E` | |
| 13 | `$2029E` | |
| 14 | `$202CC` | 'Goods' shop verb (calls `$2A22A`/`$298D2`) — **not** Load (corrected in #019) |
| 15 | `$202FA` | **not** Save (corrected in #019) |
| 16 | `$2031C` | |
| 17 | `$20332` | |
| 18 | `$20370` | `$FF0132` Help toggle |
| 19 | `$2038C` | |
| 20 | `$203C6` | `$FF0116` Direct toggle |
| 21 | `$203E8` | |
| 22 | `$2040C` | Music |
| 23 | `$20430` | |
| 24 | `$20462` | |
| 25 | `$20466` | |
| 27 | `$204CA` | |
| 28 | `$204CE` | |
| 50 | `$204DC` | |
| 51 | `$20514` | |
| 52 | `$2054C` | |
| 53 | `$20584` | |
| 54 | `$205BC` | **Diags `$FF0134` toggle** |
| 55 | `$205D8` | **Combat `$FF013A` toggle** |
| 56 | `$205F4` | |
| 80 | `$2063C` | Music |
| 81 | `$20652` | **Load** — calls `$2F896` (corrected in #019; was mislabelled as case 14) |
| 82 | `$20670` | **Save** — calls `$2F11A` (corrected in #019; was mislabelled as case 15) |
| 100 | `$20194` | |
| 101 | `$201EA` | |
| 102 | `$20226` | |
| 105 | `$20252` | |
| 254 | `$20188` | **`$FF00BE`=-1, quit/reset** |

Verb record = 14 bytes [10-byte name][A][B][C][grp]; header = 12
bytes [10-byte name][A][grp]. **B = submenu group id** (main-menu
"System" trailer `[00 08 00 01]` → B=8 → SYSTEM grp-8 submenu).
**C = the `$1F296` case code.**

**`$12FE8` command production — CORRECTS #020 (CODE-VERIFIED).**
`$12FE8` (`0x12FE8–0x13650`) writes the `$FF0240` command byte
from the **button pressed + mode flags**:

| button | command |
|---|---|
| D-pad only | 10 (when selection returns to 4 / `$FF0086==4`) or 0 |
| A (bit 4) | 21 (if `$FF00AC`) / 30 (if `$FF00AE==1`) / 35 (otherwise), plus 40/0 variants |
| B (bit 5) | 22 (if `$FF00AC`) / 50 (if `$FF00AE==1`) / 55 (otherwise) |
| C (bit 6) | 37 (if `$FF00AC`) / 45 (if `$FF010E` bit 0) / 40 (selection changed) / 0 |
| Start (bit 7) | 20, and combos 24 (Start+C, selection byte 6) / 25 (Start+A or Start+B) |

`$FF00AE` (1/2) is the input mode flag (set 1 at `$D29E` each
`$D28E` iteration; set 2 at `0x1DC1C`, back to 1 at `0x1DE6A`).
**Command 23's writer NOT found** (no literal `move.b #$17, -4(a6)`
in `disasm/rop.s`) — OPEN. `$D28E` switch is on the `$FF0240`
command byte (copied into the `$D28E` frame at `-4(a6)`); verb C
codes are NOT `$D28E` codes — the bridge is `$D28E` case 21 →
`$1F296`, which dispatches on the selected record's C byte. `$D328`
writes command 10 in the `$FF0128` path; `$D43E` clears the command
to 0 when a message is pending (unless command is 0/37/40) and calls
`$17586(-1, 0x14)`. `$D28E` case handlers (from #020's
`d28e_switch.txt`, re-verified): 0→idle, 10→`$1EEEE`, 20→`$1E3B0`
(message push), 21→`$1F296`, 22→`$207D8`, 23→`$1E5A0`,
24→`$20884`, 25→`$20A36`, 30→`$265BE`, 35→`$2A562`,
37→`$26CCA`+`$17586(0x11,-1)` confirm, 40→`$2AFF2`,
45→`$FF0138`=-1 inline, 50→`$2619C`, 55→`$32C18`/`$26A8C`/`$2AD64`.

Corrections applied to `docs/architecture.md` (the `$12FE8`
"only command 0 or 37" note) and `docs/overview.md`.

---

## 12. Terrain decoder entry and `$FF1EC0` consumers (audit Q7)

**Finding (CODE-VERIFIED, narrowed).** The `$DF58` table has 16+
longword entries alternating `$E3E2`/`$E43C`. Entry is
**fall-through**: the outer driver at `0xE358` (4 word args from
stack `$4`/`$6`/`$8`/`$A`) walks a table (`movea.l (a1,d4.w), a0;
adda.l #$603E4, a0`) and at `0xE3B0` does `tst d3; bne $E412`
else falls into `$E3B4`. **Stream source is `0x603E4` + table
offsets (~`0x60400+`), NOT the `0x044000–0x05FFFF` block** — that
#006 prime suspect is **killed** for the terrain stream. `$E358`
callers (jsr `$E358.l`): `0x1BC1A`, `0x1BC3C`, `0x1BC84` (new-game
init area) and `0x23234`, `0x2326C`, `0x2329E`, `0x232C6`,
`0x23346`, `0x233A6`, `0x2342C` (`0x23000` area).

**`$FF1EC0` is a shared decode scratch buffer:** cleared by `$11DE8`
(`0x19E0` longwords of 0), written by `$1383C` (map decode: `pea
$FF1EC0; push index; pea $96120; pea $9638C; jsr $13654`, returns
a0=`$FF1EC0`) and by the threaded terrain decoder (a4=`$FF1EC0`).
**Bitmap consumers still not located** (read via pointers — prime
suspects `$1C21A` movement and `$32C56`). The walkable
terrain grid itself is still not located as a data structure; the
decoder and its entry are now understood, the consumers are the
remaining gap.

---

## 13. Food/water consumption — NOT located; leads killed (audit Q6)

**Finding (OPEN, leads killed).** The transport/food-water
consumption routine is still not located. The strongest remaining
leads from #007/#020 are **killed**:

- `$2F1F0`/`$2FA2A`/`$302F0`/`$2EC80` (`$FF0E16` "readers") are
  **save serialisation code** (push `$FF0E16`, `$FF0116`,
  `$FF0132`, `$FF0134`, `$FF013A` into the `$FFA800` save buffer via
  `$2F082`) — not consumption.
- `$32C56` (`0x32C56–0x32D0A`) is a **4-direction tile scan**
  (loops 0–3, calls `$269F2` and `$253FE` per direction with the
  leader's position, records the first direction where `$253FE`
  returns nonzero) — not consumption.
- `$170DA` is a **palette** routine, not consumption.
- The `$2BBD2` codes `0x380`/`0x381` (food/water goods slots 0/1)
  are **inventory-count codes** (`$2C8F2`), not consumption.

The guide's transport rates (Path 1/1, Grass 4/2, Desert 7/5,
Swamp 8/4, Ice 4/3, Boat deep 5/20, Dragon 40/40) stay
**hypotheses** (player-observed, fan-site) until a routine is
found. No byte/word/interleaved table for those rates exists in
the ROM (searched). Next leads: the `$FF0E16` step-counter
consumers in the `$2155E` tick path other than the save code, and
the `$32C56` position-based call's callers.

---

## 14. +0x14 party names 57–62 (audit Q5)

**Finding (CODE-VERIFIED, call chain OPEN).** Writers of +0x14
(the name index):

- `$23B84` template copy (template word 0 → +0x14) — but the
  new-game leader is created with **template 0** ("Man", name 1),
  not Buc (57), and Slash/Mortimer/Obliky/Feather (58–61) do not
  appear in templates 0–199 at all.
- `$2B240` family frame-arg writes (+0x14 = `$C`/`$E`/`$16(a6)`
  per sibling) — the combatant-setup path.
- Small-constant writes at `0x19632` (#4), `0x1CCEC`/`0x1CD5A`
  (#4), `0x1D060` (#`$FF`), `0x1D684` (#2), `0x1D7F0` (#1).
- `0x2311C` (`move.w $16(a0), $14(a1)` — copies +0x16 → +0x14
  between structs, inside the `0x23138` `$3A62E`-caller routine).

**The specific call chain passing 57–62 into `$2B240`'s `$C(a6)`
is not traced** — OPEN, narrowed to the `$2BBD2` major/minor
dispatch and the party-join call sites. The leader's name must be
set after `$23B84` (by `$25456`/`$243D6`/`$2CDD4` or by the
intro/story flow), or the party joins later. `$243D6`
(`0x243D6–0x24474`) is a position helper (copies X/Y +0x0C/+0x0E
to +0x10, calls `$20D9E(X, Y, &d4, &d5)`, bounds-checks 0 < d4 ≤
10 and 0 < d5 ≤ 10, returns `0xFF` if out) — **not** the +0x14
name writer. `$25456` sets +0x00 flag bits from args (`$C` →
bits 4–7, `$E` → bits 10–11, `$10` → bits 12–13, `$12` → …; each
−1 = skip) — also not the name writer.

**Settled (from #020, restated):** the six disciplines ARE named
in ROM (PARTY menu: Sorc/Knight/Archer/Necro/Enchnt/Conjur — verb
table `0xCCDB8`, grp 2, C=0–5). "Archer" exists as a discipline
name; the character name 61 is "Feather" and "Arrow" is name 80
(also a spell name_idx 200). The fan guide's "Arrow" is the
archer's discipline name conflated with the character — **the ROM
calls the character Feather**. Discipline↔spell-block mapping is
still **not** proven from code.

---

## 15. DoT drain rates — ANSWERED: both run, they stack (audit Q10)

**Finding (CODE-VERIFIED).** `0x2257C` (in the `$22594`
combat-round driver): if +0x2A bit 11 set (`rol #5; and #1` on
+0x2A) → `subi.w #$A, $1C(a0)` — **−10 HP per combat round** —
then calls `$36E2E`, which drains 1 HP with 1/3 chance per
sequencer step (per #008 §6.4). **Same bit gates both; neither
"wins" — they add.** The +0x2A field is dual-purpose: for party
chars it is gold (cap 15000); in combat the same field is a status
word (bit 11 = DoT active, bits 12–15 = DoT duration counter).
Do not overwrite #007's gold finding — the field is reused by
context.

---

## 16. Q12 misc — mostly answered

**Bribe (text found, code path OPEN).** Text exists — `$DDBD8`
rec 140 (ptr `0x00B82`): "How dare you insult my honor by trying
to bribe me."; dictionary word 'bribe' (`0x00CFD`). The 10-gold
Bribe mechanic's code path is **not located** — OPEN.

**Doggonia 1,000-gold entry fee — NOT located in code** — OPEN
(player-observed claim from the walkthrough; no routine found that
checks gold ≥ 1000 at a Doggonia entry).

**Gems sell 428 — guide wrong or a different sell path.**
#007 §3.5: Gems sell 428 implies `$2EA92` = 856 = 4.28× base 200;
max with doubling is 2.72× → impossible through the traced sell
path (`$1FB88`, sell = `$2EA92(14, slot)/2`). Either the guide
price is wrong or a different sell path exists. **Unresolved,
carried as open** (needs a second sell-path candidate; none found
in the `$2BBD2` handlers traced so far).

**+0x02 (CODE-VERIFIED).** Set by `$23B84` from its 3rd arg
(`$C(a6)`, `0x23D28`: `move.w $C(a6), (a0,d0.l)` at `$FF02B6`);
+0x04 is initialised to `0xFF` (`0x23D40`). `0x4D` (immunity) is
compared **only** in `$3B1EE` (`0x3B386`/`0x3B3A6`); `0xFE`
(no-target/skip marker) is compared in the combat drivers at
`0x22ED6`, `0x230D4` (`cmpi.w #$fe, $2(a0)`), and `0x24BDA`.
Which spawner passes `0x4D`/`0xFE` as the 3rd arg is not yet
identified — OPEN, narrowed to the 27 `$23B84` call sites, esp.
the `$2B240`-family ones at `0x2B112`/`0x2B236`/`0x2B38C`/
`0x2B484`/`0x2B584`.

**+0x27 (medium confidence).** The high byte of the +0x26 word —
set by `$2B240` (`move.w $12(a6), $26(a3)`), defaults to 0 via
`clr.b (a0,d0.l)` at `$FF02DB` in `$23B84`'s tail (`0x23EEA`);
read as a char index in `$3B1EE`'s immunity check and in the
message routines (`0x277C2`/`0x27970`/`0x27996`/`0x279BA`/
`0x27F9E`/`0x28EFC`/`0x2993C`/`0x299A0`, all `move.b $27(a3/a0),
d0`). Semantic (summoner/owner vs self) is medium-confidence
OPEN.

**`$3019A` (CODE-VERIFIED).** A `$2BBD2` handler — rolls
`$12B82(3)`: 0 → `0x5E` (94), 1 → `0x4D` (77), 2 → `0x4C` (76),
then calls with `0x1E`; also calls `$26A8C` first if `$FF00AE==2`.
Other `$2BBD2` handlers (`$2C0A6`/`$2C0BE`/`$2C0EE`/`$2C212`/
`$2C0D6`) not yet traced — OPEN.

**Item-record +4..+9 bytes (dumped, meaning OPEN).**

| category | +4..+9 bytes |
|---|---|
| 0 (Nobody, dummy) | [7, 72, 8, 20, 0, 1] |
| 1–9 (spells) | [7, 72, 9–13, 20, 0, 1] (byte+6 = 8+block, byte+7 = 20 = spells per block) |
| 10 (rings) | [6, 68, 26, 2, 0, 1] |
| 14 (goods) | [6, 22, 28, 4, 0, 1] |
| 18 (goods) | [6, 68, 25, 3, 0, 1] |

Meaning open (display/icon params hypothesis; consumers in
shop/message code — `$D66A6` base read at `0x27DA6`/`0x286C2`,
`$D66A8+2` read at `0x1E8B8`/`0x1EB28`/`0x1F19A`/`0x1FCC4`/
`0x20072`/`0x27D44`/`0x27EDC`/`0x282C0`/`0x2873A`/`0x28886`).

**`$23B84` tail (type-1 only, CODE-VERIFIED).** Template-derived
stat (template word at `$CF1BC` + template byte `$CF1BE` ×
table[`$FF00C0` + template-word-6×2] / 100, clamped to [−100,
+100] — with a suspicious low-clamp `moveq #$9c, d0` = 156 when
below −100) stored at struct.+0x22; template bytes
`$CF1BA`/`$CF1BB`/`$CF1BE` → +0x24/+0x25/+0x26; +0x20 from
template word 6 (`$CF1B8`) or `$FFC408` if that word == `0x24`.
Note: +0x22 is written by **three** systems (template stat at
spawn, max Power by `$2BBD2` on level-up, self-index by `$2B240`
in combat) — field-reuse hazard, safe in combat only because
`$2B240` overwrites it first.

**+0x14 group-list navigation (medium confidence, inferred).**
Not observed in play; the inference from the `$23B84`/`$2B240`
write sites stands as medium confidence — see §14.


## 17. `$1350` joypad-queue pop — PROVEN, reproduced (audit Q3)

**Finding (PROVEN).** `$1350` (`0x1350–0x1392`) is a FIFO pop over
the 16-entry ring at `$FF001C`:

```
d0 = 0; d1 = 0
SR = $2700 (mask interrupts — critical section)
d1 = $FF001B (tail = read pointer)
a0 = $FF001C (ring base)
if d1 == $FF001A (head = write pointer) → $1388 (empty):
    d0 = $FF002C (last value); SR=$2000; rts
d0 = ring[d1] (byte at tail)
$FF002C = d0 (save as last value)
d1 = (d1+1) & 0xF; $FF001B = d1 (advance tail)
SR = $2000; rts
```

So: **empty when tail == head; an empty pop returns the last
popped value** (not 0, not garbage); the tail wraps mod 16; the
head is the VBlank handler's write pointer. Note `$1350` sets
SR=`$2000` on exit (enables interrupts) — that is the routine's
own behaviour, and it is how interrupts get enabled once the main
loop runs (the attract loop runs at SR=`$2700`).

**Harness reproduction** (result words [13..23]): ring
`[0x11,0x22,0x33,0x44]`, head=4 tail=0 → pops
`[0x11,0x22,0x33,0x44,0x44,0x44]` (the 5th and 6th pops are
empty → last value `0x44`) ✓; head=4, tail=4 after ✓; wrap test
(tail=15 head=1, ring[15]=`0xAA` ring[0]=`0xBB`) → pops
`[0xAA,0xBB,0xBB]` ✓. All match. **25/25 harness run.**

**Debounce (audit Q3, partially open).** The VBlank handler
re-queues a joypad byte every 3 frames unless the ring is full
(16-entry ring `$FF001C`). Whether fast mashing overflows the 16
entries, and whether the 3-frame debounce eats legitimate
presses, is **unmeasured in live play** — the pop semantics are
proven, the overflow behaviour is not. The ring-full path (VBlank
handler drops the byte when full) is the mechanism by which a
press would be lost; no live measurement exists.

---

## 18. Post-harness PC=0 fault — SOLVED, harness bug (audit Q13)

**Finding (PROVEN, reproduced, fixed).** The fault is **not** a
game bug and **not** leftover game state. It is a **stack leak in
the harness hook design**, common to the #007 and #008 harnesses.

**Mechanism.** The hook replaces `move.w $C00004, d1` at `0x35C`
with `jsr $FD0CC.l`, which pushes return address `0x362`. Both
harness exits used `jmp 0x362` instead of `rts` — so the pushed
return address is **never popped: 4 stack bytes leak on every hook
hit**. The hook sits at `0x35C`, the target of the attract loop's
VBlank spin (`btst #3, d1; bne $35C` at `0x362–0x366`), so it is
hit hundreds of times per frame — not once per frame. The stack
plummets from `$FFEC1E` into RAM; at the fault `a7 = $FFFFD3B4`
(~6 KB consumed, confirmed by reading register `a7` in the
BlastEm debugger) and an `rts` eventually pops a 0 → PC=0. The
CPU then executes the vector table as code and writes to
`0xDFFFFE` → freeze.

**Bisection evidence (all runs mode=none, pure attract loop,
breakpoint at 0):**

| variant | PC=0? | time |
|---|---|---|
| #007 control (rebuilt byte-identical: 1,338 B, header `0x169F`, runtime `0x7C7B5FDB`) | **yes** | ~3.1 s |
| skip gold (§7) | yes | ~3.3 s |
| skip XP (§8) | yes | ~3.1 s |
| skip damage (§9) | yes | ~3.1 s |
| skip price (§10) | yes | ~3.1 s |
| restore `a5` | yes | ~3.4 s |
| **rts fix (both exits)** | **no** | **12 s clean** |

Skipping any single test section does not stop it; restoring `a5`
does not stop it. The fault is in the attract loop **before** the
attract exit — breakpoints at `$392` (attract exit), `$119E`
(RAM-clear entry) and `$D25C` (dispatcher) are **never hit** before
PC=0, while the original ROM reaches all three (attract exit at
5.7 s, `$119E` at 5.7 s, `$D25C` at 5.9 s) with no fault.

**The #008 harness has the same fault.** Its test ROM also hits
PC=0 at ~3.2 s if left running. It was never observed because the
#008 driver's run ends right after reading the results at `done`.
The issue brief's "the #008 harness does NOT hit it" is **wrong**
— corrected here and in `docs/logic.md` §7.3.

**Killed leads.** The level-up jingle (`$173EC(8)`), the RNG seed
(`$FF0072`), and the scrubbed message records are all killed by the
skip variants. The `0x882` seen on the stack at the fault was a
red herring (it is the target of `$4E6`'s `bge`, not a return
address). `$26CCA`/`$1E426` (message pump) never hit before PC=0.

**Fix (applied #021 to all three harness sources).** Both exits
use `rts` instead of `jmp 0x362` — `rts` returns to the pushed
`0x362` **and pops it**, so there is no leak. Verified: the fixed
#007 harness produces the same **90/90** results (test ROM header
`0x0EBF`, runtime `0x7C7B5FDB`) and runs 12 s clean; the fixed
#021 harness still gives **25/25**. **Rule for all future
harnesses: a `jsr` hook must be exited with `rts`, never `jmp`.**
`docs/logic.md` §7.3 updated with the resolution.

---

## 19. Live combat — NOT attempted, no credible path (audit Q3)

**Finding (OPEN, with evidence).** Driving a real fight headlessly
was not attempted. #020 found no credible path without a
save-state + scripted-input driver, and none was built in this
issue. What is proven at dispatch level stands: `$3A62E`
dispatches on +0x24 (spell → giant function `$3E2D4` with
`$FFC418`/`$FFC41A` as target/caster indices; melee → `$3B1EE`
with the `$2B240` combatant setup, §10); both damage paths run,
in different turns. What `$FFC418`/`$FFC41A` contain mid-fight in
a live combat round is **unmeasured** — the values are written
only in `$3A62E` and read in ~25 spell-routine sites, so the
dispatch-level proof is strong, but the live contents are not
observed. **Not spent on:** building a save-state + scripted-input
driver is a separate, larger piece of work (it needs a title-screen
→ new-game → encounter path driven by scripted joypad input, plus
a way to read mid-fight RAM); it is not justified for this audit
when the dispatch-level proof already answers which path runs.

---

## 20. Harness evidence

**#021 audit harness** (`tools/test_audit_harness.s`, 1,042 bytes
assembled with the `rts` fix; test ROM header `0xD010`, runtime
`0x7C7B5FDB` — same runtime as #007/#008, expected: identical
hook bytes, harness outside the summed range). Driver
`/tmp/ropre/run021.py` (Xvfb `:99` + xdotool clicker for the
BlastEm vsync dialog). **25/25 result words PASS**
(`/tmp/ropre/run021.json`):

| words | test | result |
|---|---|---|
| [0..3] | gold overflow boundary | 15000, 0, 0, 0 ✓ |
| [4..6] | negative damage (heal) | d0 −6, HP 106, `$FFC380` −6 ✓ |
| [7..9] | control damage | d0 2, HP 98, `$FFC380` 2 ✓ |
| [10..12] | `$3B4AC` install/guard | `0x87D`, `0x08E`, 7 ✓ |
| [13..18] | `$1350` pops | `0x11,0x22,0x33,0x44,0x44,0x44` ✓ |
| [19..20] | head/tail after | 4, 4 ✓ |
| [21..23] | `$1350` wrap pops | `0xAA,0xBB,0xBB` ✓ |
| [24] | canary | `0xA5A5` ✓ |

Flag `$FFD000` = `0xBEEF`, canary1 `$FFD002` = `0xA5A5`, canary2
`$FFD0FE` = `0x5A5A`.

**#007 harness re-verification** (Q13 bisection + fix): rebuilt
byte-identical from `tools/test_logic_harness.s` (1,338 bytes,
header `0x169F`, runtime `0x7C7B5FDB` — matches the #007 record);
the `rts`-fixed variant gives the same **90/90** results
(`/tmp/ropre/run007_rts.json`) and runs 12 s clean.

**#008 harness fault check:** the #008 test ROM hits PC=0 at
~3.2 s when left running (bisect driver, mode=none) — confirming
the leak is hook-design, not test content.

**Harness method notes (for the next agent).** Hook at `0x35C`,
results in `$FFD000+`, driver `/tmp/ropre/run008.py` is the proven
pattern (Xvfb `:99` + xdotool clicker; one `c` per stop, drain
until `Continuing`, consume each stop report). Recompute
breakpoints from the `.bin` after any harness edit (`done` moves
when code above it grows). **A `jsr` hook must be exited with
`rts`, never `jmp`** (§18). The BlastEm debugger's `bt`
(backtrace) prints nothing when the stack is corrupted; `p/x a7`
(no `$`) prints register a7 — `p/x $a7` reads memory at address
`0xA7` instead. The debugger stop report is just PC + one
disassembly line; registers must be read explicitly.

---

## 21. Open items (honestly open, with narrowed leads)

| item | status | narrowed lead |
|---|---|---|
| Void message trigger + timer | OPEN | No pointer to `0x1215A`; search the `0x23000`-area encounter tables and any timer that wipes the party (§7) |
| Command-23 writer | OPEN | No literal `move.b #$17` into the command slot in `disasm/rop.s` (§11) |
| +0x14 chain passing 57–62 | OPEN | `$2BBD2` major/minor dispatch + party-join call sites (§14) |
| Food/water consumption routine | OPEN | `$FF0E16` step-counter consumers in the `$2155E` tick path other than save code; `$32C56` callers (§13) |
| Bribe 10-gold code path | OPEN | Text rec 140 exists; no routine found (§16) |
| Doggonia 1,000-gold fee | OPEN | Player-observed only; no routine found (§16) |
| Gems sell 428 | OPEN | Guide wrong or a second sell path; none found in the `$2BBD2` handlers traced (§16) |
| Discipline↔spell-block mapping | OPEN | Names only suggest it; not proven from code (§14) |
| `$2BBD2` handlers `$2C0A6`/`$2C0BE`/`$2C0EE`/`$2C212`/`$2C0D6` | OPEN | Not traced (§16) |
| Item-record +4..+9 byte meanings | OPEN | Dumped; consumers in shop/message code listed (§16) |
| +0x27 exact semantic | OPEN (medium confidence: char index) | Read as an index in `$3B1EE` + message routines (§16) |
| `$2B240` family entry mechanism | OPEN | No jsr/jmp/longword refs; likely a computed jump through `$2BBD2` (§10) |
| Giant-function per-block internals | OPEN (dispatch mapped) | `0x40880` max-HP path arithmetic; five `$39xxx` spell effects (§9) |
| Live-combat headless drive | OPEN (not attempted) | Needs a save-state + scripted-input driver (§19) |
| Joypad mashing / debounce in live play | OPEN | Pop semantics proven; overflow unmeasured (§17) |
| `$FF012A` ≥ 22 phrasing | SUPERSEDED | Per-block step compares (§9) |
| 0x4D-spawning `$23B84` call site | OPEN | 27 call sites, esp. `$2B240`-family ones (§16) |

---

## 22. Corrections applied by this audit

- **EEPROM labels swapped** (`docs/architecture.md`, `docs/overview.md`):
  `$43012` = READ (block), `$430F4` = WRITE (one byte) — §5.
- **`$12FE8` command map** (`docs/architecture.md`): produces 0, 10,
  20, 21, 22, 24, 25, 30, 35, 37, 40, 45, 50, 55 — not "only 0 or
  37" — §11.
- **Audit list answered** (`docs/overview.md`): all six questions
  now carry their #021 verdict, pointing here.
- **Debug mode reachable** (`docs/overview.md`): the open question
  is now an answer — §6.
- **Post-harness fault solved** (`docs/logic.md` §7.3): root cause
  (stack leak), killed leads, the #008 correction, the `rts` fix —
  §18.
- **Harness `rts` fix** (`tools/test_logic_harness.s`,
  `tools/test_spells_harness.s`, `tools/test_audit_harness.s`):
  both exits use `rts`, not `jmp 0x362` — §18.
- **#008 "does not fault" claim corrected**: the #008 harness
  faults identically if left running; it was an observation-window
  artifact — §18.

**ROM integrity.** `rop-original.gen` MD5 re-verified unchanged:
`30c18fdbe2183f64702ae9f1a45d63f9`. No commit or push made by this
issue (parent verifies and pushes).
