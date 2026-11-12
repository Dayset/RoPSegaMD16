# The Fezzik cutscene (Ring of Perfection)

The scripted scene in which Buc brings the Sun and Moon gems to Fezzik,
the two of them fit the gems into the slots at opposite ends of the room,
a Ring materializes — and Fezzik takes it. This is event-script case 6
(`menu_select_screen` `$02D3DC`). It is documented here as part of the RE
spec for the tribute remake (M7): every record, actor, line of dialog,
and the event call that does *not* grant the Ring.

> **A correction that shapes this whole document.** The dialog lines a
> cutscene shows are **not** the raw text records numbered by the script's
> `w4`. Op-6 calls `text_event_resolve(3, 11, w4)` (`$02D964` → `$02D9CA`),
> and with arg1 = 3 the resolver takes the `L032D9E` path
> (`$032D9E`–`$032DA6`): the displayed text record is **w4 + 0x60 (96)**,
> via `text_record_dispatch` (`$032EB0`–`$032EC4`, tables `$DDBD8` /
> `$E0A18`). The same +96 shift applies to TALK-dialog events (event N
> displays text N+96) and to op-15's `text_event_resolve(3, 11, 541)`,
> which shows text 637, not 541. Every line quoted below is therefore
> given by its **displayed** text-record number, with the raw `w4` /
> event id in parentheses. An earlier reading of this scene quoted the raw
> records (542–545) and identified the speaker as a crystal-ball "seer";
> that identification is withdrawn — the speaker is Fezzik, and the
> crystal-ball lines belong to another thread (see §10).

## At a glance

- **Script:** ROM `$1A4E8`–`$1A518`, 7 8-byte records, opcode = `abs(byte0)`,
  negative `byte0` chains to the next record, non-negative `byte0` pauses.
  Pointer `$FFC384`, engine `sys_event_run` (`$02D56A`, dispatch `$02DBB8`,
  relative jump table, base `$02DBE8`).
- **Location:** the trap room — event 100's location gate is `$D1D00`
  record 405 (key (329,184)); Fezzik's home is record 60 (see §8).
- **Entry:** TALK to Fezzik, pick the menu option that yields event 540
  in `npc_attitude_positive` (`$0298D2`) → case 6 in `menu_select_screen`
  (`$02D3DC`).
- **The scene:** Fezzik has been waiting for someone to help him open
  the trap and get the Ring of Perfection (text 636). If Buc lacks the
  two gems, Fezzik says so (text 637); otherwise the gems are fitted,
  the Ring materializes (text 640) — and Fezzik claims it (text 641).
- **Effects:** event-bit 100 set in the `$FFC326` bitmap; **no ring is
  granted** — there is no `inv_apply_resource` call anywhere in the
  script, and no dialog event grants item 650 (Ring of Perfctin). The
  scene grants **0 XP**.
- **Exit:** op-0 grants 0 XP and clears the dialog lock (`$FF0110`).

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 6 is `$1A4E8` (dispatch table `$02D480`, base `$02D4A4`).
The in-game caller is `$02A188`, inside `npc_attitude_positive`
(`$0298D2`): it pushes a local `-$6(a6) & 0xFFF` as the case. The case is
reached from TALK-dialog event 540:

- Event 540 in the `$D3102` table (12-byte records): `+2 = 108`,
  `+8 = 0x4006`, `+10 = 0xF000`. The second dispatch (table `$02A1EE`,
  on `(rec+8 rol 4) & 0xF` = 4) takes action 4 → `$02A17C` →
  `menu_select_screen(rec+8 & 0xFFF)` = case 6 (`$02A188`).
- Event 540's own dialog text is text 636 (540 + 96): *"So we meet
  again, Buc. I have been waiting here for someone to show up and help
  me open the trap and get the Ring of Perfection."* — Fezzik's greeting,
  spoken when the player picks the option that leads into the scene.
- Which menu-option text yields event 540 is open: the menu-choice →
  `$02A6` event-id mapping (which option text the player picks) is not yet
  traced.

After loading the pointer, `menu_select_screen` clears `$FF00AC` and
`$FFA7FA`, sets `$FFB08A=$FF`, `$FF009C=$FFFF`, `$FF0110=$FFFF` (dialog
lock), calls `$138A8`, then `$1E5A0` or `$26DD2`, then `$26E44` if
`$FF009C!=0`. From then on the script runs on its own, about one
`sys_event_run` call per 4 ticks, gated by `grid+$A` (`$FFB0B6`).

## 2. Script table

