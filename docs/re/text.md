# Text: the message file, the message window, menus and built-in texts

Everything the player reads in *Virgin Angel* is drawn by `M.EXE` into **graphics** VRAM with
glyphs from the PC-98 kanji ROM (read through the CRT BIOS) and an 8×16 font embedded in the
program. Scenario text lives in `CMD00.TXB` (213 messages, §2) and is shown by statement 19h in
a four-line window at the bottom of the screen (§3); the menu choices of statement 24h come from
the scenario's menu table and use the same window (§4). A few texts are built into `M.EXE` or
read from `ANNOUNCE.TXT` and drawn by the built-in sequences (§5; their flow and timing are in
[platform.md](platform.md) §5).

Conventions as in [scenario-format.md](scenario-format.md): addresses are `SEG:OFF` of the
unpacked `M.EXE` (image-relative segments), `DS:xxxx` = DGROUP 0BAFh. **Verified** = checked
against the original code, either by running it under `re-tools/mcall.py` (named where it was) or
by reading it; **inferred** = PC-98 hardware/BIOS meaning or intent not proven by the binary.
Names are in `docs/re/listing/m-names-text.tsv`; an annotated listing of every routine named
here is `resources/derived/listing/text.asm`. Game text is quoted only to identify things.

## 1. Function map

| Address | Name | Role |
|---|---|---|
| 0724:0018 | `txb_load` | open the text file, build the message index (§2.2) |
| 0724:0006 | `txb_getc` | `~fgetc(file)` |
| 0724:0119 | `txb_index_msg` | one index record: offset and length of the next message |
| 0724:0186 | `txb_read_msg` | read one message (length + 10 bytes) into the 2000h buffer |
| 0724:0206 | `txb_line` | expand one line (dictionary), at most N output bytes (§2.4) |
| 001E:0965 | `op_19` | statement 19h: clear the skip flag, `msg_show`, v1 := skip flag |
| 0315:07FC | `msg_show` | the page loop (§3.4) |
| 0315:0BD6 / 0B7C | `msg_wait_key` / `msg_poll` | page wait with blinking icon / input test (§3.5) |
| 0315:0EAD | `msg_icon` | draw (1) / erase (0) the page-wait icon |
| 02BE:015F | `win_line` | draw one string into the window work buffer (§3.3) |
| 02BE:00AC / 00CC / 00BC / 009C | `win_snapshot` / `win_clear` / `win_show` / `win_restore_screen` | window buffers (§3.1) |
| 02EC:0006 / 00B1 | `win_kanji` / `win_ank` | glyph into the work buffer: bold, shadowed (§3.2) |
| 02EC:0154 | `win_blit_raw` | VRAM ↔ window buffer (68×80 bytes × 4 planes) |
| 001E:0A8D | `op_24` | statement 24h: menu (§4) |
| 0315:0C4F / 0CC9 / 001E:0B2B | `menu_draw` / `menu_update` / `menu_loop` | menu drawing and selection |
| 02BE:020E / 0263 | `menu_choice` / `rect_invert` | one choice + its hit rectangle / inverted bar |
| 0A96:0002 | `sjis_to_jis` | Shift-JIS → JIS X 0208 for the kanji ROM |
| 0504:0B52 | `ank_glyph` | 16 bytes of the embedded 8×16 font (§3.2) |
| 05C3:00CD / 01E9 | `vram_kanji` / `vram_ank` | direct-to-VRAM glyphs for the built-ins (§5.1) |
| 05C3:02F9 / 03A9 / 04DB / 05E2 | prologue wipe / double-size kanji / double-size ANK / outline | §5.3, §5.4 |
| 0504:007C | `bi_text_line` | 80-column text line for ANNOUNCE and the music mode (§5.1) |

## 2. `CMD00.TXB` ("CRTX")

### 2.1 Container (**verified**)

```
0   "CRTX"                 plain
4   body                   every byte stored inverted: b_file = b ^ FFh
```

There is no header beyond the magic, no index and no length field. The decoded body is the 213
messages one after another, each **terminated by 1Ah**. The file is not compressed in the
LZ sense: the only space saving is a one-byte code for 90 frequent full-width characters (§2.4).
Inverted it reads as Shift-JIS mixed with stray half-width kana and capital letters, which is
what made it look compressed.

