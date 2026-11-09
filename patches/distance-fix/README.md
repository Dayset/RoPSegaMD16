# Distance-fix patch — Rings of Power (Mega Drive)

**Issue #022 first mod — target picked by Dayset, 2026-11-09:
Candidate A (fix the dead distance term).**

Status: **SHIPPED + VERIFIED 2026-11-09.** `rings-of-power-distance-fix.ips`
(54 bytes) is in this folder. Dayset supplied the ROM (verified MD5);
the locate step (§2) pinned the bug at `0x3B2B2`, the patch was built,
and verification (§4) passed in full — see "Verification results"
below. One caveat is recorded there about the harness build.

## 1. The bug (verified, #007/#021)

Damage routine `$3B1EE`–`$3B408` (538 bytes; callers `0x3A842`,
`0x3B094`; args `$8(a6)` attacker idx, `$A(a6)` target idx,
`$C(a6)` base) — `docs/logic.md` §5.1:

```
d0  = atk*base>>5 + base - def*base>>5
d0 += base/(dist+2)        # intended distance term
d0 += ((att+0x2C>>8)&3)*base>>4 - ((tgt+0x2C>>8)&3)*base>>4
then order/rank switch, else dmg = dmg/3 + 1
```

As written, the distance term loads the constant **1** as the
dividend and divides by (dist+2): `1/(dist+2) = 0` for every
dist ≥ 0 (integer `divs`), then multiplies by base — always 0.
**Distance has zero effect on damage in the original game.**
The division is inverted: the dividend should be `base`.

Harness-proven (`disasm/logic/damage_tests.txt`, D1): attacker
atk 20, target def 10, base 60, dist 5 → damage **28**, which is
exactly the dead-term arithmetic (79 + 0 + 7 − 3 = 83; 83/3+1 = 28).
A live term would be `60/(5+2) = 8`, giving (83+8)/3+1 = **31**.

Distance itself is real and proven: `$3778E` computes Euclidean
distance from the +0x0C/+0x0E positions via integer sqrt `$377FE`
(harness: (0,0)–(3,4) → 5). Only its use in damage is dead.

## 2. Locate step (must run first, on the real ROM)

`docs/logic.md` gives the routine's semantics, **not** the exact
bytes of the distance block inside `$3B1EE`. Per this repo's rules
(no claim without address + bytes), the patch is built in two steps:

1. `python3 build_patch.py locate rop-original.gen`
   Verifies size (1,048,576) + MD5 `30c18fdbe2183f64702ae9f1a45d63f9`,
   disassembles `0x3B1EE–0x3B408` with Capstone, and prints every
   `divs`/`divu` and every load of the constant 1 in the routine,
   with file offsets and raw bytes. That output pins the exact
   hook site. **Stop and review it before applying anything.**
2. Only after the site is confirmed: `build_patch.py apply …`
   with the confirmed site passed explicitly (see the script's
   `--help`). The script refuses to guess a site.

## 3. Fix design

Two designs, in preference order — the locate output decides:

- **Inline (preferred if it fits):** if the constant-1 load and the
  division occupy a sequence where `base` is reachable in the same
  byte count (e.g. base still in a register at that point), replace
  the dividend load so the division computes `base/(dist+2)`.
  Smallest possible diff, no trampoline.