Verbatim ROM bytes, `$1A4E8`–`$1A518`. `w4` is the record's word at +4,
`w6` the word at +6, `b1`/`b2`/`b3` the bytes at +1/+2/+3. Opcode is
`abs(byte0)`; a negative `byte0` means "run the next record
immediately", a non-negative `byte0` pauses until the next engine tick.
Handler addresses are from the verified dispatch table `$02DBB8`
(relative offsets, base `$02DBE8`).

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A4E8` | `0F 00 00 00 00 00 00 00` | +15 | Text-event resolve (all-zero record). Handler `$02D67C`. See §5. |
| `$1A4F0` | `06 00 00 00 02 1E 00 00` | +6 | Text w4=542 → **text 638**. Speaker `raise_by_id(0)` (leader). Handler `$02D964` (`sys_event_op6_text`). |
| `$1A4F8` | `06 00 00 00 02 1F 01 56` | +6 | Text w4=543 → **text 639**. Speaker `raise_by_id(342)` (Fezzik). |
| `$1A500` | `FA 00 00 0D 02 20 00 FF` | -6 | Text w4=544 → **text 640**. Speaker portrait b3=13 (w6=0xFF). |
| `$1A508` | `0B 00 00 01 00 64 00 00` | +11 | Event call w4=100, b3=1. Handler `$02DB06` → `npc_attitude_event_apply` (`$02B6E0`). |
| `$1A510` | `06 00 00 00 02 21 01 56` | +6 | Text w4=545 → **text 641**. Speaker `raise_by_id(342)` (Fezzik). |
| `$1A518` | `00 00 00 00 00 01 00 00` | +0 | Grant: w4=1, w6=0 → **0 XP** per party member, clear `$FF0110`. Handler `$02D5D4` (`sys_event_op0_grant`). |

### Opcode handlers used (dispatch `$02DBB8`, base `$02DBE8`)

| op | handler | name | does |
|---|---|---|---|
| 0 | `$02D5D4` | `sys_event_op0_grant` | Grant w6 XP per party member; clear `$FF0110`. |
| 6 | `$02D964` | `sys_event_op6_text` | Enqueue text w4 (displayed as w4+96); speaker = char[`npc_attitude_raise_by_id` (w6)].portrait, or b3 if w6 == 0xFF. |
| 11 | `$02DB06` | *(unnamed — see REPORT)* | Call `npc_attitude_event_apply` (`$02B6E0`, w4, b3). |
| 15 | `$02D67C` | *(misnamed `sys_event_op1_teleport` — see REPORT)* | Text-event resolve: Fezzik/gems check, else the location-392 / bit-174 / message branch. See §5. |

## 3. Actors

Char struct 52 B at `$FF02B4`; id → char via `npc_attitude_raise_by_id`
(`$02D50C`), which scans type-1 chars for `+0x02 == id` and returns the
attitude byte at `char[nameIdx].+0x26`. The mapping is per-scene, from
the char setup at entry — do not carry the Buc setup's mapping onto this
scene.

### Fezzik — id 342

- Template 342 (`$CF1AC` + 24×342): word0 = 108, words
  (108, 113, 121, 130, 137, 145), `+12 = 34`, `+16 = 0x3C` (60, home
  location record), `+18 = 90`, `+19 = 2`.
- The template's spawn list starts with spawn 108 (`$CECF0` + 6×108):
  name index 144 = **'Fezzik'**, portrait byte 50. The remaining list
  entries (113, 121, 130, 137, 145) are all name index 0 = 'Nobody' —
  generic/encounter stat blocks, not named characters.
- Fezzik is the speaker of texts 636 (entry), 639 and 641 (via
  `raise_by_id(342)`), and the template the op-15 handler looks up.
  He is **not** a crystal-ball seer: the seer reading came from the
  unshifted raw text records 540–546; the shifted lines are Fezzik's
  Perfection-trap dialog.

### The leader — id 0

- The party leader (w4=0 / w6=0 in the op-6 speaker resolution). Speaks
  text 638 (*"I have both of the gems Fezzik."*) — the line is addressed
  to Fezzik, and the speaker resolves via `raise_by_id(0)`, the id-0
  slot (the leader in the `slot_0` setup; per-scene mapping otherwise
  open).

## 4. Dialog (verbatim)

Displayed text records (raw `w4` / event id in parentheses). All lines
are from `disasm/text/records_ddbd8.txt`.

- **Text 636** (entry, event 540 → 540+96; Fezzik): *"So we meet again,
  Buc. I have been waiting here for someone to show up and help me open
  the trap and get the Ring of Perfection."*
- **Text 637** (op-15, shown only if the leader lacks both gems; see
  §5): *"Unfortunately, both the Sun and the Moon gems are needed to
  free the Ring."*
- **Text 638** (op-6, w4=542; leader): *"I have both of the gems
  Fezzik."*
- **Text 639** (op-6, w4=543; Fezzik): *"Good, then let me help you get
  the Ring."*
- **Text 640** (op-6, w4=544; speaker portrait b3=13): *"The two of you
  each take a gem and fit it into the slots at opposite ends of the room.
  Suddenly a Ring materializes in the center of the chamber."*
- **Text 641** (op-6, w4=545; Fezzik): *"The Ring of Perfection. I'm
  afraid you're out of luck, Buc. This Ring is mine."*

No other dialog is shown in this scene. The crystal-ball / Ahab /
Bandit Hole lines (raw text records 540–546) are **not** in this script
— they are the raw records for events 540–546, and the lines the player
actually sees from those events are the +96 records 636–642 (see §10).

## 5. Effects

### The op-15 resolve — `$02D67C`

The all-zero op-15 at `$1A4E8` runs the op-15 handler verbatim
(`$02D67C`):

1. `world_find_char_template(0x156 = 342)` (`$031998`) — looks for
   Fezzik's template char. If found (the normal case here — this is
   Fezzik's scene):
2. `item_category_of(0x35B = 859, leader)` (`$02C8F2`) — tests whether
   the leader has item 859. Item categories (`$D66A0`, 20 records × 10
   B): category 13 = "items", count 33; item 859 = price record 180 =
   **"S Gem"** (Sun gem), item 860 = price record 181 = **"M Gem"**
   (Moon gem). If the leader does **not** have the S Gem, the text path
   runs: `text_event_resolve(3, 11, 0x21D = 541)` → displays **text
   637** (*"Unfortunately, both the Sun and the Moon gems are needed to
   free the Ring."*), `text_enqueue_message` with the speaker from
   char[`raise_by_id(342)`], clears `$FF0110`, `combat_select_unit`,
   `menu_set_mode(0)`.
3. If the leader **does** have the S Gem, `item_category_of(0x35C =
   860, leader)` is tested: if the leader also has the M Gem, the
   handler returns with no text (both gems present — the scene proceeds
   to text 638); if the leader has the S Gem but not the M Gem, the
   text path runs as above.
4. If template 342 is **not** found, the else branch (`L02D740`)
   runs: location 392 → release `party[0]` + spell effect 9; else
   bit 174 test → return; else message (74, 37) + song 4. Not expected
   in this scene.

Note the order: the op-15 gem check runs **before** the cutscene's
own lines. If Buc lacks a gem, text 637 is shown — and the script then
continues unconditionally into text 638 (*"I have both of the gems
Fezzik."*), which contradicts it. The script has no branch on the
op-15 outcome; whether the contradiction is visible in play (does the
scene even start without both gems, or does the entry dialog gate it?)
is open.

### The op-11 event call — `npc_attitude_event_apply` (`$02B6E0`)

Op-11 (`$02DB06`) at `$1A508` calls `npc_attitude_event_apply(100, 1)`.
The routine first sets bit 100 in the event bitmap at `$FFC326`
(`sys_bitmap_write`), then looks up the 6-byte record at
`$D601E + 6*100` and dispatches on its kind (`rol5(word0) & 0xF`,
jump table `$02BBB4`).

- ev100: w0 = `0x1A8A`, kind 3, location 405, chunk 2, b4 = 2, b5 = 5.
  Code word0 & `0x7FF` = `0x28A` = 650 = **Ring of Perfctin** (ring
  items are 640–650; category 10 = rings, count 11 at `$D6707`).
- Kind 3 (`L02B9B8`) is the spawn/place-NPC path via the `$CF1C0`
  table — but it does **not** fire for this record. The guard passes
  only if `npc_attitude_raise_by_id(rec+2 word)` returns exactly
  $FFFF (not found — `moveq #$ff` sign-extends to $FFFF), which it does
  here (rec+2 = `0x2195`, no char carries it); then the routine indexes
  `$CF1C0` by rec+2 × 24 = 206,328 bytes past the table base — out of
  the 1 MB ROM. The read returns $FFFF, whose low 10 bits (1023) never
  match the current location (405), so the location gate fails and the
  path bails to the tail (which runs `combat_attacker_check` only if a
  char was found — none was). The same out-of-ROM index holds for all
  16 kind-3 records, so kind 3's spawn path is effectively dead in the
  shipped ROM; its only reliable effect is the bitmap write.
