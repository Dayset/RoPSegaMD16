# Reconciliation of the two work lines (2026-11-09, session #8)

The `agent/all-open-issues` branch union-merged two independently
run work lines (sessions #1–#7 of the agent line, and a parallel
main-line set of sessions) at 6ed21f0. PROGRESS.md's merge note
kept both lines' claims standing "until reconciled with
evidence". This document is that reconciliation: every
disagreement found in the merged corpus, with claim A (agent
line), claim B (main line), a verdict, and the evidence —
including the checks re-run for this document. Neither line's
text is deleted; verdicts stand alongside the original claims.

## R1 — #011 function and edge counts: 446/1,449 vs 438/1,434 (and a 436)

- **Claim A (agent line):** 438 functions / 1,434 edges
  (`disasm/ghidra/function_map.csv`; also the #003 entry's
  "436 functions, 1,434 edges" from an earlier run).
- **Claim B (main line):** 446 functions / 1,449 edges
  (`disasm/ghidra/functions.txt`, `call_edges.txt`); "auto-
  analysis found 435; 11 created manually".
- **Evidence (recomputed from the two exports in the tree):**
  the 438 set is a strict subset of the 446 set. The delta is
  exactly 8 function starts: **0x2988E, 0x2B2B2, 0x2B502,
  0x3536C, 0x3539A, 0xEB7C8, 0xEB8E0, 0xEBA00**. The main
  line's PROGRESS entry names its 11 manual creations: those
  same 8 plus 0x1270, 0x1272 and $EB772 — and those three
  *are* present in the agent line's export. 8 + 3 = 11: the
  delta is fully accounted for. The "435 auto" vs the agent
  export's composition (387 auto + 51 doc-sourced) is
  bookkeeping from different analysis configurations (the main
  line itself records that Ghidra merges flow-connected
  routines, e.g. $2B240 into FUN_0002b190); the 436 in the
  #003 entry is an earlier run of the same kind. Edges:
  1,434 (agent CSV callee sum) vs 1,449 (main call_edges.txt);
  set difference = +23 main-only (13 are the 8 extra
  functions' edges; 10 are self-edges X→X the CSV export
  drops) and −8 agent-only (small edges in the 0xDCxx/0xEB9xx
  joypad/sound regions the TXT export does not record).
  1434 + 23 − 8 = 1449. ✓
- **Verdict:** both counts are accurate reports of their own
  Ghidra projects. The ROM-level union is **446 function
  starts, 11 of them human-created** (8 unique to the main
  export). Cite counts as "446 (union) / 438 (agent export)"
  and "1,449 / 1,434 edges (export-dependent)". #011 is done
  on both lines — no status disagreement.

## R2 — #021: done vs in progress

- **Claim A (agent line):** in progress — after session #7,
  on sub-items (g) (the Void death string's caller) and 2(b)
  (a genuine Map purchase) alone.
- **Claim B (main line):** done 2026-11-09 (issue header;
  PROGRESS "M4 complete") — while its own Result text still
  listed the Void trigger, the food/water routine and live
  combat as not located/attempted.
- **Evidence:** mapped against the issue's written acceptance
  (tables located; every `docs/overview.md` audit question
  answered with an address + trace; debug reachability
  decided; audit written to docs/logic-audit.md): every item
  is met by the combined corpus — gold overflow and negative
  damage (main §2/§3, proven + reproduced), save checksum
  (both lines), debug mode (both lines), food/water (agent
  §8/§10, R4), live combat caller $3A842 (agent §9), the
  §11.3 list (agent §12), and, as of session #8, the Void
  question (agent §13.1: there is no trigger — the text is
  the fatal-error screen $12072's message, its "seconds"
  number a decimal error code). The genuine Map purchase
  (2b) is not an acceptance item: it began as the means to
  execute the pad-2 teleport (agent §10.3), which was
  executed via a labelled scratch-ROM grant (§11); the
  purchase itself remains open as a follow-on experiment
  (agent §13.2) and stays tracked in PROGRESS's Next list.
- **Verdict:** **#021 is done** — its acceptance is met by
  the two lines' combined evidence, completed in session #8.
  The main line's "done" was early when written (its open
  items were real at that point); the agent line's "in
  progress" was correct at every point it was written. The
  Map purchase (2b) remains open as a follow-on, explicitly
  not a #021 blocker.

## R3 — #017: "0x044000 killed" vs "0x044000 is $DD5C maps"

- **Claim A (agent line):** closed in session #5 — the
  0x044000–0x05FFFF bulk IS a $DD5C LZSS archive: 252-record
  descriptor table at 0x043850, streams 0x044228–0x05EDC3,
  `tools/decode_44000.py` decodes 252/252 byte-exact;
  consumer FUN_00019692 via $13654 with a 4-slot cache;
  content = VDP nametable map data.
