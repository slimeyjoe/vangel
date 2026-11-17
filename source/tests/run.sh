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

# the keyboard as the engine models it from lrvne's keys
run "$BIN/test_input"

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
    # the game: the console's question, the title, into the story (a save, the prologue's
    # built-in sequence) until the tick limit; with the music its first save comes at about
    # tick 31 000 (the fades block, the opening waits for measures)
    echo "== vangel (the game) to --max-ticks: the engine frees everything it allocated"
    rm -f "$BIN/teardown/game.dat"
    t=0
    "$BUILD/vangel" --pak "$PAK" --storage "$BIN/teardown" \
        --autoplay 'y:wait return:wait' --max-ticks 40000 >/dev/null \
        2>"$BIN/teardown/log" || t=$?
    if [ $t -eq 3 ] && [ -f "$BIN/teardown/game.dat" ]; then
        echo "teardown: ended at the tick limit, a save written, nothing left"
    else
        echo "teardown: exit $t (not 3) or no save"; cat "$BIN/teardown/log"; rc=1
    fi
    # the same with the pretend audio device pulling the sound, as a real device's callback
    echo "== vangel (the game, --audio pull) to --max-ticks"
    rm -f "$BIN/teardown/game.dat"
    t=0
    "$BUILD/vangel" --pak "$PAK" --storage "$BIN/teardown" --audio pull \
        --autoplay 'y:wait return:wait' --max-ticks 40000 >/dev/null \
        2>"$BIN/teardown/log" || t=$?
    if [ $t -eq 3 ] && [ -f "$BIN/teardown/game.dat" ]; then
        echo "teardown: ended at the tick limit, a save written, nothing left"
    else
        echo "teardown: exit $t (not 3) or no save"; cat "$BIN/teardown/log"; rc=1
    fi
    # the routes of the end-to-end check: the engine still plays each plan as recorded
    run $PY -I "$HERE/e2e/explore.py" --check "$BIN/test_game" "$PAK"
    # translated text: a pseudo-translation of every string packed, laid out as the reference
    # lays it out, played through every plan in the same states as Japanese
    run $PY -I "$HERE/check_lang.py" "$BUILD" "$PAK" "$ROOT/build/fonts"
    # ... and the game in that language to the tick limit: nothing left behind (its first
    # save comes later than in Japanese, after the pseudo-translation's extra pages)
    echo "== vangel (the game, --lang pl, the pseudo-translation) to --max-ticks"
    rm -f "$BIN/teardown/game.dat" "$BIN/teardown/lang"
    t=0
    "$BUILD/vangel" --pak "$BIN/lang/pseudo.pak" --storage "$BIN/teardown" --lang pl \
        --autoplay 'y:wait return:wait' --max-ticks 90000 >/dev/null \
        2>"$BIN/teardown/log" || t=$?
    if [ $t -eq 3 ] && [ -f "$BIN/teardown/game.dat" ]; then
        echo "teardown: ended at the tick limit, a save written, nothing left"
    else
        echo "teardown: exit $t (not 3) or no save"; cat "$BIN/teardown/log"; rc=1
    fi
    rm -f "$BIN/teardown/lang"
else
    skip teardown "needs the game and $PAK (make pack)"
    skip explore "needs the game and $PAK (make pack)"
    skip check_lang "needs the game and $PAK (make pack)"
fi

# ---- against the original code under emulation (re-tools/mcall.py) -------------------------
if [ -x "$EMU_PY" ] && "$EMU_PY" -c 'import unicorn' 2>/dev/null && [ -n "$HAVE_GAME" ] &&
   [ -f "$PAK" ]; then
    run "$EMU_PY" -I "$HERE/check_gf.py" "$BIN/test_gf" "$PAK"
    run "$EMU_PY" -I "$HERE/check_buf.py" "$BIN/test_buf" "$PAK"
    run "$EMU_PY" -I "$HERE/check_pal.py" "$BIN/test_pal" "$PAK"
    if "$EMU_PY" -c 'import capstone' 2>/dev/null; then
        run "$EMU_PY" -I "$HERE/check_fx.py" "$BIN/test_fx" "$PAK"
    else
        skip check_fx "needs capstone in EMU_PYTHON (the 80286 clocks)"
    fi
    run "$EMU_PY" -I "$HERE/check_input.py" "$BIN/test_text" "$PAK"
    run "$EMU_PY" -I "$HERE/check_text.py" "$BIN/test_text" "$PAK"
    run "$EMU_PY" -I "$HERE/check_menu.py" "$BIN/test_text" "$PAK"
    run "$EMU_PY" -I "$HERE/check_builtin.py" "$BIN/test_bi" "$PAK"
    run "$EMU_PY" -I "$HERE/check_scb.py" "$BIN/test_vm"
    run "$EMU_PY" -I "$HERE/check_expr.py" "$BIN/test_vm"
    run "$EMU_PY" -I "$HERE/check_save.py" "$BIN/test_vm"
    if "$EMU_PY" -c 'import capstone' 2>/dev/null; then
        run "$EMU_PY" -I "$HERE/check_vmstep.py" "$BIN/test_vm"
    else
        skip check_vmstep "needs capstone in EMU_PYTHON (the 80286 clocks)"
    fi
    run "$EMU_PY" -I "$HERE/check_snd.py" "$BIN/test_snd" "$PAK"
    run "$EMU_PY" -I "$HERE/check_pmd.py" "$BIN/lrv_test_pmd" "$PAK"
    run "$EMU_PY" -I "$HERE/check_vm.py" "$BIN/test_game" "$PAK"
else
    for c in check_gf check_buf check_pal check_fx check_input check_text check_menu \
             check_builtin check_scb \
             check_expr check_save check_vmstep check_snd check_pmd check_vm; do
        skip $c "needs the game, $PAK and a Python with unicorn (EMU_PYTHON)"
    done
fi

if [ $rc -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "TESTS FAILED"; fi
exit $rc