### 2.2 Loading and the index (**verified**, `txb_load` run under mcall)

`txb_load` (called by `main` after `scb_load`, [scenario-format.md](scenario-format.md) §1):

1. `fopen(name, "rb")`, name = SCB section 0Ah (`cmd00.txb`, 0BA1:0016); FILE* in DS:1092.
2. The four bytes must be `C R T X` (read with plain `fgetc`).
3. The message count is SCB section **tag 7** (0BA1:0052 = 213); it must be 0..1000.
4. An array of count + 1 far pointers is allocated (0BA1:003E); entry 0 is NULL, the scenario's
   message numbers are 1-based.
5. For message i = 1..count: an 8-byte record is allocated, `{u32 offset = ftell(), u16 length}`;
   length = number of bytes up to **and including** the next 1Ah, read through `txb_getc`
   (`~fgetc`). The length must be 1..1FFFh. Any failure returns 0 (`main`: `error!`, exit 2).

Statement 19h n uses entry n (the scenario loader checks `0 ≤ n ≤ count`; n = 0 would be a
NULL record). `txb_read_msg` allocates a 2000h-byte buffer once (DS:108E), seeks to the offset
and reads **length + 10** decoded bytes into it — the message, its 1Ah and ten bytes of the next
message (or `EOF` = FFh after the last one). Nothing is zero-terminated; the buffer is reused.

### 2.3 Messages, lines and control codes (**verified**)

A message is a sequence of **lines**, each terminated by 00h; the last "line" is the 1Ah. A
control code is recognised only as the **first byte** of a line (`msg_show`, jump table
0315:087C for 10h..1Ah):

| Code | Count | Meaning |
|---|---|---|
| 12h | 1 565 | end of page: show it and **wait for the player** (§3.5); wait mode := key |
| 13h | 375 | speaker: the rest of the line is the speaker's name; following lines are speech (§3.4) |
| 14h | 72 | end of page: show it and **wait a time** (§3.5); wait mode := timed. Quirk §3.4 |
| 1Ah | 213 | end of message |
| 10h, 11h | 0 | the byte is dropped and the rest of the line is ordinary text |
| 00h–0Fh, 15h–19h | — | not codes: the line is text (an empty line, 00h, is a blank row; one line starts with 09h, drawn as a blank cell) |

Inside speech the two ASCII bytes `\e` at the **end** of a line close the speech (§3.4); 375
occurrences, one per 13h. Other ASCII in the text: `#`, `$`, `%` (20 / 78 / 20; the embedded font
draws them as the left end, middle and right end of a long horizontal bar, so `#$$$$%` is an
elongated "ー" spanning six half-width cells), spaces, one `!` and one `"`. Upper-case letters
cannot occur as such (they are dictionary codes), nor half-width kana.

Typical message: `text{n}text{n}{12}{n}{13}NAME{n}speech{n}speech\e{n}{12}{n}...{n}{1A}` (with
`{n}` = 00h). Names are padded with full-width spaces to 4 characters by the scenario writer.

### 2.4 Line coding (**verified**: `re-tools/txb_verify.py`)

`txb_line(msg, pos, out, max)` expands the line at buffer offset `pos` into `out`, stops at the
00h or when the output count reaches `max` (79 in `msg_show`, so a decoded line keeps at most 79
— 80 if the last code was a two-byte one — bytes; no line in the file is longer than 68), writes a
terminating 00h and returns the **source** length + 1 (the 00h included; the caller adds it to
`pos`):

| Byte (after inversion) | Output |
|---|---|
| 81h–9Fh, E0h–FCh (Shift-JIS lead, `_mbctype` DS:1155 bit 2) | the byte and the **next byte unchanged** (a trail byte is never a code) |
| A0h–DFh | the two bytes `DICT[b − A0h]` |
| 41h–5Ah (`A`–`Z`) | the two bytes `DICT[40h + b − 41h]` |
| anything else | the byte itself |