- **Claim B (main line):** its #017 entry says the **same
  thing** (252 records, table $43850, base 0x44228, streams
  contiguous to 0x05EDC4, 252/252 exact, $19692 4-slot cache
  via $1C802; content split 99 × 2048 B 32×32 chunks + 153 ×
  242 B 11×11 chunks — the same two sizes the agent line
  recorded). Its #021 §12 separately "killed" 0x044000 **as
  the $E358 terrain-stream source**, precisely scoped
  ("killed for the terrain stream") — which is also true,
  and agrees with claim A. The contradiction exists only in
  the unscoped summary compressions (the main line's #021
  Result line and the PROGRESS #021-done bullet: "0x044000–
  0x05FFFF killed").
- **Verdict:** **0x044000 is a $DD5C map archive** (both
  lines, independently, byte-exact 252/252) **and** it is
  not the $E358 stream source (both lines). Read the two
  "killed" summaries with §12's scope. The agent line's own
  session-#2 "not $DD5C" verdict was already retracted by
  its session #5.
- **Sub-point — the $5F524 table's extent:** main line "176
  u32, streams 0x603E4+, last ends ~0x68300" vs agent line
  "944 entries, streams $0603E4–$096069, 943/943 validated"
  (`tools/decode_e358.py`). Recomputed from the ROM: the
  table holds **944 distinct, monotonically increasing u32
  offsets filling $5F524–$603E3 exactly** (944 × 4 lands the
  table's end precisely on the stream base $603E4); the
  largest offset 0x35C85 puts the last stream at 0x96069.
  The 176 figure is the table's prefix (entry 175 → stream
  ≈ 0x6825B ≈ "~0x68300"). **Verdict: 944 is the full
  table; the main line read a prefix.**

## R4 — Food/water consumption: "not located" vs Camp + step drain

- **Agreement first:** $FF0E16 is the world clock (mod-2400
  tick counter), not a provisions store (both lines); the
  four named candidates $2F1F0/$2FA2A/$302F0/$2EC80 do not
  consume provisions (main line: they are save serialisation
  pushing $FF0E16 &c. into the $FFA800 save buffer; agent
  line §7.2 reached the same negative); $32C56 is a
  4-direction tile scan, not consumption (both lines).
- **Claim A (agent line):** the routine IS located — Camp
  ($3019A) consumption block at 0x30346–0x303B4 takes
  **−100 Food / −100 Water per Camp** from $FFC364/$FFC366,
  clamped [1, 30000], **live-measured exactly** (§8.1, §9);
  and movement drains per step in FUN_00024984 (store at
  0x24F78), **live breakpoint-measured at −3 Food / −1 Water
  per grassland step**, with a 60 s idle control draining
  nothing (§10.1). Session #8 re-confirmed the same stores
  live (overworld travel: Food 1312 → 472, Water 1728 →
  1458, the same 3:1 ratio; §13.2).
- **Claim B (main line):** "routine NOT located; leads
  killed" (§13), with the guide's per-terrain rates (Grass
  4/2, Desert 7/5, …) left as hypotheses.
- **Verdict:** **claim A stands** — the consumption routine
  is located and measured (Camp + per-step drain). The main
  line's kills of the named candidate sites also stand; only
  its headline conclusion is superseded (its own §13 "next
  leads" pointed at the tick path the agent line then
  traced). Its "$FF0E16 readers are save code" is true of
  the four named functions, not of $FF0E16 generally
  (world_tick advances and reads it). The guide's rates
  remain unverified player-observed numbers: the code's
  per-step amounts are the step record's +0x26/+0x28 fields
  (terrain-dependent in principle), and the one measured
  terrain — grassland, 3/1 — does not match the guide's
  Grass 4/2.

## R5 — Terrain stream source: "~0x60400+" vs $0603E4

- **Verdict: not a disagreement.** The main line's own §12
  text gives the mechanism exactly (`adda.l #$603E4, a0`);
  "~0x60400+" in its summaries is the same base loosely
  rounded (offset[0] = 0, so the first stream starts at
  $603E4 itself). The agent line's census (944 streams,
  $0603E4–$096069, table $5F524 — see R3) is the precise
  form. Cite **$0603E4**.

## R6 — Post-harness PC=0: the `rts` fix vs the `lea` fix

- Both lines diagnosed the identical root cause (a `jsr`
  hook inside the VBlank busy-poll at 0x35C whose `jmp`
  exits never pop the pushed return address — a 4-byte
  stack leak per poll iteration). The main line fixed it
  with `rts` in all three harness sources (verified: #007
  harness 90/90, 12 s clean); the agent line fixed it with
  `lea 4(%sp),%sp` at the exits of the two harnesses it used
  (§12.8). Both fixes coexist in the merged tree.
- **Verdict:** same diagnosis, two valid fixes; no conflict
  and no action. (The main line's observation that the #008
  harness faults identically if left running matches the
  agent line's §12.8 note verbatim in substance.)

## Checked — no material disagreement

- **#015/#016:** both lines closed them independently with
  complementary, consistent findings (register sets and the
  G/L layouts; sprites written straight to VRAM by $11BD8 —
  named by both lines; $EB772 is the sound tick, not a draw
  dispatch — corrected by both lines).
- **#017 status:** both lines closed it (R3); PROGRESS's
  board row was simply stale and is updated.
- **#019 / save medium:** serial EEPROM via $200000, 128 B,
  forgeable sum — both lines agree (agent line's
  docs/save-validation.md, main line's docs/save.md).
- **Dead distance term in $3B1EE (#022):** both lines found
  it (main §3's damage traces; agent #007) — the shipped
  patch rests on shared ground.

## PROGRESS.md updates made with this document

- The merge note above the main-line section now points
  here.
- Board rows corrected where a verdict supports it: #017
  → done; #021 → done (the genuine Map purchase carried as
  an open follow-on in the Next list, per R2); the Epic 2 /
  Epic 3 / M3 / M4 status texts updated to match.
- Next-list item 2 rewritten to the post-session-#8 state:
  (g) done (§13.1); only the Map purchase (2b) remains,
  with its §13.2 resume recipe.
