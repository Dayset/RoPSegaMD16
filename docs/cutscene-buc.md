# The Buc cutscene (location 156)

The scripted scene in which Buc meets Thalmus and Thalmus fires four shots
at the room's west wall, while his five students stand by. This is the scene
Dayset's save file `slot_0` is parked at, and the scene the
`sys_event_run` driver was identified from. It is documented here as part of
the RE spec for the tribute remake (M7): every record, actor, line of dialog,
and the exact mechanism that keeps the students safe.

## At a glance

- **Script:** ROM `$1A228`–`$1A390`, 8-byte records, opcode = `abs(byte0)`,
  negative `byte0` chains to the next record, non-negative `byte0` pauses.
  Pointer `$FFC384`, engine `sys_event_run` (`$02D56A`).
- **Location:** 156 (`$FF0E98`), chunk 233, a 32x32 room. The party leader
  stands on the overworld at (117,113); the scene plays in the room.
- **Entry:** TALK to Thalmus, pick the menu option that yields case 1 in
  `menu_select_screen` (`$02D3DC`).
- **The "spell":** Thalmus does **not** cast a spell record. Four times he
  takes an animated cast pose (op-13, `w6=16`) and fires a mode-6 projectile
  west (op-4, SFX 3). The projectiles travel 1 cell per world tick along row
  26 and despawn at the west wall cell (2,26). No spell record, no Power
  cost, no `$FF012C` action code is ever involved.
- **The students:** Roakus, Imino, Yoppa, Fezzik, Darius (spawn-table
  indices 101-105). They are protected **twice**: the shots are aimed down
  row 26, which no student stands on (geometric protection), and even a
  shot re-aimed onto a student does no damage (collision-level protection
  against friendly fire). See §6.
- **Exit:** op-0 grants 25 XP to each of the 6 party members and clears the
  dialog lock (`$FF0110`).

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 1 is `$1A228` (dispatch table `$02D480`, base `$02D4A4`). The
only in-game caller is `$02A188`, inside `npc_attitude_positive` (`$0298D2`):
it pushes a local `-$6(a6) & 0xFFF` as the case — the local is the out-param
of a `$32D4C` text/menu call, i.e. the player's TALK-dialog menu choice.
So the entry is: **TALK to Thalmus, pick the menu option that yields case
1**. (Which option text that is needs the `$32D4C` menu-table trace for
Thalmus; open item.)

After loading the pointer, `menu_select_screen` clears `$FF00AC` and
`$FFA7FA`, sets `$FFB08A=$FF`, `$FF009C=$FFFF`, `$FF0110=$FFFF` (dialog
lock), calls `$138A8`, then `$1E5A0` or `$26DD2`, then `$26E44` if
`$FF009C!=0`. From then on the script runs on its own, about one
`sys_event_run` call per 4 ticks, gated by `grid+$A` (`$FFB0B6`).

## 2. Script table

