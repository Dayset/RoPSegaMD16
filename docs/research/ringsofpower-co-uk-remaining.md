# ringsofpower.co.uk — remaining pages (issue #033)

Status 2026-11-09: **READ via Wayback Machine (live-browser session).**
All 31 HTML pages in the 59-URL inventory are now accounted for.
29 read in full, 1 unrecoverable, image-only pages noted.
Summaries below are in our own words; only data (codes, coordinates,
spell names, track lists) is reproduced as data. Fan-site content is
player-observed — hypotheses for RE work, never evidence on its own.

Correction to earlier draft: this file did not exist on `main`; the
59-URL inventory lives in `ringsofpower-co-uk-guides.md`.

## Coverage

| Page | Snapshot | Status |
|---|---|---|
| index.htm / home | 20071228222249, 20080923231811 | Read |
| intro.htm | 20080409192152 | Read — index only |
| what.htm | 20080409223904 | Read |
| story.htm | 20080409223850 | Read |
| walkthroughs.htm | 20080410150728 | Read — index only |
| walkthrough.htm | 20081005202627 | Read in full |
| speedguide.htm | 20081005202622 | Read — "Coming soon", never published |
| help.htm | 20080410150637 | Read — index only |
| hints.htm | 20081005052958 | Read |
| cheats.htm | 20081005202612 | Read — high value, see below |
| secrets.htm | 20081005202617 | Read |
| spells.htm | 20080920151205, verified vs 20120614131003 | Read in full |
| uskabau.htm | 20080410150722 | Read — index only |
| map.htm | 20090204065753 | Read — image hotspots not recoverable in this view |
| invertedmap.htm | 20090206175938 | Image-only, no text |
| pics.htm | 20090204072833 | Image-only |
| sounds.htm | 20090717044508 | Read |
| loony.htm | 20090208114332 | Read |
| commerce.htm | 20090204072507 | Read — heading + city-plan image only |
| division.htm | 20120513115634 | Read — only full city profile |
| places.htm | 20080410150655 | Read — index only |
| links.htm | 20090209220731 | Read |
| tradinginv.htm | 20080410160717 | **NOT READABLE** — 302 to 110mb.com 404, no 200 capture; printer-friendly trading guide is lost |
| maze.htm (+ images) | 20080410150650; GIF 20131214200129 | Text read; maze GIF did not render — route not transcribed, archived GIF URL recorded for follow-up |

## Home / news diary — key findings

- Site by Y8C, tagline "The complete Rings of Power experience".
- 1 Apr 2007: relaunched at ringsofpower.co.uk after the original
  ringsofpower.8m.com was lost.
- 4 Mar 2008: Xavier Whipon emailed Game Genie codes + IPS patch +
  a glitch (now on secrets page).
- 12 May 2008: author says he removed the character/spell pages
  without realising — explains why no character pages are in the
  inventory. Guestbook gone; speed guide promised, never appeared
  (speedguide.htm is only "Coming soon...").

## Story / what

Buc must find the 11 rings to restore the Rod of Creation. Backstory
per story.htm: Void summoned, 66-year cataclysm 500 years ago, rod
split in two, each half split into 11 rings hidden across Uska Bau
(site spelling; ROM/docs use Ushka Bau). Buc, top student at the
Academy of Sorcery in Mind, is sent with the six arts.

## Walkthrough (walkthrough.htm) — summary

Three parts. Part 1: recruitment — Thalmus (spells.htm: Thalamus)
gives map + Warn; Slash in Division, Arrow/Feather in the Mines of
Mysery, Alexi in Perfection, Obliky in Kaos, Mortimer last (corpse
taken to Old Tsalmi's grave at night). Part 2: the 11 rings with the
page's difficulty table (Thought Easy/first, Will Medium, Intuition
Hard, Division Medium, Advancing Medium, Perfection Hard, Calling
Medium, Bile Hard/late, Blood Hard/late, Variation Easy, Mutation
Easy) and sextant coordinates for most rings (e.g. Intuition
11'-18', Division 8'-8', Perfection 3'-18', Calling 1'-18',
Bile 23'-26', Blood 9'-14', Variation 29'-12'). Part 3: Holy Seal,
Bandit HQ 30'-18', final battle vs Darius/Derek, also called Void;
ending appears scripted. Name inconsistencies flagged for
transcription: Feather/Arrow, Obliky/Oblisky, Thalmus/Thalamus.

## Spells (spells.htm) — per character, author's claims only

No mana costs or systematic damage values are given on the page.

