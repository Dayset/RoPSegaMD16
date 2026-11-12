# Cutscenes — complete inventory

> **The checklist.** Every cutscene (event script) in the game, starting from
> Buc meeting Thalmus. Each row: scene name, script address, entry (which
> NPC/dialog/location triggers it), one-line summary, and status. The list is
> **complete** — a static-only row with its address and entry is here rather
> than missing. Per-scene detail lives in `docs/cutscene-<name>.md` behind
> each row; this file is what to read first.

## Enumeration — closed

The set is bounded by construction. `menu_select_screen` (`$02D3DC`) has a
10-word dispatch table at `$02D480` (base `$02D4A4`; target = `$02D4A4` +
word, verified against ROM bytes) — exactly 10 cases, cases 0–9. `sys_event_run`
(`$02D56A`) has exactly one caller (`$022778` in `combat_turn_run`,
`$0226BC`); `$FFC384` is written only by `menu_select_screen` (10 sites)
plus the pointer advance (`addq.l #8` at `$02DBFA`). All 10 scripts were
decoded in full (198 records total; decode in
`.scratch-cutscenes/decode_all.txt`, decoder `decode_scripts.py`): all end
in op-0, no overlaps, no sharing. A second `menu_select_screen` caller
exists (`$0368D8` in `combat_battle_start`, `$0362D6`) but it passes a
hardcoded 8 behind two gates that cannot both pass — dead code (case 8).

The 11th row is the final animation (game completed, 11 rings found). It
is **not** a `menu_select_screen` case: the ending is driven by the
item-USE dispatcher (the Holy Seal gate, `$02DD9A`) plus the normal
location-transition system, with the Darius monologue as case 7. See
`docs/cutscene-final-animation.md`.

## The engine in brief

`sys_event_run` (`$02D56A`) executes 8-byte records from the pointer in
`$FFC384`. Record layout: byte 0 = signed opcode (negative byte 0 chains,
non-negative pauses), byte 1 = b1, byte 2 = b2, byte 3 = b3, bytes 4–5 =
w4 (big-endian), bytes 6–7 = w6 (big-endian). Call chain: main loop
`$D28E` → `combat_turn_run` (`$0226BC`, gates `$FF0110 != 0`, grid+`$A`
== 0) → `sys_event_run` → opcode handlers (dispatch table `$02DBB8`,
base `$02DBE8`; target = `$02DBE8` + word, recomputed from ROM bytes —
all 16 verified). Entry: TALK to an NPC → `npc_attitude_positive`
(`$0298D2`) → `menu_select_screen` (`$02D3DC`) → case → `$FFC384` +
`$FF0110 = $FFFF`.

### The +96 rule — read this before trusting any dialog number

Op-6 displays text record **w4 + 96**, not w4. The op-6 handler (`$02D964`)
calls `text_event_resolve(3, 11, w4)` (`$032D4C`); arg1 = 3 dispatches via
the table at `$032DDE` to `$032D9E`, which does `add.w #$60,d0` (+96).
The same +96 applies to the TALK greeting path (`shop_record_score`,
`$0331A4`, returns best + 96 via `add.w #$60` at `$03373C`) and to op-15's
`text_event_resolve(3, 11, …)` call. The resolver has other offsets for
other callers (arg1 = 4 → +1101, arg1 = 2 → +58, arg1 = 1 → +0) — the
+96 is specific to the op-6 / kind-11 path.

