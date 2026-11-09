# rings-of-power.ru — fan-site scrape report

Scraped 2026-11-09 by subagent for the Rings of Power (Mega Drive, 1992) RE project.
Site language is Russian; key points translated below. All page reads via browser.open;
binaries downloaded with curl into `/tmp/rop-ru-site/` (see note on /tmp at the end).

## What the site is

A WordPress fan site (2009–2010) run by admin **Созидатель (Sozidatel), aka Kirill Bagnyukov**
(contact in an old post: kirill.cre@gmail.com), dedicated to a Russian fan translation of
Rings of Power that **never shipped**. The translation team had translated nearly all the
text by late 2009 but never solved how to insert it into the ROM ("вопрос о том, как этот
перевод будет внедрён в игру ещё не решён", Nov 2009 post). Last post May 27, 2010;
site effectively abandoned since. In April 2010 the host's datacenter (Hosting.UA,
server Europe-10) burned down, backups were unrecoverable, and content was only
partially restored — so some pages/files may be missing. This is a *separate, earlier*
effort from bybyc9lc9l's 2012 translation on romhacking.ru, which did ship.

## Page inventory

| Page | URL | Contents |
|---|---|---|
| Home (blog p.1) | https://rings-of-power.ru/ | Latest post May 27 2010: translation at "turtle speed", thanks to Freezy for help |
| Blog p.2 | https://rings-of-power.ru/page/2/ | Posts Apr 2010–May 2009: datacenter fire, userbars, sounds update, ~30% text done (Dec 2009), translation "practically complete" (Nov 2009), calls for ROM-hackers/artists |
| Blog p.3 | https://rings-of-power.ru/page/3/ | "О переводе" (About the translation): glossary + translation-progress files |
| Files | https://rings-of-power.ru/files/ | English ROM link (NOT downloaded), full world map, walkthrough, soundtracks |
| Soundtracks | https://rings-of-power.ru/files/sounds | 17 MP3 tracks from the game (see below) |

## Downloaded files (`/tmp/rop-ru-site/`)

| File | Size | What it is |
|---|---|---|
| `RingsOfPower-World.png` | 2,907,123 | Full world map of Ushka Bau, 8076×4654, 8-bit PNG |
| `RingsOfPower-World(Animated).gif` | 9,706,419 | Same map, 2-frame GIF 89a, 8076×4654 (animated water) |
| `walkthrough.rar` → `walkthrough/RingsofPower.doc` | 996,505 → 1,234,432 | Full Russian walkthrough by Leonid Mayer (pics/coords: Alexander Efremov); original http://www.rings-of-power.narod.ru |
| `4translate.doc` | 297,984 | Glossary of terms/names EN→RU with commentary, 18 pp., 3,217 words (Feb–Jun 2009) |
| `english-and-russian.doc` | 237,568 | Game text in English AND Russian, 16 pp., 9,948 words (Mar–May 2009) |
| `russian.doc` | 130,048 | Same game text, Russian only, 8 pp., 4,950 words |
| `Rings-main-theme.mp3` | 1,634,637 | Main theme ("Главаня тема / тема Колец"), 102 s; valid MPEG audio, odd leading ~0x1A0 zero bytes before first frame sync |
| `txt/*.txt` | — | LibreOffice conversions of the four .doc files (UTF-8) |
| `map-thumb.jpg` | 83,685 | 900-px thumbnail of the world map (made for visual check) |

NOT downloaded on purpose: the English ROM linked from /files/ (full commercial ROM — out of scope).

## Findings, by project issue

### #004 Text/dialogue — HIGH VALUE (best find on the site)

