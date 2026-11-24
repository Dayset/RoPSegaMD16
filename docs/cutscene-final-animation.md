# Cutscene: The Final Animation (game completed, 11 rings found)

> **Status (2026-11-24, issue #275 work): O5 live-proven, O1/O2/O3/O6
> closed statically, O4 partly closed.** The four "missing" ring grants
> (642/643/647/649) were found and live-proven, and the Holy Seal gate
> was live-proven (probes `probe_o5`/`probe_o5b`/`probe_o5c`, §
> Live-proven). The Bandit HQ (O1), the grid-base/`$03B224` check (O2),
> the double-Rashiid spawn (O3, static), and the `$02BA` vessel-mode /
> TALK-repeat questions (O6) are closed statically. O4: the case-7
> invocation path from dialog EXISTS (the issue's "no in-dialog
> invocation" premise was wrong — it rested on a swapped dispatch
> model, corrected below); the fight trigger itself is narrowed to the
> scan-ahead pairing that sets the leader's combat-opponent link
> (`+0x29`), and that pairing is now **live-proven** (probes
> `probe_o4d`/`probe_o4e` — the scan finds a facing type-4 Darius and
> links him; see Live-proven). What is still open is the full
> TALK-to-Darius sequence in real Kaos game state (probe C).
>
> The "final animation" as coded is **not a single dedicated
> routine**: it is a chain — the Darius confrontation at Kaos, the Holy Seal
> gate at the Fount door, a white flash and a painted door tile, and entry
> into the Fount of Heaven interior (room 170). One link of the chain *is* an
> event script — the Darius monologue is `sys_event_run` case 7, `$1A520`
> (see `docs/cutscene-darius-endgame.md`; its dialog is live-proven) — but
> there is **no intro-style picture sequence and no single ending-only
> driver** behind the chain as a whole. The last link — what happens inside
> room 170 — is the least pinned part of the chain; see Open items.
>
> **Correction (2026-11-12, assembly):** an earlier version of this doc
> claimed `sys_event_run` was ruled out as the ending driver because no
> menu script contained texts 666–680. That scan used unshifted op-6 w4
> values. Op-6 displays text **w4 + 96** (`text_event_resolve(3, 11, w4)`
> → `$032D9E` `add.w #$60`), so case 7's w4 571–583 display texts
> 667–679 — the Darius monologue. The 666–680 range spans three delivery
> paths (greeting 666, script 667–679, bark 680); see "The final battle —
> Darius" below.

## At a glance

| | |
|---|---|
| Scene | The ending: 11 rings collected → Holy Seal used at the Fount door → the door opens → Fount of Heaven interior (room 170) |
| Trigger | `USE` the Holy Seal (item code 861) while standing on location 392, with all 11 ring bits set on the leader and event bit 143 clear |
| Gate routine | `$02DD9A` inside `sys_dispatch_action_2dcce` (`$02DCCE`) — the **only** "all 11" check in the ROM |
| Driver | Mixed: the Darius monologue IS a `sys_event_run` script (case 7, `$1A520`); the Holy Seal gate is a branch of the item-USE dispatcher, followed by the normal location-transition system; not `intro_helper`/`snd_music_start` |
| Final battle | vs Darius (spawn 105, name idx 145) — greeting 666 (TALK path) + monologue 667–679 (case-7 script) + bark 680 (hostile TALK), at Kaos per text 668 |
| Door location | Loc 392, key (12, 184), destination room 170, `$FF013E` = 6 (scripted encounter) |
| Room 170 | Fount of Heaven interior, placement (15, 30), song 7; sole placed occupant is Darius (placement template 424, key 392, at (15, 9), gated on event bit 144 — see Room 170) |
| Live-proven | **O5 (2026-11-24):** all four "missing" ring grants live-proven (probe_o5/o5b) and the Holy Seal gate live-proven (probe_o5c). The Darius monologue dialog was live-proven earlier (probe_case7). The rest is static analysis. |

## Entry / trigger

### The 11 rings

The rings are item-category table record 10 (`$D66A0`, 20 records × 10
bytes; record 10 at `$D6707`: `E=2, A=67` gold-ring sprite, `B=0`,
count **11**, cap 1, name_idx 147, `w=125`). Price table `$D6768`,
257 records × 4 bytes; rings are price records **125–135**:

| Code | Price rec | Name (as spelled in ROM) | Raw value |
|---|---|---|---|
| 640 | 125 | Will | 99 |
| 641 | 126 | Thought | 125 |
| 642 | 127 | Intuitin | 157 |
| 643 | 128 | Division | 196 |
| 644 | 129 | Advance | 245 |
| 645 | 130 | Blood | 307 |
| 646 | 131 | Bile | 384 |
| 647 | 132 | Mutation | 415 |
| 648 | 133 | Variatin | 415 |
| 649 | 134 | Calling | 415 |
| 650 | 135 | Perfctin | 415 |

Grant code = category × 64 + index, so rings are codes **640–650**
(`$280`–`$28A`). They are tracked as a **per-character bitfield at char
struct +`$2E`** (char struct base `$FF02B4`, 52 bytes / `$34`;
`+0x2E` word, via `$2B68C`; `docs/logic.md` §1, `equates.s`
`ram_sys_field_02e2` = `$FF02E2` = base + `$2E`):

- `inv_apply_resource` (`$02BBD2`, `code_05.csv`) Q10 path (`$02BD70`):
  `sys_bitmap_write(flag, code%64, ptr=char+0x2E)` — sets/clears the ring
  bit on the effective char (type 4 → `+0x27` redirect target; type 1 →
  itself).
- `item_category_of` (`$02C8F2`) Q10 path (`$02CA74`):
  `sys_bitmap_test(code%64, char+0x2E)` on the effective char —
  **per-char, not party-summed** (the group-recursion loop at `$02C986`
  runs only for quotient < 10, i.e. spells).
- Q10 XP side-effect (`$02BDA2`/`$02BDAA`/`$02BDB2`): party XP grant of
  500 for minor 0 (Will), 350 for minor 4 (Advance), 3000 for minor 10
  (Perfctin), 0 otherwise — via recursive `$02BBD2(..., 0x401, ...)` per
  party member, gated on `$FF0112 != 0x2A` and flag != 0.
- Save format (`docs/save.md:379,384,393`): rings saved as **15 bits
  padded** (11 items + 4 pad) in the inventory section; the serializer
  calls `item_category_of` per ring code.

**Correction to the task brief:** `$2B6E0` is `npc_attitude_event_apply`,
not a ring-grant routine. Its args are (flag, event-index into `$D601E`);
it sets an event bit in `$FFC326` then dispatches on `$D601E[event].w0`
type. Case-6 op-11 `w4=100` is **event 100**, whose `$D601E` record has
code 650 (Ring of Perfection), type 3 — the grant is indirect
(event → spawn/apply), not a direct `$2BBD2` call.

### Where the rings come from (`$D601E` event table, 161 records × 6 bytes)

Ring-code records (code 640–650) in `$D601E` — **only 7 of 11**:

| Event | Code | Ring | Type | `w1` | Route |
|---|---|---|---|---|---|
| 71 | 644 | Advance | 5 | `0x00F1` | Battle-end grant (see below) |
| 78 | 646 | Bile | 3 | `0x3165` | Type-3 spawn/apply, loc 357 |
| 93 | 648 | Variatin | 3 | `0x3189` | Type-3 spawn/apply, loc 393 |
| 100 | 650 | Perfctin | 3 | `0x2195` | Type-3 spawn/apply, loc 405 — case-6 op-11, text 544 "Here, take the Ring." |
| 108 | 641 | Thought | 3 | `0x1193` | Type-3 spawn/apply, loc 403 |
| 140 | 640 | Will | 5 | `0x00C1` | Battle-end grant |
| 160 | 645 | Blood | 5 | `0x0162` | Battle-end grant |

Missing from `$D601E`: codes **642, 643, 647, 649** (Intuitin, Division,
Mutation, Calling) — **CLOSED 2026-11-24 (O5): they are granted by
dialog, not by `$D601E` events.** All four grant records route through
the first dispatch's arm 6 (`$029B0C`, party-slot/item grant:
`(w10 & 0xFFF) >> 6` = category; category > 6 → `inv_apply_resource`
grant). The prior "no grant site" conclusion rested on the swapped
dispatch model (it read the records' w10 nibble 6 as the second
dispatch's no-op arm 6). Full chains, texts, NPCs, anchors, and live
proof: see "The four dialog ring grants (O5 — CLOSED)" below.

Battle-end grant path (`npc_attitude_adjust`, `$035656`): `$2D284`
(`sys_copy_stride6_2d284`, `$02D284`) returns an event index; if its bit
is set in `$FFC326`, the `$D601E[ev]` code (`& 0x7FF`) is granted via
`inv_apply_resource` and the bit is cleared; else `$FFC410 = 0x7530`
(30000 default). Type-5 records set only the event bit (no dispatch
action) — their ring grant comes from this battle-end path. Which enemy
maps to which ring event is not yet traced (residual, not part of O5's
close).

### The four dialog ring grants (O5 — CLOSED 2026-11-24)

The four rings missing from `$D601E` are granted by **dialog records**,
through the first dispatch's arm 6 (`$029B0C`, party-slot/item grant):
it reads `w10`, computes category `(w10 & 0xFFF) >> 6`, and if the
category is > 6 grants via `inv_apply_resource(leader, code, 1, 1)`
(`$02BBD2`), then enqueues a category-name message and plays song 8.
Rings are category 10, so every `w10 = 0x62XX` record grants ring
`0x2XX`. The `w10 = 0x62XX` low bits are the **item code**, not a
chain index — chains run through the re-resolve arms (first-dispatch
arm 0 on `w10` low bits, second-dispatch arm 0 on `w8` low bits), which
reload the out struct with the next record's `w8`/`w10` and loop back
through both dispatches.

The entry records are all **b5 = `0xFE` gated**: eligible only while
the leader CARRIES the handover item (`w8 & 0xFFF`) — see the scorer
(`shop_record_score`, `$0331A4`) b5 switch at `$0334D6`. The handover
items are consumed by their chains (Milk by rec312, Ball by rec448,
Dove by rec441; the painting is kept). All four chains share
`b6=145, b7=111` (the b6/b7 gate is skipped when b7 == 111).

**643 Division — rec313** (kind 50, ident 153, `w8=0x013A`,
`w10=0x6283`), text 409. Chain: rec310 (kind 50, text 406, the ask:
"break the spell, kill the Regent, get me some milk") → rec311 (kind 9,
b5=`0xFE` HAS Y Milk 846, text 407 "I feel much better now — I can
remember!", `w10` low `0x138` → 312) → rec312 (kind 50, text 408 "You
got me the Milk of Youth, that must mean that the Regent is dead.",
TAKES the Milk via first-dispatch arm 7, `w8` low `0x139` → 313) →
rec313 grants 643 (text 409 "Here take this old ring. My father's
father owned it and it's very valuable.", `w8` low `0x13A` → 314) →
rec314 (kind 50, text 410 "I think it's called Division — I'm still a
little foggy...", second dispatch `w8` nib 12 → SET event bit 15;
first dispatch `w10=0xE0FA` nib 14 → grant XP 250). Speaker: template
153, "Nobody" (spawn 144, spawn byte 3 = 13), at anchor 142 (key
(40,136), room 82), coords (7,9) — the old king under the Regent's
spell (Milk of Youth quest). The Division *scholar* litany is a
separate chain, texts 276–280 (recs 180–184, ident 2234→186, chained
via `w10` lows `0xB5`–`0xB8`): 276 "According to legend the Ring of
Division was given by Nexus to a young Knight named Doggon...",
278 "Division shall be found in the form of a Division of Age and a
Division of Power", 279 "Doggon XXIV has been Divided from his
power...". The blind-spot report's "Cathedral scholar, Doggon legend
(texts 548–558)" is the Keef/pirate chain (recs 452–462, idents
187/190; text 557 is Keef finding the Ring of Will in a bagel), NOT
the Division grant.

**642 Intuitin — rec442** (kind 50, ident 0, `w8=0x3000`,
`w10=0x6282`), text 538. Chain: rec440 (kind 10, ident 93, b5=`0xFE`
HAS Dove 854, text 536 "Ah, a dove. Delicious, thank you. Here take
your pick from my treasure horde.", `w10` low `0x1B9` → 441) → rec441
(kind 50, text 537 "A nice shiny Ring of Power. Doesn't fit on my
claw anyway.", TAKES the Dove via first-dispatch arm 7, `w8` low
`0x1BA` → 442) → rec442 grants 642 (text 538 "Go away, before I get
hungry again!", second dispatch `w8` nib 3, low 0 → FIGHT via
`combat_select_unit(-1, party[0])` + `menu_set_mode(0)`). Speaker:
template 93, "Nobody" (spawn 117, spawn byte 3 = 10), at anchor 82
(key (6,83), room 46), coords (5,8) — a clawed creature that eats the
dove. Its gated pair rec439 (kind 10, ident 93, b4=52, b5=`0xFF`
NOT-have-Dove, `w8=0xF356`, `w10=0x3000`) is the hungry greeting,
text 535 "Growwlll! I'm hungry. A little white bird might be
nice..." (`w10` nib 3 → level-2 key 0 → FIGHT). **Rec440 can never win
a kind-10 TALK query for the real dragon in the shipped ROM:** it
needs `-$c`=1 (char `+0x17` == b4=52) to offset the `+0x1000` `-$22`
penalty for b4≠0 with b5 outside [`0xFA`, `0xFD`] (at `$0335DA`); the
real dragon's `+0x17` is 10 (spawn 117 byte 3), and the `$d` path
needs the low byte of max HP == 254, impossible (max HP ≤ 140).
Live-proven only with a fabricated `+0x17`=52 char (probe_o5b, §
Live-proven); the kind-50 entry is unreliable (a lottery — in
probe_o5b the kind-50 query resolved rec446, the Bandit HQ direction,
not rec441). Intuitin has no text mention besides the grant chain
itself (the walkthrough's "Intuition Hard, 11'-18'" remains unmapped).

**649 Calling — rec448** (kind 50, ident 0, `w8=0x7357`,
`w10=0x6289`), text 544. Chain: rec444 (kind 25, ident 2467, b5=`0xFF`
NOT-have-649, text 540 "So, you're looking for the Rings. I know
where the Ring of Calling is, but I will only tell you if you find my
lost crystal ball.", `w10` low `0x1BD` → 445) → rec445 (kind 50, text
541 "The ball was stolen by the crew of the pirate ship Ahab. Find her
and you will find it. Start first at the Bandit Hole.", `w10` low
`0x1BE` → 446) → rec446 (kind 50, text 542 "You can find that Bandit
cess pool at 30' 18'.", chain ends — `w10=0xF000`) → [player recovers
the ball] → rec447 (kind 9, ident 2467→419, b5=`0xFE` HAS C Ball 855,
text 543 "Thank you for recovering my crystal ball. It's irreplacable
for my visions. Let's take a look now...", `w10` low `0x1C0` → 448) →
rec448 grants 649 (text 544 "I see great forces aligned against each
other. I see choices that must be made, sides that must be taken.
Here, take the Ring.", second dispatch `w8` nib 7 → TAKES the C Ball).
Speaker: template 419, "Nobody" (spawn 143, spawn byte 3 = 13), at
anchor 399 (key (301,54) = 30°1′/5°4′, room 39) — the old woman
behind the waterfall (matches the text lead "30'1\" 5'4\""). The
report's text 1080/1082 quotes ("old woman behind the waterfall",
"crystal ball") do not match the extracted corpus: text 1080 is "Do
you know anything of the Rings of Power or the Temple of Nexus?" and
1082 is "I know nothing that can help you." The actual crystal-ball
chain is texts 540–544 (recs 444–448). Item 855 is pinned as the C
Ball (crystal ball).

**647 Mutation — rec497** (kind 50, ident 2446→398, `w8=0xD08A`,
`w10=0x6287`), text 593. Chain: rec496 (kind 9, ident 2446, b5=`0xFE`
HAS painting 1106, text 592 "Hey, that picture is of my real shape.",
`w10` low `0x1F1` → 497) → rec497 grants 647 (text 593 "I am returned
unto my orginal form.", second dispatch `w8` nib 13 → CLEAR event bit
138). Speaker: template 398, "Woman" (spawn 26, spawn byte 3 = 11),
at anchor 347 (key (241,143), room 43), coords (3,1), gated on ev138
(init SET) — so after the grant clears ev138 she stops spawning. The
painting ("pic", 1106) is NOT consumed by the chain. The report's
Mutation leads (Enchanter Guildmasters / inn woman, texts 1180/1182)
do not match the corpus: text 1180 is "Game cannot be restored
because of version differences." and 1182 is "\<NA\>" — those quotes
are stale/wrong; the actual grant is the Woman at anchor 347.

**Live proof (probes `probe_o5`/`probe_o5b`, 2026-11-24):** VBlank-hook
probes fabricating chars, pre-granting the handover item to the
leader, calling `npc_attitude_positive(char, kind)`, logging leader
ring bits + event words + `$FFBB86`. Division — rings `0x0000`→`0x0800`
(bit 3 = 643), `$FFBB86` = text 410; Calling — rings `0x0800`→`0x0802`
(bit 9 = 649), text 544, C Ball bit absent afterwards (consumed);
Mutation — rings `0x0802`→`0x8802` (bit 7 = 647), text 593, evW8
`0x2437`→`0x2433` (event 138 cleared); Intuitin — with fabricated
char `+0x17`=52: rings `0x0000`→`0x0400` (bit 2 = 642), text 538, Dove
bit cleared (consumed); control with `+0x17`=10 (the real dragon's
spawn byte): rings unchanged, `$FFBB86` = text 103 (kind-54 fallback)
— reproducing the original failure exactly. Probe ROMs MD5
`057b3c5e…` (o5) / `d4443244…` (o5b); logs in
`/tmp/rop275/probe/cut_log_o5.txt` / `cut_log_o5b.txt` (scratch, not
committed). Event-15 SET (rec314): evW0 bit 7 was already set in
slot_0, so the live delta is unobservable — the SET arm (`$02A086`)
is statically verified and the chain ran (text 410). The rec442
fight arm (second dispatch nib 3, low 0) is statically traced; its
live effect was not logged.

### The "all 11" check — the trigger

`sys_dispatch_action_2dcce` (`$02DCCE`), branch at **`$02DD9A`** — reached
when verb `$8(a6)==0xD` (USE item) and item-minor `$a(a6)==29` (Holy Seal:
items cat 13, `w=153`, minor 29 → price record 182 "H Seal"; code 861).
Callers at `$020352` (map verb, hardcoded minor 6), `$020400`,
`$020424` (menu-verb dispatch passing `$FFBB6F` verb / `$FFBB70` index
bytes). This is the **only** count-against-11 in the ROM (no other caller
of `item_category_of` loops to 11).

`$02DD9A` logic, verbatim from `disasm/src/rop.s`:

1. Only if `($FF0E92 & 0x3FF) == 0x188` (= **392**, a `$D1D00` anchor
   record index).
2. Loop `i = 0 .. shop_category_count(10)-1` (= 11):
   `sum += item_category_of(leader, 0x280 + i)` — counts the leader's
   ring bits 640–650.
3. If `sum < 11` **or** event bit `0x8F` (143) in `$FFC326` already set →
   `text_show_message(0x13, 0x0D)` → text **1120** (see Dialog) → return.
4. Else (all 11, bit 143 clear) → `text_show_message(0x12, 0x28)` →
   text **1119**, then:
   - `npc_attitude_event_apply(0x8F, 1)` — event 143;
   - `pal_load_set($CCC58, 0)` — all-white palette (every entry `$0EEE`);
   - `sfx_request(0x13, -1)`, `sfx_request(1, -1)`;
   - `$FF0124 = $FFFF` (palette-fade latch).

**Live-proven (probe_o5c, 2026-11-24, ROM MD5 `3337c64a…`):** calling
`sys_dispatch_action_2dcce` action `$8=0x0D`, sub-action `$a=29` at
loc 392 with 10 rings → evW8 `0x2437` (bit 143 clear), text 1120;
with **11 rings at loc 392 → evW8 `0x2437`→`0x24B7` (bit 143 SET:
evW8 bit 7 = `0x0080`), text 1119**; a repeat call → bit stays set,
text 1120 again. Full texts: 1119 "You hold up the Holy Seal. A bright
light is emmited from it and the entrance to the Fount of Heaven
opens."; 1120 "You hold up the Holy Seal. Nothing happens. Something
tells you that you need all eleven Rings and a closed door." Log in
`/tmp/rop275/probe/cut_log_o5cb.txt` (scratch, not committed — the
run-script filename carries a sed-mangling artifact, `o5cb` for `o5c`).

**The seal ITEM (861, "H Seal") has no consumer in the two `$D601E`
dispatchers and no dialog grant** — residual unknown. Exactly one
`$D601E` record carries it (rec130: `a35d00810100`, code 861, type 4),
and no `$D3102` record carries 861 in `w8`/`w10` low bits (full
1005-record enumeration). `world_enter_location` handles types 1, 2, 3
only; `npc_attitude_event_apply` handles types 0–3 only (type ≥ 4 →
return). So the gate works via event 143 without any item ("Holy Seal"
is the gate action itself). Whether 861 is obtainable via shop stock or
via the type-4/5/6 handling in other `$D601E` readers (`$02A80A`,
`$02A906`, `$02AA26`, `$02AA5C`, `$02AA76`, `$02AA98`, `$02AC76`,
`$02AC9A`, `$02ACB6`, `$02B604`) is open; the authority that would
close it is enumerating those readers plus merchant-stock
initialization.

Text-number resolution, verified: `text_show_message($a)` passes `$a` to
`text_event_resolve` (`$032D4C`) with `$9==4`, whose dispatch case 4
(`$032E74`) calls `sys_set_flag_bit3_add44d` returning `$a + 0x44D`
(= +1101). So 18→1119, 19→1120. Cross-checked: `$02DD3A` map branch uses
`$a=0x1D`=29 → 1130, consistent with location-message numbering.

### The door location (loc 392)

`$D1D00` record 392, bytes `00 0C 00 B8 AA 53 05 00 10 66`: key (12, 184),
+4 byte `0xAA` = **170** (destination room), +5 byte `0x53` = 83
(sextant-directions text: "Speed - 72 klicks south ^Cathedral - 55
north"). Per `docs/maps.md:393`, loc 392 is the "scripted encounter"
anchor (+4=170, `$FF013E`=6, chunk 247, song 7, placement (15, 30, 0)).
Sextant mapping (key ≈ degrees×10, confirmed by the Speed / Perfection /
Asylum anchors): (12, 184) ≈ 1°2′ / 18°4′. **The identity of the place at
(12, 184) as the Fount door is inferred from the texts, not yet pinned
against the world map** (open item O1). Note the walkthrough's "Bandit HQ
30′-18′" shares the 18′ but not the degrees — the two anchors are not
obviously the same place.

Destination room 170: `$D63E4` record 170 = bytes `0F 1E 00 07` →
placement (15, 30), song 7. Chunk = 77 + 170 = **247** (32×32, since
+4 ≥ 153). Hazard dispatch `$01DD1A` (inside `world_location_transition`,
`$01DA6C`): +4=170 → `$FF013E` = 6 (the scripted-encounter case).

### What event 143 does (the door opens)

`$D601E` record 143: `w0=0x0863` (code 99, type 1), `w1=0x3188`
(location word: loc 392, hi nibble 3), bytes b4=15, b5=27. Type-1 branch
in `npc_attitude_event_apply` (`$02B73C`, jump-table entry 1): after a
location match against `$FF0E92`, calls
`world_pos_add_x(0x113, 15, 27)` (`$0319EC`).

`world_pos_add_x` adds offsets to the grid base (mod grid size), loads
the chunk, and writes the tile word at the cell: clears bits 9–15, ORs
the tile value (`& 0x1FF`). So event 143 **paints tile 275 (`0x113`) at
grid offset (15, 27)** in the loaded chunk. Tile 275: `$5EDC4` word
`0x240D` → terrain 9 = Road, walkable (same terrain as tiles 184/213/
218). Reading: the closed-door cell becomes walkable road — the entrance
opens. Door-transition tiles are `0x11A`/`0x11B` (282/283, terrain 34);
tile 275 is distinct. Palette `$CCC58` (all `$0EEE` white) is also used
at `$0394F6` in a combat white-flash (random 1/6 when `$FF012A` in
6..30) — it is a generic white flash, not ending-specific.

**Whether bit 143 / the tile paint actually gates entry into room 170 is
NOT yet established** — `sys_struct52_flag_test` (`$026834`) reads +4 and
passes it to `world_location_transition` (`$01DA6C` stores to `$FF0E98`);
no bit-143 check has been found there. **O2 sub-items closed statically
(2026-11-24): (a)** the entry-time repaint and the USE-time paint touch
the same grid — both call `world_pos_add_x` with (x, y, tile) from the
same `$D601E` event record: the entry loop at `$030BCE` (type-1 arm
`$030C3C`: x = record+5 byte, y = record+4 byte, tile =
`sys_bitmap_test(ev, $FFC326) + 0x112`) and the USE-time paint at
`$02B73C` (same anchor/nibble match checks against `$FF0E92`, same
`world_pos_add_x(x=b5, y=b4, tile=$a(a6)+0x112)` where the flag arg is 1
for the Holy Seal call, so it paints 275 unconditionally while entry
repaints 274 or 275 from the stored bit). Same routine + same record
fields = same grid by construction. `$D601E` event 143 record:
`w0=0x0863` (code 99, type 1), `w1=0x3188`, b4=15, b5=27. **(b)**
`$03B224` is unrelated to bit 143 — it is inside `damage_calc`
(`$03B1EE`): `cmpi.w #$8F, ram_event_code` (`$FF012C`) is one of a run of
comparisons against `0x8E`–`0x92` and `0x97` (`$03B21A–$03B24C`); on
match it sets flat damage 70 (`0x46`, at `$03B256`). `ram_event_code`
is a combat code variable (written at `$03B4BA` from an arg, cleared at
`$036200`, set to `$200` at `$037E56`; read at `$028002`, `$03E2F8`,
etc.), compared as a *value*, with no `sys_bitmap_test` and no `$FFC326`
involvement. The numeric coincidence (0x8F = 143) is not an event-bit
test. Residual open: the bit-143 transition check itself and the
pre-paint door tile at grid offset (15, 27).

### The door guardian (loc 392, before the gate)

Two more loc-392 behaviours, both keyed to event bit **144**:

- Ambient: `world_ambient_event` (`$032284`) case 6 (`$03261A`): with
  probability 1/8 per tick, out of combat and while `$FF0124 == 0`, load
  palette `$0CCCD8` + SFX 19, latch `$FF0124 = $FFFF`.
- Step: `world_step_event` (`$032730`) case 6 (`$0328BC`): stepping with
  Y ≤ 20 while event-bit **144** of `$FFC326` is clear and `$FF0110 == 0`
  releases an NPC struct (`npc_struct_release(leader)`) and starts spell
  effect 9 (`spell_effect_start`, `$03CC4C`, mode 9; sequencer
  `spell_effect_step`, `$03D9F8` — 10-frame tile-fly-in per
  `docs/maps.md:393`, then a greeting).

Event 144 (`$D601E` record 144): `w0=0x8000` (code 0, type 0),
`w1=424` (placement-template index), b4=b5=0. **Bit-144 lifecycle
pinned (2026-11-24):** SET at new game by `shop_merchant_scan`
(`$02B5F4`), CLEARED by `npc_attitude_adjust` after beating Darius.
`$D601E` rec 144 is the spawn gate for placement template 424
(Darius in room 170): `sys_copy_stride6_2d284(0, 424)` returns 144,
so the spawn requires bit 144 SET. The earlier speculation (a
`$D3102` rec-143 route) is superseded — no dialog record sets or
clears event 144. Which NPC the step encounter (case 6, `$0328BC`)
releases remains unpinned.

## Driver

There is **no dedicated ending driver**. What drives each link:

| Link | Driver | Address |
|---|---|---|
| All-11 gate + flash + tile paint | `sys_dispatch_action_2dcce` branch | `$02DD9A` in `$02DCCE` |
| Door ambience (1/8 per tick) | `world_ambient_event` case 6 | `$03261A` in `$032284` |
| Door step encounter | `world_step_event` case 6 | `$0328BC` in `$032730` |
| Room-170 entry + occupant spawn | `world_location_transition` → `world_enter_location` | `$01DA6C` → `$03090A` |
| Darius conversation | NPC conversation system (`npc_attitude_positive` → `text_event_resolve` → `$D3102`) | `$0298D2` → `$032D4C` |

Ruled out as the ending driver (with one correction — see below):

- **`sys_event_run` (`$02D56A`)**: **NOT ruled out — it drives the Darius
  monologue.** Case 7 (`$1A520`) is a `sys_event_run` script whose 13
  op-6 records (w4 571–583) display texts 667–679, the Darius monologue
  (dialog live-proven by probe_case7; see
  `docs/cutscene-darius-endgame.md`). An earlier scan of
  `.scratch-cutscenes/decode_all.txt` concluded no script contained texts
  666–680, 1119, or 1120 — but it compared against **unshifted** op-6 w4
  values. Op-6 displays w4 + 96 (`$032D9E` `add.w #$60`), so the
  per-case displayed texts are: case 0, 210–220; case 1 (Buc), 221–226;
  case 2, 462–463; case 4, 502–504; case 5, 565–568; case 6, 636–641;
  case 7, 667–679. What `sys_event_run` does **not** drive is the Holy
  Seal gate (texts 1119/1120) or the room-170 entry — those run through
  the item-USE dispatcher and the location-transition system.
- **`intro_helper` (`$015012`)**: its only caller is `intro_story_driver`
  (`$014FB6`, via `bsr` at `$014FC0`, looped until return 0, then
  `world_map_draw`). It requests song 1, calls `snd_music_start`, decodes
  maps 29/30/31 (`map_decode` `$1D/$1E/$1F`), uploads tiles, loads palette
  `$0CCAF8`, SFX 1. Intro/attract only.
- **`snd_music_start` (`$015C08`)**: callers at `$015028`
  (`intro_helper`), `$0154EC`/`$01550C`/`$01553A` (all inside
  `intro_helper`, `$015012`–`$015BB7`), `$0195BE` (title region). No caller
  in gameplay/ending code.
- **`$01DD1A`**: not a driver — the hazard dispatch inside
  `world_location_transition`; its 170→6 arm is the Fount-door encounter,
  already covered above.

The per-tick mode-6 stepper is unlocated (separate open item from the Buc
work) and was not chased here.

## Content

### The final battle — Darius

The confrontation is texts **666–680** (verbatim in Dialog below) — but they
arrive over **three delivery paths**, not one script. Text 668 places
Darius "living it up at Kaos", so the battle is at Kaos, not at the Fount.
The walkthrough (fan site,
`docs/research/ringsofpower-co-uk-remaining.md`) agrees: final battle vs
Darius/Derek, also called Void; Part 3: Holy Seal, Bandit HQ 30′-18′;
"ending appears scripted".

- **666 — the greeting, via the TALK path before the menu.**
  `npc_attitude_positive` (`$0298D2`) at `$029990` calls
  `text_event_resolve` with kind 10 and the talked-to char's `+0x02`
  (424); `shop_record_score` (`$0331A4`) picks `$D3102` index 570 and
  returns best + 96 (`add.w #$60` at `$03373C`): 570 + 96 = 666. The
  entry record is idx 570: kind 10, identity 2472, `w8=0x4007`,
  `w10=0xF000`.
- **667–679 — the monologue, via `sys_event_run` case 7.** TALK to
  Darius (menu option 10 = kind 10, per the `$0220AA` menu dispatch)
  → rec570's `w8` arms case 7 through the second dispatch (see below),
  script `$1A520` (13× op-6, w4 571–583, speakers `w6=424` Darius ×11,
  `w6=0` Buc ×2), then op-0 exit. Dialog live-proven, all 13 lines
  (probe_case7; see `docs/cutscene-darius-endgame.md`).
- **680 — the bark, via the TALK greeting path, hostile, no menu.**
  `$D3102` index 584 (verbatim `00 0A 00 00 25 00 00 91 F0 00 B0 05`):
  kind 10, identity 0, `w8=0xF000`, `w10=0xB005`. If it wins the scoring
  for a kind-10 TALK, `shop_record_score` returns 584 + 96 = 680 and it
  is displayed; then the first dispatch (table `$029F8A`, nibble 11 →
  `$029C70`) applies attitude −5, and the second dispatch (table
  `$02A1EE`, nibble 15) no-ops (nibble ≥ 14). No menu, no cutscene. Who
  says it is **open**: identity 0 earns no identity bonus, so it can
  only win for a talked-to char with no identity-matching kind-10
  record. The "Sss" spelling marks a serpentine / VOID-aligned speaker,
  not Darius — and recs 584–588 (texts 680–684, all b4=37, ident 0)
  are one VOID-cultist bark family ("What do you want, Filth? Have you
  come to bow down before my massster VOID the Dessstroyer?",
  "Void is my masster. Join him or die."), so 680 is a cultist bark,
  not a Darius line.

Darius: spawn-table record 105 (`$CECF0` rec 105: `00 91 25 16 01 00`,
name idx 145 = "Darius"). The other four ring-holders of text 668 are
spawn 101 Roakus, 102 Imino, 103 Yoppa, 104 Fezzik (name idx 141–144).

The dispatch tables are decoded — **correction (2026-11-24):** the
blind-spot report and the issue body had the two dispatches swapped.
Verified against `disasm/src/rop.s` and the `shop_record_score` tail
(`$033744–$03377A`): the out struct carries out+0 = record+8 (w8),
out+2 = record+10 (w10), out+4 = best index. **First dispatch
(`$029AC0`, table `$029F8A`, 15 arms, base `$029FB8`) keys on w10's top
nibble** (the `-$4` slot in `npc_attitude_positive`'s frame):
0→`$29F32` re-resolve+enqueue, 1→`$29C4E` attitude+,
2/4/8→fall through, 3→`$29C94` level-2 (key `w10 & 0xFFF`: 0→FIGHT,
1→`combat_battle_end`, 2→nothing, 3–7→spawn party member, 8→song 8,
9→recurse positive), 5→`$29C14` toggle event bit, 6→`$29B0C`
party-slot/item grant, 7→`$29BB8` item TAKE, 9→`$29F0C` take gold,
10→`$29E2A` recurse positive, 11→`$29C70` attitude−, 12→`$29ADA` SET
event bit, 13→`$29AF4` CLEAR event bit, 14→`$29DCA` grant XP.
**Second dispatch (`$029FCA`, table `$02A1EE`, 14 arms, base `$02A21A`)
keys on w8's top nibble:** 0→`$29FE0` re-resolve, 1→`$2A034` attitude+,
2/5/6/10→no-op, 3→`$2A19A` sub-dispatch (low 0 → FIGHT via
`combat_select_unit(-1, party[0])` + `menu_set_mode(0)`; low 8 → song 8),
4→`$2A17C` `menu_select_screen(w8 & 0xFFF)`, 7→`$2A11A` item TAKE,
8→`$2A0F0` gold grant, 9→`$2A0C4` gold grant, 11→`$2A05C` attitude+,
12→`$2A086` SET event bit, 13→`$2A0A6` CLEAR event bit. Arm-0
re-resolve (either dispatch) reloads the out struct with the chained
record's w8/w10 and loops back through both dispatches — this is how
kind-50 topic chains work. (The first dispatch's table has a 16th word,
index 15, pointing to `$25074` mid-routine; no valid record observed
indexing it — open micro-question, not blocking.) `shop_record_score`
(`$0331A4`) picks the winning `$D3102` record by score (`0x4000` if
record+2 matches char `+0x02` — small path direct, large path
ident − `0x800` — `0x10000` on kind match, gate bit7 `0x8000`, bit5
`0x2000` / bit4 `0x1000` / bit3 `0x0800`, + RNG `0x400` jitter; the
`-$22` score-high term penalises b4≠0 records unless the `-$c`/`-$e`
arg matches hold).

**O4 consequence — invocation CLOSED:** rec570's `w8=0x4007` →
second-dispatch arm 4 → `menu_select_screen(7)` → case-7 script
`$1A520`. Exactly 8 records in the ROM have w8 nibble 4 (menu cases
0–7): rec104 case 1, rec113 case 0, rec365 case 2, rec401 case 3,
rec406 case 4, rec468 case 5, rec540 case 6, rec570 case 7. The
case-7 invocation path from dialog EXISTS; the issue's "no in-dialog
invocation path" premise is false. **Fight trigger — mechanism
live-proven (probes `probe_o4d`/`probe_o4e`, 2026-11-24):** op-0's
`combat_battle_end` (`$03599C`) STARTS the battle only if the leader
has a live combat opponent linked in char `+0x29` — it plays song 20,
then runs the battle body only when both groups have someone alive
(`combat_group_alive`: 1 iff ALL group members via char+`0x14` links
have the dead flag), else falls back to kind-54 dialog. The `+0x29`
link is written only by `combat_select_unit`'s pairing tail
(`L02A410`), whose only pairing callers are the three sites in
`world_scan_ahead_for_char` (`$02AD64`) — the facing scan (called from
the main-loop input dispatch at `$00D736` when not in combat and
anchor ≠ `0x3FF`). The scan pairs **only type-4 (redirect) chars** —
each phase skips non-4 chars at the cell — so a type-1 Darius is
correctly ignored (probe_o4 run 2, negative-but-clean: leader+`0x29`
stayed `$FF` through all four dir calls, combat flags clear,
`$FF02A0`=50, Darius findable — the scan's type filter, not a failure
to find him). Probe_o4d (direct `combat_select_unit(53, leader)`,
`$FF02A0`=53, ROM MD5 `98458cbc…`): leader+`0x29` `$FF`→`0x35` (53),
Darius 53's +`0x29` `$FF`→`0x00` — the pairing tail live-proven.
Probe_o4e (scan dir 0 north, `$FF02A0`=53, ROM MD5 `8cfe74b4…`): the
scan found the type-4 Darius at the adjacent north cell and paired
him — leader+`0x29` = 53, Darius 53's +`0x29` = 0 — the scan-ahead
pairing live-proven end-to-end. Logs `/tmp/rop275/probe/cut_log_o4d.txt`,
`cut_log_o4e.txt` (scratch, not committed). **Wedge note (honest
negative):** probe_o4c (same setup, `$FF02A0`=50, all four dirs) hung
twice — spin never hit in 180 s, twice, while the type-1 run and the
o4d/o4e runs hit it in ~2 s. The ROMs differ by exactly two bytes
(checksum + the type immediate), so the wedge is in the scan's
**merchant-setup branch**: with `$FF02A0` (50) ≠ the found Darius's
+`0x27` (53), `combat_select_unit` takes the `shop_merchant_setup`
path (`$02A3DC`) instead of the direct pairing path — and with a
fabricated non-merchant Darius (template 424) that path wedges
somewhere in `shop_merchant_setup` / the SFX / `cmd24_handler`
tail (which of the three is unpinned). It is confined to that branch
with a fabricated char: the direct path and the scan-with-matching-
`$FF02A0` both complete cleanly, and the fabricated type-4 chars
themselves do not wedge the main loop (o4d/o4e ran fine with them
present). In the real game `$FF02A0` is set by `shop_merchant_setup`
to the merchant's char, so the mismatch branch is the normal TALK
path — the wedge is a probe artifact, not evidence the real path is
broken. What remains open is the full probe C (TALK to Darius in real
Kaos game state, verb-menu options, fight trigger / case-7 arming)
and probes A/B (fabricated endgame state → Holy Seal → room 170 →
Darius at (15,9); bit-144 clear → walk north past Y=20 in room 170 →
spell effect 9 → text 1121).

The combat-victory path is `npc_attitude_adjust` (`$035656`): gold/XP
split, then the `$2D284` event lookup → grant (see Entry / trigger).
`$FFC40A` = battle-won flag; `$FFC40C` gold total; `$FFC40E` XP total.
No post-victory routine specific to Darius/Void has been found — no
routine runs after that victory that has been identified as an ending
sequence (open item O6).

### Room 170 — the Fount of Heaven interior

**Correction (2026-11-24):** the previous version of this section said
room 170's sole occupant was placement record 28, a "Woman" at (5, 3).
That was wrong twice over: it read the template key 170 as a *room*
number, and it took the name from the *spawn* table record 28 instead
of the placement record. The template loop in `world_enter_location`
(`$03090A`, `$030A64`) matches on the **anchor** index (`d4` =
`$FF0E92 & 0x3FF`): branch 1, template key (low 10 bits of the
`$CF1C0` word) == anchor; branch 2, template key == the byte at
`$D1CFC+10*anchor`; then the nibble (`(word rol 4) & 0xF`) must equal
the location word's high nibble (`d5`). Placement is x = template
byte 2, y = template byte 3, heading = `(word rol 6) & 3`.

- **Template 424 — Darius — is the room-170 occupant.** Word `0x3988`
  (key **392**, nibble 3), bytes 2–3 = (15, 9), heading 2. It spawns on
  entering **anchor 392** (dest room 170), via branch 1. Gate:
  `sys_copy_stride6_2d284(0, 424)` returns **144** (`$D601E` record 144
  has `w1=424`), so the spawn requires event bit **144 SET** in
  `$FFC326`. Bit-144 lifecycle: SET at new game by
  `shop_merchant_scan` (`$02B5F4`), CLEARED by `npc_attitude_adjust`
  after beating Darius — so Darius spawns in room 170 only while bit
  144 is set, and after the victory he is gone.
- **Template 28 is Rashiid, not the room-170 Woman.** Word `0x38AA`
  (key **170**, nibble 3), bytes 2–3 = (5, 3), heading 2 — it spawns on
  entering **anchor 170** (dest room 29), via branch 1, alongside
  template 27 (branch 2, key 29 — anchor 170's branch-2 byte is 29),
  both at (5, 3): the double-Rashiid spawn (O3). The "Woman" name
  came from `$CECF0` spawn-table record 28 (`00 02 4c 1c 09 02`, name
  idx 2) — a different table from the `$CF1C0` placement record 28.
  No placement of a "Woman" in room 170 was found; whether the
  spawn-table-28 Woman appears anywhere, and whether she is Nexus, is
  unproven (open item O6).

### What the "final animation" actually is

Putting the chain together, the visible ending sequence as coded is:

1. Darius's confrontation at Kaos: greeting 666 (TALK path) → monologue
   667–679 (`sys_event_run` case-7 script `$1A520`, dialog live-proven)
   → op-0 exit → the final battle, started by `combat_battle_end` iff
   the leader's `+0x29` combat-opponent link is set (O4; the bark 680
   is a separate VOID-cultist TALK bark, not part of the fight trigger).
2. At the Fount door (loc 392): USE the Holy Seal → text 1119, an
   all-white palette flash (`$CCC58`), SFX 19 + SFX 1, and tile 275
   (Road) painted over the door cell at (15, 27) — the door opens.
3. The door ambience (1/8-per-tick palette `$0CCCD8` + SFX 19) and the
   step encounter (spell effect 9, 10-frame tile fly-in) at the same
   anchor.
4. Entry into room 170 (song 7, placement (15, 30)) and Darius
   standing at (15, 9) — the room-170 fight.

There is **no picture sequence, no credits roll, no return-to-title and
no "The End" text** anywhere in the dialog corpus (searched:
congratulations, quest complete, Rod reform, victory, "You have won",
saved the world — only text 1095, the Nexus dream, and the jackpot
texts 596/1110/1111 hit). The ending is picture/effect-driven, not
dialog-driven — or the post-battle sequence has no text at all. If a
distinct "final animation" routine exists beyond the four links above,
it has **not** been found; the doc says so plainly rather than forcing a
driver.

## Actors

| Actor | Identity in ROM | Where |
|---|---|---|
| Darius | Spawn-table 105, name idx 145 (`$CECF0` rec 105: `00 91 25 16 01 00`) | Kaos (text 668); final battle |
| Roakus / Imino / Yoppa / Fezzik | Spawn 101–104, name idx 141–144 | Named in Darius's monologue (texts 669–671) |
| "Woman" | Spawn-table 28, name idx 2 (`$CECF0` rec 28: `00 02 4c 1c 09 02`) | No placement in room 170 found (the old "room-170 Woman" was placement template 28 = Rashiid at anchor 170/room 29, misread). Whether she appears anywhere, or is Nexus, is unproven |
| Nexus | Only in texts (56, 1095); no NPC record pinned | "Inside is the divine Nexus himself" (text 56) |
| Buc (player) | Leader char; ring bits on leader's `+0x2E` | Carries the 11 rings + Holy Seal |

## Dialog (verbatim from `disasm/text/records_ddbd8.txt`)

### The Darius confrontation (texts 666–680, three delivery paths)

666 is the TALK greeting (path: `npc_attitude_positive` → `$D3102` idx
570 + 96); 667–679 are the case-7 `sys_event_run` script (dialog
live-proven); 680 is a hostile TALK bark (`$D3102` idx 584 + 96). See
"The final battle — Darius" above for the full pinning.

> 666: "Why hello there Buc, I've been waiting for you. You see, It all came to me just after our master zapped me to some random location in the artic."
>
> 667: "The best way to get the Rings of Power was to sit back and let everyone else do all the work. Then when you showed up here I would retreive them."
>
> 668: "So I have been living it up at Kaos for past few months, while you, and the four other suckers ran around the world finding my Rings for me."
>
> 669: "Imino managed to find the Ring of Advancing, but of course you took that from him in Richi."
>
> 670: "Poor old Yoppa went to all that trouble to find the Ring of Will and bring it back to the Cathedral. But you also took his Ring."
>
> 671: "Now my friend Fezzik, I told him to wait in the Chamber of Perfection, and sure enough you came along with the gems. Too bad you had to kill him."
>
> 672: "Roakus, on the other hand, was a surprise failure. He didn't manage to get a single Ring. But instead, he spent his time lounging in the Lobotomy Club."
>
> 673: "I don't know what Master Thalmus saw in him."
>
> 674: "You on the other hand, were an unprecedented success. You managed to secure all eleven of the Rings. And now... you have brought them here to me."
>
> 675: "Thank you."
>
> 676: "But Darius, you have made one fatal mistake. For I, in obtaining the Rings, also learned of their powers and can now use them against you."
>
> 677: "Allied with Nexus, this is not a power that even you can overcome."
>
> 678: "No, Buc, it is you who have made the tactical blunder. For I have a secret up my sleave, which I shall be happy to tell you..."
>
> 679: "VOID! And the spells he has crafted for your destruction. Give my regards to the rest of the gang when you meet them: In the dead lands..."
>
> 680: "Die Sssorcerer sscum!"

### The Holy Seal (texts 1119–1120)

> 1119: "You hold up the Holy Seal. A bright light is emmited from it and the entrance to the Fount of Heaven opens."
>
> 1120: "You hold up the Holy Seal. Nothing happens. Something tells you that you need all eleven Rings and a closed door."

### Related texts

> 56: "You stand before the mystic Fount of Heaven, the seat of Nexus' power. Inside is the divine Nexus himself."
>
> 430: "There are eleven Rings; they are the foundation of Nexus' power"
>
> 432: "when the Rings are together, they form the Rod of Creation"
>
> 648–652: Rod history; 651: "man will not be able to enter until he possesses all eleven Rings and uses the Holy Seal"; 652: the Holy Seal was stolen by bandits.
>
> 640: the Ring of Perfection materializes.
>
> 636–641: Fezzik / Sun+Moon gems / Chamber of Perfection.
>
> 1095 (Nexus dream): "Restore the Rings of Power to me and I shall reform the Rod of Creation and return my grace to mankind!"
>
> 1121: "You have the run of the world. All that you see is your responsibility."
>
> 1122: "An aura permeates this place, you can not use magic or attack anyone."

Texts 1121/1122 sit immediately after 1119/1120 in the corpus and read
like post-entry lines, but **their callers are unpinned** — no
`text_show_message` call with `$a=20`/`21` and no `$D3102` record with a
room-170 context has been tied to them yet (open item O6).

## Effects

| Effect | Where | Notes |
|---|---|---|
| White flash | `$02DE46` (Holy Seal gate) | `pal_load_set($CCC58, 0)` — all 16 entries `$0EEE`; also used in combat at `$0394F6`, generic |
| SFX 19 + SFX 1 | `$02DE46` | `sfx_request(0x13, -1)`, `sfx_request(1, -1)` |
| Palette `$0CCCD8` + SFX 19 | `$03261A` (ambient case 6) | 1/8 per tick at loc 392; `$FF0124` latch |
| Door tile painted | Event 143 → `$02B73C` → `world_pos_add_x(0x113, 15, 27)` | Tile 275, terrain 9 Road, at grid offset (15, 27) |
| Spell effect 9 | `$0328BC` (step case 6) | `spell_effect_start(9)`; 10-frame tile fly-in, then a greeting (NPC unpinned) |
| Song 7 | Room 170 (`$D63E4` rec 170) | Also the loc-392 anchor song |

## Exit

**None found.** No return-to-title, credits roll, reset, or attract-mode
return has been identified after room-170 entry or after the Darius
battle. The game presumably continues in room 170 with the "Woman"
present. What she says or does — whether TALK triggers texts 1121/1122,
a ring hand-over, or a further sequence — is the principal open item
(O6). If the ending is simply "walk into room 170 and the game
continues", that is itself the finding, but it has not been live-proven.

## Location

- **Fount door:** loc 392, key (12, 184) ≈ 1°2′ / 18°4′, chunk 247,
  destination room 170, placement (15, 30, 0), song 7, `$FF013E` = 6.
- **Fount interior:** room 170, chunk 247 (32×32), placement (15, 30),
  song 7.
- **Final battle:** Kaos (per text 668); exact anchor unpinned.
- **Ring-holder sites** (from `$D601E` type-3 records): loc 357 (Bile),
  loc 393 (Variatin), loc 405 (Perfctin, Chamber of Perfection),
  loc 403 (Thought).

### O1 — Bandit HQ (CLOSED statically, 2026-11-24)

**Anchor 321, key (307,181) = 30°7′/18°1′, room 164, is the Bandit HQ
("Bandit Hole").** Evidence: (1) it is the ONLY anchor with key0 in
300–309 and key1 in 180–189 — the unique anchor in the whole-degree
cell (30,18); text 542's "30' 18'" is the whole-degree truncation of
30°7′/18°1′ (the same truncation the walkthrough uses for "Bandit HQ
30'-18'"); no anchor matches (30,18), (30,180), or (300,180) exactly
(re-checked at the correct anchor base `$D1D00`, 10-byte records — an
earlier scan using `$D1CFC` was misaligned and its "absent" result was
invalid). (2) Content: anchor 321 is a 32×32 room (chunk 241, song 11)
holding template 333 "MR. Belmont" (spawn 61) at (18,17), template 334
"Lenny" at (26,23), and template 335 "Man" (spawn 54) at (20,16) whose
kind-10 records are rec566 text 662 "No admittance without Bandit ID."
and rec567 text 663 "Very well, your ID looks okay, go on in." (ident
2383→335). Texts tie Belmont to MR. B: text 1037 "Our leader is the
mysterious MR. B. The most brilliant villain the world has ever known.
Except for Void of course."; text 1165 "The bearer... is certified by
MR. B as a genuine 100% nasty bandit."; text 1166 "...men such as the
evil Mr. Belmont." (3) Quest chain fits: text 541 (rec445) "The ball
was stolen by the crew of the pirate ship Ahab. Find her and you will
find it. Start first at the Bandit Hole." → text 542 (rec446) "You can
find that Bandit cess pool at 30' 18'." — rec445/446 are kind-50,
ident 0, chained via rec445 `w10` low `0x1BE` → re-resolve 446.
**Wrinkle to record:** anchor 321's +5 byte is 24, shared by 8 anchors
(57, 196, 214, 267, 321, 322, 336, 407), and text 24 is "This is the
Necromantic Academy -- a chill creeps up your spine." — so the +5 byte
is not a unique sextant-text id. No anchor has +5 = 41 (text 41 is
Belmont's manor description, not a sextant text). The kind-24
city-topic records for bandits (rec940 text 1036, rec941 text 1037,
b4=41) use b4=41 as a city/topic id whose mapping table was not pinned.
Also checked: anchor 171 key (30,217) = 3°0′/21°7′ (template 221 Woman)
is NOT the Bandit HQ. Text 1156 ("sunk at long 18'5\"") has no anchor
with key1=185 — the Ahab wreck is not an anchor. Text 695's coordinate
format ("21'8\", 8'7\"" → keys (218,87)) confirms the degrees-minutes
key scheme.

## Live-proven vs static-only

**Live-proven (2026-11-24, issue #275 probes; BlastEm, `slot_0` state,
VBlank-hook scratch ROMs at `$FD400`, hook at `$1272`, breakpoint on
`test_spin`, words read via debugger `p/x`):**

- The four dialog ring grants (probe_o5, ROM MD5 `057b3c5e…`;
  probe_o5b, MD5 `d4443244…`): Division rings `0x0000`→`0x0800`, text
  410; Calling `0x0800`→`0x0802`, text 544, C Ball consumed; Mutation
  `0x0802`→`0x8802`, text 593, event 138 cleared; Intuitin with
  fabricated char `+0x17`=52: rings →`0x0400`, text 538, Dove consumed;
  control with `+0x17`=10 (the real dragon's spawn byte): no grant,
  text 103 fallback. Logs `/tmp/rop275/probe/cut_log_o5.txt`,
  `cut_log_o5b.txt` (scratch, not committed).
- The Holy Seal gate (probe_o5c, ROM MD5 `3337c64a…`): 10 rings at loc
  392 → text 1120, bit 143 clear; 11 rings → text 1119, evW8
  `0x2437`→`0x24B7` (bit 143 SET); repeat → bit stays set, text 1120.
  Log `/tmp/rop275/probe/cut_log_o5cb.txt` (scratch, not committed).
- The Darius monologue dialog (probe_case7, earlier): all 13 lines
  667–679, in order.
- The scan-ahead pairing (probes `probe_o4d`/`probe_o4e`, 2026-11-24):
  direct `combat_select_unit(53, leader)` with `$FF02A0`=53 →
  leader+`0x29` = 53, Darius 53's +`0x29` = 0 (ROM MD5 `98458cbc…`,
  log `cut_log_o4d.txt`); `world_scan_ahead_for_char(leader, dir 0)`
  with `$FF02A0`=53 → the scan found the type-4 Darius at the adjacent
  north cell and paired him, same link values (ROM MD5 `8cfe74b4…`,
  log `cut_log_o4e.txt`). Both hit the spin in ~2 s. The type-1
  scan run (probe_o4 run 2) was negative-but-clean (no pairing —
  the scan pairs only type-4 chars); the `$FF02A0`-mismatch scan run
  (probe_o4c) hung twice (see the wedge note in the Darius section).

**Static-only (verified verbatim against ROM bytes / `rop.s`, not run
live):** the entry record and its dispatch; the speaker attribution
(`w6=424` → Darius, `w6=0` → Buc — 424 does not resolve in `slot_0`,
so no live portrait/speaker byte was observed); the op-0
`combat_battle_end` call and what it does in the Kaos setup; the exact
Kaos location number; the pre-paint door tile and any bit-143
transition check; the seal-item 861 obtainability; the rec442
fight-arm live effect; the event-15 SET live delta (bit already set in
slot_0).

### What a live probe would need (remaining designs — Probe A is done)

Probe A — the Holy Seal gate: **DONE (probe_o5c, 2026-11-24).** The
design on paper below was executed as a function-call probe instead of
a warp-and-USE probe: call `sys_dispatch_action_2dcce` action
`$8=0x0D`, sub-action `$a=29` with fabricated ring bits at loc 392,
and log the shown text and `$FFC326` bit 143. Result: 11 rings →
text 1119, bit 143 SET (see above). What forcing proves and what it
does not: it proves the gate logic (count, texts, bit set) fires when
the state is as the game would leave it after collecting the rings
legitimately. It does **not** prove the rings can actually be
collected that way, that the Darius battle leads here, or that the door
is impassable before the paint — the pre-paint tile and any bit-143
transition check are still open (O2 residual). Every forced value is
logged as forced.

Probe B — the Darius talk (now specifiable): TALK to Darius (spawn 105)
with the `$D3102` event-9/50 state and log the resolved record and the
texts shown. The greeting path is pinned (`$D3102` idx 570, kind 10,
identity 2472 → text 666), then the second dispatch arms case 7
(`$1A520`, 667–679) → op-0. The fight-trigger mechanism is live-proven
(probe_o4d/o4e — the scan-ahead pairing; see Live-proven). Still open:
the combat start after the monologue in real Kaos game state (O4,
probe C) — the link itself is proven; what remains is observing it
happen from a real TALK, with the verb-menu options and the Kaos char
setup.

Probe C — room 170 after entry: TALK to Darius (placement template
424, at (15, 9)) and log every text shown, any event-bit changes, and
any mode change. This is the probe that would settle whether there is
any further ending sequence (O6). (The earlier design said TALK to the
"Woman" (spawn 28) — superseded: no Woman is placed in room 170.)

Harness rules (proven pattern, probe_case7 / probe_o5* / probe_o4*):
BlastEm at `/usr/games/blastem`, `DISPLAY=:99`, reuse the running Xvfb,
`SDL_AUDIODRIVER=dummy`, `PYTHONNOUSERSITE=0`, run from the save state
with `blastem -d -s <state> <rom>`, breakpoint on `test_spin`, words
read via debugger `p/x`. Scratch ROM at `$FD400`, VBlank hook at
`$1272` (original 8 bytes `33fc000000ff0016` replaced by `jmp $FD400` +
`nop`; probe replays the move and returns to `$127A`). A `jsr` hook must
exit with `rts`, never `jmp` (exception: one-shot boot hook); a `$1272`
VBlank hook must exit with `jmp`, never `rts`. RAM logs must stay below
the stack pointer `$FFEC1E` (safe region `$FFD800`–`$FFEC1E`). Use the
venv python (`~/workspace/rings-of-power/tools/.venv/bin/python`) for
anything needing capstone. Probe ROMs live in the scratch dir
(`/tmp/rop275/probe/`), never delivered. Probe bugs seen and fixed: a
helper clobbering %a0 (the log write pointer) invalidates the log;
sed-deriving probe scripts mangles `probe_o5b` → `probe_o5cb` in
filenames — check generated names after sed.

## Open items

- **O1 — Bandit HQ: CLOSED statically (2026-11-24).** Anchor 321, key
  (307,181) = 30°7′/18°1′, room 164 — see Location. Residual wrinkle:
  the +5 byte is not a unique sextant-text id (shared by 8 anchors),
  and the kind-24 b4=41 city/topic mapping table was not pinned.
- **O2 — Entry gate: sub-items CLOSED statically (2026-11-24); residuals
  open.** (a) Entry-time repaint and USE-time paint touch the same grid
  (same routine, same `$D601E` record fields — see "What event 143
  does"). (b) `$03B224` is a `damage_calc` flat-damage-70 comparison,
  unrelated to bit 143. Residual: does anything check bit 143 (or the
  painted tile) before `world_location_transition` to room 170, and
  what tile the door cell holds before the paint.
- **O3 — Double-Rashiid spawn: CLOSED statically (2026-11-24); live
  confirmation deferred.** Read from `world_enter_location` (`$03090A`)
  template loop (d6 = 0..461): branch-1 key match OR branch-2
  (`$D1CFC+10*A` byte == template key low 10 bits), nibble match, then
  gates (`sys_copy_stride6_2d284(0, template)` → if −1,
  `world_seen_check` must be 0; else the event bit must be set;
  `sys_struct24_read` ≠ 0), then `entity_spawn(1, -1, template, -1, 0,
  0, 0)` + `npc_place_group(char, x=template byte 2, y=template byte
  3, heading=(locword>>6)&3)`. No dedup by position, spawn, or
  template. Template 28 (branch 1, key 170) and template 27 (branch 2,
  key 29 — anchor 170's branch-2 byte is 29) both match, both at (5,3),
  heading 2, spawnlist [71,72,72] = Rashiid + 2 Men, each with its own
  seen-ring entry — so first entry to room 29 via anchor 170 spawns two
  Rashiid groups (6 NPCs stacked at (5,3)); thereafter both are
  seen-gated and neither respawns. Template 27 also spawns alone at
  anchor 356 (same branch-2 byte 29). NOTE: anchor 170 is also the
  live-test anchor for issue #273 item 2 (branch-2 intent); a separate
  worker is testing it — the coordinator reconciles. The step
  encounter's released NPC (case 6, `$0328BC`) remains unpinned, as
  does the (0x14, 0x0D) message-args note in `docs/maps.md:393`.
- **O4 — Darius fight trigger: invocation CLOSED statically, fight
  trigger mechanism live-proven (2026-11-24).** Greeting 666 is
  `$D3102` idx 570 (kind 10, identity 2472 = Darius) via the TALK
  path; the monologue 667–679 is the `sys_event_run` case-7 script
  `$1A520` (dialog live-proven); the case-7 invocation path from
  dialog EXISTS (rec570 `w8=0x4007` → second-dispatch arm 4 →
  `menu_select_screen(7)`) — the issue's "no in-dialog invocation"
  premise was false (swapped dispatch model, corrected above). Bark
  680 is `$D3102` idx 584 (kind 10, identity 0, hostile, no menu) and
  is a VOID-cultist family bark (recs 584–588), not Darius-specific.
  The fight trigger is proven end-to-end at the mechanism level:
  `world_scan_ahead_for_char` pairs a facing type-4 Darius
  (probe_o4e: leader+`0x29` = 53, Darius 53's +`0x29` = 0) and op-0's
  `combat_battle_end` starts the battle iff that link is set and both
  groups are alive; the direct pairing tail is proven separately
  (probe_o4d). The type-1 scan run was negative-but-clean (the scan
  pairs only type-4 chars); the `$FF02A0`-mismatch scan run (probe_o4c)
  hung twice in the merchant-setup branch with a fabricated
  non-merchant char (probe artifact, see the wedge note in the Darius
  section). Remaining: the full probe C (TALK to Darius in real Kaos
  game state, verb-menu options, fight trigger / case-7 arming) and
  probes A/B (fabricated endgame state → Holy Seal → room 170 →
  Darius at (15,9); bit-144 clear → walk north past Y=20 in room 170 →
  spell effect 9 → text 1121) — both need pad-injection /
  game-driving, unlike the function-call probes used here; static
  evidence for both is strong.
- **O5 — Ring grants for codes 642/643/647/649: CLOSED statically +
  live (2026-11-24).** All four granted by dialog via first-dispatch
  arm 6 (`$029B0C`): 643 Division rec313, 642 Intuitin rec442, 649
  Calling rec448, 647 Mutation rec497 — see "The four dialog ring
  grants". Live-proven by probe_o5/o5b (grants + handover consumption +
  the Intuitin `+0x17`=52 mechanism) and probe_o5c (Holy Seal gate).
  Residuals: the seal ITEM 861 obtainability (no consumer in the two
  `$D601E` dispatchers, no dialog grant — shop stock / type-4/5/6
  readers unenumerated); the rec442 fight-arm live effect (statically
  traced only); the event-15 SET live delta (bit already set in slot_0);
  which enemies map to the battle-end type-5 ring events 71/140/160.
- **O6 — What happens inside room 170: partly closed statically
  (2026-11-24); the room-170 aftermath is still open.** Closed: leader
  `$02BA` is char struct `+0x06`, the packed vessel value; `+0x06` ==
  1 means travel mode 1 = Dino. The `$0217AA` text-1122 path is in
  `world_tick` (`$02155E`): every 50 ticks (`$FF0144 % 50 == 0`), in
  the out-of-bounds/edge block keyed on `$FFC364`/`$FFC366`, if
  leader+`0x06` == 1 → `text_show_message(0x15, 0x04)` → text 1122,
  followed by `npc_leader_init` + `npc_spawn_adjacent` + song pick +
  SFX 20 (a leader respawn/teleport sequence). The sibling check at
  `$021676` (`leader+0x06 - 4 == 0` → Dragon) plays SFX 36. Per
  `docs/logic.md`, no live Dino spawn exists from any save in the
  shipped ROM (the Q15 vessel block `$02C212` is dead code; live
  vessels come only from statues: DragSt → Dragon `+0x06`=4, BoatSt →
  Boat `+0x06`=2), so the `$0217AA` 1122 path is effectively unreachable
  in normal play — reachable only via a fabricated state forcing
  `+0x06`=1 (or a mode-2 Dino spawn). That is the answer with its
  caveat, not a live proof. TALK-to-Darius repeat: nothing in the
  case-7 script sets a "done" bit (no op-11); greeting 666 (rec570)
  re-wins scoring on repeat TALK (ident match 2472→424) and
  `menu_select_screen(7)` re-arms the monologue each time, until the
  fight happens. After victory, `npc_attitude_adjust` clears bit 144,
  so Darius no longer spawns in room 170 and repeat TALK there is
  impossible; at Kaos before the fight, repeat = greeting → menu →
  monologue again. Still open: what happens inside room 170 after
  entry (TALK to Darius at (15,9) — probe C, not yet run); whether the
  spawn-table-28 "Woman" appears anywhere or is Nexus; the callers of
  texts 1121/1122 beyond the paths pinned above; any routine that runs
  after the Darius victory (picture sequence, `intro_helper`-like
  loop, reset/attract return, or nothing).
- **O7 — `$015400` region.** The `$15C08` callers at `$0154EC` /
  `$01550C` / `$01553A` are all inside `intro_helper`
  (`$015012`–`$015BB7`); the `$0195BE` caller is in the title region.
  No further action unless a new ending-candidate caller appears.
