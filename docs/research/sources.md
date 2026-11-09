# Source map (issue #034)

Created 2026-11-09 (agent session): web searches run this session
plus the repo's existing research files. Verdicts: **usable** =
cite it; **background** = context only; **checked** = visited via
search results, full read still owed. Dead links are findings.

| Source | Date | Contains | Verdict |
|---|---|---|---|
| `docs/research/genesis-temple-last-pure-game.md` (in repo) | article 2020, upd. 2023 | Development history; Gavin map quote; expensive cart, sell-out, no restock | usable (already in repo) |
| `docs/research/jason-rubin-interview-2012.md` (in repo) | 2012-04-09 | Rubin: Gavin = design+code authority; NO combat discussion (negative finding) | usable (already in repo) |
| rings-of-power.ru | 2009–2010 | See `rings-of-power-ru-catalog.md` (#032) | usable |
| ringsofpower.co.uk (Wayback) | 2007–2012 captures | See `ringsofpower-co-uk-remaining.md` (#033) | usable, partially read |
| Wikipedia — Rings of Power (video game) | current rev. (crawled ~Oct 2026) | Release NA Jan 1992 / EU Feb 1992; scores GamePro 21/25, MegaTech 49%; mixed-reception summary w/ citations to GamePro Feb 1992 + VideoGames & Computer Entertainment Mar 1992 | usable for #036 leads; verify scores against the magazines |
| MobyGames (game ID 15080) | added 2004, modified 2026-05-24 | Credits (matches ROM credits), Moby Score 6.7, **release year listed as 1991**, topless-intro cheat note | usable; its 1991 date conflicts with Wikipedia/ROM (see below) |
| We Play Retro — Rings of Power page | crawled Nov 2026 | Retrospective: ambition praised, controls/slow gameplay panned, sell-out + no reprint due to cart cost, "Published: 1991" | background |
| DualShockers — "That Time Naughty Dog Made An Epic RPG…" | 2023-04-22 | Retrospective play account; Naughty Dog's own deleted site entry ("largest RPG on a cartridge — ask any of the five people who have actually solved it"); the intro cheat (hold Down+Right+A+B+C+Start at power-on) | background (usable for the cheat + ND quote) |
| Vimm's Lair ROM Hacking DB | current | **"Rings of Power — The Hand of Nexus" v2.0, 2008-06-06** — a pre-existing ROM hack (thanks to Pugsy/Ugetab/GameHacking.org); plus a ColorPaletteHack (2022-05-12). ROM hashes listed match our dump (MD5 30c18fdb…) | **usable — NEW LEAD: a 2008 hack predates our mod work; check what it changes before #022 picks a target** |
| Internet Archive — Sega Mega Drive [RUS] collection | updated 2021-10-28 | Contains `Rings of Power UE [T+Rus bybyc9lc9l]` (the #035 translation) and a "Money Hack" variant listing | background (existence proof for #035's patch circulation) |

## Checked and NOT yet usable / still owed

- **Sega-16** — named in the issue; no Rings of Power article
  surfaced in this session's searches. OPEN (direct site search
  still owed; absence here is not proof of absence).
- **Hardcore Gaming 101** — same status: not surfaced. OPEN.
- **Pixelation forum world-map thread (Helm)** — not surfaced by
  search. OPEN.
- **eeggs.com** — the intro easter egg is corroborated by
  MobyGames + DualShockers (existence noted, per the issue no
  detail needed). eeggs itself not fetched. Partially checked.
- **YouTube longplays** — not catalogued this session. OPEN
  (visual reference value only).
- **Internet Archive manual scans** — the [RUS] collection above
  is a ROM collection, not a manual scan. Manual scan still OPEN.

## Release-date question (acceptance item 3 — recorded, not settled)

| Source | Date claimed |
|---|---|
| ROM header `(C)T-50 1992.JAN` | January 1992 |
| Wikipedia (current) | NA January 1992, EU February 1992 |
| MobyGames | 1991 |
| We Play Retro | 1991 |
| Wikipedia's own older mirrors (osmarks/ipfs snapshots) | 1991 |
| Genesis Temple article | 1991 (per the issue text) |

Pattern: older/secondary sources say 1991; the ROM header and
current Wikipedia (citing contemporary magazines) say Jan/Feb
1992. A plausible reconciliation is a late-1991 completion /
1992 street date, but **no source in hand states that — do not
pick a winner** (the issue forbids it without evidence). The
magazine citations (GamePro Feb 1992 review exists) make a 1991
*street* date hard to sustain; recorded as tension, not verdict.

## Leads passed on (hypotheses, not facts)

- The Hand of Nexus (2008) hack → to #022 (know what already
  exists before picking a first-mod target).
- The intro cheat (button combo at power-on) → to #021: it is a
  pad-read-at-boot behaviour; the `$4323C` pad-2 combos ($E0/$B0)
  prove the game reads pads at boot, so a pad-1 intro combo is
  mechanically plausible — the cheat's code path is unlocated.
- ~50,000 units: appears only in a Facebook community post's
  comments (search result, 2025) — **unverified, do not cite**.
