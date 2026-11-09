# Distance-fix patch — Rings of Power (Mega Drive)

**Issue #022 first mod — target picked by Dayset, 2026-11-09:
Candidate A (fix the dead distance term).**

Status: **SPEC + BUILDER READY, patch bytes NOT yet generated.**
Generating the IPS needs Dayset's own ROM dump (`rop-original.gen`)
on a machine with Capstone + BlastEm — see "Blocker" below. No IPS
is shipped in this folder yet, and none should be trusted until the
locate step (§2) has been run against the real ROM and the harness
re-run (§4) passes.

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

## 6. Blocker

This VM (agent session 2026-11-09) has **no ROM, no Capstone venv,
no BlastEm, no m68k assembler** — the locate/apply/harness steps
above must run on Dayset's machine (the #001 toolchain machine),
or Dayset supplies `rop-original.gen` to a session that has them.
`tools/verify_rebuild.py` self-tests PASS, but a real byte-compare
gate (#013) is likewise still owed. Until §2–§4 run, #022 is
**picked and designed, not shipped**.

## Files

- `README.md` — this spec.
- `build_patch.py` — verify + locate (+ guarded apply scaffold).
- `changed-bytes.txt` — to be generated by the apply step.
- `rings-of-power-distance-fix.ips` — to be generated; **not**
  present yet, deliberately.
