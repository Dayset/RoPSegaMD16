# The Imino cutscene — the Ring of Advancing in Richi

The scripted scene in which Buc meets Imino in Richi, and Imino — who
found the Ring of Advancing on Old Richi's body — challenges Buc to take
it from him. Two lines of dialog and an exit grant; no moves, no spawns,
no poses, no SFX. Documented here as part of the RE spec for the tribute
remake (M7).

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
is **text record N+96**. This is live-proven for this scene (§9):
`w4=366` displayed text 462, `w4=367` displayed text 463. The earlier
reading of these scripts (texts 366–367, Haze and the Ideal Door) is
wrong — those lines are dialog records 270–271 of another NPC, not
this scene's dialog.

## At a glance

- **Script:** ROM `$1A398`–`$1A3B0`, 3 records, 8 bytes each, opcode =
  `abs(byte0)`, negative `byte0` chains to the next record,
  non-negative `byte0` pauses. Pointer `$FFC384`, engine
  `sys_event_run` (`$02D56A`).
- **Location:** Richi (from the dialog; exact room/location number
  open, §8).
- **Entry:** TALK to Imino, pick the menu option that yields case 2 in
  `menu_select_screen` (`$02D3DC`).
- **The scene:** two lines, both Imino. He has the Ring of Advancing;
  Buc must fight him for it.
- **Exit:** op-0 grants 0 XP and clears the dialog lock (`$FF0110`),
  then calls `combat_battle_end` (`$03599C`) because `w4=1`.

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 2 is `$1A398` (dispatch table `$02D480`, base `$02D4A4`).
The only in-game caller is `$02A188`, inside `npc_attitude_positive`
(`$0298D2`): it pushes a local `-$6(a6) & 0xFFF` as the case — the local
is the out-param of a `$32D4C` text/menu call, i.e. the player's
TALK-dialog menu choice. So the entry is: **TALK to Imino, pick the
menu option that yields case 2**.

The entry record is `$D3102` index 365 (12 bytes, verbatim
`00 0A 08 F1 00 00 91 6F 40 02 F0 00`): kind 10, identity 2289
(`0x8F1`), `w8=0x4002`, `w10=0xF000`. How it is found:
`npc_attitude_positive` calls `shop_record_score` (`$0331A4`), which
scans the `$D3102` table (1005 records × 12 bytes) scoring `+0x10000`
if record+0 == kind and `+0x4000` if record+2 == the talked-to char's
`+0x02`, plus `RNG(0x400)` jitter; the best index wins. The out struct
gets out+0 = record+8, out+2 = record+10, out+4 = best index. The
first dispatch (table `$029F8A`) runs on the top nibble of record+10
(`0xF000` → nibble 15, falls through to `$029FBA`); the second dispatch
(table `$02A1EE`) runs on the top nibble of record+8 (`0x4002` →
nibble 4 → `$02A17C` → `menu_select_screen` with case = `0x4002 &
0xFFF` = 2). Kind 10 is NPC-menu option 10 (the `$022xxx` menu
dispatch, `$0220AA`: option 10 yields kind 10 when bit 0 of `$FF02A2`
is clear, kind 12 when set).

The greeting the player hears on entry is text 461 (record 365+96),
from `disasm/text/records_ddbd8.txt`:

- **461:** "Hello Buc. Fancy meeting you here!"

## 2. Script table

Verbatim ROM bytes, `$1A398`–`$1A3B0`. `w4` is the record's word at
+4, `w6` the word at +6, `b1`/`b2`/`b3` the bytes at +1/+2/+3. Opcode
is `abs(byte0)`; a negative `byte0` means "run the next record
immediately", a non-negative `byte0` pauses until the next engine tick
— and for op-6, until the player dismisses the displayed message with
a button press (`$FF010A` reads 0 while a message is on screen; the
engine resumes when it is dismissed).

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A398` | `06 00 00 00 01 6E 00 F1` | +6 | Enqueue text 462 (Imino, `w6=241`). Pauses. |
| `$1A3A0` | `06 00 00 00 01 6F 00 F1` | +6 | Enqueue text 463 (Imino, `w6=241`). Pauses. |
| `$1A3A8` | `00 00 00 00 00 01 00 00` | 0 | Grant 0 XP; clear `$FF0110`; `w4=1` → `combat_battle_end`. |

`$1A3B0` begins the next script (`menu_select_screen` case 3).

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
  both records here, so no message is consumed immediately; the
  player dismisses each line with a button press.

`sys_event_run` (`$02D56A`) runs one record per call from `$FFC384`
(gated by `combat_turn_run`, `$0226BC`: `$FF0110 != 0` and grid+`$A`
(`$FFB0B6`) == 0); after each handler `L02DBEA` adds 8 to `$FFC384`
and returns unless `byte0` was negative (chain).

## 3. Actors

- **Imino** (name index 142) — identity 2289 (`0x8F1`). His whole
  `$D3102` tree is three records: index 365 (kind 10, the entry,
  greeting 461) and indices 366–367 (kind 3, the two script lines
  462–463). The entry NPC *is* the script speaker.
- **Buc** (name index 57) — the party leader; addressed, does not
  speak in this scene.

Speaker ids are **per-scene**: op-6 resolves `w6` with
`npc_attitude_raise_by_id` (`$02D50C`), which scans for a type-1 char
whose `+0x02` equals the id and returns the attitude byte at
`char[that char's +0x14].+0x26`; the speaker picture byte passed to
`text_enqueue_message` is `char[result].+0x16` (read at `$FF02CA +
result*52`). If `w6==0xFF` the speaker is `b3`; if the id is not found
it returns `$FF` and the handler reads a garbage byte at `$FF02CA +
0xFF*0x34` = `$FF3E96` — a harmless byte read, no crash. Speaker
`w6=241` is Imino's scaffold id in *this* scene's char setup (in the
Buc scene at location 156, Imino's scaffold id was 5 — do not carry
that mapping over). It does **not** resolve in `slot_0`'s char setup
(no char there has `+0x02` = 241), so the speaker attribution below
is static reasoning from the entry tree and the line content, while
the text itself is live-proven (§9).

Why identity 2289 is Imino: Darius's own account, text 669 — "Imino
managed to find the Ring of Advancing, but of course you took that
from him in Richi." — and the Richi lore lines: text 444, "My
ancestor, the first Richi King, was said to have had the Ring of
Advancing. His crypt is below the south east tower."; text 897, "The
legend holds that the first King Richi was given the Ring of
Advancement by Nexus himself, but I don't believe it." The speaker pin
is arithmetic as well as content: `shop_record_score` (`$0331A4`)
matches `$D3102` identities at or above `0x800` as record identity −
`0x800` == the talked-to char's `+0x02` (large path, `$033264`–
`$0332A0`), and 2289 − `0x800` = **241** — the script's speaker `w6`.
Entry scoring and speaker resolution converge on the same `+0x02`
value.

