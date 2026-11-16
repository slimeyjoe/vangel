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
- `docs/game-data.md` — releases, media, files; `resources/inventory.tsv` — every file + md5.
- `re-tools/` — `human68k.py` (X68000 media); `exeunpack.py` (EXEPACK); `dis16.py`,
  `madis.py` (disassembly); `mcall.py` (unicorn harness: the original's C start-up to `main`,
  then any routine callable; VRAM/GRCG/palette modelled); `scbdis.py`, `scbsum.py`
  (scenario); sound and X68000 tools; `*_verify.py` compare the decoders with the original
  code under emulation.
- `source/` — the engine: `engine/` (C, on lrvne), `tools/` (stdlib Python: import, pack, and
  the decoders `scb.py`, `txb.py`, `gf.py` the research tools also use), `tests/` (`run.sh`,
  `test_*.c`, `check_*.py`), `lrvne/` (the submodule). `make data SRC=...`, `make pack`,
  `make test` (`EMU_PYTHON` for the checks against the original under emulation).

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
- lrvne is fixed in lrvne, generically and with a test, never worked around in the engine.
- Licence GPL-3.0-or-later (SPDX header in every own source file).
- **Public, pseudonymous repository.** Commits carry the repo-local identity only; no personal
  names, e-mail addresses, hosts or home paths in tracked files or commit messages.
  `scripts/check-leaks.sh` (installed as git hooks) enforces it, with a private pattern list in
  `.git/info/leak-patterns` that is never tracked.
