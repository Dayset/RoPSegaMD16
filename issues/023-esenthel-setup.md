# Issue #023 — Esenthel engine setup & project skeleton

**Milestone:** M7
**Epic 5** (Tribute remake)
**Status:** open

## Goal
Stand up the tribute project: Esenthel (Titan) Engine building from
source, with a skeleton `tribute/` project that opens a window and
renders a first scene. This is the foundation every other Epic 5
issue builds on.

## Acceptance
- [ ] Esenthel Engine source obtained (clone or submodule — record the
  exact version/commit and the licence file location; engine source
  itself is NOT committed to this repo)
- [ ] A minimal `tribute/` project builds on this machine (Linux) and
  opens a window / renders a first scene (a flat test terrain or a
  single textured quad is enough)
- [ ] Build steps written down in `tribute/README.md` so another
  agent (or Dayset) can reproduce the build from scratch
- [ ] Target platforms noted (Windows/Linux first; Android/Switch/Web
  later, per the engine's own support)

## Notes
- Engine: Esenthel Engine ("Titan Engine"), C++, Grzegorz Slazinski.
  Full source: https://github.com/Esenthel/EsenthelEngine. Binary from
  https://esenthel.com, docs at https://esenthel.com/?id=doc.
  Licence: free to use for games/apps, source redistributable, may
  NOT be integrated into other engines not based on Titan — our code
  must state it is based on Esenthel. Read the licence before shipping.
- See `docs/tribute-remake.md` for the goal (classic isometric vs
  modern 3D, combat old vs new, tribute not commercial).
- Owns: `tribute/` (skeleton, build files, README). Do not touch
  `disasm/`, `tools/`, `docs/` (except a pointer line if needed), or
  another Epic 5 issue's files.

## Depends on
Nothing. Start now — this is the first parallel track.

## Status
open


## Work done 2026-11-09 (agent session, no ROM in VM)

- **Deliverable:** docs/tribute/023-engine-setup.md (decisions: source clone as sibling checkout, exact-commit recording, licence summary verified by web check 2026-11-09 with an editions discrepancy flagged, Windows+Linux first) + tribute/README.md skeleton with the per-issue directory ownership table.
- **Acceptance:** PARTIAL: skeleton doc + build steps written. BLOCKED: engine source is not in this VM and acceptance requires building + opening a window — owner-machine work; engine commit + licence-file lines in tribute/README.md are deliberately blank until the clone exists.

**Status after this session:** in progress — partial (see below). Not marked done.
