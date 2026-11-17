# vangel — engine plan

**Status (2026-11-17):** M0 to M6 done. M0: import, pack, the engine skeleton with a picture
viewer (`--view`), the decoder bit-exact against the original (54 pictures × 4 cases). M1: the
three buffers, ops 31h/33h/18h and the window's background, op 32h with every transition, the
palettes and fades, on the VSYNC timer. Against the original under emulation: every write of
136 op 32h cases at the same 80286 clock (`check_fx`), 319 DAC loads on the same frames
(`check_pal`), the buffer statements (`check_buf`). M2: the message file, the window and its
glyphs, statement 19h's page loop and waits, statement 24h's menus, the keyboard latch and the
mouse; against the original under emulation, frame by frame and pixel by pixel: every page of
the 213 messages (`check_text`), the 43 menus (`check_menu`), the input layer (`check_input`). M3: the scenario's loader, the
expressions, the interpreter and its 34 statements, `GAME.DAT`, the console's mouse question;
the game plays from the question through the title into the story, without music and the
built-in sequences; against the original under emulation: the loader on both releases and
damaged files (`check_scb`), 800 random expressions (`check_expr`), saves and loads
(`check_save`), 250 000 statements on 44 routes with every call, the stack and the variables,
and the 80286 clocks of 10 000 (`check_vmstep`). M4: the music layer and the PMD binding over
lrvne's PMD module, with blocking fades and the measure counter of statement 35h; against the
original under emulation, every driver call of 348 calls into the layer on five driver set-ups
(`check_snd`), and every register write of the 21 songs on the real PMD.COM for 30 000
interrupts each (`check_pmd`). M5: the built-in sequences (the prologue, the staff rolls, the
notice, the music mode); against the original under emulation, 28 runs, 55 239 frames, page 0
and the DAC at every VSYNC (`check_builtin`): the whole game plays, with music. First
playable. M6: the whole game end to end against the original program under emulation
(`re-tools/va98.py`, `check_vm`): 12 routes through the four endings, every menu, the saves and
loads, the built-in sequences and the machine without sound, identical at every wait. M7
(translation-ready) is next.

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
| 4 | glyphs: plain `g\|g<<1` bold (8 and 16 bits) and a transparent cell (M2, **done**, lrvne 79631d2: `lrv_glyph_bold8_plain` / `16_plain`, `lrv_glyph_blit` with `LRV_GLYPH_CLEAR`); the staff roll's double size and outline stayed in the engine (M5, `gfx/glyph.c`: the original's GRCG routines with their quirks, not a general facility) | M2 |
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

### M2 — text, menus, input (done)

- **`msg_show`, line for line:** speech state, the name prefix, timed pages and their abort, the 14h quirk, the 68-column clip.
- **The window:**
  - save and work buffers;
  - the kanji-ROM stand-in and the embedded font;
  - bold and the vertical edge;
  - the ↵ icon.
