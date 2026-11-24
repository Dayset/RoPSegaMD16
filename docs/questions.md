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

## Q12 — Commit the dialogue export (assets/text/dialogue.txt)?
- Question: the round trip (`tools/text_roundtrip.py`) now re-encodes all 1184 dialogue records byte-identical. The export it writes is game text derived from ROM bytes, which is rule 4 (distributing ROM content).
- Default taken: commit the tool only. `assets/text/dialogue.txt` is generated locally and left untracked.
- If the answer is different: commit the export file as well, and the round-trip check can run in CI against it.

## Q13 — topdown (#249): walk pace and the next renderer
- Question: (a) the top-down test runs at the original's measured pace (26 frames per tick overworld, 17 in rooms). Keep it, or speed it up? (b) For the isometric look: pre-render the whole world offline into tile sets (needs a 2–4 MB ROM), or isometric only in rooms and the top-down map for the overworld?
- Default taken: (a) original pace (`TD_T1`/`TD_T2`, and `TD_TF` = 22 on the dragon, in `patches/topdown/feature.s`); (b) no renderer work yet; the next card is the byte-exact Python port of the `$E358` composite, which both options need.
- If the answer is different: (a) change two constants; (b) decides the size of the offline atlas build and the ROM size.


## Q14 — topdown (#255): show cell height in the oblique view?
- Question: draw cell height (0–7 levels) as raised tiles with shadowed south faces (mock-up `docs/img/topdown-height-mock.png`), keep the view flat, or tint by height only?
- Default taken: flat (no change); the mock-up and `tools/td_height_mock.py` are in.
- **Answered (Dayset, 2026-11-23): tinted.** Built in #264: height-0 cells shadowed, raised cells normal; the HUD band (screen lines ≥ 144) stays untinted.
- If the answer is different: raised tiles needs shadow/highlight mode, a painter-order cell draw (a cell's top can cover up to 3.5 cells to its north), streaming lookahead of 4 rows, and figures lifted by their cell's height — about one card.

## Q15 — smooth iso (#252): floating island in a fixed frame, or terrain edge to edge?
- Question: keep the original's look (a diamond of terrain on parchment) or fill the screen with terrain?
- Default taken: floating island. A fixed parchment frame in the window with a diamond hole (the camera's ±4 cells; the original shows ±5) hides the render's edges, so the picture inside only scrolls. In combat arenas (zoomed by the game) the top-down picture stands in.
- If the answer is different: edge to edge needs the plane to keep earlier renders (a world cache in VRAM with eviction by distance) and corners that are empty until visited, or a render ~2× larger than the decode buffer allows — about two cards.

## Q16 — smooth iso (#279): a quarter cell off the hole to remove render-edge slivers?
- Question: `tools/md_iso_edges.py` (#292) measured the camera's safe range as [−0.5, +1] cell per axis from the picture, while the code allows ±1, so parchment slivers show at the hole's edge in ~1/3 of overworld frames for a few frames after a picture lands. Shrink the hole by a quarter cell per side (±3.75 cells: `tools/td_iso_frame.py` HW 112 → 105, HH 64 → 60) and move it 4 px down so the range becomes ±1? About 6 % less terrain visible.
- Default taken: keep the ±4 hole (no change). Holding the camera to the measured range instead removes the edges but makes it trail ~2 cells (tested, #279 comment).
- **Answered (Dayset, 2026-11-23): keep ±4 as the default;** the 6 % smaller hole would be acceptable. Not built.
- If the answer is different: regenerate the frame data (`td_iso_frame.py`, its HW/HH/CY), re-run the edge checker; no other code changes.

## Q17 — target platforms and ROM size
- **Answered (Dayset, 2026-11-23):** play on BlastEm and other emulators, with the option of original hardware. Fitting the original 1 MB stays a goal of its own (fixing the 1992 bugs); spilling to 4 MB is acceptable.
- Taken: every ROM larger than 1 MB saves to header SRAM under its own product ID (`patches/sram-save`, #284), so no emulator database entry is needed and SRAM repro boards / flash carts work; the 1 MB builds keep the original EEPROM. A 4 MB build needs no further save work (`$A130F1` is already toggled), only `SIZES` in `tools/build_rom.py`.
- If the answer is different: `--eeprom` keeps the original save in a 2 MB build.
