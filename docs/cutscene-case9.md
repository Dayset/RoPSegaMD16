# Case 9 — the unreachable 50-XP grant

Event-script case 9 (`menu_select_screen` `$02D3DC`) is a single-record
script: one op-0 granting 50 XP. It has **no reachable entry in the
shipped ROM** — no TALK-dialog event yields it, and no other caller
passes case 9. It is documented here as part of the RE spec for the
tribute remake (M7) so the case is accounted for in the checklist and
not mistaken for a live reward.

## At a glance

- **Script:** ROM `$1A5B8`, 1 8-byte record. Pointer `$FFC384`, engine
  `sys_event_run` (`$02D56A`, dispatch `$02DBB8`, relative jump table,
  base `$02DBE8`).
- **Entry:** none found. No `$D3102` TALK-dialog event triggers case 9,
  and the only other `menu_select_screen` caller (`$0368D8`, in
  `combat_battle_start` `$0362D6`) passes a hardcoded 8, never 9.
- **The script:** op-0 alone — 50 XP per party member, dialog lock
  cleared.
- **Effects:** 50 XP per party member; `$FF0110` cleared. Nothing else.
- **Exit:** the single record is the exit.

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 9 is `$1A5B8` (dispatch table `$02D480`, base `$02D4A4`).
There are exactly two callers of `menu_select_screen` in the ROM:

1. **`$02A188`**, inside `npc_attitude_positive` (`$0298D2`) — the TALK
   path. The case comes from a dialog event's `+8` word: the second
   dispatch (table `$02A1EE`) takes action 4 for `(rec+8 rol 4) & 0xF`
   = 4, calling `menu_select_screen(rec+8 & 0xFFF)`. A scan of all
   `$D3102` events (0–2500) finds **no event with `+8 = 0x4009`**
   (and no event with `(+8 & 0xFFF) = 9` and the 0x4000 trigger bit).
   Cases 0–7 all have such events (113 → 0, 104 → 1, 365 → 2, 401 → 3,
   406 → 4, 468 → 5, 540 → 6, 570 → 7); case 9 has none. There is no
   TALK entry.
2. **`$0368D8`**, inside `combat_battle_start` (`$0362D6`) — a hardcoded
   `menu_select_screen(8)`. It passes 8, never 9 (and is itself dead
   code — see the case-8 doc).

No other caller exists, and no other path writes a case-9 pointer into
`$FFC384` that has been found. Case 9 is therefore unreachable as
shipped — unless a path outside the two `menu_select_screen` callers
reaches it (e.g. a direct `$FFC384` write, or a menu table outside
`$D3102`), which has not been found. See §10.

## 2. Script table

Verbatim ROM bytes, `$1A5B8`. Opcode is `abs(byte0)`; a non-negative
`byte0` pauses until the next engine tick — but with a single record
there is nothing to chain to.

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A5B8` | `00 00 00 00 00 00 00 32` | +0 | Grant: w4=0, w6=50 → **50 XP** per party member, clear `$FF0110`. Handler `$02D5D4` (`sys_event_op0_grant`). |

### The grant handler — `$02D5D4` (`sys_event_op0_grant`)

Op-0 grants w6 XP to each party member and clears `$FF0110` (the
dialog lock). w4 is not used for the amount. For comparison: case 4's
op-0 grants 500 XP, case 1 (Buc) grants 25 XP, cases 2/6/8 grant 0 XP,
case 3 grants 0 XP (a bare op-0, like this one but with w6=0).

## 3. Actors

None. The script spawns, places, moves, poses, kills, or speaks to
nobody. It touches only the party's XP and the dialog lock.

## 4. Dialog (verbatim)

None. The script enqueues no text.

## 5. Effects

50 XP per party member (op-0, w6=50, `$02D5D4`), `$FF0110` cleared.
No item, no event-bit write, no tile change, no spawn, no text. That
is the whole script.

## 6. Exit

The single record is the exit: after op-0 runs, `$FFC384` advances
past the script and control returns to normal play.

## 7. Camera

No op-1 — no teleport, no camera move.

## 8. Location, chunk, room

None. The script has no location of its own and references no
`$D1D00` record.

## 9. Live-proven vs static-only

**Static-only — and unreachable.** No live verification was attempted:
there is no save state that can reach this script (no TALK entry, no
other caller), and the only save on hand (`slot_0`, location 156) is
parked at a different scene entirely. The single claim above — one
record, 50 XP — is from the ROM bytes at `$1A5B8` and the verified
op-0 handler.

## 10. Open items

1. **What is case 9 for?** A 50-XP grant with no entry. Candidates:
   a vestigial reward for a removed quest step or menu option; a
   placeholder case (compare case 3, a bare 0-XP op-0, and case 8, a
   stub with a dead caller); or a reward reached by a path not yet
   found. Nothing in the shipped ROM distinguishes these.
2. **Is there a path outside `menu_select_screen`?** A direct
   `$FFC384` write, or a second dispatch table, could in principle
   reach case 9. No such path has been found; a scan for writes to
   `$FFC384` outside `menu_select_screen` would settle it.
