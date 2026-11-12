# Darius's endgame monologue — all eleven Rings

The scripted scene in which Buc finally catches up with Darius, and
Darius explains the whole game: he sat back in Kaos while Buc and the
four other students did the work of finding the Rings of Power, and
now Buc has brought all eleven of them to him. Thirteen lines of
dialog — eleven Darius, two Buc — and an exit grant; no moves, no
spawns, no poses, no SFX. The longest pure-dialog scene in the
`menu_select_screen` set. Documented here as part of the RE spec for
the tribute remake (M7).

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
is **text record N+96**. This is live-proven for this scene, all
thirteen lines (§9). The earlier reading of this scene (texts 571–583,
honey, Fen Ho, the Protectors, the talking bear) is wrong — those
lines are dialog records 475–487 of the Fen Ho / Protectors NPCs, not
this scene's dialog.

## At a glance

- **Script:** ROM `$1A520`–`$1A590`, 14 records, 8 bytes each, opcode
  = `abs(byte0)`, negative `byte0` chains to the next record,
  non-negative `byte0` pauses. Pointer `$FFC384`, engine
  `sys_event_run` (`$02D56A`).
- **Location:** Kaos (from the dialog; exact location number open,
  §8).
- **Entry:** TALK to Darius, pick the menu option that yields case 7
  in `menu_select_screen` (`$02D3DC`).
- **The scene:** Darius's monologue. He recounts what each of the
  five students did with their Ring quest — Imino, Yoppa, Fezzik,
  Roakus, and Buc himself — thanks Buc for bringing him all eleven
  Rings, and reveals VOID.
- **Exit:** op-0 grants 0 XP and clears the dialog lock (`$FF0110`),
  then calls `combat_battle_end` (`$03599C`) because `w4=1`.

## 1. Entry

`menu_select_screen` (`$02D3DC`) sets `$FFC384` to one of ten script
pointers; case 7 is `$1A520` (dispatch table `$02D480`, base `$02D4A4`).
The only in-game caller is `$02A188`, inside `npc_attitude_positive`
(`$0298D2`): it pushes a local `-$6(a6) & 0xFFF` as the case — the local
is the out-param of a `$32D4C` text/menu call, i.e. the player's
TALK-dialog menu choice. So the entry is: **TALK to Darius, pick the
menu option that yields case 7**.

The entry record is `$D3102` index 570 (12 bytes, verbatim
`00 0A 09 A8 00 00 91 6F 40 07 F0 00`): kind 10, identity 2472
(`0x9A8`), `w8=0x4007`, `w10=0xF000`. How it is found:
`npc_attitude_positive` calls `shop_record_score` (`$0331A4`), which
scans the `$D3102` table (1005 records × 12 bytes) scoring `+0x10000`
if record+0 == kind and `+0x4000` if record+2 == the talked-to char's
`+0x02`, plus `RNG(0x400)` jitter; the best index wins. The out struct
gets out+0 = record+8, out+2 = record+10, out+4 = best index. The
first dispatch (table `$029F8A`) runs on the top nibble of record+10
(`0xF000` → nibble 15, falls through to `$029FBA`); the second dispatch
(table `$02A1EE`) runs on the top nibble of record+8 (`0x4007` →
nibble 4 → `$02A17C` → `menu_select_screen` with case = `0x4007 &
0xFFF` = 7). Kind 10 is NPC-menu option 10 (the `$022xxx` menu
dispatch, `$0220AA`: option 10 yields kind 10 when bit 0 of `$FF02A2`
is clear, kind 12 when set).

The greeting the player hears on entry is text 666 (record 570+96),
from `disasm/text/records_ddbd8.txt`:

- **666:** "Why hello there Buc, I've been waiting for you. You see,
  It all came to me just after our master zapped me to some random
  location in the artic."

"Our master zapped me to some random location" is Thalmus's
dying-word scatter: text 218, "Your master's dying word forces itself
into the mind of all present, scattering them across the globe."

### How 666 is delivered (before the menu)

666 is the entry greeting, displayed by the TALK path *before* the
menu appears — it is not in the script (the script covers 667–679).
`npc_attitude_positive` (`$0298D2`) first resolves and displays the
greeting, then runs the dispatches, then the menu:

