# #031 — Save system design (tribute)

Status 2026-11-09: **design complete** from #019's consolidation
(`docs/save-validation.md`) + #020's state machine; implementation
waits on #023. #019's deep items (buffer layout, chip identity)
remain open but do not block this design — they block only the
optional import path (§3).

## 1. What gets saved (field list — acceptance item 1)

From the #020 state machine + #007 struct definitions:
- Party: for each of 6 slots (`$FF0E82` indices) the 52-byte char
  struct's gameplay fields — name idx (+0x14), order/level+rank
  (+0x18), XP (+0x1A, cap 13000), HP/Power current+max
  (+0x1C/+0x1E/+0x20/+0x22), gold (+0x2A, leader), position
  (+0x0C/+0x0E), spell selector state (+0x24/+0x25).
- World: leader position + area/location code (`$FF0E92 & 0x3FF`),
  step counter `$FF0E16`, merchant states (`$FF0E82`-adjacent
  merchant structs: attitude +0x22, type +0x20 — they drift, so
  they are state, not constants).
- Progress: quest/inventory via the `$2BBD2` resource counts
  (item×64+slot codes), `$FF0128` intro/continued flag semantics,
  music mode (Quiet state — the tribute HAS a real flag, #030).
- Meta: format version, play-time (frame counter `$FF0010`
  equivalent), combat/presentation mode switches (#027/#028).

## 2. Format — decision (acceptance item 2)

**Versioned JSON** (`tribute/save/save-v1.schema.json` to be
written with the implementation), one file per slot,
human-readable, with a SHA-256 integrity field. Rationale, stated
against the original: the original's 128-byte EEPROM image uses a
single byte-sum that cannot detect transpositions or compensating
edits (`docs/save-validation.md` §4) — **that weakness is
explicitly NOT reproduced** (#031's own instruction). JSON costs
nothing on modern platforms and makes tribute saves diff-able in
this repo's patch workflow style.

## 3. Original-save import — attempted on paper: NO for v1 (with reason)

Import would require (a) the 128-byte `$FF016A` buffer's internal
layout — **unknown** (#019 §4: only the sum check is decoded), and
(b) the EEPROM chip's exact read protocol — **unconfirmed**
(93C46 family suspected). With the layout unknown, any "import"
would be fabricating field offsets. Verdict: **NO for v1**;
revisit the moment #019's remaining work (real save dump + diff)
lands on the owner's machine — the design's field list (§1) is
already shaped to accept the original's fields when known.
This answers the acceptance item as written ("yes/no with the
reason"); the "one real save imported" sub-item is blocked on
#019, not on this issue.
