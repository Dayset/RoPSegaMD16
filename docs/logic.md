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
then `$26B58` (message queue) and `$173EC(8)` (level-up jingle). **The
XP handler never writes cur HP (+0x1C) or cur Power (+0x1E)** — a level-up
raises the maxes only; the currents are left exactly where they were.
**[live, 2026-11-10, 4/4 harness cases, `.scratch008/harness_levelup.s`,
test ROM `7932edd91c0c0700722cfcb4e9f256d4`]:** XP 90 +20 → XP 110, level
0 → 1, max HP 20 → 35, max Power 1000 → 2000, but cur HP stayed 10 and
cur Power stayed 500 (second party member also untouched).

**Correction (2026-11-10):** the earlier "party loop at `0x2C63C` — a full
heal on every XP grant" was a misreading. The code at `$02C63C` is
`bra.w L02C8AA` (all XP-handler exits go to the dispatch tail), so there
is **no** fall-through into the loop at `$02C640` — that loop is the
**separate temple Heal dispatch case** (goods code `0x402`, `$02C640`:
cur HP = max HP for all party members, max HP recomputed via `$31958`;
`0x403` Pow Up at `$02C6FA` does the same for Power). The HP/Power fill
is the temple Heal/Pow Up, invoked via the goods system — **not** via
XP, and not called by the battle-end routine (which only grants gold
`0x400` and XP `0x401`). So there is no automatic post-battle or
per-XP-grant heal; a level-up raises the ceiling but does not fill the
currents.

Harness-proven: slot 0, XP 0 → +150 → XP 150, level 1, max HP 35,
max Power 2000; then +13000 → XP 13000 (cap), level 8, max HP 140,
max Power 9000. `$2BBD2` preconditions worth noting: the quotient-16
gate at `$02BE30` makes the call a silent no-op unless
`struct[char].+0x27 == $FF02B2` (current-char index), and the `$FF0E82`
party list uses 0 as the "empty" marker (a party entry of 0 is skipped
by the Heal/Pow Up loops).

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

`0x2BBD2`–`0x2C8F2`, 3,360 bytes, 40+ callers. Signature
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

The five handlers 12/13/14/15/17 are traced (2026-11-11, static).
Quotient→category follows the name table (`$CD430`): 12 keys, 13
items, 14 goods, 17 papers. The read counterpart is
`item_category_of` (`$2C8F2`), which tests the same three bitmaps
and returns the Q14 quantity — the write handlers and the read
routine agree exactly. `world_reset_supplies` (`$2CDD4`) resets all
four regions at new-game/load (clears `$FFC33E` 2 B, `$FFC340` 5 B,
`$FFC345` 5 B, `$FFC34A` 25 B; sets bit 0 in `$FFC340`/`$FFC345`;
food/water = 2000).

- **`$2C0A6` (`sys_set_key_flag`, Q12):** 16 bytes. Sets/clears bit
  (code%64) in the 2-byte keys bitmap `$FFC33E` via `sys_bitmap_write`
  (`$2B68C`), value = flag. No immediate-code caller found (Q12
  callers pass a computed code).
- **`$2C0BE` (`sys_set_item_flag`, Q13):** same 16-byte shape, bitmap
  `$FFC340` (5 bytes). Called at location 188 (in
  `sys_dispatch_action_2dcce`, gated on `($FF0E92 & 0x3FF) == 0xBC`
  and bit 0x3E in `$FFC326`): codes 0x34F (minor 15, value −1) and
  0x34C (minor 12, value 1) set bits 15 and 12; the same branch
  plays song 8 and raises NPC attitude by id 0xE5.
- **`$2C0EE` (`sys_adjust_goods_qty`, Q14):** minor 0 → food
  (`value*100 + $FFC364`, clamped [1, 30000]); minor 1 → water
  (same, `$FFC366`); minor ≥ 2 → goods byte `$FFC34A[minor] +=
  value`, capped at the word at `$D66A4 + quotient*10` — for
  quotient 14 that is `$D6730` = **99**. **Bug (static):** the cap
  comparison is unsigned (`cmp.w max,d1; bls`), so a negative new
  quantity is clamped to the max (99), not to 0; and the would-be
  floor-at-0 is unreachable anyway (`tst.w d1` clears C, so the
  following `bcc` is always taken and `moveq #$0,d0` never runs).
  Reachable: `$02E0DC` removes 5 of goods slot 21 (code 0x395),
  and the Corpses grant re-dispatches code 0x386 (minor 6) through
  this handler.
- **`$2C212` (`world_ensure_location_entity`, Q15):** finds the
  current location's entity (`$FF0E92 & 0x3FF`) in the 56 struct
  slots by matching the `$D1D00` record's (+0x00, +0x02) cell key
  against the slot's struct +0x0C/+0x0E cell; returns at once if
  present. If absent, spawns it via `entity_spawn` with
  mode = code%64 (0→3, 1→2, 2→1, 3→4), then `npc_leader_init`.
  The `$D1D00` table is 455 records × 10 B (the earlier "175 × 10 B,
  146 distinct pairs" count was wrong — it counted only the first
  175 records; the full table holds 426 distinct key pairs, and
  `world_location_lookup` scans all 455). 30 records hold
  (999,999) = "none", all in the first 175. **The +2 is a spawn
  placement offset, not an alignment fix:** `entity_spawn` stores
  its arg6/arg7 into the new struct's +0x0C/+0x0E unconditionally
  (`$0243AE`/`$0243C0`), and `$2C212` passes (key1+2, key2) for
  spawn modes 3/2 and (key1, key2+2) for modes 1/4 — so a
  `$2C212`-spawned entity never stands on the anchor cell itself.
  The search tries both alignments because either may have spawned
  the entity; with +0 it could never find its own spawns and would
  duplicate the entity on every Q15 event. Why the offset is
  exactly 2 cells, and why the axis follows the mode (3/2 → X,
  1/4 → Y), is unpinned — arg4 is stored to struct +0x06
  (`$0241EC`), whose meaning is open.
