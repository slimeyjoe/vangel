# vangel — Virgin Angel for modern and retro machines

A new engine for *Virgin Angel* (ヴァージン・エンジェル), a Japanese visual novel published by
Crystal Soft on 1995-03-01 for the NEC PC-9801 (with X68000 and FM TOWNS versions). It runs the
original game's scenario, text, pictures and FM music unchanged, and it reproduces the PC-98
release faithfully, timing and controls included. It is built on
[lrvne](https://github.com/slimeyjoe/lrvne), a shared layer for retro visual-novel ports, and
builds for desktops with SDL3 (Linux, macOS).

You can play it in the original Japanese, or in Polish: **the repository holds a draft of a
complete Polish translation**, made from the Japanese for this port (see
[Translations](#translations)). An English translation follows.

The engine is a reimplementation of the game's own engine, `M.EXE`, written from a complete
reverse-engineering of it: the documents in [docs/re/](docs/re/README.md) are its specification.

**Adults only.** The game contains explicit sexual scenes, some of them non-consensual.

This is an unofficial fan port. It contains none of the original program code, and **it does
not include the game itself**. You need your own copy of the PC-98 release; the build turns it
into the data file the engine plays.

## Status

* **The Japanese game plays in full**, with its music, on SDL3 and on the headless backend the
  tests drive.
* **Every part is checked against the original program under emulation**: the picture decoder,
  the transitions (to the 80286 clock), the palettes, every page of the 213 messages and the 43
  menus, the input, the scenario's interpreter, the saves, the music layer and the songs on the
  real PMD.COM, the built-in sequences. End to end, 12 routes through all four endings, every
  menu, the saves and loads and the built-in sequences play identically on the engine and on
  the original `M.EXE` running on an emulated PC-98, compared at every wait.
* **Translation-ready**: a translation is a keyed TSV file, laid out in the original's window,
  menus and built-in sequences with the game's own font and our Polish letters
  ([docs/translation.md](docs/translation.md)).
* **Polish: a draft of the whole game** (2115 of 2125 strings), see below.
* **Next:** the editor's read of the Polish, the English translation, opt-in extras (the
  message-5 typo fix, a CG gallery from the Graphic Disk, skipping of read text) and the Amiga
  family (AmigaOS 3.x, WarpOS, AROS). [docs/engine-plan.md](docs/engine-plan.md) has the
  milestones.

## What you need

* **The original PC-98 game**: the two floppy disk images (D88, ...) or the files. Every file
  is checked against the release's inventory (`resources/inventory.tsv`), so any complete copy
  works. [docs/game-data.md](docs/game-data.md) describes the releases, their media and files.
* **Python 3** (the standard library is enough to import the game and build the pack).
* **A C99 and C++ compiler, make, pkg-config and SDL3** for the desktop build.

## Quick start

All `make` commands run in `source/`, and everything they build goes to the top-level `build/`.
The platform layer is [lrvne](source/lrvne), a git submodule pinned at lrvne 0.2.0: clone with
`--recurse-submodules` or run `git submodule update --init` once (and again after a pull that
moves the pin).

```sh
cd source
make data SRC=~/virginangel/disks   # import your copy of the game (a directory, images or a zip)
make pack                           # build/virginangel.pak: the game's data, fonts and translations
make TARGET=sdl3                    # build/sdl3/vangel
cd ..
build/sdl3/vangel --pak build/virginangel.pak            # in Japanese
build/sdl3/vangel --pak build/virginangel.pak --lang pl  # in Polish (the draft)
```

Put `virginangel.pak` next to the executable, or name it with `--pak`. The language given with
`--lang` is remembered: the next start without it uses the same one; `--lang ja` goes back to
the original. Saves are the original's `game.dat` (three slots) in
`$XDG_DATA_HOME/vangel/virginangel`, by default `~/.local/share/vangel/virginangel`, on macOS as
well (`--storage DIR` puts them elsewhere). A `GAME.DAT` from a PC-98 copy can be put there as
`game.dat` and is used as it is.

`make TARGET=sdl3 dist` builds the player's archive `build/sdl3/vangel-<version>-sdl3-<os>-<arch>.tar.gz`
(the program, its ReadMe and the licences, not the pack).

## Options

| Option | What it does |
|---|---|
| `--lang ja\|pl` | the language of the text (default: the original Japanese); remembered |
| `--fullscreen` | start in fullscreen |
| `--scale integer\|aspect\|fit\|stretch` | `integer`: sharp whole-number scaling. `aspect`: the same with the PC-98 monitor's 4:3 proportions. `fit`: the largest 4:3 picture that fits, smoothed. `stretch`: fill the window |
| `--window WxH` | the initial window size |
| `--pak FILE`, `--storage DIR` | where the data file is, where saves go |
| `--volume 0..100`, `--no-audio` | the music's volume, or silence |
| `--view [PICTURE]` | browse the game's pictures |

`build/sdl3/vangel --help` lists all of them.

## Controls

At the start the game asks, as on the PC-98, whether to use the mouse: Y or N.

| Key | Action |
|---|---|
| any key, left button | turn a page of text |
| Cursor Up / Down | move in a menu |
| Return | choose |
| mouse | points at a menu item; the left button chooses it |
| in the music mode | Up / Down choose a song, Return or Space play it, Esc or the right button leaves |
| F11, Alt+Return | toggle fullscreen |
| F12 | cycle the scale modes |
| Ctrl+Shift+R | reset: the game starts again (saves are kept) |
| Shift+Esc | quit at once, without asking (unsaved progress is lost) |

## Translations

Our own translations, made from the Japanese, live in [text/](text/README.md): a translation
holds keys and our text only, never the game's Japanese, and `make pack` packs every one of
them. With no translation chosen, the engine draws exactly the original.

**Polish** (`text/translation/vangel_pl.tsv`) is a **draft**. The whole script was read first,
then a story bible and two translators' guides were written; the editor's decisions on register,
address, names and the glossary are in
[TRANSLATION_GUIDE_PL.md](text/docs/TRANSLATION_GUIDE_PL.md). Each part is translated and
checked in independent passes and then read by the editor in the game:

* **approved by the editor:** the prologue and chapter 1, chapter 2, the title and system menus
  (save, load), the console's strings;
* **drafted, awaiting the editor's read:** chapters 3 to 11, the raid, the endings, the
  opening and the built-in sequences (staff roll, music room, notice);
* **not yet translated:** six passages the editor translates personally
  (`text/translation/editor_pl.tsv`), and the ending cards, which keep the game's own English
  by design.

After the editor's read comes a native read-through in play order. Expect rough lines until
then; reports are welcome. [text/docs/PASS_PL.md](text/docs/PASS_PL.md) is the hand-over for
whoever continues the pass.

**English** follows the Polish, from the Japanese, with the same story bible.

## Tests

```sh
cd source
make TARGET=host test     # conformance tests against the original under emulation
make e2e-routes           # play the end-to-end check's plans on the engine again
```

The tests that need the game are skipped with a note when it has not been imported; those that
run the original under emulation need `$EMU_PYTHON`, a Python with capstone, unicorn, Pillow and
numpy. The original's results are cached between runs (`REFCACHE=on|off|refresh|verify`).
[CLAUDE.md](CLAUDE.md) and [docs/engine-plan.md](docs/engine-plan.md) describe each check.

## Where things are

| Path | What |
|---|---|
| `source/engine/` | the engine, generic: the scenario's interpreter, pictures and transitions, palettes, text and menus, the music layer over lrvne's PMD module, the built-in sequences, translated text |
| `source/lrvne/` | the platform layer (submodule): frame loop, screen, FM chip, PMD, mixer, fonts, packs, the backends |
| `source/tools/` | game import, the pack, saves, the game's own formats, the translation tools (`tl.py`) |
| `source/tests/` | the conformance tests and the end-to-end routes |
| `text/` | the translations, the translators' guides and the story bible ([README](text/README.md)) |
| `fonts/` | our own glyphs for translated text: the Polish letters on the game's font, quotes, dashes |
| `docs/re/` | the reverse engineering of the original engine and its data: the specification ([README](docs/re/README.md)) |
| `docs/` | the engine plan, the game's data, the translation format, what lrvne covers |
| `re-tools/` | research tools: media readers, the EXEPACK unpacker, the disassembler, the emulation harnesses (a whole PC-98 running `M.EXE`), decoders and their verifiers |
| `resources/` | `inventory.tsv` (committed); everything else there (original files, derived data, listings) is git-ignored and rebuilt from your copy |

`make clean` removes `build/`. `make data-clean` removes everything made from the game outside
`build/`. `make distclean` does both and leaves only the committed files.

## Credits

The story, text, pictures, music and sound effects of *Virgin Angel* are © 1995 Crystal Soft.
This port is not affiliated with or endorsed by Crystal Soft or its successors. The engine and
the Polish translation were made for this port. Third-party code is in lrvne's `third_party/`:
[ymfm](source/lrvne/third_party/ymfm/LICENSE); the bitmap fonts are in lrvne's `fonts/x11/`.

## Licence

GPL-3.0-or-later for our own files (SPDX header in each source file); see `LICENSE`.