1. At `$029990` it calls `text_event_resolve` (`$032D4C`) with the
   TALK kind (10) and the talked-to char's `+0x02` identity (424).
   The kind byte (10, not 11) takes the non-11 path (`$032E00`),
   dispatching on arg1=3 via table `$032E92` to `$032E3A`, which calls
   `shop_record_score` (`$0331A4`). The scorer scans `$D3102` and
   picks index 570 (kind match +`0x10000`, identity match +`0x4000`
   — the large-identity path: record identity 2472 − `0x800` = 424
   == the char's `+0x02`).
2. `shop_record_score` returns the best index **+96** (`add.w #$60`
   at `$03373C`): 570 + 96 = **666**. The `text_event_resolve` tail
   (`$032EB0`) fetches text record 666 via `text_record_dispatch`
   (`$013654`) into `$FFBB86`, and `npc_attitude_positive` enqueues
   it (`text_enqueue_message`, `$029A18`). The player reads the
   greeting.
3. Only then do the first dispatch (table `$029F8A`, on record+10)
   and second dispatch (`$029FBA`, table `$02A1EE`, on record+8)
   run; the second dispatch reaches `menu_select_screen`, the player
   picks the option, and case 7's script runs (667–679).

So the full Darius sequence is: TALK → greeting 666 → menu →
monologue 667–679 → op-0 exit. The final-animation doc's "Darius
range 666–680" is this greeting (666) plus this script (667–679)
plus the bark in §4 below (680) — three different delivery paths,
not one script.

## 2. Script table

Verbatim ROM bytes, `$1A520`–`$1A590`. `w4` is the record's word at
+4, `w6` the word at +6, `b1`/`b2`/`b3` the bytes at +1/+2/+3. Opcode
is `abs(byte0)`; a negative `byte0` means "run the next record
immediately", a non-negative `byte0` pauses until the next engine tick
— and for op-6, until the player dismisses the displayed message with
a button press (`$FF010A` reads 0 while a message is on screen; the
engine resumes when it is dismissed).

| addr | bytes | op | meaning |
|---|---|---|---|
| `$1A520` | `06 00 00 00 02 3B 01 A8` | +6 | Enqueue text 667 (Darius, `w6=424`). Pauses. |
| `$1A528` | `06 00 00 00 02 3C 01 A8` | +6 | Enqueue text 668 (Darius). Pauses. |
| `$1A530` | `06 00 00 00 02 3D 01 A8` | +6 | Enqueue text 669 (Darius). Pauses. |
| `$1A538` | `06 00 00 00 02 3E 01 A8` | +6 | Enqueue text 670 (Darius). Pauses. |
| `$1A540` | `06 00 00 00 02 3F 01 A8` | +6 | Enqueue text 671 (Darius). Pauses. |
| `$1A548` | `06 00 00 00 02 40 01 A8` | +6 | Enqueue text 672 (Darius). Pauses. |
| `$1A550` | `06 00 00 00 02 41 01 A8` | +6 | Enqueue text 673 (Darius). Pauses. |
| `$1A558` | `06 00 00 00 02 42 01 A8` | +6 | Enqueue text 674 (Darius). Pauses. |
| `$1A560` | `06 00 00 00 02 43 01 A8` | +6 | Enqueue text 675 (Darius). Pauses. |
| `$1A568` | `06 00 00 00 02 44 00 00` | +6 | Enqueue text 676 (Buc, `w6=0`). Pauses. |
| `$1A570` | `06 00 00 00 02 45 00 00` | +6 | Enqueue text 677 (Buc, `w6=0`). Pauses. |
| `$1A578` | `06 00 00 00 02 46 01 A8` | +6 | Enqueue text 678 (Darius). Pauses. |
| `$1A580` | `06 00 00 00 02 47 01 A8` | +6 | Enqueue text 679 (Darius). Pauses. |
| `$1A588` | `00 00 00 00 00 01 00 00` | 0 | Grant 0 XP; clear `$FF0110`; `w4=1` → `combat_battle_end`. |

`$1A590` begins the next script (`menu_select_screen` case 8).

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
  all thirteen records here, so no message is consumed immediately;
  the player dismisses each line with a button press.

`sys_event_run` (`$02D56A`) runs one record per call from `$FFC384`
(gated by `combat_turn_run`, `$0226BC`: `$FF0110 != 0` and grid+`$A`
(`$FFB0B6`) == 0); after each handler `L02DBEA` adds 8 to `$FFC384`
and returns unless `byte0` was negative (chain).

## 3. Actors

- **Darius** (name index 145) — identity 2472 (`0x9A8`). His whole
  `$D3102` tree is fourteen records: index 570 (kind 10, the entry,
  greeting 666) and indices 571–583 (kind 3, the thirteen script
  lines 667–679). The entry NPC *is* the script's main speaker — he
  speaks eleven of the thirteen lines.
- **Buc** (name index 57) — the party leader; two interjections
  (676–677).

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
`char[1].+0x26` = 1 → Buc). `w6=424` is Darius's scaffold id in *this*
scene's char setup (in the Buc scene at location 156, Darius's
scaffold id was 8 — do not carry that mapping over). It does **not**
resolve in `slot_0`'s char setup (no char there has `+0x02` = 424),
so no live portrait/speaker byte was observed for it.