- **`$2C0D6` (`sys_set_paper_flag`, Q17):** same 16-byte shape,
  bitmap `$FFC345` (5 bytes). No immediate-code caller found.

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
    if m20 == 32 or ($FF0E92 & 0x3FF) == 367:   # 367 = 0x16F; OR, not AND
        v *= 2
    price = v - m22*v/140                  # divs, truncates toward zero
    price = clamp(price, 2, 9000)
else:
    price = clamp(v, 2, 9000)
if item == 14:                             # goods category only
    if $1B298[m20*2] == modifier:          # byte table $1B298 (high byte)
        price = clamp(price/2, 2, 9000)
    if $1B299[m20*2] == modifier:          # byte table $1B299 (low byte)
        price = clamp(price*2, 2, 9000)
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
- Item 14 special: `$1B298`/`$1B299` are the two bytes of one word
  table indexed by `m20` (one word per merchant index 0–35): the high
  byte (`$1B298[m20*2]`) is the merchant's halving slot (price /= 2
  if it equals the modifier), the low byte (`$1B299[m20*2]`) is the
  doubling slot (price *= 2 if it equals the modifier). E.g. m20=32
  (Commerce) is `0xFF02`: never halves, doubles slot 2 (Gems) — this
  second multiplier was missed in the earlier analysis and is what
  makes the guide's Gems sell 428 attainable (see §3.5).
- Callers: `0x1E908`, `0x1FB94` (sell), `0x1FD00` (buy check), `0x1FDD2`
  (buy), `0x287A4` (buy display), `0x2897A` (sell display).

Harness-proven: `$2EA92(item 23, mod 0)` → no merchant 350, att 100 →
225, att 0 → 475. (Item 23: w=86 → v=(86−16)*5=350; att100:
350−50·350/140=225; att0: 350+50·350/140=475.) Item 2 was used first
and returns 2 in all cases (its v is 0 → floor clamp) — it does not
discriminate the merchant paths.

Live (2026-11-10, `.scratch024/`, 6/6, test ROM
`41f2207211bc5f9f5dfce43e36812030`): `$2EA92(14, 2)` at Commerce
(m20=32, loc 367) = 856 @ att 40, 1084 @ att 0, 516 @ att 100,
800 @ att 50; control (m20=0, loc 0, att 40) = 214; buy
(m20=2, loc 0, att 70) = 86.

### 3.5 Trading — guide vs ROM — verified (no disagreements)

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
| Gems | 188 | 200 | 86 | 428 |
| Jewellery | 201 | 320 | 197 | 315 |
| Lottery Tickets | 193 | 20 | 10 | 20 |
| Mana | 203 | 40 | 18 | 42 |
| Nectar | 198 | 170 | 364 | — |
| Tomes | 195 | 5 | 2 | 5 |
| Weapons | 200 | 95 | 50 | 101 |
| Wood | 196 | 15 | 5 | 15 |

- **Buy:** 16/20 guide buy prices fit `(base/2)·attitude` (the item-14
  halving active, attitude 15–94 depending on the merchant). The 3 Mesa
  stones fit `base·attitude` (no halving at Mesa). Nectar fits
  `2·base·attitude` (doubling active at Commerce).
- **Sell:** 17/17 guide sell prices fit: sell =
  `$2EA92(14, slot)/2` with the doubling active, so sell ≈ base
  (attitude near neutral) — except Gems, whose slot (2) is the
  Commerce merchant's doubling slot, so sell ≈ 2× base there (see
  below). This implies the doubling condition (`m20==32` **or**
  location 367) holds at Commerce, the sell city for most goods.
- **Gems sell 428 is CORRECT — the guide was right, the earlier
  "impossible" verdict was wrong.** The earlier analysis missed the
  second slot multiplier in `$2EA92` (§3.4): the `$1B299` doubling
  table. Gems is record 188 (bytes `01 2e 00 38`, raw 56 → base 200),
  slot 2 (record − 186), and the Commerce merchant (m20=32) has
  `$1B298` word `0xFF02` — doubling slot 2, halving slot never (0xFF).
  So at Commerce `$2EA92(14, 2)` = 200 × 2 (m20/location doubling)
  × attitude × 2 (slot doubling), then sell = `$2EA92/2`. At live
  attitude 40: 400 − (−10·400/140) = 428, ×2 = 856, /2 = **428**
  exactly. Sell range at Commerce over att 0–100 is 258–542.
  **Live (2026-11-10, `.scratch024/`, 6/6):** `$2EA92(14, 2)` =
  856 @ att 40 (sell 428), 1084 @ att 0 (sell 542), 516 @ att 100
  (sell 258), 800 @ att 50 (sell 400); control (m20=0, loc 0,
  att 40) = 214 (sell 107). The guide's buy 86 is likewise exact:
  `$2EA92(14, 2)` = 86 at the m20=2 merchant (halving slot 2, no
  doubling), live attitude 70. No second sell path is needed —
  the traced sell path (`$1FB88`) produces both guide numbers.
  (Correction of the "impossible, max 2.72×" claim, which omitted
  the slot doubling; the true max `$2EA92` for a slot-doubled good
  is 5.43× base.)
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
- **Sell `0x1FB88`:** price = `$2EA92(14, slot)` — first arg is the
  literal 14 (the goods category); gold received = `price/2` (the
  single halving at `$01FB9E`, `divs.w #$2`; the sell display at
  `$02897A` shows the same halved price); receive via `$2BBD2(1, price/2,
  0x400, leader)`; remove item via `$2BBD2(1, −1, item*64+slot, leader)`;
  `$26B58` sold message; `$FFBB72` stock byte decremented. Sell slot
  chosen via `$2CC62(leader, $FFBB6F, $FFBB72+1)`; if result < 2 → exit
  (`0x1FC74`).
