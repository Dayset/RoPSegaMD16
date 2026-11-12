# The Thalmus cutscene, case 0 (location 156)

The scripted scene in which Thalmus lectures his students on the Rings of
Power, Darius — under Void's influence — fires twice at him down column 8,
and Thalmus dies, scattering the students across the globe with his dying
word. This is the game's opening plot scene: the lecture names the Rings,
the Rod of Creation, and Void's hunt for them, and the party wakes outside
a strange city with Thalmus's last request — "Seek my friend Hack". It is
documented here as part of the RE spec for the tribute remake (M7): every
record, actor, line of dialog, and the exact mechanism of the firing, the
kill, and the dispersal.

## At a glance

- **Script:** ROM `$19F90`–`$1A220`, 8-byte records, opcode = `abs(byte0)`,
  negative `byte0` chains to the next record, non-negative `byte0` pauses.
  Pointer `$FFC384`, engine `sys_event_run` (`$02D56A`).
- **Location:** 156 (`$FF0E98`), chunk 233, a 32x32 room. The party leader
  stands on the overworld at (117,113); the scene plays in the room.
- **Entry:** TALK to Thalmus, pick the menu option that yields case 0 in
  `menu_select_screen` (`$02D3DC`).
- **The "spell":** Darius does **not** cast a spell record. Twice he takes
  an animated cast pose (op-13, `w6=16`) and fires a mode-6 projectile
  south (op-4, SFX 3) down column 8, straight at Thalmus at (8,27). The
  projectiles reach Thalmus's cell and despawn there — and do no damage.
  No spell record, no Power cost, no `$FF012C` action code is ever
  involved. Thalmus dies by script (op-8), not by the shots.
- **The students:** Roakus, Imino, Yoppa, Fezzik, Darius (spawn-table
  indices 101-105). Darius is the attacker; the other four stand by and
  are released by the op-7 checks as the scene closes.
- **The dispersal:** Thalmus's dying word (text 218) scatters everyone
  across the globe; the party wakes outside a strange city (text 219),
  and the game transitions to location 15 with the leader placed at
  (164,122) — the op-9 staged coordinates.
- **Exit:** op-0 grants 65 XP to each party member and clears the dialog
  lock (`$FF0110`).

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 0 is `$19F90` (dispatch table `$02D480`, base `$02D4A4`). The
only in-game caller is `$02A188`, inside `npc_attitude_positive` (`$0298D2`):
it pushes a local `-$6(a6) & 0xFFF` as the case — the local is the out-param
of a `$32D4C` text/menu call, i.e. the player's TALK-dialog menu choice.
So the entry is: **TALK to Thalmus, pick the menu option that yields case
0**. (Which option text that is needs the `$32D4C` menu-table trace for
Thalmus; open item. Case 1, the STUN lesson, is the other option on the
same NPC — see `docs/cutscene-buc.md`.)

After loading the pointer, `menu_select_screen` clears `$FF00AC` and
`$FFA7FA`, sets `$FFB08A=$FF`, `$FF009C=$FFFF`, `$FF0110=$FFFF` (dialog
lock), calls `$138A8`, then `$1E5A0` or `$26DD2`, then `$26E44` if
`$FF009C!=0`. From then on the script runs on its own, about one
`sys_event_run` call per 4 ticks, gated by `grid+$A` (`$FFB0B6`).

## 2. Script table

Verbatim ROM bytes, `$19F90`–`$1A220`. `w4` is the record's word at +4,
`w6` the word at +6, `b1`/`b2`/`b3` the bytes at +1/+2/+3. Opcode is
`abs(byte0)`; a negative `byte0` (`F3`, `FC`, …) means "run the next record
immediately", a non-negative `byte0` pauses until the next engine tick.
Op-6 text records display as **w4 + 96** (see the opcode list below) —
the table shows both the record `w4` and the displayed text number.

