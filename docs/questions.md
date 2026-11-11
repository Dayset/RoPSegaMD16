# Open questions (owner decisions)

Each entry: question, the default taken, what changes if the answer is different.
Work continues on the default.

## Q1. `$26B58`: level-up or message queue?
- Default: keep both readings recorded side by side; name nothing new until a trace settles it.
- If the owner rules otherwise: rename the routine to match the chosen role and drop the other note.

## Q2. `$2BBD2`: resource routine or XP handler?
- Default: keep the current name; record the XP handler `xp_grant` (0x2C4E2) as a separate caller path.
- If the owner rules otherwise: rename `$2BBD2` to the chosen role.

## Q3. SFX table size: 1,365 bytes (measured) or 1,518 (69 x 22)?
- Default: trust the measured 1,365-byte row (0x0FCAE2-0x0FD036) in `disasm/doc_regions.csv`; flag the 1,518 figure as a doc error.
- If the owner rules otherwise: extend the SFX row to 1,518 bytes and re-run the gate.

## Q4. What does "M8 (all bytes accounted)" mean?
- Default: every byte is either an instruction or a documented data region; every routine is named; every computed jump target is labelled.
- If the owner rules otherwise: the M8 gate changes; no code changes needed now.

## Q5. L022 first-mod target (#022)?
- Default: the rendering fix (GitHub #22 / L037): sub-cell walking. Order #31 repro harness -> #26 diagnose the ~3 Hz update tick -> #27 -> #28. Dayset is already on #31 and #26. Patch lands in `patches/` once the gate passes with no changes.
- If the owner rules otherwise: replace this target in `issues/022-first-mod.md` (one system, one address range) and re-point the card order; nothing already built is wasted.

## Q6. Reference owner for the RAM write check: dominant writer or note owner?
- Default: dominant writer when the word is written; note owner used only for read-only words (`tools/ram_writecheck.py`, playbook section 6).
- If the owner rules otherwise: the check compares against the note owner again; 867a, 0092 and the other mismatches fail until renamed.

## Q7. Should the RAM write check block `make check`?
- Default: report only. `--strict` exists but is not in the gate.
- If the owner rules otherwise: add `--strict` to the Makefile; currently 0 fail and 8 or so have outside writers, so the gate would turn red until those are resolved.

## Q8. Minimum site count for tier-1 RAM names (currently 10, half share)?
- Default: keep 10 and half share. Top-200 ranks 101 to 200 have 9 or fewer references, so they stay tier 0.
- If the owner rules otherwise: lower the minimum to 5 and re-run the batches on ranks 101 to 200 (about 100 names, mostly weak).

## Q9. Are `ram_sys_verb_*` names (bb6f, a7f8) better under `menu`?
- Default: keep `sys`, since `sys` is the grammar default and the names are not wrong. Rename all `verb` words together in one PR if the answer changes.
- If the owner rules otherwise: rename `ram_sys_verb_*` to `ram_menu_verb_*` in one PR after checking `verb_exec` is only reached from menu code.

## Q10. Close stale issues #2 and #3 and open PR #1?
- Default: leave all three open. The close attempt was denied by the external-write check; #3 describes `split_disasm.py` and GAS, which are gone from main; PR #1 has a 2026-11-09 comment saying its merge commit was pushed.
- If the owner rules otherwise: close #3 as superseded; either merge PR #1 (if its merge commit is real) or close it unmerged with the branch kept.

## Q11. The high-entropy block `0x044228-0x05EDC3` (109,468 bytes).
- Default: stays unclassified, class `high-entropy`. The pointer scan found about 2,087 hits, but 1,185 are inside the classified dialogue table, 128 are opcode misreads, 41 follow move immediates, and 342 are inside code or 176 inside text data; no pointer table was found (lead in `docs/leads.md`).
- If the owner rules otherwise: decide whether to treat the block as LZSS payload and attempt a decoder pass, which is a larger task.
