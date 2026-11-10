# Agent playbook — structure, metrics, task queue

Written 2026-11-10 from a read of `main` at `aa6ca61` and all 16 remote
branches. GitHub issues and PRs were not readable from the review session,
so issue numbers below are placeholders (`T-…`); the lead files them.

## 1. What is slowing the project (measured)

| Finding | Evidence |
|---|---|
| Finished work is not landing | 11 branches hold unmerged commits. The tools that would speed everyone up — pinned toolchain, `make` gate, coverage for `rop.s`, symbol DB, region inventory — are each 1–3 commits, sitting 6 behind `main`. |
| The same task is done several times | Three naming branches (`gh-routine-names`, `gh-11-routine-names`, `gh-11-routine-naming`), two dispatch-label branches. `agent/all-open-issues` is 52 ahead / 48 behind with 131 files. |
| Names exist but not on `main` | 80 of 446 routines named, all on a branch. `main` has 0. |
| Status is typed by hand in four places | README bars, `PROGRESS.md` (39 KB), `issues/*.md`, GitHub. The longest section of `CLAUDE.md` is about keeping them in sync. |
| The rules contradict the tree | `CLAUDE.md` says GNU as and `0x` hex; the build uses vasm and `$` hex. `tools/coverage.py` cannot read `rop.s`. README and `CLAUDE.md` give different branch names. |
| Work drifted off the goal | The last ~25 commits on `main` are game-mechanics research (merchant table, SFX bursts, day/night clock, terrain animation), each live-verified. None moves M5, M8, M9 or M11. |
| No rule says "decide yourself" | Nothing tells an agent a name is cheap and reversible, so it asks. |
| One generated 60,663-line file | Any two agents touching `rop.s` conflict. Output must be small data files instead. |

Real position: of 1,048,576 ROM bytes, about 201 KB is labelled code and
847 KB is raw `incbin`. The unmerged region inventory lists 788,146 bytes
as unclassified — although `docs/` already identifies the text blob,
graphics, maps and sound data. That knowledge is in prose, not in the
machine-readable map. Moving it over is the cheapest large gain available.

## 2. Structure

### Roles
- **Lead** (one session at a time). Merges, cuts task cards, keeps the
  queue 8+ cards deep, answers `docs/questions.md` with defaults where it
  can. Does no reverse engineering.
- **Workers** (as many as there are free shards). One card each. Never
  wait on each other.
- **Gate** is a command (`make check`), not a person.

### Files agents write to
```
disasm/regions.csv              start,end,class,name,doc_ref,tier
disasm/symbols/code_00.csv …    addr,name,tier,note        (one file per shard)
disasm/symbols/ram.csv          addr,size,name,tier,note
disasm/symbols/data_XX.csv      addr,name,type,tier,note
docs/leads.md                   one line per unchased finding
docs/questions.md               question · default taken · impact
```
Shards are fixed and mechanical, so nobody negotiates ownership:
- Code shard `k` = rows `40k+1 … 40k+40` of `disasm/ghidra/functions.txt`
  (12 shards cover all 446 routines).
- Data shard = one 64 KB bank (`$00xxxx` … `$0Fxxxx`), 16 shards.

Generators read these files and write `rop.s`, `emu.sym` (BlastEm/Ghidra
import) and `STATUS.md`. Nothing generated is edited by hand.

### Frozen
`PROGRESS.md`, `issues/`, `NOTES.md`, `disasm/map.md` move to
`docs/archive/`. They stay readable; nobody updates them.

## 3. Metrics

All produced by `tools/status.py`. No hand counts.

### Completion
| Metric | Definition | Now | Done |
|---|---|---|---|
| Bytes accounted | bytes in code or a non-`unknown` region class ÷ 1,048,576 | ~25% (260,430) | 100% |
| Routines named | rows with tier ≥ 1 ÷ 446 | 0 on `main` (80 on a branch) | 100%, with ≥ 60% at tier 2 |
| Raw fallbacks | `dc.w` instruction fallbacks in `rop.s` | 102 | 0 |
| RAM named | named ÷ distinct `$FFxxxx` operands | measure on first run | top 200 by reference count |
| Typed data | bytes emitted as `dc.*`/labels instead of `incbin`, for regions that hold pointers | 0 | every pointer-bearing region |
| Shift test | build with 2 pad bytes inserted after the header boots identically in the harness | fail (not attempted) | pass |
| Asset round-trip | extract → re-pack → byte-identical, per asset class | 0 of 4 (text, gfx, maps, sound) | 4 of 4 |

