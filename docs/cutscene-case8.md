# Case 8 — the unreachable battle-start stub

Event-script case 8 (`menu_select_screen` `$02D3DC`) is a five-record
script whose only real content is an op-15 text-event resolution. It has
**no reachable entry in the shipped ROM**: no TALK-dialog event yields
it, and its only other caller — a hardcoded call in `combat_battle_start`
— sits behind two gates that cannot both pass. It is documented here as
part of the RE spec for the tribute remake (M7) so the case is not
mistaken for a live scene, and so the mechanism that *would* run it is
on the record.

## At a glance

- **Script:** ROM `$1A590`–`$1A5B0`, 5 8-byte records, opcode = `abs(byte0)`,
  negative `byte0` chains to the next record, non-negative `byte0` pauses.
  Pointer `$FFC384`, engine `sys_event_run` (`$02D56A`, dispatch `$02DBB8`,
  relative jump table, base `$02DBE8`).
- **Entry:** none reachable. No `$D3102` TALK-dialog event triggers case
  8, and the only other `menu_select_screen` caller (`$0368D8`, in
  `combat_battle_start` `$0362D6`) is behind contradictory gates (see
  §1).
- **The script:** op-15 (the Fezzik/gems resolution — the same handler
  that opens case 6), three op-12 no-ops, op-0 granting 0 XP.
- **Effects:** whatever op-15 does in context; nothing else.
- **Exit:** op-0 grants 0 XP and clears the dialog lock (`$FF0110`).

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 8 is `$1A590` (dispatch table `$02D480`, base `$02D4A4`).
There are exactly two callers of `menu_select_screen` in the ROM:

1. **`$02A188`**, inside `npc_attitude_positive` (`$0298D2`) — the TALK
   path. The case comes from a dialog event's `+8` word: the second
   dispatch (table `$02A1EE`) takes action 4 for `(rec+8 rol 4) & 0xF`
   = 4, calling `menu_select_screen(rec+8 & 0xFFF)`. A scan of all
   `$D3102` events (0–2500) finds **no event with `+8 = 0x4008`**
   (and no event with `(+8 & 0xFFF) = 8` and the 0x4000 trigger bit).
   Cases 0–7 all have such events (113 → 0, 104 → 1, 365 → 2, 401 → 3,
   406 → 4, 468 → 5, 540 → 6, 570 → 7); case 8 has none. There is no
   TALK entry.
2. **`$0368D8`**, inside `combat_battle_start` (`$0362D6`) — a hardcoded
   `menu_select_screen(8)`. It is reached only if two gates pass:
   - At `$0367DE`: `cmpi.w #$fb, -$4(a6); beq L0368A2` — the local
     `-$4(a6)` must equal 251 (0xFB). `-$4` is set at `$036618` from
     the opponent char's template `+14` byte: `template[char[$a].+0x02B6].+14`
     (read via `$CF1BA + 24*template`). Twelve templates have `+14`
     == 251: 92, 193, 213, 297, 306, 313, 314, 315, 316, 317, 318, 349
     (first spawns include 'Red Beard' (187), 'Mean Dean' (195),
     'Shmup' (154), 'Yoppa' (107), and several 'Nobody' generics;
     template 193's group (113, 121, 129, 137, 145) overlaps Fezzik's
     gang).
   - At `$0368A2`: `tst.w -$8(a6); beq L0368E0` — the local `-$8(a6)`
     must be non-zero. `-$8` is cleared at routine entry (`$0362DA`)
     and set to $FFFF only at `$036632`, when the opponent char's
     template index (`char[$a].+0x02B6`) equals `0x1A8` = **424**.
   - The two gates read the **same field** of the **same opponent
     char** (`char[$a].+0x02B6`): the block requires the opponent's
     template to be 424 *and* template 424's `+14` byte to be 251.
     Template 424 (`$CF1AC` + 24×424) has word0 = 110 (spawn 110,
     'Darius'), `+12 = 34`, **`+14 = 0`**, `+16 = 0x3C` (60), words
     (114, 117, 127, 138, 143, 34). Its `+14` byte is 0, not 251 —
     so the two gates **cannot both pass**, and the `$0368D8` call is
     dead code in the shipped ROM.

   (If the gates did pass, the block would first run
   `sys_struct52_assign(9, 15, party[0])` and
   `world_reposition_leader(leader, 4, 1)` — moving the leader to
   (4,1) — and then `menu_select_screen(8)`.)

No other caller exists. Case 8 is therefore unreachable as shipped:
not by TALK, and not by battle start. Whether it was reachable in an
earlier build (e.g. before template 424's `+14` byte changed, or before
the `-$8` gate was added) is open.

## 2. Script table

