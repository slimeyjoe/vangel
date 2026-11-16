# What the shared layer (lrvne) covers for this port, and what it lacks

Analysis of 2026-11-15, made before any engine code exists here, against
lrvne as it stood that day (PC-98 planar-4 video, YM2203 sound path, mono
mixer, null / SDL3 / Amiga backends). Nothing was implemented. Facts come from
`docs/re/*.md`; items marked *open* are not answered by this repository.

**Summary:** a faithful PC-98 port on the 26K sound setup needs nothing new
from lrvne beyond four small additions (1-4 below). Real gaps appear only for
the OPNA / stereo sound setups and for the X68000 release.

## Covered as is

| Area | Need (source) | lrvne |
|---|---|---|
| Video | 640x400, 16 colours, 4 planes, 56.42 Hz; page 0 displayed only, page 1 and "buffer 12" off-screen; no text layer, scroll, EGC, sprites (`graphics.md` §1, §8) | `lrv_pc98_video_mode`, `lrv_screen` with 2 pages + 1 buffer; the 544x80 window buffers are engine-owned `lrv_surface`s |
| Pointer | MSZ mouse pointer drawn over the page | screen overlay |
| Sound, 26K | PMD 4.7g on a YM2203 (`sound.md`); `PMD.COM` is the same file another engine of this family already models | `lrv_opn` + `lrv_opnq` + `lrv_mixer`, `render_music`, mixer idle hook so the measure counter runs without a device |
| Input | own INT 09h latch (last scan code only, ESC on release), INT 33h absolute mouse with level buttons (`platform.md` §3) | neutral keys + `lrvne/pc98.h`; the latch and the ESC-on-release rule are engine code |
| Text | Shift-JIS, 16x16 from the kanji ROM (`text.md`) | `lrv_font_rom_glyph`, `lrvne/sjis.h` |
| Media | D88 2HD, 1024-byte sectors, FAT12; `.LZH` shop masters (`game-data.md`) | `tools/lrvne` diskimg, source |
| Saves | `GAME.DAT`, 3 x 132 bytes | one storage record |
| Timing | 16 timer slots counted in VSYNCs (`platform.md` §2) | frame + `LRV_HOOK_TICK` |
| Tests | — | control protocol, traces, autoplay, frame hashes |

## Gaps in lrvne