- **Menus:** bar inversion, same-statement memory, keys and mouse.
- **Input:** the INT 09h latch, ESC on release, the MSZ mouse model.
- **Tests:** `check_text.py` (all 1 849 pages, layout and pixels), `check_menu.py` (43 menus), `check_input.py`.
- **Done (2026-11-16).** `engine/text/` (txb.c win.c msg.c menu.c), `engine/bios/` (input.c
  mouse.c). The checks share `tests/textrig.py`: the original under mcall with INT 18h answered
  from the pack's font16/font8 as `lrv_font_rom_glyph` reads them, INT 33h from a script, the
  original's own VSYNC and INT 09h handlers delivered as interrupts, and time passing only at
  the end of a wait loop's turn that found nothing, as in the engine. The player's input is
  decided while the original runs (an answer a while after each page) and replayed into the
  engine (`tests/test_text.c`). Compared: every page shown, the icon on and off, the text
  erased, the bar inverted (with the window's CRC-32, the page's on erasing), the pointer shown
  and hidden, each at the same frame, and v1. `check_text`: 223 runs, 1 921 pages (the 1 849
  of the 213 messages, the timed ones also cut short, all timers taken, keyboard only);
  `check_menu`: 172 runs; `check_input`: every keyboard byte and 961 results of input_poll and
  the release steps. The keyboard: lrvne's keys of each poll become PC-98 scan codes (breaks,
  then makes) through the original's handler (`tests/test_input.c`). Settled from the listing:
  the timer unit is 1/100 s (`text.md` §3.5 corrected), the mouse's release step waits for the
  left button (`platform.md` §3.4 corrected). Not charged: the time of drawing text (the BIOS's
  kanji reads are not emulated). The pointer is an arrow of our own (MSZ's is not known), an
  overlay; the original's hide/show calls decide when it is seen, also around the buffer copies
  of M1. The menus take their strings from the caller; the scenario's table and the message
  count come with the loader (M3).
### M3 — the VM, silent (done)

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
- **Done (2026-11-17).** `engine/vm/` (scb.c expr.c vm.c, vm_clk.h), `engine/game/` (saves.c
  console.c, run.c: `main` and `run_game`). The game runs: the console's question (drawn as
  the PC-98's text screen into graphics page 0, Y or N; `mouse=on|off` answer it unseen), the
  scenario and its text loaded with the original's exit codes (1, 2, 3; 4 for the
  interpreter's errors, 255 for R6003, through `vg_exit`), the devices, the graphics, the
  interpreter until 2Eh, a quit or a reset (the program again from `run_game`, the mouse's
  answer kept). The statements call the subsystems through a table (`struct vg_vm_io`) the
  tests replace. Until M4 the machine has no sound driver (as `GAME.BAT`'s option 4: 35h reads
  −1, nothing plays); until M5 statement 25h only logs its sequence. Where the original reads
  outside its tables (a pc past the statements, variable or message numbers it does not have,
  a call stack a damaged save left too deep, palettes over the count) the engine ends with
  exit 4; the loader refuses strings longer than their records and counts whose 16-bit
  allocation wraps (exit 2). The waits of M2 and M3 now send their trace events (autoplay's
  `KEY:wait`, the control protocol). **Time:** each statement charges the 80286 clocks the
  original's interpreter spends on its path (`re-tools/vm_cost.py consts` makes `vm/vm_clk.h`:
  the fetch, the dispatch, the handler, per expression node; not the subsystems, not the turns
  of a wait). **Tests** (`tests/test_vm.c`, `tests/vmrig.py`): `check_scb` (the PC-98 file, the
  X68000 one when given or imported, and 131 damaged copies: the result, every table,
  the entry); `check_expr` (800 random trees); `check_save` (the whole file after each save,
  the whole state after each load, the disk's own GAME.DAT); `check_vmstep` (the original's
  `vm_step` with every subsystem entry replaced by an `INT n; RETF` stand-in, routes chosen by an
  explorer while the original runs and replayed into the engine: 44 routes, 1 898 statements
  covered, the remaining 49 are switch defaults no state reaches; four routes under m286 with
  the clocks of every statement). `re-tools/mcall.py`: a write after a seek past the end of a
  file now extends it there (it appended). `tools/saves.py` shows a `GAME.DAT`'s slots and
  copies one into a save directory and out (the storage record `game.dat` is the file itself).

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
- **Done (2026-11-17).** `engine/snd/mus.c` (`snd/snd.h`): the machine's sound (with
  `sound=pmd26k` the music path of `lrv_music`, the driver installed with the profile's
  `pmd=/DF5 /K /M8 /V0 /E0`: `/DF` `/DS` `/M` `/F` are read, the music buffer is the engine's,
  the SSG-effect table the pack's; with `none` nothing), the binding (048F: each INT 60h through
  `vg.mus.int60`, which a test replaces; detection and queries, file choice `.n`/`.s`/`.m`,
  the part masks of the OPNA drivers, the copy into the buffer, `255 − trunc(2.55·v)` in
  16-bit arithmetic, start and stop) and the layer (04E4: init and the atexit term, play with
  the same-name rule, stop, the blocking fade one AH=19h per VSYNC with the original's long
  arithmetic, t = 0 dividing by zero as R6003, the measure + 1 / −1). `run_game` calls
  `mus_init` and `mus_term`; the VM's 1Bh, 1Ch and 35h call the layer. Without a device the
  music path renders a frame's worth per frame into nothing, so 35h advances with the frames:
  headless, the opening's first sync ends 201 ticks (3.56 s) after the song's start, as
  `sound.md` measured. `--render-wav FILE --song NAME` plays a song offline through the same
  path. The fades now block (180 VSYNCs for 1Ch 320): the first save of the autoplay run in
  `run.sh` moved from tick ~28 600 to ~30 900 (its limit is now 40 000). **Found on the way**
  (verified, `check_snd`): on the drivers other than PMD.COM the binding's last open is of the
  name as the script wrote it, not of the name it made with `.m` (`sound.md` §3.3). **Tests:**
  `tests/test_snd.c` + `check_snd.py`: the original's 04E4/048F under `re-tools/sndcall.py`'s
  stand-in and the engine's on the same stand-in, 348 commands on no driver and on boards 0,
  1, 2 and FFh (plays of the same and other names, `.n` songs, missing files, names without or
  with several dots, volumes 0 to 200 and −1, fades of −5 to 1000, no timer, no free slot,
  t = 0, term and init again): every return value, every one of the 3 012 driver calls with
  the frames before it, every file tried, the layer's variables and the music buffer
  identical. `check_pmd.py`: each song on the real PMD.COM (`re-tools/pmd_capture.py`, GAME.BAT's
  options, results kept by refcache) for 30 000 interrupts, the last 6 000 with an AH=19h ramp
  and a stop, replayed by lrvne's `tests/test_pmd.c` (built here as `lrv_test_pmd`) on the
  pack's song and SSG-effect table: all 21 the same.

