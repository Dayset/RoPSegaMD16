# "Rings of Power — Naughty Dog's last pure game" — notes (summary, not verbatim)

Source: The Genesis Temple (genesistemple.com),
"Rings of Power - Naughty Dog's last pure game",
published 2020-02-29, updated 2023-03-13.
URL: https://genesistemple.com/rings-of-power-naughty-dogs-last-pure-game
Read 2026-11-09 via browser.open (full text, 221 lines).
This file is a summary in our own words; the article text is
copyrighted and stays at the URL above. Dayset: this one is about
GAME HISTORY, not combat.

## Development history (paraphrased)

- Started **1989 with a PC release in mind** — which the author says
  explains the "weirdly out of place on a 16-bit console" design
  choices. EA then decided to publish it exclusively on Sega Genesis
  because "it is going to sell better".
- A rare **western RPG for a Sega console**, inspired more by computer
  titles like Ultima and The Bard's Tale than by Final Fantasy or
  Phantasy Star.
- Rubin calls it **"Naughty Dog's last pure game"**: the last time the
  duo worked together on a title they liked, as opposed to something
  people were supposed to like. (The author links the 2012 Rubin
  interview for this quote.)
- The cartridge was **1 MB with save RAM — expensive to publish**. It
  sold out quickly and EA never restocked it, because the first Madden
  was also sold out but cheaper to produce and replace. Per Rubin, it
  became the best-selling used Genesis game very quickly "because it
  simply couldn't be found new".
- Frustrated with EA's publishing practices, Rubin and Gavin **left the
  gaming industry for several years**, returning with the 3DO Mortal
  Kombat clone Way of the Warrior, which almost bankrupted Naughty Dog.
  EA has never re-released Rings of Power in any form (no compilation,
  no Genesis Mini, as of the article's 2023 update).
- Release-date note: the article calls it a **1991** game; our ROM
  header says (C)T-50 **1992.JAN**. Both recorded; the header date is
  likely the build date, not the street date. Do not "correct" either
  without a source.

## World/map (relevant to #006)

- Gavin: it took **"six months to lay out the map, one block at the
  time"**. The world is a **scaled map**: Buc explores a small map, and
  pressing "B" reveals the full size; every square can be further
  explored for NPCs, items, money, treasure, clues. The author calls
  Ushka Bau meticulously crafted and natural/organic (contrasted with
  Phantasy Star 3's artificial map).
- The world-map image in the article is credited to the **Pixelation
  forum (Helm above all)** — the fan map's lineage.
- The in-game map is barebones: the only way to know a city's name is
  to travel there. The author recommends playing with a detailed map
  open on a PDF reader.

## Gameplay/design (player-observed; leads for #007/#008, not verified)

- **Not a levelling/battle RPG**: the focus is finding rings via clues
  and talking to people; the author says it would be wrong to call it
  an actual RPG — closer to a semi-graphical adventure (Deja Vu-like),
  "rpg-lite".
- **No equipment**: inventory is only quest items and goods to buy/sell
  — no potions/armor/weapons. Team members **fight only with spells**,
  gaining more powerful ones as they level up, usable only after
  shopping at Magic'R'Us. Battle has a **manual mode** (pick each
  character's cast); the player cannot move the team around, only wait
  for turns to cast. Random encounters ignore the player's spell level.
- **Survival**: food and water levels are constantly at risk
  (starvation/thirst); ice and rough surfaces consume a lot. Transports:
  dinosaur (saves from many random battles, fast), boat (food/water,
  worse in deep water), ship (food/water + money — sailors need wages,
  and unpaid sailors may attack), dragon (required for the final boss,
  Darius; consumes a lot of food/water, rarely used). Random pirate
  encounters exist.
- **Economy**: buy goods at the lowest price, sell at the highest in
  another city. The false king of Doggonia takes **1,000 gold each time
  Buc enters his room** (advice: talk to him penniless).
- **Interface**: a fixed list of verbs (late-80s style) — talk about
  everything, show inventory, bribe, buy/sell, pick a fight with anyone
  (including quest-critical NPCs, which can soft-lock the quest — the
  "doomed world you have created").
- **Cryptic by design**: clues are usually pieces of paper (search
  libraries/bookshelves first); day/night cycle gates NPC meetings;
  a couple of mazes. NTSC copies bundled a walkthrough in the manual's
  appendix (PAL owners got none). Adventure is 20–40 hours.
- Tone: the game alternates comical, weird and downright creepy; taverns
  with bingo, bars with techno music and strobe lights, absurd dialogue.
  The author notes a "nude" easter egg exists but declines to discuss it
  (links eeggs.com) — recorded here only as "known easter egg, out of
  scope for the RE work unless it touches code paths".
- Reception at the time: lukewarm; reviewers singled out slowness and
  cryptic nature, some recommending Buck Rogers – Countdown to Doomsday
  instead. The author wrote four articles about the game over 25 years
  of games journalism (first in Italian, this is his first in English).

## Why it matters for the project

- History/background for the repo (docs/overview.md, README): PC-origin
  design, EA publishing story, "last pure game" framing, 1 MB + save
  RAM cost.
- The six-months-one-block-at-a-time map quote supports #006's open
  walkable-grid question: the terrain grid was hand-laid, so it exists
  somewhere — the #006 leads (threaded decoder, 0x044000 block) stay
  live.
- Gameplay leads above are hypotheses for #007 (gold/shops/combat
  modes) and #008 (spells) — player-observed, need code evidence.
- NOT a source for the combat-rework story: the article does not
  discuss combat revisions. That claim still rests only on the in-game
  line, $DDBD8 rec 1004.