This overturned the pre-work readings of **every** scene, including the
landed Buc doc: its dialog is records 221–226, not 125–130 (see "Known
corrections" below). Every dialog line in the per-scene docs is quoted at
the shifted (displayed) number; the raw w4 is shown alongside it.

### Opcode table (handlers verified from the `$02DBB8` table bytes)

| Op | Handler | What it does |
|---|---|---|
| 0 | `$02D5D4` `sys_event_op0_grant` | Party XP (`xp_grant` `$02C4E2` per member, w6) + dialog unlock; clears `$FF0110` |
| 1 | `$02D802` `sys_event_op1_teleport` | Teleports the party leader's attitude-resolved char to (b1, b2); ignores w4 |
| 2 | `$02D892` `sys_event_op2_spawn` | Spawn a char |
| 3 | `$02D852` `sys_event_op3_place` | Place a char |
| 4 | `$02D8F4` `sys_event_op4_spawn` | SFX + mode-6 projectile spawn (via `npc_spawn_at_step` `$02B190`) |
| 5 | `$02D7D6` `sys_event_op5_move` | Move a char (via `combat_move_unit` `$024984`, through `npc_attitude_raise_by_id` `$02D50C`) |
| 6 | `$02D964` `sys_event_op6_text` | Enqueue text record **w4 + 96** (speaker: `npc_attitude_raise_by_id`(w6), or b3 if w6 == `$FF`) |
| 7 | `$02DA0A` `sys_event_op7_check` | Attacker check — husks the target (`combat_attacker_check` `$023AE0`, type → `$A0`); scaffold fan-out via `sys_struct52_nibble_read` `$025B4E` |
| 8 | `$02DA3E` `sys_event_op8_kill` | Kill a char: clears +`$1C` cur HP, sets status bit 13 (dead), SFX 91 |
| 9 | `$02DAB4` `sys_event_op9_stage` | Stage leader return coords: `$FF0E9A` = w4, `$FF0E9C` = w6 |
| 10 | `$02DAD4` `sys_event_op10_flush` | Flush + SFX |
| 11 | `$02DB06` `sys_event_op11_event` | `npc_attitude_event_apply` (`$02B6E0`, w4, b3) — event-bit write + location-gated tile/grant/spawn |
| 12 | `$02DB2A` `sys_event_op12_noop` | No-op |
| 13 | `$02DB2E` `sys_event_op13_pose` | Cast pose (draw-record heading/template) |
| 14 | `$02DB88` `sys_event_op14_step` | Step |
| 15 | `$02D67C` `sys_event_op15_resolve` | Text-event resolve (`world_find_char_template` `$031998` + `text_event_resolve(3, 11, …)`) |

Two corrections to the landed Buc doc's opcode table are baked in here:
op 1 is `$02D802`, **not** `$02D67C` (that is op 15's handler, and it is
not a teleport); op 11's arg order is (w4, b3). The `sys_event_op1_teleport`
name was mis-assigned at `$02D67C` in `disasm/symbols/auto.csv` before this
change; it now lives at `$02D802`, and `$02D67C` is `sys_event_op15_resolve`.

Text records: `disasm/text/records_ddbd8.txt` (1,184 records, type 5).
Char struct: 52 B at `$FF02B4`; id→char via `npc_attitude_raise_by_id`
(`$02D50C`), which returns the attitude byte at char[nameIdx].+`$26` —
the w4→char mapping is **per-scene**, from the char setup at entry. Do not
carry one scene's mapping onto another.

## The checklist

`[x]` = identified and documented (doc linked; draft unless noted).
Status carries live-verified vs static-only and open items, per scene.

|  | Scene | Script | Entry | What happens | Status | Doc |
|---|---|---|---|---|---|---|
| [x] | **Thalmus dies** (case 0) | `$19F90` (83 recs, ends `$1A220`, 65 XP) | TALK to Thalmus, menu option → case 0 | The game's opening: Thalmus lectures on the Rings of Power and the Rod of Creation; Darius fires twice south at him (no damage on contact); Thalmus dies by script (op-8) and disperses the students; the party wakes outside a strange city seeking Hack. | Script flow, walk, firing, kill, op-7/op-11 **live-verified** (probes k–k7); dialog text static (probes logged message counters only, content re-read at shifted numbers); entry menu text, post-scene transition trigger, location 15 open. | `docs/cutscene-thalmus-death.md` |
| [x] | **Buc, the STUN lesson** (case 1) | `$1A228` (46 recs, ends `$1A390`, 25 XP) | TALK to Thalmus, menu option → case 1 | Thalmus demonstrates STUN, firing four shots west at the wall while his five students stand by; students protected twice (aim + collision). | **Documented on main** (`docs/cutscene-buc.md`); walk/fire/exit live-verified; **dialog correction pending** (125–130 → 221–226) and 7 further deltas — see below. | `docs/cutscene-buc.md` |
| [x] | **Imino, Ring of Advancing** (case 2) | `$1A398` (3 recs, ends `$1A3A8`, 0 XP) | TALK to Imino (identity 2289), menu option 10 → case 2 | Imino found the Ring of Advancing on Old Richi and challenges Buc to take it from him (2 lines + exit grant). | Dialog **live-verified** (probe_case2); speakers, exit transition, location number static-only. | `docs/cutscene-imino-ring-of-advancing.md` |
| [x] | **Thespian, false mustache** (case 3) | `$1A3B0` (1 rec, op-0, 0 XP) | TALK to the thespian (identity 2432), menu option 25 → case 3 | The thespian hands Buc his false mustache (entry grant: item-flag bit 20 + song 8); the script is a 1-record unlock. | **Static-only** (no theatre save state on hand). | `docs/cutscene-thespian-false-mustache.md` |
| [x] | **Tutu's tower** (case 4) | `$1A3B8` (33 recs, ends `$1A4B8`, 500 XP) | TALK to Tutu, event 406 → case 4 | Buc walks into the Great Enchanter Tutu's tower, is frozen and imprisoned, and is offered help by Fiver, who works for Tutu. | **Static-only** (`slot_0` resolves neither 389 nor 218). | `docs/cutscene-tutu.md` |
| [x] | **Yoppa, Ring of Will** (case 5) | `$1A4C0` (5 recs, ends `$1A4E8`, 0 XP) | TALK to Yoppa (identity 107), menu option 10 → case 5 | Buc demands the Ring of Will; Yoppa refuses under the High Priest's orders to deliver it to the Temple and tells Buc he must fight him for it (4 lines + exit grant). | **Static-only** (mechanism live-proven via cases 2/7; a case-5 probe is a cheap follow-up). | `docs/cutscene-yoppa-ring-of-will.md` |
| [x] | **Fezzik, Ring of Perfection** (case 6) | `$1A4E8` (7 recs, ends `$1A518`, 0 XP) | TALK to Fezzik, event 540 → case 6 | Buc brings the Sun and Moon gems; the gems are fitted, the Ring of Perfection materializes — and Fezzik takes it. No ring is granted anywhere in the scene. | **Static-only** (`slot_0` lacks template 342). | `docs/cutscene-fezzik.md` |
| [x] | **Darius, endgame monologue** (case 7) | `$1A520` (14 recs, ends `$1A588`, 0 XP) | TALK to Darius (identity 2472), menu option 10 → case 7 | Darius reveals he let the others find the Rings while he waited in Kaos, thanks Buc for bringing him all eleven, and reveals VOID (13 lines + exit grant). Greeting 666 arrives by the TALK path; bark 680 ("Die Sssorcerer sscum!") is a hostile TALK, not in the script. | Dialog **live-verified, all 13 lines** (probe_case7); speakers, exit transition, location number static-only. | `docs/cutscene-darius-endgame.md` |
| [x] | **Case 8 — battle-start stub** | `$1A590` (5 recs, ends `$1A5B0`, 0 XP) | **None reachable** | Op-15 resolution + three no-ops + 0 XP. Its only other caller (`$0368D8` in `combat_battle_start`) is dead code: two gates that cannot both pass. | **Static-only, unreachable.** | `docs/cutscene-case8.md` |
| [x] | **Case 9 — 50-XP grant** | `$1A5B8` (1 rec, op-0, 50 XP) | **None found** | A single op-0 granting 50 XP; no TALK trigger, no caller passes 9. Possibly a vestigial reward for a removed quest step. | **Static-only, unreachable.** | `docs/cutscene-case9.md` |
| [x] | **Final animation** (11 rings) | Gate `$02DD9A` in `sys_dispatch_action_2dcce` `$02DCCE` (no `sys_event_run` script) | USE the Holy Seal (code 867) at loc 392 with all 11 ring bits (codes 640–650) set on the leader and event bit 143 clear | The only all-11 check in the ROM opens the Fount of Heaven door (white flash + tile 275 painted at (15, 27), event 143) and leads into room 170, whose sole occupant is a "Woman" (spawn 28). No dedicated ending routine, picture sequence, credits, or "The End" text exists. | **Static-only**; open items O1–O7 (entry gate, door guardian, Darius fight trigger, 4 unaccounted ring grants, room-170 contents). | `docs/cutscene-final-animation.md` |

## Status summary

- **Dialog text live-verified (message buffer logged):** cases 2, 7. Case 0's
  script execution is live-proven (probes k–k7) but its probes logged
  message counters only, so its dialog text is static (re-read at shifted
  numbers from the corpus). Case 1's walk/fire/exit are live-proven; its
  dialog text is static and currently misquoted in the doc (pending
  correction). 2 of 10 menu scripts have live dialog-text proof.
- **Static-only:** cases 3, 4, 5, 6, final animation. The only save state on
  hand is `slot_0` (location 156, Thalmus's room, mid-game); scenes whose
  actors do not resolve in it cannot be probed without a new save or a
  forced char setup.
- **Unreachable in the shipped ROM:** cases 8, 9.
- **No scene casts a spell record.** Case 0 and case 1 both fire mode-6
  projectiles (op-13 pose + op-4 spawn) that look like spells and are not:
  no spell record is referenced, no Power is deducted, the spell system
  never starts. The projectiles cannot hurt friendlies on contact — the
  collision-level protection is live-proven in case 0 by the shipped scene
  with no patch (Thalmus stays 140/140 through both impacts).

## Known corrections to the landed Buc doc (`docs/cutscene-buc.md`)

The Buc doc landed as PR #224 before the +96 rule and the handler
corrections were found. Its conclusions stand, but these deltas are owed
(listed, not applied — the file is on main):

1. **Dialog 125–130 → 221–226** (the STUN lesson; supports the doc's STUN
   reading). Text 130's "speaker 36" open item carries over to 226.
2. **Op-1 handler is `$02D802`, not `$02D67C`** (that is op 15's handler).
   Conclusion "Buc teleports to (6,17)" still holds via the
   leader-attitude indirection.
3. **Op-15 row is backwards** (`$02D67C` *is* the op-15 handler).
4. **Op-6 row is missing the +96** (enqueue w4+96 via
   `text_event_resolve(3, 11, w4)`).
5. **Op-11 arg order is (w4, b3)**, not (b3, w4).
6. **Op-7 row overgeneralizes** the w4 = 2 instance (El Gripa); the general
   mechanism is `combat_attacker_check` husking + the scaffold fan-out.
7. **El Gripa's name is 76, not 95** (95 is his `+0x02` id; 76 is `+0x14`).
8. The final-animation doc's earlier "sys_event_run ruled out" claim is
   already corrected in that doc (case 7 is the Darius script).

## Live-proven vs static-only — how to read it

"Live-verified" means observed on a running game in BlastEm 0.6.3.4 from
the `slot_0` state (`~/workspace/user/files/slot_0_1_ou3l.state`), with
the script pointer injected (`$FFC384` = script, `$FF0110` = `$FFFF`) —
probe logs in `.scratch-cutscenes/case0-1/` (probes k–k7) and
`.scratch-cutscenes/case2-3-5-7/` (probe_case2, probe_case7). Injection
bypasses the TALK menu, so entry menu text and the pre-menu greeting are
static-only everywhere except where the `$D3102` record pins them.
"Static-only" means traced to ROM bytes / `disasm/src/rop.s` and quoted
verbatim, but never run. Nothing here claims live proof it does not have.

## Open items (by scene; detail in the per-scene docs)

- **Cases 0/1:** which TALK-menu option text yields case 0 vs case 1; the
  post-scene transition trigger and the identity of location 15 / (164,122);
  the per-tick mode-6 stepper (unlocated — the remaining piece for a fully
  "protection off" ROM); whether the mode-6 effect corresponds to Stun
  mechanically (remake design question).
- **Case 2:** exact Richi room / location number; `combat_battle_end`
  branch after op-0 w4 = 1.
- **Case 3:** confirm item-flag bit 20 is the false mustache (find the read
  site testing bit 20 of `$FFC340`); Lucius's location and which spell text
  494 grants; needs a theatre save state to probe.
- **Case 4:** tower record 389 vs 391; tile 274/275/263/264 visuals; op-15
  fallback message; bit-174 setter.
- **Case 5:** confrontation site (unknown); optional case-5 probe for its
  own live log.
- **Case 6:** whose portrait 13 is; where the Ring of Perfection goes (no
  grant of 650 exists anywhere; no reader of bit 100 found); the gem-check
  contradiction (637 then 638 unconditionally).
- **Case 7:** Darius's char-slot setup in Kaos; the fight trigger after the
  monologue; who says text 680.
- **Case 8:** ever reachable in an earlier build? What the `+14` == 251
  templates share; template 424's role at record 60.
- **Case 9:** what it rewards, if anything; any path outside
  `menu_select_screen` that reaches it.
- **Final animation:** O1–O7 in `docs/cutscene-final-animation.md`
  (loc-392 identity, entry gate, door guardian, Darius fight trigger, 4
  unaccounted ring grants 642/643/647/649, room-170 contents, `$015400`
  region).
- **Engine:** the grid+`$A` (`$FFB0B6`) writer / cycle driver (gates
  `sys_event_run` calls); the `$0A`-execution gate during the pan; op-0
  w4 meaning (0 vs 1 across scripts).
