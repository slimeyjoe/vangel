# vangel — Virgin Angel

A faithful reimplementation of the PC-98 visual novel **Virgin Angel** (Crystal Soft, 1995-03-01;
programmer 宮本正城) on **lrvne**, the shared layer for retro visual-novel ports
(`source/lrvne`, GitHub `slimeyjoe/lrvne`). The research comes first and is the specification;
the engine `vangel` is built from it (`docs/engine-plan.md`). The Japanese release is reproduced
first; our own Polish and English translations follow.

## Where things are

- `docs/engine-plan.md` — the plan: milestones, layout, pack, profile, tests, translations.
- `docs/re/README.md` — index of the research. **The documents are the specification; the
  annotated listing is the final word** (made locally by `re-tools/madis.py` into
  `resources/derived/listing/`, names in `docs/re/listing/m-names*.tsv`). Read the routine
  before changing a documented behaviour.
- `docs/lrvne-fit.md` — what lrvne covers for this port, its gaps, what the engine must plan for.
- `docs/translation.md` — translated text (M7): the keys, the TSV files in `text/translation/`,
  the layout of every kind of text, the fonts (`fonts/vangel-latin.txt`: our own glyphs and
  the Polish marks on the game's letters), the pack's table, the engine's side
  (`engine/text/lang.c`, `layout.c`) and the test. Tools: `source/tools/tl.py` (template,
  pseudo, check, layout, ...), `vgtext.py` (keys, files, table), `vglayout.py` (the reference
  layout), `vgfont.py` (latin8, wide16); `mkpack.py --text LANG=FILE`.
- `docs/game-data.md` — releases, media, files; `resources/inventory.tsv` — every file + md5.
- `re-tools/` — `human68k.py` (X68000 media); `exeunpack.py` (EXEPACK); `dis16.py`,
  `madis.py` (disassembly); `mcall.py` (unicorn harness: the original's C start-up to `main`,
  then any routine callable; VRAM/GRCG/palette modelled); `m286.py` (mcall with time: 80286
  clocks, the VSYNC, the spin loops); `fx_cost.py` (op 32h's clocks: the engine's
  `gfx/fx_clk.h`, the transitions' durations); `vm_cost.py` (the interpreter's clocks:
  `vm/vm_clk.h`); `va98.py` (the whole program on an emulated PC-98, from its start: the
  end-to-end reference); `scbdis.py`, `scbsum.py`
  (scenario); sound and X68000 tools; `*_verify.py` compare the decoders with the original
  code under emulation.
- `source/` — the engine: `engine/` (C, on lrvne; `snd/mus.c` the music layer over lrvne's
  PMD module; `bi/` the built-in sequences, `gfx/glyph.c` their VRAM routines of segment
  05C3), `tools/` (stdlib Python: import, pack,
  `saves.py` (GAME.DAT in and out), and the decoders `scb.py`, `txb.py`, `gf.py` the research tools also use), `tests/` (`run.sh`,
  `test_*.c`, `check_*.py`), `lrvne/` (the submodule). `make data SRC=...`, `make pack`,
  `make test` (`EMU_PYTHON` for the checks against the original under emulation).
- `source/tests/` — `check_*.py` run the original under emulation and the engine's `test_*`
  program on the same input, and compare; the original's results are cached by
  `refcache.py` (`REFCACHE=on|off|refresh|verify`). `check_gf`/`check_buf`/`check_pal`/
  `check_fx` (M0/M1; `check_fx` times in 80286 clocks with `re-tools/m286.py`);
  `check_text`/`check_menu`/`check_input` (M2) share `textrig.py`: the kanji ROM answered
  from the pack's fonts, INT 33h from a script, the original's own VSYNC and INT 09h handlers
  delivered as interrupts, time passing only at the end of a wait loop's turn that found
  nothing (its FRAME_POINTS, as the engine's loops end such a turn with a frame); the input
  is decided while the original runs and replayed into `test_text`. `test_input` (no data):
  the keyboard model.
  `check_scb`/`check_expr`/`check_save`/`check_vmstep` (M3) share `vmrig.py` and
  `test_vm`: the original's loader, `expr_eval`, `save_slot`/`load_slot` and `vm_step` under
  mcall (a fresh machine after any `exit()`: unicorn delivers no second divide error);
  `check_vmstep` replaces every subsystem entry with `INT n; RETF` and a Python stand-in, its
  explorer answers waits, messages, menus, sequences and 35h while the original runs, the
  engine replays the answers; four routes under m286 compare each statement's clocks with
  `vm/vm_clk.h` (`re-tools/vm_cost.py consts` makes it). The statements reach the
  subsystems through `vg.vm.io`; a test replaces it.
  `check_snd` (M4): the original's music layer and PMD binding (04E4/048F) under
  `re-tools/sndcall.py`'s stand-in driver and `test_snd` on the same stand-in (the binding
  calls the driver only through `vg.mus.int60`, which the test replaces): every call, file
  tried and variable. `check_pmd`: the real PMD.COM on every song (`re-tools/pmd_capture.py`)
  replayed by lrvne's `tests/test_pmd.c`, built here as `lrv_test_pmd`.
  `check_builtin` (M5): statement 25h's sequences (segment 0504) on textrig with their wait
  loops as frame points and the music layer stood in for, against `test_bi`: page 0 and the DAC
  at every VSYNC, the pointer, the music calls, the result, pages 0/1 and buffer 12 at the end.
  `check_vm` (M6): the whole game end to end. `re-tools/va98.py` runs `M.EXE` from its start
  (an instruction time base, its spin loops skipping to the next VSYNC, its own VSYNC and
  keyboard handlers, INT 18h/33h, the real `PMD.COM` behind INT 60h through `pmdemu.py`);
  `test_game` is the whole engine (`vg_run`) on the test HAL. Both play a route
  (`tests/e2e/routes/*.route`: a line a wait, the input a frame from the frame after the wait
  began) and print the state at every wait (the engine's `vg_wait_begin`, the original's
  `va98.WAITS`): the interpreter, CRCs of both pages, buffer 12 and the window's buffers, the
  DAC, flags, music, pointer, `game.dat`, the INT 60h calls. The routes come from
  `tests/e2e/explore.py`'s plans played on `test_game` (stdin: it decides at each wait);
  `make e2e-routes` makes them again, `make test` checks that the engine still plays them so.
  `check_lang` (M7): a pseudo-translation of every string (`tl.py pseudo`) packed; `test_lang`
  plays every message, menu and built-in in it and prints where it draws each line, which
  must equal `tools/vglayout.py` (lrvne's reflow in Python over the original's page loop);
  every explore plan played with `lang=pl` must meet its menus in the same state as in
  Japanese. The engine's test hooks for it: `vg.text.on_line`, `on_text`, `VG_TEV_PAGE`.

## Rules

- **No game data in the repository, ever**: no original files, decoded pictures or text dumps,
  disassembly listings, recordings or screenshots. They live in `resources/original/` and
  `resources/derived/` (git-ignored) and are rebuilt from the player's copy. Docs quote the game
  only as far as needed to identify things. `GAME.DAT` on disk A holds a previous owner's saves:
  a test input at most, never packed. The media location is given on the command line or in
  `LRVNE_MEDIA`, never written into a tracked file.
- Research documents describe the original only; mark claims **verified** / **inferred** and
  cite code addresses as `SEG:OFF` of the unpacked `M.EXE` (image-relative segments).
- Tools: decoders a build reuses are stdlib-only Python, run as `python3 -I`; emulation and
  disassembly tools need `$EMU_PYTHON`, a Python with capstone, unicorn, pillow and numpy. Every
  verification compares against the original code or data, never against a model's or the
  engine's own output.
- Tests are event-driven: no sleeps, no wall-clock budgets; they wait on frames, ticks,
  instruction counts or protocol stops. A busy machine must not fail them.
- The engine is generic: no game name in `source/engine`; facts about the game live in the
  pack's profile, written by the tools.
- Translations hold keys and our text only, never the game's Japanese; templates and reading
  copies made from the pack stay in `build/`. A translation changes only what is printed: with
  none (or the original's language) the engine draws exactly the original.
- lrvne is fixed in lrvne, generically and with a test, never worked around in the engine.
- Licence GPL-3.0-or-later (SPDX header in every own source file).
- **Public, pseudonymous repository.** Commits carry the repo-local identity only; no personal
  names, e-mail addresses, hosts or home paths in tracked files or commit messages.
  `scripts/check-leaks.sh` (installed as git hooks) enforces it, with a private pattern list in
  `.git/info/leak-patterns` that is never tracked.