`DICT` is **90 two-byte Shift-JIS characters** (180 bytes) at **0B85:0000** of the image, i.e.
offset B850h of the load image of `M_unpacked.EXE` and offset **B852h** of the packed `M.EXE`.
They are ordered roughly by descending frequency: `、…のいに　て。たクっをる…` (A0h–DFh) and
`…ぁ一見言出ど` ending the 26 letter codes. The X68000 `M.X` holds the same table with every
two-byte pair swapped, at file offset C246h. `re-tools/txb.py` reads the table from the EXE.

66 351 of the 106 372 body bytes are dictionary codes; the expanded text is 163 019 bytes.

### 2.5 The SCB counts 7, 0Bh and 0Ch

* Tag 7 (213, 0BA1:0052) is the **number of messages** in the text file (§2.2): it sizes the
  index and bounds statement 19h. **Verified.**
* Tags 0Bh (199, 0BA1:00D4) and 0Ch (61, 0BA1:0004) are written by `scb_read_sections` and set to
  0 in `0468:0191`, and **never read** anywhere in `M.EXE` (every reference to the two words is
  one of those writes). **Verified.** What the compiler counted is unknown; it is none of: speaker
  blocks (375), page codes (1 565 / 72), distinct speaker names (18), messages used (211),
  pictures (54), jump/call targets (134 / 320 incl. switch cases), labels (93 × 2Bh). A port can
  ignore them.

### 2.6 Export

`re-tools/txb.py CMD00.TXB --tsv resources/derived/scenario/messages.tsv` writes one row per
message: index (1-based, = statement 19h operand), file offset of the message's first byte,
stored length (incl. 1Ah), text with lines joined by `{n}` and control bytes as `{XX}`
(`{12}`, `{13}`, `{14}`; the final `{1A}` line is implied). `txb.layout(msg)` models the page
loop of §3.4 and returns, per page, the rows handed to the line drawer, the wait mode and the
byte count that sets the timed wait.

### 2.7 PC-98 vs X68000 (**verified**: both files decode with the same code and table)

The X68000 `CMD00.TXB` is one byte shorter. At the decoded-text level the only change is one
typo fix in **message 5, line 81** (0-based; the 82nd line): PC-98 `…真似をしなかっかただけでも…`,
X68000 `…真似をしなかっただけでも…` — the dictionary byte for `か` at file offset **0F9Dh** (3997)
removed; everything after it is shifted by one byte. All other messages, the counts, line structure and control codes are identical.

## 3. The message window (statement 19h)

### 3.1 Buffers and geometry (**verified**; positions confirmed by rendering under mcall)

The window is a fixed **544 × 80** pixel area of VRAM at **(48, 307)–(591, 386)** (VRAM offset
5FF6h = 307 × 80 + 6, 68 bytes × 80 lines). `win_alloc` (02BE:0006, from `gfx_init`) allocates two
off-screen copies, each 4 planes × 1540h bytes (68 bytes × 80 lines, stride 68):

* **save buffer** (0BA1:0074): the window area as it is on screen without text. `win_snapshot`
  (02BE:00AC) copies VRAM → save; it runs after **every rectangle copy to the screen** (statement
  32h, `0315:07CB`), so the text background is whatever the last screen update put there.
  `win_zero` (02BE:0118) zeroes it when the screen is cleared (`0315:0132`).
* **work buffer** (0BA1:0054): the page being composed. `win_clear` copies save → work;
  `win_show` copies work → VRAM (the whole page appears at once); `win_restore_screen` copies
  save → VRAM (erases the text). Statement 18h (`0315:07F5`) is exactly `win_restore_screen`:
  it erases the text window.

The scenario puts the window frame on screen as a picture: `va_mw01` (576 × 94, drawn at
(32, 300) with colour 8 transparent, [graphics.md](graphics.md)) is a rounded frame in colour 3
whose interior is a checkerboard of colour 0 and colour 8 — a 50 % black screen door over the
picture behind it; the text area sits 16 px inside the frame's left and right edges and 7 px below
its top. `va_mw02` (640 × 400: the same frame in a screen otherwise of colour 14) is drawn straight to the
screen by statements 682, 1391, 1555 and 1577 (its use: [graphics.md](graphics.md)). The engine
itself draws no frame.

Text cell coordinates: row r = 0..3, column c = 0..67 (half-width cells):