### M5 — built-in sequences: first playable

- **OPENING:** the column reveal, 3 s pages, the decrement fade, skip.
- **ENDING / ENDING2:** the staff roll at double size, outline, effect-31 copies.
- **ANNOUNCE.**
- **The music mode.**
- **Test:** `check_builtin.py`, the DAC and VRAM at every VSYNC against the original.

Exit: the whole Japanese game plays on SDL3 with music. lrvne and vangel go public on GitHub.

**Done (2026-11-17).** `engine/bi/` (bi.c opening.c ending.c announce.c musmode.c) and
`engine/gfx/glyph.c` (segment 05C3: the glyphs into VRAM, the prologue's wipe, the double-size
glyphs, colour 15 → 8, the outline, the GRCG fill); statement 25h calls them, INIT asks the
console's question again unseen. The tables, strings, palettes and the roll's six rectangle
copies come from `M.EXE` (`tools/mexe.py builtin`: `bi.prologue`, `bi.staff`, `bi.music`,
`bi.strings`, `bi.rects`, `pal.prologue`, `pal.end1.*`, `pal.end2.*`). The music mode calls
the layer through `vg.bi.mus` (a test replaces it). **Test:** `tests/test_bi.c` +
`check_builtin.py`: the original's routines of segment 0504 on `textrig` (their wait loops,
`dac_set`'s wait for the retrace, `fx31_wait` and the fades as frame points; the music layer's
three entries stood in for), input decided while the original runs and replayed: OPENING with
no input and with keys, buttons and ESC at 14 points, the mouse closed, no free timer; ENDING
twice (its palette stays faded) and ENDING2; ANNOUNCE by keys, by buttons, with the mouse
closed, without its file; the music mode by keys and by the mouse, with the mouse closed,
without a driver and once more (remembered). Page 0 and the DAC at every VSYNC where either
changed, the pointer, the music calls, and at the end the result, pages 0 and 1, buffer 12
and the DAC: all 28 runs identical. **Found on the way** (verified, `platform.md` §5,
`text.md` §5.4): a later `gfx_init` also clears both pages (the engine set only the palette:
the music mode now starts and ends on black); the prologue's colour fade is 32 VSYNCs, the
staff roll's palette fade 64 and its working palette stays faded; the roll's 360/120 count from
the end of its effect-31 copies, and one more restore follows the last page; its double-size
glyphs are not emboldened; the sequences unlock the pointer with `mouse_lock(0, 1)`.
`textrig.run` now fails a run the emulation stops short of (it took that for the routine's
end). **Not charged:** the drawing's 80286 clocks (as for M2's text): about 5 frames a page of
the staff roll (four outlines) and about 5 once (colour 15 → 8) at 10 MHz; ANNOUNCE's 23-line
page and long-line cut are not reached by the shipped file.

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

