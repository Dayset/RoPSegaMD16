#!/bin/sh
# setup.sh — one-command toolchain install and version check (GitHub issue #4).
# Debian/Ubuntu: apt packages. Then capstone pinned via pip, vasm built by tools/install_vasm.sh.
# Usage: sh tools/setup.sh        (re-runnable; each step is skipped when already satisfied)
set -eu
cd "$(dirname "$0")/.."
CAPSTONE=5.0.7
APT_PKGS="binutils-m68k-linux-gnu blastem xvfb xdotool openjdk-21-jre-headless build-essential git python3-pip"

if command -v apt-get >/dev/null 2>&1; then
    missing=""
    for p in $APT_PKGS; do
        dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"
    done
    if [ -n "$missing" ]; then
        echo "installing:$missing"
        sudo apt-get install -y $missing
    fi
else
    echo "no apt-get: install these by hand: $APT_PKGS"
fi

if ! python3 -c "import capstone, sys; sys.exit(capstone.__version__ != '$CAPSTONE')" 2>/dev/null; then
    python3 -m pip install --user "capstone==$CAPSTONE" 2>/dev/null \
        || python3 -m pip install --user --break-system-packages "capstone==$CAPSTONE"
fi

if [ ! -x tools/vasm/vasmm68k_mot ] || [ ! -x tools/vasm/vasmz80_oldstyle ]; then
    sh tools/install_vasm.sh
fi

# Version check: fails loudly if anything the build or the tests need is missing.
fail=0
check() { printf '%-28s %s\n' "$1" "$2"; }
check "python3" "$(python3 --version 2>&1)"
cap=$(python3 -c "import capstone; print(capstone.__version__)" 2>/dev/null || echo missing)
check "capstone (need $CAPSTONE)" "$cap"; [ "$cap" = "$CAPSTONE" ] || fail=1
check "vasmm68k_mot" "$([ -x tools/vasm/vasmm68k_mot ] && echo ok || echo missing)"; [ -x tools/vasm/vasmm68k_mot ] || fail=1
check "vasmz80_oldstyle" "$([ -x tools/vasm/vasmz80_oldstyle ] && echo ok || echo missing)"; [ -x tools/vasm/vasmz80_oldstyle ] || fail=1
check "m68k-linux-gnu-as" "$(m68k-linux-gnu-as --version 2>/dev/null | sed -n 1p || echo missing)"
check "blastem" "$(command -v blastem || ls /usr/games/blastem 2>/dev/null || echo missing)"; [ -e /usr/games/blastem ] || command -v blastem >/dev/null || fail=1
check "xvfb-run" "$(command -v xvfb-run || echo missing)"
check "java" "$(java -version 2>&1 | grep -v JAVA_TOOL_OPTIONS | sed -n 1p || echo missing)"
if [ -d .git ]; then
    git config core.hooksPath tools/hooks   # pre-push gate (#5)
fi
[ "$fail" -eq 0 ] && echo "PASS toolchain ready" || { echo "FAIL toolchain incomplete"; exit 1; }
