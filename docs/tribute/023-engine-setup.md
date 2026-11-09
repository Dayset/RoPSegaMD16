# #023 — Esenthel/Titan engine setup guide (tribute spec)

Status 2026-11-09 (agent session): **guide + decisions written;
engine build BLOCKED in this VM** (no engine source, multi-GB
download/build is owner-machine work). Sources: `docs/tribute-remake.md`,
issue #023, and web check 2026-11-09 (esenthel.com feature list +
the EsenthelEngine GitHub README as mirrored in search results).

## Decisions (recorded for the skeleton)

- **Source, not binary:** clone https://github.com/Esenthel/EsenthelEngine
  as a *sibling* checkout (`../EsenthelEngine`), NOT a submodule and
  NOT committed here — the engine is large and separately licenced;
  issue #023 acceptance requires recording the exact commit.
  Record it in `tribute/README.md` on first clone (line left blank
  there on purpose: `Engine commit: <fill on clone>`).
- **Licence (verified from the engine README, web 2026-11-09):**
  free to use for games/apps, unlimited titles, source may be
  redistributed and modified; **may NOT be integrated into other
  game engines not based on Titan/Esenthel**; engines/games based
  on it must state they are based on Esenthel. (One mirror shows a
  royalty clause from an older/other edition — **read the LICENSE
  file in the actual clone before shipping**; the tribute is
  non-commercial per `docs/tribute-remake.md`, which sidesteps the
  question but does not remove the duty to read it.)
- **Platforms:** engine supports Windows, Xbox, Mac, iOS, Android,
  Nintendo Switch, Linux, Web (esenthel.com). Tribute targets:
  **Windows + Linux first** (issue #023), others later.

## Build steps (to execute on the owner's machine)

1. `git clone https://github.com/Esenthel/EsenthelEngine ../EsenthelEngine`
   and record `git -C ../EsenthelEngine rev-parse HEAD` in
   `tribute/README.md`.
2. Open the engine's Editor project for the `tribute/` skeleton
   (layout in `tribute/README.md`); the engine's own tutorials
   (100+, per esenthel.com) cover the first-window scene.
3. First scene acceptance: a window rendering **one flat textured
   quad** using a #024-exported tile PNG — that single step proves
   engine + asset pipeline together.
4. Verify a Linux build from a clean checkout using only this doc
   + `tribute/README.md`; fix the docs, not just the build.

## Blockers (exact)

No Esenthel source in this VM; downloading + building a full C++
engine is out of scope for the agent session and would not be
verifiable headlessly (acceptance requires opening a window).
Everything downstream (#028 cameras especially) waits on step 3.
