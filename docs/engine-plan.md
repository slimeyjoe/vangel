# vangel — engine plan

**Status (2026-11-16):** M0 and M1 done. M0: import, pack, the engine skeleton with a picture
viewer (`--view`), the decoder bit-exact against the original (54 pictures × 4 cases). M1: the
three buffers, ops 31h/33h/18h and the window's background, op 32h with every transition, the
palettes and fades, on the VSYNC timer. Against the original under emulation: every write of
136 op 32h cases at the same 80286 clock (`check_fx`), 319 DAC loads on the same frames
(`check_pal`), the buffer statements (`check_buf`). M2 (text, menus, input) is next.

vangel reimplements `M.EXE`, the engine of Crystal Soft's *Virgin Angel* (PC-98, 1995), on
[lrvne](https://github.com/slimeyjoe/lrvne). It reproduces the PC-98 release faithfully in
Japanese first. Our own Polish translation follows, then English, both from the Japanese, and
then opt-in extras. The research in `docs/re/` is the specification; this plan says how the
engine is built from it and how each part is checked against the original.

## Decisions

| Topic | Decision |
|---|---|
| Release | PC-98 (1995-03-01). The X68000 release serves only as a second witness when reading code, and as the source of the message-5 typo fix |
| Sound | the 26K setup: YM2203 + PMD 4.7g through lrvne's PMD module, with SSG drums. OPNA / PPS / 86-PCM come later, behind the profile key `sound=` |
| Targets | host (headless, tests) and SDL3 first; Amiga 68k / WarpOS / AROS in a late milestone |
| Translations | ours, from the Japanese: Polish first, then English; a keyed runtime lookup with reflow into the original window |
| Latin text | the game's own 8x16 half-width font (from `M.EXE`), plus our own Polish letters, quotes and dashes drawn to match; lrvne `latin8` as fallback |
| Extras | all opt-in, faithful by default: the message-5 typo fix, a CG gallery from the Graphic Disk, skipping of text already read |
| CPU-bound transitions | effects 10/20/30/32/33/34 charge `lrv_sys_cpu` with the clocks of the original's instructions on an 80286 without wait states (Intel's clock counts: `re-tools/m286.py`; instruction counts were rejected, as one `rep movsw` copies a whole line). The reference machine is an 80286 at 10 MHz: `cpu_per_frame` = 177 242, a profile key, correctable once real hardware is measured |

## Layout

```
docs/            engine-plan.md, game-data.md, translation.md, lrvne-fit.md, re/
re-tools/        research tools; va98.py (whole-machine harness), fx_cost.py
resources/       inventory.tsv (original/, derived/ git-ignored)
fonts/           vangel-latin.txt (our own glyphs and diacritic marks)
text/            translation/vangel_<lang>.tsv; docs/ (guides, story bible)
scripts/         check-leaks.sh
source/
  Makefile       includes lrvne/mk/lrvne.mk; LRVNE_PMD=1 LRVNE_YMFM=1 LRVNE_CONTROL=1
  lrvne/         submodule (slimeyjoe/lrvne)
  engine/        vg.h app.c main.c version.h
    game/        run.c profile.c console.c saves.c
    vm/          scb.c expr.c vm.c timer.c
    bios/        input.c mouse.c
    gfx/         gf.c buf.c fx.c pal.c glyph.c
    snd/         mus.c             the music layer over lrv_pmd
    text/        txb.c win.c msg.c menu.c lang.c layout.c
    bi/          opening.c ending.c announce.c musmode.c
    extras/      gallery.c skip.c
  tools/         gamedata.py games.py mkpack.py vgpak.py mexe.py vgfont.py tl.py saves.py
                 scb.py txb.py gf.py (one copy; re-tools import them)
  tests/         run.sh refcache.py check_*.py test_*.c e2e/explore.py
```

## lrvne additions (made in lrvne, generic, with tests)

| # | Addition | Needed by |
|---|---|---|
| 1 | `tools/lrvne/exepack.py`: EXEPACK unpacker | M0 |
| 2 | `xfont.py` raw glyph-array input (`add_raw`, `--raw FILE@OFF:CODES`) | M0 |
| 3 | palette `lrv_pal_shift` (add and clamp), `lrv_pal_step_down` (decrement only) | M1 (**done**, lrvne 47f114f) |
| 4 | glyphs: plain `g\|g<<1` bold (8 and 16 bits), transparent OR blit, double size, planar 4-neighbour outline | M2 |
| 5 | reflow `lrv_reflow_layout_from(..., first_line)`, plus `tools/lrvne/reflow.py` as the Python reference | M7 |

Engine-specific drawing stays in the engine: the black vertical edge, the prologue's reveal
mask, and the colour 15 → 8 step.

## Milestones

### M0 — repository, skeleton, data import

