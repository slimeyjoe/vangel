# Game data: releases, media and files

The repository carries none of the game. This page lists what the original releases contain,
how the media are read, and which files matter for the research and a future reimplementation.
`resources/inventory.tsv` (committed, our own table) has every file with release, disk, size,
date, md5 and kind; everything extracted or derived lives in the git-ignored `resources/`
subdirectories.

## Releases

| Release | Media in the dump | Contents |
|---|---|---|
| `pc98` — PC-9801, 1995-03-01 | two 5.25" 2HD disks, D88 (also SCP/MFI/HFE flux images) | the game; this is the version the research documents |
| `x68k` — X68000, 1995-05 | one 2HD disk, DIM | the same scenario, text and pictures with an X68000 engine `M.X` and OPM songs ([re/other-versions.md](re/other-versions.md)) |
| `ibm` — "Graphic Disk", 1995-12-13 (labelled [IBM] by the dump) | one 3.5" 2HD disk, D88 | 22 BMP pictures (21 CGs without the baked-in message window, one new picture) with the FM TOWNS viewer MGV486 and a Macintosh viewer (PixelCat); not the game ([re/other-versions.md](re/other-versions.md)) |

Image checksums (md5) of the dumps used: PC-98 disk A `f0000a2fc462b338ba16820f0d6b5782`,
disk B `8b40092ff1ad170062cfa7d8b4c9b2c7` (D88); X68000 `e38a1df6a496da95eb619226b5044032`
(DIM); Graphic Disk `8deaef7b77a08d697d5924d3cf9b5e65` (D88). Any copy whose files match the
inventory's md5 is equivalent.

## Media

* **PC-98 disks**: D88 images of 77 × 2 × 8 sectors of 1024 bytes (1 261 568 bytes of data);
  each is an MS-DOS FAT12 volume (BPB at the start of sector 0: 1024 bytes/sector, 1 sector per
  cluster, 2 FATs of 2 sectors, 192 root entries, 1232 sectors, media FEh). Disk A also carries
  the NEC MS-DOS 3.3 system (`IO.SYS`, `MSDOS.SYS`, `COMMAND.COM`; Epson boot sector) and boots
  into `GAME.BAT`. `re-tools/d88raw.py IMAGE.d88 OUT.img` writes the plain sector image;
  `mcopy -n -m -i OUT.img '::*' DIR` (mtools) extracts the files.
* **X68000 disk**: DIM image = 256-byte header ("DIFC HEADER") + the same 1232 × 1024-byte
  geometry. The volume is Human68k's FAT12 variant with a Hudson boot sector whose BPB is
  big-endian at offset 12h; mtools cannot read it, `re-tools/human68k.py IMG OUTDIR` can
  (MS-DOS-style FAT and directory, Human68k's 10 extra name bytes at entry offset 0Ch). The
  disk has no `HUMAN.SYS`: it is started from a Human68k system disk or hard disk.
* **Graphic Disk**: D88 of 80 × 2 × 18 sectors of 512 bytes, an ordinary 1.44 MB FAT12 volume
  (label `VAGD/1.44`; the boot sector carries the stamp Windows 95 writes).

## The PC-98 files

| File | Size | Role | Document |
|---|---|---|---|
| `M.EXE` | 54 504 | the engine (Microsoft C, EXEPACK; `re-tools/exeunpack.py` unpacks it) | [re/README.md](re/README.md) |
| `CMD00.SCB` | 19 430 | compiled scenario "CRSC" (program, menus, expressions, palettes) | [re/scenario-format.md](re/scenario-format.md) |
| `CMD00.TXB` | 106 376 | message text "CRTX" | [re/text.md](re/text.md) |
| `GDATA.LIB` (disk B) | 969 441 | 54 pictures "GA00"/"GF0" | [re/graphics.md](re/graphics.md) |
| `VA_M01.M` … `VA_M21.M`, five as `.N` | 545–6 431 | songs (PMD) | [re/sound.md](re/sound.md) |
| `VA_PCM__.PPC`, `VA_PPS.PPS` | 62 240, 52 246 | PCM and SSG-PCM sound data | [re/sound.md](re/sound.md) |
| `ANNOUNCE.TXT` | 1 549 | notice shown by the title menu's 4th item | [re/platform.md](re/platform.md) §5.4 |
| `GAME.DAT` | 396 | three save slots (the dump holds a previous owner's saves) | [re/scenario-format.md](re/scenario-format.md) §7 |
| `GAME.BAT`, `HDGAME.BAT`, `AUTOEXEC.BAT`, `CONFIG.SYS`, `INSTALL.BAT`, `KIN.COM`, `ONGCHK.COM` | | start-up and sound-board selection | [re/platform.md](re/platform.md) §1 |
| `PMD.COM` 4.7g, `PMD86.COM`, `PMDB2.COM`, `PMDPCM.EXE`, `PPSDRV.COM`, `PDR.COM`, `P86DRV.COM`, `CNVLOAD.COM` | | sound drivers and loaders (M. Kajihara and others) | [re/sound.md](re/sound.md) |
| `MSZ.COM` | 5 024 | mouse driver (ZOBplus) | [re/platform.md](re/platform.md) §3.3 |
| `LHE.COM` | 6 376 | LHA extractor used by `INSTALL.BAT` | — |
| `開発.DOC` | 9 864 | developers' afterword (1995-03-01) | — |
| `IO.SYS`, `MSDOS.SYS`, `COMMAND.COM`, `OPENING.SYS` | | NEC MS-DOS 3.3 | — |

What a reimplementation needs from the PC-98 release: `CMD00.SCB`, `CMD00.TXB`, `GDATA.LIB`,
the songs (and, for the PCM-capable boards, `VA_PCM__.PPC` / `VA_PPS.PPS`), `ANNOUNCE.TXT`.
`M.EXE` is needed only as a reference for verification. The kanji glyphs come from the PC-98's
kanji ROM, not from the release ([re/text.md](re/text.md)).

`CMD00.SCB`, `CMD00.TXB` and `GDATA.LIB` of the X68000 release are the same files except for
palette #1 in the scenario (never referenced) and a few bytes of the text
([re/other-versions.md](re/other-versions.md)).
