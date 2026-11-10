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
**Command 23 has no writer anywhere in the ROM** — resolved
2026-11-10 [static]: no literal `move.b #$17, -4(a6)` in either
disassembly file, no register write or arithmetic on the command
slot, and `$FF0240`'s only writers are the reset RAM-clear and
`$12FE8`'s three exit sites. `$12FE8` produces only 14 distinct
command values (0, 10, 20, 21, 22, 24, 25, 30, 35, 37, 40, 45, 50,
55) — 23 is the only switch case with no writer, so the command-23
dispatch entry (`$D566`, which calls `$1E5A0`) is dead code. The
handler `$1E5A0` itself is NOT dead (called live from 4 other
sites). `$D28E` switch is on the `$FF0240`
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

**Bribe (text found, code path LOCATED 2026-11-10) [static].** Text exists — `$DDBD8`
rec 140 (ptr `0x00B82`): "How dare you insult my honor by trying
to bribe me."; dictionary word 'bribe' (`0x00CFD`). The 10-gold
Bribe mechanic's code path is the merchant-submenu verb "Bribe" (ROM
`0xCD38C`, record byte 12 = `0x19` = C 25) → C-dispatch case 25 →
handler `$020466`: gates on `$01E49A($FF0E18)` returning 0, checks
party gold ≥ 10 (`cmpi.w #$a`), deducts 10 gold via
`$2BBD2(char, 0x400, −10, 1)` at `$0204A0`, and raises the attitude
via `$02A22A` → `$0298D2` → `$02CE74` (event id 8). There is no
Bribe goods code in `$2BBD2` (quotient 16 has remainders 0–4 only) —
the Bribe is a verb/C-code action, not a goods transaction. **Delta
mechanism PINNED (2026-11-10) [static]:** `$02CE74(char, delta)`
moves the live attitude (`+0x22`) by the full delta and the
persistent `$FF00C0` entry (indexed by `+0x20`) by
`(char.+0x26 × delta) / 100`, both clamped to [−100, +100]
(`$02CE74`); delta = ±(event word & `0xFFF`), positive at
`$029C66` (type 1), negative at `$029C8A` (type 3). **Event
records ENUMERATED (2026-11-10) [static]:** 11 records in the
`$0D3102` table have word0 == 8; the event word is the record's
+10 word, (type << 12) | delta. Type-1 deltas: **50** (rec 20),
**99** (rec 75), **15** (rec 603); type-3: 1 (rec 44); type-0xF:
0 (recs 18/19/189/550 — conversation-continue, no `$02CE74`
call). **Which record matches is the merchant's +0x02
(template index):** `$0331A4` scores `0x4000` for a +2 match +
`0x10000` for the event id + `RNG(0x400)`, highest wins; for
+0x02 == 1, recs 18/19 win (type 0xF); for other merchants the
winner is RNG-selected among the tied records — **so the Bribe's
delta is not a single universal number**. Live confirmation is
[open] (harness in `.scratch023/`, blocked by the VM replacement
removing the emulator toolchain). **`$02A22A` return semantics
PINNED (2026-11-10) [static]:** it returns
`char[char[arg1].+0x14].+0x26`, used by `$0298D2` as a **char
index** — in the Bribe context that byte is the merchant's char
index, not a percentage; the percentage `$02CE74` uses is a
different +0x26 byte (via the merchant's +0x27). See
`docs/logic.md` §3.5/§7.

**Doggonia 1,000-gold entry fee — NOT located in code** — OPEN
(player-observed claim from the walkthrough; no routine found that
checks gold ≥ 1000 at a Doggonia entry).

**Gems sell 428 — RESOLVED: the guide was right (2026-11-10)
[live].** #007 §3.5: the earlier "impossible, max 2.72×" verdict
missed the second slot multiplier in `$2EA92` (§3.4): the `$1B299`
doubling table. Gems (rec 188, base 200, slot 2) is the Commerce
merchant's (m20=32) doubling slot (`$1B298` word `0xFF02`), so at
Commerce `$2EA92(14, 2)` = 200 × 2 × attitude × 2; at att 40 that
is 856, and sell = `$2EA92/2` = **428** exactly. **Live
(2026-11-10, `.scratch024/`, 6/6):** `$2EA92(14, 2)` = 856 @ att 40
(sell 428), 1084 @ att 0 (sell 542), 516 @ att 100 (sell 258),
800 @ att 50 (sell 400); control (m20=0, loc 0, att 40) = 214;
buy (m20=2, att 70) = 86 (the guide's buy number). No second sell
path exists or is needed — the traced sell path (`$1FB88`) produces
both guide numbers. True max `$2EA92` for a slot-doubled good is
5.43× base (sell max 542 for Gems at Commerce).

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
`$FF00C0` itself is the persistent merchant-attitude table (36
words, indices 0–35, values [−100, +100], saved to EEPROM with a
+0x80 bias; resolved 2026-11-10 — see `docs/save.md`): `+0x20` is
the merchant's index into it, `+0x22` is the live attitude used by
the price function `$2EA92`, and CAMP (`$03019a`, +3 toward 10),
battle-end (`$035656`, −40), `$030628` (−5) and `$02CE74`
(percentage-based) are the attitude adjustments.
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
| Bribe 10-gold code path | LOCATED + delta mechanism PINNED (2026-11-10) [static] | Verb "Bribe" (ROM `0xCD38C`, C 25) → handler `$020466`: gold ≥ 10, deduct 10 via `$2BBD2`, raise attitude via `$02A22A` → `$02CE74` (§16). `$02CE74`: live +0x22 += full delta, persistent `$FF00C0` += (pct × delta)/100, both clamped [−100,+100]. 11 event-8 records in `$0D3102`; type-1 deltas 50/99/15, type-3 −1. Which record matches is the merchant's +0x02 (RNG tie-break) — not a single universal number. Live confirmation [open] (`.scratch023/` harness blocked by VM replacement removing the emulator toolchain). |
| Doggonia 1,000-gold fee | OPEN | Player-observed only; no routine found (§16) |
| Gems sell 428 | RESOLVED (2026-11-10) [live] | Guide was right; `$2EA92` slot-doubling table `$1B299` was missed. `$2EA92(14,2)` = 856 @ Commerce att 40, sell 428 (§16) |
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