**Done (2026-11-17).** `re-tools/va98.py` runs `M.EXE` whole, from its C start-up to its
exit: a VSYNC every `ipf` instructions (cpu_per_frame over an 80286's 6 clocks an instruction),
the spin loops' heads skipping to the next VSYNC when reached twice in one frame (so the
emulation does not spin), the VSYNC interrupt armed by port 64h and masked at the PIC, the
GDC status's retrace bit once after each VSYNC, the keyboard through the program's own INT 09h
handler (make and break codes), the keyboard BIOS for the console's question and the kanji
ROM (INT 18h), MSZ (INT 33h), and behind INT 60h the real `PMD.COM` resident in its own
machine (`pmdemu.py`), its timer interrupts on the master clock (3 993 600 / 56.42 clocks a
VSYNC), so statement 35h reads the real driver's measure counter. The waits are hooked where
the engine's `vg_wait_begin` stands (`va98.WAITS`: the message pages, the timed pages, menus,
statements 15h/16h, the prologue's pages, the notice, the music mode, the console's question).
`tests/test_game.c` is the whole engine (`vg_run`) on the test HAL. A route is a line a wait,
the input one entry a frame from the frame after the wait began (on the original: after its
first input poll, as a wait may draw first: the music mode draws its list for longer than a
frame, which the engine does in no time, and a key pressed and let go before the first poll
would be lost); both play it and print the
state at every wait; `tests/check_vm.py` compares: pc, depth, stack, every variable, CRCs of
both pages, buffer 12 and the window's two buffers, the page shown, the DAC, the skip flag, the
last menu's choice, the music layer's song and volume, the pointer, `game.dat`, and the INT 60h
calls since the wait before. The routes are made by `tests/e2e/explore.py` from 12 plans played
on `test_game` (which reads the route from stdin as the waits come, so the player decides
there; not the control protocol, so the routes replayed are exactly the ones played): the four
endings by six routes (ending 3 also by losing the fight, ending 4 also by the wrong armour),
the six save points into slots 1, 2, 3, 1, 2, 3, six investigation orders (all of menus 23-37),
all 42 menus the scenario has (menu 22 is never asked), 209 of the 211 messages it shows, the
prologue cut short, the prelude cut short in each of messages 206-209, the logo cut short,
the notice and the music mode (all 18 songs) by keys and by the mouse, the mouse not used,
loads of a good, a damaged and an empty slot and of no file, and `sound=none`. The loads start
from the `game.dat` the end1 route leaves (written by the explorer from the engine's run;
end1's own comparison checks that the original writes the same file). `make test` also checks
that the engine still plays every plan as recorded (`explore.py --check`; `make e2e-routes`
records them again), runs the game to `--max-ticks` with `--audio pull`, and every route runs
clean under `SAN=1` with the same output. **Result:** 12 routes, 8 015 waits, 388 235 frames
of the original: identical at every wait.

**Found on the way:** the binding's `int86x` keeps its REGS between calls, so every call but
AH=19h passes on the AL of the call before (AH=01h after a fade is 01FFh): the engine now does
the same (`vg.mus.in_al`). Not compared: time (the original's instruction time base is not the
engine's clock model; a route's input is tied to waits, so the state at each wait does not
depend on it), the measure counter's reads (statement 35h's loop reads it as often as it
turns; where the loop ends is in the variables), the driver's registers after a call other
than the AL the binding reads (09h, 17h, 22h), and, at the console's question, page 0, the
DAC, the pc and the variables (the original asks on the text screen before the scenario is
loaded). An entry of a route given while a blocking fade runs is gone, on both sides alike:
the music mode's routes leave 100 frames after each song.

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