- **Bribe / attitude:** attitude lives in merchant `+0x22` and enters
  the price formula. **Attitude repair is LOCATED (2026-11-10)
  [static]:** the persistent attitude table is `$FF00C0` (36 words,
  indices 0–35, one per merchant identity, each in [−100, +100],
  saved/loaded with a +0x80 bias); CAMP (`$03019a`) raises each entry
  by +3 toward 10 (entry 34 skipped), and `$02CE74` / `$030628` /
  `$035656` are the attitude adjustments (see `docs/save.md`). **The
  Bribe action itself is LOCATED (2026-11-10) [static]:** it is the
  merchant-submenu verb "Bribe" (ROM `0xCD38C`, in the
  Buy/Sell/Show/Bribe/Fight submenu, matching the official manual),
  record byte 12 = `0x19` = **C 25**; the C-dispatch (`$02068E`)
  case 25 goes to handler **`$020466`**, which checks the party
  gold (`$FF02DE`, char struct `+0x2A`) is ≥ 10 (`cmpi.w #$a`, skip
  if less), deducts **10 gold** via `$2BBD2(char, 0x400, −10, 1)`
  (`$0204A0`), then raises the attitude via `$02A22A` →
  `$0298D2` → `$02CE74` (positive delta). The exact attitude delta
  is data-driven (from the conversation event record loaded by
  `$032D4C`) and is [open]. **Delta mechanism, PINNED (2026-11-10)
  [static]:** `$02CE74(char, delta)` (`$02CE74`) applies the delta
  in two places — the merchant's **live** attitude (`+0x22`) moves
  by the **full** delta, clamped to [−100, +100] (`$02CEAC`–
  `$02CF00`); the **persistent** `$FF00C0` entry (indexed by the
  merchant's `+0x20`) moves by `(char.+0x26 × delta) / 100`, also
  clamped to [−100, +100] (`$02CF04`–`$02CF80`) — so the live
  attitude jumps by the whole delta while the saved attitude moves
  by only the merchant's `+0x26`-percent of it (the `+0x26` byte is
  the per-merchant "influence" percentage from template byte
  `$CF1BE`; e.g. 80 for most merchants, 90 for some, 5 for the
  hostile ones). `$02CE74` is called from `$0298D2` with delta =
  ±(event word & `0xFFF`) — positive at `$029C66`, negative at
  `$029C8A` (the sign is the event word's type; see below).
  **Event records, ENUMERATED (2026-11-10) [static]:** the Bribe
  event (id 8) lives in the `$0D3102` conversation table (1005
  12-byte records); 11 records have word0 == 8. Each record carries
  **two** event words, both packed as (type << 12) | delta: the **+10
  word** (dispatched first) and the **+8 word** (dispatched only if
  the first dispatch leaves no effect). `$0298D2` dispatches on the
  type (jump table `$029F8A`, types 0–14; a second table `$02A1EE`,
  types 0–13, takes the +8 word on fall-through): type 1 →
  `$02CE74(+delta)` at `$029C4E` (attitude up), type 11 (0xB) →
  `$02CE74(−delta)` at `$029C70` (attitude down) — the only two types
  that reach `$02CE74`. Type 3 → `$029C94` → a delta dispatch
  (`L029DB4`); rec 44 (delta 1) resolves to `combat_battle_end`,
  not an attitude change. Type 0xF has **no case in either table**:
  the merchant's reply text is shown, but no attitude function is
  ever called — a +0x02==1 merchant's Bribe changes attitude by
  exactly zero (live and persistent) while the 10 gold is still
  deducted. **Corrected 2026-11-11 [static, both dispatch tables
  fully decoded]:** the earlier note said type 3 →
  `$02CE74(−delta)` and type 0xF → `$025074`; the down path is
  type 11, and `$025074` is inside `combat_move_unit` `$024984`,
  unrelated to events. The 11 Bribe records: rec 18
  (+2=1, +10=`0xF000`, type 0xF, delta 0), rec 19 (same as 18),
  rec 20 (+2=0, +10=`0x1032`, type 1, **delta 50**), rec 44
  (+2=0, +10=`0x3001`, type 3, delta 1), rec 75 (+2=0,
  +10=`0x1063`, type 1, **delta 99**), rec 176 (+2=`0x084C`,
  +10=`0xC010`, type 0xC, delta 16), rec 189 (+2=`0x0856`,
  +10=`0xF000`, type 0xF, delta 0), rec 438 (+2=`0x0900`,
  +10=`0x6356`, type 6, delta 854), rec 548 (+2=`0x00C1`,
  +10=`0x645D`, type 6, delta 1117), rec 550 (+2=`0x00C2`,
  +10=`0xF000`, type 0xF, delta 0), rec 603 (+2=0, +10=`0x100F`,
  type 1, **delta 15**). **Which record matches is the merchant's
  +0x02 (template index):** `$0331A4` scores each record as
  `0x4000` (if record+2 == merchant +0x02 and +0x02 ≠ 0) +
  `0x10000` (event id matches) + `RNG(0x400)`; the highest score
  wins, RNG breaking ties among equal base scores. Merchant
  templates are indexed 0–39+, so only +2 = 0 or 1 can match a
  merchant (the large +2 values are non-merchant characters). For
  a merchant with +0x02 == 1, recs 18/19 win outright (base
  `0x14000`) → type 0xF. For +0x02 == 0 or 2–39, all event-8
  records tie at base `0x10000` and the winner is RNG-dependent —
  so **the Bribe's delta is not a single universal number; it
  depends on the merchant, and for most merchants it is
  RNG-selected among the tied records — the type-1 records
  (+50, +99, +15) raise attitude, while rec 44 (type 3, delta 1)
  ends combat instead of changing attitude. The +4/+5-byte match flags do not
  discriminate for a typical merchant (most templates have
  +0x17 = 0, so the +4-byte flag is skipped; record+5 is 0x00
  while the attitude index is non-zero). **Delta mechanism
  confirmed LIVE (2026-11-10, `.scratch023/`, 6/6, test ROM
  `d4a75f32562e6f3732ae0ec74df34b97`):** `$02CE74` called directly
  with a known merchant struct (char 5, +0x20=7) and a known delta
  — live +0x22 moves by the full delta and the `$FF00C0` entry by
  pct×delta/100, both clamped [−100,+100]: (+50, pct 80, live
  50→100, entry 10→50), (+50, pct 80, live 90→100 clamped, entry
  10→50), (−15, pct 90, live 60→45, entry 20→7 — the divs
  truncation −1350/100 → −13), (−50, pct 100, live 50→0, entry
  −90→−100 clamped), (0, pct 80, unchanged), (+99, pct 80, live
  0→99, entry 0→79 — the real rec-75 max delta). The `$0331A4`
  record-match is **RESOLVED [live]** (2026-11-10, `.scratch025/`,
  batch mode, RNG seed 1): +0x02 == 1 → rec 19 ($F000, type 0xF,
  delta 0); +0x02 == 0 → rec 20 ($1032, type 1, +50) — exactly the
  simulated picks, SP unchanged, no hang. The old debugger failures
  were a SIGSEGV from an unset char struct (`$FF02B2`/goods list),
  not a hang — the no-match infinite-recursion hypothesis is refuted
  for these inputs.
  **$02A22A return semantics, PINNED (2026-11-10) [static]:**
  `$02A22A(char, arg2, event_id)` returns
  `char[char[arg1].+0x14].+0x26` — the +0x26 byte of the struct
  indexed by the caller's +0x14 word. For event id 8 (and any id
  except 0/1) it returns that byte directly; id 1 takes an RNG
  branch. `$0298D2` uses the return value as a **char index**
  (into `$FF02B4` + index×52), so in the Bribe context the byte
  is the merchant's char index — **not** the percentage. The
  percentage `$02CE74` uses is a *different* +0x26 byte, read
  from the struct identified via the merchant's +0x27 byte. The
  two +0x26 uses (char index vs. percentage) come from different
  structs; do not conflate them. The handler is gated on
  `$01E49A($FF0E18)` returning 0 (a message-queue-state
  precondition). There is **no** Bribe goods code in `$2BBD2`
  (quotient 16, remainders 0–4 only; remainder ≥ 5 exits) — the
  Bribe is a verb/C-code action, not a goods transaction.
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

  All other types leave the base unchanged. `-$a(a6)` is the **step
  count** the routine returns in `d0` — 0 = no step, 1 = one cell,
  2 = two cells — not a blocked flag (the old "(1 = blocked, 0 = free)"
  reading was inverted: handlers set it to 1 when the step is
  *allowed* and leave it at its entry-cleared 0 when it is not). It is
  set to 2 only by types 10/11 in mode 2, for a straight
  vertical/horizontal step (with `-$c(a6)=$FFFF`, which skips the slope
  check below). Types 4, 12–16, 29 clear it unconditionally (never set
  it); types 30–34 clear it and set it to 1 only for mode 7 (31–33
  also for mode 6 when combat-flags bit 0 is set); the rest test the
  mode and the step-direction deltas (struct `+0x0A`/`+0x0C`). The
  caller (`combat_move_unit` `$024984`) uses the return as a count:
  `d4==0` skips the position update and `map_place_record_step` runs
  `d4` times; inside `$1C892` the step deltas are multiplied by `-$a`
  (`$01D916`/`$01D926`) and `-$a==0` at the end marks the step record
  blocked (struct `+0x18=$FF`, `$01D946`). A slope check also zeroes
  it: if `-$c(a6)==0` and `-$12(a6)` (|height delta|, minus 1 when both
  tiles have bit 8 set) `>= -$1a(a6)` (4), the step is blocked
  (`$01D938`). Note the mode matters: walkability is judged in mode 2
  (via `map_walk_check`, the `$02DC0C` gate), where Grass → 1 and
  Forest → 0; in vessel mode 0 the Grass handler leaves `-$a`=0 — the
  harness's mode-0 (3,1) on Grass is the cost, not a step (the cost is
  computed before the dispatch regardless of `-$a`).
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
(below). The **terrain-type → terrain-name mapping is now pinned by a
world-map pin (2026-11-10, see below)** — Road, Desert, Grass, Swamp
and Ice all have a `$5EDC4` type. The manual's rates for
Grass/Swamp/Ice remain approximate (see the verdict below); the pins
are mapping claims (which type is which terrain on the world map),
not rate claims.

