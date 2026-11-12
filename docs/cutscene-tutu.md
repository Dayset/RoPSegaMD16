# The Tutu cutscene (Tutu's tower)

The scripted scene in which Buc walks into the tower of the Great Enchanter
Tutu, is frozen and imprisoned by him, and is then rescued — in the loose
sense — by Fiver, who is doing work for Tutu. This is event-script case 4
(`menu_select_screen` `$02D3DC`). It is documented here as part of the RE
spec for the tribute remake (M7): every record, actor, line of dialog, and
the tile-change events it fires.

> **A correction that shapes this whole document.** The dialog lines a
> cutscene shows are **not** the raw text records numbered by the script's
> `w4`. Op-6 calls `text_event_resolve(3, 11, w4)` (`$02D964` → `$02D9CA`),
> and with arg1 = 3 the resolver takes the `L032D9E` path
> (`$032D9E`–`$032DA6`): the displayed text record is **w4 + 0x60 (96)**,
> via `text_record_dispatch` (`$032EB0`–`$032EC4`, tables `$DDBD8` /
> `$E0A18`). The same +96 shift applies to TALK-dialog events (event N
> displays text N+96) and to op-15's `text_event_resolve(3, 11, 541)`,
> which shows text 637, not 541. Every line quoted below is therefore given
> by its **displayed** text-record number, with the raw `w4` / event id in
> parentheses. An earlier reading of this scene quoted the raw records
> (407/408) and attributed them to the King of Doggania; that attribution
> is withdrawn — the King's lines belong to another scene (see §10).

## At a glance

- **Script:** ROM `$1A3B8`–`$1A4B8`, 33 8-byte records, opcode = `abs(byte0)`,
  negative `byte0` chains to the next record, non-negative `byte0` pauses.
  Pointer `$FFC384`, engine `sys_event_run` (`$02D56A`, dispatch `$02DBB8`,
  relative jump table, base `$02DBE8`).
- **Location:** Tutu's tower — the exact `$D1D00` record is unpinned (see
  §8); the scene's event calls are gated on records 389, 390 and 391.
- **Entry:** TALK to Tutu, pick the menu option that yields event 406 in
  `npc_attitude_positive` (`$0298D2`) → case 4 in `menu_select_screen`
  (`$02D3DC`).
- **The scene:** Tutu freezes Buc and locks him in his cell (text 503);
  Fiver, who works for Tutu, offers to help (text 504). No spell record is
  cast and no combat happens — the "FREEZE!" is dialog only.
- **Effects:** event-bit writes 79, 80, 81 in the `$FFC326` bitmap
  (with tile changes only where the scene's location matches the event's
  gate), the op-15 resolution (see §5), and 500 XP per party member.
- **Exit:** op-0 grants 500 XP to each party member and clears the dialog
  lock (`$FF0110`).

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 4 is `$1A3B8` (dispatch table `$02D480`, base `$02D4A4`).
The in-game caller is `$02A188`, inside `npc_attitude_positive`
(`$0298D2`): it pushes a local `-$6(a6) & 0xFFF` as the case. The case is
reached from TALK-dialog event 406:

- Event 406 in the `$D3102` table (12-byte records): `+2 = 2437`,
  `+8 = 0x4004`, `+10 = 0xF000`. The second dispatch (table `$02A1EE`,
  on `(rec+8 rol 4) & 0xF` = 4) takes action 4 → `$02A17C` →
  `menu_select_screen(rec+8 & 0xFFF)` = case 4 (`$02A188`).
- Event 406's own dialog text is text 502 (406 + 96): *"Stop Invader! I
  didn't invite you into my tower. FREEZE!"* — Tutu's greeting, spoken
  when the player picks the option that leads into the scene.
- Which menu-option text yields event 406 is open: the menu-choice →
  `$02A6` event-id mapping (which option text the player picks) is not yet
  traced.

After loading the pointer, `menu_select_screen` clears `$FF00AC` and
`$FFA7FA`, sets `$FFB08A=$FF`, `$FF009C=$FFFF`, `$FF0110=$FFFF` (dialog
lock), calls `$138A8`, then `$1E5A0` or `$26DD2`, then `$26E44` if
`$FF009C!=0`. From then on the script runs on its own, about one
`sys_event_run` call per 4 ticks, gated by `grid+$A` (`$FFB0B6`).

