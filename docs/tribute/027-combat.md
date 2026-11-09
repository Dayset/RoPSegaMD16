# #027 — Combat: classic vs new (design)

Status 2026-11-09: **design complete** — #007's damage routine and
#021's flaw list both exist, so the fix list (acceptance item 2)
can be written now; code waits on #023/#026.

## Old (classic) combat — implement THIS path (verified)

- Dispatch `$3A62E`: attacker `+0x24` selects — `0x50`/nonzero ⇒
  giant spell machine `0x3E2D4`; zero (with `+0x18 != 0`) ⇒ melee
  `$3B1EE`. Both paths run in the original, in different turns
  (harness-proven dispatch, spells.md §4).
- Melee formula `$3B1EE` **verbatim, dead distance term included**:
  atk/def from `+0x28` bits, rank switch on the LOW nibble
  (7/8 ⇒ (level+1)·2; 9 ⇒ level+1; else dmg/3+1), `$FF012C` flat
  codes (0x8E–92 ⇒ 70; 0x97 ⇒ 5), immunity `+0x02 == 0x4D`,
  death/revive via `$37B82` (member-0 1-HP revive rule included).
- Spell-only team combat, manual mode picks each cast, no team
  movement (player-observed, partly code-confirmed — logic.md
  Background). Cost/deduction per spells.md §3 incl. the
  out-of-power HP −5 drain.
- The in-game joke is the design authority for preserving this:
  `$DDBD8` rec 1004, "Did someone say redo the combat a fifth
  time?" — do NOT attribute any rework story to the Rubin
  interview (the word "combat" never appears in it).

## New combat — the fix list (each row = one #021 flaw)

| Fix | Flaw | Change |
|---|---|---|
| N1 | F1 dead distance term | damage uses `base/(dist+2)` — ranged attacks weaken with distance as evidently intended |
| N2 | F4 self-kill casting | casting is blocked (not HP-drained) when Power < cost; or cost capped at max Power — pick at implementation, record it |
| N3 | F5 full-party heal per XP grant | only the levelling member heals (shared with #026 decision) |
| N4 | flat-code opacity (`0x8E–92` ⇒ 70) | keep values, surface them as named spell effects in data, not magic codes |
| N5 | member-0 revive asymmetry (`$37B82`) | uniform death rule for all slots |

## The switch (acceptance items 3–4)

One runtime toggle (menu + key), current mode always visible in
the combat UI header ("Combat: Classic/New"). State is a single
`CombatMode` enum read by the damage/cost functions — no world
reload. **Named old-behaviour proof for acceptance:** with dist 5,
base 60, the D1 harness case deals **28 in Classic and 31 in New**
(logic.md §5.1 numbers) — the acceptance test is literally those
two numbers from the same inputs.
Open (does not block design): which damage path fires in *live*
original combat (F9 field puzzle) — Classic implements the
dispatch as traced; if the live trace ever contradicts it, the
spec gets a correction note, not a rewrite.