Verbatim ROM bytes, `$1A590`–`$1A5B0`. `w4` is the record's word at +4,
`w6` the word at +6. Opcode is `abs(byte0)`; a negative `byte0` means
"run the next record immediately", a non-negative `byte0` pauses until
the next engine tick. Handler addresses are from the verified dispatch
table `$02DBB8` (relative offsets, base `$02DBE8`).

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A590` | `0F 00 00 00 00 00 00 00` | +15 | Text-event resolve (all-zero record). Handler `$02D67C`. See §5. |
| `$1A598` | `0C 00 00 00 00 00 00 00` | +12 | No-op. Handler `$02DB2A` (unnamed — see REPORT). |
| `$1A5A0` | `0C 00 00 00 00 00 00 00` | +12 | No-op. |
| `$1A5A8` | `0C 00 00 00 00 00 00 00` | +12 | No-op. |
| `$1A5B0` | `00 00 00 00 00 00 00 00` | +0 | Grant: w4=0, w6=0 → **0 XP** per party member, clear `$FF0110`. Handler `$02D5D4` (`sys_event_op0_grant`). |

## 3. Actors

None. The script spawns, places, moves, poses, or kills nobody. The
only character the script can touch is whoever op-15 resolves against
(Fezzik, template 342 — see §5), and only if he is present.

## 4. Dialog (verbatim)

The script itself enqueues no dialog. The only text it can show comes
from op-15 (§5): text 637 (*"Unfortunately, both the Sun and the Moon
gems are needed to free the Ring."*) if Fezzik (template 342) is present
and the leader lacks both gems — or the op-15 fallback message (74, 37)
if he is absent. Which, if either, would show in the (unreachable)
battle-start context is open.

## 5. Effects

### The op-15 resolve — `$02D67C`

The all-zero op-15 at `$1A590` runs the op-15 handler verbatim
(`$02D67C`), exactly as in case 6's opener:

1. `world_find_char_template(0x156 = 342)` (`$031998`) — looks for
   Fezzik's template char. If found: `item_category_of(0x35B = 859,
   leader)` (`$02C8F2`) tests for the S Gem; if absent, the text path
   runs (`text_event_resolve(3, 11, 541)` → displays **text 637**,
   speaker from char[`raise_by_id(342)`], clears `$FF0110`,
   `combat_select_unit`, `menu_set_mode(0)`); if the S Gem is present,
   `item_category_of(0x35C = 860, leader)` tests for the M Gem, and
   the handler returns silently only if the leader has both.
2. If template 342 is not found, the else branch (`L02D740`) runs:
   location 392 → release `party[0]` + spell effect 9; else bit 174
   test → return; else message (74, 37) + song 4 + `$FF0112 = 1` +
   `msg_queue_consume(1)` ×3.

That is the script's entire content. The three op-12s do nothing
(`$02DB2A` returns immediately), and op-0 grants 0 XP.

### Why the script exists (hypothesis, not established fact)

The most economical reading is that case 8 is a **shared
battle-start hook for the Perfection-gems check**: when a battle starts
against one of the twelve `+14 == 251` opponents, the game was meant to
reposition the leader to (4,1) and run the op-15 resolution (the same
gem check that opens Fezzik's scene) before the fight. The `-$8`
(template == 424) gate then looks like a later restriction — or a
mistake — that killed the hook: template 424 ('Darius', home record 60,
the same record as Fezzik's home) is the only template that can pass
the `-$8` gate, and its `+14` byte is 0. Whether the hook ever fired in
an earlier build, and what fiction the `+14 == 251` opponents share
(Red Beard, Mean Dean, Shmup, Yoppa, Fezzik's gang…), is open.

## 6. Exit

Op-0 at `$1A5B0` (bytes `00 00 00 00 00 00 00 00`): 0 XP, `$FF0110`
cleared. The script ends; control returns to normal play (or, in the
hypothetical battle-start context, to the battle).

## 7. Camera

There is no op-1 in this script — no teleport, no camera move. (The
dead caller block in `combat_battle_start` would have repositioned the
leader to (4,1) via `world_reposition_leader` before calling
`menu_select_screen`, but that code never runs.)

## 8. Location, chunk, room

No fixed location: the script has no location of its own, and its
hypothetical caller (`combat_battle_start`) runs wherever the battle
starts. Op-15's else branch tests for location record 392 (key
(12,184), dest 170, the scripted-encounter room) — that test is the
only location the script references.

## 9. Live-proven vs static-only

**Static-only — and unreachable.** No live verification was attempted:
there is no save state that can reach this script (no TALK entry, and
the battle-start caller is dead code), and the only save on hand
(`slot_0`, location 156) is parked at a different scene entirely. Every
claim above is from ROM bytes and `disasm/src/rop.s` unless marked
open. A live battle-start probe against a `+14 == 251` opponent could
confirm the branch never fires, but no save can reach such a battle;
the static proof (same field, two reads, contradictory requirements)
stands on its own.

## 10. Open items

1. **Was case 8 ever reachable?** The dead-branch proof is static. If
   template 424's `+14` byte or the `-$8` gate changed during
   development, the hook may have fired in an earlier build. Nothing in
   the shipped ROM says so either way.
2. **What do the twelve `+14 == 251` templates have in common?** Their
   first spawns are a mixed bag (Red Beard, Mean Dean, Shmup, Yoppa,
   'Nobody' generics, Fezzik's gang via template 193). The fiction of
   the `+14` byte (250 for most templates, 251 for these twelve, 0 for
   342/389/424) is unpinned — `sys_struct24_read` (`$02EC64`) only
   distinguishes 254/255 from everything else.
3. **What is template 424 ('Darius') doing at record 60?** Its home
   record (60) is Fezzik's home, and its group (114, 117, 127, 138,
   143) is a 'Nobody' gang. Its role in the Perfection thread — if any
   — is open.
4. **Why three no-ops?** Padding, a vestigial body, or a slot where
   content was removed — unknown.
