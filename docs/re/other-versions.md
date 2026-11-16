# Other releases

The analysis in this directory is of the **PC-9801 release** (two 2HD disks, 1995-03-01; engine
`M.EXE`). Two more media were examined: the **X68000 release** (one 2HD Human68k disk, May 1995)
and the **"Graphic Disk"** `VAGD` (one 1.44 MB disk, December 1995). An **FM TOWNS** version is
known from the credits and the developers' notes, but no data for it is available (§4).

| | PC-9801 (1995-03) | X68000 (1995-05) | Graphic Disk (1995-12) |
|---|---|---|---|
| Engine | `M.EXE` (MS C 6/7, 16-bit, EXEPACK) | `M.X` (GCC, libc 1.1.32, MC68000): **the same C program**, new platform layer (§2.4) | none: a viewer, `MGV.EXP` (FM TOWNS) plus `PixelCat` (Macintosh) |
| Scenario `CMD00.SCB` | | identical except the unused first palette (§2.5) | — |
| Text `CMD00.TXB` | | one typo corrected, 1 byte shorter (§2.5) | — |
| Pictures `GDATA.LIB` | 54 `.gf`, 16 colours | byte-identical | 21 of the event CGs as 640×400 4-bit BMPs **without the message window** baked into the PC-98 pictures, plus one new picture (§3.2) |
| Music | PMD for OPN/OPNA (`.M`/`.N`), PCM/PPS banks | 21 `.M` for `PMD.X` 3.9f (OPM), no PCM | — |
| Saves `GAME.DAT` | 3 × 132 bytes, big-endian | same format, interchangeable (§2.7) | — |

Tools written for this (run with `$EMU_PYTHON -I`): `re-tools/x68dis.py`
(Human68k `.X` disassembler, capstone M68K; names file `docs/re/listing/mx-names-x68k.tsv`),
`re-tools/vagd_compare.py` (BMP ↔ `GDATA.LIB` comparison, numpy). Outputs (game code and data,
git-ignored): `resources/derived/x68k/mx.asm` (annotated listing of `M.X`), `pmdx.asm` (partial
listing of `PMD.X`), `mx_strings.txt` / `mexe_strings.txt` (string dumps of both engines);
`resources/derived/ibm_bmp/` (the 22 BMPs, `compare.txt`), `resources/derived/ibm_pixelcat/`.

Addresses: `M.EXE` as `SEG:OFF` of the unpacked image (as elsewhere in this directory); `M.X` as
`tXXXXX` = offset in the text section (= load image offset; the data section starts at image
offset C0AAh, bss at CFACh, and data/bss addresses are given as plain image offsets). **Verified**
= read in the code (both binaries where a comparison is stated) or checked by a script over the
data; **inferred** = concluded, not checked.

## 1. Sources

| Medium | File | Notes |
|---|---|---|
| X68000 | `resources/raw/x68k.img` → `resources/original/x68k/` (`re-tools/human68k.py`) | 1 261 568 bytes, 2HD 1024-byte sectors, Human68k FAT12 (BPB big-endian at 12h: 1232 sectors, 2 FATs of 2 sectors, 192 root entries, media FEh). |
| Graphic Disk | `resources/raw/ibm_g.img` → `resources/original/ibm/` | 1 474 560 bytes, standard FAT12 1.44 MB, volume label `VAGD/1.44` (1995-12-13 16:56). The boot sector's OEM field is `(0R{+IHC` — the random `?????IHC` stamp Windows 95 writes on a floppy it mounts, so the disk passed through a Windows 95 machine at some point (not necessarily at mastering). |

## 2. X68000 release

### 2.1 Disk and boot (verified)