Verbatim ROM bytes, `$1A228`–`$1A390`. `w4` is the record's word at +4,
`w6` the word at +6, `b1`/`b2`/`b3` the bytes at +1/+2/+3. Opcode is
`abs(byte0)`; a negative `byte0` (`F3`, `FC`, …) means "run the next record
immediately", a non-negative `byte0` pauses until the next engine tick.

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A228` | `FF 06 11 00 00 00 00 00` | -1 | Buc teleport to (6,17). Handler `$02D67C`. |
| `$1A230` | `FD 09 11 00 00 01 00 00` | -3 | Place id 1 (Thalmus) at (9,17). Handler `$02D852`. |
| `$1A238` | `F9 00 00 00 00 02 00 00` | -7 | Attacker check, id 2. Handler `$02DA0A` → `combat_attacker_check(4)`. |
| `$1A240` | `FD 0A 18 00 00 03 00 00` | -3 | Place id 3 (Roakus) at (10,24). |
| `$1A248` | `F3 00 00 03 00 03 00 04` | -13 | Roakus faces west (b3=3), template base 4. Handler `$02DB2E`. |
| `$1A250` | `FD 0A 1A 00 00 05 00 00` | -3 | Place id 5 (Imino) at (10,26). |
| `$1A258` | `F3 00 00 03 00 05 00 04` | -13 | Imino faces west, template base 4. |
| `$1A260` | `FE 06 19 01 00 06 00 00` | -2 | Spawn id 6 (Yoppa template) at (6,25). Handler `$02D892`. |
| `$1A268` | `FE 04 18 01 00 07 00 00` | -2 | Spawn id 7 (Fezzik template) at (4,24). |
| `$1A270` | `02 04 19 01 00 08 00 00` | +2 | Spawn id 8 (Darius template) at (4,25). Pauses. |
| `$1A278`–`$1A2F0` | alternating `FB … 00 01` / `05 … 02 00 00` | -5 / +5 | 18 move records: Buc 8x south, Thalmus 1x west + 9x south. Handler `$02D7D6`. |
| `$1A2F8` | `0D 00 00 01 00 00 00 04` | +13 | Buc faces east (b3=1), template base 4. Pauses. |
| `$1A300` | `05 00 00 02 00 01 00 00` | +5 | Thalmus moves south (w4=1). |
| `$1A308` | `05 00 00 02 00 01 00 00` | +5 | Thalmus moves south. |
| `$1A310` | `F3 00 00 00 00 01 00 04` | -13 | Thalmus faces north (b3=0), template base 4. |
| `$1A318` | `FA 00 00 00 00 7D 00 01` | -6 | Enqueue text w4=125 → displays 221 (Thalmus). Handler `$02D964`. |
| `$1A320` | `06 00 00 00 00 7E 00 01` | +6 | Enqueue text w4=126 → displays 222 (Thalmus). Pauses. |
| `$1A328` | `06 00 00 00 00 7F 00 01` | +6 | Enqueue text w4=127 → displays 223 (Thalmus). Pauses. |
| `$1A330` | `F3 00 00 03 00 01 00 10` | -13 | Thalmus faces west (b3=3), template base **16** (animated cast pose). |
| `$1A338` | `04 01 FF 03 00 01 00 00` | +4 | SFX 3 + spawn mode-6 projectile west. Handler `$02D8F4`. Pauses. |
| `$1A340` | `F3 00 00 03 00 01 00 10` | -13 | Thalmus cast pose again. |
| `$1A348` | `04 01 FF 03 00 01 00 00` | +4 | SFX 3 + projectile west. Pauses. |
| `$1A350` | `F3 00 00 03 00 01 00 10` | -13 | Thalmus cast pose again. |
| `$1A358` | `04 01 FF 03 00 01 00 00` | +4 | SFX 3 + projectile west. Pauses. |
| `$1A360` | `F3 00 00 03 00 01 00 10` | -13 | Thalmus cast pose again. |
| `$1A368` | `FC 01 FF 03 00 01 00 00` | -4 | SFX 3 + projectile west. Chains. |
| `$1A370` | `06 00 00 00 00 80 00 01` | +6 | Enqueue text w4=128 → displays 224 (Thalmus). Pauses. |
| `$1A378` | `06 00 00 00 00 81 00 01` | +6 | Enqueue text w4=129 → displays 225 (Thalmus). Pauses. |
| `$1A380` | `F6 00 00 00 00 00 00 00` | -10 | Flush message queue + SFX 12. Handler `$02DAD4`. |
| `$1A388` | `06 00 00 24 00 82 00 FF` | +6 | Enqueue text w4=130 → displays 226, speaker = b3=36 (meaning of speaker 36 open). Pauses. |
| `$1A390` | `00 00 00 00 00 00 00 19` | 0 | Grant 25 XP to each party member; clear `$FF0110`. Handler `$02D5D4`. |

`$1A398` begins the next script (`menu_select_screen` case 2).

### Opcode handlers (dispatch `$02DBB8`, base `$02DBE8`)

- op 0 → `$02D5D4`: loops the party list `$FF0E82`, calls
  `$2BBD2(member, 0x401, w6, 1)` per member, clears `$FF0110`. The
  quotient `0x401` = major 16, minor 1 → `xp_grant` (`$02C4E2`): adds
  `w6` = 25 XP to `char+0x1A`, clamped to 13000, recomputes level.
- op 1 → `$02D802`: teleport — resolves the party leader's attitude byte to a char (`npc_attitude_raise_by_id(leader)` → Buc), places it at (b1,b2), repositions the camera. Ignores w4.
- op 2 → `$02D892`: `entity_spawn(1, -1, w4, -1, 0, 0, 0)` (mode-1
  template char), then `npc_place_group(slot, b1, b2, b3)`.
- op 3 → `$02D852`: `npc_attitude_raise_by_id(w4)` → char, then
  `$2570A(char, b1, b2)` (place at b1,b2; b3 ignored).
- op 4 → `$02D8F4`: `npc_attitude_raise_by_id(w4)` → char,
  `sfx_request(3)`, then `npc_spawn_at_step(char, -1, 10, b2, b3, b1,
  -1, 0, 0)` — spawns the mode-6 projectile.
- op 5 → `$02D7D6`: move, via `npc_attitude_raise_by_id` →
  `combat_move_unit`.
- op 6 → `$02D964`: enqueue text record `w4 + 96` via `text_event_resolve(3, 11, w4)` (`$032D4C` → `$032D9E` `add.w #$60`);
  speaker = `npc_attitude_raise_by_id(w6)` unless `w6==0xFF`, then
  speaker = `b3`. If `b1!=0` it also consumes one message immediately.
