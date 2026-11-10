# Game logic: stats, XP, gold, combat (issue #007)

**Status:** done (2026-11-09). **Confidence is marked per finding:**
verified = read from the ROM and confirmed by an emulator harness run or a
byte-level check; likely = decoded from the code but not executed;
unknown = open question. Player-observed claims (walkthroughs, fan guides)
are labelled as such and are never evidence on their own — the code wins
on disagreement.

**This document is the remake spec.** It is written for the tribute remake
(Epic 5, `docs/tribute-remake.md`): every finding is implementation-grade —
exact addresses, table layouts, formulas, edge cases. Where the original
has a bug or a dead code path, that is recorded as a behaviour to reproduce
faithfully in "classic" mode and to fix in "fixed" mode.

## Background

Andy Gavin was the lead designer **and** wrote the code (Jason Rubin
interview, 2012-04-09; Rubin worked remotely from another university and
says he could not have as much design influence from 1,000 miles away).
The game took three years, largely because the two worked by modem between
universities. Quote Gavin as the code/design authority, not Rubin.

**Negative finding:** the word "combat" does not appear in the Rubin
interview at all, and Rubin never discusses a combat rework. Do **not**
attribute the rework story to Rubin.

### The combat rework — primary evidence

`$DDBD8` record 1004 (pointer `0x09778`, 30 bytes, type 5, 16 words):

> "Did someone say redo the combat a fifth time? I need a haircut."

It sits in a cluster of developer in-jokes: rec 1002 (ptr `0x09706`)
"Please don't make me reprogram the interface again. Not the blitter
code, and never ever let me see the buc1.bc file again!"; rec 1003 (ptr
`0x09738`) "Make a joke and I will sigh, and you will laugh, and I will
cry. Happiness I can not feel, and love to me is so unreal."; rec 1005
(ptr `0x09796`) "There once was a rich man: 178 131 17 108 304 150!".
(Verified in `disasm/text/records_ddbd8.txt`, lines 2006–2012.)