| File | Size | Date | |
|---|---|---|---|
| `M.X` | 56 102 | 1995-05-19 | engine (§2.2) |
| `PMD.X` | 10 322 | 1992-09-23 | "Music Driver P.M.D. for X68000 (Version 3.9f) Copyright (C) Aug.18th 1992 by M.Kajihara(KAJA)" |
| `VA_M01.M`…`VA_M21.M` | 379–5 747 | 1995-05-12 | OPM songs ([sound.md](sound.md) §7) |
| `GAME.BAT` | 407 | 1995-05-17 | `pmd /K`, `m cmd00.scb gdata.lib`, `pmd -r` |
| `HDINST.BAT` | 663 | 1995-05-19 | `HDINST src: dst:` copies `*.*` to `dst:\V_ANGEL` ("HDインストールは無保証です") |
| `CMD00.SCB` / `CMD00.TXB` / `GDATA.LIB` / `ANNOUNCE.TXT` | | 1995-03-01/02 | the PC-98 files (SCB/TXB with the changes of §2.5; `GDATA.LIB` and `ANNOUNCE.TXT` byte-identical) |
| `GAME.DAT` | 396 | 1996-01-05 | a player's saves (§2.7) |
| `DIRDTOP.SX` | 116 | 2000-09-26 | SX-Window desktop state, written when the disk was opened under SX-Window years later |
| `V_ANGEL\` | (empty dir) | 2005-04-05 | later addition (an `HDINST` aimed at the floppy itself would create it) |

Everything fits on one disk (the PC-98 release needs two because `GDATA.LIB` alone fills disk B).
**The disk is not bootable on its own:** the boot sector is the standard Human68k one ("Hudson soft
2.00", BPB at 12h), which loads `HUMAN.SYS` from the root and otherwise prints `Human.sys が
見つかりません` — and there is no `HUMAN.SYS`, `COMMAND.X` or `CONFIG.SYS`. The user boots
Human68k from a system disk or hard disk and runs `GAME.BAT` (which needs `PMD.X` found as `pmd`;
the `exitdrv2` lines are commented out). Unlike the PC-98 `GAME.BAT` there is no sound-board menu:
the X68000 always has the YM2151.

### 2.2 `M.X` (verified)

Human68k `.X` header: base 0, entry t07D9C, text C0AAh, data F02h, bss 67E36h (425 KB),
relocation table B3Ah bytes (1437 longword fixups), no symbols. Compiler and library: GCC for
X68k with the Project-LIBC library 1.1.32 (data string `1.1.32`, the `HUPAIR` marker after the
entry jump, `libc: setblock failed.`, `libc: this version of human68k is not supported.`, the
POSIX error texts). C functions use `link a6` frames and stack arguments; switches compile to
`move.w tab(pc,d0.l),d1; jmp tab(pc,d1.w)` (decoded by `x68dis.py`).

**It is the PC-98 C source recompiled**, with the platform layer rewritten:

* every engine string is shared: `シナリオバイナリ(*.scb)を指定してください`, `file not found`,
  `scenario reading...`, `text reading...`, `Warning : 開始番地が設定されていません…`,
  `Calling nested too much`, `No Calling stack (Invalid RETURN)`, `ID error;_;`, `メモリ不足です`,
  `lastが変です`, the init failures (`タイマー/入力系/グラフィックの初期化に失敗しました`),
  `お知らせ用ファイルが見つかりません`, `マウスのボタンかキーを押して下さい`, the prologue text,
  the staff roll and the music-mode table (same 18 songs in the same order);
* the function decomposition and control flow match routine by routine wherever compared: SCB
  header and section reader (`06BB:01AB` ↔ t0018E, both skip the 4 "system" bytes `DOS ` without
  checking them), the palette record reader, the loader of op 30 (`063C:046C` ↔ t005F4: palette
  byte ≤ 1 ⇒ NULL), the TXB reader, the expression evaluator (ops 5..16, t01296 switch), the VM,
  save/load (`001E:042C`/`0577` ↔ t01806/t01924, same off-by-one over variable entries 0..19),
  the timer API, the music API (state values 0Ah/0Bh/0Ch, same-name test, loop counter);
* the TXB dictionary (90 SJIS characters) is the same table, but stored **byte-swapped**
  (image C206h, `41 81 63 81 …` = 8141h, 8163h as big-endian words); `txb_line` t010B4 emits the
  low byte first. So the table is a `unsigned short[]` in the C source, written with integer
  values, which a little-endian and a big-endian compiler lay out differently;
* new code: `graph_init: めもりがないぴょん.`, `graph_init:onexit failed.`,
  `music_init:onexit failed.`, the TVRAM fallback messages (§2.4.5), all IOCS/DOS calls.

The credits string (staff roll) differs: PC-98 `プログラム PC-9801/FM-TOWNS 宮本 正城`, then
`原画`/`ＣＧ`/`作曲／編曲`, `Special Thanks to 梶原 正裕`, `Special Thanks to ＴＥＡ`; X68000
inserts `X680x0 匿名希望 :-)` (the porter is anonymous) under プログラム, labels the KAJA line
`MusicDriver Ｐ．Ｍ．Ｄ．`, drops the ＴＥＡ line and ends with `Copyright(c) 1995 CRYSTAL SOFT`.

### 2.3 The scenario VM (verified)

`main` t0099C: `m SCENARIO.SCB [GDATA.LIB]` (argc < 2 ⇒ usage, exit 1), `mem_probe` t04AA8,
SCB load (exit 2 on error), TXB load (named by the SCB, exit 2), entry statement must be op 2Dh
(else the warning and pc = 1), `run_game` t01438: `timer_init` t01F52, `music_init` t02FEA,
`input_init` t02C9C, `gfx_init` t01FFA, each with an `atexit` terminator, then `vm_run` t014FA.
Same order and the same exit codes as `run_game 001E:0069`.

* **Decryption**: t0023C `state ^= raw + key; return state & 0FFh`, key from the header (6Ah) —
  the SCB format of [scenario-format.md](scenario-format.md) unchanged.
* **Dispatch** (`vm_step` t0150E): `op = stmt[0] (u16); switch (op − 15h)` over 0..22h at
  t0152C, exactly as `001E:015B`. Opcodes 26h–2Ah and 2Ch call `exit(4)` (t016E0; PC-98
  `001E:01B4`), 2Bh/2Dh are no-ops, 2Eh returns 0 (end). Handlers (names in
  `mx-names-x68k.tsv`): 15 t01B8A, 16 t01C5E, 17 t01CD2, 18 t01CD4, 19 t01CDC, 1A t01D54,
  1B t01D94, 1C t01DAA, 1D t01738, 1E t01A36, 1F t01A7A, 20 t01AA4, 21 t01B68, 22 t01AEE,
  23 t01B0E, 24 t01DEC, 25 t016EE, 2F t01D6C, 30 t01D7E, 31 t01D26, 32 t01D34, 33 t01D42,
  34 t01B76, 35 t01DCE, 36 t0175E, 37 t01CAE.
* **Message control codes** (`msg_show` t026E8, switch at t0277E over 10h..1Ah): 10h/11h ignored,
  12h page + key, 13h speaker, 14h page + timed, 1Ah end — as in [text.md](text.md); a line is cut
  at 79 bytes (`txb_line` limit 4Fh).

### 2.4 Platform layer

#### 2.4.1 Timing (verified)

The X68000 build has no timer of its own: **it runs its 16 timer slots from `PMD.X`'s interrupt**.
`tmr_init` t03C3E clears the slots, calls `pmd_check` t039F6 and registers `tmr_isr` t03BDE with
`trap #0` function 14h. In `PMD.X` that function stores the hook (t01434 → `$163A`), which the
MFP Timer-D handler (t01026; `IOCS _TIMERDST` with D1 = 07A6h: prescaler 1/200 of 4 MHz, count
166 ⇒ 120.48 Hz) calls on every second interrupt — **60.24 Hz**. The engine knows it:
`tmr_start` t03CE6 sets `target = t × 6024 / 10000` and `tmr_elapsed` t03DBC returns
`count × 10000 / 6024` — the same "t in 1/100 s" API as the PC-98 (`t × 564 / 1000` VSYNCs at
56.4 Hz, [platform.md](platform.md) §2). **Waits therefore last the same real time on both
machines** (to within one tick). Consequence: if `PMD.X` is not resident (`trap #0` vector not
pointing into RAM), `timer_init` fails and the program exits with `タイマーの初期化に失敗しました`;
the PC-98 build runs without a sound driver.