- op 7 → `$02DA0A`: `npc_attitude_raise_by_id(w4)` → char, then `combat_attacker_check(char.+0x27 byte)`. The check husks the target char (map record removed; `+0x00` low byte → `0xA0`); if the target is a type-1 scaffold with `+0x27==1`, `sys_struct52_nibble_read` (`$025B4E`) first fans out over the scaffold's `+0x14` list. (The w4=2 instance here is El Gripa.)
- op 10 → `$02DAD4`: `jsr $26A8c`, `msg_queue_consume(1)` x2,
  `sfx_request(12)`.
- op 11 → `$02DB06`: `npc_attitude_event_apply` (`$02B6E0`, w4, b3) — event-bit write + location-gated tile/grant/spawn (not used in this script).
- op 12 → `$02DB2A`: no-op.
- op 13 → `$02DB2E`: `npc_attitude_raise_by_id(w4)` → char, then
  `combat_effect_apply(char+0x04, -1, -1, b3, w6, -1, -1)` — writes the
  char's draw record (`$FFB0CC`): `+2 = b3` (heading: 0=N, 1=E, 2=S,
  3=W), `+4 = w6` (template base). **Op-13 is a facing/pose change, not
  a spell cast.**
- op 14 → `$02DB88`: `npc_attitude_raise_by_id(w4)` → char, then
  `world_step_tile(char, b3)`.
- op 15 → `$02D67C`: text-event resolve (`world_find_char_template` `$031998` + `text_event_resolve(3, 11, …)`). Not a teleport.

`id → char` is resolved by `npc_attitude_raise_by_id` (`$02D50C`): it
scans for a type-1 char whose `+0x02` equals the id, then returns the
attitude byte at `char[that char's +0x14].+0x26`. Live-proven mapping:
`w4=0 → Buc`, `w4=1 → Thalmus`, `w4=2 → El Gripa`, `w4=3 → Roakus`,
`w4=5 → Imino`.

## 3. Actors

At load (`slot_0`), chars 0-12; slots 13-15 empty until the scene spawns
into them.