```
x = 48 + 8·c          y = 309 + 20·r        (glyph 16 px high, rows 20 px apart)
work-buffer offset = r·550h + c + 88h       (88h = 2 lines top margin)
```

A full-width character takes two columns: **34 full-width characters per row, 4 rows**.

### 3.2 Glyphs: kanji ROM, embedded font, bold and shadow (**verified**)

* **Full-width** (Shift-JIS lead byte): `sjis_to_jis`, then **INT 18h AH=14h** (CRT BIOS: read
  the kanji-generator pattern, DX = JIS code, BX:CX = 34-byte buffer: 2 size bytes, then 16 rows
  of left byte, right byte). `win_line` issues INT 18h **AX=1B01h** before each string (KCG
  access mode; inferred meaning). `M.EXE` never touches the kanji ROM ports (A1h/A3h/A5h/A9h): every glyph comes through INT 18h.
* **Half-width** (any other byte): the embedded font — `ank_glyph(ch, dst)` copies 16 bytes
  through the far-pointer table **0ABB:07C0** (256 entries). The glyphs lie in DGROUP 0684h–1083h;
  159 codes have one (01h, 02h, 21h–7Eh, A1h–DFh), all others point at the blank glyph at DS:0684
  (so 00h, 20h and control bytes draw nothing but take a cell). The font is the developers' own:
  digits and letters differ from the ROM's ANK, `#`/`$`/`%` are the long-bar pieces (§2.3) and
  `&` / `'` (26h/27h) together form the return-key arrow ↵ of the page-wait icon.

Every glyph row g (16 bits for full-width, 8 for half-width; MSB = leftmost pixel) is
**emboldened by one pixel to the left**, then written with a black edge above and below:

```
b[r]      = g[r] | (g[r] << 1)                 r = 0..15, b[-1] = b[16] = 0
plane p:  dst[r] = (dst[r] & ~b[r-1] & ~b[r+1]) | b[r]       (same for all 4 planes)
```

i.e. glyph pixels become colour **15**, pixels directly above or below a glyph pixel (within the
16-line cell) become colour **0**, everything else keeps the background. There is no left/right
shadow. This is the "easier to read" text of the developer notes: bold white with a black
vertical outline over the dithered window. Rendering under mcall with the real kanji patterns
matches this pixel for pixel (e.g. the stroke of `午` at ROM column 4 covers screen columns 3–4).

### 3.3 The line drawer `win_line(str, row, col)` (02BE:015F, **verified**)

Hides the mouse pointer, AX=1B01h INT 18h; returns 0 at once if row > 3 (or < 0) or col > 43h.
Then for each byte until 00h: a lead byte draws the full-width glyph of the two bytes at col and
advances col by 2; any other byte draws the half-width glyph and advances by 1; the loop stops
as soon as col > 43h (67). A full-width glyph started at column 66 still fits; one that would
start at 67 is drawn across the buffer's row end (no case in the data). There is **no line
breaking and no kinsoku**: the scenario's lines are pre-broken; anything beyond column 67 is
dropped. Three rows in the game exceed 68 bytes after the speaker prefix (§3.4) and lose their
closing `」` (messages 140, 144, 185; confirmed by rendering message 140). The pointer is shown
again at the end.

### 3.4 The page loop `msg_show(record)` (0315:07FC, **verified**: `txb_verify.py` phase 2)

State: `dlg` (in speech), `first` (name prefix not yet used), `name`, `nlen`, `mode`
(0 key / 1 timed; starts at 0 for each message and persists across pages), `end`.

```
win_clear; txb_read_msg; pos = 0
repeat:                                   ; one page
    row = shown = nbytes = 0
    while row < 4:
        line = txb_line(pos, max 79); pos += source length + 1
        c = line[0]
        12h: row = 4; first = 0; mode = 0;            continue (nothing drawn)
        13h: name = line[1:]; nlen = strlen(name)/2 + 1; first = 0; dlg = 1; continue
        1Ah: row = 4; end = 1;                         continue
        14h: row = 4; first = 0; mode = 1; line = line[1:]   ; and FALL THROUGH (quirk)
        10h,11h: line = line[1:]                       ; fall through
        text:
          if dlg:
              if not first: s = name + "「" + line; first = 1
              else:         s = "　" × nlen + line     ; full-width spaces
              if s ends with "\e": replace those 2 bytes by "」"; dlg = 0
          else: s = line
          if s != "": win_line(s, row, 0)            ; refused if row > 3
          row++; shown++; nbytes += strlen(s)
    if shown == 0: (nothing to show) continue unless end
    win_show; win_clear
    wait: mode 0 → msg_wait_key; mode 1 → timed wait (§3.5)
until end
win_restore_screen; mouse_lock(0, 0)
```

