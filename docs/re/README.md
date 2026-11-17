# Virgin Angel (Crystal Soft, PC-9801, 1995) — reverse engineering notes

Scope: the PC-98 release of 1995-03-01 — two 2HD MS-DOS disks with the engine `M.EXE`
(Microsoft C, EXEPACK), the compiled scenario `CMD00.SCB`, the text `CMD00.TXB`, the picture
library `GDATA.LIB`, PMD songs and PCM banks — documented as the basis for a new engine; plus a
survey of the X68000 release and the "Graphic Disk". The documents describe the original only.

Source material (not in the repository): the D88 images of the two PC-98 disks, the X68000 DIM
image and the Graphic Disk D88 ([../game-data.md](../game-data.md), `resources/inventory.tsv`).

## The engine at a glance

`GAME.BAT` sets up the sound driver and runs `m cmd00.scb b:\gdata.lib`. `M.EXE` asks on the
console whether to use the mouse, loads the whole scenario (decrypting it) and all messages into
memory, takes over the VSYNC and keyboard interrupts, and runs a small statement VM: 2 034
statements of 34 opcodes (assignments and C-like expressions over 20 variables, if/switch/goto/
call/return, messages, menus, picture loads, rectangle copies with seven transition effects,
palette fades, music, saves, six built-in sequences). There is no animation, no sound effect
and no page flipping: everything is drawn into graphics page 0, text included.

## Documents

| Document | Contents |
|---|---|
| [`scenario-format.md`](scenario-format.md) | `CMD00.SCB` ("CRSC"): start-up, header and sections, the running-XOR encryption, the tables (variables, menus, expression nodes, palettes, statements), loader checks, expression evaluation, the VM (state, loop, v1 result register), **every opcode**, the save file `GAME.DAT` (with its off-by-one), the built-in table, compiler idioms |
| [`script-catalog.md`](script-catalog.md) | the game's structure: boot, logo, title menu, the opening, chapters 1–11, the raid and the decision tree to the **four endings**, variables, music cues (sub 1670), save points, unused messages |
| [`text.md`](text.md) | `CMD00.TXB` ("CRTX": inverted bytes + a 90-character one-byte dictionary), control codes, the message window (geometry, glyph drawing via INT 18h AH=14h and the embedded font, emboldening, colours, page waits, the ↵ icon, timed pages and their abort), menus (layout, inversion bar, keys, mouse hover), built-in texts (ANNOUNCE, prologue, staff roll, music mode) |
| [`graphics.md`](graphics.md) | `GDATA.LIB` and the `.gf` coder (Pi-style: 2-pixel copies from five positions, Elias-gamma lengths, per-colour move-to-front lists; colour 8 transparent), buffers 10/11/12, op 31 load, op 32 copies and **transitions 10/20/30/31/32/33/34** pixel-exact with timing, palettes and fades (op 30/1A/2F), PC-98 hardware use, screen layout, every picture with its palette, quirks to copy |
| [`sound.md`](sound.md) | the music layer over PMD (INT 60h calls, file choice `.n`/`.s`/`.m` per driver, volume, the blocking VSYNC fade, the measure counter of op 35h), `GAME.BAT`'s five board set-ups and the drivers, `ONGCHK`, the 21 songs (parts, tempo, lengths, OPN vs OPNA), `VA_PCM__.PPC`/`VA_PPS.PPS`, reference VGMs; PMD 4.7g itself is lrvne's PMD module (`docs/pmd.md` there) |
| [`platform.md`](platform.md) | the release's boot chain, machine requirements, timing (VSYNC timers, `t × 564 / 1000`), input (own INT 09h handler, ESC-on-release quirk, MSZ mouse via INT 33h, pointer lock, the "release" step), shutdown and exit codes, the built-in sequences INIT, OPENING, ENDING/ENDING2 (staff roll), ANNOUNCE, MUSMODE |
| [`other-versions.md`](other-versions.md) | the X68000 release (`M.X`: the same C program built with GCC; graphics, timing via PMD.X, behaviour and data differences), the "Graphic Disk" (an FM TOWNS/Macintosh CG disk: 21 clean CGs as BMP, palettes), FM TOWNS (no data) |
| [`listing/`](listing/) | names files for the annotated disassembly: `m-names*.tsv` (M.EXE, by area: VM/platform, graphics, text, sound) and `mx-names-x68k.tsv` (X68000 `M.X`) |

## Coverage

The annotated listing finds 437 functions (18 000 instructions) in `M.EXE`. Every function
outside segment 0886 has a name and a role in `listing/m-names*.tsv`; segment 0886 is the
Microsoft C run-time library (1990), of which the routines the game calls are named (stdio,
heap, `int86`, interrupt vectors, 32-bit arithmetic) and 57 internals (buffering, heap
management, start-up) are left unnamed. `0000:046A` is the expression evaluator's jump table
mis-read as code.