| char | name (idx) | type | start | role in the scene |
|---|---|---|---|---|
| 0 | leader "Man" (1) | 1 | (117,113) | Party leader; stands on the overworld, never enters the room. Camera anchor at the end. |
| 1 | Buc (57) | 4 | (8,7) head S | Walks south 8 cells to (6,25); faces east at the end. |
| 2 | Davin (3) | 1 | (0,0) | Inactive scaffold; Thalmus's `+0x27` link. |
| 3 | Thalmus (75) | 4 | (9,17) head W | Walks to (8,26); speaks lines 221-225; fires the four shots west. |
| 4 | Maldavin (5) | 1 | (0,0) | Inactive scaffold; Yoppa's `+0x27` link. |
| 5 | El Gripa (76) | 4 | (16,13) head E | Present at load; not moved by the script. |
| 6 | Beenie (77) | 4 | (15,14) head E | Present at load; not moved by the script. |
| 7 | Dunn (8) | 1 | (0,0) | Inactive scaffold; Roakus's `+0x27` link. |
| 8 | Roakus (141) | 4 | (18,5) head S | Placed (10,24); faces west. Student. |
| 9 | Opul (10) | 1 | (0,0) | Inactive scaffold (name 10); Imino's `+0x27` link. |
| 10 | Imino (142) | 4 | (18,7) head N | Placed (10,26); faces west. Student. |
| 11 | Levin (9) | 0x1025 | (4,3) | Bystander; not moved. |
| 12 | Opul (10) | 0x1025 | (11,4) | Bystander; not moved. |
| 13 | Fezzik (144) | 4 | — | Spawned by op-2 `$1A268` at (4,24). Student. |
| 14 | (template 8) | 1 | (0,0) | Invisible scaffold for Darius's spawn. |
| 15 | Darius (145) | 4 | — | Spawned by op-2 `$1A270` at (4,25). Student. |
| 5 | Yoppa (143) | 4 | — | Spawned by op-2 `$1A260` at (6,25). Student. (Slot 5 is freed when El Gripa leaves the party list before the spawns; the exact free moment is open.) |

Final positions (live): Buc (6,25) head E; Thalmus (8,26) head W;
Roakus (10,24); Imino (10,26); Yoppa (6,25); Fezzik (4,24); Darius
(4,25). All five students at 20/20 HP, Thalmus 140/140, Buc 20/20,
unchanged through the whole scene.

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

## 4. Thalmus's fire — the "spell"

### Dayset's read (hypothesis, not established fact)

> "Thalmus fires a STUN spell, aimed at the wall in front of the
> students."

### What the code actually does

There is no spell-record cast anywhere in the scene. The combat spell
system never starts: `$FF012C`, `$FF0EA8`, `$FF012A`, `$FFC418`,
`$FFC41A` are 0 in every probe row, and no spell sequencer step, caster,
or target index is ever installed. Stun is spell record 1, block 1
(Sorc/Buc), name index 157 (`disasm/spells/spell_list.txt`), but the
script never references spell record 1, and no Power is deducted.

What fires is the **op-13 / op-4 pair, four times**:

- **op-13 (`$02DB2E`, `w6=16`)** puts Thalmus in an animated cast pose
  facing west: draw rec 1 `+2 = 3` (west), `+4 = 16`. Template 19
  (= heading 3 + base 16) is an animated template — its groups cycle
  `0x0A/0x0B/0x0A/0x08` — versus the static templates 4/5/7 used by
  the first-half op-13s (`w6=4`). Live: Thalmus's draw rec 1 reads
  `+2=3, +4=16` throughout the firing.
- **op-4 (`$02D8F4`)** plays **SFX 3** (`sfx_request(3)`) and calls
  `npc_spawn_at_step` (`$02B190`): it steps one cell west from Thalmus
  (direction `b3=3` via `$1E022`), checks the caster's cell is free
  apart from the caster himself (`$258EE(1, Y, X)` — returns the *second*
  char at the cell, so the caster does not block his own shot), then
  `entity_spawn(6, -1, b1-1, -1, b3, X, Y)` — a **mode-6 entity at
  Thalmus's own cell (8,26), direction west**. Fields: `+0x14=10`,
  `+0x16=10`, `+0x18=255`, `+0x1C=255`, `+0x1E=-1`, `+0x20=0`,
  `+0x22=3` (caster = Thalmus), `+0x24=0`, `+0x26=1`, `+0x28=0`.

### The projectiles, live

Four projectiles, one per op-4 (`$1A338`, `$1A348`, `$1A358`, `$1A368`),
all type `0x0096`, caster 3 (Thalmus), `+0x24=0`, `+0x18=255`. They
spawn in the first free slots (16, then 17 while 16 is occupied, then
16 and 17 reused after the earlier ones despawn; slots 18/19 never
used). Each travels **1 cell per world tick west along row 26**:

```
(8,26) Thalmus -> (7,26) -> (6,26) -> (5,26) -> (4,26) -> (3,26) -> (2,26) wall
```

