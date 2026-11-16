# Platform layer: start-up, timing, input, built-in sequences

What `M.EXE` needs from the PC-98 and how it uses it, apart from graphics
([graphics.md](graphics.md)), text rendering ([text.md](text.md)) and sound
([sound.md](sound.md)); and the six built-in sequences that statement 25h calls
([scenario-format.md](scenario-format.md) §8). Addresses are `SEG:OFF` of the unpacked `M.EXE`.
**Verified** = read in the code (and, where noted, run under `re-tools/mcall.py`).

## 1. The release and its boot

The two 5.25" 2HD disks are MS-DOS volumes (1 232 KB, 1024-byte sectors). Disk A is bootable
(`IO.SYS`, `MSDOS.SYS`, `COMMAND.COM` of NEC MS-DOS 3.3, Epson boot sector) and holds the program,
scenario, text, drivers and songs; disk B holds only `GDATA.LIB`. The disks in the dump are an
*installed* pair: the shop master disk carried `DISKA.LZH`/`DISKB.LZH`, which `INSTALL.BAT`
unpacks with `LHE.COM` onto two blank disks. (`docs/game-data.md` lists every file.)

`AUTOEXEC.BAT` runs `GAME.BAT` (`HDGAME.BAT` is the same for a hard disk, `m cmd00.scb
gdata.lib`), which:

1. prints the title, loads the mouse driver `MSZ.COM` (MSZ 1.03, ZOBplus 1990: INT 33h);
2. runs `ONGCHK.COM` (exit code = detected board: none, 26K, FM×6 without PCM, 86, Speak
   Board, Chibi-oto) and prints it;
3. asks for a sound setup 0–4 with `KIN.COM` (30 bytes: INT 18h AH=03h keyboard reset, AH=00h
   read a key; the digit becomes the exit code; anything but 0–9 is asked again);
4. loads the matching drivers (PMD / PMD86 / PMDB2, PPSDRV + PDR, P86DRV + CNVLOAD, PMDPCM;
   details in [sound.md](sound.md)) — option 4 loads none;
5. runs `m cmd00.scb b:¥gdata.lib`; on return prints `異常終了しました…` (the program never
   returns normally: statement 2Eh exits to DOS after shutdown, which then also reaches this
   line) and removes the resident drivers.