## Tools (`../../re-tools/`; the decoders a build reuses in `../../source/tools/`)

Run Python with `-I`; tools marked † need `$EMU_PYTHON`, a Python with capstone, unicorn,
pillow, numpy). Listings and outputs go to the git-ignored `resources/derived/`.

| Tool | Purpose | Verification |
|---|---|---|
| `human68k.py` | Human68k volumes (X68000); the PC-98 disks are read by lrvne's `diskimg` (`source/tools/gamedata.py`) | the volumes list cleanly; files match `inventory.tsv` |
| `exeunpack.py` | removes `M.EXE`'s EXEPACK layer | the unpacked image runs to `main` under `mcall.py` |
| `dis16.py`, `madis.py` † | recursive-descent disassembly; annotated listing with names, DGROUP strings and far globals resolved through the segment-pointer table | — |
| `mcall.py` † | unicorn harness: the original C start-up to `main` with a Python INT 21h, then any routine callable; VRAM pages, GRCG, palette ports modelled; screenshots | the original loaders, decoders and effects run in it |
| `scb.py` (in `source/tools`), `scbdis.py`, `scbsum.py`, `scb_verify.py` † | scenario parser; readable listing (1-based pc, infix expressions, menus); flow/reachability; per-subroutine summary; check against the original loader | `scb.py` consumes both releases' `CMD00.SCB` exactly; `scb_verify.py`: all variables, menus, expression nodes, palettes, 2 034 opcodes and the operands of 1 458 statements equal the original loader's tables, both releases |
| `txb.py` (in `source/tools`), `txb_verify.py` †, `text_render.py` † | text decoder and page-layout model; check against the original; renders pages/menus with the original code | all 213 messages / 5 732 lines byte-identical, 1 849 pages laid out identically, both releases |
| `gf.py` (in `source/tools`), `gf_verify.py` † | archive and picture decoder, PNG export; check against the original | 54 pictures × 4 decoder variants bit-exact |
| `gfx_fx.py`, `gfx_pal.py`, `gfx_fx_verify.py` †, `pal_verify.py` † | models of the transitions and palette fades; checks | 136 transition cases (every VRAM write in order, waits), 20 palette sequences |
| `m286.py` †, `fx_cost.py` † | `mcall.py` with time: 80286 clocks per executed instruction (Intel's table, no wait states), a VSYNC every frame's worth, the spin loops jumping to what they wait for; the clocks of op 32h's parts and the transitions' durations, the engine's `gfx/fx_clk.h` | the engine's transitions match the original's clock at every write (`source/tests/check_fx.py`) |
| `vm_cost.py` † | the clocks of the interpreter (vm_step's paths, expr_eval's nodes) on the 80286 of `m286.py`: the engine's `vm/vm_clk.h` | the engine's charge equals the original's clocks at every statement of four routes (`source/tests/check_vmstep.py`) |
| `sndcall.py` †, `pmdinfo.py`, `pmdemu.py` †, `pmd_capture.py` † | the sound layer against a fake PMD/PPSDRV; song structure table; the real PMD.COM under emulation → VGM | every INT 60h/64h call of the engine traced per driver; 21 songs recorded on a 26K; the engine's music layer matches the original's on sndcall's stand-in (`source/tests/check_snd.py`), lrvne's PMD module matches the real driver on every song (`check_pmd.py`, from `pmd_capture.py`'s logs) |
| `x68dis.py` †, `vagd_compare.py` †, `ibm_bmp_compare.py` | X68000 `M.X` disassembly; Graphic Disk BMPs vs the `.gf` pictures and palettes | — |
| `sjstrings.py` | Shift-JIS strings with offsets | — |

## Open questions (collected)

* Section tags 0Bh (199) and 0Ch (61) of the scenario: stored, never read; what the compiler
  counted is unknown.
* The rule behind effect 30 vs 32 (only a tendency is visible), the real-machine duration of the
  transitions that run at CPU speed (only effect 31 waits for VSYNC; their cost in 80286 clocks
  is measured, the machine's speed and wait states are not).
* MSZ's INT 33h functions FDh/FFh; INT 18h AX=1B01h before text lines; port 68h ← 08h.
* PMD86/PMDB2 behaviour is read from the binaries, not run; the PCM sample rates are assumed;
  no reference recording of the 86 / Speak Board versions.
* X68000: screen mode 19h (HELP key at start), PMD.X details, step-by-step comparison of its
  transitions.