| addr | bytes | op | meaning |
|---|---|---|---|
| `$19F90` | `FF 06 11 00 00 00 00 00` | -1 | Buc teleport to (6,17). Handler `$02D802`. |
| `$19F98` | `FD 09 11 00 00 01 00 00` | -3 | Place id 1 (Thalmus) at (9,17). Handler `$02D852`. |
| `$19FA0` | `F9 00 00 00 00 02 00 00` | -7 | Attacker check, id 2 (El Gripa). Releases El Gripa (char 5) and his scaffold Maldavin (char 4) — frees slot 5 for Yoppa. Handler `$02DA0A` → `combat_attacker_check`. |
| `$19FA8` | `FD 0A 18 00 00 03 00 00` | -3 | Place id 3 (Roakus) at (10,24). |
| `$19FB0` | `F3 00 00 03 00 03 00 04` | -13 | Roakus faces west (b3=3), template base 4. Handler `$02DB2E`. |
| `$19FB8` | `FD 0A 1A 00 00 05 00 00` | -3 | Place id 5 (Imino) at (10,26). |
| `$19FC0` | `0D 00 00 03 00 05 00 04` | +13 | Imino faces west, template base 4. Pauses. |
| `$19FC8`–`$1A048` | alternating `FB … 00 01` / `05 … 02 00 00` | -5 / +5 | 17 move records: Thalmus 1x west, then Buc 8x south and Thalmus 8x south, alternating. Handler `$02D7D6`. |
| `$1A050` | `0D 00 00 01 00 00 00 04` | +13 | Buc faces east (b3=1), template base 4. Pauses. |
| `$1A058` | `05 00 00 02 00 01 00 00` | +5 | Thalmus moves south (9th). |
| `$1A060` | `05 00 00 02 00 01 00 00` | +5 | Thalmus moves south (10th). |
| `$1A068` | `F3 00 00 00 00 01 00 04` | -13 | Thalmus faces north (b3=0), template base 4. |
| `$1A070` | `FA 00 00 00 00 72 00 01` | -6 | Enqueue text w4=114 → displays **210** (Thalmus). Handler `$02D964`. |
| `$1A078` | `FE 06 12 02 00 06 00 00` | -2 | Spawn id 6 (Yoppa template) at (6,18). Handler `$02D892`. |
| `$1A080`–`$1A0A0` | `05 00 00 02 00 06 00 00` ×6 | +5 | Yoppa walks south 6x: (6,18) → (6,24). |
| `$1A0B0` | `F3 00 00 01 00 06 00 04` | -13 | Yoppa faces east (b3=1), template base 4. |
| `$1A0B8` | `FE 06 12 02 00 07 00 00` | -2 | Spawn id 7 (Fezzik template) at (6,18). |
| `$1A0C0` | `FE 08 12 02 00 08 00 00` | -2 | Spawn id 8 (Darius template) at (8,18). |
| `$1A0C8`–`$1A100` | alternating `FB … 00 07` / `05 … 02 00 08` | -5 / +5 | 8 move records: Fezzik 4x south, Darius 4x south, alternating. Fezzik (6,18) → (6,22); Darius (8,18) → (8,22). |
| `$1A108` | `06 00 00 00 00 73 00 01` | +6 | Enqueue text w4=115 → displays **211** (Thalmus). Pauses. |
| `$1A110` | `06 00 00 00 00 74 00 01` | +6 | Enqueue text w4=116 → displays **212** (Thalmus). Pauses. |
| `$1A118` | `06 00 00 00 00 75 00 01` | +6 | Enqueue text w4=117 → displays **213** (Thalmus). Pauses. |
| `$1A120` | `06 00 00 00 00 76 00 01` | +6 | Enqueue text w4=118 → displays **214** (Thalmus). Pauses. |
| `$1A128` | `06 00 00 00 00 77 00 01` | +6 | Enqueue text w4=119 → displays **215** (Thalmus). Pauses. |
| `$1A130` | `06 00 00 00 00 78 00 01` | +6 | Enqueue text w4=120 → displays **216** (Thalmus). Pauses. |
| `$1A138` | `F3 00 00 02 00 08 00 10` | -13 | Darius faces south (b3=2), template base **16** (animated cast pose). |
| `$1A140` | `FC 01 FF 02 00 08 00 00` | -4 | SFX 3 + Darius fires south (mode-6, slot 16). Handler `$02D8F4`. Chains. |
| `$1A148` | `F3 00 00 00 00 01 00 18` | -13 | Thalmus faces north (b3=0), template base 24. |
| `$1A150` | `F3 00 00 01 00 00 00 14` | -13 | Buc faces east (b3=1), template base 20. |
| `$1A158` | `F3 00 00 03 00 05 00 14` | -13 | Imino faces west (b3=3), template base 20. |
| `$1A160` | `F3 00 00 01 00 06 00 14` | -13 | Yoppa faces east (b3=1), template base 20. |
| `$1A168` | `FA 00 00 00 00 79 00 01` | -6 | Enqueue text w4=121 → displays **217** (Thalmus). Chains. |
| `$1A170` | `F9 00 00 00 00 03 00 00` | -7 | Attacker check, id 3 (Roakus). Releases Roakus (char 8) and his scaffold Dunn (char 7). |
| `$1A178` | `07 00 00 00 00 07 00 00` | +7 | Attacker check, id 7 (Fezzik). Releases Fezzik (char 13) and his template (slot 6) — frees slot 6 for the second shot. Pauses. |
| `$1A180` | `F3 00 00 02 00 08 00 10` | -13 | Darius cast pose again (south, base 16). |
| `$1A188` | `FC 01 FF 02 00 08 00 00` | -4 | SFX 3 + Darius fires south again (mode-6, slot 6). Chains. |
| `$1A190` | `F3 00 00 00 00 01 00 18` | -13 | Thalmus faces north, template base 24. |
| `$1A198` | `F3 00 00 01 00 00 00 14` | -13 | Buc faces east, template base 20. |
| `$1A1A0` | `07 00 00 00 00 06 00 00` | +7 | Attacker check, id 6 (Yoppa). Releases Yoppa (char 5) and his scaffold Maldavin (char 4). Pauses. |
| `$1A1A8` | `F9 00 00 00 00 05 00 00` | -7 | Attacker check, id 5 (Imino). Releases Imino (char 10) and his scaffold Opul (char 9). |
| `$1A1B0` | `F8 00 00 00 00 01 00 00` | -8 | KILL id 1 (Thalmus): HP 140 → 0, status bit 13 set. Handler `$02DA3E`. |
| `$1A1B8` | `06 00 00 00 00 7C 00 08` | +6 | Enqueue text w4=124 → displays **220** (Darius). Pauses. |
| `$1A1C0` | `F9 00 00 00 00 08 00 00` | -7 | Attacker check, id 8 (Darius). Releases Darius (char 15) and his template (slot 14). |
| `$1A1C8` | `06 00 00 0D 00 7A 00 FF` | +6 | Enqueue text w4=122 → displays **218**, speaker = b3=13 (Fezzik). Pauses. |
| `$1A1D0` | `F7 00 00 00 00 A4 00 7A` | -9 | Stage (164,122) into `$FF0E9A`/`$FF0E9C`. Handler `$02DAB4`. |
| `$1A1D8` | `F5 00 00 00 00 00 00 00` | -11 | Event flag bit 0 clear. Handler `$02DB06` → `npc_attitude_event_apply`. |
| `$1A1E0` | `F5 00 00 00 00 01 00 00` | -11 | Event flag bit 1 clear. |
| `$1A1E8` | `F5 00 00 01 00 06 00 00` | -11 | Event flag bit 6 **set** (b3=1). |
| `$1A1F0` | `F5 00 00 00 00 02 00 00` | -11 | Event flag bit 2 clear. |
| `$1A1F8` | `F5 00 00 00 00 03 00 00` | -11 | Event flag bit 3 clear. |
| `$1A200` | `F5 00 00 00 00 04 00 00` | -11 | Event flag bit 4 clear. |
| `$1A208` | `F5 00 00 00 00 05 00 00` | -11 | Event flag bit 5 clear. |
| `$1A210` | `F6 00 00 00 00 00 00 00` | -10 | Flush message queue + SFX 12. Handler `$02DAD4`. |
| `$1A218` | `06 01 00 0D 00 7B 00 FF` | +6 | Enqueue text w4=123 → displays **219**, speaker = b3=13 (Fezzik); b1=1 also consumes one message immediately. Pauses. |
| `$1A220` | `00 00 00 00 00 00 00 41` | 0 | Grant 65 XP to each party member; clear `$FF0110`. Handler `$02D5D4`. |

