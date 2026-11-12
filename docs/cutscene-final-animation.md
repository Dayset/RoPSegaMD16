# Cutscene: The Final Animation (game completed, 11 rings found)

> **Status: static-only identification — NO live proof.** Every claim below is
> traced to a ROM address, but nothing in this document has been observed on a
> running game. The "final animation" as coded is **not a single dedicated
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
| Trigger | `USE` the Holy Seal (item code 867) while standing on location 392, with all 11 ring bits set on the leader and event bit 143 clear |
| Gate routine | `$02DD9A` inside `sys_dispatch_action_2dcce` (`$02DCCE`) — the **only** "all 11" check in the ROM |
| Driver | Mixed: the Darius monologue IS a `sys_event_run` script (case 7, `$1A520`); the Holy Seal gate is a branch of the item-USE dispatcher, followed by the normal location-transition system; not `intro_helper`/`snd_music_start` |
| Final battle | vs Darius (spawn 105, name idx 145) — greeting 666 (TALK path) + monologue 667–679 (case-7 script) + bark 680 (hostile TALK), at Kaos per text 668 |
| Door location | Loc 392, key (12, 184), destination room 170, `$FF013E` = 6 (scripted encounter) |
| Room 170 | Fount of Heaven interior, placement (15, 30), song 7; sole placed occupant is spawn-table 28, name idx 2 "Woman", at (5, 3) |
| Live-proven | **None.** Static analysis only. |

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
Mutation, Calling) — presumably granted via direct `$2BBD2` calls or
battle-end grants; not yet traced (open item O5).

Battle-end grant path (`npc_attitude_adjust`, `$035656`): `$2D284`
(`sys_copy_stride6_2d284`, `$02D284`) returns an event index; if its bit
is set in `$FFC326`, the `$D601E[ev]` code (`& 0x7FF`) is granted via
`inv_apply_resource` and the bit is cleared; else `$FFC410 = 0x7530`
(30000 default). Type-5 records set only the event bit (no dispatch
action) — their ring grant comes from this battle-end path. Which enemy
maps to which ring event is not yet traced (open item O5).

### The "all 11" check — the trigger

`sys_dispatch_action_2dcce` (`$02DCCE`), branch at **`$02DD9A`** — reached
when verb `$8(a6)==0xD` (USE item) and item-minor `$a(a6)==29` (Holy Seal:
items cat 13, `w=153`, minor 29 → price record 182 "H Seal"; code 867).
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
no bit-143 check has been found there. Open item O2: find what, if
anything, blocks stepping onto the anchor before the gate opens, and what
tile the door cell holds before the paint.

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
`w1=424` (`$CF1C0` record index), b4=b5=0. Its firing route is **not
fully pinned**: the only `$D3102` record whose event word has delta 144
is rec 143 (event id 9, match key `0x869` → 105 = Darius's spawn-table
index; +10 word delta 144 → first-dispatch type 0 → text re-resolve +
enqueue). Which NPC appears at the door, and whether the step encounter
is Darius or someone else, is unpinned (open item O3).

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
  Darius, menu option 10 → case 7, script `$1A520` (13× op-6, w4
  571–583, speakers `w6=424` Darius ×11, `w6=0` Buc ×2), then op-0 exit.
  Dialog live-proven, all 13 lines (probe_case7; see
  `docs/cutscene-darius-endgame.md`).
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
  not Darius.

Darius: spawn-table record 105 (`$CECF0` rec 105: `00 91 25 16 01 00`,
name idx 145 = "Darius"). The other four ring-holders of text 668 are
spawn 101 Roakus, 102 Imino, 103 Yoppa, 104 Fezzik (name idx 141–144).

The dispatch tables are decoded — first dispatch `$029F8A` (15 entries, on the +10
word type): type 0 → `$029F32` (re-resolve text via `$32D4C` `$b=0xB` +
enqueue), type 12 → `$029ADA` (event apply, flag 1), type 13 →
`$029AF4` (event apply, flag 0), type 4 → `$02A17C`
(`menu_select_screen(delta)`); second dispatch `$02A1EE` (14 entries,
on the +8 word type): type 3 → `$02A19A` (delta subtract chain: 0 →
fight via `combat_select_unit` + `menu_set_mode`, 8 → song 8) — a
candidate for the fight trigger after text 680 — and `shop_record_score`
(`$0331A4`) picks the winning `$D3102` record by score (`0x4000` if
record+2 matches char `+0x02`, `0x10000` if the event id matches `$9(a6)`,
+ RNG `0x400`). But the fight trigger after the monologue / after text
680 is **not pinned** (open item O4).

