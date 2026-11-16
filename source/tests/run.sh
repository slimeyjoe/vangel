#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Run the conformance tests. $1 = the build directory (../build/host), holding tests/ and the
# engine. The data-free tests run first; the ones that need the imported game (make data) or
# the pack (make pack) are skipped with a note when those are missing, and the ones against
# the original code under emulation when there is no Python with unicorn (EMU_PYTHON).
set -u
BUILD=${1:-../build/host}
BIN=$BUILD/tests
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
GAME=${GAME:-virginangel}
PAK=${PAK:-$ROOT/build/$GAME.pak}
PY=${PYTHON:-python3}
EMU_PY=${EMU_PYTHON:-$(command -v "$PY")}
rc=0

run() {
    echo "== $*"
    "$@" || rc=1
}

skip() {
    echo "== $1: skipped ($2)"
}

# the presentation test's frame sequence through the headless backend's present path, in the
# PC-98 mode the engine opens: run without the engine, so it needs no game data
echo "== vangel --present-test-mode pc98"
n=$("$BUILD/vangel" --present-test-mode pc98 | grep -c '"ev":"snap"') || rc=1
[ "${n:-0}" -gt 0 ] && echo "present-test: $n snapshots" ||
    { echo "present-test: no snapshots"; rc=1; }

# ---- with the imported game ----------------------------------------------------------------
if $PY -I "$HERE/../tools/gamedata.py" check >/dev/null 2>&1; then
    HAVE_GAME=1
else
    HAVE_GAME=
    echo "note: the original game is not imported (make data SRC=...): game tests skipped"
fi

# the engine's own shutdown: the tick limit ends the run through it, and the headless backend
# fails a run that leaves memory behind (exit 1 instead of 3)
if [ -n "$HAVE_GAME" ] && [ -f "$PAK" ]; then
    echo "== vangel --view to --max-ticks: the engine frees everything it allocated"
    mkdir -p "$BIN/teardown"
    t=0
    "$BUILD/vangel" --pak "$PAK" --view --storage "$BIN/teardown" \
        --autoplay 'at:10=right,20=right,30=left' --max-ticks 60 >/dev/null \
        2>"$BIN/teardown/log" || t=$?
    if [ $t -eq 3 ]; then
        echo "teardown: ended at the tick limit, nothing left"
    else
        echo "teardown: exit $t, not 3"; cat "$BIN/teardown/log"; rc=1
    fi
else
    skip teardown "needs the game and $PAK (make pack)"
fi

# ---- against the original code under emulation (re-tools/mcall.py) -------------------------
if [ -x "$EMU_PY" ] && "$EMU_PY" -c 'import unicorn' 2>/dev/null && [ -n "$HAVE_GAME" ] &&
   [ -f "$PAK" ]; then
    run "$EMU_PY" -I "$HERE/check_gf.py" "$BIN/test_gf" "$PAK"
else
    skip check_gf "needs the game, $PAK and a Python with unicorn (EMU_PYTHON)"
fi

if [ $rc -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "TESTS FAILED"; fi
exit $rc