- **`english-and-russian.doc` is a ground-truth corpus of the game's text.**
  It opens with the exact location-description strings from the packed dialogue blob
  ("An unknown building. / A Sorcerer's Guild. You feel eyes watching you. / A Guild
  of the Knights of the Holy Order of Separation. Clanks and bangs emerge from within.
  / An Archer's Guild. …"), i.e. the same text we found packed/concatenated at
  0x0D6EBA — here decoded, spaced, and in reading order. It continues through NPC
  dialogue (Talmus, the hermit quest, the witch Hideous / Ogre Egg quest, the Confessor,
  the Regent of Doggon, the sick king / Milk of Youth quest…). 816 lines total,
  English and Russian blocks interleaved by section. Use it to **validate the
  dictionary decoding**: any word sequence we extract from the blob must match this
  text, and any gap in it points at text we haven't decoded yet.
- **`russian.doc`** is the parallel Russian-only version of the same strings (408 lines).
- **`4translate.doc`** (glossary) is a terminology reference with sections: Geographic
  places, City guide, Historical figures, **Magic & skills** (6 Disciplines/"Таинства";
  spells STUN, CLUE, DISPERSE, MIRAGE with explanations), Races & classes, Items,
  Interface, Interesting phrases (jokes explained), Other. Useful as a terminology
  cross-check for #004/#007/#008 — but note it is one fan's opinion ("моё личное ИМХО"),
  not canonical.
- Caveat: this team's translation never shipped and its insertion method was never
  solved, so these docs are **transcriptions/translations, not ROM data**. They tell us
  what the text says, not how it is stored. The dictionary-vs-compressed-blocks
  question (#004) is answered by bybyc9lc9l's 2012 patch notes, not by this site.

### #006 Maps/world data — HIGH VALUE

- **The world map is a complete render of Ushka Bau** (8076×4654, visually verified):
  isometric/diamond orientation (rotated ~45°, compass rose top-left), continents,
  oceans, desert, ice caps, towns/castles visible as sprites. Likely stitched from
  in-game map screens. Use as the reference layout to validate extracted map data —
  city positions, coastline shape, desert/ice placement. Note the diagonal orientation
  when comparing against ROM map data.
- **Walkthrough gives in-game coordinates for cities** in a degrees/minutes style,
  e.g. City of the Mind 11'9'' 11' 4''1, City of the Division 16'' 9' 11' 3'. Format is
  inconsistent in the text; treat as approximate until tied to ROM coordinates.

### #007 Game logic / #008 Spells — MEDIUM VALUE

- Walkthrough documents mechanics in passing: merchant attitude levels
  (WORSHIPFUL … VIOLENT), Bribe (10 gold to repair attitude), combat modes
  MANUAL/AUTO/Wary, spells STUN (low damage, low mana), WARN (predict/block),
  CLUE (attacks always land), transport types (Boat/Ship/Dino/Dragon) with
  food/water/money consumption rules. All player-observed, not RE-verified — good
  hypotheses/leads for #007/#008/#020, not evidence.
- Glossary's Magic & skills section names the 6 Disciplines and several spells
  with their roles.

### #018 Sound — MEDIUM VALUE

- Soundtrack page lists **17 named tracks** (MP3, ~41 KB–1.57 MB each): Main theme
  (Rings theme), Wizards, Knights, Archers, Sorceresses, Necromancers,
  Enchanters (also the map theme), Battle, Castle, Death, Nexus, Quest, At sea,
  Someone's home, Tavern, Victory, On the street. The mapping of track → in-game
  situation is the useful part for #018 (which song plays where). One commenter
  names "Guilds" as a favourite — that title is not in the list, so either a
  misremembered name or a missing track.
- Only the main theme was downloaded (verified 102 s MP3). Other track filenames
  were not enumerated (would need 16 more page fetches); the page lists names+sizes.
- Blog (Jan 2010) also mentions the team's romhacker was building "a convenient tool
  for translating into other languages" — no download link found; likely lost in the
  2010 fire.

### Music-off bug (music re-enables on location change) — NO DIRECT HELP

- No mention of the music on/off setting anywhere on the site (walkthrough grep for
  "музык" returns nothing). The soundtrack list does confirm the per-location music
  design (map theme = Enchanters' theme, etc.), which is consistent with a
  location-change song-start routine — but gives no flag/routine information.

### #019 Save/EEPROM — NOTHING

- No mention of saves, EEPROM, or SRAM anywhere found.

## Things that look wrong or outdated

- The site's own /files/ comment links the Russian translation via
  `https://rings-of-power.ru/goto/http://romhacking.net.ru/load/rings_of_power_ru_3_moda/6-1-0-221`
  — **404, dead**: the old romhacking.net.ru domain is gone. The live equivalent is
  romhacking.ru (same path), where the bybyc9lc9l patch lives.
- "Главаня тема" on the soundtrack page is a typo for "Главная тема" (Main theme).
- The English ROM link on /files/ was not followed/downloaded (deliberate).
- The translation-progress claim "practically complete" (Nov 2009) vs "~30% of all
  text" (Dec 2009) is contradictory — the 30% figure is probably the edited/finalised
  share, or the Nov post was optimistic. Don't cite either as fact.
- Search engines do not index this site (site: query returns nothing); the pages
  above were reached by direct URL/pagination only.

## Note on /tmp

Mid-task the exec service restarted and **/tmp was wiped completely** (tmpfs).
All files above were re-downloaded afterwards and sizes verified identical to the
first download (byte counts match). `/tmp` is ephemeral: if the parent agent wants
any of these files kept, copy them into `~/workspace/rings-of-power/` (e.g. as
reference material, NOT into git unless decided) before the next restart.