The combat-victory path is `npc_attitude_adjust` (`$035656`): gold/XP
split, then the `$2D284` event lookup → grant (see Entry / trigger).
`$FFC40A` = battle-won flag; `$FFC40C` gold total; `$FFC40E` XP total.
No post-victory routine specific to Darius/Void has been found — no
routine runs after that victory that has been identified as an ending
sequence (open item O6).

### Room 170 — the Fount of Heaven interior

On entering location 170, `world_enter_location` (`$03090A`) scans the
`$CF1C0` placement table (462 records × 24 bytes) for records whose
locword matches (low 10 bits == 170, hi nibble == 3). One record matches:

- **Rec 28**: loc word `0x38AA` (loc 170, hi 3), b3=5, b4=3, b6=27,
  b8=27, b18=`0x20`, trailing `0x5A 0x5A`.

Gate: `sys_copy_stride6_2d284(0, 28, NULL)` returns −1 (no type-0
`$D601E` event has `w1==28`), so `world_seen_check(28)` must be 0 and
`sys_struct24_read(28)` must be nonzero; then `entity_spawn(1, -1, 28,
-1, 0, 0, 0)` + `npc_place_group(heading 2, x=5, y=3)`. Spawn-table
record 28 (`$CECF0` rec 28: `00 02 4c 1c 09 02`): **name idx 2 =
"Woman"** (`$CD430` base verified: 141 Roakus, 142 Imino, 143 Yoppa, 144
Fezzik, 145 Darius, 2 Woman). Whether this "Woman" is Nexus, or a
generic NPC, is **unproven** — no dialog record for her has been pinned
(open item O6).

No `$D601E` event has `w1 == 28` (no type-0 event points at `$CF1C0`
rec 28 / room 170 directly); event 144 points at rec 424 (loc 392).

### What the "final animation" actually is

Putting the chain together, the visible ending sequence as coded is:

1. Darius's confrontation at Kaos: greeting 666 (TALK path) → monologue
   667–679 (`sys_event_run` case-7 script `$1A520`, dialog live-proven)
   → bark 680 (hostile TALK) → the final battle.
2. At the Fount door (loc 392): USE the Holy Seal → text 1119, an
   all-white palette flash (`$CCC58`), SFX 19 + SFX 1, and tile 275
   (Road) painted over the door cell at (15, 27) — the door opens.
3. The door ambience (1/8-per-tick palette `$0CCCD8` + SFX 19) and the
   step encounter (spell effect 9, 10-frame tile fly-in) at the same
   anchor.
4. Entry into room 170 (song 7, placement (15, 30)) and the "Woman"
   standing at (5, 3).

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
| "Woman" | Spawn-table 28, name idx 2 (`$CECF0` rec 28: `00 02 4c 1c 09 02`) | Room 170, at (5, 3) — Nexus? Unproven |
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

## Live-proven vs static-only

**Everything in this document is static-only.** No live run has been
done; no completed-game save exists (only the `slot_0` mid-game state).
Nothing here should be presented as observed behaviour.

### What a live probe would need (design on paper — not built)

Probe A — the Holy Seal gate (honest, forceable):

1. Start from the `slot_0` mid-game state.
2. Force the leader's ring bits: set bits 0–10 of the word at leader
   char struct `+0x2E` (char struct base `$FF02B4`, 52 bytes per char).
3. Force the Holy Seal: set bit 29 of the items bitmap `$FFC340`
   (items cat 13, minor 29; Q13 handler, `item_category_of` Q13 /
   `inv_apply_resource` Q13).
4. Warp to loc 392 (set `$FF0E92` low 10 bits = 392, `$FF0E98` = 170,
   `$FF013E` = 6, and the matching chunk/placement state), or walk there
   from a nearby anchor.
5. USE the Holy Seal (verb `0xD`, minor 29) and log: the shown text
   (1119 vs 1120), `$FFC326` bits 143/144, `$FF0124`, the tile word at
   grid offset (15, 27) before/after, and `$FF0E98` after stepping onto
   the door.
6. Step onto the door cell and log room-170 entry, the spawned NPC
   (expect spawn-table 28, "Woman", at (5, 3)), and song 7.

What forcing proves and what it does not: it proves the gate logic
(count, texts, flash, tile paint, transition) fires when the state is
as the game would leave it after collecting the rings legitimately. It
does **not** prove the rings can actually be collected that way, that
the Darius battle leads here, or that the door is impassable before the
paint — the pre-paint tile and any bit-143 transition check are still
open (O2). Every forced value must be logged as forced.