- **Net effect of the op-11: event-bit 100 is set. Nothing else.** No
  NPC spawns, no item is granted, no tile changes.

### The Ring is not granted here

- The script contains no `inv_apply_resource` call. The op-11 does not
  grant anything (see above). The closing op-0 grants 0 XP.
- A scan of all `$D3102` dialog events for the grant action
  (first-dispatch action 6, `+10` nibble 6 → `inv_apply_resource(leader,
  id & 0xFFF, 1, 1)` at `$029B4E`) finds **no event granting item 650**
  (Ring of Perfctin). The ring grants that do exist nearby are
  different rings: event 313 grants 643 (Division), event 442 grants
  642, event 448 grants 649 (Calling), event 497 grants 647.
- The Ring of Calling (item 649) is granted by **event 448**
  (`+10 = 0x6289` → `inv_apply_resource(leader, 649, 1, 1)` + message +
  song 8). Event 448's own dialog text is text 544 (448+96) — the
  *"Here, take the Ring"* line — but event 448 is not the seer's
  dialog and not part of case 6; its speaker/context is not pinned.
  Do not conflate it with this scene.
- In-fiction, the Ring of Perfection materializes (text 640) and
  Fezzik takes it (text 641). Whether event-bit 100 is read anywhere
  as "Perfection obtained / attempted" is open — no reader of bit 100
  has been found yet.