and despawns at **(2,26)** (type `0x0096` → `0x00A0`, mode nibble
cleared). Row 26 west of Thalmus: x=7..3 are tile 184 (terrain 9,
Road, walkable); x=2 is tile 210 (terrain 4, Forest, **not**
walkable) — the room's west wall. The projectile stops on the wall
cell; it does not pass through it. No student stands on row 26 west of
Thalmus (Imino is at (10,26), **east** of the caster). No HP changes
anywhere; no damage is dealt.

So Dayset's read is confirmed in its geometry — Thalmus fires west,
at the wall, in front of (west of) the room the students stand in —
but the "spell" is a mode-6 projectile spawned directly by the event
script, not a Stun spell-record cast, and it never touches a student.

### The one sound anomaly

At ignition the song start `$FF022C` flips `0x6844` → `0x363E` for
~120 frames, then back; the song index `$FF012E` stays 13 throughout.
`$F363E` is song 8's start. The Life path bypasses the
`song_request` wrapper and calls `song_play_direct(8)` directly, which
is why the index does not change. The exact caller at ignition is not
pinned (candidates: `npc_attitude_positive` x4, `world_step_tile`,
`xp_grant`, `sys_dispatch_action_2dcce` x2). The visible "spell-fire"
in the first half is the op-13 pose change (Thalmus turns north) plus
this ignition sting — not a Stun cast.

## 5. Dialog (verbatim)

All spoken by Thalmus (`w6=1` → speaker id 1 → Thalmus), except 226,
whose record has `w6=0xFF` so the speaker is `b3=36` (meaning of
speaker 36 open). From `disasm/text/records_ddbd8.txt`. **Op-6 displays
record w4 + 96** — the numbers below are the displayed records; the
script's `w4` values are in the §2 table.

- **221** (w4=125): "I see we are all here, even Darius and Fezzik. Thank you for joining us, gentlemen."
- **222** (w4=126): "Today's topic is STUN. It takes very little energy to cast, and does little damage. As you gain experience, it will become your spell of last resort."
- **223** (w4=127): "STUN has a range of about ten feet, and gives your enemy a painful jolt. I will demonstrate..."
- **224** (w4=128): "Students, you are ready to use the STUN spell. I have a task for each of you."
- **225** (w4=129): "Buc, Ak Thul at the Temple of Nexus has asked to see you. When you're finished there, come back and I'll give you your assignment."
- **226** (w4=130): "Lesson over."

This is the STUN lesson itself — Thalmus introduces the spell, demonstrates it, and assigns the students' tasks. (The lines 125–130 previously quoted here are Thalmus's generic TALK barks, not this scene's dialog.)

## 6. The students are protected — twice

### Layer 1: the aim (geometric)

The four shots travel west along row 26 and despawn at the wall cell
(2,26). No student stands on row 26 west of Thalmus: Roakus (10,24),
Imino (10,26, east of the caster), Yoppa (6,25), Fezzik (4,24),
Darius (4,25). The shots cannot reach a student because the script
never aims at one. This is the protection in the shipped scene.

### Layer 2: no damage to a friendly on contact (collision-level)

Re-aiming the shots east, onto Imino, proves the second layer. A test
ROM (`rop-smooth-v2-fix-noprotect.rom`, built on the v3 smooth-move
fix) changes the four op-13 `b3` and four op-4 `b3` bytes from 3 (west)
to 1 (east), so Thalmus turns east and fires east. Live, the re-aimed
projectile travels (8,26) → (9,26) → **(10,26), Imino's cell**, and
despawns there — but **Imino's HP stays 20/20**, and every other HP is
unchanged. The projectile reaches the student and still does no
damage. So the mode-6 impact does not apply damage to a friendly char,
even on direct contact. The exact check is not located: the per-tick
mode-6 stepper (movement/collision/damage on impact) is unlocated, so
whether the guard lives in the stepper's collision test or in the
`attack_dispatch`/`damage_calc` path it would call is open.

### Checked and ruled out: the `damage_calc` +0x02==77 guard