This is the primary evidence that the combat code went through ~5
revisions. Consequence, confirmed by the code: the combat system is
**layered/vestigial** — there are multiple damage paths, at least one of
which is dead, and the question of which path actually runs in live combat
is still open (see §5.4). The Genesis Temple article ("Rings of Power —
Naughty Dog's last pure game") is about **game history, not combat**; it
never discusses combat revisions and is not evidence for them.

### Player-observed leads (hypotheses, not findings)

From the Genesis Temple article and the ringsofpower.co.uk guides — all
player-observed, verified only where the code confirms them:

- **No equipment** — inventory is quest items + goods to buy/sell.
  Confirmed in code: there is no equipment slot anywhere in the 52-byte
  character struct (§1); the item system is categories + goods (§3).
- **Team fights only with spells**; manual mode lets the player pick each
  character's cast; no team movement in battle. Partly confirmed: the
  combat action routine `$3A62E` dispatches on the spell/attack selector
  (+0x24), and the damage routine `$3B1EE` takes a spell "base" value;
  the manual/auto mode flag itself was not located in #007.
- **Economy is buy-low/sell-high across cities**; the false king of
  Doggonia takes 1,000 gold per room entry. Buy-low/sell-high confirmed
  in code (§3.4, §3.5); the Doggonia 1,000-gold entry fee was not located
  in code (open, #021).
- **Food/water survival + transports with running costs** (dinosaur / boat
  / ship / dragon). Food and Water are goods (price records 186/187, §3.3)
  and are consumed per step, but the consumption routine itself was **not**
  located in #007 (open, §6.2; the guide's rates are reproduced in §3.6
  as the verification target).
- The game started 1989 as a PC project (explains console-odd design);
  EA made it Genesis-exclusive. The 1 MB + save-RAM cart was expensive,
  sold out fast, never restocked. (History, not code.)

## 1. Character struct (52 bytes, $34) — verified

Base `$FF02B4`; index in `$FF0E80`. `$FF02B2` = party leader index (word
before the table). `$FF0E82` = array of 6 party member indices (words).

| Offset | Size | Meaning |
|--------|------|---------|
| +0x00 | word | type (low nibble: 1 = direct char, 4 = redirect via +0x27 byte) |
| +0x02 | word | compared to `0x4D` for immunity, to `0xFE` in a `$3A62E` caller |
| +0x04 | word | ×12 → `$FFB0D0` enemy table |
| +0x0A | word | arg to `$1E0A4` |
| +0x0C | word | X position (proven via `$3778E` distance) |
| +0x0E | word | Y position |
| +0x14 | word | name index (into `$CD431`, 16-byte entries) |
| +0x16 | byte | arg to level-up `$26B58` call |
| +0x18 | word | "order": **high nibble = level 0–8, low nibble = rank 1–9**; order-name table `$1AA60`, index = `((low&0xF)−1)*90 + ((high>>4)&0xF)*10` |
| +0x1A | word | XP (cap 13000) |
| +0x1C | word | current HP |
| +0x1E | word | current Power |
| +0x20 | word | max HP |
| +0x22 | word | max Power |
| +0x24 | word | spell/attack selector (`0x50` = special) |
| +0x25 | byte | spell-table index (used in the `0x40880` path) |
| +0x27 | byte | char index — redirect target for type 4, immunity lookup, death-path leader check |
| +0x28 | word | stat word: **bits 6–10 = attack 0–31, bits 11–15 = defence 0–31** |
| +0x2A | word | gold (cap 15000) |
| +0x2C | word | flags: bit 0, bits 8–9 = 2-bit modifier 0–3, bit 13 = dead flag, bit 15 = ? |
| +0x2E | word | bitfield via `$2B68C` |

Related globals: `$FF010E` combat flags (bit 1 = order nonzero / attacker
has rank; bit 9 = "Enemy" prefix test via rol 7; bit 11 via rol 5);
`$FF012A` flag set by the `$3B4AC` path; `$FF012C` event/state code
(`0x07`, `0x7D` = max-HP loss, `0x7F` = max-HP gain, `0x8E`–`0x92` /
`0x97` = spell/damage special cases); `$FFC37C` message target char index
(−1 = none); `$FFC380` damage display amount (signed: ≤0 = heal path,
negated for display); `$FFC40A` battle-won flag; `$FFC40C` gold total;
`$FFC40E` XP total; `$FFC410` enemy gold/XP value (from `$D601E` & `0x7FF`,
or `0x7530` = 30000 default); `$FFC418`/`$FFC41A` written **only** in
`$3A62E` from attacker +0x1E/+0x22, read as char indices by spell paths
(unresolved — §5.4).

## 2. XP and levelling — verified

### 2.1 There is no XP table — it is a formula

**`$2F030` (0x2F030–0x2F058) → level.** Level = smallest L with
`XP < 100·2^L`, via recursive `$2F05A(level, 100) = 100·2^level`.
Thresholds: 100, 200, 400, 800, 1600, 3200, 6400, 12800.

**Max level is 8, not 7.** `100·2^7 = 12800` is not > 12800, so
`$2F030(12800) = 8` and `$2F030(13000) = 8`. Harness-proven
(`tools/test_logic_harness.s`, XP-level test: XP 12800 → 8, XP 13000 → 8).
Full table in `disasm/logic/xp_levels.txt`.

### 2.2 Max HP / max Power per level — verified

- **`$31958` (0x31958) → max HP = min(20 + 15·level, 140).**
  Levels 0–8: 20, 35, 50, 65, 80, 95, 110, 125, 140.
- **`$31946` (0x31946) → max Power = (level+1)·1000.**
  Levels 0–8: 1000, 2000, …, 8000, 9000.

Harness-proven for every level (see §7).

### 2.3 XP grant / level-up handler — verified

**`$2BBD2` XP handler, `0x2C4E2`** (inside the resource routine `$2BBD2`,
0x2BBD2–0x2C8F2; signature `$2BBD2(char_idx, code, value, flag)`).
Requires `struct[char].+0x00 & 0xF == 4` (else only the party HP refresh
at `0x2C63C` runs). XP = `struct+0x1A`, **cap 13000, floor 0** (note: the
cap path uses `bls` on the sum, the floor path `bcc` — signed/unsigned
edge cases as written; reproduce exactly).

On level change: set order high nibble (`andi #$FF0F` / `or (level<<4)`),
max Power = `$31946(level)` → +0x22, max HP = `$31958(level)` → +0x20,
then `$26B58` (message queue) and `$173EC(8)` (level-up jingle).
Then the party loop at `0x2C63C`: **all** party members' max HP is
recomputed via `$31958(order-high)` and current HP set to max — a full
heal on every XP grant (code-verified, needs live confirmation).

Harness-proven: slot 0, XP 0 → +150 → XP 150, level 1, max HP 35,
max Power 2000; then +13000 → XP 13000 (cap), level 8, max HP 140,
max Power 9000.

### 2.4 Battle-end XP/gold — verified

Routine containing `0x35600` (Ghidra func `0x354A4`, next `0x35612`).
Gold total `$FFC40C` starts 20, XP total `$FFC40E` starts 6. Loop over
6 enemy slots: if the enemy struct word `+0x14+i*2` is nonzero,
gold += `(rand19+11) * order_high_nibble`, XP += `(rand7+5) *
order_high_nibble`, where `order_high_nibble = (struct+0x18 >> 4) & 0xF`
and rand is `$12B82(n)`. Party count = alive members via
`$FF0E82[i] != 0`. **XP/person = `$FFC40E` / party_count, clamped to
[1, 50].** Then `$2BBD2(1, gold_total, 0x400, $FF02B2)` (gold to leader)
and per party member `$2BBD2(1, XP/person, 0x401, member_index)`.

Earlier part (`0x356E0`–`0x35802`): `$2D284(char field, 5)` lookup,
`$2B656`/`$2B68C` with `$FFC326` pointer; enemy tables `$D601E` (word &
`0x7FF` → `$FFC410`) and `$D6022` (byte), indexed by enemy type×6;
`$FFC410` = 30000 if `$2D284` returns −1. `$FFC40A` cleared at `0x356E4`,
set to 1 at `0x30680`.

### 2.5 RNG — verified

**`$12B82` (0x12B82–0x12BFC), 122 bytes.** LCG: seed `$FF0072`;
`state = state * 0x41C64E6D + 0x3039` (via `$DE8E`); output =
`((state >> 16) & 0x7FFF)`; then `$DEF4(arg)` = modulo by arg. Returns
`0..arg−1`. The constants are the classic glibc ANSI C LCG
(1103515245, 12345); the extraction is classic `rand()` 15-bit output.
So `$12B82(n) = rand() % n`. ~100 call sites. Harness-proven from seed 0:
`$12B82(19)×3, $12B82(7)×3` → `[0, 17, 13, 4, 5, 1]`.

Note: the sign-fix branch after `and.l #$7FFF` looks unreachable (AND
clears carry, so `bcc` is always taken) — observed, not yet
harness-verified (#021).

### 2.6 Level-up message — verified

Message routine `0x275B0` (7,530 bytes — one giant event-message
function). Level-up message at `0x27B08`–`0x27BFA`: `a3 =
struct[$FF0E80]`; formats `$1A(a3)` XP, `$18(a3)` order via `$1AA60`,
`$20(a3)` after "Maximum Health is now" (string `0x29424`, `pea` at
`0x27BD0`, `move.w $20(a3)` at `0x27BE8`). Strings (spaced ASCII,
`0x2937D`–`0x29767`): " has earned " `0x293AF` / " experience points"
`0x293BC`; "Congratulations, " `0x293D1` / " experience points therefore
reaching the order of " `0x293F0` / ". Maximum Health is now " `0x29424` /
" points and Maximum Power is " `0x2943D`; "Battle successful." `0x29464` /
"You earned " `0x29477` / " experience per person. You also captured "
`0x29483` / " gold pieces" `0x294AE`.

Also `0x27996`–`0x279E6`: `d7 = ((struct[byte+0x27].+0x22 + 10) * 12) /
100`, clamped [0,100], used as an index into `$1A990` (16-byte entries) —
purpose unclear (unknown).

Formatter helpers: `$DE30` strcpy, `$DE3E` strcat, `$DE52` strcmp,
`$DE7C` strlen (corrected 2026-11-09 by direct read of `0xDE30`–`0xDE8C`:
all `movem.l $4(a7), a0-a1` style, plain C string helpers, NOT sprintf);
`$11F3A` number→string (base 10); `$11624` display text box; `$DE8E`
32-bit multiply; `$DEB2` signed 32/32 divide (quotient in d0); `$DEF4`
unsigned divide (remainder in d0); `$DF0A` core divide (quotient d0,
remainder d1).

### 2.7 Message queue `$26B58` — verified (and a divide-by-zero hazard)

`0x26B58`–`0x26CCA`, 370 bytes. Entry: if `$A(a6)==4` → leader check
(bit 6 of leader's +0x28 at `$FF02DC+leader*0x34`; if set, return). Else
compares the current record at `$FFC324` (8 slots × 210 bytes at
`$FFBC94`; record fields: +0 = arg0, +2 = text-buffer ptr, +6 = arg1,
+8 = arg2) against args (`$8`=byte+0x16, `$A`=`0x10`, `$C`=char idx); if
all match → `$DE52` (strcmp) of arg3 vs record text; if equal →
`clr $FF010A`, return (dedup). Else advance: `$FFC324 = ($FFC324+1) % 8`,
call `$1E3B0($FF0E18, new_idx)`; if it returns < 0, return without
queuing. Else write the record (words + long text ptr at
`$FFBC9E+idx*210`), `$DE30` (strcpy) of arg3 (`$E(a6)`, = 0 in the XP
call → copies an empty string from address 0, first byte `0x00`) into
the text buffer. Sets `$FF009A = −1` (message pending) at `0x26C2E`.

`$1E3B0` (0x1E3B0–0x1E426, push/enqueue): reads bytes [0]=head, [1]=tail,
[2]=capacity of the struct at `$A(a6)`; computes `q = (head+1) % capacity`
via `divu.w` — the swap/clr/swap dance cancels out (first reading was
wrong: it is a plain modulo, not `(x<<16)%cap`). If `q == tail` → return
−2 (`0xFE`). Else write idx word at offset `2*(head+2)` from struct base,
set byte0 = q, return 1. **Divides by byte[2] — zero divisor = divide-by-
zero exception, and this ROM has no fault handlers.** `$1E426`
(0x1E426–0x1E49A, pop/dequeue): if tail == head → return −1 (`0xFF`);
else read word at `2*(tail+2)` into *out (`$8(a6)`), advance
`tail = (tail+1) % capacity` (same divu pattern, also divides by byte[2]).
`$1E49A` (0x1E49A+): returns byte0 − byte1 (queue depth), used as a
boolean (0 = empty).

`$FF0E18` and `$FF0E30` are two structs of this shape (same 3 header bytes
+ word entries). No code in the linear sweep writes `$FF0E18`/`$FF0E19`/
`$FF0E1A` directly — the header bytes are only touched through `$1E3B0`
(byte0) and `$1E426` (byte1); byte[2] (capacity/divisor) must be
initialized by game startup / new-game init, **not yet located**. In real
gameplay it is nonzero before any XP grant; at the attract loop it is 0
(cold RAM). The harness proved the hazard directly: the first freeze was
inside the XP test at `$26B58` → `$1E3B0` dividing by `$FF0E18[2] = 0`
(see §7.2). **Remake note:** the queue capacity must be initialised
before any message is queued; the original crashes (divide-by-zero, no
fault handler) if a message is queued while it is 0.

`$26CCA` (0x26CCA+, queue consumer): calls `$1E426($FF0E18, local)` to
pop; reads `$FF0E78`. The `0x1B8D8+` region tests `$FF009A` (`0x1B92C`,
`0x1B970`) and clears it (`0x1B9B6`) — the message pump. `$FF009A` is
also set to −1 by `$3B1EE`'s tail and many shop-code sites — a common
"something happened / message pending" flag.

## 3. Gold and shops — verified

### 3.1 Gold storage — verified

Gold at struct `+0x2A`, **cap 15,000, floor 0** (gold handler `0x2C474`
inside `$2BBD2`). Battle-end gold goes to the leader's `+0x2A`. Shop
display (`0x28664`) reads `struct[leader].+0x2A`.

### 3.2 The resource routine `$2BBD2` — verified (decoded in full)

`0x2BBD2`–`0x2C8F2`, 3,324 bytes, 40+ callers. Signature
`$2BBD2(char_idx, code, value, flag)`: `$8(a6)`=char index, `$A(a6)`=code,
`$C(a6)`=value, `$E(a6)`=flag (1 in battle-end calls). Locals: −$2 =
code/64, −$4 = code%64, −$6 = effective char (`struct+0x00&0xF==4` →
byte +0x27; `==1` → `$8` itself; else stale + `$12FA0(50)` call).
Dispatch on code/64 in [11,20] via jump table at `0x2C8C4`
(PC-relative to `0x2C8EC`): 11→`0x2BE4A` (code%64 switch: 0→`$3019A(1)`,
1→heal party +25 HP clamped to max HP), 12→`0x2C0A6`, 13→`0x2C0BE`,
14→`0x2C0EE`, 15→`0x2C212`, 16→`0x2C46A` (gold/XP handler), 17→`0x2C0D6`,
18→`0x2C8AC` (re-dispatches `$2BBD2` with code `0x386`), 19→`0x2BF76`
(power add: code%64 0→+2000, 1→+4000, 2→+10000 to party +0x1E clamped
to +0x22), 20→`0x259A8`. code/64==10 path: `$2B68C(flag, code%64,
ptr=struct.+0x2E)` + party XP grant 350/500/3000 for code%64 in
{0,4,10}. code%64 switch at `0x2C898` (table at `0x2C88E`, PC-relative
to `0x2C8A8`): 0→`0x2C474` gold, 1→`0x2C4E2` XP, 2→`0x2C640`,
3→`0x2C6FA`, 4→`0x2C760`.

- **Gold handler `0x2C474`:** gold = `struct[−$6].+0x2A`, cap 15000,
  floor 0. Harness-proven: slot 0, gold 1000 → +500 → 1500; +20000 →
  15000 (cap); −20000 → 0 (floor).
- **`$2B656`** = bit test (bit `$C(a6)` of byte array at `$8(a6)`);
  **`$2B68C`** = bitfield set (clears bit, then ORs `$E(a6)` bit).
- **`$12FA0(arg)`** → `$12072(arg)`: VDP/text drawing routine (blits
  `$11820`/`$11A1A`/`$11AE4`, `$1000` VRAM addresses).

### 3.3 Item and price tables — verified

**Item categories, table `$D66A6`, 20 records × 10 bytes**
(`$D66A6`–`$D6768`). Record: +0 word name_idx (`$CD431`, 16-byte
entries — a **category** word), +2 word `w` (base index into the price
table), +4..+9 bytes (undecoded — see below). Item 0 is a dummy (name
"Nobody", w=0). Full table in `disasm/logic/items.txt`.

| item | category | w |
|------|----------|---|
| 0 | Nobody (dummy) | 0 |
| 1–9 | spells | 1, 21, 41, 61, 81, 101, 121, 122, 123 |
| 10 | rings | 125 |
| 11 | services | 136 |
| 12 | keys | 138 |
| 13 | items | 153 |
| 14 | **goods** | **186** |
| 15 | crafts | 211 |
| 16 | healing | 215 |
| 17 | papers | 220 |
| 18 | goods | 253 |
| 19 | drinks | 254 |

The record's +4..+9 bytes are not yet decoded (e.g. item 0:
`07 48 08 14 00 01`; item 13: `06 44 1b 19 00 63`; item 15:
`05 56 14 05 27 0f`). Unknown — #021.

**Price/value table `$D6768`, 257 records × 4 bytes**
(`$D6768`–`$D6B68`). Record: +0 word name_idx (`$CD431` — the
**specific** name), +2 word raw value. Full table in
`disasm/logic/price_table.txt`.

- Records 1–120: spells (6 disciplines × 20: Stun, Clue, Warn, Inform,
  Jolt, Confse, Knwldg, Help, Predict, Daze, Free, Mesmer, Insane, Shock,
  Support, Assist, Swarm, Mirage, Packs, Master; then Stab…Pain;
  Dart…Twister; Claw…Djinn). Values in tiers: raw 36→100, 56→200,
  86→350, 101→500, 103→700, 106→1000, 110→1400, 116→2000, 125→2900.
- Records 121–135: rings/quest words (Rot, Claw, Punch, Kick, Will,
  Thought, Intuitin, Division, Advance, Blood, Bile, Mutation, Variatin,
  Calling, Perfctin), all raw 99 → 415.
- Records 136–137: Sleep (31→75), Meal (26→50).
- Records 138–152: keys ("Sorc Key" … "Div Key"), all 415.
- Records 153–158: guild symbols ("So Sym" … "Co Sym"), all 415.
- Records 159–185: quest items (Map, Sxtnt, Bingo 10, Mirror, F Wood,
  O Egg, HairLk, SigRng, Y Milk, Finger, So Eye, Specs, Lens, Whip,
  Mustch, Orb, Dove, C Ball, Leaf, Honey, MedSup, S Gem, M Gem, H Seal,
  Ruby, Skull, Goblet), mostly 415.
- **Records 186–216: trade goods, food/water, transports** (see §3.4).
- Records 217–218: Heal / Pow Up (46→150). Record 219: Life (103→700).
- Records 220–256: notes/tomes/scraps/maps/letters (raw 39–70 → 115–275).
  Record 253 is a second "Corpse" (raw 1). Record 257+ is not table data.

The shop display (`0x28664`) shows the current item's **category** name
via the item record (`word at $D66A6 + item*10`, ×16 → `$CD431`) and
the specific good's name via the price record (`word at $D6768 +
(w+modifier)*4`, ×16 → `$CD431`). `$D6734` (a ROM word, value 186 =
the goods category's `w`) is the shop base offset, read at `0x1FB6E`
(sell) and `0x28938`/`0x28A8A` (shop displays).

### 3.4 Price function `$2EA92` — verified

`0x2EA92`–`0x2EC5C` (approx). Signature `$2EA92(item $8(a6),
modifier $A(a6)) → price` (word, in d0).

```
w   = word($D66A8 + item*10)              # item record's +2 word
v   = word($D676A + (w + modifier)*4)     # price record's +2 word
      # ($D676A = $D6768+2: the SECOND word of the 4-byte price record)
if 20 < v <= 100:  v = (v-16)*5
elif v > 100:      v = (v-96)*100
# else v = v
merchant = $FF02A0
if merchant != 0x00FF:                     # NOTE: compares against 0xFF, NOT 0xFFFF
    m20 = merchant_struct.+0x20           # word at $FF02D4 + merchant*0x34
    m22 = merchant_struct.+0x22 - 50      # word at $FF02D6 + merchant*0x34
    if m20 == 32 and ($FF0E92 & 0x3FF) == 367:  # 367 = 0x16F
        v *= 2
    price = v - m22*v/140                  # divs, truncates toward zero
    price = clamp(price, 2, 9000)
else:
    price = clamp(v, 2, 9000)
if item == 14:                             # goods category only
    if $1B298[m20*2] == modifier:          # byte table $1B298
        price = clamp(price/2, 2, 9000)
```

Notes:
- **Merchant-none is `0x00FF`, not `0xFFFF`.** The code does
  `cmpi.w #$ff, -$8(a6)` — the harness first used `0xFFFF` and the
  merchant block ran with index −1, reading garbage fields. Fixed in
  the harness; re-run green.
- Merchant `+0x22` reads as **attitude (0–100)**: 100 → ~0.64×, 0 →
  ~1.36× (because `m22 = att−50`, `price = v − m22·v/140`).
- Merchant `+0x20 == 32` is a merchant-type check; `$FF0E92 & 0x3FF`
  is the **current location code** (masked to 10 bits) — location 367 is
  the doubling location (see §3.5: the guide's sell prices imply the
  doubling is active at Commerce). `$FF0E92` itself has no direct writes
  in the linear sweep (written via pointer or in mis-decoded code) —
  unknown, #020.
- Item 14 special: if `$1B298[m20*2] == modifier` → price /= 2.
  `$1B298` is a byte table; `m20` is the merchant's +0x20 word.
- Callers: `0x1E908`, `0x1FB94` (sell), `0x1FD00` (buy check), `0x1FDD2`
  (buy), `0x287A4` (buy display), `0x2897A` (sell display).

Harness-proven: `$2EA92(item 23, mod 0)` → no merchant 350, att 100 →
225, att 0 → 475. (Item 23: w=86 → v=(86−16)*5=350; att100:
350−50·350/140=225; att0: 350+50·350/140=475.) Item 2 was used first
and returns 2 in all cases (its v is 0 → floor clamp) — it does not
discriminate the merchant paths.

### 3.5 Trading — guide vs ROM — verified (one disagreement)

The ringsofpower.co.uk trading guide's 21 goods all exist in the ROM
(price records 186–216). Full per-good table in
`disasm/logic/trading_check.txt`. Summary (ROM base = scaled value,
mod 0, no merchant):

| Goods | ROM rec | ROM base | Guide buy | Guide sell |
|-------|---------|----------|-----------|------------|
| Balm | 204 | 40 | 19 | 39 |
| Blades | 189 | 70 | 35 | 74 |
| Boat Stones | 209 | 320 | 324 | — |
| Books | 202 | 15 | 7 | 15 |
| Bridge stones | 210 | 170 | 172 | — |
| Caskets | 191 | 220 | 78 | 217 |
| Corpses | 192 | 1400 | — | 1500 |
| Crystal | 199 | 120 | 54 | 128 |
| Dragon Stones | 208 | 500 | 507 | — |
| Finini | 206 | 2400 | 1314 | 2366 |
| Flip Stones | 190 | 50 | 27 | 54 |
| Flowers | 194 | 10 | 5 | 10 |
| Gate Stones | 197 | 30 | 13 | 30 |
| Gems | 188 | 200 | 86 | **428** |
| Jewellery | 201 | 320 | 197 | 315 |
| Lottery Tickets | 193 | 20 | 10 | 20 |
| Mana | 203 | 40 | 18 | 42 |
| Nectar | 198 | 170 | 364 | — |
| Tomes | 195 | 5 | 2 | 5 |
| Weapons | 200 | 95 | 50 | 101 |
| Wood | 196 | 15 | 5 | 15 |

- **Buy:** 17/21 guide buy prices fit `(base/2)·attitude` (the item-14
  halving active, attitude 15–94 depending on the merchant). The 3 Mesa
  stones fit `base·attitude` (no halving at Mesa). Nectar fits
  `2·base·attitude` (doubling active at Commerce).
- **Sell:** 17/18 guide sell prices fit the ×2 band: sell =
  `$2EA92(14, slot)/2` with the doubling active, so sell ≈ base
  (attitude near neutral). This implies the doubling condition
  (`m20==32` and location 367) holds at Commerce, the sell city for
  most goods.
- **Gems sell 428 is impossible.** Sell = `$2EA92/2`, so 428 implies a
  `$2EA92` value of 856 = 4.28× the base 200; the maximum with doubling
  is 2.72×. The guide's Gems sell price is wrong, or Gems sells through
  a different path (unknown — #021).
- City names: "Fenopolis" is in the ROM (plain ASCII at `0xD7842`,
  `0xD7873`) despite missing from the guide's 20-city list; "Shard" is
  in the ROM (`0xD773E`); the guide's "Protect" is an abbreviation of
  the ROM city name **Protection** (`0xD99EF`); Commerce at `0xD76A0`.
  "Doggonia" was not found as plain ASCII (it lives in dictionary text).

### 3.6 Buy / sell arithmetic — verified

- **Buy check `0x1FD00`:** gold >= price else "not enough gold" path
  `0x1FE4E`; inventory check via `$2C8F2`/`$2D38C`; "already have
  enough" path at `0x1FD50` (`$26B58`).
- **Buy transaction `0x1FDC4`:** price = `$2EA92(item=$FF02A8,
  modifier=slot)`; deduct via `$2BBD2(1, −price, 0x400, leader)`; add
  item via `$2BBD2(1, 1, item*64+slot, leader)`. Shop menu state machine
  at `0x1FA60`–`0x1FB60` (jump table on menu choice 0–9).
- **Sell `0x1FB88`:** price = `$2EA92(14, slot)/2` — first arg is the
  literal 14 (the goods category); receive via `$2BBD2(1, price/2,
  0x400, leader)`; remove item via `$2BBD2(1, −1, item*64+slot, leader)`;
  `$26B58` sold message; `$FFBB72` stock byte decremented. Sell slot
  chosen via `$2CC62(leader, $FFBB6F, $FFBB72+1)`; if result < 2 → exit
  (`0x1FC74`).
- **Bribe / attitude:** attitude lives in merchant `+0x22` and enters
  the price formula, but the Bribe action (10 gold, walkthrough claim)
  and attitude repair were **not** located in code (unknown — #021).
  Merchant attitude levels (WORSHIPFUL…VIOLENT) are player-observed
  only.
- Shop globals: `$FF02A8` = current item index, `$FF02AA` = ?, `$FF02A0`
  = merchant index (`0x00FF` = none), `$FFBB72` = stock byte,
  `$FFBB6D`/`$FFBB6E`/`$FFBB6F` = shop state bytes. Shop strings
  (`0x2960C`–`0x296FA`): "You have " / " gold pieces with which to
  purchase " / " will cost " / " gold." / "Sorry you don't have enough
  gold to buy that." / "Sorry you already have enough of those." /
  " purchased!" / "I'll give you " / " gold for each " / ". You have " /
  " gold now." / " sold!" / "Sorry I can't buy that back."

### 3.7 Transport / food & water — routine LOCATED, live-verified (2026-11-10)

**[live]** Food and Water are goods (price records 186/187: Food raw 12,
Water raw 8). **[static]** Their live counts are the words at
**`$FFC364` (food)** and **`$FFC366` (water)** — proven from the
inventory-count getter `$2C8F2`: goods code `$380` (food) returns
`$FFC364`, code `$381` (water) returns `$FFC366` (group 14 = code/64,
remainder = code%64; the save serialiser `$2F11A`/`$2F896` uses
`add.w #$380` for the same two slots). The goods-adjust routine is
`$2BBD2`; the per-step consumption does **not** go through it — it is a
direct RAM write (below).

#### The consumption routine [static]

The per-step deduction is in the movement dispatcher
**`FUN_024984` (`$024984`)**, at **`$024F38`–`$024FB2`**, gated by
`cmpi.w #$1,$ff00ae.l` (only runs when **`$FF00AE == 1`**):

```
$024F38: cmpi.w #$1,$ff00ae.l ; gate
$024F44: food  = $FFC364 - struct+0x1A   ; struct = FUN_024984 local at -$22(a6)
$024F78: $FFC364 = clamp(food, 1, $7530) ; 30000
$024F7E: water = $FFC366 - struct+0x1C
$024FB2: $FFC366 = clamp(water, 1, $7530)
```

So the per-step cost is the struct's **`+0x1A` (food)** and **`+0x1C`
(water)**. Those two words are computed by the step routine
**`FUN_01c892` (`$01C892`)**, called from `FUN_024984` at `$024B6E`
(`pea.l -$22(a6); jsr FUN_01c892` — the struct is the local at
`-$22(a6)`, so struct+0x1A = `-$8(a6)`, struct+0x1C = `-$6(a6)`).
`FUN_024984` callers: **39 `jsr` sites in 12 functions** —
`FUN_02241c` (2), `FUN_0226bc` (9), `FUN_0265be` (1), `FUN_02d56a` (1),
`FUN_03268e` (1), `FUN_0337ee` (14), `FUN_034b50` (1), `FUN_034d32` (2),
`FUN_037976` (1), `FUN_038b96` (1), `FUN_03ae40` (1), `FUN_03e2d4` (5).
(An earlier draft listed only the 12 sites in the movement area; the
full count is 39.)
`$1C892` also reads the destination tile via `$1C176` (chunk cache) and
the `$5EDC4` terrain word, and returns a step status in `d0`.

#### The formula [static]

`$1C892` computes the cost as **base(mode) + terrain addition**, plus a
**height term on food only**:

```
food  = base_food(mode)  + terrain_food(type, mode) + height_delta/2
water = base_water(mode) + terrain_water(type, mode)
```

* **Base — `$01C8C6`–`$01C928`, on the struct's `+0x08` (the "mode"):**

  | mode | food | water |
  |------|------|-------|
  | 0 | **3** | **1** |
  | 1 | 3 | 1 |
  | 4 | 38 (`$26`) | 38 (`$26`) |
  | anything else (2, 3, 5, 6, 7) | 1 | 1 |

  **[live — correction to the static reading]** The mode-0 base is
  **(3,1), not (2,2)**. The `$01C8C6` block writes (2,2) and then
  **falls through** into the mode-1 block at `$01C8DA`, which overwrites
  it with (3,1) — there is no branch between them. So the (2,2)
  assignment is dead code and modes 0 and 1 share the base (3,1). The
  live harness (below) measured mode 0 on 25 distinct terrain types:
  every type with no addition returned exactly (3,1), never (2,2).

* **Mode — `$025D8E`**, called from `FUN_024984` at `$024B26` with the
  moving character's **`+0x06`** word, stored to the struct's `+0x08`
  (`move.w d0,-$1a(a6)`). It divides `+0x06` by `$100` (256) and
  dispatches on the high byte (jump table `$25DBC`, 4 entries):
  high byte 0 → returns the low byte; 1 → 6; 2 → 5; 3 → 7; ≥ 4 → error
  `$12FA0($192)`. So `+0x06` is a packed vessel/mount value: high byte
  = category, low byte = sub-value. `+0x06` is set by the
  character-spawn/setup routine **`FUN_023b84` (`$023B84`)** from its
  arguments (`$8(a6)` = type 1/2/4/5/6, `$e(a6)`, `$c(a6)`): type 6 →
  `+0x06 = $c(a6)+$300` (high byte 3 → mode 7); type 5 → `+0x06 =
  …+$200` (high byte 2 → mode 5); type 1 with `$e==$FFFF` →
  `+0x06 = 0`, `+0x08 = 4`; type 4 → `+0x08 = 4`. `+0x06` is otherwise
  0 (cleared at `$024264`, `$0367B4`), so **plain on-foot walking is
  mode 0, base (3,1)** — live, see the fall-through correction above.
* **Terrain addition — jump table at `$01D73E`** (35 entries, terrain
  types 0–34, offsets relative to `$01D794`; dispatch at `$01D784`,
  `cmp.l #$23,d0` bounds-checks, out-of-range → `$01D736` sets the
  blocked flag). The terrain type is `$5EDC4` bits 10–15 (the same
  field the walkability gate `$02dc0c` tests). The **only** `$1A`/`$1C`
  modifications in `$1C892` besides the base are:

  | `$5EDC4` type | condition (mode) | food | water | notes |
  |---|---|---|---|---|
  | 0 | mode 2 or 7 | +4 | +19 (`$13`) | `$01CFAA`/`$01CFB2` |
  | 9 | mode 0, 1, 6, 7 | **set 1** | **set 1** | `$01D134`/`$01D13E`, `$01D156`/`$01D160` |
  | 17 | mode 0, 6, 7 | +4 | +4 | `$01D2E2`/`$01D2EA`; also sets `-$22(a6)=10` |
  | 17 | mode 2 | +2 | +2 | `$01D30E`/`$01D316` |
  | 18 | mode 0 | +2 | +4 | `$01D33E`/`$01D346` |
  | 19 | mode 0 | +3 | +4 | `$01D37C`/`$01D384` |
  | 19 | mode 1 | +3 | +6 | `$01D394`/`$01D39C` |

  All other types leave the base unchanged. Most handlers also set the
  step-blocked flag `-$a(a6)` (1 = blocked, 0 = free); types 4, 12–16,
  29, 31–34 clear it unconditionally, the rest test the mode and the
  step-direction deltas (struct `+0x0A`/`+0x0C`).
* **Height term — `$01D800`–`$01D8B4`:** after the dispatch, `$1C892`
  computes a height delta `-$10(a6)` from the source/destination tile
  words' bit fields (tile bits 13–15, `$5EDC4` bits 7–8 — the same
  fields the `$E358` row-count formula uses), then
  `food += height_delta / 2` (`move.w -$10(a6),d0; divs.w #$2,d0;
  add.w d0,$1a(a0)` at `$01D8A6`–`$01D8B4`). Water gets no height term.
  This is the multilevel-terrain cost: walking uphill costs extra food.
  **[live]** Confirmed by the harness on type 9 (delta +4 → food 3,
  +2 → 2, −4 → −1): the term applies in both directions, and food can
  go negative (the `FUN_024984` clamp [1, 30000] applies afterwards, to
  the party totals, not to this per-step cost).

#### Rates: manual vs code [live for the code column; mapping partly open]

The official manual (see `docs/research/official-manual-transcript.md`)
gives rates per mile, party of 6. The code column is the flat-terrain
(`height_delta = 0`) cost, **measured live** by the `$1C892` harness
(below). The **terrain-type → terrain-name mapping is partly open** —
Road and Desert are now pinned; Grass, Swamp and Ice are not.

| Manual (per mile) | Food | Water | Code match |
|---|---|---|---|
| On foot — Road | 1 | 1 | **type 9, mode 0: set (1,1) ✓ [live]** |
| On foot — Grass | 4 | 2 | no mode-0 type gives (4,2) — [open] |
| On foot — Desert | 7 | 5 | **type 17, mode 0: (3,1)+(4,4) = (7,5) ✓ [live]** |
| On foot — Swamp | 8 | 4 | no mode-0 type gives (8,4) — [open] |
| On foot — Ice waste | 4 | 3 | no mode-0 type gives (4,3) — [open] |
| Boat, shallow | 1 | 1 | base (1,1) ✓ (no addition) [live] |
| Boat, deep | 5 | 20 | **type 0, mode 7: (1,1)+(4,19) = (5,20) ✓ [live]** |
| Ship, deep | 1 | 1 | base (1,1) ✓ [live] |
| Dino, road | 1 | 1 | type 9, mode 1: set (1,1) ✓ [live] |
| Dino, other | 3 | 1 | **mode 1 base (3,1) ✓ [live]** |
| Dragon, all | 40 | 40 | mode 4 base (38,38) — **off by 2, confirmed live** [open] |

Code costs actually attainable on flat terrain **[live]**: mode 0 →
(1,1), (3,1), (7,5), (5,5), (6,5); mode 1 → (3,1), (1,1), (6,7);
mode 4 → (38,38); mode 7 → (1,1), (5,20), (5,5); mode 2 → (5,20)
on type 0; mode 6 → (5,5) on type 17. Mode-0 water is only **1 or 5**
(live) — never 2, 3 or 4 — so the manual's Grass (2), Swamp (4) and
Ice (3) water values cannot be flat mode-0 costs. Either the manual's
rates are approximate (per "mile" may not be one step, or the rates
are rounded), or those terrains are reached via a different mode or a
height component. **Desert is the one manual on-foot terrain that
matches exactly: type 17 gives (7,5) on foot.** Which world-map
terrain type 17 *is* (desert, by the rate) is a mapping claim, not a
code claim — the type's identity still needs a world-map pin
(overworld coordinate (58,81) is a type-17 cell).

#### Live harness — `$1C892` (2026-11-10, 44/44 cases)

`.scratch007/harness_c892.s` + `build_c892.py` + `run_c892.py`
(test ROM `.scratch007/test007.gen`, MD5
`bc40401378c482c182f1ba379466eb4d`). Hook at the attract loop `0x35C`
(`jsr $FD0CC.l`, trampoline at `0xFD0CC`, exits with `rts`), results
in `$FFD000+` (7 words/case: mode, live type, dest tile, food, water,
d0, blocked). Each case sets the struct at `$FFD300` (mode at `+0x08`,
dx = 1, dy = 0, `+0x1E = $FFFF`, `+0x20 = 2`), positions the party at
a chosen overworld (x,y), loads the real chunk via `$19692`, calls
`$1C892`, and records the struct `+0x1A`/`+0x1C` plus the live
`$5EDC4` type (`rol.w #$6` extraction, as `$02dc0c` does it) and the
destination tile from `$FF0248`. `$FF00A4 = 1` is required (the terrain
dispatch at `$01CF38` is skipped when it is 0). **All 44 cases passed
against the live-corrected expectations** (ran flag `$FFD000 = $BEEF`,
canary `$FFDFFE = $5A5A`; every destination tile matched the offline
chunk decode, proving the chunk-cache positioning is correct). The
44 cases: mode 0 on 30 `$5EDC4` types (0–23, 25, 27, 28, 30, 31, 33 —
types 24/26/29 do not exist in `$5EDC4`; 32/34 exist but no flat east
step onto them was found in the overworld); mode 1 on types 9/0/17/19;
mode 4 on types 9/0; mode 7 on types 0/9/17; mode 2 on type 0;
mode 6 on type 17; and three height cases on type 9 (delta +4 → food
3, delta +2 → food 2, delta −4 → food −1 — **the height term is
confirmed live, including the negative direction: food can go below
the type-9 base, to −1**). Two harness bugs were found and fixed
during the run: the type extraction used `lsr #6` (wrong — it reads
bits 6–11, not 10–15; fixed to `rol #6` like `$02dc0c`), and the
`lsr #10` fix attempt was rejected by GAS (immediate shifts are 1–8
only). `$1C892` also returns a step-blocked flag (`d0` + struct
`+0x18`): it varies by **coordinate**, not by terrain type (the same
type 9 gives d0 = 1 at (151,15) and (150,15) but d0 = 0 at (148,15)
and (266,101)) — likely entity occupancy at the destination, separate
from the cost, and not pursued here.

**No plain rate table exists in the ROM** (searched byte sequences
`[1,8,7,4,4]`/`[1,4,5,3,2]`, fan order, interleaved pairs, word tables
— all 0 hits). The rates are computed in code as above.

#### Related [static]

* **`$FF0E16` is a clock, not a step counter** (increments every frame
  in `$2155E`, wraps at 2400; `$170DA` displays time from
  `$FF0E16`/`$FF0E18`). The consumption is not driven by it; it is
  driven by the movement dispatcher `FUN_024984`.
* **Low-supplies regen penalty:** in the `$2155E` tick, the HP/Power
  regen loop uses `d7 = +5` normally (`$021712`); if food or water
  `≤ 500` (`cmpi.w #$1f4,$ffc364.l` / `$ffc366.l` at `$021714`/
  `$02171E`) it enters the low-supplies path, and if either is `≤ 1`
  it shows a message (`$35612($44)`) and sets `d7 = $FC = −4`
  (`$02176E`) — regen becomes a drain when supplies run out.
* **CAMP — LOCATED and live-verified (2026-11-10).** The handler is
  **`FUN_03019a` (`$03019a`)**, reached as **C=28** from the verb
  executor `$1F296`: the Camp verb-table record (ROM `0xCCE0A`) carries
  byte 11 = `$1C` = 28, and the C-dispatch case 28 (`$0206E8` →
  `L0204CE`) is `clr.w -(a7); jsr FUN_03019a.l` — argument 0.
  **[live]** All three CAMP effects measured in one harness call
  (`FUN_03019a(0)`, party = one member, HP 10/100, Power 20/80,
  food/water 1000):
  * **100/100 deduction [live]:** food `$FFC364 −= 100`, water
    `$FFC366 −= 100`, clamped [1, 30000] — a **direct register
    subtract + store** (`$030346`–`$0303B4`: `move.w $ffc364.l,d0;
    sub.w #$64,d0; …; move.w d0,$ffc364.l`, same for water), **not**
    via the goods-adjust `$2BBD2`. The earlier "no `sub` on
    `$FFC364`/`$FFC366`" was about the memory operand — the subtract
    is on `d0`, then stored back. The `$02C188` (quantity×100) candidate
    is wrong for CAMP: `$02C188` is an instruction *inside* `$2BBD2`,
    and CAMP never calls `$2BBD2`. Measured: 1000 → 900 for both.
  * **Regain [live] — the manual's "50%" does NOT match the CAMP
    verb.** CAMP (arg 0) runs regain loop 1 (`$0303BE`–`$0304D4`,
    `divs.w #$4`): each party member's current HP/Power moves
    **25% of the way toward max** — `new = current +
    (max − current)/4`, per member, only if current < max. Measured:
    HP 10 → 32 (`10 + 90/4`), Power 20 → 35 (`20 + 60/4`). The
    **50% regain is the inn service Sleep** [live, 2026-11-10]:
    `FUN_03019a(1)` runs loop 2 (`$030500`–`$030620`, `divs.w #$2`,
    `new = current + (max − current)/2`, measured HP 10 → 55,
    Power 20 → 50) with **no** deduction — it is called from the
    goods-adjust `$2BBD2` (`$02BE58`, argument 1) when the goods code
    is **704** (`$2C0`). Goods-code formula [static, verified live on
    food/water/gold]: `goods = item_category × 64 + (price_record −
    category_w)`. Sleep is item 11 ("services", `w` = 136), price
    record 136 → `11×64 + 0 = 704`. The `$2BBD2` dispatch splits the
    code by 64 (quotient → jump table `$02C8C4`, quotient 11 →
    `$02BE4A`; remainder → `$02BF66`, remainder 0 → `L02BE54` →
    `FUN_03019a(1)`). Live harness (`.scratch007/harness_sleep.s`,
    test ROM `3e3ae5380302abcbe3e79a05ec80ded7`, 3/3 cases):
    `$2BBD2(1, 704, 1, 1)` → HP 10 → 55, Power 20 → 50, food/water/
    gold unchanged (1000), clock 100 → 540; with HP already at max,
    HP stays 100 while Power still regains 20 → 50 (per-stat "only if
    current < max"). The paired service **Meal** (goods 705, item 11,
    price record 137, 50 gold) gives **+25 HP only** (capped at max,
    Power untouched, no clock change) — measured HP 10 → 35. Sleep
    costs **75 gold** (price raw 31 → `(31−16)×5`), Meal 50 gold
    (raw 26 → `(26−16)×5`); the manual confirms both are inn services
    ("Inns (Sleep/Meals) are cheaper than Temples (Heal/Power) at low
    levels"). Sleep is a **service, not a carried item**: it is bought
    at an inn and the effect applies immediately — the `$2BBD2(704)`
    call itself deducts no gold/food/water (measured gold unchanged),
    so the 75-gold payment is a separate transaction by the purchase
    code, not part of the regain call. The temple counterparts are
    Heal (goods 1026) / Pow Up (1027) / Life (1028) — same formula,
    item 16 ("healing", `w` = 215) — **LOCATED and live-verified
    (2026-11-10, 4/4 harness cases, `.scratch007/harness_temple.s`,
    test ROM `a24ea110c7dfe46432a63f211c67689e`)**: the quotient-16
    dispatch `$02C46A` loads the remainder and branches to the
    remainder jump table `$02C88E` (remainders 0–5); remainder 0 = gold
    (adds `$c(a6)` to `$FF02DE`, clamps to `$3A98` = 15000 — the gold
    cap), remainder 1 = XP (adds to `$FF02CE`, clamps to `$32C8` =
    13000, then recomputes the level and writes it into order-word
    bits 4–7 at `$02C5A8`–`$02C5C8`), remainder 2 → `$02C640` (Heal),
    3 → `$02C6FA` (Pow Up), 4 → `$02C760` (Life). **Heal [live]: full
    HP restore** — per party member, recompute max HP from level via
    `FUN_031958` (20+15·level, cap 140) into `+0x20`, then copy max HP
    to cur HP (`+0x1C`); measured HP 10 → 95, HP max 100 → 95 (level 5,
    stored max was deliberately inconsistent to test the recompute).
    **Pow Up [live]: full Power restore** — per party member, copy
    stored max Power (`+0x22`) to cur Power (`+0x1E`), no recompute;
    measured Power 20 → 80, HP untouched. **Life [live]: revive** —
    per party member with `+0x2C` bit 13 set (dead): cur HP = 5, cur
    Power = 5, recompute max HP (`FUN_031958`) and max Power
    (`FUN_031946`, (level+1)·1000), clear bit 13 of `+0x2C`; measured
    HP 0 → 5, Power 0 → 5, HP max 100 → 95, Power max 80 → 6000 (level
    5), `+0x2C` `$2000` → `$0000`. A Life call on a live member does
    nothing (measured: no change). None of the three deducts gold,
    food or water (measured unchanged at 1000), none flips the clock
    (stays 100) or sets `$FF0124` (stays 0) — like Sleep, the payment
    is a separate purchase transaction. If Life revives anyone it plays
    song 8 (`jsr $173EC` at `$02C884` — [static]; the call was NOP'd in
    the test ROM only, freeze risk in the attract context). Prices
    (price table `$D6768`, raw byte b3; `$2EA92`: raw 20–100 →
    (raw−16)·5, raw >100 → (raw−96)·100): Heal raw 46 → **150 gold**,
    Pow Up raw 46 → **150 gold**, Life raw 103 → **700 gold** (the
    >100 branch — not (103−16)·5 = 435). All three are more expensive
    than the inn services (Sleep 75, Meal 50), matching the manual's
    "Inns are cheaper than Temples at low levels".
  * **Clock [live] — day↔night flip, but NOT a +1200 advance.**
    `$0302F0`–`$030318`: if `$FF0E16 ≤ 540` (`$21C`) set it to **540**,
    else set it to **0**. Measured: clock 100 → 540, clock 1000 → 0.
    So CAMP *sets* the clock to one of two anchors (0 / 540), it does
    not add half the 2400 cycle. (Dayset 2026-11-10: CAMP turns the
    world clock around — day becomes night and vice versa.) Which
    `$FF0E16` range counts as day vs night is [open] — the palette
    routine `$170DA` reads `$FF0E16`/`$FF0E18`.
  * Also: `$FF0124 = $FFFF` after CAMP (`$030336`) [live].
  * Harness notes: direct `jsr $03019a` from the attract loop
    (`0x35C`, hook exits `rts`); the three `$35612` message-display
    calls (`$03030E`, `$03032E`, `$0304F4`) freeze in the attract
    context (`$32D4C` writes to `$DFFFFE` — the in-game text system
    is not set up), so they were NOP'd **only in the test ROM**;
    RNG seed set to 1 (32-bit, `$FF0072`) so the random-event message
    is skipped (`RNG(3)=2`); interrupts masked during the run.
    Test ROM `.scratch007/test030.gen`
    (MD5 `226cc6d4bd2a7400891f7ed636f11beb`). Harness:
    `.scratch007/harness_camp.s`, `build_camp.py`, `run_camp.py`
    (3/3 cases OK).
* **Random event in the same function:** after the consumption block,
  if struct `+0x08` (`-$1a(a6)`) `== 3` and a 1/9 RNG roll (`$12B82`
  with 9) is 0, `FUN_024984` calls `$2BBD2(char, $400, −4, 1)` and sets
  `$FF009A=$FFFF` (`$024FB8`–`$024FE0`) — a separate random loss
  (code `$400` is likely gold), not the per-step consumption.
* **Vessel state:** the vessel/mount is the character's `+0x06` word
  (packed, see above), decoded by `$25D8E` into the mode. The
  character's `+0x08` is a separate field (set to 4 or 0 by
  `FUN_023b84`); it is **not** the `$1C892` mode.
* The `$5EDC4` terrain type is loaded by only 5 functions: `$01ba4e`
  (per-cell driver), `$01c892` (this step routine), `$02619c`/`$0265be`
  (NPC/AI), `$02dc0c` (walkability gate).

#### What would settle the open rates [partly open]

The `$1C892` live harness ran 2026-11-10 (44/44 cases, `.scratch007/harness_c892.s`, test ROM `bc40401378c482c182f1ba379466eb4d`): it called `$1C892` with a controlled mode and terrain (chunk cache pre-loaded via `$19692`) and read struct `+0x1A`/`+0x1C`. It pinned Road (type 9, 1/1) and **Desert (type 17, 7/5)** and confirmed the Dragon 38/38 (not the manual's 40/40) and the height term live, including the negative direction. The routine, the formula shape, the base costs (corrected live: mode 0/1 base is (3,1), not (2,2)), the terrain additions and the height term are now **live-verified**. Still open: the Grass/Swamp/Ice type mapping (live mode-0 water is only 1 or 5, so the manual's 4/2, 8/4, 4/3 cannot be flat mode-0 costs) and the Dragon 40/40 vs live 38/38 gap.

## 4. Combat action routine `$3A62E` — verified (static)

`0x3A62E`–`0x3AAC4`, 1,174 bytes. Callers `0x22EE0`, `0x23138`,
`0x24C56`.

Locals: −$4 = attacker struct; −$A = attacker +0x1E (current Power) —
used as a TARGET struct index at `0x3A6B6` (`struct[attacker+0x1E]`);
−$8 = target struct; −$10 = word from `$FFB0D0 + (target+0x04)*12`,
must be < 0x24 (36); −$12 = `$1E0A4(attacker+0x0A)`; −$14 = attacker
+0x20 (max HP); −$16 = attacker +0x24; −$1A = flag.

Flow: if attacker +0x18 != 0 set `$FF010E` bit 1. If attacker power ==
−1 → exit (`0x3A9CE`, clr −$18(a6)). If attacker +0x24 == `0x50`:
`$3B4AC(0x50)`, set `$FFC418` = attacker +0x1E, `$FFC41A` = attacker
+0x22, `$FF012A`=1, exit. Else if +0x24 != 0 and `$FF012C` != 7 and
target +0x2C bit 15 clear: `$3B4AC(+0x24)`, same setup. If target +0x2C
bit 15 set → `0x3A7C8`. Else if attacker +0x20 >= 0: `$23AE0(attacker)`,
−$1A=1, `$FF012A`=0, `$25DE4(target struct)`; if nonzero: `$2140A`
effect (`0x14`) then exit. At `0x3A7C8`: if attacker +0x18 != 0 and
−$16 == 0: `$25DE4(target)`; if nonzero → `$2140A` (`0x18`) then exit.
At `0x3A814`: if −$14(a6) < 0 → damage-apply block `0x3A84C`, else call
`$3B1EE` at `0x3A842` with args (`$8` = attacker +0x22, `$A` = attacker
+0x1E, `$C` = attacker +0x20) — the index puzzle (§5.4).

**Damage-apply block `0x3A84C` (dead code, likely):** `$FFC37C` =
attacker +0x1E; target HP = clamp(HP − X, 0, target+0x20), target power
= clamp(power − X*10, 0, target+0x22), X = attacker +0x20; `$FFC380`
+= X; `$FF010E` bit 1 set; SFX via `$17586` (`0x1A`/9/`0x13` by −$16).
Runs only when attacker +0x20 < 0 (never for valid chars) → likely
dead/vestigial code.

`$3B4AC` (26 bytes, `0x3B4AC`–`0x3B4C6`; callers `0x37538`, `0x37E46`,
`0x3A690`, `0x3A738`, `0x3AB94`, `0x40E0E`, `0x421E2`, `0x42236`): if
`$FF012C` != 7: `$FF012C` = arg. Tiny state setter.

## 5. Combat damage — verified (formula), live path open

### 5.1 Damage routine `$3B1EE` — verified

`0x3B1EE`–`0x3B408`, 538 bytes. Callers `0x3A842`, `0x3B094`. Args:
`$8(a6)` = attacker idx, `$A(a6)` = target idx, `$C(a6)` = base.
Locals: −$4 attacker struct, −$8 target struct, −$A result damage.

```
if $FF012C in {0x8E, 0x8F, 0x90, 0x91, 0x92}: result = 70; jump to tail
if $FF012C == 0x97: result = 5; jump to tail
atk_stat = (attacker+0x28 >> 6) & 0x1F
def_stat = (target+0x28 rol 5) & 0x1F   # = (target+0x28 >> 11) & 0x1F
d0 = atk_stat*base>>5 + base - def_stat*base>>5
d0 += base/(dist+2)                      # DEAD TERM — always 0 (see below)
d0 += ((attacker+0x2C >> 8) & 3)*base>>4
d0 -= ((target+0x2C >> 8) & 3)*base>>4
# order switch on attacker+0x18 LOW nibble (verified at 0x3B360):
if rank in {7, 8}: dmg = ((order_high)+1)*2
elif rank == 9:    dmg = order_high+1
else:              dmg = dmg/3 + 1        # divs #3, +1
# tail (0x3B36E):
# immunity: attacker +0x27 byte and target +0x27 byte, each used as an
# index: struct[byte].+0x02 compared to 0x4D (77); if either == 0x4D,
# skip HP subtraction. Else target+0x1C -= result.
# Then $37B82(target struct). If $FFC37C != target idx: $FFC37C = target
# idx, $FFC380 = 0. $FFC380 += result. $FF010E bit 1 set. $FF009A = -1.
# Return result in d0.
```

**The distance term is dead.** The code does `d1=1; divs.w d0,d1` →
`d1 = 1/(dist+2) = 0` for all dist ≥ 0 (integer division), then × base
= 0. So distance contributes nothing as written — almost certainly a
bug (the division is inverted: it should be `base/(dist+2)`, i.e. divide
the base by the distance, not 1 by the distance). Harness-proven:
D1 with dist 5 gives 28, which matches the formula with a zero distance
term (79+0+7−3=83; 83/3+1=28) and contradicts a live `base/(dist+2) =
60/7 = 8` term (which would give 91/3+1 = 31). **Remake note:** classic
mode reproduces the dead term (distance has no effect on damage); fixed
mode should use `base/(dist+2)`.

**Order switch is on the rank (low nibble), not the level.** Verified
at `0x3B360`; harness D2–D4 confirm (rank 7 → 6, rank 8 → 8, rank 9 →
5 with the D1 base of 83 — see `disasm/logic/damage_tests.txt`).

Second call site at `0x3B094`: `$3B1EE($FF0EAA, $8(a6), val&0x7F)` —
fits (attacker idx, target idx, base) cleanly; preceded by
`$25DE4(target)` check, followed by `$2140A` effect (`0x18`). Its
function also has the `0x3B0D2` block: if `struct[$8].+0x00 & 0xF == 1`
→ clear `$FF010E` bit 9, loop 6 slots calling `$3AF92`.

### 5.2 Distance `$3778E` and integer sqrt `$377FE` — verified

`$3778E`: dx = attacker+0x0C − target+0x0C, dy = attacker+0x0E −
target+0x0E, returns `$377FE(dx²+dy²)`. `$377FE(n)` = smallest k with
`k(k+1) >= n`, max 255 (integer sqrt via odd-number accumulation).
Harness-proven: n=0→0, 1→1, 2→1, 3→2, 4→2, 5→2, 20→4, 25→5, 30→5,
100→10, 10000→100, 65025→255. Distance (0,0)-(3,4) → 5.

### 5.3 Death check `$37B82` — verified (static)

If target HP > 0 → rts (via `0x37D0A` bra `$37C16`). If HP ≤ 0: if
`$FF010E` bit 0 set → death handling `0x37C26`; else if target == party
member 0 and its +0x2C bit 13 clear → search party slots 1..5 for a
member with bit 13 clear → set dead char's HP to 1 and return (**revive
with 1 HP**); else `0x37C26`: HP = 0; if target +0x04 != `0xFF`: set bit
7 of `$FFB0D4 + target[+0x04]*12`; +0x2C: `andi #$DFFF` then `ori
#$2000` (set bit 13); play SFX `0x5B`; if byte +0x27 == `$FF02B2`
(party leader) → call `$36A00`.

### 5.4 Sibling / vestigial damage paths — UNRESOLVED (which runs?)

At `0x40880+` inside giant func `0x3E2D4` (19,280 bytes, likely merged
functions): spell/max-HP damage paths using `$FFC418`/`$FFC41A` as char
indices. `0x40934`: `$FFC380` = computed damage; target max HP −=
damage (clamped [1, `$31958(level)`]); target cur HP clamped to new max
HP; `$37B82` death check; `$FFC37C` = `$FFC418`. Damage from `$FFA7CC`
table (indexed by attacker's order low nibble −1, ×4) + byte
`struct[$FFC41A].+0x25` ×6, word & `0x7F`, /3, clamped to [0, maxHP−1].
`0x40B7A`: max-HP GAIN path: −$C = ((word at table+2 & 0xF)+1)*4;
target max HP += −$C (clamped to `$31958(level)`); `$FFC380` =
`$31958(level)` − old max HP; `$FFC37C` = `$FFC418`. This is the
`$FF012C` == `0x7F` "got max pts" case. `0x40A0E`: revive path (target HP
= 1, clears +0x2C bit 13, `$3CB66`).

**Which path actually runs is unresolved** — needs live-combat breakpoint
observation. `$FFC418` is read in many places (`0x38BC6`/`0x38BE0`/
`0x38BF4`/`0x38C1E`/`0x38C38`; `0x3EEAC`/`0x3EF12`/`0x3EFD6`/`0x3EFEE`/
`0x3F03C`/`0x3F100`/`0x3F11C`/`0x3F134`/`0x3F182`/`0x3F254`/`0x3F26C`/
`0x3F2D2`/`0x3F3B0`/`0x3F3C8`/`0x3F416`/`0x3F4A0`/`0x3F5AA` — spell
routine region) but written **only** in `$3A62E`. The `$3A62E` call to
`$3B1EE` passes attacker +0x22/+0x1E/+0x20 as (attacker idx, target idx,
base) — those are Power values used as indices, which only makes sense
if +0x1E/+0x22 hold indices in that context, or if the call is itself a
vestigial mis-wiring. Open for #008/#021: break at `$3A62E`/`$3B1EE`/
`0x40880` in live combat and record which fires and what
`$FFC418`/`$FFC41A` contain.

Combat message strings (`0x295C8`–`0x29603`): "Enemy" / " lost " / " got
" / " max pts" / " took " / " hit pts" / " got " / " miscast".

## 6. Open questions for #008 / #020 / #021

1. **Which damage path runs in live combat?** `$3B1EE` vs the `0x40880`
   spell/max-HP path; what `$FFC418`/`$FFC41A` contain in real combat;
   the `$3B1EE` arg puzzle (+0x1E/+0x22 as indices). Needs a live-combat
   breakpoint run (#008).
2. **Transport/food-water consumption routine** — located (static):
   `FUN_024984` `$024F38`–`$024FB2` + `FUN_01c892` `$01C892` (§3.7).
   Open: terrain-type → terrain-name mapping for Grass/Desert/Swamp/
   Ice, Dragon 40/40 vs code 38/38, CAMP 100/100 — needs a live
   `$1C892` harness.
   Leads: decoder `0xE3B4`/`0xE412`, tables `$433C0`–`$436E0`, decoded
   map `$FF1EC0`, location code `$FF0E92`, `$2BBD2` codes `0x380`/`0x381`.
   The guide's rates are the verification target. (#020.)
3. **Bribe (10 gold) / attitude repair** — not located in code. Merchant
   attitude is confirmed in the price formula; the action that changes
   it is not. (#021.)
4. **Gems sell price 428** — impossible under `$2EA92` (§3.5). Guide
   wrong, or a different sell path. (#021.)
5. **`$FF012C` action-code meanings** (`0x07`, `0x7D`, `0x7F`,
   `0x8E`–`0x92`, `0x97`) — map from the message routine's cases. (#021.)
6. **+0x02 codes** (`0x4D` immunity, `0xFE` in the `$3A62E` caller) and
   the **+0x27 byte** meaning. (#021.)
7. **`$3019A`, `$2C0A6`/`$2C0BE`/`$2C0EE`/`$2C212`/`$2C0D6` handlers**
   (other `$2BBD2` code/64 cases) — read briefly or note as out of
   scope. (#021.)
8. **Level-up "Maximum Power is"** — formats +0x22; dump `0x27BFA`–
   `0x27C60` (cut off in the prior read). (#021.)
9. **Who initialises `$FF0E18[2]`** (message-queue capacity/divisor) in
   real gameplay — not located (no direct writes in the sweep). (#021.)
10. **Item-record +4..+9 bytes** — undecoded (§3.3). (#021.)
11. **Doggonia 1,000-gold entry fee** — walkthrough claim, not located
    in code. (#021.)
12. **Post-harness PC=0 fault** — the harness run faults after returning
    to the attract loop (see §7.2); root cause unresolved. (#021.)

## 7. Tests (emulator harness)

### 7.1 Harness method — verified

`tools/test_logic_harness.s` (1,338 bytes assembled, GNU as 2.42,
`m68k-linux-gnu-as -m68000`). A test harness in the `0xFF` padding at
`0xFD0CC+`, hooked at `0x35C` (attract loop top, replaces the 6-byte
`move.w $C00004,d1` = `32 39 00 C0 00 04` with the 6-byte
`jsr $FD0CC.l` = `4E B9 00 0F D0 CC`). The harness runs once (flag in
scratch), calls the game routines with crafted inputs, stores results
as words in scratch RAM `$FFD000`–`$FFD1FF`, executes the displaced
instruction, jmps to `0x362`. The game continues to the title screen;
results are read back via the BlastEm debugger `p/x $FFD0xx`.

Scratch `$FFD000`–`$FFD1FF` was chosen after a gap analysis of referenced
`$FFxxxx` addresses in `disasm/rop.s` (largest gaps: `$FF5926`–`$FF5FF3`,
`$FF392A`–`$FF3F33`, `$FF899A`–`$FF8EE8`, `$FFCDDE`–`$FFD1FF`). Canaries:
`0xA5A5` at `$FFD002`, `0x5A5A` at `$FFD0FE`; flag `0xBEEF` at `$FFD000`
(harness ran), `0xDEAD` if the end canary was clobbered. Backups at
`$FFD100` (slots 0,1,2 — 156 bytes), `$FFD19C` (party array), `$FFD1A8`
(saved `$FF02B2`), `$FFD1AA` (message-queue header `$FF0E18`), `$FFD1C2`
(saved `$FFC324`), `$FFD1C4`/`$FFD1C6`/`$FFD1C8`/`$FFD1CA` (saved
`$FF009A`/`$FFC37C`/`$FFC380`/`$FF02A0`).

Build/run recipe: assemble, `objcopy -O binary`, copy `rop-original.gen`
to `/tmp/test007.gen`, write the harness at `0xFD0CC`, write the hook at
`0x35C`, `python3 tools/checksum.py fix-all` (header `0x0EBF` after the
#021 `rts` fix — `0x169F` before it — runtime `0x7C7B5FDB`, both OK). Read back with a breakpoint at address 0 (see
§7.2). The original ROM is never modified (MD5 re-verified after every
build: `30c18fdbe2183f64702ae9f1a45d63f9`).

GAS syntax that this GNU as wants: **%-prefixed registers** (`%d0`,
`%a5`, `%sp`), no `.l` on absolute addresses, `lea label(%pc), %a0` for
PC-relative, no `.s` on branches (GAS picks sizes itself). Plain register
names fail with "operands mismatch"; `sp` is not a register name (use
`%sp`); `lea 0xFFD004.l, a5` fails.

### 7.2 Results — all 90 words PASS

Run 2026-11-09, read back via debugger breakpoint at 0 (see below).
Flag `0xBEEF`, canaries intact.

| Test | Result | Expected |
|------|--------|----------|
| `$2F030` level for XP [0,99,100,199,200,399,400,799,800,1599,1600,3199,3200,6399,6400,12799,12800,13000] | [0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8] | same |
| `$31958` max HP, level 0–8 | [20,35,50,65,80,95,110,125,140] | same |
| `$31946` max Power, level 0–7 | [1000..8000] | same |
| `$377FE` isqrt [0,1,2,3,4,5,20,25,30,100,10000,65025] | [0,1,1,2,2,2,4,5,5,10,100,255] | same |
| `$3778E` distance (0,0)-(3,4) | 5 | 5 |
| RNG `$12B82(19)×3, $12B82(7)×3` from seed 0 | [0,17,13,4,5,1] | same |
| Gold: +500 / +20000 / −20000 from 1000 | [1500,15000,0] | same |
| XP: +150 → XP/level/maxHP/maxPower | [150,1,35,2000] | same |
| XP: +13000 → XP/level/maxHP/maxPower | [13000,8,140,9000] | same |
| Damage D1–D7 (d0, tgt HP, `$FFC380`) | [28,72,28, 6,94,6, 8,92,8, 5,95,5, 70,30,70, 5,95,5, 28,100,28] | same |
| Price `$2EA92(item 23, mod 0)`: none / att100 / att0 | [350,225,475] | same |

Two corrections the harness forced: (a) max level is **8**, not 7
(XP 12800 → 8; the first run's expectation of 7 was wrong, the code
was right); (b) the price test's first version used item 2 (returns 2
in all cases — its v is 0 → floor clamp) and merchant-none `0xFFFF`
(the code compares against `0xFF`); item 23 + `0x00FF` discriminates
all three merchant paths.

### 7.3 The post-harness fault (SOLVED in #021, Q13)

After the harness returns, the game faults: after `c` (continue) the
log shows `machine freeze due to write to address DFFFFE`, then `Saved
EEPROM...`, and the debugger stops answering. Bisected with
breakpoints: the harness completes (`done` reached), the attract loop
re-enters repeatedly, then **PC reaches address 0** — the CPU fetches
from address 0 (`0: dc.w $FF`), executes the vector table as code,
and eventually writes to `0xDFFFFE` → freeze.

**Root cause (found #021): the harness itself leaks the stack.** The
hook is `jsr $FD0CC` (pushes return address `0x362`), but both
harness exits used `jmp 0x362` instead of `rts` — so the pushed
return address is never popped: **4 stack bytes leak on every hook
hit**. The hook sits at `0x35C`, the target of the attract loop's
VBlank spin (`btst #3, d1; bne $35C`), so it is hit hundreds of times
per frame; the stack plummets from `$FFEC1E` into RAM (at the fault,
`a7 = $FFFFD3B4`, ~6 KB consumed) and an `rts` eventually pops a 0 →
PC=0. The fault is in the attract loop, **before** the attract exit
(`$392`, `$119E`, `$D25C` are never reached — proven by breakpoints).
The earlier prime suspects are all **killed**: skipping gold, XP,
damage, or price individually does not stop the fault, and restoring
`a5` does not either. The `0x882` seen on the stack was a red herring
(it is the target of `$4E6`'s `bge`, not a return address). The
`#008` harness has the **same** fault (its test ROM also hits PC=0 at
~3.2 s if left running) — it was never observed because that driver's
run ends right after reading the results at `done`.

**Fix (applied #021 to all three harness sources):** both exits use
`rts` instead of `jmp 0x362` — `rts` returns to the pushed `0x362`
and pops it, so there is no leak. Verified: the fixed #007 harness
produces the same **90/90** results and runs 12 s clean (no PC=0);
the fixed #021 harness still gives **25/25**. **Rule for all future
harnesses: a `jsr` hook must be exited with `rts`, never `jmp`.**

**Readback method that works:** set a breakpoint at 0 (`b 0`), `c`,
wait ~5 s, then read `$FFD000+` while stopped at PC=0 — the debugger
stays alive because the breakpoint catches the cascade before the
freeze. Reading after the freeze does not work (debugger unresponsive).
The fault does not corrupt the results (all 90 words read cleanly).