| Manual (per mile) | Food | Water | Code match |
|---|---|---|---|
| On foot — Road | 1 | 1 | **type 9, mode 0: set (1,1) ✓ [live]** |
| On foot — Grass | 4 | 2 | **type 1 [live, world-map pin]** — manual approximate, water 2 unattainable in any mode [live/static, resolved] |
| On foot — Desert | 7 | 5 | **type 17, mode 0: (3,1)+(4,4) = (7,5) ✓ [live]** |
| On foot — Swamp | 8 | 4 | **type 8 [live, world-map pin]** — manual approximate, water 4 unattainable in any mode [live/static, resolved] |
| On foot — Ice waste | 4 | 3 | **type 6 [live, world-map pin]** — manual approximate, (4,3) unattainable as a flat cost [live/static, resolved] |
| Boat, shallow | 1 | 1 | base (1,1) ✓ (no addition) [live] |
| Boat, deep | 5 | 20 | **type 0, mode 7: (1,1)+(4,19) = (5,20) ✓ [live]** |
| Ship, deep | 1 | 1 | base (1,1) ✓ [live] |
| Dino, road | 1 | 1 | type 9, mode 1: set (1,1) ✓ [live] |
| Dino, other | 3 | 1 | **mode 1 base (3,1) ✓ [live]** |
| Dragon, all | 40 | 40 | mode 4 is **always (38,38)** — the manual rounds 38 to 40 **[live/static, resolved]** |