### Flow (these show stalls early)
| Metric | Now | Target |
|---|---|---|
| Branches with unmerged work | 11 | ≤ active workers |
| Oldest open branch | > 24 h | < 24 h |
| Sessions ending without a merged PR | not tracked | 0 |
| Blocking questions to the owner | frequent | 0 (non-blocking log only) |
| Commits on `main` that move a completion metric | low | ≥ 70% |

Milestones map to metrics: M5 = raw fallbacks 0. M11 = routines named +
RAM named. M8 = bytes accounted 100% — every byte of the 1,048,576-byte ROM is
either labelled 68000 assembly in disasm/src/rop.s or an incbin range with a
non-`unknown` region class in disasm/regions.csv; no code byte hides in incbin
or in a `dc.*` fallback. M5 (zero fallbacks) is a precondition. `padding-ff`
(12,084 bytes) counts as accounted. Any non-`unknown` class counts, including
`high-entropy`, but `high-entropy` is reported as its own status line so M8
can't read 100% while ~19% of the ROM is still opaque (identified-as-compressed,
not decoded). Measured by tools/status.py once the region join lands;
tools/coverage.py as-is can't measure it. Current (2026-11-10): 72.8%
(763,653 / 1,048,576); unknown 284,923; high-entropy 195,886. M9 = typed data +
shift test. M10 = asset round-trip.

## 4. Task queue

Run Phase 0 first, serially, by the lead. Phases 1A–1E then run in
parallel. Each card is sized for one session.

### Phase 0 — land what exists (lead, serial)