## 2. Script table

Verbatim ROM bytes, `$1A3B8`–`$1A4B8`. `w4` is the record's word at +4,
`w6` the word at +6, `b1`/`b2`/`b3` the bytes at +1/+2/+3. Opcode is
`abs(byte0)`; a negative `byte0` (`F3`, `FC`, …) means "run the next
record immediately", a non-negative `byte0` pauses until the next engine
tick. Handler addresses are from the verified dispatch table `$02DBB8`
(relative offsets, base `$02DBE8`).

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A3B8` | `FF 06 01 00 00 00 00 00` | -1 | Leader teleport to (6,1). Handler `$02D802`. |
| `$1A3C0` | `FD 05 03 00 01 85 00 00` | -3 | Place id 389 (Tutu) at (5,3). Handler `$02D852` (`sys_event_op3_place`). |
| `$1A3C8` | `06 00 00 00 01 97 01 85` | +6 | Text w4=407 → **text 503** (Tutu). Speaker `raise_by_id(389)`. Handler `$02D964` (`sys_event_op6_text`). |
| `$1A3D0` | `FB 00 00 03 01 85 00 00` | -5 | Move id 389, step b3=3. Handler `$02D7D6` (`sys_event_op5_move` → `combat_move_unit` `$024984`). |
| `$1A3D8` | `05 00 00 02 00 00 00 00` | +5 | Move id 0 (leader), step b3=2. |
| `$1A3E0` | `FB 00 00 00 01 85 00 00` | -5 | Move id 389, step b3=0. |
| `$1A3E8` | `05 00 00 02 00 00 00 00` | +5 | Move id 0, step b3=2. |
| `$1A3F0` | `FB 00 00 00 01 85 00 00` | -5 | Move id 389, step b3=0. |
| `$1A3F8` | `05 00 00 03 00 00 00 00` | +5 | Move id 0, step b3=3. |
| `$1A400` | `FB 00 00 00 01 85 00 00` | -5 | Move id 389, step b3=0. |
| `$1A408` | `05 00 00 02 00 00 00 00` | +5 | Move id 0, step b3=2. |
| `$1A410` | `0D 00 00 01 01 85 00 04` | +13 | Pose id 389, heading b3=1 (east), template base w6=4. Handler `$02DB2E` (`sys_event_op13_pose`). |
| `$1A418` | `F5 00 00 00 00 4F 00 00` | -11 | Event call w4=79, b3=0. Handler `$02DB06` → `npc_attitude_event_apply` (`$02B6E0`). |
| `$1A420` | `F5 00 00 01 00 50 00 00` | -11 | Event call w4=80, b3=1. |
| `$1A428` | `05 00 00 02 00 00 00 00` | +5 | Move id 0, step b3=2. |
| `$1A430` | `05 00 00 02 00 00 00 00` | +5 | Move id 0, step b3=2. |
| `$1A438` | `0B 00 00 00 00 51 00 00` | +11 | Event call w4=81, b3=0. |
| `$1A440` | `05 00 00 02 00 00 00 00` | +5 | Move id 0, step b3=2. |
| `$1A448` | `0D 00 00 00 00 00 00 04` | +13 | Pose id 0 (leader), heading b3=0, template base w6=4. |
| `$1A450` | `0F 00 00 00 00 00 00 00` | +15 | Text-event resolve (all-zero record). Handler `$02D67C`. See §5. |
| `$1A458` | `FE 06 01 02 00 DA 00 00` | -2 | Spawn template 218 (Fiver) at (6,1), b3=2. Handler `$02D892` (`sys_event_op2_spawn` → `npc_place_group` `$02D004`). |
| `$1A460` | `05 00 00 02 00 DA 00 00` | +5 | Move id 218, step b3=2. |
| `$1A468` | `05 00 00 02 00 DA 00 00` | +5 | Move id 218, step b3=2. |
| `$1A470` | `05 00 00 03 00 DA 00 00` | +5 | Move id 218, step b3=3. |
| `$1A478` | `FA 00 00 4B 01 98 00 FF` | -6 | Text w4=408 → **text 504** (Fiver). Speaker portrait b3=75 (w6=0xFF). |
| `$1A480` | `F5 00 00 01 00 51 00 00` | -11 | Event call w4=81, b3=1. |
| `$1A488` | `0D 00 00 02 00 DA 00 04` | +13 | Pose id 218, heading b3=2, template base w6=4. |
| `$1A490` | `05 00 00 01 00 DA 00 00` | +5 | Move id 218, step b3=1. |
| `$1A498` | `05 00 00 00 00 DA 00 00` | +5 | Move id 218, step b3=0. |
| `$1A4A0` | `05 00 00 00 00 DA 00 00` | +5 | Move id 218, step b3=0. |
| `$1A4A8` | `0D 00 00 03 00 DA 00 04` | +13 | Pose id 218, heading b3=3, template base w6=4. |
| `$1A4B0` | `07 00 00 00 00 DA 00 00` | +7 | Attacker check, id 218. Handler `$02DA0A` (`sys_event_op7_check` → `combat_attacker_check`). |
| `$1A4B8` | `00 00 00 00 00 00 01 F4` | +0 | Grant: 500 XP per party member, clear `$FF0110`. Handler `$02D5D4` (`sys_event_op0_grant`). |

### Opcode handlers (dispatch `$02DBB8`, base `$02DBE8`)

The dispatch table holds signed word offsets from `$02DBE8`; every
handler address below was recomputed from the table bytes
(`$02DBB8`–`$02DBD7`) and matches the task's engine map.

| op | handler | name | does |
|---|---|---|---|
| 0 | `$02D5D4` | `sys_event_op0_grant` | Grant w6 XP per party member; clear `$FF0110`. |
| 1 | `$02D802` | *(unnamed — see REPORT)* | Teleport the party LEADER to (b1,b2); reposition camera; ignores w4. |
| 2 | `$02D892` | `sys_event_op2_spawn` | Spawn template char + `npc_place_group` (`$02D004`). |
| 3 | `$02D852` | `sys_event_op3_place` | Place char id w4 at (b1,b2). |
| 5 | `$02D7D6` | `sys_event_op5_move` | Move char id w4 one step (b3 = direction) via `combat_move_unit` (`$024984`). |
| 6 | `$02D964` | `sys_event_op6_text` | Enqueue text w4 (displayed as w4+96); speaker = char[`npc_attitude_raise_by_id` (w6)].portrait, or b3 if w6 == 0xFF. |
| 7 | `$02DA0A` | `sys_event_op7_check` | Attacker check on char id w4. |
| 11 | `$02DB06` | *(unnamed — see REPORT)* | Call `npc_attitude_event_apply` (`$02B6E0`, w4, b3). |
| 13 | `$02DB2E` | `sys_event_op13_pose` | Set draw record: +2 = b3 (heading), +4 = w6 (template base). |
| 15 | `$02D67C` | *(misnamed `sys_event_op1_teleport` — see REPORT)* | Text-event resolve: Fezzik/gems check, else the location-392 / bit-174 / message branch. See §5. |

## 3. Actors

Char struct 52 B at `$FF02B4`; id → char via `npc_attitude_raise_by_id`
(`$02D50C`), which scans type-1 chars for `+0x02 == id` and returns the
attitude byte at `char[nameIdx].+0x26`. The mapping is per-scene, from the
char setup at entry — do not carry the Buc setup's mapping onto this
scene.

### Tutu — id 389

- Template 389 (`$CF1AC` + 24×389): word0 = 186, words all 0,
  `+12 = 19`, `+16 = 0x46` (70, home location record), `+18 = 90`,
  `+19 = 2`.
- The template's spawn list starts with spawn 186 (`$CECF0` + 6×186):
  name index 88 = **'Tutu'**, portrait byte 44. The dialog names him
  "the Great Enchanter Tutu" (texts 502/503), so id 389 is Tutu — the
  name comes from the spawn table, the title from the dialog.
- Placed at (5,3) by the script (`$1A3C0`); posed east (b3=1) at
  `$1A410`.

### Fiver — id 218

- Template 218 (`$CF1AC` + 24×218): word0 = 155, words all 0,
  `+12 = 32`, `+14 = 250`, `+16 = 0x32` (50, home location record),
  `+18 = 90`, `+19 = 2`.
- The template's spawn list starts with spawn 155: name index 94 =
  **'Fiver'**, portrait byte 75. Text 504's speaker portrait is b3=75
  and the line introduces itself as Fiver — the identification is
  consistent on both legs (template → spawn → name, and dialog →
  portrait).
- Spawned mid-scene at (6,1) by op-2 (`$1A458`), the same cell the
  leader teleported to at the scene's start.

### The leader — id 0

- The party leader (w4=0 in the moves/poses). Teleported to (6,1) by
  op-1 (`$1A3B8`); the camera follows the leader.

## 4. Dialog (verbatim)

Displayed text records (raw `w4` in parentheses). All three lines are
from `disasm/text/records_ddbd8.txt`.

- **Text 502** (entry, event 406 → 406+96; Tutu): *"Stop Invader! I
  didn't invite you into my tower. FREEZE!"*
- **Text 503** (op-6, w4=407; Tutu, speaker = char[`raise_by_id(389)`]):
  *"That will teach you not to trespass in the tower of the Great
  Enchanter Tutu! Now rot forever in my cell!"*
- **Text 504** (op-6, w4=408; Fiver, speaker portrait b3=75): *"Why
  hello Buc, fancy meeting you here. It's Fiver. I'm doing some work for
  Tutu, but since you helped me out when I was in need, I'll give you a
  hand."*

No other dialog is shown in this scene. In particular, the King's
lines (raw text records 403–410: the Milk of Youth, the Regent, the
Ring of Division) are **not** in this script — they belong to another
scene (see §10).

## 5. Effects

### The op-11 event calls — `npc_attitude_event_apply` (`$02B6E0`)

Op-11 (`$02DB06`) calls `npc_attitude_event_apply(w4, b3)`. The
routine first sets/clears bit w4 in the event bitmap at `$FFC326`
(`sys_bitmap_write`), then looks up the 6-byte record at
`$D601E + 6*w4` and dispatches on its kind
(`rol5(word0) & 0xF`, jump table `$02BBB4`: kind 0 → `$02B73C`,
1 → `$02B7CE`, 2 → `$02B860`, 3 → `$02B9B8`; kinds ≥ 4 return after the
bitmap write only). Kinds 0/1 are change-a-map-tile events via
`world_pos_add_x` (`$0319EC`), which writes `value & 0x1FF` into the
map cell at (gridX+dx, gridY+dy), preserving high bits — and only if
the current location (`$FF0E92 & 0x3FF`) matches the record's location
and chunk.

| call | event record | effect |
|---|---|---|
| `$1A418` w4=79, b3=0 | ev79: w0=`0x8000` kind 0, loc 389, chunk 0, b4=0, b5=0 | Bit 79 set. If at location 389: tile `0x112`+0 = **274** at offset (0,0). |
| `$1A420` w4=80, b3=1 | ev80: w0=`0x0000` kind 0, loc 390, chunk 0, b4=0, b5=0 | Bit 80 set. If at location 390: tile `0x112`+1 = **275** at offset (0,0). |
| `$1A438` w4=81, b3=0 | ev81: w0=`0x8863` kind 1, loc 391, chunk 6, b4=5, b5=4 | Bit 81 set. If at location 391: tile `0x107`+0 = **263** at offset (5,4). |
| `$1A480` w4=81, b3=1 | ev81 (same record) | Bit 81 set (again). If at location 391: tile `0x107`+1 = **264** at offset (5,4). |

The scene fires all three events in sequence, but only the one whose
location gate matches the scene's actual location changes a tile; the
others only set their bitmap bit. Which location the scene is at is
open (§8) — location 390 is the Lunatic Asylum, so the tower is most
likely 389 or 391, and at most one of the four tile writes takes
effect. What tiles 274/275 and 263/264 depict (door? cell bars?) is
open — it needs the tile/terrain lookup.

### The op-15 resolve — `$02D67C`

The all-zero op-15 at `$1A450` runs the op-15 handler verbatim
(`$02D67C`):

1. `world_find_char_template(0x156 = 342)` (`$031998`) — looks for
   Fezzik's template char. In Tutu's tower Fezzik is (presumably)
   absent, so the routine takes the else branch (`L02D740`).
2. Else branch: if (`$FF0E92 & 0x3FF`) == `0x188` (392) → release
   `party[0]` and start spell effect 9. The tower is not record 392,
   so this does not fire here.
3. Else if `sys_bitmap_test($FFC326, 0xAE = 174)` != 0 → return
   silently. Event 174 is a kind-1 tile event (w0=`0x0022`, loc
   264, offset (0,36)); what sets bit 174 is unpinned.
4. Else: clear `$FF0110`, `text_show_message(0x4A = 74, 0x25 = 37)`,
   `$FF0112 = 1`, `song_request(4)`, `msg_queue_consume(1)` ×3. The
   message's displayed line is not yet pinned (it resolves via
   `text_pick_record(0, 37)` over the `$D2EC2` table — see §10).

So in this scene op-15 most likely shows a message and plays song 4 —
unless bit 174 is already set, in which case it does nothing.

### The rest

- **Op-7** (`$1A4B0`): attacker check on Fiver (id 218) via
  `combat_attacker_check`.
- **Op-0** (`$1A4B8`): 500 XP per party member; clears `$FF0110`.

No item is granted or taken, no character is killed, and no spell is
cast in this scene. Tutu's "FREEZE!" is dialog, not a spell record.

## 6. Exit

Op-0 at `$1A4B8` (bytes `00 00 00 00 00 00 01 F4`): 500 XP to each
party member, `$FF0110` cleared. The scene ends; control returns to
normal play.

## 7. Camera

Op-1 (`$1A3B8`, handler `$02D802`) teleports the party leader to (6,1)
and repositions the camera on the leader. There is no other camera move
in the script; Fiver's spawn at (6,1) puts him on the leader's cell.

## 8. Location, chunk, room

The `$D1D00` table is 455 records × 10 B: +0 word = overworld key X,
+2 word = key Y, +4 byte = destination location number, +5 byte =
message index. The scene's location record is **not pinned**. The
candidates from the op-11 gates:

| record | key (X,Y) | +4 dest | +5 msg | note |
|---|---|---|---|---|
| 389 | (274,97) | 163 | 83 | Candidate for the tower. |
| 390 | (312,82) | 171 | 83 | **Lunatic Asylum** (per `docs/maps.md`) — not the tower. |
| 391 | (331,91) | 122 | 83 | Candidate for the tower. |
| 392 | (12,184) | 170 | 83 | Scripted-encounter room (spell effect 9); not the tower — but op-15's else branch tests for it. |

Template 389's home location (`+16`) is record 70: key (173,116),
dest 56, msg 26. Whether the scene runs at the template's home record
or at one of the op-11 gate records is open. No chunk number is known
for the tower room.

## 9. Live-proven vs static-only

**Static-only.** No live verification was attempted, and none is safe
with the save on hand: the only save state is `slot_0` (location 156,
Thalmus room setup), whose char setup resolves only small ids (0, 1, 2,
3, 5) and spawn ids 94–96, 101, 102. This scene needs ids 389 (Tutu)
and 218 (Fiver); `npc_attitude_raise_by_id` returns $FF for both in
`slot_0`, and `combat_move_unit($FF)` can corrupt RAM/crash, so the
scene's pointers must not be injected into `slot_0`. Every claim above
is from ROM bytes and `disasm/src/rop.s` unless marked open.

## 10. Open items

1. **Which `$D1D00` record is Tutu's tower** — 389 or 391 (390 is the
   Asylum). Decides which op-11 tile write takes effect. Needs the
   location-setup NPC list for the tower, or a live check from a save
   parked at the tower.
2. **What tiles 274/275 and 263/264 depict** — needs the tile/terrain
   lookup (tile 263 is also the bit-10 maze-wall tile; whether the
   tower's tile change is a door, cell bars, or something else is
   unknown).
3. **The op-15 fallback message (74, 37)** — its displayed line is not
   pinned; it resolves via `text_pick_record(0, 37)` over `$D2EC2`.
4. **What sets event-bit 174** (the op-15 silent-return gate) — no
   op-11 w4=174 exists in any cutscene script; its setter is unpinned.
5. **The menu-option text that yields event 406** — the menu-choice →
   `$02A6` mapping is untraced.
6. **Move/pose compass mapping** — op-5 b3 values (0–3) and op-13 b3
   headings are recorded verbatim; which b3 is which compass direction
   is not pinned here (b3=1 reads as east in the task's note for Tutu's
   pose).
7. **The King's scene is elsewhere.** The Milk-of-Youth / Regent /
   Ring of Division lines (raw text records 403–410) are not in this
   script. They are reached from other events (e.g. event 401, the
   Regent's mustache line, triggers case 3) — that scene is not this
   document's subject, and nothing here should be read as the King's
   story.
