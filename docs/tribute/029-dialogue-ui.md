# #029 — Dialogue & UI spec

Status 2026-11-09: **spec complete** from #004 + #020 evidence;
implementation waits on #023 + #024 text export.

## Verb list (verified from the `0xCCDB8` verb table, #020)

Menus are 14-byte records `[10-byte name][A][B][C][grp]` under
12-byte headers. Implement these sets verbatim
(`disasm/main-loop/verb_menus.txt`):
- **MAIN:** Inven, Spells, Party, Search, Map, Camp, System
- **FIGHT:** Flee, Berzrk, Advnce, Hold, Wary (+ separator)
- **MOOD:** Berzrk, Advnce, Hold, Wary (C=1–4)
- **PARTY:** the six disciplines **Sorc, Knight, Archer, Necro,
  Enchnt, Conjur** (grp 2, C=0–5) — named in ROM; the character is
  **Feather**, not the guide's "Arrow" (#020 settled this)
- **TACTIC:** Asasin, GangUp, Cover, Guard
- **BUY/INVEN/USE/SYSTEM** shop sets; Goods/Items/Papers C values
  (14/13/17) match #007 item categories; Keys (105) / Rings (102)
  do NOT match their categories (12/10) — reproduce the ROM values,
  the mismatch is recorded as unexplained in #020.
The issue's shorter verb summary (talk / inventory / bribe / buy /
sell / fight) maps onto these menus; the ROM table is the authority.
**One verb list everywhere** (the original never changes it per
NPC) — keep that property.

## Dialogue display

- Data: #024's `dialogue.json` — 1,184 `$DDBD8` records decoded
  through the 3,466-word dictionary (`$136FC` semantics: skip
  array[0], separator in top-2-bits). Never parse the raw blob.
- Line behaviour: reproduce the message-queue flow — queue
  `$26B58`/`$1E3B0` (capacity 8 in real flow, `$1B5D6`), pop/display
  `$26CCA`; dedup of identical consecutive records is original
  behaviour, keep it. The queue's div-by-zero hazard is an
  implementation bug of the original, NOT a behaviour — the
  tribute initialises capacity before first use (logic-audit F10).
- Record-0 "An" drop: export is verbatim; display the record as
  decoded and log the known bug (first-mod candidate C).

## Sextant readout

Degrees-minutes format exactly as locations.htm / the fan
walkthrough use it (e.g. `15'-18'`), shown **only once the player
has the sextant** (item "Sxtnt", price record 160 area — logic.md
§3.3 quest items). Coordinates must agree with #025's city
placement table.

## Music menu

Present, with Quiet — and in the tribute Quiet **works** (that is
#030's fix, deliberately not the original behaviour). The menu
lists the 19 entries from ROM text `0xCD208` (Quiet + 18 songs).

## Fight-anyone quirk — decision

The player can pick a fight with anyone, including quest-critical
NPCs ("the doomed world you have created"). **Classic keeps it**
(it is original behaviour with an in-game acknowledgement);
New-combat mode (#027) also keeps targeting freedom but applies
its uniform death rules. Recorded here as the issue requests.
