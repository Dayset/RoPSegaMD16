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

1. Live combat: which damage path fires in a real fight (F9, and
   the giant function `0x3E2D4`'s block selection) — needs a
   save-state/input driver (architecture.md #020: bounded, no
   credible headless path without one).
2. Save corruption matrix (Q1) and `$FF0168` mapping (#019 §5).
3. Debug-mode xrefs (§3) + `$1F296` verb-executor full case map +
   the (A,B,C,grp) → `$D28E` command-code mapping (#020 leftovers).
4. Food/water consumption routine — still unlocated after #020
   (leads: `$FF0E16` readers `$2F1F0`/`$2FA2A`/`$302F0`/`$2EC80`;
   guide rates in logic.md §3.7 remain hypotheses).
5. Bribe/attitude-repair action (attitude itself is proven in
   `$2EA92` + the `$2155E` drift loop +5/−4; the Bribe verb's
   effect is not), Doggonia 1000-gold entry fee, item-record
   +4..+9 bytes, `$FF012C` live mapping for `0x8E–0x92` spells,
   party-name writes of name indices 57–62 into `+0x14`.
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
