# rings-of-power.ru — catalogue (issue #032)

Completed 2026-11-09 (agent session) from the existing scrape in
`docs/research/rings-of-power-ru/` (SCRAPE-REPORT.md) + the saved
files themselves. **No re-download was done or needed** — everything
below is verified against the files in this repo. Site: Russian
WordPress fan site 2009–2010 by Sozidatel (Kirill Bagnyukov),
translation project that **never shipped** (see Gaps).

## 1. File inventory (acceptance item 1 — MET for what exists in repo)

Saved under `docs/research/rings-of-power-ru/`:
| File | Size | What |
|---|---|---|
| `RingsOfPower-World.png` | 2,907,123 | Full world map 8076×4654 — Dayset-verified legit/perfect (#006) |
| `4translate.doc` + `txt/4translate.txt` | 297,984 / 36,072 | Glossary, 18 pp (§4) |
| `english-and-russian.doc` + txt | 237,568 / 92,981 | Game text EN+RU — the #004 ground-truth corpus (647/649) |
| `russian.doc` + `txt/russian.txt` | 130,048 / 59,504 | Same text, Russian only |
| `walkthrough/RingsofPower.doc` + `txt/RingsofPower.txt` | 1,234,432 / 133,578 | Full Russian walkthrough (Mayer/Efremov), ~11,600 words in txt form |
| `SCRAPE-REPORT.md` | — | The 2026-11-09 scrape report this catalogue builds on |

**Still only on the site (not saved, per .gitignore / scope):**
the animated GIF of the map (9.7 MB), the other 16 soundtrack MP3s
(only the main theme was fetched, to /tmp, now lost), the
walkthrough `.rar` wrapper, and the English ROM link (deliberately
never downloaded — commercial ROM). Blog pages were read via the
browser but not archived as files. **Gap recorded:** if the site
dies, the blog text and 16 MP3s are the un-backed-up remainder.

## 2. Walkthrough mechanics leads (acceptance item 2 — hypotheses, NOT facts)

Mined from `txt/RingsofPower.txt` (line refs to the txt file):
- **Bribe = 10 gold, repeatable, raises merchant attitude to
  WORSHIPFUL; at VIOLENT the merchant attacks and trade becomes
  impossible** (line 11). Also: stealing from the Academy degrades
  attitude; good attitude discounts FOOD & WATER. → Status vs ROM:
  attitude itself is PROVEN in `$2EA92` + the `$2155E` drift loop
  (#007/#020); the Bribe action and the 10-gold figure are
  **still unlocated in code** (logic-audit §5 item 5). Hypothesis.
- **Bribe also works on NPCs for quest items** — e.g. bribe the
  wizard → receive the Dove (line 232); bribe four tavern patrons
  to WORSHIPFUL before a killing (line 390). → Hypothesis for
  #020/#021: Bribe may be a general verb, not merchant-only.
- Combat modes MANUAL/AUTO/Wary and quest coordinates throughout
  (degrees-minutes, e.g. Dragon Cave at (30'3" 11'9")) —
  player-observed; the verb table's MOOD set (Berzrk/Advnce/Hold/
  Wary) partially corroborates the mode names from ROM (#020).

## 3. Soundtrack — 17 named tracks (acceptance item 3 — MET, from SCRAPE-REPORT)

Main theme (Rings theme), Wizards, Knights, Archers, Sorceresses,
Necromancers, Enchanters (also the map theme), Battle, Castle,
Death, Nexus, Quest, At sea, Someone's home, Tavern, Victory, On
the street. Handed to #018/#030 (`docs/sound.md` §4,
`docs/tribute/030-audio.md`). Caveat: a commenter names a "Guilds"
track not in the list — and the ROM menu does contain "Guilds" —
so the list is likely incomplete or one name differs.

## 4. 4translate.doc glossary summary (acceptance item 4 — MET)

Structure (from `txt/4translate.txt` contents page): Synopsis,
Geographic places, City guide, Historical figures, **Magic &
skills**, Races & classes, Items, Interface, Interesting phrases,
Other. The Magic & skills section names the **6 Disciplines** and
discusses spells incl. **STUN, CLUE, DISPERSE, MIRAGE** with role
explanations (txt lines ~406–409 for STUN/CLUE). For #008: useful
as terminology cross-check only — the author states it is his
personal opinion ("моё личное ИМХО"), and the ROM's own discipline
names (Sorc/Knight/Archer/Necro/Enchnt/Conjur, PARTY menu #020)
are the authority.

## 5. Gaps (acceptance item 5 — MET)

- **Lost:** content destroyed in the April 2010 Hosting.UA
  datacenter fire (Europe-10); only partially restored. The team's
  translation tool (mentioned Jan 2010) has no download and is
  presumed lost in the fire.
- **Never solved:** ROM text insertion — text was translated but
  the team never worked out how to put it back ("вопрос … ещё не
  решён", Nov 2009). Progress claims contradict ("practically
  complete" Nov 2009 vs "~30% done" Dec 2009) — cite neither.
- **Contradiction recorded:** the site's /files/ link to the 2012
  translation via romhacking.net.ru is dead (404); the live home
  of that patch is romhacking.ru (#035).