`$1A228` begins the next script (`menu_select_screen` case 1, the Buc
scene).

### Opcode handlers (dispatch `$02DBB8`, base `$02DBE8`)

- op 0 → `$02D5D4`: loops the party list `$FF0E82`, calls
  `$2BBD2(member, 0x401, w6, 1)` per member, clears `$FF0110`. The
  quotient `0x401` = major 16, minor 1 → `xp_grant` (`$02C4E2`): adds
  `w6` = 65 XP to `char+0x1A`, clamped to 13000, recomputes level.
  (If `w4 != 0` it also calls `combat_battle_end`; here `w4=0`, so it
  does not.)
- op 1 → `$02D802`: LEADER teleport — resolves the party leader's
  attitude byte to a char (`npc_attitude_raise_by_id(leader)` → Buc),
  places it at (b1,b2), repositions the camera. **Ignores w4.**
  (The landed Buc doc says op 1 → `$02D67C`; that is the op-15
  handler, not op 1's — see the report.)
- op 2 → `$02D892`: `entity_spawn(1, -1, w4, -1, 0, 0, 0)` (mode-1
  template char), then `npc_place_group(slot, b1, b2, b3)`.
- op 3 → `$02D852`: `npc_attitude_raise_by_id(w4)` → char, then
  `$2570A(char, b1, b2)` (place at b1,b2; b3 ignored).
- op 4 → `$02D8F4`: `npc_attitude_raise_by_id(w4)` → char,
  `sfx_request(3)`, then `npc_spawn_at_step(char, -1, 10, b2, b3, b1,
  -1, 0, 0)` — spawns the mode-6 projectile.
- op 5 → `$02D7D6`: move, via `npc_attitude_raise_by_id` →
  `combat_move_unit`.
- op 6 → `$02D964`: enqueue text record **w4 + 96** via
  `text_event_resolve(3, 11, w4)`. Inside `text_event_resolve`
  (`$032D4C`), arg1=3 dispatches to `$032D9E`, which does
  `add.w #$60,d0` (+96) to w4 before storing the resolved record
  number (`$032D9E`–`$032DA2`). Speaker =
  `npc_attitude_raise_by_id(w6)` unless `w6==0xFF`, then speaker =
  `b3`. If `b1!=0` it also consumes one message immediately.
- op 7 → `$02DA0A`: `npc_attitude_raise_by_id(w4)` → char, then
  `combat_attacker_check(char.+0x27 byte)`. The check husks the
  target char: its map record is removed if any, and its `+0x00`
  low byte becomes `0xA0` (mode nibble cleared). If the target is a
  type-1 scaffold with `+0x27==1`, `sys_struct52_nibble_read`
  (`$025B4E`) first runs the same check on every char in the
  scaffold's `+0x14` list, then copies the `$CF1AC` table words into
  the scaffold's `+0x14` list and clears the scaffold's `+0x27`.
  Net effect in this scene: each op-7 releases a student **and** his
  scaffold/template. See §3.
- op 8 → `$02DA3E`: `npc_attitude_raise_by_id(w4)` → char; clears
  `char+0x1C` (current HP), sets a draw-record flag bit, sets status
  bit 13 (`0x2000`, dead) on `char+0x2C`, `sfx_request(91)`.
- op 9 → `$02DAB4`: writes `$FF0E9A = w4`, `$FF0E9C = w6` — the
  leader's return/entry coordinates for the next mode-0 location
  transition (`world_location_transition`, `$01DA6C`).
- op 10 → `$02DAD4`: `jsr $26A8c`, `msg_queue_consume(1)` x2,
  `sfx_request(12)`.
- op 11 → `$02DB06`: `npc_attitude_event_apply(w4, b3)` (`$02B6E0`).
  First act: `sys_bitmap_write($FFC326, w4, b3)` — clears bit `w4`
  when `b3=0`, sets it when `b3=1`. Then a dispatch on the `$D601E`
  table: all seven w4 values here (0–6) have table word `0x8000`,
  which routes to `$02B9B8`, where `b3==0` runs the same attacker
  check as op-7 on the id from `$D6020[w4]` (ids 1,3,5,6,7,8) — the
  final cleanup that releases Thalmus himself (via his scaffold
  Davin) and the remaining scaffolds/templates. The one `b3=1`
  record (w4=6) takes the spawn branch instead: its id (`$D6020[6]`
  = 4) resolves to no char, and the location-match checks fail
  (`$FF0E92 & 0x3FF` = 30 vs the record's 47), so no spawn happens.
- op 12 → `$02DB2A`: no-op.
- op 13 → `$02DB2E`: `npc_attitude_raise_by_id(w4)` → char, then
  `combat_effect_apply(char+0x04, -1, -1, b3, w6, -1, -1)` — writes the
  char's draw record (`$FFB0CC`): `+2 = b3` (heading: 0=N, 1=E, 2=S,
  3=W), `+4 = w6` (template base). **Op-13 is a facing/pose change, not
  a spell cast.**
- op 14 → `$02DB88`: `npc_attitude_raise_by_id(w4)` → char, then
  `world_step_tile(char, b3)`.
- op 15 → `$02D67C`: text-event resolve — `world_find_char_template
  (0x156)`, `item_category_of` gates, `text_event_resolve(3, 11,
  0x21D)`, `text_enqueue_message`, clears `$FF0110`. **Not** a
  teleport. (Not used in this script.)

`id → char` is resolved by `npc_attitude_raise_by_id` (`$02D50C`): it
scans for a type-1 char whose `+0x02` equals the id, then returns the
attitude byte at `char[that char's +0x14].+0x26` — which by
construction equals the linked char's index. Live-proven mapping:
`w4=0 → Buc`, `w4=1 → Thalmus`, `w4=2 → El Gripa`, `w4=3 → Roakus`,
`w4=5 → Imino`, `w4=6 → Yoppa`, `w4=7 → Fezzik`, `w4=8 → Darius`.

## 3. Actors

At load (`slot_0`), chars 0-12; slots 13-15 empty until the scene spawns
into them. `+0x02` is the char's identity word, `+0x14` the name index
(for placed chars) or the linked-char index (for type-1 scaffolds).

| char | name (idx) | +0x02 | type | start | role in the scene |
|---|---|---|---|---|---|
| 0 | leader "Man" (1) | 0 | 1 | (117,113) | Party leader; stands on the overworld, never enters the room. |
| 1 | Buc (57) | 1 | 4 | (8,7) head S | Teleports to (6,17); walks south 8 cells to (6,25); faces east at the end. |
| 2 | Davin (3) | 1 | 1 | (0,0) | Inactive scaffold; Thalmus's `+0x27` link (Thalmus `+0x27` = 2). Released by the op-11 w4=0 tail. |
| 3 | Thalmus (75) | 94 | 4 | (9,17) head W | Walks to (8,27); speaks lines 210–217; is killed by op-8 at `$1A1B0`. |
| 4 | Maldavin (5) | 2 | 1 | (0,0) | Inactive scaffold; El Gripa's `+0x27` link, then Yoppa's template slot. Released by the opening op-7 id 2. |
| 5 | El Gripa (76) | 95 | 4 | (16,13) head E | Present at load; released by the opening op-7 id 2 (frees slot 5). Replaced in slot 5 by Yoppa. |
| 6 | Beenie (77) | 96 | 4 | (15,14) head E | Present at load; not moved by the script. His slot is reused by Fezzik's template, then by the second projectile — the exact freeing record is open. |
| 7 | Dunn (8) | 3 | 1 | (0,0) | Inactive scaffold; Roakus's `+0x27` link. Released by op-7 id 3. |
| 8 | Roakus (141) | 101 | 4 | (18,5) head S | Placed (10,24); faces west. Student. Released by op-7 id 3. |
| 9 | Opul (10) | 5 | 1 | (0,0) | Inactive scaffold; Imino's `+0x27` link. Released by op-7 id 5. |
| 10 | Imino (142) | 102 | 4 | (18,7) head N | Placed (10,26); faces west. Student. Released by op-7 id 5. |
| 11 | Levin (9) | 0x300 | 0x1025 | (4,3) | Bystander; not moved. |
| 12 | Opul (10) | 0x42 | 0x1025 | (11,4) | Bystander; not moved. |
| 13 | Fezzik (144) | 104 | 4 | — | Spawned by op-2 `$1A0B8` at (6,18); walks to (6,22). Student. Speaks the dispersal narration (218, 219). Released by op-7 id 7. |
| 14 | (template 8) | 8 | 1 | (0,0) | Invisible scaffold for Darius's spawn. Released by op-7 id 8. |
| 15 | Darius (145) | 105 | 4 | — | Spawned by op-2 `$1A0C0` at (8,18); walks to (8,22). Fires both shots south at Thalmus; speaks 220 ("Die, Thalmus!"). Released by op-7 id 8. |
| 5 | Yoppa (143) | 103 | 4 | — | Spawned by op-2 `$1A078` at (6,18); walks to (6,24); faces east. Student. (Slot 5 is freed when El Gripa is released by the opening op-7 id 2.) Released by op-7 id 6. |

Final positions (live): Buc (6,25) head E; Thalmus (8,27) head N, HP 0,
status `0x2000`; Roakus (10,24); Imino (10,26); Yoppa (6,24); Fezzik
(6,22); Darius (8,22). All five students at 20/20 HP, Buc 20/20,
unchanged through the whole scene except Thalmus's scripted kill.

### The five students

Roakus, Imino, Yoppa, Fezzik, Darius — spawn-table indices 101-105,
name indices 141-145 (spawn table `$CECF0`, 6-byte records). Roakus and
Imino are already in the party list at load; Yoppa, Fezzik, and Darius
are spawned by the op-2 records. The op-2 mechanism: the handler spawns
a mode-1 **template** char (templates 6/7/8; `w0` = 103/104/105), whose
`+0x14` block holds (103/104/105, 0, 0, 0, 0, 0). `npc_place_group`
(`$02D004`) first calls `sys_struct52_scan` (`$02595A`), which reads
`+0x14` = 103/104/105 **as a spawn-table index** — the coincidence that
the template `w0` values equal the spawn-table indices for
Yoppa/Fezzik/Darius is what makes the scene work — and spawns the mode-4
student (the only mode-4 `entity_spawn` call site in the ROM is
`$025A38` inside that routine). `npc_place_group` then places the
student exactly at the op-2 record's (b1,b2) (offset (0,0) for i=0).
The template chars themselves stay at (0,0), unplaced, `+0x04=0xFF`
(no draw record): invisible scaffolding.

### The op-7 / op-11 releases, live

Each op-7 releases a student **and** his scaffold/template, in one
call: `combat_attacker_check` husks the scaffold (type → `0xA0`), and
`sys_struct52_nibble_read` first fans out over the scaffold's `+0x14`
list, husking the student, then rewrites the scaffold's `+0x14` list
from the `$CF1AC` table. Live flip sequence (dense probe, 10-frame
sampling): Fezzik (char 13) and his template (slot 6) flip to `0xA0`
in the `$1A138`–`$1A180` window (op-7s id 3 and id 7); Yoppa (char 5)
flips in the `$1A180`–`$1A1A8` window (op-7 id 6); Darius (char 15)
flips by `$1A1D0` (op-7 id 8). End-state `+0x14` values (post-scene
dump): Davin 94, Dunn 101, Opul 102, Maldavin 103, Darius's template
105 — the `$CF1AC` rewrite (scaffold id → spawn-table index:
1→94, 2→103, 3→101, 5→102, 8→105). The op-11 tails finish the job:
w4=0 releases Thalmus himself via Davin, and w4=1–5 release the
remaining scaffolds/templates. After the op-11s every room char except
Buc and the leader reads type `0xA0`.

## 4. Darius's fire — the attack on Thalmus

### What the code actually does

There is no spell-record cast anywhere in the scene. The combat spell
system never starts: `$FF012C`, `$FF0EA8`, `$FF012A`, `$FFC418`,
`$FFC41A` are 0 in every probe row, and no spell sequencer step, caster,
or target index is ever installed. Stun is spell record 1, block 1
(Sorc/Buc), name index 157 (`disasm/spells/spell_list.txt`), but the
script never references spell record 1, and no Power is deducted.

What fires is the **op-13 / op-4 pair, twice**, and this time the
shooter is **Darius**, not Thalmus:

- **op-13 (`$02DB2E`, `w6=16`)** puts Darius in an animated cast pose
  facing south: draw rec `+2 = 2` (south), `+4 = 16`. Template 18
  (= heading 2 + base 16) is an animated template, as in the Buc
  scene's cast pose (template 19 = heading 3 + base 16).
- **op-4 (`$02D8F4`)** plays **SFX 3** (`sfx_request(3)`) and calls
  `npc_spawn_at_step` (`$02B190`): it steps one cell south from Darius
  (direction `b3=2`), checks the caster's cell is free apart from the
  caster himself (`sys_struct52_find` — returns the *second* char at
  the cell, so the caster does not block his own shot), then
  `entity_spawn(6, -1, b1-1, -1, b3, X, Y)` — a **mode-6 entity at
  Darius's own cell (8,22), direction south**. Fields: `+0x14=10`,
  `+0x16=10`, `+0x18=255`, `+0x1C=255`, `+0x1E=-1`, `+0x20=0`,
  `+0x22=15` (caster = Darius), `+0x24=0`, `+0x26=1`, `+0x28=0`.

### The projectiles, live

Two projectiles, one per op-4 (`$1A140`, `$1A188`), both type `0x0096`,
caster 15 (Darius), `+0x24=0`, `+0x18=255`. The first spawns in slot
16 (the first free slot); the second spawns in **slot 6** — the
Fezzik-template slot, freed by the op-7 id 7 release just before the
second firing pair (`entity_spawn` scans from slot 0, so slot 6 is the
first free slot). Each travels **1 cell per world tick south down
column 8**:

```
(8,22) Darius -> (8,23) -> (8,24) -> (8,25) -> (8,26) -> (8,27) Thalmus
```

and despawns at **(8,27), Thalmus's cell** (type `0x0096` →
`0x00A0`, mode nibble cleared). **Thalmus's HP stays 140/140 through
both impacts** — the projectile reaches his cell and still does no
damage. The kill is purely the op-8 script record at `$1A1B0`, which
runs after the second shot has already despawned: Thalmus HP
`0x8C` → `0x00`, status `0x0000` → `0x2000` (bit 13), between the
`$1A1A8` and `$1A1C0` probe rows.