Requirements of `M.EXE` itself (verified from the code): a PC-9801 with 640×400 graphics, two
graphics pages and the 16-colour analog palette, the GRCG, the kanji ROM through the CRT BIOS
(INT 18h AH=14h), the VSYNC interrupt (IRQ 2), the keyboard interrupt (IRQ 1); optionally an
INT 33h mouse driver and PMD. The code uses the 80186 instruction subset (`enter`/`leave`,
`pusha`, immediate shifts and pushes) and no protected-mode instructions, so it runs on a V30
(GAME.BAT's option 0 mentions "v30マシン用"). Load size: 53 792-byte image + 1 607 paragraphs
minimum allocation; pictures are buffered in memory allocated at run time
([graphics.md](graphics.md)). `GAME.BAT` quotes 390–530 KB of free memory depending on the
drivers.

## 2. Timing (segments 0752/075A)

Everything in the game is timed by the **VSYNC interrupt** — there is no use of the 8253 timer or
the CPU speed, except in loops that simply poll the frame counter.

* **Install** (`075A:000E`, called through `0752:0002` by `run_game`): clears 16 timer slots,
  saves vector 0Ah (`_dos_getvect`), installs the handler `075A:00A6`, remembers whether IRQ 2
  was masked (port 02h bit 2), unmasks it, writes port 64h (arm the VSYNC interrupt), and hooks **INT 18h** (`05C3:000A`):
  the hook (`05C3:004A`) calls the BIOS and then unmasks IRQ 2 again and re-arms port 64h, so
  the CRT-BIOS calls the game makes for every kanji glyph (AH=14h) cannot leave the VSYNC
  interrupt off.
* **Handler** (`075A:00A6`, every vertical retrace): `frame_counter += 1` (word DS:109E); for each
  slot in use and not done: `elapsed += 1` (32-bit), done when `elapsed ≥ target`; EOI (port 00h
  ← 20h), re-arm (port 64h ← 1), then chains to the previous vector 0Ah.
* **Timer slots** (16 × 16 bytes at 0B91:0000: in-use, done, elapsed, target, the requested
  time): `timer_start(t)` (`0752:0026` → `075A:011E`) takes the first free slot and sets
  `target = t × 564 / 1000` (32-bit, truncating) — `t` is in hundredths of a second and the
  program assumes 56.4 frames per second, the 400-line VSYNC rate (≈56.42 Hz); returns slot+1,
  or 0 when all 16 are busy (then waits that use it end at once). `timer_done(h)` (`0752:0076`),
  `timer_free(h)` (`0752:0043`), `timer_elapsed(h)` (`0752:005C`: elapsed time counting up, `elapsed × 1000 / 564`, or the
  requested time once done).
* **Remove** (`075A:0080`): restores INT 18h (`05C3:0030`), the IRQ 2 mask bit and vector 0Ah.

So a wait of `t` in a statement lasts `floor(t × 564 / 1000)` frames, at least 1 (the first VSYNC
after the start completes a zero target); at 56.42 Hz that is `t/100 × 1.0004` s. Built-in
sequences also count frames directly by zeroing DS:109E and polling it. **Verified.**

## 3. Input (segments 043A/0401)

### 3.1 Devices

`input_init` (`043A:0008`, from `run_game`) opens each device enabled in the mask DS:0110
(initially FFFFh) and records the ones that work in DS:0112:

| Bit | Device | Open / close | Read |
|---|---|---|---|
| 1 | keyboard | `0401:030A`: hooks INT 05h, 06h and 09h / `0401:0312` restores them | `0401:0317` |
| 2 | mouse (INT 33h) | `0401:001A` / `0401:0082` | `0401:008A` |
| 4 | joystick | `0401:0004`: always fails (a stub) | `0401:0008`: zeros |

The mouse bit is decided by `sys_init` (`0504:0004`, built-in 0 `INIT`), before the graphics
start, on the DOS console: it prints `マウスを使用しますか?[Y/N]` (DOS AH=09h) and reads keys
through the keyboard BIOS (`0504:0B7E`: INT 18h AH=03h, initialise, then AH=00h, the next key's
character code; no echo) until one of `Y`, `y`, `ﾝ` (DDh, the Y key in kana mode) — mouse on — or
`N`, `n`, `ﾐ` (D0h) — mouse off; prints `マウスを使用します` / `マウスを使用しません` and
`プログラムのロード中です...`. If the mouse driver is missing, opening fails (INT 33h AX=0 returns
0) and the mouse simply stays off. If no device opens at all, `input_init` fails and the program
exits (`入力系の初期化に失敗しました`).

### 3.2 Keyboard

The game **replaces** INT 09h (keyboard, IRQ 1) with `0401:0228` and does not chain to the BIOS:
the BIOS key buffer is not fed while the game runs. The handler reads the scan code from the
8251 (port 41h), keeps `code & 7Fh` (DS:00FE) and sets the "new key" flag DS:00FF to the result
of `neg al; rol al,1; and al,1`, then sends EOI. For a make code 01h–7Fh that is 1; for a break
code 81h–FFh it is 0 — but for **ESC** (scan code 00h) the make code gives 0 and the break code
80h gives 1: **ESC registers when it is released**, all other keys when pressed. The handler
keeps only the last code; no buffering. INT 05h and 06h (the BIOS's COPY and STOP key
interrupts) are pointed at `0401:0258`, which prints `(^-^)` through DOS AH=09h; with the BIOS
keyboard handler out of the way they are not raised (inferred).

`kbd_read` (`0401:0317`) returns `{event, code}` and clears the flag: `event` = the flag;
`code` = 100h ESC (scan 00h), 101h RETURN (1Ch), 102h SPACE (34h), 103h UP (3Ah), 104h LEFT
(3Bh), 105h RIGHT (3Ch), 106h DOWN (3Dh), else 0. Any key therefore produces an event; only
these seven have a code. (The ten-key pad, function keys, Ctrl etc. are "some key".)

### 3.3 Mouse

Through INT 33h (`int86(33h)` at `0886:062C`, registers in DS:172E): open = AX=0 (reset; fails if
AX returns 0), then the pointer is hidden (state DS:00F6 = 0), then AX=00FDh with BX=1 and
AX=00FFh with BX=0Fh — MSZ-specific functions, not part of the Microsoft API (not traced in
MSZ). Read = AX=3: position CX, DX and buttons BX (bit 0 left, bit 1 right). `mouse_read`
returns `{x, y, right = bit1, left = bit0, 0}`; the coordinates are the driver's (the game sets
no range; the 640×400 default of a PC-98 driver, inferred). The pointer is shown with AX=1 and
hidden with AX=2 (`0401:00F6`), only when its state changes, and not at all while it is
**locked** (DS:00F8 = 1): `mouse_lock(lock, show)` (`0401:0154`; statement 37h, the built-ins)
sets the lock and, when locking, applies `show`. `043A:0295` / `043A:02A5` show / hide the
pointer unless locked (menus and the music mode).

### 3.4 Polling and the "release" step

`input_poll(p)` (`043A:01DA`) fills a 26-byte record — for each open device the reading plus a
"changed since the previous poll" word — and returns 1 if any device is open. Callers decide
from the fields; the common rule (statements 15h, 16h, the built-ins) is: **a key event, or the
left or right mouse button held down** counts as "input". Mouse buttons are levels, not edges:
holding a button down keeps satisfying a wait.

