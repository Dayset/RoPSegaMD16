# Tribute remake — Rings of Power in the Esenthel (Titan) Engine

Goal stated by Dayset, 2026-11-09: **recreate the same environment
with an open-source custom 3D engine — a tribute project.** The engine
is the **Esenthel C++ Titan Engine**.

## The goal, in Dayset's words (paraphrased only where noted)

- Recreate the same environment (Ushka Bau, its cities, quests, systems)
  in a modern 3D engine.
- We need **all the routines and game logic** — that is what the
  reverse-engineering work in this repo is for: the RE docs are the
  spec the remake implements.
- Some parts, like the broken/crutched combat, **can be replaced or
  switched between old/new** — the original combat stays available as
  "classic", a fixed combat as "new".
- The game can run in **classic style (isometric)** and **modern**
  (3D camera) — both presentations of the same world and logic.
- It is a **tribute project**, not a commercial product.

## The engine (verified 2026-11-09)

- **Esenthel Engine ("Titan Engine")**, by Grzegorz Slazinski, in
  development since 2000. C++.
- Full source at https://github.com/Esenthel/EsenthelEngine; binary
  edition from https://esenthel.com. Docs at https://esenthel.com/?id=doc.
- Licence (per the repo README): free to use to create games and
  applications; unlimited games/apps; source may be redistributed;
  **may NOT be integrated into other game engines not based on
  Titan/Esenthel** — our own engine code built on it must clearly
  state it is based on Esenthel. (Read the licence file in the repo
  before shipping anything.)
- Cross-platform: Windows version builds for Windows, Android,
  Nintendo Switch and Web; Mac/Linux projects exist too. Editor with
  100+ tutorials; its Code Editor writes C++ without hand-written
  headers.
- The engine source itself is **not** committed to this repo (it is
  large and separately licenced) — #023 decides clone vs submodule
  and records the exact version/commit used.

## What the RE work is for now

Every RE issue feeds the remake as a spec:

| RE issue | Remake use |
|---|---|
| #003 entry/VBlank/save | boot flow, frame loop, input, save format |
| #004 text/dialogue | dialogue data + dictionary decoder → engine text |
| #005 graphics | tiles/palettes → 3D textures, sprite art direction |
| #006 maps | world map + (once found) walkable terrain grid |
| #007 game logic | XP/level, gold/shops, combat formulas, food/water |
| #008 spells | six-arts spell tables, costs, effects |
| #015/#016 VDP/VRAM | how the original presented the world (classic look) |
| #017 compression | asset decoding for the export pipeline |
| #018 sound/Z80 | music/SFX map → remake audio |
| #019 save | save format → modern saves (with import, if feasible) |
| #020 main loop | state machine → engine game states |
| #021 flaw audit | which bugs to keep (classic) vs fix (new) |

Rule: a remake behaviour is either **verified** (traced to a ROM
address) or labelled **tribute** (our invention, e.g. the new combat).
Never present a tribute behaviour as "how the original worked".

## The two switches (the product's heart)

1. **Presentation: classic (isometric) vs modern (3D).** Same world,
   same logic, two cameras/rendering styles. Classic aims at the
   original's look and feel (isometric overworld, original pacing);
   modern is a free 3D camera over the same terrain.
2. **Combat: old vs new.** Old = the original combat, bugs and all
   (the ~5-times-redone system the game jokes about, rec 1004);
   new = a fixed combat. Switchable, so the tribute never pretends
   the fix is the original.

## Scope and non-goals

- The remake lives in `tribute/` in this repo, separate from
  `disasm/` and `tools/`. The original ROM is still never committed
  and never modified in place; the remake reads exported data, not
  the ROM at runtime (decide in #024 whether the shipped game needs
  the user to supply a ROM — default: no, export at build time).
- The ROM-rebuild contract (Epic 1) still stands: it is how we prove
  the RE is right, and the mod workflow (Epic 4) continues in
  parallel — the remake does not replace it.
- No new art direction decisions in this doc — assets start as
  faithful exports of the original tiles/palettes/maps; new 3D art
  is a later decision, owned by whoever takes #025/#028.
- Non-commercial tribute: no sale, no crowdfunding, clear
  attribution to Naughty Dog / EA as the original creators.

## Workstreams (issues #023–#031, Epic 5, milestone M7)

- #023 engine setup & project skeleton (start now)
- #024 asset extraction pipeline (start now, builds on #004–#006)
- #025 world & overworld (start now on the known map; grid work continues)
- #026 game logic reimplementation (needs #007/#008 docs)
- #027 combat: classic vs new (needs #007)
- #028 presentation: classic isometric vs modern 3D (needs #025)
- #029 dialogue & UI (start now, builds on #004)
- #030 audio (needs #018)
- #031 save system (needs #019)

Parallel rules for agents: each issue owns its files (see the issue);
`tribute/` is the shared tree — coordinate through the issue files,
never by editing another issue's files. Research/history issues
#032–#036 (Epic 6) run in parallel with everything.
