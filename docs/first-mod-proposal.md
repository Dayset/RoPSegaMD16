# First-mod proposal (issues #010 + #022) — PROPOSAL, awaiting Dayset's pick

Written 2026-11-09 (agent session). **Nothing here is a decision.**
Both issues require the target to be "picked by Dayset"; this doc
does the analysis so the pick is one line. The one shipped mod so
far (music-off) was a separate user-requested fix and is explicitly
NOT the #022 pick (PROGRESS.md).

## Preconditions — status

| #022 acceptance item | Status |
|---|---|
| Target picked by Dayset | **OPEN — this doc proposes, Dayset picks** |
| Rebuild gate passes with no changes (#009/#013) | Blocked: needs disasm/src (#012) + ROM + assembler on owner's machine. `tools/verify_rebuild.py` gate script exists and self-tests PASS |
| Checksums fixed / BlastEm boot / scene played / hardware checklist | Cannot run in this VM (no ROM/BlastEm); checklist exists at `docs/hardware-limits.md` |
| Patch in `patches/` with before/after | Only after the pick + gate |

#010's patch-workflow half is otherwise proven by the music-off
patch: IPS in `patches/<name>/`, `changed-bytes.txt`, hooks in the
`0xFD0CC+` padding, `fix-all`, IPS round-trip verified. Any #022
mod should copy that workflow exactly.

## Candidate targets (analysed from the #021 audit, docs/logic-audit.md)

### A. Fix the dead distance term (F1) — RECOMMENDED first pick
- **What:** in `$3B1EE` (damage, `docs/logic.md` §5.1), the distance
  term divides 1 by (dist+2) — always 0. Fix = compute
  `base/(dist+2)` as the code evidently intended.
- **Size:** one routine, one division operand order; harness D1
  gives the acceptance numbers (dist 5 case: 28 → 31 damage).
- **Risk:** low blast radius (one routine, two call sites
  `0x3A842`/`0x3B094`); balance shifts at range — that IS the fix.
- **Verify:** rebuild the #007 harness case D1–D7 with the patch;
  expect only distance-sensitive cases to change.

### B. Make Quiet two-way (extend music-off)
- **What:** the shipped patch is a one-way switch (reset to restore
  music) because at `$173EC` a menu pick is indistinguishable from
  a location request. A two-way version needs the menu path traced
  (the un-traced menu→`$173EC` path in the patch README).
- **Size:** medium — one tracing task + hook redesign.
- **Risk:** medium (touches the sound dispatch everyone uses).

### C. Fix the record-0 dropped "An" (F8)
- **What:** `$DDBD8` record 0 loses its first word ("An") — the
  blob literally starts `Anunknownbuilding…` (`disasm/map.md`).
- **Size:** small IF the cause is the `$136FC` skip-array[0]
  semantics PROGRESS.md describes for #004; needs the live check
  #004 specified before touching bytes.
- **Risk:** low, text-only; but cause is "likely", not proven.

### D. Difficulty/balance: cap the out-of-power HP drain (F4) or the full-heal on XP grant (F5)
- **What:** F4 — casting at 0 Power drains 5 HP/cast (`$37D0E`);
  F5 — every XP grant full-heals the party (`0x2C63C` loop).
- **Size:** small (one clamp / one loop). **Risk:** these may be
  intended design, not bugs — changing them is a *balance* mod,
  and F5 still lacks live confirmation. Weakest evidence of the
  four candidates.

### E. Spell/dialogue content mod
- No concrete target survives the evidence: spell costs are
  table-clean (tiers in spells.md §1.2), and dialogue edits are
  dictionary-system edits (#004 machinery exists:
  same-length replacement proven, `Continue`→`Resumed ` at
  `0x15BE1`). Viable only if Dayset names specific text.

## Recommendation (agent's, not Dayset's)

**Pick A.** It is the only candidate that is (1) proven a bug from
code + harness, (2) one routine wide, (3) verifiable against
existing harness numbers, and (4) the flagship finding of the
#021 audit — it also becomes the "new combat" reference fix for
the tribute (#027 F1 row). Patch plan once picked: minimal binary
patch in `$3B1EE`'s distance block (or labelled-asm once #012
lands), trampoline space in `0xFD0CC+` padding if the fix outgrows
the inline bytes, `fix-all`, #007 harness re-run (D-cases), BlastEm
scene test, `patches/distance-fix/` with before/after — copying
the music-off layout file-for-file.
