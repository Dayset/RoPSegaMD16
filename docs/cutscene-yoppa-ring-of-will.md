# Buc confronts Yoppa over the Ring of Will

The scripted scene in which Buc tracks Yoppa down and demands the Ring
of Will. Yoppa has it, and is under orders from the High Priest to
deliver it to the Temple; he refuses, and tells Buc he must fight him
for it. Four lines of dialog — two each — and an exit grant; no moves,
no spawns, no poses, no SFX. Documented here as part of the RE spec
for the tribute remake (M7).

**How the dialog works in these scenes — read first.** Op-6's `w4` is
*not* the text record. The op-6 handler (`$02D964`) calls
`text_event_resolve` (`$032D4C`) with kind 11; the kind-11 path
(`$032D68`) dispatches on the third argument via table `$032DDE` to
`$032D9E`, which sets the result to **`w4 + $60` (96)** and copies
`$D3102[w4]+8/+10` into the out struct. The tail (`$032EB0`) then calls
`text_record_dispatch` (`$013654`), which fetches text record
**`w4+96`** from the `$DDBD8` table and copies its text into `$FFBB86`
(`&P` sequences become NUL paragraph breaks). `text_enqueue_message`
(`$026B58`) enqueues (`$FFBB86`, mode 1, speaker picture) into the
`$FFBC94` message ring. So the line the player sees for op-6 `w4=N`
is **text record N+96**. This is live-proven for the sibling scenes
(§9): case 2's `w4=366/367` displayed texts 462/463, and case 7's
`w4=571–583` displayed texts 667–679. The earlier reading of this
scene (texts 469–472, tomes and magic sand and the glass blower) is
wrong — those lines are dialog records 373–376 of the master and
assistant glass-blower NPCs, not this scene's dialog.

## At a glance

- **Script:** ROM `$1A4C0`–`$1A4E8`, 5 records, 8 bytes each, opcode =
  `abs(byte0)`, negative `byte0` chains to the next record,
  non-negative `byte0` pauses. Pointer `$FFC384`, engine
  `sys_event_run` (`$02D56A`).
