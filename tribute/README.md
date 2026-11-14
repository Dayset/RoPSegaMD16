# Rings of Power — Tribute remake (M7)

Recreate the same environment (Ushka Bau, its cities, quests, systems) in
the open-source Esenthel C++ Titan Engine. A tribute project, not a
commercial product. No sale, no crowdfunding, clear attribution to
Naughty Dog / EA as the original creators.

Two switches (the product's heart):
1. **Presentation: classic (isometric) vs modern (3D).** Same world, same
   logic, two cameras/rendering styles. Classic aims at the original's look
   and feel (isometric overworld, original pacing); modern is a free 3D
   camera over the same terrain.
2. **Combat: old vs new.** Old = the original combat, bugs and all;
   new = a fixed combat. Switchable, so the tribute never pretends the
   fix is the original.

Rule: a remake behaviour is either **verified** (traced to a ROM address)
or labelled **tribute** (our invention, e.g. the new combat). Never present
a tribute behaviour as "how the original worked". The RE docs in this repo
are the spec the remake implements.

## Layout

- `RoP/` — the tribute app (classic isometric mode, #023). Source in
  `RoP/Source/`, Linux build in `RoP/Linux/`, data in `RoP/Data/`.
- `EsenthelEngine/` — the engine source. **Not committed to this repo**
  (large, separately licenced). See `ENGINE_VERSION.txt` for the exact
  commit. Clone vs submodule decision (#023): **clone** (a separate
  directory, not a submodule), because the official repo is gone and a
  submodule would force every fresh checkout to clone the full history
  of a fork-of-a-fork. The version is pinned by hash in
  `ENGINE_VERSION.txt`; re-fetch it with the tarball URL in `build.sh`.
- `build.sh` — top-level build (ThirdPartyLibs -> Engine -> RoP app).
- `patches/` — engine patches applied by `build.sh` after a fresh fetch
  (see "Engine patches" below).
- `assets/` — extracted ROM assets (the #024 asset pipeline output).

## Engine patches (#023)

The stock 2019 engine segfaults at startup (Gui.* globals are null when
the first Desktop is constructed). Three null-deref guards in
`Engine/Source/Gui/Gui Object.cpp` fix it; they live in
`patches/esenthel-null-deref.patch` (4 hunks) and `build.sh` applies the
patch automatically after a fresh engine fetch (skipped when already
applied). The patch was verified against the true 86f897a tarball:
applies cleanly, result byte-identical to the #023 worktree's patched
file, app starts and renders. The engine itself is never committed, so
the patch file is the only copy of the fix — do not delete it.

## Engine source (#023)

- **Source:** `feiyunwill/EsenthelEngine`, master,
  commit `86f897a749522d14207772e5d055e00b8ea4ddce` (2019-03-10, "ok").
  Pinned in `ENGINE_VERSION.txt`.
- **Why this copy:** the official `Esenthel/EsenthelEngine` GitHub repo
  is gone (404 via the API, 2026-11-14). The surviving copies are forks
  of `feiyunwill/EsenthelEngine`; this is the canonical, smallest one
  (373 MB full history, 1.2 GB extracted). Mirrors exist
  (`Karolyna84/EsenthelEngine`, `study-game-engines/esenthel`) but are
  larger and no newer.
- **Licence:** free to use to create games/applications; unlimited
  games/apps; source may be redistributed; may NOT be integrated into
  other game engines not based on Titan/Esenthel. Our engine code built
  on it must clearly state it is based on Esenthel. (Read the licence
  file in the engine repo before shipping anything.)
- **Linux build:** the engine's Linux makefiles use **clang++** (not
  g++). Requires clang plus X11/GL/OpenAL/Motif dev libraries
  (`libmotif-dev` for `Xm/MwmUtil.h`, plus `libxrandr-dev`,
  `libxinerama-dev`, `libxmu-dev`, `libxxf86vm-dev`, `libxi-dev`,
  `libxcursor-dev`, `libopenal-dev`, `libudev-dev`, `libgl1-mesa-dev`,
  `zlib1g-dev`, `unixodbc-dev`, `libxext-dev`).
- **PhysX:** the real PhysX SDK is NOT in the engine repo (only
  `Android` + `Dummy`). On Linux the app links the **Dummy** libs
  (`ThirdPartyLibs/PhysX/Dummy/Linux`, pre-built stubs). Verified:
  the built `EsenthelEngine.a` references 0 real PhysX SDK symbols,
  so the dummy libs satisfy the link.

## Build

```sh
./build.sh            # ThirdPartyLibs -> Engine -> RoP app (Release)
./build.sh clean      # clean all build outputs
```

Or step by step (all Release, from `tribute/`):

```sh
# ThirdPartyLibs (17 libs that need building; FBX/JpegTurbo/Flac/Opus/VP
# and PhysX-Dummy are pre-built and skipped)
for lib in Recast Png Vorbis Theora SQLite Webp LZ4 Ogg Tiff FreeType \
           Bullet Snappy LZMA LZHAM Zstd FDK-AAC mbedTLS; do
  make -C EsenthelEngine/ThirdPartyLibs/$lib/Linux CONF=Release -j2
done
# Engine (324 .cpp files, ~10 min at -j2)
make -C EsenthelEngine/Engine/Linux CONF=Release -j2
# RoP app
make -C RoP/Linux CONF=Release
```

Run (from the RoP dir — DataPath is relative to the working directory):

```sh
cd RoP && ./RoP        # arrow keys walk the dot, ESC quits
```

The window is 1024x768 windowed (set in InitPre via D.mode). Do NOT run
fullscreen under a headless X server: DrawState() skips drawing when
fullscreen + unfocused, which is always true there.

## Status (#023, engine setup & project skeleton)

- [x] Engine source acquired + pinned (feiyunwill, 86f897a, 2019-03-10)
- [x] Engine static lib builds on Linux (`EsenthelEngine.a`, 17 MB, 0 errors)
- [x] ThirdPartyLibs build (17 libs; 6 pre-built, PhysX dummy)
- [x] RoP app builds + runs (classic isometric skeleton)
- [ ] Game rules (later issues: #024 assets, #025 world, #026 logic,
      #027 combat, #028 presentation, #029 dialogue, #030 audio, #031 save)

## Workstreams (docs/tribute-remake.md, Epic 5, milestone M7)

- #023 engine setup & project skeleton (this) — done
- #024 asset extraction pipeline (builds on #004–#006)
- #025 world & overworld
- #026 game logic reimplementation (needs #007/#008 docs)
- #027 combat: classic vs new (needs #007)
- #028 presentation: classic isometric vs modern 3D (needs #025)
- #029 dialogue & UI (builds on #004)
- #030 audio (needs #018)
- #031 save system (needs #019)

Note: the GitHub issues numbered #023/#024 are NOT these workstreams
(#023 is a docs issue about packed-vs-planar tiles, #024 is a workflow
issue). The M7 milestone on GitHub is empty (0 issues) — the #023–#031
workstream numbers come from docs/tribute-remake.md and were never
filed as GitHub issues. Filing the M7 workstream issues is a follow-up
for the parent agent, not this setup task.