Consequences a renderer must reproduce:

* **Paging**: a page is at most 4 rows; 12h/14h end it early; four text lines end it too (and
  then the *current* mode applies — after a 14h, full pages keep auto-advancing until a 12h).
* **Speech layout**: the first line after 13h is `NAME「text`; continuation lines are indented
  by `nlen = bytes/2 + 1` full-width spaces, i.e. they start under the first character after
  `「` (names are 4 full-width characters, so 5 spaces); a line ending in `\e` gets `」` instead
  and ends the speech. `\e` elsewhere in a line is left as is (does not occur). After a 12h
  inside speech the next page starts with `NAME「` again.
* **The 14h quirk**: 14h does not skip the line like 12h but runs the text path with the rest
  of the line (empty) as **row 4**: `win_line` refuses it, yet the row counts as shown, so a
  14h directly after a full page or at the start of a message produces a page **with nothing new
  on it** that is still shown and timed (150 ms minimum); inside speech it consumes the name
  prefix (`NAME「` counted in `nbytes`, not drawn), so the next page continues **indented and
  without the name** (message 208 shows both cases).
* Empty lines are blank rows (they count as shown).

### 3.5 Waits, keys and skipping (**verified**, input details in [platform.md](platform.md) §3)

* **Key wait** (`msg_wait_key`): a blink loop with a timer of 80 ms (`timer_start(80)`): icon
  off (`msg_icon(0)` restores the cell from the work buffer), poll; 80 ms later icon on, and so
  on — a 160 ms period starting with the icon hidden. Continues when `msg_poll` reports input;
  then the icon is erased. If no timer is free the icon is drawn steadily and the poll blocks.
  The **icon** is `vram_ank` glyphs 26h and 27h in transparent mode (bold, OR-ed in colour 15,
  no shadow) at byte columns 72–73, y 369, i.e. the cell (576, 369)–(591, 384) = row 3, columns
  66–67 of the window (it can overlap the end of a long fourth row).
* **Input** (`msg_poll`): any **key** (a make code; ESC on release), or the **left** mouse button
  (held), or the joystick button (the joystick driver is a stub). The right button does not
  advance. After accepting, the device's release step runs. While polling without blocking the
  pointer is locked hidden (`mouse_lock(1, 0)`); `msg_show` unlocks it at the end.
* **Timed wait** (mode 1, code 14h): `t = max(150, nbytes × 100 / 12)` ms (integer division;
  `nbytes` includes speaker prefixes and indentation), i.e. ≈ 8.3 ms per byte, ≈ 16.7 ms per
  full-width character, converted to VSYNC frames as `t × 564 / 1000`. Skipped when nbytes < 1.
  **Input during a timed wait aborts the whole message**: the skip flag (byte 0BA1:0000) is set
  and `msg_show` returns at once (text erased). Statement 19h then sets **v1 := 1** (bool), else
  0; the scenario tests it to skip the rest of a sequence (e.g. statement 1786 after message 206).
  Timed pages occur only in messages 20 and 206–209.
* There is **no typewriter effect, no text speed setting, no fast-forward/skip-read mode and no
  backlog**: every page appears at once and waits.

### 3.6 Colours

Text pixels are palette index 15, the edge index 0, the icon index 15; the menu bar inverts
(§4.1). The actual colours are whatever the scenario's current palette assigns to 0 and 15
(statement 30h; [graphics.md](graphics.md)). The window background is the screen.

## 4. Menus (statement 24h)

### 4.1 Drawing (**verified**; geometry confirmed by rendering under mcall)