Code costs actually attainable on flat terrain **[live]**: mode 0 →
(1,1), (3,1), (7,5), (5,5), (6,5); mode 1 → (3,1), (1,1), (6,7);
mode 4 → (38,38); mode 7 → (1,1), (5,20), (5,5); mode 2 → (5,20)
on type 0, **(3,3) on type 17**; mode 6 → (5,5) on type 17. Static
enumeration over all 8 modes × 35 terrain types gives attainable
water values **[1, 3, 5, 7, 20, 38] — never 2 or 4**. So the manual's
Grass (water 2) and Swamp (water 4) are **unattainable in the code in
any mode, on any terrain, with any height** (the height term only
affects food, never water — `$01D8B4` writes to `+$1A` only). Water 3
is attainable only as mode 2, type 17 → (3,3) **[live, 2026-11-10,
46/46 harness]** — but that is not on foot (mode 2, not mode 0) and
type 17 is Desert, not Ice, so (4,3) is unattainable as a flat
on-foot cost too. **Verdict: the manual is approximate for
Grass/Swamp/Ice.** The food values (4, 8, 4) are attainable via the
height term (base 3 + height/2), but the water values (2, 4, 3)
cannot be produced by any code path. Desert and Road match exactly,
so the manual is generally accurate — but these three terrains do not
correspond to any per-step cost the code can produce. **Desert is the
one manual on-foot terrain that matches exactly: type 17 gives (7,5)
on foot.** The type identities are mapping claims, not code claims —
they were pinned by a world-map pin (below), not by the rates.

#### World-map pin: Grass = type 1, Swamp = type 8, Ice = type 6 [live, 2026-11-10]

The manual's rates cannot pin these three (see the verdict above —
water 2/4/3 are unattainable), so they were pinned by matching
overworld coordinates to terrains named in the game itself
(dialogue + the fan world map), then reading the live `$5EDC4` type
at those coordinates with a focused `$1C892` harness
(`.scratch007/harness_types.s`, test ROM
`47964be7dd96170794817b85f66120f3`, **9/9 types live-confirmed**;
the 2 food mismatches are a blocked step and a +2 height slope, not
type errors — see the harness note below).

- **Ice = type 6 [live, high confidence].** Type 6 is the only
  strongly **bimodal** terrain: 4,924 cells in the far north
  (y 0–56) and 5,120 in the far south (y 168–224), sparse in the
  middle (983 / 617) — a polar distribution, the ice caps at both
  poles. It is the dominant far-south land type. The dialogue
  places the ice in the far south explicitly: *"a town in the far
  south on the polar plains … at about 3' 22'"* (Sunrise) and
  *"around 6' 21' on the south ice plane"* (the Conjurers' skull
  cave). The fan world map shows its pale/white terrain at the
  diamond's poles. Live: type 6 at (48,5) far north, (96,202) and
  (100,200) far south.
- **Grass = type 1 [live, moderate confidence].** Type 1 is the most
  common non-polar land type (8,231 cells) and is uniformly spread
  across all latitudes (bands 1830 / 2228 / 2071 / 2102) — the
  default ground cover. Live: type 1 at (25,100).
