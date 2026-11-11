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