After accepting input the callers run `input_release(mask)` (`043A:0236`) for the device that
fired: keyboard (1) — read again while there is a new key event (drains a pending event; it does
not wait for the key to be let go, as releases set no event); mouse (2) — read again while the
left button is down: it **waits for the left button to be let go** (the right button is not
waited for); joystick (4) — while its fields are non-zero. (An earlier version of this section
had the mouse's step end on a still mouse; the loop at 043A:025E tests only the left button,
and `tests/check_input.py` runs it.) A poll of the mouse (`0401:008A`) first shows the pointer
when it is hidden, unless it is locked.

## 4. Shutdown

The `atexit` handlers registered by `run_game` run in reverse order: graphics (`0315:005F`),
input (`043A:0066`: restore INT 05h/06h/09h, hide the pointer), sound (`04E4:0021`), timer
(`0752:0019` → `075A:0080`). Exit codes: 0 after statement 2Eh; 1 usage/graphics failure;
2 scenario or text load error; 3 out of memory while loading; 4 run-time error of the
interpreter (bad opcode, bad expression, call stack, timer/input init); 255 a run-time error of
the C library (R6003, an integer divide error, from statements 1Eh–23h, op 2Fh), which ends
with `_exit`: the atexit handlers do not run and the game's interrupt handlers stay installed.
The interpreter's messages (`Calling nested too much`, `No Calling stack (Invalid RETURN)`) are
printed with `printf` while the text screen is off: they are seen once the program has left.

## 5. Built-in sequences (segment 0504)

Called by statement 25h n, which clears the result flag (byte 0BA1:0000) first and copies it to
v1 afterwards; a sequence sets the flag to 1 when the player skips it. Each one locks the mouse
pointer hidden (`mouse_lock(1, 0)`) on entry and unlocks it (`mouse_lock(0, 0)`) on exit
(OPENING, ENDING, ENDING2). "Input" below is the §3.4 rule, polled without waiting
(`0504:039C`); its release step follows.

### 5.1 INIT (0) — `0504:0004`

The console mouse prompt of §3.1, called by `main` before loading. Not used by the scenario.

### 5.2 OPENING (1) — `0504:0295`, scenario statement 1771

The prologue: four pages of centred text on a black screen; the scenario then shows the title
(script-catalog.md).

* Page table 0ABB:0416: rows of `{row word, far string}`; a NULL string ends a page; a row of −1
  after it ends the table. 4 pages of 6, 7, 4 and 5 lines (the texts are in 0ABB and DGROUP:
  `西暦２０８０年代、日本の首都トーキョウは、…` … `設立するに至った………。`).
* Per page: the text area (32, 59)–(607, 342) is filled with colour 0 (`05C3:0753`, a GRCG
  fill: x and width in 16-pixel words, y and height in lines) and the palette at 0ABB:0566 (set with `0315:0144`,
  [graphics.md](graphics.md)); then each line: x (in 8-pixel columns) `= 40 − len/2` (truncating) where
  `len` is the line's length in bytes, i.e. centred; y (in 16-pixel text rows) `= (row + 3) × 2`,
  i.e. pixel line `96 + 32 × row`. Each full-width character is drawn by `05C3:02F9`: the
  kanji-ROM glyph (INT 18h AH=14h) emboldened by OR-ing it with itself shifted one pixel left,
  revealed **left to right in 16 column steps** into planes 1 and 2 (colour 6) — the callback
  `0504:02C8`, run after each step, waits for a VSYNC on every second step (a global step
  counter DS:04CA decides the parity), so a character takes about 8 frames; the callback also polls input and sets the skip flag. Half-width bytes are
  skipped (the texts have none).
* After a page: a 3-second timer (`timer_start(300)`), ended early by input (→ skip). Then, if
  another page follows, colour 6 is faded out (`0504:030E`): 16 frames, each decrementing that
  entry's three components by 1 while above 0, set each frame with `0315:0144`.