**T-01 Branch triage.** Rebase, run the gate, merge, delete. Order:
1. `gh-4-pin-toolchain`, `gh-5-make-gate`, `gh-6-coverage-rop`
2. `gh-7-jump-dispatch`, then `gh-8-dispatch-labels-2`. (`gh-8-dispatch-labels` was already deleted 2026-11-10; its tip `8a03208` is recorded for recovery — cherry-pick anything unique from it first.)
3. `gh-15-unclassified-regions`, `gh-20-symbol-db`
4. Naming: take `gh-11-routine-naming` (80 names, PR #37) as the base; add any unique names from `gh-11-routine-names`; delete both. (`gh-routine-names` was already deleted 2026-11-10; its tip `caa4f81` is recorded for recovery.)
5. `gh-12-split-rebuildable`: already deleted 2026-11-10 (tip `eabef89` recorded for recovery); PR #35 closed when its head branch was deleted. Its bit-ops/jump-table content is recoverable from `eabef89`.
6. Delete the zero-ahead branches: `advisor/workflow-coverage`,
   `gh-14-hardware-limits`, `gh-9-rebuildable-skeleton`
7. `agent/all-open-issues`: do not merge. List files that do not exist on
   `main`; copy over only data files that still apply; log the branch in
   `docs/questions.md` for deletion (rule 3)
- Done when: `git branch -r` shows `main` plus at most the one parked branch.

**T-02 Symbol pipeline.** `tools/gen_src.py` reads `disasm/symbols/*.csv`
and `disasm/regions.csv`; convert the 80 names into shard files; emit
`emu.sym`. Lint: grammar regex, unique names, address is a real label,
tier present.
- Done when: `rop.s` on `main` carries the 80 names and the gate passes.

**T-03 `make check` + `tools/status.py`.** One command for build, verify,
lint, status. `status.py` prints every metric in §3 and rewrites the
README block between markers.
- Done when: `STATUS.md` is generated and the hand-maintained bars are gone.

**T-04 Rules swap.** Replace `CLAUDE.md` with the new one; archive the
frozen files; fix the README workflow section to point at `CLAUDE.md`.

**T-05 CI.** GitHub Action for the parts that need no ROM: symbol lint,
CSV schema, shard-ownership check (a PR touches one shard). The
byte-identical gate needs the ROM, so it stays a local pre-push hook.

**T-06 Cut cards.** File one GitHub issue per card below with the card
template (§5). Keep 8+ unclaimed at all times.

### Phase 1A — backfill regions from existing docs (4 workers)
No new reverse engineering. Copy what `docs/` already proves into
`disasm/regions.csv` with class, name and `doc_ref`.
- **T-10** text: dictionary blob, offset table, `$DDBD8` records, three
  LZSS streams (`docs/` text notes, `disasm/text/`)
- **T-11** graphics: tiles, sprites, palettes, compressed blocks (`docs/graphics.md`)
- **T-12** maps: 252 chunks, terrain grid, object records (`docs/maps.md`)
- **T-13** sound: Z80 driver, song and SFX tables (`docs/sound.md`)
- **T-14** tables: spells, stats, shop, save (`docs/spells.md`, `logic.md`, `save.md`)
- Done when (each): every address range the doc names is a row; bytes
  accounted rises; gate passes.

### Phase 1B — naming (up to 12 workers)
- **T-20 Auto-name pass** (one worker, first). Script assigns tier-0
  names from structure: hardware port touched (`vdp_`, `z80_`, `pad_`,
  `sram_`), thunks, jump-table targets, single-caller helpers of named
  routines. Target: no `FUN_` label left.
- **T-21 … T-32 Shard naming**, one card per code shard. Method, per routine:
  1. Read callers and callees in `call_edges.txt`
  2. Note hardware ports, RAM addresses and data tables it touches
  3. Grep `docs/` for its address
  4. Name it; set the tier; 20-minute cap, then tier 0 and move on
  Work most-called routines first: their names make the rest readable.
- Done when (each): all 40 rows have a name and tier; ≥ 25 at tier 1+.

### Phase 1C — raw fallbacks (1 worker)
- **T-40** Group the 102 `dc.w` fallbacks by cause (which instruction
  form vasm re-encodes). Fix the generator one class at a time; gate
  after each class.
- Done when: fallbacks = 0, or the remainder is listed by class with the
  reason vasm cannot emit it.

### Phase 1D — unknown regions (up to 16 workers, after 1A)
- **T-50 Classifier.** Script tags every remaining `unknown` region:
  ASCII, long-pointer table (values inside ROM, even), word-offset table,
  LZSS header, 4bpp tile plausibility, Z80 code, padding (`$00`/`$FF`),
  high entropy.
- **T-51 … T-66** one card per bank: confirm or correct the classifier's
  tag by finding the code that reads the region (search `rop.s` for the
  address or a `lea`/`pea` to it). 20-minute cap per region.
- Done when (each): no region in the bank is `unknown` without a note
  saying what was ruled out.

### Phase 1E — RAM map (1–2 workers)
- **T-70** Script lists every `$FFxxxx` operand with reference count and
  the routines using it. Name the top 200. Seed from `docs/save.md`,
  `docs/logic.md`, `docs/architecture.md`.

### Phase 2 — after 1A done and routines named ≥ 60%
- **T-80** Emit pointer-bearing regions as `dc.l label` / `dc.w label-base`.
- **T-81** Shift test in the harness (insert 2 bytes, rebuild, boot,
  compare event logs).
- **T-82 … T-85** asset round-trip, one card per class: text, graphics,
  maps, sound.

### Parked — nobody picks these up unless Dayset names them
Tribute remake (Epic 5), research and history (Epic 6), the rendering fix
(L037), further game-mechanics verification. One patch slot may be open
at a time, and only with a target Dayset chose.

## 5. Templates

### Task card (GitHub issue body)
```
Goal: <one sentence>
Shard: <files this task may edit>
Inputs: <docs / tool outputs to read>
Method: <3–5 steps>
Done when:
- <metric> moves from X to ≥ Y
- make check passes
Time cap: 1 session. Unfinished part → new card.
Do not: ask about names; edit rop.s; chase leads.
```

### Worker start prompt
```
Read CLAUDE.md and docs/agent-playbook.md. Take the top unclaimed card in
the queue and assign it to yourself. Work only inside its shard. Do not
ask questions: apply the defaults in CLAUDE.md §1 and log anything for
the owner in docs/questions.md. Finish with a merged PR whose body lists
each "Done when" line as met / not met and the make check summary. Then
take the next card.
```

### Lead start prompt
```
Read CLAUDE.md and docs/agent-playbook.md. Do no reverse engineering.
1) Merge every open PR that passes make check; rebase it yourself if needed.
2) Close or land any branch older than 24 h.
3) Keep 8 or more unclaimed cards in the queue, cut from §4.
4) Answer docs/questions.md where a default is safe; leave the four
   owner-only items for Dayset.
Report only: metrics before → after, and cards remaining per phase.
```