Probe B — the Darius talk (now specifiable): TALK to Darius (spawn 105)
with the `$D3102` event-9/50 state and log the resolved record and the
texts shown. The greeting path is pinned (`$D3102` idx 570, kind 10,
identity 2472 → text 666), then the menu → case-7 script `$1A520`
(667–679) → op-0. Still open: the combat start after the monologue /
after text 680 (O4).

Probe C — room 170 after entry: TALK to the "Woman" (spawn 28) and log
every text shown, any event-bit changes, and any mode change. This is
the probe that would settle whether there is any further ending
sequence (O6).

Harness rules if built: BlastEm 0.6.3.4 at `/usr/games/blastem`,
`DISPLAY=:99`, reuse the running Xvfb, `SDL_AUDIODRIVER=dummy`, batch
mode `blastem -b <frames> <rom>`, results via EEPROM payload at
`~/.local/share/blastem/<romname>/save.eeprom`. A `jsr` hook must exit
with `rts`, never `jmp` (exception: one-shot boot hook); a `$1272`
VBlank hook must exit with `jmp`, never `rts`. RAM logs must stay below
the stack pointer `$FFEC1E` (safe region `$FFD800`–`$FFEC1E`). Use the
venv python (`~/workspace/rings-of-power/tools/.venv/bin/python`) for
anything needing capstone. Probe ROMs live in the scratch dir, never
delivered.

## Open items

- **O1 — Pin loc 392's identity on the world map.** Confirm (12, 184)
  is the Fount door (vs e.g. a signpost) using `docs/maps.md` anchors /
  sextant mapping; check which overworld chunk holds it and what tile
  the door cell holds before the paint (decode chunk 247, or note as
  static-only). Reconcile with the walkthrough's "Bandit HQ 30′-18′".
- **O2 — Pin the entry gate.** Does anything check event bit 143 (or
  the painted tile) before `world_location_transition` to room 170?
  Search `sys_struct52_flag_test` (`$026834`), `world_step_event`, and
  bitmap-test sites for `0x8F`/`0x90`. Also decode the pre-paint door
  tile at grid offset (15, 27).
- **O3 — The door guardian.** Find who sets event bit 144, which NPC
  the step encounter (case 6, `$0328BC`) releases, and whether the
  greeting message path is `npc_show_greeting` or a `$D3102` record.
  The (0x14, 0x0D) message args noted in `docs/maps.md:393` do not
  resolve cleanly to a sensible text under the +1101 rule (13→1114 "You
  make camp until dusk") — unresolved.
- **O4 — Darius dialog trigger (largely pinned, 2026-11-12 assembly).**
  Greeting 666 is `$D3102` idx 570 (kind 10, identity 2472 = Darius)
  via the TALK path; the monologue 667–679 is the `sys_event_run`
  case-7 script `$1A520` (dialog live-proven); bark 680 is `$D3102`
  idx 584 (kind 10, identity 0, hostile, no menu). Remaining: the
  fight trigger after the monologue / after text 680 (second-dispatch
  type 3 → `combat_select_unit` + `menu_set_mode` is a candidate), and
  which NPC says text 680 (identity 0, gated by the +4/+5/+6 match
  keys). The earlier rec 659 (660) / rec 674 (675) / rec 143 hypotheses
  are superseded by the idx 570 / 584 pinning.
- **O5 — Ring grants for codes 642/643/647/649.** Find their grant
  sites (direct `$2BBD2` immediates, battle-end events, or other) to
  complete the "11th ring obtained → ending" chain. Also trace which
  enemies map to the battle-end type-5 ring events 71/140/160.
- **O6 — What happens inside room 170.** Resolve the "Woman" (spawn
  28): is she Nexus? What does TALK to her do — texts 1121/1122, a ring
  hand-over, a further sequence, or nothing? Find the callers of texts
  1121/1122. Trace the combat-victory path for the Darius/Void enemy
  (`$2D284` event → `$D601E` code → grant?) and search for any routine
  that runs after that victory (picture sequence, `intro_helper`-like
  loop, reset/attract return, or nothing).
- **O7 — `$015400` region.** The `$15C08` callers at `$0154EC` /
  `$01550C` / `$01553A` are all inside `intro_helper`
  (`$015012`–`$015BB7`); the `$0195BE` caller is in the title region.
  No further action unless a new ending-candidate caller appears.