## 6. Exit

Op-0 at `$1A518` (bytes `00 00 00 00 00 01 00 00`): w4=1, w6=0 — **0 XP**
to each party member, `$FF0110` cleared. (What w4=1 means in the grant
handler is open; the XP amount is w6 = 0.) The scene ends; control
returns to normal play.

## 7. Camera

There is no op-1 in this script — no teleport, no camera move. The
scene plays wherever the player stands when talking to Fezzik.

## 8. Location, chunk, room

The `$D1D00` table is 455 records × 10 B: +0 word = overworld key X,
+2 word = key Y, +4 byte = destination location number, +5 byte =
message index. Two records matter here:

| record | key (X,Y) | +4 dest | +5 msg | note |
|---|---|---|---|---|
| 60 | (164,113) | 49 | 19 | Fezzik's home (template 342 `+16` = 60). |
| 405 | (329,184) | 131 | 16 | Event 100's location gate — the trap room (per text 640's room with slots at opposite ends). |

Which record the scene runs at is open: the op-11 gate says 405, and
Fezzik's template home says 60. The room itself (chunk, dimensions) is
unpinned. Note that record 405's key (329,184) is close in X to the
Temple of Variation's record 393 (key (330,62)) but far in Y — they are
different rooms.

## 9. Live-proven vs static-only

**Static-only.** No live verification was attempted, and none is safe
with the save on hand: the only save state is `slot_0` (location 156,
Thalmus room setup), whose char setup resolves only small ids (0, 1, 2,
3, 5) and spawn ids 94–96, 101, 102. This scene needs id 342 (Fezzik);
`npc_attitude_raise_by_id(342)` returns $FF in `slot_0`, and the op-6
speaker resolution would read char[255]'s portrait (out of bounds), so
the scene's pointers must not be injected into `slot_0`. Every claim
above is from ROM bytes and `disasm/src/rop.s` unless marked open.

## 10. Open items

1. **Who is portrait 13?** Text 640's speaker is portrait b3=13. No
   spawn-table record has portrait byte 13 — it is a direct `$B86AE`
   portrait index, and whose face it is (a narrator? one of Fezzik's
   gang?) is open.
2. **Where does the Ring of Perfection go?** No grant of item 650
   exists in any dialog event or cutscene script, and no reader of
   event-bit 100 has been found. Is bit 100 the "Perfection" flag, and
   does anything check it — or is the Ring simply unobtainable (Fezzik
   keeps it)?
3. **The gem-check contradiction.** Op-15 shows text 637 when Buc
   lacks a gem, then the script continues unconditionally to text 638
   (*"I have both of the gems Fezzik."*). Is the scene gated before
   entry (so 637 never shows in practice), or does the contradiction
   play out? Needs a live check from a save at the trap room.
4. **The crystal-ball thread.** The Ahab / Bandit Hole / "Here, take
   the Ring" lines (raw text records 540–546) are the raw records for
   events 540–546, whose displayed texts are 636–642. Text 541 (the
   Ahab line) would be displayed by event 445 (445+96) or op-6 w4=445
   — which event or scene actually shows it is unpinned. The
   Observatory (text 902: *"Hello sir, welcome to the Observatory..."*,
   west of Richi per text 441) may be the seer's location, but the
   seer's identity and location are not pinned.
5. **Which record the scene runs at** — 405 (the op-11 gate) or 60
   (Fezzik's home). Needs the location-setup NPC list or a live check.
6. **The menu-option text that yields event 540** — the menu-choice →
   `$02A6` mapping is untraced.
7. **Op-0's w4=1** — the grant handler's use of w4 (if any) is open;
   the XP amount is w6 = 0 either way.