- **Forest = type 4 [live, high confidence].** Type 4 (6,933 cells on the
  overworld, 18,094 across all 252 chunks) is a distinct terrain, NOT a grass
  variant: it is non-walkable (`$02DC0C` → 0, live 13/13; the `$01C892`
  type-4 handler `$01D052` never sets the proceed flag, and a live step onto
  type 4 at (107,106) was blocked, d0=0, blocked=255), while Grass (type 1)
  is walkable, and the two tile sets are fully disjoint (83 type-4 indices vs
  18 Grass indices, zero overlap). The manual lists Forest as a terrain the
  Dino cannot handle ("Most land except forest/water",
  `docs/research/official-manual-transcript.md:31`), and the dialogue names
  forests in the world ("the great forest on the eastern coast of the east
  continent", rec_0583; Doggania's forests, rec_0859; "can't handle forests
  or mountains", rec_0160). Cost: no food/water addition — base (3,1) on flat
  ground, same as Grass — but the step is blocked on foot, so no cost is
  computed; the two are told apart by walkability, not cost. Largest type-4
  region is 252 cells at x 297–320, y 174–194 (south-east, near the eastern
  coast). Mountains are type 19, not type 4 (walkable, +3/+4, the big brown
  massif).
- **Swamp = type 8 [live, moderate confidence].** The Fire Swamp is
  where the witch Hideous lives (*"Stay away from the Fire Swamp
  to the south of here!"*; *"the swamp in front of, and very close
  to, her home"*). Hideous is listed at sextant 12°–13° (≈
  overworld (120,130)); the region south of it (x 100–140,
  y 130–170) is dominated by types 4 and 8, and type 8 is the
  mid-latitude terrain concentrated there (5,224 cells, bands
  301 / 1781 / 2442 / 700), while type 4 is ubiquitous. Live:
  type 8 at (127,130) in that region.
- **Not used as a pin:** the fan world map
  (`docs/research/rings-of-power-ru/RingsOfPower-World.png`) was
  tested as a geometric source and **rejected** — a sea-mask IoU
  search over the isometric parameters and all 4 orientations
  peaked at 0.085–0.117 (chance). It is an artistic render, useful
  only for rough geography (desert south-central, pale terrain at
  the poles), not for precise coordinates. The sextant→overworld
  mapping is only approximate (≈ ×10; 7–8 of 20 cities land on
  type 9 roads at ×10, all 20 on land), so town coordinates from
  dialogue/the Locations guide were used regionally, not as exact
  cells.
- **Harness note:** the 9-case run reports 7/9 OK because two
  food values differ — case [4] (type 4 at (107,106)) food 0 is a
  **blocked step** (d0=0, blocked=255; the step did not happen, so
  no cost was computed), and case [5] (type 8 at (127,130)) food 4
  is a **+2 height slope** (base 3 + 2/2). Both types still read
  live-correct. The type column is 9/9.
- **Desert coordinate correction:** the type-17 cell is the harness
  destination (59,81) (case x=58, step east), not (58,81) itself —
  (58,81) is type 1. The earlier "(58,81) is a type-17 cell" was
  shorthand for the case's x-coordinate.

**Verdict: the Dragon manual rate (40/40) is a rounding of the code's
(38,38).** Mode 4's cost is **always (38,38)** — no terrain addition
and no height term can change it. The dispatch at `$01CF38`–`$01CF68`
is reached for mode 4 only if the terrain type is 29 (`$1D`); type 29
does not exist in `$5EDC4`, and the type-29 handler (`$1D65A`) adds
nothing anyway (`clr.w -$a(a6)` + `bra.w L01D796`). And the height
term is **skipped** for mode 4: when the dispatch is skipped (mode 4
on a non-29 type), it goes to `L01D9B6` → `L01C984` (direct return),
bypassing the height term at `$01D800`–`$01D8B4`. **[live, 2026-11-10,
46/46 harness]:** mode 4 on a +4 slope (148,15) still gives food 38,
water 38 — the height term does not run for the dragon. So (40,40)
cannot be produced by any code path; the manual rounds 38 to 40 (or
approximates). The same skip applies to mode 5 (dispatch skipped
entirely) and to `$FF00A4 == 0`.

#### Live harness — `$1C892` (2026-11-10, 46/46 cases)

`.scratch007/harness_c892.s` + `build_c892.py` + `run_c892.py`
(test ROM `.scratch007/test007.gen`, MD5
`58e9778049980ea6861954d376b0a65c`). Hook at the attract loop `0x35C`
(`jsr $FD0CC.l`, trampoline at `0xFD0CC`, exits with `rts`), results
in `$FFD000+` (7 words/case: mode, live type, dest tile, food, water,
d0, blocked). Each case sets the struct at `$FFD300` (mode at `+0x08`,
dx = 1, dy = 0, `+0x1E = $FFFF`, `+0x20 = 2`), positions the party at
a chosen overworld (x,y), loads the real chunk via `$19692`, calls
`$1C892`, and records the struct `+0x1A`/`+0x1C` plus the live
`$5EDC4` type (`rol.w #$6` extraction, as `$02dc0c` does it) and the
destination tile from `$FF0248`. `$FF00A4 = 1` is required (the terrain
dispatch at `$01CF38` is skipped when it is 0). **All 46 cases passed
against the live-corrected expectations** (ran flag `$FFD000 = $BEEF`,
canary `$FFDFFE = $5A5A`; every destination tile matched the offline
chunk decode, proving the chunk-cache positioning is correct). The
46 cases: mode 0 on 30 `$5EDC4` types (0–23, 25, 27, 28, 30, 31, 33 —
types 24/26/29 do not exist in `$5EDC4`; 32/34 exist but no flat east
step onto them was found in the overworld); mode 1 on types 9/0/17/19;
mode 4 on types 9/0; mode 7 on types 0/9/17; mode 2 on types 0/17;
mode 6 on type 17; and three height cases on type 9 (delta +4 → food
3, delta +2 → food 2, delta −4 → food −1 — **the height term is
confirmed live, including the negative direction: food can go below
the type-9 base, to −1**), plus two discrepancy cases added 2026-11-10:
mode 2 type 17 → (3,3) (the only water-3 in any mode) and mode 4 on a
+4 slope (148,15) → (38,38) (**the height term is skipped for the
dragon** — the dispatch bypass at `$01CF50`–`$01CF68` returns via
`L01D9B6` → `L01C984` without running it). Two harness bugs were found and fixed
during the run: the type extraction used `lsr #6` (wrong — it reads
bits 6–11, not 10–15; fixed to `rol #6` like `$02dc0c`), and the
`lsr #10` fix attempt was rejected by GAS (immediate shifts are 1–8
only). `$1C892` also returns the step count in `d0` (0/1/2, see the
`-$a(a6)` note above) plus a blocked marker in struct `+0x18`
(`$FF` when blocked): `d0` varies by terrain type *and* by
coordinate — the handler sets it per type+mode (e.g. Grass mode 0
leaves it 0 at every coordinate), and the same type 9 gives d0 = 1 at
(151,15) and (150,15) but d0 = 0 at (148,15) (a +4 slope — likely
the `$01D938` slope check, unconfirmed) and (266,101) — likely entity
occupancy at the destination, separate from the cost, and not pursued
here.

**No plain rate table exists in the ROM** (searched byte sequences
`[1,8,7,4,4]`/`[1,4,5,3,2]`, fan order, interleaved pairs, word tables
— all 0 hits). The rates are computed in code as above.

#### Related [static]

* **`$FF0E16` is a clock, not a step counter** (increments every frame
  in `$2155E`, wraps at 2400; the palette routine `$170DA` reads it to
  pick the day/night palette — see the CAMP clock entry above). The
  consumption is not driven by it; it is driven by the movement
  dispatcher `FUN_024984`.
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
    song 8 (`jsr $173EC` at `$02C884`) — **VERIFIED LIVE 2026-11-10**
    (harness `.scratch007/harness_life_song.s`, test ROM
    `9179140b088d141c20fd72e9415befee`, 1/1): on a revive, `$FF022C`
    becomes `$000F363E` (song 8's data — the song-8 dispatch case at
    `$1748A` pushes `$F363E`, not `$ED0E8`, which is song 0's data) and
    `$FF0230` becomes `$000F373E` (song 8's end, u32 at `$F363A`); the
    Z80 driver is uploaded (Z80 `$00DA` = `$16`, signature clobbered)
    and the play command is written (Z80 `$000B` = `$0D`). A Life call
    on a live member starts no song (`$FF022C`/`$FF0230` stay 0). Note:
    the Life path calls the dispatch (`$0173EC`) directly, bypassing
    the `$0173C0` wrapper, so **`$FF012E` (current song index) is NOT
    updated** — it stays 0 (measured). **Watchdog behaviour RESOLVED
    [live] (2026-11-10, `.scratch026/`, test ROM
    `e1ddd59f9871e67a7ded156ab096e271`, 300 frames sampled):** song 8
    plays to completion (~1.2 s, 72 frames) and only then does the
    watchdog replay song 0 (`$FF022C` → `$000ED0E8`, `$FF012E` = 0,
    exactly one replay at frame 72) — a natural end, not a cut-off.
    The bypass is the cause of the replay (it replays `$FF012E` = 0),
    but it does not truncate the sting.
    Audio captures of the harness run are silent after the boot
    transient, but song 8's own dedicated capture
    (`.scratch018/songs/raw_song08.raw`) is likewise essentially
    silent (RMS 23 after 0.5 s), so the silence does not contradict
    the start — whether the 1.2 s sting is audible in real gameplay
    is [open]. Prices
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
    world clock around — day becomes night and vice versa.)
    **Day/night ranges — LOCATED and live-verified (2026-11-10, 15/15
    harness cases, `.scratch009/harness_daynight.s`, test ROM
    `2bdb36a03d9fbd2aeca24f164df63148`).** The palette routine
    **`FUN_0170da` (`$0170DA`)** reads the palette mode `$FF0126`
    (high nibble of the location-table byte at `$D63E7` + location×4)
    and the clock `$FF0E16`, computes `q = clock / 18`, and selects
    CRAM palette 0. For mode 2 (46 outdoor locations, incl. the
    overworld 0–31): **NIGHT is clock 18–539** (`q` 1–29, palette 19,
    dark blue-shifted, brightness 58); **DAY is clock 558–2399**
    (`q` 31–133, palette 10, bright, brightness 134); **dusk is clock
    0–17** (`q` 0, crossfade DAY→NIGHT, factor `(clock%18)/2`);
    **dawn is clock 540–557** (`q` 30, crossfade NIGHT→DAY, same
    factor). The blend (`FUN_01225c`) interpolates per channel as
    `A + (B−A)·factor/8` and uploads to CRAM palette 0; the factor
    runs 0–8 over each 18-frame transition. The CAMP anchors are the
    **starts** of the transitions: **0 = start of dusk** (pure DAY at
    the instant of setting, fading to NIGHT over the next 17 frames)
    and **540 = start of dawn** (pure NIGHT at the instant of setting,
    fading to DAY over the next 17 frames) — so 0 and 540 are on
    opposite sides of the boundary in the sense that 0 leads into
    NIGHT and 540 leads into DAY. The clock itself increments by 1 per
    `$2155E` tick and wraps at 2400 (`divs.w #$960`), so a full
    day/night cycle is 2400 ticks (DAY 1842, NIGHT 522, transitions
    18+18). `$170DA` is called from the per-frame tick `$2155E`
    (`$0215F6`: when `$FF0124` is dirty, or when mode 2 and `q` is 0
    or 30, so the blend updates every frame during a transition) and
    on location load (`$017976`). Other modes: 0 (99 locations) and 3
    (3 locations) → always DAY (pal 10); 1 (2 locations, 59/62) →
    always NIGHT (pal 19); 4 (2 locations, 132/133) → palette 23
    (brightest, blue-heavy, brightness 172). `$FF0124` is the
    "palette dirty" flag: CAMP/Sleep/location loads set it to `$FFFF`,
    `$170DA` clears it after updating the palette. **Dusk-blend
    bit-14 (`$4000`) artifact — RESOLVED (2026-11-10) [live].** The
    artifact has TWO parts, and only the first is blend arithmetic.
    (1) The blend (`FUN_01225c`) uses unsigned `mulu.w` + logical
    `lsr.w #3` on the signed per-channel difference `(B−A)`, so a
    negative difference produces a large garbage value instead of a
    small negative one; when the red result lands on `0x2000`/`0x2001`,
    the red `asl.w #1` places it at bit 14. This sets bit 14 in the
    RAM output buffer `$FF864A` on the entries with **negative red
    diffs** (dusk: 5, 7, 8, 9, 10, 11, 12, 14, 15) — correctly
    emulated by the harness runner's model. (2) The EXTRA `$4000` on
    the R-diff==0 entries (0, 1, 2, 3, 4, 6, 13) is **not** produced
    by the blend at all: the buffer is clean there
    (`.scratch009/harness_b14.s`, test ROM
    `9811d05f7e9599c6b943846103d0c940` — `$FF864A` matches the model
    exactly in all 4 cases, dusk/dawn/zero). It appears only in the
    CRAM read-back, and only when the uploaded palette has bit 14 set
    on **CRAM palette-0 entry 12**: then ALL 16 CRAM entries read
    back with bit 14 set. When entry 12 lacks bit 14, bit 14 is
    stripped from every entry on read-back — even from entries that
    had it in the buffer (`.scratch009/harness_b14b.s` /
    `harness_b14c.s` / `harness_b14d.s`: single-bit-14 masks on every
    other entry read back clean; `{12}`, `{5,12}`, `{4,12}` and
    `{0..15}` all trigger the all-entries spread; `{5}`, `{5,13}`,
    `{0,7}`, `{1,8}`, `{6,13}` do not). `$11082`/`$D9EE` write the
    words verbatim to the VDP data port, so the spread is a VDP
    (BlastEm) CRAM write/read behaviour, not game code. Entry 12
    carries bit 14 in the dusk buffer because its red diff is −4
    (day red 7, night red 3): red result `0x2005`, `<<1` = `0x400A`.
    The dawn blend's buffer has no bit-14 entries at all (entry 12 =
    `0x042A`), so the spread never triggers there — that is why the
    artifact is dusk-only. Bit 14 is ignored by the VDP for display,
    and the visible R/G/B fields match the emulated blend exactly in
    all 15 cases. [Open] whether the entry-12 spread is real Genesis
    hardware behaviour or a BlastEm emulation quirk (needs real-hardware
    testing or BlastEm source inspection); the game-code side is
    settled. `$FF0E18` is not read by `$170DA` itself (it is passed
    by address to other routines, not part of the palette decision).
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

#### What would settle the open rates [resolved 2026-11-10]

The `$1C892` live harness ran 2026-11-10 (46/46 cases, `.scratch007/harness_c892.s`, test ROM `58e9778049980ea6861954d376b0a65c`): it called `$1C892` with a controlled mode and terrain (chunk cache pre-loaded via `$19692`) and read struct `+0x1A`/`+0x1C`. It pinned Road (type 9, 1/1) and **Desert (type 17, 7/5)** and confirmed the height term live, including the negative direction. The routine, the formula shape, the base costs (corrected live: mode 0/1 base is (3,1), not (2,2)), the terrain additions and the height term are now **live-verified**. **Both remaining discrepancies are resolved:** Grass/Swamp/Ice — the manual is approximate (water 2 and 4 are unattainable in any mode; water 3 exists only as mode 2, type 17 → (3,3), not on foot and not Ice); Dragon — mode 4 is always (38,38), the manual rounds 38 to 40 (no terrain addition for mode 4, and the height term is skipped for it — live: mode 4 on a +4 slope still gives (38,38)).

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
3. **Bribe (10 gold)** — **LOCATED (2026-11-10) [static]:** the
   merchant-submenu verb "Bribe" (ROM `0xCD38C`), C 25, handler
   `$020466`: checks gold ≥ 10, deducts 10 gold via `$2BBD2(char,
   0x400, −10, 1)`, then raises the attitude via `$02A22A` →
   `$0298D2` → `$02CE74` (positive delta). **Delta mechanism
   PINNED (2026-11-10) [static]:** `$02CE74(char, delta)` moves
   the live attitude (`+0x22`) by the full delta and the
   persistent `$FF00C0` entry by `(char.+0x26 × delta) / 100`,
   both clamped to [−100, +100]; delta = ±(event word &
   `0xFFF`), the event word being the matched `$0D3102` record's
   +10 word (type << 12 | delta). The 11 Bribe event records give
   type-1 deltas **50** (rec 20), **99** (rec 75), **15** (rec
   603), a type-3 delta of 1 (rec 44), and type-0xF records
   (recs 18/19/189/550, delta 0, no direct attitude change).
   **Which record matches is the merchant's +0x02 (template
   index)** — `$0331A4` scores `0x4000` for a +2 match +
   `0x10000` for the event id + `RNG(0x400)`; for +0x02 == 1,
   recs 18/19 win (type 0xF); for other merchants the winner is
   RNG-selected among the tied records, so **the Bribe's delta
   is not a single universal number**. **Delta mechanism confirmed
   LIVE (2026-11-10, `.scratch023/`, 6/6):** `$02CE74` moves the
   live attitude by the full delta and the persistent entry by
   pct×delta/100, both clamped [−100,+100] (see §3.5 for the six
   cases). The `$0331A4` record-match is **RESOLVED [live]**
   (2026-11-10, `.scratch025/`, batch mode): +0x02 == 1 → rec 19
   ($F000); +0x02 == 0 → rec 20 ($1032, +50) — the simulated picks,
   SP unchanged. See §3.5 for the full record table and the
   `$02A22A` return semantics. **Attitude repair is LOCATED (2026-11-10) [static]:**
   CAMP raises each `$FF00C0` entry by +3 toward 10 (entry 34
   skipped), and `$02CE74` / `$030628` / `$035656` adjust it — the
   persistent merchant-attitude table `$FF00C0` (36 words, indices
   0–35) is the backing store (see `docs/save.md`). Merchant
   attitude is confirmed in the price formula and the Bribe action
   that changes it is now located. (#021.)
4. **Gems sell price 428** — RESOLVED (2026-11-10) [live]: the guide
   was right; `$2EA92(14, 2)` = 856 at Commerce, att 40 (the
   slot-doubling table `$1B299` was missed in the earlier analysis),
   sell 428. See §3.5. (#021.)
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

### 6.1 Command 23 — resolved (2026-11-10) [static]

**There is no writer of command 23; the `$D28E` switch case 23 is dead
code.** The `$D28E` main-loop command switch (`$D740`) has 15 cases
(0, 10, 20, 21, 22, 23, 24, 25, 30, 35, 37, 40, 45, 50, 55); case 23
(`$D566`) calls `$1E5A0` then continues. The command byte lives at
`$FF0240`, and its only writer is `$12FE8` (`0x12FE8–0x13650`), which
builds a 4-byte record in its frame (byte0 = command at `-$4(a6)`,
byte1 = selection at `-$3(a6)`, word = -1 at `-$2(a6)`) and copies it
to `$FF0240` at three exit sites (`$013154`, `$0131CC`, `$01363C`).
Exhaustive enumeration of every immediate byte write to the command
slot `-$4(a6)` in the whole disassembly gives 14 distinct values —
0, 10, 20, 21, 22, 24, 25, 30, 35, 37, 40, 45, 50, 55 — **never 23**.
No register byte-write to `-$4(a6)` exists in `$12FE8`, no arithmetic
on `-$4(a6)` exists anywhere, and all `$FF0240` references in both
disassembly files are the reset RAM-clear and the `lea.l $ff0240.l,a0`
sites inside `$12FE8`. `$D28E`'s own frame writes are only 10
(`$D328`) and 0 (`$D462`, `$D8BA`). The only "23" near the command
production is `move.b #$17,-$3(a6)` at `$0135CC`, which writes 23 to
the *selection* byte (`$FF0241`) — and only when the selection index
`$FFA7F8` is already 23 (a verb-table index), producing command 25.
The handler `$1E5A0` is NOT dead: it reloads the current menu record
from `$FFA7F8` (via `$FF01EA` offsets into the `$CCDB8` verb table),
sets `$FFBB82`, and redraws unless the record's A byte is 'I'/'L'/'B'
— called live from `$1B994` (world-map redraw), `$209FC`
(command-24 handler), `$20BBE` (command-25 area), and `$2D4E0` (in
`$2D3DC`). So only the command-23 dispatch entry is dead, not the
routine. No live run: the static enumeration covers all code paths
exhaustively. (The matching "open" notes in `docs/architecture.md`
and `docs/logic-audit.md` §11 need the same update.)

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