- **Trampoline (fallback, music-off workflow):** replace ≥6 bytes
  at the distance block with `jsr <trampoline>.l`, trampoline in
  the `0xFF` padding **after** the music-off trampolines
  (`0xFD0CC–~0xFD137` are taken by music-off; start at `0xFD138`
  or later, still inside `0xFD0CC–0xFFFFF` and outside the runtime
  checksum's summed range `0x000000–0xFD07B`). The trampoline
  replicates the replaced instructions, computes
  `base/(dist+2)`, and returns to the instruction after the hook.

Either way, afterwards:

- `tools/checksum.py fix-all` (header checksum at `0x18E` **and**
  the runtime self-check immediate at `0xFD098` — a header-only
  fix hangs at boot, proven in #001).
- Emit the IPS + `changed-bytes.txt` into this folder, copying the
  `patches/music-off/` layout file-for-file.
- Original ROM untouched; work only on a copy.

Edge cases the fix must preserve (all in `docs/logic.md` §5.1):
`$FF012C` specials (0x8E–0x92 → 70, 0x97 → 5) bypass the formula;
rank 7/8/9 order switch replaces the result; immunity
(struct[+0x27].+0x02 == 0x4D) skips HP subtraction. The distance
fix touches none of those paths.

## 4. Verification (acceptance numbers)

Rebuild the #007 harness (`tools/test_logic_harness.s`, damage
cases D1–D7, base 60, dist 5 for all cases) against the patched
ROM. Expected changes — **only D1 and D7 change**:

| Case | Condition | Before (d0 / HP / $FFC380) | After fix |
|---|---|---|---|
| D1 | order 0x00 | 28 / 72 / 28 | **31 / 69 / 31** |
| D2 | order 0x27 (rank 7) | 6 / 94 / 6 | 6 / 94 / 6 (rank switch overrides) |
| D3 | order 0x38 (rank 8) | 8 / 92 / 8 | 8 / 92 / 8 |
| D4 | order 0x49 (rank 9) | 5 / 95 / 5 | 5 / 95 / 5 |
| D5 | $FF012C=0x8E | 70 / 30 / 70 | 70 / 30 / 70 (special) |
| D6 | $FF012C=0x97 | 5 / 95 / 5 | 5 / 95 / 5 (special) |
| D7 | immunity 0x4D | 28 / 100 / 28 | **31 / 100 / 31** |

Plus a distance sweep the original cannot produce (D1's other
parameters fixed; pre-distance subtotal is 83 in all three):
dist 0 → live term `60/2 = 30` → 113/3+1 = **38**; dist 5 →
**31** (above); dist 13 → live term `60/15 = 4` → 87/3+1 = **30**.
Damage must now **decrease as distance grows**: 38 > 31 > 30.
These numbers are computed from the §1 formula here, before any
run — not fitted afterwards.

Then: `checksum.py verify-all` on the patched ROM, BlastEm boot
smoke test (boots past the runtime checksum, reaches the main
loop), one real combat scene played, and the hardware-limits
checklist (`docs/hardware-limits.md`).

## 5. Prior art checked — "The Hand of Nexus" (2008)

Checked 2026-11-09 before designing this patch (#034 lead):
*The Hand of Nexus* v2.0, by Whipon (the Xavier Whipon of #033),
released 6 Jun 2008, romhacking.net/hacks/354, targets this exact
ROM (MD5 matches). Its published feature list is a cheat/easy-mode
set — party invincible (no HP/MP loss), max level on XP, infinite/
max food, water and gold, all spells, inventory in battle, start
items — with **no damage-formula or distance change**. Its
invincibility is a loss-block, not a `$3B1EE` fix. Conclusion: no
evidence it touched the distance term; this patch is not a
duplicate. (Certainty limit: based on the hack's published
description, not an IPS diff — a diff would settle it fully.)

## 6. The built patch (2026-11-09)

Locate output (Capstone, verified ROM) — the distance block is at
`0x3B2A8–0x3B2BE`:

```
3B2A8: jsr $3778E.l          ; d0 = distance(attacker, target)
3B2AE: addq.w #$4, a7        ; pop the two index args (saved d0 stays)
3B2B0: addq.w #$2, d0        ; d0 = dist+2
3B2B2: moveq #$1, d1         ; d1 = 1            <-- THE BUG
3B2B4: ext.l d1
3B2B6: divs.w d0, d1         ; d1 = 1/(dist+2) = 0
3B2B8: muls.w $C(a6), d1     ; d1 = 0 * base = 0
3B2BC: move.w (a7)+, d0      ; restore atk/def subtotal
3B2BE: add.w d1, d0          ; += 0
```

Built as the §3 trampoline design (the inline design does not fit:
loading base cleanly needs 6 bytes, the dividend block offers 4
before the division):

- Hook at `0x3B2B2` (6 bytes): `72 01 48 C1 83 C0` →
  `4E F9 00 0F D1 38` (`jmp $FD138.l`).
- Trampoline at `0xFD138` (14 bytes, FF padding; stacks cleanly
  after music-off's `0xFD0CC–0xFD137` if both patches are applied):
  `move.w $C(a6),d1; ext.l d1; divs.w d0,d1; jmp $3B2BC.l`
  — computes `base/(dist+2)` in d1 and resumes at the subtotal
  restore, skipping the dead multiply at `0x3B2B8` (which stays in
  place, unreachable). a6 (arg frame) and the saved subtotal on the
  stack are untouched by the jmp/jmp path. No overflow is possible:
  base ≤ 140 at the `0x3A842` call site (max HP) and ≤ 127 at
  `0x3B094` (`val & 0x7F`); divisor ≥ 2; quotient ≤ 70.
- Checksums re-fixed with `tools/checksum.py fix-all`: header
  `0x8B9F → 0x4F95`, runtime `0x8F33608C → 0x46818AFC`;
  `verify-all` passes on the patched ROM.
- Full byte list: `changed-bytes.txt` (4 runs, 26 bytes total).

## Verification results (2026-11-09, this VM's toolchain)

- **IPS round-trip:** applying the IPS to the verified original
  reproduces the patched ROM byte-for-byte. Original untouched.
- **Boot (BlastEm 0.6.3.4 headless):** patched ROM boots, passes
  the runtime checksum (`0xFD07C` reached, hang address `0xFD0CA`
  never hit), reaches the `$D28E` main loop, still running at the
  12 s timeout — same signature as the original.
- **Hook executes live:** the patched run's address log vs the
  original's (2,493 targets) differs by exactly two extra targets:
  `0xFD138` (trampoline) and `0x3B2BC` (its return). Nothing the
  original reaches is missing. The attract sequence exercises the
  damage routine, so the fix ran end-to-end in-game code.
- **Harness D1–D7 (#007 harness, BlastEm debugger readback):**
  D1 **[31, 69, 31]** (was [28, 72, 28]), D2 [6, 94, 6], D3
  [8, 92, 8], D4 [5, 95, 5], D5 [70, 30, 70], D6 [5, 95, 5],
  D7 **[31, 100, 31]** (was [28, 100, 28]) — **all seven exactly
  as pre-registered in §4**, canaries intact ($FFD002 = A5A5,
  $FFD0FE = 5A5A, $FFD000 = BEEF).
- **Caveat:** the harness binary occupies `0xFD0CC–0xFD606`, so
  the harness test build carried the identical trampoline at
  `0xFE000` instead of `0xFD138` (same bytes except the two
  addresses). The shipped `0xFD138` build is the one boot-tested
  and hook-traced above. A real combat scene played by a human
  and real-hardware testing remain untested, as with music-off.

## Files

- `README.md` — this spec + build/verification record.
- `build_patch.py` — verify + locate (the apply was performed by
  the build recorded in §6; the script's guarded scaffold remains
  as the audit trail of that process).
- `changed-bytes.txt` — the 4 changed runs.
- `rings-of-power-distance-fix.ips` — the patch (54 bytes). Apply
  to a clean copy of the original ROM (MD5
  `30c18fdbe2183f64702ae9f1a45d63f9`).