* Skip: input at any time sets the flag and returns at once (the screen is left as is).
* On normal or skipped exit: `0315:04E2(0, 100)` (fade to black in 1 s, = op 1Ah) and
  `screen_clear` (`0315:0132`: both VRAM pages cleared by `vram_clear` `00DD:00E3`, the
  window's background zeroed).

### 5.3 ENDING (2) and ENDING2 (5) — `0504:0568`, `0504:05CA`; statements 1939, 1920

The same staff roll with different palettes:

1. Palette fade (`0504:0632`): a working palette (0ABB:0596 for ENDING, 0ABB:0626 for ENDING2)
   is moved towards a target (0ABB:05C6 / 0ABB:0656) in 16 steps; each step decrements every
   component that differs from the target by 1, sets the working palette, then waits 3 VSYNCs
   (48 frames in all). The fade only decrements.
2. every colour-15 pixel on the screen becomes colour 8 (`05C3:0588`: planes 0–2 cleared where
   all four planes are set), then the roll palette 0ABB:05F6 (ENDING) / 0686 (ENDING2).
3. The roll (`0504:06FA`): the area 512×130 at (128, 256) of the screen is saved, and for each
   page of 4 lines from the list 0ABB:04B2 (far string pointers, NULL = end; 11 pages:
   スタッフ, 企画・プロデュース 鈴木 憲一 (CRYSTAL SOFT), シナリオ 飯縄 誠, キャラクターデザイン
   中村 錦, プログラム PC-9801/FM-TOWNS 宮本 正城, 原画 中村 錦, ＣＧ ＰＲＯＰＥＲ, 作曲／編曲 柴田
   泉, Special Thanks to MusicDriver Ｐ．Ｍ．Ｄ． 梶原 正裕, Special Thanks to LZH Extract
   Utility ＬＨＥ ＴＥＡ, Copyright(c) 1995 CRYSTAL SOFT) the lines are drawn on graphics page
   1 at double size (full-width: `05C3:03A9`; half-width: `05C3:04DB` with the callback
   `0504:0B52`; x = 2 × byte index, line y = 0, 2, 4, 6 — double size inferred from the
   advance; [text.md](text.md)), composed with `05C3:05E2`, and shown
   with the rectangle copies of statement 32h (`0315:07CB`, operand records in DGROUP 04CCh–
   0526h): background → work buffer (effect 10), page → screen area with **effect 31**; it stays
   until 360 frames (6.4 s) after the page started, is replaced by the saved background with
   effect 31, then 120 frames (2.1 s) pass before the next page. The staff roll cannot be
   skipped (no input is polled).
4. `0315:04E2(0, 100)` (fade to black in 1 s), `screen_clear`.

### 5.4 ANNOUNCE (3) — `0504:0114`, statement 2007

Shows the text file `announce.txt` (Crystal Soft's notice: anti-piracy, coming titles,
support BBS): `0315:04E2(0, 1)` (fade to black in 0.01 s) and `screen_clear` (`0315:0132`) clear the screen; the file is read with
`fgets` (≤ 83 bytes per line) and each line drawn on text row 0..22 with `0504:007C` (80 columns:
kanji through `05C3:00CD`, half-width bytes with the embedded font; attribute E1h). A line
starting with `#p` ends the page, as does the 23rd line; `#e` ends the file. At a page end
the standard palette 0AA8:0030 faded in over 0.01 s (`pal_fade_in`, `0315:031E`), the prompt `マウスのボタンかキーを押して下さい` on row 23, a wait for
input (`0504:0257`), a fade to black and `screen_clear`. A missing file shows
`お知らせ用ファイルが見つかりません` and returns at once. Details of the 80-column text output:
[text.md](text.md).

### 5.5 MUSMODE (4) — `0504:088E`, statement 2001

The music mode. `0315:000E` (graphics re-initialisation) before and after.

* If the sound layer reports no driver (`04E4:0004` ≠ 1), the mode remembers that (DS:0682 = 2)
  and returns at once, now and on later calls.
* The song list is the table 0ABB:0728: 8-byte rows `{far file name, far title}`, NULL-ended —
  18 songs (タイトル va_m19, ムラクモ m03, ユキ m06, シノブ m07, レイコ m13, ササメ m04, 捜査 m05,
  交渉 m15, 戦闘 m10, 病院１ m09, 病院２ m12, えっち１ m11, えっち２ m02, オープニング１ m01,
  オープニング２ m18, エンディング１ m14, エンディング２ m16, スタッフロール m17; m08, m20 and
  m21 are not listed).
* Screen (80-column text via `0504:007C`): heading `★ ☆ ★  ミュージックモード  ★ ☆ ★` at column
  21, row 0; the titles at column 20, rows 3.. (attribute E5h for the selected one, E1h for the
  others; only the two changed rows are redrawn when the selection moves); help line
  `選択：カーソル上下   演奏：スペースキー又はリターンキー   終了：ＥＳＣキー` at column 3, row 24.
* Keys: UP / DOWN move the selection (no wrap); RETURN or SPACE plays the selected song; ESC
  (on release, §3.2) leaves; LEFT/RIGHT do nothing. Mouse: whenever the reading changes, the
  row under the pointer becomes the selection (row k for 48 + 16k < y < 64 + 16k; elsewhere it
  stays); the left button then plays it, the right button leaves.
* Playing: if a song was started in this visit, `04E4:00F0(150)` first, then
  `04E4:0034(file, 100)` ([sound.md](sound.md)). Leaving: `04E4:00F0(150)` if a song was played.