So the scene's geometry is the opposite of the Buc scene's: there the
shots are aimed at the wall and no student stands in the way; here the
shots are aimed **at** a character and the collision-level protection
is the only thing keeping him alive until the script kills him. The
mode-6 impact does not apply damage to a friendly char, even on
direct contact. The exact check is not located: the per-tick mode-6
stepper (movement/collision/damage on impact) is unlocated, so whether
the guard lives in the stepper's collision test or in the
`attack_dispatch`/`damage_calc` path it would call is open.

### Checked and ruled out: the `damage_calc` +0x02==77 guard

`damage_calc` (`$03B1EE`) does contain a damage-skipping guard
(`$03B36E`–`$03B3B6`): after computing damage, if
`char[caster+0x27].+0x02 == 77` **or** `char[target+0x27].+0x02 == 77`,
it branches to `$3B3BA` and skips the HP subtraction (`sub.w d0,$1c(a0)`
at `$03B3B6`). But it does **not** fire for Darius vs Thalmus here:
Darius `+0x27=14` → char 14 (template) `+0x02=8`; Thalmus `+0x27=2`
→ char 2 (Davin) `+0x02=1`. No char in the scene has `+0x02==77`
(name 77 is 'Beenie'; spawn-table 77's name is 102 'VOID'). The guard
is real but irrelevant here; it was **not** patched. (Same finding as
the Buc scene, with the attacker/target pair changed.)

### The poses around the firing

After the first shot, four op-13s pose the room: Thalmus faces north,
base 24 (`$1A148`); Buc faces east, base 20 (`$1A150`); Imino faces
west, base 20 (`$1A158`); Yoppa faces east, base 20 (`$1A160`). The
same two (Thalmus north 24, Buc east 20) repeat after the second shot
(`$1A190`, `$1A198`). Live: Thalmus's draw rec 1 reads `+2=0, +4=24`
after `$1A148`. These are reaction poses, not casts — no op-4 follows
them. No song change is observed at either firing (song index
`$FF012E` stays 13 throughout; SFX 3 from the op-4 handler is
static-only).

## 5. Dialog (verbatim)

All spoken by Thalmus (`w6=1` → speaker id 1 → Thalmus), except 220
(Darius, `w6=8`) and 218/219 (speaker = `b3=13`, char 13 = Fezzik).
From `disasm/text/records_ddbd8.txt`. **Op-6 displays record w4 + 96**
— the numbers below are the displayed records; the script's `w4`
values are in the §2 table.

- **210:** "Ah, Imino and Roakus are early, as usual, and Father Yoppa is here as well. But where are Darius and Fezzik? Will they keep us waiting again?"
- **211:** "Ahem -- thank you all for coming. The things I must tell you are of the utmost urgency."
- **212:** "As you may know, I have recently been researching the origins of the Six Arts. You are familiar with the stories of the Rings of Power, and of the Rod of Creation."
- **213:** "Until now these stories have been dismissed as legends, but the Six Guildmasters have uncovered evidence that the Rings of Power do indeed exist."
- **214:** "There are eleven Rings; they are the foundation of Nexus' power, and the power of the Six Arts."
- **215:** "This has frightening implications, for when the Rings are together, they form the Rod of Creation, the most powerful object known to us."
- **216:** "Void and his minions seek the Rings even as we speak. You must each form parties and find them before Void can reassemble the Rod. The locations are..."
- **217:** "DARIUS YOU ATTACK ME! I feared that Void's influence reached this far... Students DISPERSE!"
- **220:** "Die, Thalmus!" (Darius.)
- **218:** "Your master's dying word forces itself into the mind of all present, scattering them across the globe." (Speaker mechanically Fezzik; the line is narration, not Fezzik speaking.)
- **219:** "You find yourself outside a strange city. \"Seek my friend Hack...\" was Thalmus' last request. Might you find him here?" (Speaker mechanically Fezzik; narration.)

This is the game's opening: the Rings lecture (210–216), the attack
(217, spoken after the first shot lands on Thalmus), the killer's line
(220, after the scripted kill), and the dispersal narration (218–219).
Note the script order: 217 comes between the two firing pairs, 220
comes after the kill, and 218/219 come after the op-9 staging and the
op-11 flag writes — the dispersal is narrated while the exit
coordinates are already staged.

## 6. The students are protected — once (collision-level)

### No geometric protection here

Unlike the Buc scene, the shots in this scene are aimed at a
character: Darius fires south down column 8 and Thalmus stands at
(8,27), directly in the line of fire. There is no wall between them
and no empty row. The script aims at Thalmus on purpose — that is the
attack.

### The collision-level protection, live-proven without a patch

Both projectiles reach Thalmus's cell (8,27) and despawn there, and
**Thalmus stays 140/140** until the op-8 record kills him. The mode-6
impact does not apply damage to a friendly char, even on direct
contact. This is the same second layer the Buc doc proves with a
re-aimed test ROM — here it is proven by the shipped scene itself, no
patch needed. The exact check is not located (the per-tick mode-6
stepper is unlocated).

## 7. Exit

Op-0 (`$1A220`, handler `$02D5D4`): loops the party list `$FF0E82`,
calls `$2BBD2(member, 0x401, 65, 1)` per member. Quotient `0x401` =
major 16, minor 1 → `xp_grant` (`$02C4E2`): +65 XP to each party
member (clamped to 13000, level recomputed). Buc's XP reads `0x41`
= 65 live in the end-state dump. Then clears `$FF0110` (dialog
unlock) and control returns to the player. If the XP crosses a level
boundary, `xp_grant` plays song 8 (`$02C634`) as the level-up sting.

### After the scene: the dispersal transition (observed, trigger open)

With continued input after op-0, the game leaves the room: location
156 → 15 (`$FF0E98` `0x9C` → `0x0F`), the leader is placed at the
op-9 staged coordinates (164,122), and Buc is re-placed at (5,8)
(camera (5,6)). In the probes this lands ~600 frames after op-0. The
narration (record 219, "You find yourself outside a strange city")
frames it as the dispersal — but the mechanical trigger is not pinned:
it could be automatic (a queued post-scene advance) or driven by the
post-scene button presses. A control probe with input stopping just
after op-0 (probe_k6, input to elapsed 2050) stalled the scene itself
at `$1A180` before op-0 ever ran (`$FF010A=0` gate — the script needs
a dialog advance to proceed), so it does not settle the question; a
no-input-after-op-0 control is still needed. Leading hypothesis: the
message-consume path (the `$026846` caller) transitions on consuming
a message whose location field matches — that would make the exit
happen on the first post-scene dialog advance. The op-9 coordinates
(164,122) are not a location-table key (no (164,122) pair in
`$D1C00`–`$D2200`); the nearest keyed locations are (164,113),
(164,115), (164,117) (locations 49, 51, 43). What place (164,122)
is, and what location 15 is, remain open.

## 8. Camera

The camera follows via `combat_move_unit` → `world_reposition_leader`
(`$02513E`) → `leader_spawn` mode 5: each op-5 move repositions the
leader's spawn to the moved char's cell and the camera steps toward
it. The scene-end camera position was not separately logged (the
probe layout did not include camX/camY); the post-transition camera
(5,6), on Buc at (5,8), is the post-scene state, not the scene's end.
Open item.

## 9. Location, chunk, room

- Location 156 = the `$D1D00` record with `+4` high byte 156, key
  (116,113), message 29 ("The Lobotomy Club sits atop Cogito Falls.
  The sign reads: \"Come on in and lose your mind.\"" — text record
  29). The overworld anchor; the leader in `slot_0` stands at
  (117,113), one cell east.
- Chunk 233 (a 32x32 chunk, decoded 2048 B). Same room as the Buc
  scene: cell words (chunk-local) (6,17) `0x00DA` tile 218; (9,17)
  `0x00D5` tile 213; (6,25)/(8,26)/(10,24)/(10,26) `0x00B8` tile
  184; (8,7) `0x00DA` tile 218.
- Terrain via the `$5EDC4` table (bits 10-15): tiles 184/218/213 →
  terrain 9 = Road, walkable. The shots travel down column 8 over
  ordinary room floor; no wall is involved.
- Op-9 stages (164,122) as the leader's return coordinates; the
  op-11s clear `$FFC326` bits 0–5 and set bit 6 (`$FFC326`
  `0xBFF7` → `0xC0F7`, live).

## 10. Live-proven vs static-only

**Live-proven** (BlastEm harness, `slot_0` state, probes k/k2/k3/k4/k5/
k6/k7 in `.scratch-cutscenes/case0-1/`): the full walk (Buc 8x south
to (6,25), Thalmus 1x west + 10x south to (8,27)); the spawns and
walks (Yoppa to (6,24), Fezzik to (6,22), Darius to (8,22)); the text
enqueues in order (message counters 6→7→0→1→2→3→4→5→6→7); the two
op-13 cast poses (Darius south, base 16) and the two mode-6
projectiles (type `0x0096`, caster 15, slots 16 and 6, 1 cell/tick
south down column 8, despawn at Thalmus's cell (8,27)); Thalmus's HP
staying 140/140 through both impacts and going 140 → 0 with status
`0x2000` at op-8; the op-7 release flips (Fezzik + template, Yoppa,
Darius) and the op-11 bitmap result (`$FFC326` `0xBFF7` → `0xC0F7`);
the op-9 staging (`$FF0E9A`/`$FF0E9C` 117/113 → 164/122); Buc's +65 XP
live; the op-0 clear of `$FF0110`; the post-scene transition to
location 15 with the leader at (164,122) and Buc at (5,8).

**Static-only** (verified verbatim against ROM bytes / `rop.s`, not
run live): the op-6 +96 shift mechanism (`$032D9E` `add.w #$60`);
the op-1 leader-attitude indirection; the `npc_spawn_at_step` field
assignments; the `damage_calc` +0x02==77 guard and its non-firing for
Darius vs Thalmus; the entry menu-choice mechanism
(`menu_select_screen` case 0 via `npc_attitude_positive`); SFX 3 from
the op-4 handler (the SFX itself is not visible in the song state);
SFX 91 from op-8 and SFX 12 from op-10 (likewise not visible in the
song state); the op-11 w4=6 spawn-branch non-firing (location
mismatch); the exact `+0x14` rewrite source (`$CF1AC` table copy in
`sys_struct52_nibble_read`); the post-scene transition trigger.

## 11. Open items

- Which TALK-menu option text yields case 0 vs case 1 (needs the
  `$32D4C` menu-table trace for Thalmus).
- The post-scene transition trigger (automatic vs input-driven) and
  the identity of location 15 / the place at (164,122).
- When Beenie's slot 6 was freed before the id-7 template spawn
  (`$1A0B8`) — the template occupies slot 6 by `$1A130`, but no
  record in between is pinned as the freeing one (same open item as
  the Buc doc's "when Maldavin/El Gripa/Beenie were freed").
- The scene-end camera position (not logged).
- How the narration lines 218/219 render their speaker — the records
  name char 13 (Fezzik) as speaker, but the lines are third-person
  narration ("Your master's dying word…", "You find yourself…").
  Whether the dialog box shows a name, and whose, is open.
- The per-tick **mode-6 stepper** (movement/collision/damage on
  impact) is unlocated. It is the routine that decides what happens
  when a projectile reaches an occupied cell — the collision-level
  friendly-fire guard lives there or in the path it calls.
- The exact `song_play_direct(8)` caller at ignition in the Buc scene
  (inherited; case 0 showed no song change in its logs).
- Whether the mode-6 projectile's effect corresponds to Stun (spell
  record 1) mechanically — the script never references spell record 1,
  so this is a design question for the remake, not a code fact.
- Probe note: probes k/k2/k3/k4/k5/k6/k7 all run clean in the safe log
  region `$FFD800`–`$FFEC1E`. Probe k6's stall at `$1A180` is
  expected behavior (`$FF010A=0` gate — the script needs a dialog
  advance to proceed), not a crash. Probe note 2: the k3 end dump was
  taken **after** the post-scene transition, so its type-`0xA0`
  readings for the students are post-transition state, not
  end-of-scene state; the per-record flips are established by the
  k4/k7 dense logs instead.
