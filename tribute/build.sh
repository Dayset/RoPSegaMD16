#!/bin/bash
# Top-level build for the RoP tribute (M7, 2D classic mode).
#   ./build.sh        # ThirdPartyLibs -> Engine -> RoP app (Release)
#   ./build.sh clean  # clean all build outputs
#
# Engine source: feiyunwill/EsenthelEngine, pinned in ENGINE_VERSION.txt.
# If EsenthelEngine/ is missing, fetch it first (tarball, fast):
#   curl -sL -o /tmp/esenthel.tar.gz \
#     https://codeload.github.com/feiyunwill/EsenthelEngine/tar.gz/$(cat ENGINE_VERSION.txt)
#   tar -xzf /tmp/esenthel.tar.gz
#   mv EsenthelEngine-*/ EsenthelEngine
set -e
cd "$(dirname "$0")"

ENGINE_COMMIT=$(cat ENGINE_VERSION.txt)
ENGINE_DIR=EsenthelEngine

if [ "$1" = "clean" ]; then
  echo "Cleaning..."
  make -C "$ENGINE_DIR/Engine/Linux" clean CONF=Release 2>/dev/null || true
  for lib in Recast Png Vorbis Theora SQLite Webp LZ4 Ogg Tiff FreeType Bullet Snappy LZMA LZHAM Zstd FDK-AAC mbedTLS; do
    make -C "$ENGINE_DIR/ThirdPartyLibs/$lib/Linux" clean CONF=Release 2>/dev/null || true
  done
  make -C RoP/Linux clean 2>/dev/null || true
  echo "Clean done."
  exit 0
fi

if [ ! -d "$ENGINE_DIR/Engine" ]; then
  echo "ERROR: $ENGINE_DIR/Engine not found."
  echo "Fetch the engine first (commit $ENGINE_COMMIT):"
  echo "  curl -sL -o /tmp/esenthel.tar.gz https://codeload.github.com/feiyunwill/EsenthelEngine/tar.gz/$ENGINE_COMMIT"
  echo "  tar -xzf /tmp/esenthel.tar.gz && mv EsenthelEngine-*/ $ENGINE_DIR"
  exit 1
fi

# 0. Engine null-deref patches (RoP M7 #023) — the stock 2019 engine
#    segfaults at startup without them (Gui.* globals are null when the
#    first Desktop is constructed). Applied once after a fresh fetch;
#    skipped when already applied (PATCH marker present in the file).
#    The patch file is committed with the project (patches/); the engine
#    itself is re-fetched, never committed. Verified against the true
#    $ENGINE_COMMIT tarball: applies cleanly, result byte-identical to
#    the #023 worktree's patched file, app starts and renders.
#    NOTE: the filename has a space, so `patch` gets the file explicitly
#    (header parsing cannot find it).
PATCH_FILE="patches/esenthel-null-deref.patch"
PATCHED_FILE="$ENGINE_DIR/Engine/Source/Gui/Gui Object.cpp"
if ! grep -q "PATCH (RoP M7 #023" "$PATCHED_FILE" 2>/dev/null; then
  echo "=== Engine patches ==="
  command -v patch >/dev/null 2>&1 || { echo "ERROR: 'patch' is required to apply $PATCH_FILE"; exit 1; }
  echo "Applying $PATCH_FILE ..."
  patch -p1 -d "$ENGINE_DIR" "Engine/Source/Gui/Gui Object.cpp" < "$PATCH_FILE" \
    || { echo "ERROR: engine patch failed to apply (see $PATCH_FILE)"; exit 1; }
  grep -q "PATCH (RoP M7 #023" "$PATCHED_FILE" \
    || { echo "ERROR: engine patch did not land in $PATCHED_FILE"; exit 1; }
fi

# The app reads engine data via RoP/Data (CWD-relative, see the #023
# report). The symlink is a build-time artifact of the engine layout,
# not committed — (re)create it here so a fresh clone just works.
ln -sfn ../EsenthelEngine/Data RoP/Data

# 1. ThirdPartyLibs that need building (FBX/JpegTurbo/Flac/Opus/VP and
#    PhysX-Dummy are pre-built and skipped).
echo "=== ThirdPartyLibs ==="
for lib in Recast Png Vorbis Theora SQLite Webp LZ4 Ogg Tiff FreeType Bullet Snappy LZMA LZHAM Zstd FDK-AAC mbedTLS; do
  echo "--- $lib ---"
  make -C "$ENGINE_DIR/ThirdPartyLibs/$lib/Linux" CONF=Release -j2
done

# 2. Engine static lib.
echo "=== Engine ==="
make -C "$ENGINE_DIR/Engine/Linux" CONF=Release -j2

# 3. RoP app.
echo "=== RoP app ==="
make -C RoP/Linux CONF=Release

echo ""
echo "Built: RoP/RoP"
echo "Run:  cd RoP && ./RoP   (arrow keys walk the dot, ESC quits)"