### Pin: w6=424 is Darius (bias arithmetic, not just content)

The pin does not rest on the line content alone. `shop_record_score`
(`$0331A4`) matches `$D3102` identities in two ways: identities
below `0x800` match the talked-to char's `+0x02` directly (small
path, `$0332A8`), while identities at or above `0x800` match as
record identity − `0x800` == the char's `+0x02` (large path,
`$033264`–`$0332A0`; the `+0x800` bit marks non-merchant/story
identities). Darius's entry record carries identity **2472**, and
2472 − `0x800` = **424** — the talked-to char's `+0x02`. The script's
speaker id `w6=424` is that same value, so `npc_attitude_raise_by_id`
(424) resolves through the type-1 scaffold (whose `+0x14` links to
Darius, whose `+0x26` gives Darius's char index) to the same char the
entry matched. Two independent paths — entry scoring and speaker
resolution — converge on the same `+0x02` value, 424, and the only
char in the scene with that identity is Darius (greeting content +
tree). The same arithmetic pins Imino in case 2 (2289 − `0x800` =
241 = the script's `w6`), and the Buc scene's own live-proven
mapping shows the scaffold pattern working (speaker 1 → Thalmus via
the Davin scaffold, speaker 5 → Imino via the Opul scaffold).
Corroborating content: the monologue is first-person throughout —
"I have been living it up at Kaos", "my friend Fezzik", "you have
brought them here to me" — and Buc addresses the speaker as Darius
by name in 676 ("But Darius, you have made one fatal mistake…").

## 4. Dialog (verbatim)

From `disasm/text/records_ddbd8.txt`, displayed records (`w4+96`).
ROM spellings kept ("retreive", "sleave", "artic", "for past few
months", "And now.." with two dots).

- **667** (`$1A520`, `w4=571`, Darius): "The best way to get the
  Rings of Power was to sit back and let everyone else do all the
  work. Then when you showed up here I would retreive them."
- **668** (`$1A528`, `w4=572`, Darius): "So I have been living it up
  at Kaos for past few months, while you, and the four other suckers
  ran around the world finding my Rings for me."
- **669** (`$1A530`, `w4=573`, Darius): "Imino managed to find the
  Ring of Advancing, but of course you took that from him in Richi."
- **670** (`$1A538`, `w4=574`, Darius): "Poor old Yoppa went to all
  that trouble to find the Ring of Will and bring it back to the
  Cathedral. But you also took his Ring."
- **671** (`$1A540`, `w4=575`, Darius): "Now my friend Fezzik, I told
  him to wait in the Chamber of Perfection, and sure enough you came
  along with the gems. Too bad you had to kill him."
- **672** (`$1A548`, `w4=576`, Darius): "Roakus, on the other hand,
  was a surprise failure. He didn't manage to get a single Ring. But
  instead, he spent his time lounging in the Lobotomy Club."
- **673** (`$1A550`, `w4=577`, Darius): "I don't know what Master
  Thalmus saw in him."
- **674** (`$1A558`, `w4=578`, Darius): "You on the other hand, were
  an unprecedented success. You managed to secure all eleven of the
  Rings. And now.. you have brought them here to me."
- **675** (`$1A560`, `w4=579`, Darius): "Thank you."
- **676** (`$1A568`, `w4=580`, Buc): "But Darius, you have made one
  fatal mistake. For I, in obtaining the Rings, also learned of their
  powers and can now use them against you."
- **677** (`$1A570`, `w4=581`, Buc): "Allied with Nexus, this is not
  a power that even you can overcome."
- **678** (`$1A578`, `w4=582`, Darius): "No, Buc, it is you who have
  made the tactical blunder. For I have a secret up my sleave, which
  I shall be happy to tell you..."
- **679** (`$1A580`, `w4=583`, Darius): "VOID! And the spells he has
  crafted for your destruction. Give my regards to the rest of the
  gang when you meet them: In the dead lands..."

### Record 680: "Die Sssorcerer sscum!" — not in the script

Text 680 is adjacent to the monologue but is **not** part of it: the
script covers `w4` 571–583 → texts 667–679, and 680 is `$D3102`
index 584, outside Darius's tree (indices 570–583). It is a different
record on a different delivery path:

- The record (verbatim `00 0A 00 00 25 00 00 91 F0 00 B0 05`):
  kind 10, identity **0**, `w8=0xF000`, `w10=0xB005`.
- **Delivery:** the same TALK greeting path as 666, *if* it wins the
  scoring. `npc_attitude_positive` calls `text_event_resolve` →
  `shop_record_score` returns best + 96 (`$03373C`), so a win for
  index 584 displays text 584 + 96 = **680** via
  `text_enqueue_message`. Then the first dispatch (table `$029F8A`)
  runs on the top nibble of record+10 (`0xB005` → nibble 11 →
  `$029C70`), which applies attitude **−5** (`npc_attitude_apply`,
  val = `0xB005 & 0xFFF` = 5, negated). Then the second dispatch
  (`$029FBA`, table `$02A1EE`) runs on the top nibble of record+8
  (`0xF000` → nibble 15) — but the dispatch requires nibble < 14
  (`cmp.l #$e` at `$02A20A`), so it falls through to `$02A1E6` and
  does nothing: **no menu, no cutscene, no script**.
- So 680 is a hostile TALK bark — the player sees "Die Sssorcerer
  sscum!" and the NPC's attitude drops by 5 — not a line of the
  monologue and not a fight cue inside case 7.
- **Who says it is open.** Identity 0 earns no identity bonus in
  `shop_record_score`, so the record can only win for a talked-to
  char that has no identity-matching kind-10 record, gated by the
  +4/+5/+6 match keys (+4 byte `0x25`, +5 `0x00`, +6 `0x00`) against
  per-char state — the exact trigger NPC was not pinned. The "Sss"
  hissing spelling marks a serpentine / VOID-aligned speaker, not
  Darius (who speaks plainly in 666–679). It is also *not* delivered
  by the op-0's `combat_battle_end` path: that path calls
  `npc_attitude_positive` with kind 54, and kind 10 does not match
  kind 54. The final-animation doc's "Darius range 666–680" therefore
  spans three delivery paths — greeting 666, script 667–679, bark
  680 — and `sys_event_run` *is* the driver of the middle one (this
  script runs under `sys_event_run` from `$FFC384`).

The story, in order: Darius's plan was to let the other four students
do the work. Imino found the Ring of Advancing (taken from him in
Richi — the case-2 scene); Yoppa found the Ring of Will (taken from
him — the case-5 scene); Fezzik waited in the Chamber of Perfection
and was killed by Buc; Roakus found nothing and lounged in the
Lobotomy Club. Buc, "an unprecedented success", secured all eleven
Rings and brought them to Darius. Buc claims the Rings' powers plus
Nexus as his edge; Darius answers that his secret is VOID, "and the
spells he has crafted for your destruction".

## 5. Effects

None in the script: no moves, spawns, poses, or SFX records. The
only state change the script itself makes is the op-0 exit (§6).

## 6. Exit

Op-0 (`$1A588`, handler `$02D5D4`): 0 XP to each party member
(`w6=0`), clears `$FF0110` (dialog unlock), and because `w4=1` calls
`combat_battle_end` (`$03599C`). What `combat_battle_end` does in this
context — which branch it takes in the Kaos setup, and what
`char[leader]+0x29` is there — is open (§10). The closing line (VOID,
"the spells he has crafted for your destruction") reads as the
lead-in to the endgame fight; whether the battle-end call transitions
into one or merely cleans up the TALK encounter state is not
established.

## 7. Camera

No camera records: no op-1 teleport, no op-5 moves. The camera stays
where the entry TALK left it; the scene plays in place.

## 8. Location

Kaos. Text 668: "I have been living it up at Kaos for past few
months". Corroborated by text 128, "Welcome to Kaos, population 50
(subject to change without notice).", and text 54, "This impressive
structure is the Tower of Kaos." The exact Kaos location number
(`$D1D00` record) is open (§8) — the `$D1D00` table (455 records ×
10 B, +4 byte = location number) is dumped at
`.scratch-cutscenes/case2-3-5-7/d1d00_dump.txt` for the follow-up.

## 9. Live-proven vs static-only

**Live-proven** (BlastEm harness, `slot_0` state, probe `probe_case7`
in `.scratch-cutscenes/case2-3-5-7/`; VBlank hook at `$1272`, arm
`$FFC384=$1A520, $FF0110=$FFFF, $FF010A=2, $FFA7FA=0`, A/B/C pad
rotation to dismiss each message, freeze when `$FFC384` reaches
`$1A588` before op-0 runs) — **all thirteen lines**, in order
(`cut_log_case7.txt`):

- 667 "The best way to get the Rings of Power was to sit back and
  let e…", 668 "So I have been living it up at Kaos for past few
  months, while y…", 669 "Imino managed to find the Ring of
  Advancing, but of course you t…", 670 "Poor old Yoppa went to all
  that trouble to find the Ring of Will…", 671 "Now my friend Fezzik,
  I told him to wait in the Chamber of Perfe…", 672 "Roakus, on the
  other hand, was a surprise failure. He didn't man…", 673 "I don't
  know what Master Thalmus saw in him. ", 674 "You on the other hand,
  were an unprecedented success. You manage…", 675 "Thank you. ",
  676 "But Darius, you have made one fatal mistake. For I, in
  obtaining…", 677 "Allied with Nexus, this is not a power that even
  you can overcom…", 678 "No, Buc, it is you who have made the
  tactical blunder. For I hav…", 679 "VOID! And the spells he has
  crafted for your destruction. Give m…" (freeze record, frame
  `0x0DE1`: `$FFC384=$1A588`, `$FF0110=0`, `$FFBB86` = "VOID! And the
  spells he has crafted for your destruction. Give m" — text **679**,
  not 583).

Each `$FFBB86` capture is the first 64 bytes of the resolved line;
the full lines are quoted verbatim from `records_ddbd8.txt` in §4.
Note the first probe run stalled at line 673: the pad injector's
600-frame window expired just as that message appeared (elapsed
~566), the held A predated the message so no fresh press edge
dismissed it, and `$FF010A` stayed 0 to the 1200-frame timeout. The
rerun extends the injector to the full 1200-frame window and
completes in ~1100 frames. Log slots 55–59 in `cut_log_case7.txt`
were never written by the probe (the freeze record is index 54) and
hold stale RAM — fragments of the message buffer — not probe data.

**Static-only** (verified verbatim against ROM bytes / `rop.s`, not
run live): the entry record and its dispatch (kind 10 = menu option
10); the speaker attribution (`w6=424` → Darius, `w6=0` → Buc — 424
does not resolve in `slot_0`, so no live portrait/speaker byte was
observed); the op-0 `combat_battle_end` call and what it does in the
Kaos setup; the location number.

## 10. Open items

- Exact Kaos location number, and Darius's char-slot setup there
  (which slot carries `+0x02` = 424).
- What `combat_battle_end` does after the op-0 with `w4=1` in this
  context — fight transition or encounter cleanup — and the value of
  `char[leader]+0x29` in the Kaos setup.
- Which TALK-verb call site yields kind 10 (the menu option text for
  option 10 for Darius needs the `$32D4C` menu-table trace).
- Record 680's trigger: which char's kind-10 TALK selects `$D3102`
  index 584 (needs the +4/+5/+6 match-key decode — +4 byte `0x25`,
  +5 `0x00`, +6 `0x00` — against per-char state). Mechanism pinned
  (§4); speaker open.