- **Repository and submodule.** Leak hooks, lrvne submodule, `Makefile`, `app.c`, `main.c`, and a `--view NAME` picture viewer.
- **`gamedata.py` / `games.py` on lrvne `source` + `inventory`:**
  - `inventory.tsv`: `date` is renamed `mtime`, and names get release prefixes `pc98/`, `x68k/`, `ibm/`;
  - `pc98` is required; `x68k` and `ibm` are optional;
  - `GAME.DAT` is the previous owner's state and is never packed;
  - after import, `M.EXE` is unpacked and the result's md5 checked.
- **`mkpack.py` (XPAK v2)** packs:
  - the game files: SCB, TXB, LIB, the 21 songs, `ANNOUNCE.TXT`;
  - `ssgtab`, from `PMD.COM`;
  - `txbdict` and `ank8`, the embedded font;
  - `builtin`, md5-checked regions of `M.EXE`: prologue pages, staff strings and their copy records, the music-mode table, prompts, built-in palettes, the effect-31 order. These are packed with the milestones that use them (M1, M2, M5), not in M0. M1 packs them as BLOB entries of their own (`tools/mexe.py`, the image's md5 checked): `pal.black`, `pal.white`, `pal.default` and `fx31.order`;
  - `font16`, `font8`, `profile`.
- **Correction.** `game-data.md` is corrected: `M.EXE` is a pack input.
- **Test.** `check_gf.py`: 54 pictures × 4 decoder variants against the original `gf_load`.
- **Viewer.** `--view [PICTURE]` shows the library's pictures. The pictures carry no palette, so
  the pack's META `viewer` gives each one the scenario palette it appears with.

### M1 — graphics and palettes (done)

- **Pictures and transitions:**
  - op 31 (buffers 10/11/12, transparency, the −1 rule, the window snapshot), op 33, op 18;
  - op 32 with effects 10/20/30/31/32/33/34, pixel-exact.
- **Palettes:** ops 30h/1Ah/2Fh, `t·564/1000`, the no-free-timer rule, DAC loads at retrace.
- **Tests:**
  - `check_fx.py`: 136 cases; every write to the destination, in order, at the same clock
    (so the same picture at every frame for any `cpu_per_frame`), run at 177 242 and at 997
    clocks per frame; effect 31 by frame and clock at both speeds;
  - `check_pal.py`: every DAC load and its frame;
  - `check_buf.py`: ops 31h/32h/33h/18h and `screen_clear` on the three buffers and the
    window's background.
- **Done (2026-11-16).** The clocks: `re-tools/m286.py` (the 80286 table and a timed machine
  over `mcall`); `re-tools/fx_cost.py consts` makes `engine/gfx/fx_clk.h`. Not charged yet:
  op 31h's decoding (its time depends on the data; a later milestone), the palette code
  between its waits (far below a frame), `vram_clear`. The pointer's hiding in ops 31h/32h
  comes with the mouse (M2). Op 2Fh with t < 2 ends the program with R6003, as the original
  does (`vg_runtime_error`; exit code 255 once the VM owns the exit, M3).

### M2 — text, menus, input

- **`msg_show`, line for line:** speech state, the name prefix, timed pages and their abort, the 14h quirk, the 68-column clip.
- **The window:**
  - save and work buffers;
  - the kanji-ROM stand-in and the embedded font;
  - bold and the vertical edge;
  - the ↵ icon.
- **Menus:** bar inversion, same-statement memory, keys and mouse.
- **Input:** the INT 09h latch, ESC on release, the MSZ mouse model.
- **Tests:** `check_text.py` (all 1 849 pages, layout and pixels), `check_menu.py` (43 menus), `check_input.py`.

### M3 — the VM, silent

- **The VM:**
  - the loader checks and exit codes;
  - expressions (no short-circuit, `idiv`, R6003);
  - 34 opcodes;
  - the v1 result register, the call stack;
  - a CPU charge per statement, so that the busy-poll of statement 35h advances time without a sound device.
- **Saves:** `GAME.DAT`, byte-compatible, imported and exported by `tools/saves.py`.
- **Console prompt:** the INIT mouse prompt (`mouse=ask|on|off`).
- **Tests:**
  - `check_scb.py`, `check_expr.py`, `check_save.py`;
  - `check_vmstep.py`: the original `vm_run` with its subsystems stubbed, compared statement by statement, plus a coverage report of the 1 947 reachable statements.

### M4 — music

- **The music layer** over `lrv_music` + `lrv_pmd`:
  - file choice `.n`, then `.s`, then `.m`;
  - the same song while playing is a no-op;
  - the AH=19h volume;
  - the blocking fade;
  - the measure counter for 35h.
- **Profile:** `sound=pmd26k|none`. `none` is GAME.BAT's option 4: 35h gives −1 and the music mode refuses.
- **Tests:**
  - `check_pmd.py`: 21 songs × 30 000 interrupts against the real driver's logs;
  - `check_snd.py`: the driver-call trace against the original layer, 26K and none.

### M5 — built-in sequences: first playable

- **OPENING:** the column reveal, 3 s pages, the decrement fade, skip.
- **ENDING / ENDING2:** the staff roll at double size, outline, effect-31 copies.
- **ANNOUNCE.**
- **The music mode.**
- **Test:** `check_builtin.py`, the DAC and VRAM at every VSYNC against the original.

Exit: the whole Japanese game plays on SDL3 with music. lrvne and vangel go public on GitHub.

### M6 — end to end

**`re-tools/va98.py`:** the original's main loop under emulation:
- instruction time base;
- PIC, VSYNC IRQ, keyboard IRQ;
- INT 18h glyphs, INT 33h, INT 21h console and files;
- INT 60h as the real resident PMD.COM, or a stub;
- sync points at every input wait.

**`tests/e2e/explore.py`** covers:
- every menu;
- the four endings;
- every save point and slot, and good, empty and invalid loads;
- the prologue skip;
- the timed aborts;
- the music mode;
- ANNOUNCE;
- `sound=none`.

**`check_vm.py`** compares at every wait: VM state, both pages, the buffers, the DAC, the driver calls and `GAME.DAT`.

Also: the teardown run, sanitizers, pull audio, and the whole suite rerun under CPU load with identical results.

### M7 — translation-ready

**Keys, stable under reflow:**

| Key | Covers |
|---|---|
| `m<NNN>.<L>` | message NNN from source line L: a run of text lines between control lines. Speech is stored without the name and its brackets |
| `name` (a kind) | speaker names |
| `menu<MM>.<c>` | menu items |
| `bi.prologue.<p>`, `bi.staff.<p>`, `bi.music.*`, `bi.announce.*` | the built-in sequences |
| `announce.<p>` | `ANNOUNCE.TXT` pages |
| `con.*` | the console prompts |

**Layout.** The original page state machine runs over the original lines. Each unit is laid out at its first line:
- a hanging indent after the speaker;
- row 3 ends before the icon cell;
- overflow adds pages in the current mode;
- timed pages last in proportion to the text drawn.

**Fonts:**
- ASCII comes from the game's font, except its bar and icon pieces;
- Polish letters are composed from the game's letters and our own marks;
- quotes and dashes are our own glyphs;
- a `wide16` subset is built per language.

**Tools and packaging.** `tl.py` (template, pseudo, check, layout, view, put, fill, status); `--lang`; saves record the language; `make dist`.

**Test.** `check_lang.py` with a pseudo-translation:
- the pack round-trips;
- the C layout equals the Python layout;
- nothing is drawn out of bounds;
- the whole route in the translated language reaches every menu in the same VM state as Japanese.

### M8 — Polish

A guide (register, the ty/pan matrix, gender concealment, name declension, glossary), a story
bible and calibration samples come first. Then a pass chapter by chapter, followed by a native
read-through in play order.

### M9 — English

The same pipeline and the same story bible, translated from the Japanese.

### M10 — extras (opt-in; with them off, behaviour is unchanged)

- **Typo fix:** a `txbpatch` entry, checked against the X68000 file's md5.
- **Skip of read text:** a `READ.DAT` record. It finishes waits only and never changes the skip flag or v1.
- **CG gallery:** from the Graphic Disk's 21 clean BMPs, when the player has that disk. It is a fifth title-menu item, and a CG unlocks once shown.

### M11 — Amiga family

`TARGET=amiga|warpos|aros`, `.lha` dist, the lrvne emulator rigs, big-endian unit tests, memory budget.

### Later

- OPNA / PPS / 86 under `sound=`: needs a YM2608 core, a PCM channel and stereo in lrvne.
- An X68000 profile.

## Risks and open items

- `text.md` §3.5's timer units ("80 ms", "150 ms") disagree with `platform.md` §2 (hundredths of a second). Settle it from the listing before M2.
- The `cpu_per_frame` value (an 80286 at 10 MHz, no wait states) is assumed. The e2e syncs on state at input waits, not on frame numbers.
- The speed of the whole-machine harness: mitigated by the statement-level fast path, parallel segments and a result cache.
- MSZ functions FDh/FFh and the pointer shape.
- Pixel tests hold only with the same kanji-ROM stand-in on both sides.
- Translation fit: long speaker names, menus, the prologue's row limit, the 32-column staff roll.
- `other-versions.md` §2.4.4 contradicts `graphics.md` §8 and `text.md` §5.1 on text VRAM: fix it in M0.

## Verification

- **Each milestone:** `make -C source test` (`tests/run.sh`): data-free tests first, then the game checks. Each check is skipped with a note when the media, the pack or `$EMU_PYTHON` is missing.
- **Also each milestone:** a sanitizer build, and the teardown run.
- **References:** every comparison is against the original under emulation, or a decoder verified that way. Never against the engine's own output.
- **Before every push:** `scripts/check-leaks.sh tree` and `commits`.
