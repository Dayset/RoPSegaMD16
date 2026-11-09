# disasm/main-loop/ — issue #020 tables

- `verb_menus.txt` — the menu verb table at ROM `0xCCDB8–0xCCFF0`,
  re-parsed 2026-11-09. Item records are 14 bytes (10-byte name +
  4 trailer bytes A/B/C/grp); headers are 12 bytes (10-byte name +
  2 trailer bytes). Includes the six PARTY disciplines
  (Sorc/Knight/Archer/Necro/Enchnt/Conjur, grp 2, C=0–5).
- `d28e_switch.txt` — the `$D28E` command switch at `$D740`
  (subtract-and-branch chain, re-verified): 15 cases, 0/10/20/21/
  22/23/24/25/30/35/37/40/45/50/55, with the routine each case calls.
- `entity_templates.txt` — the 24-byte entity templates at ROM
  `$CF1AC` (templates 0–19 decoded): template word 0 is the name
  index (`+0x14`). Template 0 = "Man" — the new-game leader is
  created from it, which is the open "party names" puzzle for #021.
