# vangel — Virgin Angel for modern and retro machines

A reimplementation of the engine of *Virgin Angel* (ヴァージン・エンジェル), a Japanese adult visual
novel published by Crystal Soft on 1995-03-01 for the NEC PC-9801 (with X68000 and FM TOWNS
versions). The goal is a portable engine that runs the original scenario, text, pictures and
music unchanged and reproduces the PC-98 release faithfully, built on
[lrvne](https://github.com/slimeyjoe/lrvne), a shared layer for retro visual-novel ports.
Polish and English translations will follow the Japanese release.

**Status:** the reverse engineering is complete: the documents in [`docs/re/`](docs/re/README.md)
specify the original engine `M.EXE` and all its data formats. The engine plays the whole
Japanese game with its music (headless and SDL3), each part checked against the original code
under emulation, and the whole game end to end: routes through all four endings, every menu,
the saves and loads and the built-in sequences, played on the engine and on the original
program under emulation, identical at every wait. The translations, the extras and the Amiga
family come next ([`docs/engine-plan.md`](docs/engine-plan.md)).

**Adults only.** The game contains explicit sexual scenes, some of them non-consensual.

## You need the game

The repository carries none of the game. [`docs/game-data.md`](docs/game-data.md) describes the
releases, their media and files; `resources/inventory.tsv` lists every file with its md5.

## Layout

* `docs/re/` — the research: engine, scenario VM, text, graphics, sound, platform, the game's
  structure, other releases.
* `re-tools/` — research tools (Python 3; the emulation and disassembly tools need capstone and
  unicorn): media readers, the EXEPACK unpacker, the annotated disassembler, a harness that runs
  the original's routines under emulation, decoders for every data format and their verifiers.
* `resources/` — `inventory.tsv` (committed); everything else there (original files, extracted
  and derived data, listings) is git-ignored and rebuilt from your copy.

## Licence

GPL-3.0-or-later for our own files (SPDX header in each source file); see `LICENSE`.
