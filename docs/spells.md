# Spells / skills system (issue #008)

## Background

Rings of Power has no equipment and no weapon skills: combat is
spells-only. There are **120 spells**, stored as price-table records
1–120 in six blocks of 20 (`$D6768`, see `docs/logic.md` §3.3), and
**six effect (rank) tables** of 21 records each that actually define
what a spell does. The spell you *buy* (price record) and the spell
effect you *cast* (rank-table record) are different objects, joined
only by the caster's `+0x25` byte and rank — see §2.

The combat-rework evidence (`$DDBD8` rec 1004, "Did someone say redo
the combat a fifth time?") and the Gavin/Rubin authorship notes live
in `docs/logic.md` §Background and are not repeated here.

### Player-observed leads (hypotheses, not findings)

- The fan guide (ringsofpower.co.uk `spells.htm`, issue #033) lists
  spells per character: Buc (sorcerer), Slash (knight), Arrow
  (archer), Alexi (conjuror), Mortimer (necromancer), Obliky
  (enchanter) — six characters, six disciplines, six price blocks.
  That mapping is **not proven from code** (§1.3).
- The Russian walkthrough (rings-of-power.ru) mentions combat modes
  MANUAL / AUTO / Wary and spells STUN / WARN / CLUE. Player-observed
  only.

## 1. Spell list and names — verified

### 1.1 The name table `$CD431` — verified

893 entries × 16 bytes (`$CD431`–`$D0701`); entry = name, NUL-padded,
trailing byte (`+15`) `0x10` / `0x11` / `0x0E` / `0x0F`, meaning
unknown. Full dump: `disasm/spells/names_cd431.txt`. Referenced by
the price table (`+0` word = name index), char struct `+0x14`, and
the `$136FC` text-word indices.

Character names: **Buc 57, Slash 58, Mortimer 59, Obliky 60,
Feather 61, Alexi 62**. No discipline names ("sorcerer", "knight",
etc.) exist anywhere in this table.

**Unresolved — "Arrow" vs "Feather":** the fan guide calls the
archer "Arrow", but name 61 is "Feather". "Arrow" also appears as
name 80 **and** as spell name index 200 (block 3, rec 44 is the spell
"Arrow"). Which is the archer's ROM name is unresolved — it needs a
live new-game character-creation trace (#020). Do not rename
either in the remake until that is settled.

### 1.2 Spell list: price records 1–120 — verified

Spell ID = price-table record number (1–120). Full table with
`name_idx`, raw value and scaled shop price:
`disasm/spells/spell_list.txt`. Names are the 6-letter truncations
stored in `$CD431` (e.g. `Confse`, `Knwldg`); the full display names
come from the dictionary text system (`docs/` text docs).

| Block | Records | Spells |
|-------|---------|--------|
| 1 | 1–20 | Stun, Clue, Warn, Inform, Jolt, Confse, Knwldg, Help, Predict, Daze, Free, Mesmer, Insane, Shock, Support, Assist, Swarm, Mirage, Packs, Master |
| 2 | 21–40 | Stab, Cleave, Knives, Cut, Rend, Dice, Rip, Split, Sever, Puree, Sunder, Frigid, Swords, Torrent, Delete, Axes, Lava, Divide, Blades, Pain |
| 3 | 41–60 | Dart, Ripple, Shove, Arrow, Ambush, Surround, Dizzy, Brand, Blow, Tempest, Stream, Fling, Tornado, Implode, Fire, Shield, Unshield, Propel, Defend, Twister |
| 4 | 61–80 | Claw, Graze, Comfrt, Hurt, Relief, Wound, Solace, Slay, Cure, Blind, Death, Health, Dazzle, Insane, Repair, Restore, Freeze, Perfct, Raise, Reaper |
| 5 | 81–100 | Mix, Scatter, Dagger, Icebrg, Sword, Frenzy, Wall, Swamp, Geyser, Axe, Pool, Lava, Bear, Corpse, Alter, Dragon, Modify, Random, Mutate, Wyrm |
| 6 | 101–120 | Spark, Earth, Daggers, Rock, Bolts, Air, Rapids, Energy, Sabers, Flare, Icebrg, Axes, Blaze, Stones, Inferno, Flames, Master, Wave, Servants, Djinn |

Shop prices use the same raw-value tiers in every block
(`$2EA92`, `docs/logic.md` §3.4): raw 36→100, 56→200, 86→350,
101→500, 103→700, 106→1000, 110→1400, 116→2000, 125→2900. The
first spell of each block has raw 0 → shop price 2 (floor clamp).
Note the duplicate names across blocks: `Insane` (block 1 rec 13
and block 4 rec 74), `Master` (block 1 rec 20 and block 6 rec 117),
`Icebrg` (block 5 rec 84 and block 6 rec 111), `Lava` (block 2 rec
37 and block 5 rec 92), `Axes` (block 2 rec 36 and block 6 rec 112)
— different price records, different `name_idx` values, so the
duplicates are distinct spells that happen to share a display name.

### 1.3 Block ↔ discipline mapping — NOT proven (hypothesis only)

The names suggest block 2 = knight weapons (Stab, Cleave, Knives…),
block 3 = archer (Dart, Arrow, Ambush…), block 4 = necromancer
(Claw, Death, Raise, Reaper…), block 5 = conjuror summons (Bear,
Dragon, Wyrm, Djinn-adjacent…), but **no code found ties a price
block to a discipline or a character**. The six characters' spell
access is decided by the rank tables (§2) and the `+0x25` selector,
not by the price block. The remake must not hard-code
block→discipline until a character-creation / shop trace proves it
(#020). The fan guide's six-characters structure is the hypothesis
to test, not the answer.

## 2. Spell effect (rank) tables — verified

### 2.1 The pointer table `$FFA7CC` — verified

New-game init at `0x1B5F4` installs a 10-entry pointer table at
`$FFA7CC` (verified in `disasm/rop.s`):

| Rank | Table address |
|------|---------------|
| 1 | `$D6B6C` |
| 2 | `$D6BEA` |
| 3 | `$D6C68` |
| 4 | `$D6CE6` |
| 5 | `$D6D64` |
| 6 | `$D6DE2` |
| 7–10 | `$D6BEA` (rank 2's table reused) |

Rank here = caster order low nibble (`+0x18 & 0xF`) — the same
nibble that selects the level thresholds in `$2F030`. Ranks 7–10
share rank 2's table, so there are only **six distinct effect
tables** for ten ranks. Cold RAM at `$FFA7CC` is 0 before a new
game, so any routine that reads a spell record before new-game
init dereferences address 0 — the harness installs this table
itself (§8).

### 2.2 Record layout (6 bytes) — verified

Each table = **21 records × 6 bytes** (`0x7E` bytes). Record
indexed by the caster's `+0x25` byte; table indexed by
(caster rank − 1). Full dump with decoded fields:
`disasm/spells/rank_tables.txt`.

| Offset | Field | Meaning |
|--------|-------|---------|
| +0 (word) | `w0` | low 7 bits = damage base (`(w0 & 0x7F) / 3` in the damage path); bits 8–10 = effect class 0–7 (`$36E2E` reads `(w0>>8)&7`, 0 maps to 15); bit 11 tested in `$3B51E` / `$3B748` (heal-target selection when set) |
| +2 (word) | `w1` | low nibble = effect parameter 0–8 (≈ rec/2, capped at 8); `w1>>4` = the `$FF012C` action code the `$37D0E` tail installs (§4, §5); `(w1>>4)&0x7FF == 0` selects a status path in `$3B51E` (true when `w1` is in `0x8001`–`0x8008`: rank 4 recs 2/4/6/17) |
| +4 (word) | `w4` | Power cost base — see §3 |

**Records 19 and 20 are identical in every table** (verified in
all six tables, e.g. rank 1: both `w0=0x168D w1=0x0918 w4=1000`).
Record 19 is the top spell: the AI chooser (`$3BB4E`, §6.3) and
the player menu (`0x3BB72`, `move.b #$13, $25(a3)`) both write 19
into `+0x25`. Record 20 is dead weight — or a deliberate duplicate
so that `+0x25` = 20 still resolves to the top spell.

Notable `w1>>4` values (the action code a cast installs): `0x87D`
rank-2 recs 1/4/6/8/10/17; `0x87F` rank-4 rec 14; `0x87E` rank-5
recs 14/16/18; `0x091` rank-1 recs 19/20; `0x097` recs 19/20 in
ranks 2/3/4/6; `0x08E` rank-5 recs 19/20. These are **not** the
message routine's exact `0x7D`/`0x7F` codes (§5) — `0x87D ≠ 0x7D`
as a word compare.

Power-cost ladder (`w4`, rank 1): rec 0 = 0, recs 1–3 = 30–40,
recs 4–10 = 50–80, rec 11 = 600, recs 12–18 = 100–400, rec 19/20
= 1000. The top spell costs 1000 base Power before the
`×(modifier+1)×3` multiplier (§3) — i.e. 3000–12000 Power, against
a max Power of `(level+1)·1000` (max 9000 at level 8). At modifier
3 the top spell costs more than any character can ever hold, which
is why the out-of-power HP drain (§3) matters.

## 3. Power cost — verified

### 3.1 Cost formula `$3C2C0` — verified (asm + harness §8)

```
cost = record.w4 * (modifier + 1) * 3
modifier = (caster.+0x2C >> 8) & 3        ; 2-bit field, 0-3
```

Verified instruction-for-instruction at `0x3C2C0` in
`disasm/rop.s`: loads `struct[$FF0EAA].+0x2C` (via base `$FF02E0`
+ index `× 0x34`), `(word >> 8) & 3`, `+1`, `mulu.w record.+4`,
`mulu.w #6`, `lsr.w #1` (×6 then ÷2 = ×3). `$FF0EAA` is the
current-actor index; the record pointer arrives as the stack arg.
`$DE8E` is a 32-bit multiply (`d0 = d0*d1`), not a table lookup —
it computes the `(rank−1)*4` and `+0x25*6` offsets in the callers.

### 3.2 Deduction `$37D0E` — verified (asm + harness §8)

`$37D0E(char_idx)`; if the arg is 4, the char is
`struct[$FF0EAA].+0x0A` instead. Steps (verified at `0x37D0E`):

1. Record = rank table `(caster order low nibble − 1)` + `+0x25 × 6`.
2. `cost = $3C2C0(record)`.
3. `new Power = clamp(cur Power − cost, [0, max Power])`.
4. **Out-of-power rule:** if new Power < 1 **and** cur HP > 5:
   Power = 0, HP −= 5. (Verified: `tst.w $1e(a0); bgt` /
   `cmpi.w #$5, $1c(a0); ble` / `clr.w $1e(a0)` /
   `subq.w #$5, $1c(a0)` at `0x37DE0`–`0x37DFE`.) Casting with no
   Power left drains 5 HP per cast — the game lets you kill
   yourself casting.
5. Tail: `$25456` twice, `$FFC37C = $FFC37E = -1` (unconditional —
   the harness's `0x7777` sentinel is always overwritten, §8.2),
   `$FF012C = record.w1 >> 4` (via `$3B4AC`; if 0 → `0x200`),
   `$25DE4` then maybe `$2140A`, actor `.+0x00 |= 0x4000`,
   `$FF012A = 1`.
6. **`$25456` is not contained — the harness stall (§8.3):**
   `$25456(char_idx, ...)` first checks `struct[idx].+0x00 & 0xF`;
   if it is 0 it calls `$12FA0(0x1C)` → `$12072` (sound setup),
   which never returns in the cold attract context (no game /
   sound state initialised). The first harness runs stalled
   exactly there: S1's `$3A62E` dispatches leave
   `slot0.+0x00 = 0xA0` (low nibble 0), and `setup_spell` did not
   reset it. The fix (in `tools/test_spells_harness.s`) resets
   the whole slot via `setup_combat` (`+0x00 = 4`, low nibble
   non-zero, `$12FA0` skipped) and forces `+0x04 = 0` so the
   tail's `$25DE4` / `$2140A` pair indexes enemy record 0
   (saved/restored) instead of the bogus `0xFF` slot.

## 4. Action dispatch `$3A62E` — verified (static + harness §8.2)

**This answers #007 open question 1 at the dispatch level: both
damage paths run, in different turns — `+0x24` selects spell vs
melee.** `$3A62E(char_idx)` (verified at `0x3A62E` in
`disasm/rop.s`):

1. Attacker = `struct[idx]`; target = `struct[attacker.+0x1E]`.
   If `+0x1E == -1`, a find-target scan runs (`$258EE` path via
   `$3A9CE`).
2. Pre-checks: target's `$FFB0D0[+0x04]` word must be `< 0x24`
   (inline, `0x3A6CE`–`0x3A6E8`; same test as `$25DE4`), and
   `$1E0A4(attacker.+0x0A)` runs (helper, meaning unmapped).
3. If attacker `.+0x24 == 0x50`: `$FF012C = 0x50` (via `$3B4AC`),
   `$FFC418 = target idx`, `$FFC41A = attacker.+0x22`,
   `$FF012A = 1` → the giant spell state machine `0x3E2D4`.
4. Else if `+0x24 != 0` **and** `$FF012C != 7` **and** target
   `+0x2C` bit 15 clear: `$FF012C = +0x24`, same
   `$FFC418` / `$FFC41A` / `$FF012A = 1` setup → giant spell path.
5. Else (attacker `.+0x18 != 0` **and** `+0x24 == 0`): melee —
   `$3B1EE(attacker.+0x22, attacker.+0x1E, attacker.+0x20)`,
   i.e. caster idx = attacker `.+0x22`, target idx =
   attacker `.+0x1E`, base = attacker `.+0x20` (max HP).
   `$3B1EE` takes three separate word args (pushed at
   `0x3A832`–`0x3A842`; the second call site `0x3B094` pushes
   the same three) — there is no packed pair. That resolves the
   #007 arg puzzle at the calling-convention level, but **not**
   the field puzzle: `+0x1E` is current Power and `+0x22` is
   max Power in the party context (`docs/logic.md` §2.2,
   `$37D0E` §3.2), yet here they are read as target/caster
   indices. Who writes indices into those fields before
   `$3A62E` runs — or whether the combat attacker is a
   different record layout — is still open (#021, §9 Q1).

`$FFC418` / `$FFC41A` are written **only** in `$3A62E` (the two
branches above) and read in many spell-routine places: in the
`0x40880` paths they are used as char indices,
`struct[$FFC41A]` = caster, `struct[$FFC418]` = target. In real
combat they therefore hold the current spell's caster and target
indices — but that is a static inference; a live-combat
breakpoint run is still owed to observe them mid-fight (#021).

The `0x40880` max-HP path lives **inside** the giant function
(state `$FF012A ≥ 22`); the loss/gain/effect block selection
inside the giant function is **not** fully traced (open for #021).
The `$3A84C` "dead apply block" is confirmed dead: it is reached
only if attacker `.+0x20 < 0` (max HP negative — never in
practice; `tst.w -$14(a6); blt.b $3a84c` at `0x3A814`–`0x3A818`).

A live-combat breakpoint run (driving a real fight headlessly)
was **not** achieved in this issue: the harness (§8) proves the
dispatch branches with crafted inputs, but no real combat was
observed. That is the remaining half of #007 question 1 — see §8.

## 5. `$FF012C` action codes — verified (static)

`$FF012C` is the current-action code, written by `$3B4AC` (which
refuses to overwrite it while it is `0x07`). Meanings from
`$3B4AC` call sites, the message routine `0x283BC`, `$3B1EE`,
and the giant-function comparisons:

| Code | Meaning |
|------|---------|
| `0x07` | locked / busy — blocks `$3B4AC` writes; set by `$3AB8C`; `$3A62E` refuses the spell branch while `$FF012C == 7` |
| `0x22` | giant-function state code (set at `0x421E2` / `0x42236`, read at `0x4223E`) |
| `0x50` | "special" (from `+0x24 == 0x50`; read at `0x429A8` / `0x42A9A`) |
| `0x7D` | max-HP loss — message "`<name>` lost `<N>` max pts" |
| `0x7F` | max-HP gain — message "`<name>` got `<N>` max pts" |
| `0x8E`–`0x92` | flat 70 damage in `$3B1EE` |
| `0x97` | flat 5 damage in `$3B1EE` |
| other | the caster's `+0x24` spell selector passed through `$3B4AC`, or a record `w1>>4` value installed by `$37D0E`'s tail (§2.2, §3.2) |

Message routine strings at `0x295C8`–`0x29604`: "Enemy", " lost ",
" got ", " max pts", " took ", " hit pts", " got ", " hit pts",
"miscast". The `0x7D`/`0x7F` codes as `$FF012C` come from `+0x24`
(action selection); the record `w1>>4` values (e.g. `0x87D`) are a
different family that only shares the low byte — do not conflate
them.

## 6. Spell status and targeting — verified (static; §6.1–6.2 + harness §8.2)

All in this section is static analysis (Capstone linear
disassembly + Ghidra decompile, cross-checked against `rop.s`);
the harness (§8) proves `$3B6C0`, `$3B748` and the `$3B51E` full
path with crafted inputs.

### 6.1 `$3B51E` per-turn spell-status routine — verified (static + harness)

`$3B51E(char_idx)` (`0x3B51E`–`0x3B6BE`):

1. Calls `$36A00` (returns 1 iff `struct[idx].+0x00 & 0xF == 1`
   — a type-1 entity; a type-4 caster returns 0, so `$3AACC` /
   `$3AB8C` are skipped), then `$3BB4E` (AI spell chooser, §6.3).
2. If `$3BB4E` returns 0: reads the caster's spell record;
   status = `(char +0x2C rol 6) & 7` = flags bits 10–12 (3-bit
   status); if record `w0` bit 11 set **and**
   `(record.w2>>4)&0x7FF == 0` → status = 2.
3. Jump table at `0x3B6A0` dispatches status
   0→`$3B6C0`, 1→`$3B988`, 2→`$3B748`, 3→`$3BA4C`; each returns a
   byte written into char `+0x2C` low byte.

### 6.2 The four status sub-routines — verified (static + harness)

- **`$3B6C0` (status 0):** 3-hop link chain — byte =
  `struct[struct[struct[char].+0x27].+0x29].+0x14].+0x26`; if 0
  or that char's `+0x2C` bit 13 set → fall back to `$3B748`;
  else return the byte (a char index).
- **`$3B988` (status 1):** loops over 6 members of
  `struct[struct[char.+0x27].+0x29].+0x14[0..5]`; returns the
  char index of the highest-level (order high nibble) alive
  member.
- **`$3B748` (status 2, the target picker):** modifier =
  `(char.+0x2C >> 8) & 3`; group =
  `struct[char.+0x27].+0x29` (or `char.+0x27` itself if record
  `w0` bit 11 set); loops over the group's 6 members, tracking
  min-distance and max-distance members (distance via `$3778E`,
  minus a random `$12B82()` draw when modifier is 0 or 1),
  lowest-HP member (HP < 140) and highest-HP member. If record
  `w0` bit 11 clear **or** lowest HP > 98: if effect class == 0
  **or** modifier == 3 → return farthest member, else return
  nearest member. Else (bit 11 set **and** someone hurt, HP ≤ 98):
  return the lowest-HP member.
- **`$3BA4C` (status 3):** loops over the group's 6 members;
  returns the nearest member whose `+0x2C` low byte ==
  caster `.+0x26` byte and alive; if none → `$3B748()`.

### 6.3 `$3BB4E` AI spell chooser — verified (static)

- If `char.+0x02 == 0x6E`: `char.+0x25 = 0x13` (19, the top
  spell) and returns 0 deterministically.
- Else if `char.+0x18` bit 8 clear: RNG checks set `+0x25` via
  `$3C362` / `$3BD3A` / `$3C520` using the 2-bit modifier and a
  table at `0x1B5CC` indexed by (rank−1); returns nonzero (from
  `$3BD3A`) to skip the `$3B51E` dispatch.
- Else (bit 8 set): record/bit checks, may set `+0x25` via
  `$3C520`.

So `+0x25` (current spell index) is set by `$3BB4E` (AI) or by
the player menu (`0x3BB72` writes `move.b #$13, $25(a3)` = 19).

### 6.4 `$36E2E` spell-effect sequencer — verified (static)

`$36E2E` (one caller, `0x22594`), driven by `$FF0EA8` (steps
0–7, then 100–104):

- **Step 0:** clear `$FF010E` bits, `$FFC380` / `$FFC378` = 0,
  call `$3B51E`, gate via `$387AE`, set `+0x2A =
  (+0x2A & 0xFFF) | 0xA000` (DoT duration 10). Effect class `d7 =
  (record.w0>>8)&7` (0→15). DoT tick: if `char.+0x2A` bit 11
  set **and** `rand(3)==0` → cur HP −= 1 + `$37B82`. Step 0 also
  decrements `$FF010E` bits 6–8 when the leader acts; if
  `char.+0x28 & 3 != 0` → step 100.
- **Steps 1–4:** movement toward target (`$25DE4`, `$36CFC`,
  `$1E18A` — `$1E18A` decomposes the movement direction into
  axis components); the spell duration nibble −= 1 each step
  (a separate step operation, not performed by `$1E18A`);
  steps 2/4 call
  `$3B748` when `(record.w1>>4 & 0x7FF)==0` and write the result
  to `char.+0x2C` low byte; returns `$FF0250 + 0x40` (which the
  caller at `0x225AA` turns into a `$37D0E` Power-deduction call
  when ≥ `0x40`).
- **Step 5:** `$39F48` / `$377FE` / `$37840` sequence, sets
  `$FF0250` = 0 or `0x10`.
- **Step 6:** `$36DE8` + `$3B4AC(0)`.
- **Step 7 (cleanup):** `+0x18` bit 9 set (bit 8 cleared if
  `$FF013A != 0`), `$25456`, decrement `+0x28` bits 2–3 and 4–5
  fields (clearing `+0x18` low nibble from bits 10–13 /
  `+0x2C` bit 15 when they hit 0), `$3CB66`, `$FF0EA8 = 0`,
  `$FF010E` bit 2 clear, `$FF0EAA = $36A94(...)`, `$26B58(4,0)`,
  `$26CCA`.
- **Steps 100–104:** `$FF0EA8++` per call; at 104 → step 7 +
  decrement `char.+0x28 & 3`.

### 6.5 `$398E0` status-effect applier — verified (static)

Called **only** from the `0x40BAA` path (3 sites):
`char.+0x18 = (char.+0x18 & 0xC3FF) | ((char.+0x18 & 0xF) << 10)`
(rank saved to bits 10–13), then low nibble = 9; `$2140A`,
`$25456`, `char.+0x28 |= 0xC` (bits 2–3 set), `$3AF92(0)`,
`$3CB66`. So `$398E0` = "apply a status effect" (rank saved,
rank set to 9). The `0x40BAA` path: `record+2 & 0xF < 7` →
`$398E0(0x1A0, target)` else `$398E0(0x2F0, target)`, then a
party loop (6 slots, 1/3 chance each via `$12B82(3)` + rol-3
bit test on `+0x2C`) calling `$398E0(0x2F0, member)`.

### 6.6 Helpers — verified (static)

- **`$36CFC`** movement helper: step-toward-target; returns 4
  or a direction code (+8 if blocked/diagonal and `$3AF10 != 0`).
- **`$36DE8`:** dx/dy → `$1E18A` → direction byte.
- **`$3B408`:** modulo/reflect helper (x % (2n), reflect if > n).
- **`$25456`:** struct bit-field writer (verified at `0x25456`–
  `0x25708`, `movem d4-d6`, epilogue `movem (a7)+, d4-d6; unlk;
  rts` at `0x25702`). Head: if `struct[idx].+0x00 & 0xF == 0` →
  `$12FA0(0x1C)` (see `$37D0E` §3.2 step 6 — this is the harness
  stall); else arg-driven writes to `+0x00` bits 12–13,
  `+0x06` / `+0x08` / `+0x0A`, and (if `+0x04 != 0xFF`) an
  `$FFB0D4` write. With `+0x04 == 0xFF` it takes the early
  epilogue.
- **`$12FA0`:** trivial wrapper — push arg, `jsr $12072`, `rts`
  (verified at `0x12FA0`). No wait loop; the spin is inside
  `$12072` (sound setup: `$138A8`, `$11820`, `$11A1A`, `$11AE4`,
  `$DE30` — exact spin loop unlocated, #021).
- **`$25DE4`:** returns -1 if `$FFB0D0[char.+0x04].word0 < 0x24`
  else 0.
- **`$2140A`:** writes `$FFB0CC` / `$FFB0CE` / `$FFB0D0` /
  `$FFB0D2` / `$FFB0D6` enemy-table fields (skipping -1 args;
  `$12FA0` if a field is already 9999 or > `0x23` in the guarded
  case).
- **`$23B84`** character creation: finds a free slot in the
  `0x38`-entry char table (first slot with `+0x00 & 0xF == 0`);
  `+0x00` low nibble = arg `$8 & 0xF`; `+0x18` bits 4–9 from arg
  `$A` (level in bits 4–7); if arg `$8 == 1` and arg `$C != -1`,
  reads a 24-byte template table at `$CF1BF + $C*0x18`. Party
  leader created at `0x1B792` / `0x1B802` via `$23B84` (result →
  `$FF02B2`).
- **`$1C0EC` is NOT the party init** — it is a 10×10 grid fill
  writing `$FFAE7A` / `$FFAF42`, map-related.
- **`$DE8E` is a 32-bit multiply** (`d0 = d0*d1`), not a table
  lookup — Ghidra decompiles of `$3B51E` / `$36E2E` / `$3B748`
  mislead on this; the asm is authoritative.

## 7. Struct-field conflicts and navigation notes

### 7.1 `+0x2A` is dual-purpose — verified (conflict recorded)

For party chars `+0x2A` = **gold** (cap 15000, #007 verified via
`$2BBD2`); for enemies / in-combat the same field is a **status
word** — bit 11 = DoT active (caller at `0x2257C` drains 10
HP/turn when set; `0x36E2E` drains 1 HP with 1/3 chance), bits
12–15 = DoT duration counter (set to 10, −1 per step). Do **not**
overwrite #007's gold finding: the field means gold outside
combat and status inside it. The `$36E2E` step-7 code also
decrements `+0x28` bits 2–3 and 4–5 as separate 2-bit counters.
**Remake note:** keep gold and combat-status in separate fields;
the original's overlap is a bug farm, not a design to copy.
Classic mode reproduces it; fixed mode splits the field.

### 7.2 `+0x14` group member list — medium confidence

In GROUP records the offset `+0x14` starts a 6-word member list
(`+0x14`..`+0x1E`); in CHARACTER records `+0x14` is the name
index. Navigation is via the `+0x27` / `+0x29` chain
(`char.+0x27` → struct → its `+0x29` byte → group index).
Inferred from decompile/asm, not directly observed in play —
medium confidence.

## 8. Tests (emulator harness)

### 8.1 Harness method

`tools/test_spells_harness.s` (2,198 bytes assembled, GNU as 2.42,
`m68k-linux-gnu-as -m68000`). Same pattern as #007
(`docs/logic.md` §7.1): harness in the `0xFF` padding at `0xFD0CC+`,
hooked at `0x35C` (attract loop top, replaces the 6-byte
`move.w $C00004,d1` with `jsr $FD0CC.l`). Runs once (flag in
scratch), calls the game's own spell routines with crafted
inputs, stores results as words in scratch RAM `$FFD004+`
(44 words, indices 0–43, canary at index 43), executes the
displaced instruction, jmps to `0x362`. Results read back via the
BlastEm debugger (`p/x $FFD0xx`, breakpoint at `done` — currently
`0xFD6AE`; **recompute it from the `.bin` with objdump after any
harness edit, the label moves when code above it grows** — a stale
`done` breakpoint made one run look hung for 150 s, §8.3).

Build: assemble, `objcopy -O binary`, copy `rop-original.gen`
to `/tmp/test008.gen`, write the harness at `0xFD0CC`, write the
hook at `0x35C`, `python3 tools/checksum.py fix-all` (header
`0xD948` after the #021 `rts` fix — `0xE136` before it — runtime
`0x7C7B5FDB` — same runtime value as #007's run,
expected: identical hook bytes and harness outside the summed
range), `verify-all` passes. The original ROM is never modified
(MD5 re-verified after every build:
`30c18fdbe2183f64702ae9f1a45d63f9`).

The harness installs the new-game rank table (`$FFA7CC`..`$FFA7F0`,
same 10 pointers as `0x1B5F4`) because cold RAM there is 0 and
the spell routines dereference it; inits the message-queue header
`(0,0,7)` defensively; saves/restores slots 0–1, the `$FFA7CC`
table, the queue header, the `$FFB0CC` record, the S4 spot
fields (incl. `slot5.+0x28/+0x29`), and the misc globals
(`$FF0EAA`, `$FF012A`, `$FF012C`, `$FFC418`, `$FFC41A`, `$FFC37C`,
`$FFC380`, `$FF009A`, `$FF010E`, `$FF0130`, `$FF02B2`, `$FF0072`).

Setup shared by the S1/S4 cases: attacker slot 0 (type 4,
`+0x04=0xFF` to dodge `$210D8` in `$23AE0`, `+0x18=0x11` rank 1,
`+0x1E=1` target idx, `+0x20=60`, `+0x22=0` caster idx,
`+0x28` atk 20, `+0x2C` mod 2), target slot 1 at (3,4) (type 4,
`+0x04=0`, `+0x28` def 10, `+0x2C` mod 1, HP 100). Melee needs
attacker `.+0x18 != 0` (else `$3A62E` takes the no-damage
branch) — verified from the decompile. **S3's `setup_spell`
resets the whole slot via `setup_combat` first** (`+0x00 = 4`)
and forces `+0x04 = 0` — S1's dispatches mutate `slot0.+0x00`
to `0xA0`, which stalls `$37D0E` via `$25456` → `$12FA0` (§3.2
step 6, §8.3). **S4b/S4c set `slot5.+0x29 = 5`** (group
self-link): rec 0 / rec 19 bit 11 is clear, so `$3B748` takes
group = `struct[5].+0x29`; cold RAM (0) sent it to struct[0]'s
words instead (§8.3).

### 8.2 Results — 44/44 PASS (2026-11-09, run `/tmp/ropre/run008.json`)

Harness completed in ~1 s of emulated time (hits `FD0CC` →
`$37D0E` jsr/return ×3 → `done` `0xFD6AE`). Flag `0xBEEF`,
canaries intact (`$FFD002` `0xA5A5`, `$FFD0FE` `0x5A5A`,
result canary `0xA5A5`). Values are unsigned words as read
with `p/x` (`$FFD004` = index 0).

| Test | Got | Expected | |
|------|-----|----------|---|
| S1A `$3A62E` melee (`+0x24=0`): `$FF012C, $FF012A, $FFC418, $FFC41A`, tgt HP, `$FFC380` | `[0, 0, -1, -1, 72, 28]` | `[0, 0, -1, -1, 72, 28]` | PASS |
| S1B `$3A62E` special (`+0x24=0x50`) | `[0x50, 1, 1, 0, 100, 0]` | same | PASS |
| S1C `$3A62E` spell code `0x8E` | `[0x8E, 1, 1, 0, 100, 0]` | same | PASS |
| S1D `$3A62E` spell code `0x7D` | `[0x7D, 1, 1, 0, 100, 0]` | same | PASS |
| S2 `$3C2C0` cost, rec19 mod0 | `3000` | `3000` (1000×1×3) | PASS |
| S2 `$3C2C0` cost, rec19 mod1 | `6000` | `6000` (1000×2×3) | PASS |
| S2 `$3C2C0` cost, rec0 mod3 | `0` | `0` (0×4×3) | PASS |
| S3a `$37D0E` deduct rec19 mod0, Power 5000/9000, HP 100: `+0x1E, +0x1C, $FFC37C, $FF012C` | `[2000, 100, -1, 0x91]` | same | PASS |
| S3b `$37D0E` deduct rec19 mod1, Power 9000 | `[3000, 100, -1, 0x91]` | same | PASS |
| S3c `$37D0E` out-of-power rec19 mod1, Power 5000, HP 100 | `[0, 95, -1, 0x91]` | same (Power 0, HP −5) | PASS |
| S4a `$3B6C0(0)` link chain | `5` | `5` | PASS |
| S4b `$3B748(0)` target pick, mod 3 | `2` | `2` (farthest member, dist 10) | PASS |
| S4c `$3B51E(0)` full path: `slot0.+0x2C, $FF012C` | `[0x0B02, 0]` | same | PASS |
| Canary | `0xA5A5` | `0xA5A5` (`$FFD0FE` intact) | PASS |

What this proves live (beyond the static traces):

- **S1 — #007 Q1 at the dispatch level:** melee (`+0x24=0`)
  deals 28 damage (target HP 100→72, `$FFC380`=28) via `$3B1EE`;
  spell selectors (`0x50`/`0x8E`/`0x7D`) set `$FF012C` +
  `$FF012A=1` + `$FFC418=1` (target idx) + `$FFC41A=0` (caster
  idx) and deal no damage (HP stays 100) — the giant spell
  path is entered, not the melee path. `$FFC418`/`$FFC41A`
  confirmed as target/caster indices.
- **S2 — cost formula exact:** `1000×(mod+1)×3` for mod 0/1,
  `0` for a zero-cost record.
- **S3 — deduction, clamp, out-of-power drain all live:**
  Power 5000−3000=2000 (mod 0), 9000−6000=3000 (mod 1),
  and 5000−6000 clamps to 0 with HP 100→95 (the −5 drain).
  `$FFC37C` is `-1` in all three: the `$37D0E` tail
  unconditionally overwrites the `0x7777` sentinel (§3.2).
  `$FF012C = 0x91` in all three (`rec19 w1 0x0918 >> 4`).
- **S4b/S4c — `$3B748` farthest-pick live:** with group members
  at (3,4)/(6,8)/(0,5) and modifier 3, returns member 2
  (dist 10) — the effect-class/modifier MAX branch (§6.2).
  The first run returned 1 here (nearest) because the group
  link was unset (§8.3); with `slot5.+0x29 = 5` it returns 2.

### 8.3 How the run was unblocked — the `$37D0E` divert (2026-11-09)

The first harness builds verified (checksums pass) but no
debugger run produced results. The bisect, in order:

1. **Vsync dialog:** on startup BlastEm shows a modal SDL dialog
   ("Failed to set vsync to off: That operation is not supported")
   with an OK button; the game does not execute until it is
   dismissed. Dismiss with `xdotool mousemove 512 312 click 1`
   (+ `xdotool key Return`) on the 1024×768 Xvfb screen, repeated
   for the first ~60 s. `-g` (disable OpenGL) does NOT avoid it.
   The earlier "byte-identical frames 90 s apart" was this dialog
   undismissed (game never executed), not a stuck game: with
   robust clicking the original ROM advances (title at ~30 s,
   story page at ~180 s).
2. **First bisect** (breakpoints at harness entry / S1 / S2 /
   S3 / S4 / `done`): S1 and S2 complete every cycle; S4/`done`
   never reached; the harness re-enters every attract iteration.
3. **Fine bisect** (breakpoints at every S3 call/return):
   `FD756` (`jsr $37D0E`) hits, `FD75C` (`$37D0E` returned)
   never does — the divert is **inside `$37D0E`**. (The fine
   driver's "~1 s cycle" of re-entries was an artifact: its
   buffer kept stale stop-lines and re-fired them, and its `p/x`
   parser matched hex out of `Continuing` echoes — the `[12,
   None × 26]` S1+S2 read was garbage, a `C` from "Continuing".
   The machine was stuck at `FD756` the whole time.)
4. **Deep bisect** (breakpoints at every `$37D0E` tail call and
   return): `$3C2C0` returns (`37D8E` hits); the first `$25456`
   call (`37E20`) never returns.
5. **State probe** (breakpoints on return addresses only, reads
   at `jsr $37D0E`): `slot0.+0x00 = 0xA0`, `+0x04 = 0xFF`,
   `+0x1E = 5000`, `+0x22 = 9000`, `$FF0EAA = 0`. Root cause:
   `$25456` calls `$12FA0(0x1C)` → `$12072` whenever
   `struct[idx].+0x00 & 0xF == 0`, and `$12072` (sound setup)
   never returns in the cold attract context. S1's `$3A62E`
   dispatches leave `slot0.+0x00 = 0xA0` (low nibble 0);
   `setup_spell` did not reset it. **Fix:** `setup_spell`
   resets the whole slot via `setup_combat` (`+0x00 = 4`) and
   forces `+0x04 = 0` (§3.2 step 6).
6. **First green run: 40/44.** Two expectation errors and one
   setup error, all in the harness, none in the game:
   - `[29]`/`[33]` (`$FFC37C`): expected `0x7777`, got `-1` —
     the `$37D0E` tail unconditionally sets `$FFC37C = -1`
     (§3.2). Expectation corrected to `-1`.
   - `[40]`/`[41]` (S4b/S4c): expected member 2 (farthest),
     got 1 (nearest). Rank-1 rec 0 `w0 = 0x138D` has bit 11
     clear, so `$3B748` takes group =
     `struct[5].+0x29` — which the harness never set (cold RAM
     0) — and iterated struct[0]'s `+0x14..+0x1E` words as a
     member list. **Fix:** set `slot5.+0x29 = 5` (group
     self-link) in S4b/S4c, save/restore it.
7. **Stale-breakpoint trap:** after the fixes the harness grew
   2170 → 2198 bytes, moving `done` `0xFD692` → `0xFD6AE` and
   the `$37D0E` return `0xFD75C` → `0xFD784`. The run with the
   old breakpoints recorded hundreds of `FD0CC` hits (the
   harness had completed; the attract loop kept taking the
   skip path) and looked hung for 150 s. **Recompute every
   harness breakpoint from the `.bin` with objdump after any
   harness edit.**

After `done` the game continues in the attract loop normally
(skip-path re-entries prove it); the #007 post-harness PC=0
fault does not occur here.

**Debugger notes (BlastEm `-d`, pty):** `p/x $ADDR` replies
`$ADDR: <lowercase hex, no $ prefix>` (e.g. `$FFD000: beef`).
Send exactly one `c` per stop and drain until `Continuing`;
a second `c` queues in the pty and corrupts the next read.
Consume each stop report from the buffer — re-scanning an
accumulated buffer re-fires old stops. `p/x a7` (register read)
prints nothing usable; use `vr` or memory reads instead.

## 9. Open questions for #020 / #021

Carried forward from #007 §6 where they touch spells, plus new
ones from this issue:

1. **Live combat (the remaining half of #007 Q1):** which damage
   path runs in a real fight, what `$FFC418` / `$FFC41A` contain
   mid-fight, and whether the giant function's loss/gain/effect
   block selection matches the static trace. Needs a live-combat
   breakpoint run — driving a real fight headlessly is the hard
   part (#021). The same run must settle the **field puzzle**
   (§4 step 5): who writes target/caster indices into
   `+0x1E`/`+0x22` before `$3A62E` runs, given those are the
   Power fields outside combat.
2. **Giant-function block selection:** the loss/gain/effect block
   selection inside the giant function (`0x3E2D4`, state
   `$FF012A ≥ 22`) is not fully traced — which block runs for
   which effect class / `w1` value.
3. **Discipline ↔ block mapping:** no code ties price blocks to
   disciplines or characters (§1.3). Needs a character-creation /
   shop trace (#020).
4. **"Arrow" vs "Feather":** which is the archer's ROM name (§1.1).
   Needs a new-game character-creation trace (#020).
5. **`$1E0A4(attacker.+0x0A)`** in `$3A62E`'s pre-check path:
   unmapped helper; its return feeds the `$2140A` calls.
6. **`$FF012C` values `0x8E`–`0x92` vs `0x97`:** the flat-70 /
   flat-5 damage codes in `$3B1EE` — which spells produce them in
   play (record `w1>>4` values `0x87D`/`0x87E`/`0x87F`/`0x08E`
   are nearby but not equal; the exact mapping through `$3B4AC`
   is unproven in live play).
7. **DoT drain rates:** `$36E2E` drains 1 HP with 1/3 chance per
   step; the caller at `0x2257C` drains 10 HP/turn when `+0x2A`
   bit 11 is set — whether both run in the same fight, and which
   wins, is unmeasured in play.
8. **`+0x14` group-list navigation** (§7.2) is medium confidence
   — inferred, not observed in play.
9. **`$FF0E18[2]` initialiser:** partly answered — new-game init
   at `~0x1B5DA` sets up the message-queue header via
   `$1E390($FF0E18, 8)`, i.e. queue capacity byte[2] = 8 (this
   also explains the #007 harness's first freeze: cold RAM has
   0). Still open: which routine owns that init in the live
   new-game flow.
10. **Post-harness PC=0 fault** (`docs/logic.md` §7.3) — unresolved,
    #021. The #008 harness does **not** hit it: after `done` it
    returns cleanly to the attract loop (skip-path re-entries
    observed). The #007 fault is specific to that harness's exit
    path, not a general harness property.
11. **`$12072` spin loop:** `$25456` → `$12FA0` → `$12072` never
    returns in the cold attract context (§8.3) — the exact
    polling loop inside `$12072` (`$138A8` / `$11820` / `$11A1A` /
    `$11AE4` / `$DE30` callees) is unlocated. #021: find which
    flag it waits on and whether real gameplay ever takes that
    `$25456` branch with `+0x00 & 0xF == 0`.
