# Issue #036 — Reception & release history (reviews, dates, sales)

**Milestone:** Research
**Epic 6** (Research & history)
**Status:** open

## Goal
Assemble the game's reception and release history from magazines,
reviews, and sales accounts: what reviewers said at the time, when
and where it released, and how it sold. This is the history chapter
of the project — background, not RE evidence.

## Acceptance
- [ ] Contemporary reviews found and summarised (scores + the
  substance of the criticism: slowness, cryptic nature are already
  known from the Genesis Temple article — find the actual reviews)
- [ ] Release dates per region recorded with sources (the 1991 vs
  1992.JAN question from #034 is part of this)
- [ ] Sales/publishing facts recorded with sources: 1 MB + save-RAM
  cost, sell-out, no restock, best-selling used Genesis game
  (Rubin's account — find any second source or record that there
  is none)
- [ ] A short reception section drafted for `docs/overview.md`
  (or a standalone `docs/research/reception.md`) — submitted as a
  proposal, not applied directly

## Notes
- Junior-agent job: searching magazine archives (Internet Archive,
  RetroMags, Sega-16, MobyGames), reading, summarising. No ROM work.
- The Genesis Temple article (2020, upd. 2023) is the starting
  point, not the endpoint — it cites no review scores itself.
- Do not present a single reviewer's opinion as the consensus;
  give the range.

## Depends on
#034 (source map) for where to look. Start now on the known
sources (Genesis Temple, MobyGames, Sega-16).

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/research/reception.md — contemporary reviews table (GamePro Feb 1992, MegaTech 49% Jun 1992, VG&CE Mar 1992, Mean Machines) with the GamePro 21/25-vs-5/5 score conflict flagged for magazine-scan verification; per-region dates with sources; sales/publishing facts with the 'best-selling used game' claim recorded as single-source (Rubin) and the ~50,000-units figure flagged unverified; §4 is a DRAFT reception section for docs/overview.md.
- **Acceptance:** PARTIAL: reviews/dates/sales assembled from web sources searched this session; overview.md was NOT edited (the acceptance asks for a proposal — §4 is that proposal). Scores should be verified against magazine scans (Internet Archive/RetroMags) before the proposal is applied.

**Status after this session:** in progress — partial (see below). Not marked done.

## Update 2026-11-09 (continuation session)

- **GamePro score conflict RESOLVED against the magazine scan.** Internet Archive holds the full text of GamePro Issue 031 (February 1992): https://archive.org/stream/GamePro_Issue_031_February_1992/GamePro_Issue_031_February_1992_djvu.txt — read this session; it confirms Earth Angel's p.52 review, its substance and its five-category rating header. The category numerals are a printed graphic (absent from the OCR layer); a recap of the same scan (https://countzeroor.com/2009/06/25/where-i-read-gamepro-31/) reads them as FunFactor 5, Challenge 5, Graphics 4, Sound 4, Gameplay 3 = **21/25 exactly**, and Sega Retro's scan index independently converts GamePro to 84 (= 21/25). **Verdict: 21/25 is the aggregate; the older mirror's "5/5" is a single 5-scoring category mistaken for an overall score. Do not cite 5/5 as GamePro's overall mark.**
- **MegaTech review read in scan:** the full review is in **MegaTech issue 4 (April 1992), pp.29–31** — IA "Unedited Scans of UK Gaming Magazines" (MegaTech_04 full text read this session). In own words: controls extremely awkward, combat overly difficult, navigation hard, graphics slow/ugly, "tedious and unenjoyable"; verdict to give it a miss for Buck Rogers. Overall **49%** per Sega Retro's scan index and Wikipedia (both revisions). New discrepancy recorded honestly: Wikipedia's footnote cites issue 6 p.77 for the rating, but the full review itself is in issue 4 — the issue-6 pointer is presumably a later index listing; not resolved further.
- **Scores captured for the remaining two:** VideoGames & Computer Entertainment (Mar 1992, Howard H. Wen) **6/10**; Mean Machines (Mar 1992, issue 18, Automatic/Rignall) **41%** — size/concept praised, potential wasted by slow, unresponsive, frustrating gameplay (Wikipedia current + Sega Retro index).
- **Retrospective added, kept separate:** Sega-16 (2011) **4/10** — from #034.
- **§4 remains a draft proposal; docs/overview.md was NOT edited.**