The operand is a 1-based index into the scenario's menu table (T44, 0BA1:0012; 43 menus of 1–4
plain Shift-JIS strings, not dictionary-coded; [scenario-format.md](scenario-format.md) §2.4).
`menu_draw` (0315:0C4F): `win_clear`, then choice i (0-based) is drawn with `win_line(str, row i,
col 0)` — same glyphs and clipping as messages — and gets the hit rectangle
**x 48–591, y 307 + 20·i … 326 + 20·i**; then `win_show`. There is no prompt, number or cursor
glyph: the current choice is marked by **inverting all four planes** of its rectangle in VRAM
(`rect_invert` → `05C3:005B`, colour c → 15 − c; 68 bytes × 20 lines), so the white text turns
black on an inverted background. Moving the selection inverts the old bar back and the new one.

### 4.2 Selection (`op_24`, `menu_loop`, `menu_update`; **verified**)

* **Initial cursor**: `op_24` remembers the operand pointer of the last menu statement
  executed (DS:00C0) and its result (DS:00C4). Executing **the same statement** again starts with
  the previous choice highlighted; any other menu starts with none — after one input poll (which
  may already place it under the mouse), the first choice is highlighted.
* **Mouse**: whenever the mouse reading changes and the pointer is inside a choice's rectangle,
  that choice becomes the selection (hover). The **left button** confirms the *current*
  selection wherever the pointer is.
* **Keyboard**: **UP / DOWN** move the selection with **wrap-around**; **RETURN** confirms. No
  other key does anything (no SPACE, no number keys, no ESC/cancel; LEFT/RIGHT ignored). Each key
  is followed by the keyboard release step.
* Joystick (stub): up/down bits move, a button bit confirms.
* **No cancel**: a menu always returns a choice. The right button is ignored.
* Result: v1 := choice (1-based, int; clamped to 1 if out of range), remembered in DS:00C4;
  the screen under the window is restored (`0315:0EA8` → `win_restore_screen`). The scenario
  then switches on v1 (statement 20h).

### 4.3 Title, save and load menus

They are ordinary statement-24h menus; their behaviour is the scenario's:

* **Title** (menu 43, statement 1991): 4 choices — start, continue, music mode, notice from
  Crystal Soft. The centring is done in the data with leading full-width spaces (13, 13, 12 and 8),
  drawn in the same window over `va_main` + `va_mw01`.
* **Save** (menu 41, after message 204): slots 1–3 or "don't save"; **load** (menu 42, after
  message 205 on failure): slots 1–3 or "back to the menu". The slot is passed in v1 to
  statements 1Dh/36h ([scenario-format.md](scenario-format.md)).

## 5. Built-in texts

The console strings (`マウスを使用しますか?[Y/N]`, `プログラムのロード中です...`, load errors) are
printed through DOS before graphics start ([platform.md](platform.md) §3.1). Everything else
below is drawn directly into VRAM (no window buffers).

### 5.1 Direct glyph routines (**verified**)

`vram_kanji(xbyte, y, sjis, mode)` (05C3:00CD) and `vram_ank(xbyte, y, ch, mode, glyph_fn)`
(05C3:01E9, the font callback is `ank_glyph`): same kanji ROM / embedded font and the same
one-pixel-left bold as §3.2, no shadow, VRAM offset `y·80 + xbyte`, written to all four planes:

| mode | Effect |
|---|---|
| 0 | inverse cell: `~b` written opaque (black glyph on white) |
| 1 | opaque cell: `b` written (white glyph on black) |
| 2 | transparent: `dst |= b` (white glyph, background kept) — the page icon |

`bi_text_line(col, row, str, attr)` (0504:007C) draws an 80-column line at x = 8·col,
**y = 16·row** (no line gap): lead byte → `vram_kanji` (2 columns), bytes > 20h → `vram_ank`,
bytes ≤ 20h (space) are skipped but take a column; at most 80 columns. `attr` E1h gives mode 1,
any other value (E5h) mode 0 (inverse). Used by ANNOUNCE and the music mode
([platform.md](platform.md) §5.4–5.5: the music mode list is at 0ABB:0728, heading at column 21
row 0, titles at column 20 rows 3.., help at column 3 row 24, the selection inverse).

### 5.2 `ANNOUNCE.TXT` (built-in 3, **verified**; rendered under mcall)

A plain Shift-JIS text file with CR LF line ends, read with `fgets(buf, 83, f)` in text mode
(so CR LF → LF; the last character of every line is then cut — the LF). Per line:

