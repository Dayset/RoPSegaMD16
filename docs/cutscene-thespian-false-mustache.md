# The thespian's false mustache (Great Ampitheatre)

The scripted scene in which a thespian at the Great Ampitheatre hands
Buc his false mustache — the ingredient Lucius the Necromancer needs
to dispel the undead. The scene has no dialog of its own: its one
script record is a bare op-0, and all the action happens in the entry
dispatch, before the script runs. Documented here as part of the RE
spec for the tribute remake (M7).

## At a glance

- **Script:** ROM `$1A3B0`, 1 record, 8 bytes. Pointer `$FFC384`,
  engine `sys_event_run` (`$02D56A`).
- **Location:** the Great Ampitheatre (text 82; exact location number
  open, §8).
- **Entry:** TALK to the thespian, pick the menu option that yields
  case 3 in `menu_select_screen` (`$02D3DC`).
- **The scene:** the entry itself. The greeting (text 497) offers Buc
  the false mustache; the entry dispatch grants item-flag bit 20 in
  the items bitmap `$FFC340` and plays song 8. The script then runs a
  single op-0: 0 XP, dialog unlock, no battle-end.
- **The quest link:** Lucius the Necromancer (identity 173) needs "the
  mustache of a thespian" to dispel the undead (text 492) and, on
  receiving it, hands Buc a Necromancer spell (text 494).

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 3 is `$1A3B0` (dispatch table `$02D480`, base `$02D4A4`).
The only in-game caller is `$02A188`, inside `npc_attitude_positive`
(`$0298D2`): it pushes a local `-$6(a6) & 0xFFF` as the case — the local
is the out-param of a `$32D4C` text/menu call, i.e. the player's
TALK-dialog menu choice. So the entry is: **TALK to the thespian, pick
the menu option that yields case 3**.

The entry record is `$D3102` index 401 (12 bytes, verbatim
`00 19 09 80 00 00 91 6F 40 03 63 54`): kind 25, identity 2432
(`0x980`), `w8=0x4003`, `w10=0x6354`. It is the thespian's *only*
`$D3102` record. How it is found: `npc_attitude_positive` calls
`shop_record_score` (`$0331A4`), which scans the `$D3102` table (1005
records × 12 bytes) scoring `+0x10000` if record+0 == kind and
`+0x4000` if record+2 == the talked-to char's `+0x02`, plus
`RNG(0x400)` jitter; the best index wins. The out struct gets out+0 =
record+8, out+2 = record+10, out+4 = best index. Kind 25 is NPC-menu
option 25 (the `$022xxx` menu dispatch, `$0221EE`: options 14–45 pass
through as the kind, so option 25 yields kind 25).

The greeting the player hears on entry is text 497 (record 401+96),
from `disasm/text/records_ddbd8.txt`:

- **497:** "So you want to see our show? Please, sit down! Wait a
  sec, hold on to this false mustache of mine. I don't need it for
  this play."

## 2. Script table