`damage_calc` (`$03B1EE`) does contain a damage-skipping guard
(`$03B36E`–`$03B3B6`): after computing damage, if
`char[caster+0x27].+0x02 == 77` **or** `char[target+0x27].+0x02 == 77`,
it branches to `$3B3BA` and skips the HP subtraction (`sub.w d0,$1c(a0)`
at `$03B3B6`). But it does **not** fire for the students in this scene:
Thalmus `+0x27=2` → char 2 (Davin) `+0x02=1`; Roakus `+0x27=7` →
char 7 (Dunn) `+0x02=3`; Imino `+0x27=9` → char 9 `+0x02=5`; Yoppa
`+0x27=4` → char 4 (Maldavin) `+0x02=2`; Fezzik `+0x27=6` → char 6
(Beenie) `+0x02=96`; Darius `+0x27=14` → char 14 `+0x02=8`. No char
in the scene has `+0x02==77` (name 77 is 'Beenie'; spawn-table 77's
name is 102 'VOID'). The guard is real but irrelevant here; it was
**not** patched. A candidate patch (NOP the two `beq $3b3ba` at
`$03B38C` `67 2C` and `$03B3AC` `67 0C` → `4E 71` each) is recorded for
completeness but does not change this scene.

### The noprotect test ROM

- **File:** `rop-smooth-v2-fix-noprotect.rom` (MD5
  `253a03531108053562b3c0ed281583cc`), built on the v3 smooth-move fix
  (`rop-smooth-v2-fix.gen`, MD5 `662dc6c64211491bd6ef0fba0182eed7`),
  normal art, no cutskip, no freeze. Header checksum `0x5686`,
  runtime checksum `0xB9CD0069` (the runtime sum moved exactly `-0x10`
  for the eight word-changes).
- **Patch (8 bytes, all `0x03` → `0x01`):** op-13 `b3` (Thalmus
  heading) at `$1A333`, `$1A343`, `$1A353`, `$1A363`; op-4 `b3`
  (projectile direction) at `$1A33B`, `$1A34B`, `$1A35B`, `$1A36B`.
  Build: `~/workspace/rop-work/buc-scene/patches/noprotect/build.py` (worktree — diagnostic test patch, not on main) (verifies the v3 base MD5 and
  the eight `0x03` bytes, then `tools/checksum.py fix-all`).
- **Live result:** the ROM boots and the cutscene runs. GUI screenshots
  of the noprotect ROM and v3 at the cutscene (28 s after loading
  `slot_0`, `.scratch-buc-scene/shot_noprotect.png` vs `shot_v3.png`)
  are **byte-identical** (SHA-256
  `7f3af108099ace860aaecf9e192800b2b47a5036725f23fd76cb1a59e904afe5`):
  both show the in-world room with the HUD, the scene stalled at the
  same dialog point (text 223, waiting for A) — as expected, since the
  re-aim only affects the later projectile phase. The dialog text box
  is not distinctly visible in the capture; the stall point is
  established by the probe logs, not the screenshot. Separately,
  probe_j (same re-aim, original-based probe ROM) proves the logic:
  Thalmus fires east, the projectile reaches Imino's cell (10,26) and
  despawns — Imino stays 20/20. The ROM removes the **aim** protection
  and thereby proves the **collision** protection exists. It does
  **not** make the shots able to hurt the students; fully enabling
  damage would need the collision-level guard located and disabled
  (open item).
- **"Optional" form:** by ROM choice — this test ROM is protection-off
  (aim), normal ROMs are protection-on. A runtime toggle would be
  trivially feasible in principle (a single flag checked by the op-4
  handler or by the mode-6 stepper, e.g. a byte in unused RAM read
  before choosing the direction / before the friendly check), and the
  remake could implement it as a real option (a "friendly fire"
  toggle on the cutscene). No runtime toggle was built here; the
  separate-ROM form is the deliverable.

## 7. Exit

Op-0 (`$1A390`, handler `$02D5D4`): loops the party list `$FF0E82`,
calls `$2BBD2(member, 0x401, 25, 1)` per member. Quotient `0x401` =
major 16, minor 1 → `xp_grant` (`$02C4E2`): +25 XP to each of the 6
party members (clamped to 13000, level recomputed). Then clears
`$FF0110` (dialog unlock) and control returns to the player. If the XP
crosses a level boundary, `xp_grant` plays song 8 (`$02C634`) as the
level-up sting. The exit past `$1A378` (text 225) was not live-observed
(the probes ended at text 225); the op-0 handler and the XP path are
verified statically.

## 8. Camera