## 4. Dialog (verbatim)

From `disasm/text/records_ddbd8.txt`, displayed records (`w4+96`).
Both lines Imino, speaker id 241.

- **462** (`$1A398`, `w4=366`): "It seems that the Ring was real
  after all. Old Richi had it on him all the time!"
- **463** (`$1A3A0`, `w4=367`): "I hate to do this Buc, but if you
  want this Ring you're going to have to take it from me."

The story: the Ring was real; Old Richi — the first Richi King, whose
crypt is below the south east tower — had it on him. Imino found it
and now holds it. Buc must fight him for it.

## 5. Effects

None in the script: no moves, spawns, poses, or SFX records. The
only state change the script itself makes is the op-0 exit (§6).

## 6. Exit

Op-0 (`$1A3A8`, handler `$02D5D4`): 0 XP to each party member
(`w6=0`), clears `$FF0110` (dialog unlock), and because `w4=1` calls
`combat_battle_end` (`$03599C`). What `combat_battle_end` does in this
context — which branch it takes in the Richi setup, and what
`char[leader]+0x29` is there — is open (§10). The challenge line
("take it from me") reads as the lead-in to a fight; whether the
battle-end call transitions into one or merely cleans up the TALK
encounter state is not established.

## 7. Camera

No camera records: no op-1 teleport, no op-5 moves. The camera stays
where the entry TALK left it; the scene plays in place.

## 8. Location

Richi. The location is identified from the dialog (text 669: "you
took that from him in Richi"; text 444: the first Richi King's crypt
below the south east tower). The exact Richi room / location number
(`$D1D00` record) is open (§8) — the `$D1D00` table (455 records ×
10 B, +4 byte = location number) is dumped at
`.scratch-cutscenes/case2-3-5-7/d1d00_dump.txt` for the follow-up.

## 9. Live-proven vs static-only

**Live-proven** (BlastEm harness, `slot_0` state, probe `probe_case2`
in `.scratch-cutscenes/case2-3-5-7/`; VBlank hook at `$1272`, arm
`$FFC384=$1A398, $FF0110=$FFFF, $FF010A=2, $FFA7FA=0`, freeze when
`$FFC384` reaches `$1A3A8` before op-0 runs):

- The +$60 mechanism, both lines. Freeze record (frame `0x0A35`,
  `cut_log_case2_v2.txt`): `$FFC384=$1A3A8`, `$FF0110=0` (frozen by
  the probe), `$FFBB86` = "I hate to do this Buc, but if you want
  this Ring you're going to" — text **463**, not 367. Intermediate
  records (frames `0x09EC`–`0x0A32`, `$FFC384=$1A3A0`) show
  `$FFBB86` = "It seems that the Ring was real after all. Old Richi
  had it on h" — text **462**, not 366.
- The pause-until-dismissed behavior: the first probe run
  (`cut_log_case2_v1.txt`, no pad injector) stalled at `$1A3A0` for
  the full 1200-frame timeout — `$FF010A` went 2→0 while the first
  message sat undismissed, and record 2 never ran. The v2 run adds
  probe_e's A/B/C pad rotation to dismiss each message; the engine
  then advances through both lines and freezes in ~90 frames.

**Static-only** (verified verbatim against ROM bytes / `rop.s`, not
run live): the entry record and its dispatch (kind 10 = menu option
10); the speaker attribution (`w6=241` → Imino — 241 does not resolve
in `slot_0`, so no live portrait/speaker byte was observed); the
op-0 `combat_battle_end` call and what it does in the Richi setup;
the location number.

## 10. Open items

- Exact Richi room / location number, and Imino's char-slot setup
  there (which slot carries `+0x02` = 241).
- What `combat_battle_end` does after the op-0 with `w4=1` in this
  context — fight transition or encounter cleanup — and the value of
  `char[leader]+0x29` in the Richi setup.
- Which TALK-verb call site yields kind 10 (the menu option text
  for option 10 for Imino needs the `$32D4C` menu-table trace).