#### 2.4.2 Music (verified unless marked)

`PMD.X` is called with `trap #0`, D0 = function (dispatch table `PMD.X` t01354): 0 start,
1 stop, 2 fade-out speed (stores D1), 6 music buffer address (A0), 10h work area (A0),
13h/14h install hooks. `pmd_check` t039F6 takes the buffer (fn 6) and the work area (fn 10h),
installs `pmd_vol_hook` t039AC with fn 13h. Play (`pmd_load_play` t03ACA): `_OPEN` the song
(".m" appended if the name has no dot), `_READ` at most 3C00h bytes straight into PMD's buffer,
fn 0, then fn 2 with D1 = 1. Volume: the hook writes PMD work+23h = `(100 − vol) × 254 / 100 + 1`
(vol 100 → 1, 0 → 255) each time `PMD.X` calls it (*inferred*: from its OPM/music interrupt, the
caller of the fn 13h hook was not traced; and that this emulates the PC-98 AH=19h fade volume by
overriding PMD's own fade-out byte, the speed-1 fade being reset each time). Statement 35h returns work+24h
+ 1 (the loop/measure counter, as PC-98).

**Difference: statement 1Ch (fade and stop) lasts half as long.** `music_fade` t030F0 starts with
`d = t / 2` and ramps the volume linearly to 0 over `d` hundredths; `mus_fade_stop 04E4:00F0`
uses `t` itself ([sound.md](sound.md) §3.4). The music mode's 150 becomes 0.75 s instead of 1.5 s.
Like PC-98 the fade blocks the game.

#### 2.4.3 Graphics (verified)

* **Screen mode** (`crt_init` t05962): `IOCS _CRTMOD` 10h (768×512, 16 colours, 31 kHz; the
  graphic VRAM is one 1024×1024 page, one word per pixel, colour in bits 0–3), then the CRTC
  display window is narrowed with `_B_WPOKE`: R2/R3 (E80004h/E80006h) = 24h/74h, R6/R7
  (E8000Ch/E8000Eh) = 60h/1F0h — 80 × 8 = 640 columns and 400 lines, centred in the 768×512
  raster. The old mode is restored at exit. If **HELP** is held at start (`_BITSNS` group 0Ah
  bit 4, key 54h) `graph_init` t058EA tries `_CRTMOD` 19h instead and keeps it if the read-back
  confirms it (*inferred*: a mode of an extended IOCS for another monitor; not identified).
* **Buffers** (PC-98 buffer numbers kept): **10 = graphic VRAM C00000h** (visible), **11 =
  D00000h** (rows 512–1023 of the same page: off-screen VRAM, the counterpart of PC-98 page 1),
  **12 = 640×400 words in main memory** (`malloc(7D000h)`). Row stride 800h bytes in VRAM, 500h in
  memory (`buf_clear` t05ACC and the copy routines test the address range C00000h–DFFFFFh).
* **Palette** (`pal_set_hw` t05B70): the 48-byte record R[16], G[16], B[16] (4-bit; the SCB nibble
  triples in read order are R, G, B, `scb_read_palette` t00EAC) becomes the X68000 word
  `G<<11 | R<<6 | B<<1 | 1` with each 4-bit value **doubled** (5-bit 0..30, intensity bit set);
  written with `IOCS _GPALET` after waiting while MFP GPIP (E88001h) bit 4 (V-DISP) is set. The
  PC-98 routine (`dac_set 00DD:01D0`) writes the same three arrays to the DAC ports AC/AA/AE.
  So colour 15 is 30/31 of full scale on the X68000 (*inferred*, from the doubling).
* **Effects** of statement 32h (`rect_dispatch` t05EE8, switch at t05FDE over 0Ah..22h): 0Ah
  t052E6, 14h t0538A, 1Eh t055D8, 1Fh t0568E, 20h t0544C, 21h t055D8, 22h t05516; other values
  draw nothing. Same effect set as PC-98 (`fx_copy`, `fx_20`, `fx_30`…`fx_34`), except that **21h
  (33) runs the 1Eh (30) routine** on the X68000 — harmless, the scenario uses only 10, 30, 32
  and 34 (144/36/54/1 statements). The effect algorithms were not compared.
* **Message window**: the 544×80 area at (48, 307) is saved from VRAM into a byte-per-pixel
  buffer (bss 58B3Ah, `win_save` t060A2, `movep.l` reads of the odd bytes) before a picture or
  copy changes the screen and put back by statement 18h (`win_restore` t06108); text is composed
  in a second such buffer (6353Ah). The PC-98 counterpart is `op18_flip 0315:07F5` /
  `02BE:009C` ([graphics.md](graphics.md)).

#### 2.4.4 Text rendering (verified)

Glyphs come from the **X68000 CG ROM** through `IOCS _FNTGET` (t06276 half-width 8×16 with D1 =
0008xxxxh, t0639A full-width), not from an embedded font: for codes below 28h a 40-entry
pointer table (C78Ah) may supply a built-in 8×16 glyph — entries 01h, 02h and 21h–27h are set
(01h is a raised comma-like mark). Each set bit is drawn as colour 15 at x and x−1 (doubled
horizontally) with colour 0 one pixel down-right (t06288 onwards: a bold face with a drop
shadow). `IOCS _SYMBOL` is used for some screens (t0434C, t048D4…, t06774). The menu, announce
and music-mode screens use the **text plane** (`_B_PUTMES`, `_B_CLR_ST`, `_TPALET`). The
PC-98 build does not: its text GDC stays off and those screens are drawn into graphics VRAM like
everything else ([graphics.md](graphics.md) §8, [text.md](text.md) §5.1).

#### 2.4.5 Memory probe and the TVRAM fallback (verified)

`mem_probe` t04AA8 tries `malloc(96000h)` (614 400 bytes) and frees it. On failure it prints
`主記憶が不足しているため、TVRAM をバッファに用います` / `マウスによる入力はできません` /
`描画速度が遅くなります`, uses **text VRAM E00000h (512 KB) as buffer 12** (`_TGUSEMD` 1,2 —
text screen in use by an application), and clears flag bit 1 of the long at C374h; with that bit
clear the 15 text palette entries are set to black (`graph_init`) and the mouse is not used. This
is **the PC-98 "use the mouse?" flag** (`DS:0110` bit 1): PC-98 `sys_init 0504:0004` asks
`マウスを使用しますか?[Y/N]` (Y/y/ﾝ, N/n/ﾐ) and then prints `プログラムのロード中です...`; the
X68000 build asks nothing and derives the flag from free memory (*inferred*: a 1 MB machine gets
the fallback, a 2 MB one does not; bss 425 KB + 512 000 bytes + buffers).

#### 2.4.6 Input (verified)

Polled, no interrupt handler (PC-98 hooks the keyboard IRQ, [platform.md](platform.md) §3):
`keys_read` t038A2 reads the key matrix with `IOCS _BITSNS` and maps ESC → 100h, RETURN and
keypad ENTER → 101h, SPACE → 102h, ↑ / keypad 8 → 103h, ← / keypad 4 → 104h, → / keypad 6 →
105h, ↓ / keypad 2 → 106h, and `_B_SFTSNS` SHIFT → 200h, CTRL → 400h. Mouse through IOCS
(`_MS_INIT`, `_MS_LIMIT` 0..639 × 0..399, `_MS_CURGT`, `_MS_GETDT`, `_MS_CURON/OF`); a joystick
in port 1 (`_JOYGET`, t036CC: directions and the two buttons) — the PC-98 build has no
joystick. `_KFLUSH` empties the key buffer.

### 2.5 Data differences (verified)

* **`GDATA.LIB`**, **`ANNOUNCE.TXT`**: byte-identical to PC-98.
* **`CMD00.SCB`**: same size and header (`CRSC` 01 01 `DOS `, key 6Ah, entry 1979). The 25
  differing bytes (file 5223–5247) decode to a different **first palette record** (table entry 1)
  and nothing else; every other table and all 2034 statements are equal (`scb.py`). That entry
  cannot be used: the op 30 loader maps palette numbers ≤ 1 to NULL (`063C:04A4`, t0061E) and no
  other code reads the palette table (`0BA1:0084`, `58B06h` have no other users). Both versions
  hold random-looking values there (PC-98 `a2c 580 edf f70 …`, X68000 `4a6 8fc d0d 6c6 …`);
  *inferred*: uninitialised memory written by the scenario compiler.
* **`CMD00.TXB`**: 106 375 bytes, PC-98 106 376. The X68000 file is the PC-98 file with byte 3997
  (0-based) deleted; message 5 (0-based, at 2402) loses one dictionary byte `か`, correcting the
  typo `しなかっかただけ` → `しなかっただけ`. No other change: the text is otherwise identical
  (`txb.py` on both; also [text.md](text.md) §2.7).
* **Songs**: re-made for OPM (type byte 01h, no memo strings, 9–36 % smaller); see
  [sound.md](sound.md) §7. The X68000 has no counterpart of the PC-98 PCM/PPS banks.

### 2.6 Content and behaviour differences

| | PC-9801 | X68000 | |
|---|---|---|---|
| Wait timing | VSYNC 56.4 Hz, `t × 564/1000` | PMD.X Timer-D 60.24 Hz, `t × 6024/10000` | same real time, verified |
| Statement 1Ch | fade over t/100 s | fade over t/200 s | verified |
| Sound driver | optional (no driver ⇒ silent, waits skipped) | `PMD.X` mandatory (timer) | verified |
| Mouse | optional, asked at start | automatic (off only in the TVRAM fallback) | verified |
| Joystick | — | port 1 | verified |
| Music mode | help line `選択：カーソル上下   演奏：…   終了：ＥＳＣキー` | no help line; a 19th list entry `メインメニューに戻る` (t050B4) | verified |
| Effect 21h | own routine `fx_33` | = effect 1Eh | unused by the scenario |
| Credits | §2.2 | §2.2 | |
| Text | one typo | corrected | §2.5 |
| Palette accuracy | 4-bit DAC | 4-bit ×2 on 5-bit (max 30/31) | inferred |

Nothing in the scenario differs, so there is no X68000-only or PC-98-only *story* content.

### 2.7 Save compatibility (verified)

`save_slot` t01806 writes the PC-98 record byte by byte (`S`, `D`, big-endian 132, pc, depth, 32
stack words, then 20 × (type byte, BE16 value)) and `load_slot` t01924 checks `SD` and 132 —
endianness-independent C, identical layout. As the scenario is statement-for-statement identical,
a `GAME.DAT` from either machine loads on the other. The X68000 `GAME.DAT` on the disk holds
three slots at pc 1742 (the same as the PC-98 file) with call stacks (2028, 499), (1302), (1302);
its unused first variable record contains junk (type BAh, value FF03h) where the PC-98 file has
zeros — that entry is the unused slot of [scenario-format.md](scenario-format.md) §7 and a port
should ignore it.

## 3. The "Graphic Disk" (`VAGD`, 1995-12-13)

**Contradiction with the working assumption that this is an IBM PC disk:** the viewer on it is an
**FM TOWNS** program and the second viewer is for the **Macintosh**; only the image format
(Windows BMP) and the 1.44 MB FAT12 floppy are PC-like. Nothing on it targets DOS/V or Windows.

### 3.1 Files (verified)

| File | Size | Date | |
|---|---|---|---|
| `SETUPA.BAT`…`SETUPH.BAT` | 286 | 1995-12-13 | identical but for the target drive A:–H: copy `LHA.EXE`, `VAGD.LZH`, `MGV.EXP` to `\VAGD`, `lha x VAGD.lzh`, delete the archive |
| `LHA.EXE` | 34 445 | 1991-10-19 | LHA for MS-DOS ("LHARC" signature; *inferred* 2.1x by Yoshi) |
| `VAGD.LZH` | 843 299 | 1995-12-13 | `-lh5-`, 22 BMPs (§3.2) |
| `MGV.EXP` | 50 734 | 1994-12-06 | Phar Lap `P3` flat 386 executable, packed with `PACKEXP1.14`; strings `MGV486 V2.61 HIGHEND`, `FM-TOWNS Multi Graphic View(er)`, `TOWNS MOUSE LIBRARY`, BMP/GIF/JPEG/… — **the FM TOWNS image viewer MGV486**, run under the Towns' RUN386 |
| `PIXELCAT.LZH` | 207 360 | 1995-07-10 | not an LZH at offset 0: a **MacBinary** file (128-byte header: name `PixelCat167.lzh`, type/creator `LHA `/`MYMY` = MacLHA, data fork 207 165 bytes). The data fork is a normal `-lh5-` archive (7z reads it) holding three MacBinary files: `PixelCat1.6.7` (`APPL`/`xPIC`), `PixelCat 1.6.7.doc`, `.hed`: **PixelCat 1.6.7** by BombCat & Yoshiki (DreamField), a freeware Macintosh viewer (System 7 + QuickTime 1.5; BMP, MAG, PIC, Pi, GIF, JPEG …). Unwrapped copies: `resources/derived/ibm_pixelcat/`. |

So the disk is a cross-platform CG gift/sale disk: BMPs plus a viewer for the FM TOWNS and one for
the Macintosh (*inferred*: users of PC-98/X68000 had their own viewers; `SETUP?.BAT` + `LHA.EXE`
work on any MS-DOS, including the Towns' DOS).

### 3.2 The BMPs (verified, `re-tools/vagd_compare.py`)

All 22 are Windows 3 BMPs (40-byte header), 640×400, 4 bpp, uncompressed, 16-entry palette,
128 118 bytes; `bfSize` says 256 118 in every file (computed as if one byte per pixel; harmless).
`N.BMP` is `va_NN.gf` for N = 1..21 (`11.BMP` = `va_11`, …), with the colour indices unchanged
(identity map apart from colour 8, the 00FF00 key colour, which only occurs under the window):

* **The PC-98 event CGs carry the message window baked in; the BMPs do not.** In `va_01`–`va_21`
  except `va_17` the rectangle x 37–602, y 303–390 holds a frame (border lines at the top, the
  first rows starting a few pixels further in: rounded corners) and a **50 % mesh**: on pixels
  with odd `x + y` colour 0 (99.9 %), on even ones the art (90 % equal to the BMP); `va_12` has
  the mesh in the other phase (even `x + y`); `va_17` and `va_22` have no window. The BMPs have the clean art
  there (19 982–27 123 pixels differ per picture, all inside the rectangle). This mesh is what the
  game shows as its translucent message window — it is part of the picture data, not drawn by the
  engine. `va_17` (no window) is identical to `17.BMP`; `12.BMP` equals `va_12` with the 576×88
  overlay `va_12e` at (32, 303) pasted on (299 pixels differ): `va_12e` is the window-less bottom
  of picture 12.
* **One local retouch** outside the window in 11 of the pictures: a single compact region of
  460–2 900 pixels (`1.BMP` (305,257)–(370,302), `3.BMP` (129,194)–(231,302), `19.BMP`
  (18,96)–(104,189), …; full list in `compare.txt`). Neither side is a mosaic (block-uniformity
  equal in both). *Inferred*: the shipped pictures were touched up in one detail each after the
  artwork used for the BMPs; what changed was not judged.
* **Palettes**: every BMP palette is exactly one of the 44 scenario palettes, scaled by 11h
  (files dated 1995-10-20 and `VA.BMP`) or by 10h (files dated 1994-11-18 … 1995-01-06, i.e.
  converted during development):

  | BMP | `.gf` | palette | BMP | `.gf` | palette | BMP | `.gf` | palette |
  |---|---|---|---|---|---|---|---|---|
  | 1 | va_01 | 4 | 8 | va_08 | 14 | 15 | va_15 | 22 |
  | 2 | va_02 | 6 | 9 | va_09 | 15 | 16 | va_16 | 23 |
  | 3 | va_03 | 8 | 10 | va_10 | 16 | 17 | va_17 | 24 |
  | 4 | va_04 | 10 | 11 | va_11 | 17 | 18 | va_18 | 26 |
  | 5 | va_05 | 11 | 12 | va_12(+e) | 18 | 19 | va_19 | 27 |
  | 6 | va_06 | 12 | 13 | va_13 | 20 | 20 | va_20 | 28 = 29 |
  | 7 | va_07 | 13 | 14 | va_14 | 21 | 21 | va_21 | 28 = 29 |

  (1-based op 30 numbers; palettes 28 and 29 are equal.) This is an independent statement of
  which palette belongs to which CG — useful to check the scenario-based assignment
  (`gf.py gf_palettes`, which picks e.g. 5/44 for `va_01` because of flashes and fades).
* **`VA.BMP`** (1995-11-06) has no counterpart in `GDATA.LIB`: a new 640×400 picture in the grey
  ramp palette 3 (16 greys), 83 % white background. `va_22` has no BMP.
* The disk has no backgrounds (`va_bg*`), character sprites (`va_ch*`), title or staff pictures.

## 4. FM TOWNS

No data. What is known:

* The PC-98 (and X68000) credits: `プログラム PC-9801/FM-TOWNS 宮本 正城` — the PC-98 programmer
  also wrote the Towns version (*inferred*: the same C source, as for the X68000).
* Developers' notes (`開発.DOC`): `68、TOWNS版のゲームはＶirgin.Ａngelが最後かもしれません` (the
  X68000 and Towns versions may be the last for those machines); a reader question whether the
  games run on the **FM TOWNS Marty** (answer: a report says ワンダラーズ ran with the "アプリ実行セット",
  not guaranteed).
* `ANNOUNCE.TXT`: the next product, the CG collection 「ＥXCELLENT」, for PC-9801, X68000 and FM TOWNS.
* The Graphic Disk's FM TOWNS viewer (§3) shows the Towns was a target platform for the CGs.

## 5. What a PC-98-faithful port can use

* **The X68000 build as a second witness for the engine**: same C program, different compiler and
  CPU. Where a PC-98 routine is unclear, the 68000 code (flat 32-bit, no segment juggling) is
  often easier to read, with the platform-specific parts (§2.4) set aside. The timer, palette,
  buffer, save and VM semantics agree.
* Behaviour to take from PC-98, not X68000: the 1Ch fade length (t, not t/2), effect 33, the
  mouse question, the music-mode help line, the PC-98 credits; timing is equal anyway.
* The corrected message 5 of the X68000 `CMD00.TXB` is the only text fix (a port may offer it).
* The Graphic Disk BMPs give **clean versions of 21 CGs** (no window mesh) and confirm the
  intended palette of each; they are not needed to reproduce the game (the mesh *is* the game's
  look) but are the best source for any gallery/CG-mode feature and for checking the `.gf`
  decoder's colours. The retouched details mean they are not a drop-in replacement.

## 6. Open questions

* `_CRTMOD` 19h selected by HELP at start: which IOCS extension and monitor it is for.
* The exact role of `PMD.X` fn 2 with D1 = 1 at song start and of the work+23h formula (needs an
  emulation of `PMD.X`); whether the X68000 fade sounds like the PC-98 one apart from its length.
* The X68000 effect routines (t0538A, t0544C, t05516, t055D8, t0568E) were not compared with the
  PC-98 ones step by step (timing per step, order of lines).
* What the eleven retouched regions change, and the subject of `VA.BMP`.
* The FM TOWNS executable (not available).