The camera follows via `combat_move_unit` → `world_reposition_leader`
(`$02513E`) → `leader_spawn` mode 5: each op-5 move repositions the
leader's spawn to the moved char's cell and the camera steps toward
it. Final camera (6,25), on Buc. (The "invisible cell that wants to go
south" Dayset reported is Buc: entity 1 at (8,7), heading south,
walking south; the camera tracks his Y exactly.)

## 9. Location, chunk, room

- Location 156 = `$D1D00` record 30, key (116,113), message 29 (the
  overworld anchor; the leader in `slot_0` stands at (117,113), one
  cell east).
- Chunk 233 (a 32x32 chunk, decoded 2048 B). Cell words
  (chunk-local): (6,17) `0x00DA` tile 218; (9,17) `0x00D5` tile 213;
  (6,25)/(4,24)/(4,25)/(8,26)/(10,24)/(10,26) `0x00B8` tile 184;
  (8,7) `0x00DA` tile 218.
- Terrain via the `$5EDC4` table (bits 10-15): tiles 184/218/213 →
  terrain 9 = Road, walkable. The wall cell (2,26) is tile 210 →
  terrain 4 = Forest, not walkable; (1,26) tile 110, (0,26) tile 88
  (terrain 7, not walkable).

## 10. Live-proven vs static-only

**Live-proven** (BlastEm harness, `slot_0` state, probes e/h/i/j in
`.scratch-buc-scene/`): the full first half (teleport, placements,
spawns, 18 moves, text 221-223, no spell machinery, no SFX spike
except the ignition song-8 sting); Thalmus's final position (8,26)
and heading; the students' identities, spawn slots, and final
positions; all HPs unchanged at max; the four op-13 cast poses
(draw rec 1 `+2=3, +4=16`); the four mode-6 projectiles (type
`0x0096`, caster 3, slots 16/17, 1 cell/tick west along row 26,
despawn at the wall cell (2,26)); the re-aimed projectile travelling
east to Imino's cell (10,26) with Imino staying 20/20; the script
advancing through `$1A378` (text 225).

**Static-only** (verified verbatim against ROM bytes / `rop.s`, not
run live): the op-13/op-4/op-6/op-10/op-0 handler bodies; the
`npc_spawn_at_step` field assignments; the `damage_calc` +0x02==77
guard and its non-firing for the students; the entry menu-choice
mechanism (`menu_select_screen` case 1 via `npc_attitude_positive`);
SFX 3 from the op-4 handler (the SFX itself is not visible in the
song state); the op-0 25-XP grant and `$FF0110` clear; text 226 and
the exit past `$1A378`.

## 11. Open items

- The per-tick **mode-6 stepper** (movement/collision/damage on
  impact) is unlocated. It is the routine that decides what happens
  when a projectile reaches an occupied cell — the collision-level
  friendly-fire guard lives there or in the path it calls.
- The exact `song_play_direct(8)` caller at ignition (candidates:
  `npc_attitude_positive` x4, `world_step_tile`, `xp_grant`,
  `sys_dispatch_action_2dcce` x2).
- Which TALK-menu option text yields case 1 (needs the `$32D4C`
  menu-table trace for Thalmus).
- Meaning of op-6 record 226's speaker `b3=36`.
- Char 4's `+0x14` = 10 instead of 5 (Yoppa's slot) — unexplained.
- When Maldavin/El Gripa/Beenie were freed before the scene spawns.
- `sys_struct52_nibble_read(4)` effect beyond the op-7 check
  (untraced).
- Whether the mode-6 projectile's effect corresponds to Stun (spell
  record 1) mechanically — the script never references spell record 1,
  so this is a design question for the remake, not a code fact.
- Probe note: `probe_f`/`probe_g` crashed (wild-pointer) because their
  RAM log crossed the stack pointer `$FFEC1E`; the safe log region is
  `$FFD800`–`$FFEC1E` (5150 bytes). `probe_h`/`probe_i`/`probe_j` use
  it and run clean. Probe note 2: `probe_f`/`probe_j`'s header labels
  the two draw-rec fields `d1p2`/`d1p4`, but the layout only logs draw
  rec **0** (Buc's); Thalmus's rec 1 pose is logged by `probe_h`/`probe_i`.
