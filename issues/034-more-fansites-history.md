# Issue #034 — Find more fansites & history sources

**Milestone:** Research
**Epic 6** (Research & history)
**Status:** open

## Goal
Search the web for more Rings of Power history, fansites, and
primary sources, evaluate them, and save what is usable as research
notes. The goal is a complete source map for the project — not one
more article, but knowing what exists and where.

## Acceptance
- [ ] A source list in `docs/research/sources.md`: each source with
  URL, date, what it contains, and a verdict (usable / background
  only / dead link / duplicate)
- [ ] At least these checked (add more as found): Sega-16, Hardcore
  Gaming 101, MobyGames (credits, release dates, reviews), the
  Pixelation forum world-map thread (Helm), eeggs.com (the "nude"
  easter egg — note it exists, no detail needed), YouTube longplays
  (for visual reference of areas the RE hasn't reached), the
  Internet Archive's software/manual scans
- [ ] Release-date question settled as far as sources allow: the
  article says 1991, our ROM header says 1992.JAN — record what
  each source says, do not pick a winner without evidence
- [ ] Any new gameplay/mechanics lead passed to the relevant RE
  issue (#007/#008/#020) as a hypothesis, not as fact

## Notes
- Junior-agent job: web search, reading, judging sources. No ROM
  work, no code. Summarise in our own words; link, don't copy.
- Already covered (do not redo): the Jason Rubin interview 2012
  (`docs/research/jason-rubin-interview-2012.md`), the Genesis Temple
  article (`docs/research/genesis-temple-last-pure-game.md`),
  rings-of-power.ru (#032), ringsofpower.co.uk (#033), the Russian
  2012 translation (#035).
- Dead links are a finding, not a failure — record them with the
  date checked.

## Depends on
Nothing. Start now.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/research/sources.md — source map with URL/date/contents/verdict per source (repo files, Wikipedia, MobyGames ID 15080, We Play Retro, DualShockers, Vimm's Lair, Internet Archive), the 1991-vs-1992.JAN release-date table recorded WITHOUT picking a winner, and leads passed on (the 2008 'Hand of Nexus' hack -> #022; the intro cheat -> #021; the ~50,000-units figure flagged unverified). Web searches were run this session.
- **Acceptance:** PARTIAL: source list + release-date item met; Sega-16, Hardcore Gaming 101, the Pixelation (Helm) thread, YouTube longplays and an IA manual scan were NOT surfaced/fetched this session and are recorded as OPEN in sources.md rather than claimed checked-and-empty.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation session)

- **Sega-16 FOUND:** review dated 2011-04-25 at https://www.sega-16.com/2011/04/rings-of-power/comment-page-1/ — score **4/10**, header lists "Released: 1991". Substance (own words): deep/challenging Genesis RPG, but useless in-game map (no marked locations), very slow movement, aged graphics, unremarkable music; notes the intro Easter egg with a controller-2 variant combo. Recorded in sources.md as usable; the 4/10 also feeds #036 as a retrospective score.
- **Manual scan FOUND (item can close):** Internet Archive collection SEGAGenesisMegaDriveManuals (https://archive.org/details/SEGAGenesisMegaDriveManuals) file list contains "Rings of Power (USA, Europe).pdf" (2.9M), verified by opening the collection 2026-11-09. Corroboration: RetroMania lists a Genesis manual PDF for the game.
- **Longplays:** a World of Longplays (longplays.org) entry did NOT surface — recorded as not surfaced, still open for that source. Found instead: YouTube playlist "Best Video Games of 1991" (entries: Rings of Power Tutorial; RPG Quest #62 Part 1 — a beat-every-English-console-RPG series) and an embedded playthrough via segagames.online. Background/visual reference only.
- **Pixelation (Helm):** the thread itself still NOT located after targeted searches. Its existence/subject are now verified via the Genesis Temple article's thanks section ("the great people on the Pixelation forum (Helm above all) for the awesome work on the world map") — the article's world-map image is that work. Original thread URL remains OPEN.
- **Hardcore Gaming 101: NOT found.** Three searches run (site name + game, quoted domain, podcast/ranking angle); only a tangential NeoGAF remark about an HG101 book's nudity-in-games feature. Recorded honestly; remains OPEN.
- **Release-date re-check:** no decisive new source; tension stands, no winner picked. New data points: gamecompanies.com and VGFacts both say December 31, 1991; RAWG-derived listings say January 1, 1991. Noted (hedged) that Jan 1 / Dec 31 are the conventional placeholder dates in game databases, weakening them as evidence of a 1991 street date; Sega-16 also gives only the year 1991.