Verbatim ROM bytes, `$1A3B0`. Opcode is `abs(byte0)`.

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A3B0` | `00 00 00 00 00 00 00 00` | 0 | Grant 0 XP; clear `$FF0110`; `w4=0`, so no `combat_battle_end`. |

`$1A3B8` begins the next script (`menu_select_screen` case 4). The
one-record script exists because the case dispatch must land
somewhere: the grant already happened in the entry dispatch (§4), and
the script is just the unlock.

### Opcode handler used here (dispatch `$02DBB8`, base `$02DBE8`)

- op 0 → `$02D5D4`: loops the party list `$FF0E82`, calls
  `inv_apply_resource` (`$02BBD2`) `(member, 0x401, w6, 1)` per
  member — quotient `0x401` = major 16, minor 1 → `xp_grant`
  (`$02C4E2`), +`w6` XP (0 here) — then clears `$FF0110`. `w4=0`,
  so `combat_battle_end` (`$03599C`) is **not** called.

## 3. Actors

- **The thespian** — identity 2432 (`0x980`). One `$D3102` record
  (index 401, the entry). He speaks only the greeting (text 497);
  there is no other dialog of his in the table. His name is not
  recorded in the name table under this identity — "thespian" is the
  role the dialog gives him, not a pinned name. The identity decodes
  through `shop_record_score`'s large path (`$033264`–`$0332A0`) as
  2432 − `0x800` = **384** = the talked-to char's `+0x02` — the
  thespian's char identity in the theatre setup.
- **Buc** (name index 57) — the party leader; receives the mustache.
- **Lucius** (identity 173) — the mustache's recipient; see §4. His
  lines identify him by name: text 490, "I am Lucius, the greatest
  Necromancer in the world."

## 4. The entry grant — what actually happens

`npc_attitude_positive` dispatches on the out struct *before* it
reaches `menu_select_screen`. The first dispatch (table `$029F8A`)
runs on the top nibble of record+10 (`0x6354` → nibble 6 →
`$029B0C`); the second dispatch (table `$02A1EE`, at `$029FBA`) runs
on the top nibble of record+8 (`0x4003` → nibble 4 → `$02A17C` →
`menu_select_screen` with case 3). The type-6 path at `$029B0C`:

1. `val = w10 & 0xFFF` = 852. `val>>6` = 13, which is > 6, so the
   party-full check at `$029B0C` is skipped.
2. `inv_apply_resource` (`$02BBD2`) `(leader, 852, 1, 1)`. The code
   852 = major 13, minor 20 (852/64 = 13, 852%64 = 20). The quotient
   dispatcher (`$02C8D6`, table `$02C8C4`) sends major 13 to
   `sys_set_item_flag` (`$02C0BE`), which sets bit 20 in the 5-byte
   items bitmap `$FFC340` via `sys_bitmap_write` (`$02B68C`).
3. `text_enqueue_message` (`$026B58`) with picture 86, mode 12, word
   852, and an **empty** text pointer: the pushed text pointer is 0,
   and `strcpy` from address 0 stops at the first byte — the ROM
   header byte `0x00` — so an empty string is enqueued. Picture 86
   is the items-category picture: the item-category table `$D66A0`
   (20 records × 10 bytes) gives category 13 ("items") the `A` byte
   (message picture) 86 (`$D66A1 + 13*10`). The mode word 12 (≠ 1)
   means the text pointer is *not* loaded into `$FF0E7A`, and 852 is
   stored to `$FF0E80`. What the player sees for this empty message —
   a blank dialog box, or nothing at all — is not live-proven (§9).
4. `song_play_direct` (`$0173EC`) plays song 8 — the same sting the
   Buc entry plays (its `w10=0x3008` first-dispatch path also ends in
   `song_play_direct(8)`).

So TALK to the thespian, pick option 25: greeting 497, item-flag bit
20 set, song 8, an empty message, then the one-record script unlocks
the dialog.

### The mustache's purpose

Lucius's `$D3102` tree (identity 173, indices 394–398) is the other
half of the quest:

- **490** (idx 394, kind 22): "I am Lucius, the greatest Necromancer
  in the world."
- **491** (idx 395, kind 23): "I have created a brilliant new spell
  called RAISE which allows the soul of a corpse to be bound to the
  body, bringing it back to life."
- **492** (idx 396, kind 50): "Perhaps it could also dispel the
  undead. Unfortunately I am missing the primary ingredient: the
  mustache of a thespian."
- **493** (idx 397, kind 9): "Aha! The false mustache of a thespian!
  Just a moment..."
- **494** (idx 398, kind 50): "Here you go! One super powerful
  Necromancer spell. Make sure you tell everyone that you have the
  latest from Lucius -- it pays to advertise, you know!"

(The earlier note that these lines were texts 986/988 was a slip:
986/988 are Dead-Lands lines — "Ha! Job. What job need the dead
have?…" and "Magic? What magic have those who have been to the Dead
Lands?" — dialog indices 890/892, identity 0. The mustache lines are
492/493, dialog indices 396/397, identity 173.)

Item-flag bit 20 is *presumably* the false mustache — the grant
happens exactly when the thespian says "hold on to this false
mustache of mine", and Lucius's kind-9 line (493) is the handoff.
But no item-flag name table was found, so the identification rests on
the greeting plus Lucius's lines, not on a named flag; the read site
that tests bit 20 of `$FFC340` is an open item (§10). A nearby generic
theatre line, text 495 (dialog index 399, identity 0): "Welcome to our
humble theatre. I hope you will stay for our little show."

## 5. Dialog (verbatim)

The scene's only spoken line is the entry greeting, text 497 (the
thespian). The script itself has no text records. All lines from
`disasm/text/records_ddbd8.txt`.

- **497:** "So you want to see our show? Please, sit down! Wait a
  sec, hold on to this false mustache of mine. I don't need it for
  this play."

## 6. Effects

The entry dispatch sets item-flag bit 20 (`$FFC340`) and plays song 8.
The script adds nothing: 0 XP, dialog unlock, no battle-end. No
moves, spawns, poses, or SFX records anywhere in the case.

## 7. Camera

No camera records: no op-1 teleport, no op-5 moves. The camera stays
where the entry TALK left it; the scene plays in place.

## 8. Location

The Great Ampitheatre. Text 82: "This is the Great Ampitheatre,
where the finest theatrical performances in the world are held." The
exact location number (`$D1D00` record) is open — the `$D1D00` table
(455 records × 10 B, +4 byte = location number) is dumped at
`.scratch-cutscenes/case2-3-5-7/d1d00_dump.txt` for the follow-up.

## 9. Live-proven vs static-only

**Live-proven:** nothing for this scene. It is static-only.

**Static-only** (verified verbatim against ROM bytes / `rop.s`, not
run live): the entry record (kind 25, identity 2432, `w8=0x4003`,
`w10=0x6354`); the type-6 dispatch path (`$029B0C` → `inv_apply_resource`
→ `sys_set_item_flag`, bit 20 in `$FFC340`); the empty-message
enqueue (picture 86, mode 12, word 852, text pointer 0); song 8;
the one-record script. The reason it is static-only: live proof
would need a save in the theatre with the thespian present, and the
only save state on hand is `slot_0` (location 156, Thalmus's room),
where the thespian is not present. Injecting the script pointer alone
would prove nothing — the grant lives in the entry dispatch, not in
the script, so a script-pointer probe cannot observe it.

## 10. Open items

- Confirm item-flag bit 20 is the false mustache: find the read site
  that tests bit 20 of `$FFC340` (candidate: Lucius's kind-9 path at
  index 397, `w10=0x018E`, or an `item_category_of` (`$02C8F2`)
  quotient-13 read).
- Lucius's location, and which spell record text 494 grants (RAISE,
  or another Necromancer spell).
- What the player sees for the empty message (blank dialog box vs
  nothing) and whether the dedup check in `text_enqueue_message`
  can swallow it.
- Which TALK-verb call site yields kind 25 in play (menu option 25
  is pinned as the kind source; the option *text* for the thespian
  needs the `$32D4C` menu-table trace).
- A live probe for the grant needs a theatre save state; none is on
  hand.