- **Location:** not pinned (Yoppa was bringing the Ring "back to the
  Cathedral"; the confrontation site is unknown, §8).
- **Entry:** TALK to Yoppa, pick the menu option that yields case 5 in
  `menu_select_screen` (`$02D3DC`).
- **The scene:** four lines, Buc and Yoppa alternating. Buc demands
  the Ring; Yoppa refuses under the High Priest's orders; Buc must
  fight him for it.
- **Exit:** op-0 grants 0 XP and clears the dialog lock (`$FF0110`),
  then calls `combat_battle_end` (`$03599C`) because `w4=1`.

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 5 is `$1A4C0` (dispatch table `$02D480`, base `$02D4A4`).
The only in-game caller is `$02A188`, inside `npc_attitude_positive`
(`$0298D2`): it pushes a local `-$6(a6) & 0xFFF` as the case — the local
is the out-param of a `$32D4C` text/menu call, i.e. the player's
TALK-dialog menu choice. So the entry is: **TALK to Yoppa, pick the
menu option that yields case 5**.

The entry record is `$D3102` index 468 (12 bytes, verbatim
`00 0A 00 6B 00 00 91 6F 40 05 F0 00`): kind 10, identity 107
(`0x6B`), `w8=0x4005`, `w10=0xF000`. How it is found:
`npc_attitude_positive` calls `shop_record_score` (`$0331A4`), which
scans the `$D3102` table (1005 records × 12 bytes) scoring `+0x10000`
if record+0 == kind and `+0x4000` if record+2 == the talked-to char's
`+0x02`, plus `RNG(0x400)` jitter; the best index wins. The out struct
gets out+0 = record+8, out+2 = record+10, out+4 = best index. The
first dispatch (table `$029F8A`) runs on the top nibble of record+10
(`0xF000` → nibble 15, falls through to `$029FBA`); the second dispatch
(table `$02A1EE`) runs on the top nibble of record+8 (`0x4005` →
nibble 4 → `$02A17C` → `menu_select_screen` with case = `0x4005 &
0xFFF` = 5). Kind 10 is NPC-menu option 10 (the `$022xxx` menu
dispatch, `$0220AA`: option 10 yields kind 10 when bit 0 of `$FF02A2`
is clear, kind 12 when set).

Other same-case records ruled out as entries (their `w8` top nibble
is not 4, so the second dispatch never reaches `menu_select_screen`):
index 209 (`0xB005`/`0x3000`, kind 10, identity 133), index 210
(`0x1005`/`0xF000`, kind 22, identity 2175), indices 834/837
(`0x9005`/`0xF000`, kinds 24/41, identity 0).

The greeting the player hears on entry is text 564 (record 468+96),
from `disasm/text/records_ddbd8.txt`:

- **564:** "So Buc, you have tracked me here. I assume you are after
  the Ring of Will."

## 2. Script table

Verbatim ROM bytes, `$1A4C0`–`$1A4E8`. `w4` is the record's word at
+4, `w6` the word at +6, `b1`/`b2`/`b3` the bytes at +1/+2/+3. Opcode
is `abs(byte0)`; a negative `byte0` means "run the next record
immediately", a non-negative `byte0` pauses until the next engine tick
— and for op-6, until the player dismisses the displayed message with
a button press (`$FF010A` reads 0 while a message is on screen; the
engine resumes when it is dismissed).

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A4C0` | `06 00 00 00 01 D5 00 00` | +6 | Enqueue text 565 (Buc, `w6=0`). Pauses. |
| `$1A4C8` | `06 00 00 00 01 D6 00 C1` | +6 | Enqueue text 566 (Yoppa, `w6=193`). Pauses. |
| `$1A4D0` | `06 00 00 00 01 D7 00 00` | +6 | Enqueue text 567 (Buc, `w6=0`). Pauses. |
| `$1A4D8` | `06 00 00 00 01 D8 00 C1` | +6 | Enqueue text 568 (Yoppa, `w6=193`). Pauses. |
| `$1A4E0` | `00 00 00 00 00 01 00 00` | 0 | Grant 0 XP; clear `$FF0110`; `w4=1` → `combat_battle_end`. |

`$1A4E8` begins the next script (`menu_select_screen` case 6).

### Opcode handlers used here (dispatch `$02DBB8`, base `$02DBE8`)

- op 0 → `$02D5D4`: loops the party list `$FF0E82`, calls
  `inv_apply_resource` (`$02BBD2`) `(member, 0x401, w6, 1)` per
  member — quotient `0x401` = major 16, minor 1 → `xp_grant`
  (`$02C4E2`), +`w6` XP (0 here) — then clears `$FF0110`. **If
  `w4 != 0`, it then calls `combat_battle_end` (`$03599C`) with
  (leader, `char[leader]+0x29` byte), skipped if that byte is `$FF`.
  `combat_battle_end` plays song 20 first, then branches on both
  groups alive to `npc_attitude_positive` (event `0x36`=54),
  `world_location_transition` (`$01DA6C`), or combat-flag cleanup.
- op 6 → `$02D964`: resolve the speaker (below), call
  `text_event_resolve(3, 11, w4)` → displayed text record `w4+96`
  in `$FFBB86`, enqueue it via `text_enqueue_message`. `b1=0` in
  all four records here, so no message is consumed immediately; the
  player dismisses each line with a button press.

`sys_event_run` (`$02D56A`) runs one record per call from `$FFC384`
(gated by `combat_turn_run`, `$0226BC`: `$FF0110 != 0` and grid+`$A`
(`$FFB0B6`) == 0); after each handler `L02DBEA` adds 8 to `$FFC384`
and returns unless `byte0` was negative (chain).

## 3. Actors

- **Yoppa** (name index 143) — identity 107 (`0x6B`). His whole
  `$D3102` tree is five records: index 468 (kind 10, the entry,
  greeting 564) and indices 469–472 (kind 3, the four script lines
  565–568). The entry NPC *is* one of the script speakers — he
  speaks the greeting and lines 566/568.
- **Buc** (name index 57) — the party leader; speaks lines 565/567.

Speaker ids are **per-scene**: op-6 resolves `w6` with
`npc_attitude_raise_by_id` (`$02D50C`), which scans for a type-1 char
whose `+0x02` equals the id and returns the attitude byte at
`char[that char's +0x14].+0x26`; the speaker picture byte passed to
`text_enqueue_message` is `char[result].+0x16` (read at `$FF02CA +
result*52`). If `w6==0xFF` the speaker is `b3`; if the id is not found
it returns `$FF` and the handler reads a garbage byte at `$FF02CA +
0xFF*0x34` = `$FF3E96` — a harmless byte read, no crash.
`w6=0` resolves to Buc wherever the leader's `+0x14` link points at
Buc (slot_0-calibrated: leader char 0 has `+0x14=1` →
`char[1].+0x26` = 1 → Buc). `w6=193` is Yoppa's scaffold id in *this*
scene's char setup. Neither 193 nor the Buc link was observed live in
this scene's own setup — 193 does not resolve in `slot_0`'s char
setup (no char there has `+0x02` = 193) — so the speaker attribution
is static reasoning from the entry tree and the line content, while
the text-resolution mechanism is live-proven on the sibling scenes
(§9).

Why identity 107 is Yoppa: he speaks the greeting ("So Buc, you have
tracked me here. I assume you are after the Ring of Will.") and the
refusal ("I wish I could, but I am under orders from the High Priest
to deliver the Ring to the Temple."), and Darius's account confirms
the quest — text 670: "Poor old Yoppa went to all that trouble to
find the Ring of Will and bring it back to the Cathedral. But you also
took his Ring."

One asymmetry to note: the entry identity (107) and the speaker id
(193) differ here — unlike Imino (2289 − `0x800` = 241 = `w6`) and
Darius (2472 − `0x800` = 424 = `w6`), where entry scoring and speaker
resolution converge on the same `+0x02` value. Identity 107 is below
`0x800`, so `shop_record_score` matches it directly against the
talked-to char's `+0x02` (small path, `$0332A8`); the speaker `w6=193`
is a separate per-scene scaffold id whose type-1 char links (`+0x14`)
to Yoppa. The Yoppa attribution therefore rests on the tree + the
line content (the entry NPC speaks the greeting and two of the four
lines; the `w6=193` lines are Yoppa's first-person refusal), not on
converging arithmetic.

## 4. Dialog (verbatim)

From `disasm/text/records_ddbd8.txt`, displayed records (`w4+96`).

- **565** (`$1A4C0`, `w4=469`, Buc): "I am afraid so Yoppa. Give it
  to me and we will avoid a fight."
- **566** (`$1A4C8`, `w4=470`, Yoppa): "I wish I could, but I am
  under orders from the High Priest to deliver the Ring to the
  Temple."
- **567** (`$1A4D0`, `w4=471`, Buc): "The Temple is not all powerful,
  Yoppa. There are other forces in the universe. I must have that
  Ring."
- **568** (`$1A4D8`, `w4=472`, Yoppa): "Then I am afraid you must
  fight me for it..."

The story: Yoppa found the Ring of Will and is carrying it back to
the Cathedral for the Temple. Buc intercepts him and demands it.
Yoppa refuses under orders; Buc invokes "other forces in the
universe"; Yoppa answers with a fight.

## 5. Effects

None in the script: no moves, spawns, poses, or SFX records. The
only state change the script itself makes is the op-0 exit (§6).

## 6. Exit

Op-0 (`$1A4E0`, handler `$02D5D4`): 0 XP to each party member
(`w6=0`), clears `$FF0110` (dialog unlock), and because `w4=1` calls
`combat_battle_end` (`$03599C`). What `combat_battle_end` does in this
context — which branch it takes in this scene's setup, and what
`char[leader]+0x29` is there — is open (§10). The closing line ("you
must fight me for it...") reads as the lead-in to a fight; whether
the battle-end call transitions into one or merely cleans up the TALK
encounter state is not established.

## 7. Camera

No camera records: no op-1 teleport, no op-5 moves. The camera stays
where the entry TALK left it; the scene plays in place.

## 8. Location

Not pinned. Yoppa was "bringing it back to the Cathedral" (text 670),
so the confrontation is somewhere on his route — but no dialog line
and no traced table names the room. The `$D1D00` location table (455
records × 10 B, +4 byte = location number) is dumped at
`.scratch-cutscenes/case2-3-5-7/d1d00_dump.txt` for the follow-up;
pinning the site needs Yoppa's char setup / spawn location, which was
not traced.

## 9. Live-proven vs static-only

**Live-proven (mechanism only):** the op-6 `+$60` text resolution and
the pause-until-dismissed engine behavior were proven live on the
sibling scenes with the identical code path — case 2 (probe
`probe_case2`, `cut_log_case2_v2.txt`: `w4=366/367` displayed texts
462/463) and case 7 (probe `probe_case7`, `cut_log_case7.txt`:
`w4=571–583` displayed texts 667–679), both in
`.scratch-cutscenes/case2-3-5-7/`. No case-5 probe was run: it would
only re-confirm the same handler for four more lines, and the
speakers (0 → Buc, 193 → Yoppa) are the same in kind as the proven
cases. A case-5 probe (arm `$FFC384=$1A4C0`, freeze at `$1A4E8`) is a
cheap follow-up if the lead wants this scene's own log.

**Static-only** (verified verbatim against ROM bytes / `rop.s`, not
run live): this scene's entry record and dispatch; the speaker
attribution (`w6=0` → Buc, `w6=193` → Yoppa — 193 does not resolve in
`slot_0`, so no live portrait/speaker byte was observed); the op-0
`combat_battle_end` call and what it does here; the location.

## 10. Open items

- The confrontation site / location number (and Yoppa's char-slot
  setup there — which slot carries `+0x02` = 193).
- What `combat_battle_end` does after the op-0 with `w4=1` in this
  context — fight transition or encounter cleanup — and the value of
  `char[leader]+0x29` in this scene's setup.
- Which TALK-verb call site yields kind 10 (the menu option text for
  option 10 for Yoppa needs the `$32D4C` menu-table trace).
- Optional follow-up: a case-5 probe (same shape as the case-2/7
  probes) for this scene's own live log.