* `#p` in the first two columns: end of page; `#e`: end of file (the rest, e.g. the final 1Ah,
  is not read). Nothing else is interpreted (no colour or position codes).
* otherwise the line is drawn with `bi_text_line(0, row, line, E1h)` on row 0, 1, …; after row
  22 (the 23rd line) the page ends by itself.
* page end: the prompt `マウスのボタンかキーを押して下さい` (0ABB:0023) at column 0, row 23
  (y 368), wait for any key or mouse button, clear the screen, next page at row 0. At `#e`/EOF the
  same prompt (0ABB:0046) and wait. A missing file shows `お知らせ用ファイルが見つかりません`
  (0ABB:0000) at row 0.

The shipped file has 3 pages (2 blank lines at the top of each), lines up to 76 bytes.

### 5.3 Prologue (built-in 1)

Table 0ABB:0416 of `{s16 row, far string}` ([platform.md](platform.md) §5.2 for the pages and
their timing). Layout (**verified**, rendered): x byte = `40 − strlen/2` (centred on 80
columns), y = `96 + 32·row`; each **full-width** character drawn by `05C3:02F9`: ROM glyph, bold
(one pixel left), revealed in 16 steps of a growing left mask (8000h, C000h, … FFFFh: one more
pixel column per step) and written opaque into **planes 1 and 2 only** (R and G: colour 6 on the
black screen; palette 0ABB:0566 makes 6 white); no shadow. Half-width bytes are skipped (but
take a column).

### 5.4 Staff roll (built-ins 2 and 5)

List 0ABB:04B2 of 44 far string pointers (NULL-ended), 11 pages of 4 lines. Each line is drawn on
graphics page 1 at **double size**: full-width `05C3:03A9` = ROM glyph, bold, every pixel doubled
horizontally and every row doubled (32 × 32, 4 bytes wide); half-width `05C3:04DB` = 16 × 32;
x byte = 2 × (byte index in the string), so a half-width character is 16 px and a full-width
one 32 px wide; line k at pixel row 32·k + 1 of the page block (k = 0..3); colour 15 through the
GRCG (RMW, all tiles FFh). `05C3:05E2(0, 1, 40h, 80h)` then adds a black outline (the text
dilated by one pixel left, right, up and down, written in colour 0 where there is no text). The
block is copied to the screen by rectangle copies ([platform.md](platform.md) §5.3). Lines are
left-aligned; the centring is done with leading ASCII spaces in the data.

## 6. Verification and tools

* `re-tools/txb.py` (stdlib only): container, dictionary, line expansion, message split,
  `layout()` model of §3.4, TSV export.
* `re-tools/txb_verify.py [pc98|x68k]` runs the original code under mcall:
  phase 1 — `txb_load`, then for every message `txb_read_msg` and `txb_line` line by line with
  the arguments of `msg_show` (max 79): index records and all **5 732 lines bit-identical** to
  `txb.py` on both files; phase 2 — `msg_show` on every message (input poll patched to "pressed",
  no timer): the rows passed to `win_line`, the page boundaries, the wait mode and the byte count
  of **all 1 849 pages identical** to `txb.layout()` on both files.
* `re-tools/text_render.py [MSG [MENU]]` builds the first scene (`gfx_init`, op 31 `va_main` and
  `va_mw01`, palette 34), runs `msg_show` and `menu_draw` with the kanji ROM answered from
  a 16x16 XFNT font (`VA_KANJI_FONT`; stand-in pattern if missing) and writes screenshots to
  `resources/derived/text/` (game imagery, not for docs/). Used to confirm §3.1–§3.3 and §4.1
  geometry, the speech indentation, the clipped `」`, the icon position and the bar inversion;
  the ANNOUNCE and prologue layouts were rendered the same way with their waits patched out.

## 7. Open questions

* What the SCB counts 0Bh (199) and 0Ch (61) counted in the developers' compiler (unused at run
  time).
* INT 18h AX=1B01h before each window line: exact BIOS function (KCG access mode is the usual
  reading) — irrelevant to the output.
* The X68000 engine `M.X` was not analysed; only its text file and dictionary copy were compared.
