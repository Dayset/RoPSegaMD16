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
