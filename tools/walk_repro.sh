#!/bin/sh
# Subcell repro (#31): run a ROM from a BlastEm state, play a key script, log events.
# usage: tools/walk_repro.sh ROM STATE KEYS_FILE [FRAMES]
# KEYS_FILE: one token per line: a key name for xdotool, or "wait N" (frames).
# Key bindings are NOT verified on the CI VM; set KEYMAP to your window's bindings.
set -eu
ROM=$1; STATE=$2; KEYS=$3; FRAMES=${4:-1800}
OUT=${OUT:-build/walk-repro}
mkdir -p "$OUT"
BLASTEM=${BLASTEM:-/usr/games/blastem}
"$BLASTEM" -s "$STATE" -b "$FRAMES" -e "$OUT/events.bin" -l "$ROM" >"$OUT/run.log" 2>&1 &
PID=$!
sleep 3
while read -r tok arg; do
  case "$tok" in
    wait) sleep "$(echo "scale=3; $arg/60" | bc)" ;;
    "")   ;;
    *)    xdotool search --name BlastEm windowactivate --sync key "$tok" ;;
  esac
done <"$KEYS"
wait "$PID" || true
echo "done: events in $OUT/events.bin, executed addresses in $(ls "$OUT"/address.log 2>/dev/null || echo 'address.log (see BlastEm cwd)')"