- Buc (Sorcerer): Warn, Raise, Random, Light, Search, Mind, Seize, Port.
- Mortimer (Necromancer): heal series Comfort, Relief, Solace, Cure,
  Health, Restore, Perfect; Pain is his super (author claims it kills
  weak enemies and halves stronger/immune ones — verify vs #008).
- Slash (Knight): Hack (super), Divide (~100 pts, "best for bosses").
- Feather (headed "Arrow", Archer): Hawk (author calls it hardest-
  hitting in the game), Force, Twister (super).
- Alexi (Conjuror): Stones (~80 pts — author also calls this the
  hardest single-target spell, contradicting the Hawk claim), Djinn
  (super, ~50), Fire, Ice, Tremor (~30), Sight/Turn, Shade, Talk.
- Obliky (Enchanter): Seduce, Dazzle, Mirage, Flames, Mix, Scatter,
  Wyrm (super), Insane.

## Hints (hints.htm) — summary

Manual-derived + author/TerraBreaks tips: save before healing,
inns cheaper than temples, daylight travel, pay tax collectors,
bribe merchants, keep wealth in trade goods to cut resurrection
donation, buy gems at Mind / sell at Commerce, Frenzy in Wary then
pause-switch to Berserk, holding HELP screen reduces encounters.

## Cheats (cheats.htm) — high value for RE

- Teleport: highlight map position, A+C+Start on joypad 2.
  Cross-check with #019's pad-2 combo decoding ($E0/$B0).
- XP: Cave of Thought, repeat the same question, ~200 XP each.
- Gens/PAR codes (Spiridakis): stable addresses for Food
  (FFC364), Water (FFC366), Money (FF02DE), and per-character
  Exp/HP/MP blocks for Buc, Slash, Feather, Alexi — plus two
  further blocks at FF05DA… and FF04A2… where the two extractions
  disagree on Mortimer vs Obliki assignment. **Verify against page
  source / ROM RAM map before using.**
- Game Genie codes (Xavier Whipon): master code R1JA-86Y6 required
  to boot, plus unlimited money/water/food and per-character
  health/power/exp codes (full list in the browser report on file
  with this session; transcribe into a codes table on verification).
- Xavier's technical claims — **hypotheses, not facts**: saves are
  serial EEPROM not SRAM (consistent with #019's EEPROM finding);
  non-Buc character stats move in RAM between new games, which is
  why PAR codes can trigger a Void kill; Food/Water/Gold addresses
  are stable.
- His IPS patch is **not** hosted on this site; the download link
  points to romhacking.net/hacks/354.

## Secrets (secrets.htm) — summary

Sunken-treasure coordinate list carved at the Rich Man's Tichhead
(7 entries, sextant coords → values), an infinite-goods Desire
glitch (stack to 255), an empty cave NE of Sunrise at 8'8"-11'2",
vehicle/invisible-party glitches, and a pad-2 boot combo
(Right+A+B+C on pad 2 at power-on, "Topples Lady").

## Other pages

- sounds.htm: 17 MP3 tracks (Title, Sorcerer, Knight, Archer,
  Conjuror, Necromancer, Enchanter/map, Battle, Castle, Death,
  Nexus, Quest, Seas, Someone's home, Tavern, Victory, Wilds),
  hosted by Rob Groove, converted by ZedPower.
- loony.htm: long dialogue corpus, useful for #004 text decoding;
  includes the known dev in-jokes (combat redone a fifth time,
  interface reprogramming, a `buc1.bc` source filename) and a
  Black Sabbath "Paranoid" quotation. Lyrics not reproduced here.
- division.htm: only full city profile — second city, knights'
  largest guild, blades sell well in Sparta, Division pays well
  for Weapons.
- map.htm: author-made map, "first map of Uska Bau in existence",
  hotspots for 14 named places + 3 unnamed.
- links.htm: outbound to Rob Groove, GameFAQs, Honest Gamers,
  Naughty Dog.

## Still open

- tradinginv.htm is unrecoverable from Wayback (no 200 capture).
- Maze route: archived GIF at
  https://web.archive.org/web/20131214200129im_/http://www.ringsofpower.co.uk/pics/mazemap.gif
  did not render in the browser view; transcription still owed.
- Mortimer/Obliki Gens-code assignment ambiguity (above).
- Game Genie full table transcription on verification.

## Maze GIF — further attempts 2026-11-09 (continuation)

Three independent retrieval routes now tried and failed:
(1) live-browser Wayback view — GIF did not render;
(2) direct download from this VM — Wayback blocks the VM's
traffic as suspected bot traffic;
(3) archive.org availability API for mazemap.gif / mazepic.gif
(both host variants) — returns **no archived snapshots**, which
contradicts the earlier CDX listing and suggests the capture may
not be served at that URL at all.
Verdict: maze route transcription is a genuine dead end with
current access; it needs a human browser download of the GIF
file itself. The maze *text* guide remains covered in
ringsofpower-co-uk-guides.md.