| # | Gap | Size | Interfaces |
|---|---|---|---|
| 1 | Palette helpers: add-and-clamp shift (`pal_shift`), decrement-only step (staff roll) | small | additive |
| 2 | Font builder: a raw 8x16 glyph array as input (the half-width font is the developers' own, in `M.EXE`, 159 glyphs) | small | additive |
| 3 | Glyph helpers: plain `g \| g<<1` bold (lrvne's keeps the 1-0-1 gap), transparent OR, inverse, outline, double size | small | additive |
| 4 | EXEPACK unpacker in the tools (`re-tools/exeunpack.py`; another engine of the family has the same) | small | additive |
| 5 | OPNA (YM2608) core: 6 FM, SSG, ADPCM-B. The vendored ymfm has it; only YM2203 is wrapped | medium | additive as a new ops + queue, or changes `opn.h` / `opnq.h` if they get a bank bit |
| 6 | A PCM channel in the sound path: 86-PCM (PMD86) and 4-bit SSG-PCM (PPS) | medium | additive |
| 7 | Stereo end to end (HAL `audio_open`, mixer, every backend) | large | changes interfaces; a mono downmix avoids it |
| 8 | X68000 DIM image kind and Human68k FAT12 probe (`re-tools/human68k.py`) | small | additive; X68000 media only |
| 9 | X68000 machine module: 768x512 mode, keyboard map, YM2151 core, a tick that is not the VSYNC (60.24 Hz from the driver's timer), joystick | large | mostly additive (joystick touches `input.h`) |
| 10 | PMD 4.7g sequencer shared in lrvne rather than one copy per engine | medium | **done** (2026-11-16): lrvne's PMD module, see below |

1-4 are all the 26K-only PC-98 port needs. 5-7 only for sound setups 2 and 3
of `GAME.BAT` (86 board, Speak Board). 8-9 only for an X68000 profile.

Gap 10 is closed (2026-11-16). PMD 4.7g, the 26K build, is lrvne's optional
PMD module (`LRVNE_PMD=1`, `lrvne/pmd.h`, lrvne `docs/pmd.md`). It now has what
this game needs beyond what the first engine to use it needed:
- rhythm part K, its drums played through PMD's built-in SSG effects (the
  table comes from the player's PMD.COM: lrvne `tools/lrvne/pmd.py`);
- the measure counter (INT 60h AH=05h: `lrv_pmd_measure`, for statement 35h);
- the installer's `/DF` and `/DS` (`lrv_pmd_set_options`).

lrvne's `lrvne/music.h` assembles the sound path around it.

**Conformance, verified.** Each song was run by the real PMD.COM under
emulation, with GAME.BAT's 26K options `/DF5 /K /M8 /V0 /E0` and PMD's own
SSG-effect table, for 30 000 timer interrupts. The capture tool is
`re-tools/pmd_capture.py`. Each log was then replayed against the module, as
lrvne's `tests/test_pmd.c` does.

For all 21 songs, every interrupt matches: the same register writes in the
same order at the same master clock, and the same status1, status2, fade
volume and measure counter after it. Two more runs match the same way:
- an engine-style fade of VA_M01 (AH=19h stepped down, then AH=01h, then a
  restart);
- VA_M19 with `/DF4`.

To repeat the check (the logs are game-derived: `resources/derived/`, never committed):

    lrvne tools/lrvne pmd ssgtab PMD.COM ssgtab.bin       # PMD's own SSG-effect table
    $EMU_PYTHON -I re-tools/pmd_capture.py --pmd PMD.COM \
        --opts "/DF5 /K /M8 /V0 /E0" --irqs 30000 -o VA_M01.M.log VA_M01.M
    <lrvne>/build/host/tests/test_pmd VA_M01.M.log VA_M01.M ssgtab.bin

The last command prints `... 30000 interrupts, the same`, or it prints the first interrupt that
differs.

**Still open for the port:**
- PPS drums (setup 1): need a PCM channel in lrvne;
- the OPNA setups 2 and 3: need a YM2608 core, and PMD86/PMDB2 modelled.

## To plan for in the engine regardless of lrvne

- **`M.EXE` is a pack-build input**, not only a verification aid: the TXB
  dictionary, the half-width font, and the texts and palettes of the built-in
  sequences (prologue, staff roll, music mode) live in it. It must be
  EXEPACK-unpacked when the pack is built. `docs/game-data.md` says otherwise
  and needed correcting. *Done (M0): the pack takes the dictionary and the
  font from it; `game-data.md` corrected.*
- **CPU-speed transitions:** effects 10, 20, 30, 32, 33, 34 run at CPU speed
  (only 31 waits for VSYNC). `lrv_sys_cpu` models this, but the reference
  machine's speed (`cpu_per_frame`) was never measured. *Open.*
- **Busy-poll of the measure counter** (statement 35h, the opening): the VM
  must charge CPU work per statement or yield, otherwise the music never
  advances in headless and push-audio modes.
- **Profile keys rather than code:** sound setup, mouse yes/no (the console
  prompt), release behaviour (PC-98 vs X68000 fade length, effect 33), the
  optional typo fix.
- **Inventory:** `resources/inventory.tsv` is nearly lrvne's format: rename
  `date` to `mtime` and prefix names with the release, since PC-98 and X68000
  files share names.
- **Duplicates to drop when the engine starts:** `re-tools/d88raw.py` and the
  mtools extraction (lrvne `diskimg`, `source`). *Done (M0): `source/tools/gamedata.py`.*
- **Doc inconsistency:** `other-versions.md` §2.4.4 says the PC-98 uses text
  VRAM for some screens; `graphics.md` §8 and `text.md` §5.1 (text GDC off,
  everything drawn into graphics VRAM) contradict it and look authoritative. *Fixed (M0).*

## Open questions

- Only the 26K setup, or also OPNA, stereo, SSG-PCM?
- Is X68000 (or FM TOWNS, for which there is no data) behaviour in scope?
- Do other games use this engine (multi-game profiles)?
- Which 16x16 font stands in for the kanji ROM; the MSZ pointer's shape and
  its INT 33h functions FDh / FFh.
- PMD86 / PMDB2 reference output (never emulated or recorded); the `.PPC` and
  PPS sample rates.
- Duration of the CPU-bound effects on real hardware.
