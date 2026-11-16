# Graphics: pictures, buffers, transitions, palettes

Everything *Virgin Angel* shows comes from 54 pictures in `GDATA.LIB`, drawn into three
640×400 16-colour buffers and moved to the screen with one of a few transition effects; colour is
set by 44 palettes stored in the scenario. This document specifies the archive, the `.gf`
picture format and its decoder, the buffers, the statements that draw (ops 31h, 32h, 33h, 18h)
and colour (ops 30h, 1Ah, 2Fh), the PC-98 hardware use and the screen layout, with a table of
all pictures. The message text drawn into the window is in [text.md](text.md); timing (the VSYNC
timer) and the built-in sequences are in [platform.md](platform.md).

Addresses are `SEG:OFF` of the unpacked `M.EXE`; labels: `docs/re/listing/m-names-gfx.tsv`,
listing `resources/derived/listing/gfx.asm`. Statement numbers are 1-based, as in
[scenario-format.md](scenario-format.md) (`pc98_scb.txt` index + 1); palette numbers **P** are
the 1-based op 30h operand (P = `scb.py` `pal[]` index + 1). **verified** = checked by running the
original code under `re-tools/mcall.py`, **code** = read in the code, **inferred** = deduced.

Tools: `re-tools/gf.py` (archive, decoder, PNG export, usage table), `re-tools/gfx_fx.py`
(op 32h model), `re-tools/gfx_pal.py` (palette model), with the checks `gf_verify.py`,
`gfx_fx_verify.py`, `pal_verify.py` and `ibm_bmp_compare.py` (§12). PNGs of all pictures:
`resources/derived/images/` (`gf.py png … --scb CMD00.SCB`).

## 1. Overview

| Buffer | What it is | Planes | Used for |
|---|---|---|---|
| 10 | VRAM page 0 — the **only page ever displayed** (A4h ← 0 once, at init) | A800h, B000h, B800h, E000h with A6h ← 0 | the screen |
| 11 | VRAM page 1 (never displayed) | same segments with A6h ← 1 | the room composite: frame `va_main` + background |
| 12 | four 32 000-byte blocks in main memory (`gfx_alloc` `00DD:0006`, segments at 0BA1:0046..004C) | same layout as VRAM | the composite of the next screen |

Each buffer is 640×400 pixels as four 1-bit planes (blue, red, green, intensity), 80 bytes per
line, bit 7 = leftmost pixel; colour number = b + 2r + 4g + 8i. **code**

A typical scene (statements 31–35): copy 11 → 12 (op 32h effect 10), load the characters into
12 with colour 8 transparent (op 31h flag 1), load the message window `va_mw01` into 12, copy
12 → 10 with a transition (effect 30 or 32). Event pictures are loaded straight into 10 or into
12 while the screen is faded out, then op 30h fades the palette in.

## 2. `GDATA.LIB` ("GA00" archive)

`lib_read_dir` `0855:000C`, `lib_read_entries` `0855:015F`, `lib_lookup` `0823:012A`. **verified**
(`gf.py` reads the same entries; the original's lookup finds all 54 under `gf_verify.py`).

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | `GA00` (checked, else `ID error;_;`) |
| 4 | 4 | 0 |
| 8 | 4 | count n = 54 (the engine reads the low word) |
| 12 | 4 | data base = 896 (ignored: the engine computes (n + 2) × 16, the same value) |
| 16 | 16 × (n + 1) | entries: name[8] NUL-padded, ext[3] (`gf`) + 1 unused byte, u32 offset from the data base |

The extra last entry has name `FF…FF` (checked, else `lastが変です`) and offset = size of the
data (968 545), so member i spans offset[i]..offset[i+1]. The lookup builds `name.ext` and
compares it **case-sensitively** with the requested name (op 31h appends `.gf`); the size field
of the result is always 0, the position is offset + base. The X68000 `GDATA.LIB` is
byte-identical.

## 3. The `.gf` picture

### 3.1 Header

`gf_header` `00DD:0403`. All 54 files: **verified**.

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | `GF0\0` (checked; otherwise nothing is drawn) |
| 4 | 2 | width w (a multiple of 8 in all files) |
| 6 | 2 | height h |
| 8 | 2 | x (used when op 31h's x is −1; replaced by 0 if outside 0..639) |
| 10 | 2 | y (likewise, 0..399) |
| 12 | … | compressed stream, to the end of the member |

There is no palette in the file.

### 3.2 Compression

A variant of the **Pi** coder (Yanagisawa's PC-98 format): every pixel is predicted by copying
runs of 2-pixel units from one of five positions, and literal colours are coded with a
move-to-front list per left-neighbour colour. Decoder core `gf_core` `015A:003D` (self-modifying;
the same 1 076 bytes, apart from relocated addresses, in all four variants 015A:000A/0554/0B0A/
1076). **verified** bit-exact for all 54 pictures (§12).

Bits are read MSB first from consecutive bytes. The decoder works on a byte-per-pixel line
buffer whose two lines above the picture are part of the history; in a linear model (equivalent
to the original's 6-line ring, which keeps the last two lines when it flushes):

```
table[r][k] = (r - k) & 15            for r, k = 0..15         (gf_mtf_init 015A:043D)

colour(prev):                         (gf_colour_pair 015A:0315, one half)
    if bit:            idx = bit                          # 1x      -> 0..1
    elif not bit:      idx = 2 + bit                      # 00x     -> 2..3
    elif not bit:      idx = 4 + bits(2)                  # 010xx   -> 4..7
    else:              idx = 8 + bits(3)                  # 011xxx  -> 8..15
    c = table[prev][idx]; move entry idx to the front of table[prev]; return c

buf = 2*w history pixels + w*h picture pixels
a = colour(0); b = colour(a); fill the 2*w history pixels with a, b, a, b, ...
p = 2*w; last = 0
while p < 2*w + w*h:
    code: 00 -> id -4,  src = p-2 if buf[p-2] == buf[p-1] else p-4
          01 -> id -w,  src = p-w            (1 line up)
          10 -> id -2w, src = p-2w           (2 lines up)
          110-> id -w+1, src = p-w+1         (1 up, 1 right)
          111-> id -w-1, src = p-w-1         (1 up, 1 left)
    if id == last:                    # the same position twice: literal colours
        repeat:
            a = colour(buf[p-1]); b = colour(a); buf[p] = a; buf[p+1] = b; p += 2
        while bit == 1
        last = 0
    else:
        last = id
        n = 1 if bit == 0 else: k = 1 + number of further 1 bits (ended by a 0);
                                 n = (1 << k) | bits(k)        # 0 ->1, 10x ->2..3, 110xx ->4..7
        copy 2*n pixels from src upward, one pixel at a time (overlap repeats the pattern)
```

Notes (all **code**, and covered by the verification):

* The prediction "left" is position 0: two pixels back if those two pixels have the same colour,
  otherwise four pixels back; its identity for the "same position" test is −4 in both cases.
* `last` starts at 0 and is reset to 0 after a literal run, so a literal run is always followed by
  a copy.
* The decoder stops after exactly h lines, counted when lines are flushed (4 at a time); it reads
  the file in 0FD2h-byte blocks straight from the DOS handle (`gf_refill` `015A:0451`), so it may
  read into the next member; no game picture needs bytes past its own end.
* The original's ring holds 6 lines of w ≤ 640 bytes at buffer+12Eh..102Eh; w > 640 would
  overrun its input buffer (no picture does).

### 3.3 Output

`gf_flush_vram` `015A:0471` converts each line, 8 pixels per byte: pixel byte = colour << 4,
bits 7..4 → planes I, G, R, B (E000h, B800h, B000h, A800h). The picture is written at byte
offset y·80 + (x >> 3) — **x is rounded down to a multiple of 8** — one line per 80 bytes, with
no clipping (a picture reaching past line 399 would run into the 768-byte gap after each plane).

| Variant | Target | Flag 0 | Flag 1 |
|---|---|---|---|
| VRAM (buffers 10, 11) | A800h.. (page per A6h) | `015A:000A` | `015A:0554` |
| memory (buffer 12) | the four segments passed (0BA1:0046) | `015A:0B0A` | `015A:1076` |

With flag 1 (`gf_flush_vram_t` `015A:09BB`) every pixel of **colour 8 is transparent**: each
destination byte becomes `dst & m | src` with m = the colour-8 pixels. **verified** (cases B and
D, random backgrounds).

## 4. Op 31h — load picture

Operands (`ld_31` `063C:02F4`): buffer (byte), x (word), y (word), flag (byte), name (string).
`pic_load` `0315:070D` → `gf_load` `00DD:0216`:

1. returns 0 if graphics are not initialised (DS:00CE); hides the mouse cursor (`043A:02A5`);
2. name + `.gf` (DS:00E2), `lib_find` → position (failure: returns 0, nothing drawn);
3. `fseek`, `gf_header`; x and y operands replace the file's values unless −1 (no range check);
4. by buffer: 10 → A6h ← 0, VRAM decoder; 11 → A6h ← 1, VRAM decoder, A6h ← 0; 12 → memory
   decoder; any other value → nothing. Flag 1 selects the transparent variant, any other value
   the opaque one;
5. `win_snapshot` (`02BE:00AC`, [text.md](text.md)): the window rectangle of page 0 is saved as
   the background for the next message.

The scenario uses x = y = −1 never; flags 0 and 1 only. **code**; steps 3–4 **verified**.

## 5. Op 32h — rectangle copy and transitions

Operands (`ld_32` `063C:0355`): src buffer (byte), sx, sy, w, h (words), dst buffer (byte), dx,
dy (words), effect (byte). `rect_copy` `0315:07CB` (cursor hidden, then `win_snapshot` as above)
→ `rect_dispatch` `00DD:051A`:

* plane tables: 10 and 11 → A800h/B000h/B800h/E000h (DS:00C6) with `out A6h` = 0 or 1, 12 →
  the memory planes; the source is selected first, then the destination, so **a VRAM→VRAM copy
  always reads the destination's page** (10→11 copies page 1 onto itself). The scenario never
  does that (it uses 11→12 ×101, 12→10 ×126, 12→11 ×6, 10→12 ×2); A6h ← 0 at the end;
* x offsets are sx >> 3, dx >> 3 (byte-aligned), no clipping;
* dispatch on the effect code (table at `00DD:05B4`):

| Code | Routine | Unit | Uses | Effect |
|---|---|---|---|---|
| 20 | `fx_masked` `0783:007C` | (w+7)>>3 bytes | — | instant copy, source colour 8 transparent (m = colour-8 pixels: dst AND m, OR src AND NOT m) |
| 30 | `fx_dissolve4` `0783:0350` | (w+7)>>4 words | 36 | **じわ出し dissolve**: 4 passes |
| 31 | `fx_dissolve64` `0783:07C0` | words | — | 64-step ordered dissolve, 2 VSYNCs per step |
| 32 | `fx_checker_tb` `0783:05DD` | bytes | 54 | **from top and bottom**, checkerboard |
| 33 | `fx_interlace_tb` `0783:0494` | words | — | lines from top and bottom, interlaced |
| 34 | `fx_slide_lr` `0783:08DA` | bytes, in word steps | 1 (#1899, title) | lines slide in from left/right |
| any other (10, 21–29, <20, >34) | `fx_copy` `0783:0000` | words | 144 (all 10) | instant copy, line by line, planes B, R, G, I |

The two effects of the developers' notes (開発.DOC: "じわ出しと、上下からのと２つ") are 30 and 32.
The final image is the plain copy in every case, except for the rounding of the width and
effect 32 with odd h (below). Write order and final contents of every effect: **verified**
(`gfx_fx_verify.py`, 136 cases including the write sequence to VRAM).

**Width rounding.** "Words" means w is rounded to the *nearest* multiple of 16 pixels
((w + 7) >> 4 words: 248 → 240), "bytes" to the next multiple of 8. Statement #127 copies
`va_ch03` (256 wide, at x 32) with w = 248 and effect 30: only 240 columns are copied, so
x 272–279 of the character stays as it was (the scenario's w already leaves out 280–287). **verified** (rounding), **inferred** (visible effect).

Per effect, with line i = 0..h−1 of the rectangle (all writes are `dst = src & m | dst & ~m`
with the given mask m per 8-pixel byte; bit 7 = left pixel):

* **30**: for pass p = 0..3, for line i = 0..h−1, for plane B, R, G, I, for each word: m =
  88h ror ((p + i) mod 4) in both bytes, i.e. pixels with x mod 4 = (p + i) mod 4. Each pass
  covers the whole rectangle top to bottom; a diagonal ¼ of the pixels per pass. The source
  line is first copied to a temporary (0783:0210), so src = dst is safe.
* **31**: 64 steps; step s = 0..63 takes cell b = byte `0783:076F − s` (the table at 0783:0730,
  a permutation of 0..63): on the lines with (h − i) mod 8 = (b >> 3) & 7, the pixel with mask
  m = 1 << (b & 7) in every byte (x mod 8 = 7 − (b & 7)). After each step `fx31_wait`
  (`00DD:04F9`) waits until the VSYNC counter DS:109E has moved by ≥ 2 since the previous step
  (DS:172C; both zeroed first): ≥ 128 frames ≈ 2.3 s in all.
* **32**: for k = 0..h−1: m = AAh when k is even, 55h when odd; write line k (top half moving
  down) then line h−1−k (bottom half moving up), each with m for the source and ~m kept, planes
  B, R, G, I. Every line is written twice, by the downward sweep with m(k) and by the upward
  sweep with m(h−1−k): complementary when h is even, so the two checkerboards complete each
  other after crossing in the middle. **With odd h only half the pixels of every line would be
  copied**; all 54 uses have even h.
* **33**: if h is odd the last line first; then for k = 0..h/2−1: line 2k, then line h'−1−2k
  (h' = even h) — even lines from the top, odd lines from the bottom.
* **34**: nb = (w+7)>>3; for k = 1..nb/2: for each line pair (2j, 2j+1), j < h/2: line 2j gets
  the rightmost 2k bytes of its source line at its left edge, line 2j+1 the leftmost 2k bytes at
  its right edge (16 pixels more per step; even lines slide in from the left, odd lines from the
  right). The destination is always A800h.. — VRAM, whatever dst says. An odd last line is not
  copied. #1899 copies (80,39) 480×322 to (80,38), one line higher.

**Timing.** Only effect 31 waits for VSYNC; 10, 20, 30, 32, 33 and 34 run as fast as the CPU
writes VRAM, so their visible speed depends on the machine (a full-screen effect 30 is
4 × 400 × 4 × 40 masked word read-modify-writes of VRAM). **code**

**Which transition when** (the notes' "ある法則"): no exact rule is visible. Tracking buffer
contents through the statements in file order (`gf.gf_usage`), effect 32 is used for 32 of its 54
copies when the background in the window changes, effect 30 for 29 of its 36 copies when it does
not (a character appears, leaves or changes). **inferred**

## 6. Op 33h (clear) and op 18h (restore window)

* **33h** buffer: `gfx_clear` `0315:01BE` → `buf_clear` `00DD:0122` — buffer 12: zero the four
  memory planes; 11 / 10: A6h ← 1 / 0, cursor hidden, zero the four VRAM planes, A6h ← 0; any
  other value is treated as 10. Result: colour 0 everywhere. **code**
* **18h**: `0315:07F5` → `win_restore` `02BE:0097`: the saved window background (§4 step 5) is
  copied back to page 0's window rectangle (48,307)–(591,386), erasing the message text
  ([text.md](text.md)). Not used by the scenario (the menu code calls the same routine). **code**

## 7. Palettes

### 7.1 Storage and the DAC

The scenario's palette table (`scb_load_palettes` `06DD:0347`, `scb_read_palette` `06DD:03F5`):
per palette 24 bytes = 48 nibbles, high nibble first; colour i = nibbles 3i, 3i+1, 3i+2 =
**red, green, blue**, stored as 48 bytes R[16] G[16] B[16]. The pointer table (0BA1:0084) has
n + 1 entries, entry 0 unused, so P = 1..44; op 30h passes NULL for P ≤ 1, which would load 48
bytes of the interrupt vector table (P = 1 is never used). The scenario uses 38 palettes; P1,
P19, P25, P31, P36 and P38 are never selected.

`dac_set` `00DD:01D0` waits for the start of a vertical retrace (`in A0h` bit 5: while set, then
until set) and writes, for i = 0..15: `out A8h, i; out AEh, B; out ACh, R; out AAh, G` —
4-bit levels for the analog palette (A8h index, AAh green, ACh red, AEh blue). It is the only
code that writes the palette. `pal_set` `0315:0144` copies a palette to the current palette
g_pal_cur (0BA1:00A0) and calls `dac_set`. **verified** (port order and values, `pal_verify.py`).

So `scb.py`'s `(c0, c1, c2)` = (R, G, B) and colour 8 = `0f0` in most palettes is pure green
(the transparent colour, §9).

Built-in palettes in segment 0AA8: 0000 all black, 0060 all white, 0030 the default set by
`gfx_init` (digital-style: `000 007 700 707 070 077 770 777 aaa 00f f00 f0f 0f0 0ff ff0 fff`).

### 7.2 Fades

A fade adds the same signed d to every component and clamps to 0..15 (`pal_shift`
`0315:0202`; d > 14 gives all white, d < −14 all black). d is recomputed whenever the timer's
elapsed time e (in 1/100 s; e = ⌊k·1000/564⌋ after k VSYNCs, [platform.md](platform.md) §2)
changes, i.e. once per VSYNC; a DAC load (at the next retrace) happens only when d differs from
the previous d (statics DS:00DE for fades in, DS:00E0 for fades out, kept across calls). The loop
runs for k = 0 .. K−1, K = max(⌊t·564/1000⌋, 1). Divisions truncate toward zero.

| Op | Routine | Operands | Effect |
|---|---|---|---|
| 30h | `pal_op30` `0315:0176` | t (word), P (byte) | t > 0: `pal_fade_in` (`0315:031E`) to palette P over t/100 s; then `pal_set(P)` |
| 1Ah | `pal_fade_out` `0315:04E2` | to_white (bool), t (word) | t ≥ 1: fade the current palette to black (to_white = 0) or white; then set black/white (which becomes the current palette); t < 1: set it at once |
| 2Fh | `pal_flash` `0315:06C2` | t (word) | fade to white in t/2, then fade in to the saved palette in t/2, then set it |

* Fade in to palette T: if the current palette is all white, s = 15 − min(all components of
  T), else s = −max(all components of T) — **from black (or white) whatever is on screen**; at
  step k, d = s·(t − e)/t; at the end `pal_set(T)` (twice for op 30h: once inside the fade).
* Fade out of the current palette C: s = −max(C) (to black) or 15 − min(C) (to white); d =
  s·e/t; then the black/white palette is set and stored.
* Example: op 30h t = 100 to a palette whose brightest component is 15 → 56 VSYNCs (≈ 0.99 s),
  d = −15, −14, …, 0 (each held 3–4 frames), 16 fade loads + 2 final loads.
* If no timer slot is free the fade is skipped and the palette set at once.

Scenario use: op 30h ×81 (t ∈ {0, 1, 30, 40, 56, 100, 150, 160}), op 1Ah ×86 (t 0–180, to white
×8), op 2Fh ×2 (t = 30). All of this: **verified** — `gfx_pal.py` reproduces every DAC load of 20
op 30h/1Ah/2Fh sequences of the original (`pal_verify.py`, VSYNC simulated).

## 8. PC-98 hardware use

**Init** (`gfx_init` `0315:000E`, first call): open the archive (`lib_open` `0315:0072`: the
path from `m.exe`'s second argument, 0BA1:006C, else `gdata.lib`), `gfx_alloc` `00DD:0006`
(8 KB decoder buffer, the four 7D00h-byte planes of buffer 12; `out A2h, 0Ch` (graphic GDC
display off), `gfx_mode`, `out A2h, 0Dh` (on)), the window buffers (`win_alloc` `02BE:0006`),
then `pal_set(default)`. Later calls only redo `pal_set(default)` and `gfx_mode`.

`gfx_mode` `00DD:00A4`, in order: `out 6Ah, 1` (analog 16-colour mode); `out A2h, 4Bh; out A0h, 0`
(graphic GDC CSRFORM/CCHAR with 1 line per row: 400-line graphics); `out 68h, 08h` (mode
flip-flop 1, inferred: all lines displayed); `out 62h, 0Ch` (**text GDC display off — the text
layer is not used**; all text is drawn into graphics VRAM); `INT 18h AX=1B01h` (inferred: KCG
dot-access mode, used for the INT 18h AH=14h glyph reads); `vram_clear` `00DD:00E3` (GRCG on in
RMW mode, tile 0, both pages filled through A800h: colour 0; GRCG off); `out A4h, 0; out A6h, 0`.
`gfx_textmode` `00DD:00D0` (exit): `gfx_mode`, `INT 18h AX=1B00h`, `out 62h, 0Dh`.

**Pages**: A4h (display) is written only by `gfx_mode`: page 0 is always shown and page 1 is an
off-screen buffer (no page flipping). A6h (access page) is switched around each access to
buffer 11 and returned to 0.

**GRCG** (7Ch/7Eh): only `vram_clear` and the glyph blitters of the built-in sequences
(`05C3`, [platform.md](platform.md)). Pictures, copies and effects write the planes directly.

**VSYNC**: `dac_set` polls the graphic GDC status (A0h bit 5); fades and effect 31 use the VSYNC
interrupt counter (DS:109E and the timer slots, [platform.md](platform.md)).

## 9. Screen layout and colour conventions

| Element | Picture | Rectangle | Drawn |
|---|---|---|---|
| room frame | `va_main` | full screen; colour 8 in (160,48)–(479,247) | into 11, at (0,0) |
| background ("window" of the frame) | `va_bg01`–`09` | 320×200 at (160,48) | into 11, opaque |
| characters | `va_ch01`–`10` | 192–544 wide, at x 0–432 (several positions per character) | into 12, flag 1 |
| message window | `va_mw01` | 576×94 at (32,300) | into 10/11/12, flag 1 |
| message text | (glyphs) | (48,307)–(591,386): 4 rows of 16-dot glyphs at y = 309 + 20·row, x = 48 + 8·col, col 0–67 | [text.md](text.md) |
| face inset | `va_ch02k` | 112×77 at (104,102) | flag 1 |
| "VA" emblem | `va_va` | 208×20 at (224,327), inside the window | into 10, flag 1 |
| event pictures | `va_01`–`va_22` (and the strip `va_12e`) | full screen, the window already drawn in | into 10 or 12, opaque |
| white screen with window | `va_mw02` | full screen (colour 14 = white in P41) | into 10, flag 1 |
| opening / title / logo | `va_opbac`, `va_title`, `logo` | full screen | P43 / P2 / P3 |
| staff credits | `va_st01`–`04` | 328–480 × 186–192 at (80–160, 104–107) | opaque, P44 |

* **Colour 8 is the transparent colour** of op 31h flag 1 and effect 20. In most palettes it is
  `0f0` (pure green), so it is never meant to be seen; event pictures drawn opaque use it as a
  normal colour where their palette says so. (`va_bg01` has one stray colour-8 pixel at
  (31,199), screen (191,247), shown green.)
* The window `va_mw01` is a frame in colours 0, 2, 3 around a 50 % checkerboard of colour 0 and
  colour 8: drawn with flag 1 it darkens what lies beneath (the notes' "文字が読みやすくなりました").
  The same darkened window is pre-drawn into every event picture and into the bottom of the
  character pictures that reach y ≥ 300.
* Text is colour 15 with colour-0 edges ([text.md](text.md)); the menu bar inverts a row
  (colour c → 15 − c, `05C3:005B`). All palettes have colour 0 = black and 15 = white except P1
  and P31 (both unused) and P5/P7/P9 (red-tinted flashback versions of P4/P6/P8, colour 15 =
  `d7a`/`d69`/`d7a`).
* The room palettes **P32–P42** are one shared palette (P32) whose colours 4 and 7 change per
  scene (P33: 7 = `005`; P34: 4 = `024`; P35: 7 = `fbc`; P36–39: 4 = `467`/`fd9`/`fd9`/`245`,
  7 = `fbc` (P36, P38 unused); P40: 4 = `352`, 7 = `8a3`; P41: 14 = `fff`; P42: 4, 7, 9 =
  `fbe`, `ddd`, `bcb`).
  Backgrounds use colours 4 and 7, the frame and characters avoid colour 4 (and mostly 7), so a
  room can be recoloured without touching the characters. **inferred** (pixel statistics)
* Event pictures each have their own palette (P4–P30); P2 is a grey ramp (title), P44 shows only
  colours 7, 8, 15 (`777`, `ccc`, `fff`: staff credits).

## 10. All pictures

Size and file position: **verified**. Uses: every op 31h (`gf.py usage`,
`resources/derived/gfx/gf_usage.txt`). Palettes: the P values the picture is on screen with in a
file-order walk of the statements (`gf.gf_usage`; control flow is ignored), most frequent first
(**bold**). The bold palette of `va_01`–`va_21` equals the palette of the IBM BMP of
the same picture (§11): **verified** for those 21; the others **inferred**; later entries may
include artefacts of the walk (e.g. `va_01`/44, `va_main`/4, 44). `va_12e` is never on screen in
the walk (#1912 is reached by a jump); it is the window-less bottom strip of `va_12` (99.4 % of its
pixels equal the clean IBM picture there), pasted over it with a dissolve before the ending.

| # | Name | Size | File x,y | Bytes | op 31 statements | Buffer (x,y) flag | Palettes | BMP |
|---|---|---|---|---|---|---|---|---|
| 0 | `va_01` | 640×400 | 0,0 | 30487 | 286, 1795 | 12 (0,0) 0 | **4**, 5, 44 | 1 |
| 1 | `va_02` | 640×400 | 0,0 | 39172 | 288, 1833 | 12 (0,0) 0 | **6**, 7, 9 | 2 |
| 2 | `va_03` | 640×400 | 0,0 | 29190 | 289, 1856 | 11 (0,0) 0; 12 (0,0) 0 | **8**, 9 | 3 |
| 3 | `va_04` | 640×400 | 0,0 | 25733 | 136 | 10 (0,0) 0 | **10** | 4 |
| 4 | `va_05` | 640×400 | 0,0 | 26982 | 614 | 10 (0,0) 0 | **11** | 5 |
| 5 | `va_06` | 640×400 | 0,0 | 40009 | 629 | 10 (0,0) 0 | **12** | 6 |
| 6 | `va_07` | 640×400 | 0,0 | 37416 | 696 | 10 (0,0) 0 | **13** | 7 |
| 7 | `va_08` | 640×400 | 0,0 | 34704 | 1359 | 12 (0,0) 0 | **14** | 8 |
| 8 | `va_09` | 640×400 | 0,0 | 28940 | 1375 | 12 (0,0) 0 | **15** | 9 |
| 9 | `va_10` | 640×400 | 0,0 | 28609 | 1380 | 12 (0,0) 0 | **16** | 10 |
| 10 | `va_11` | 640×400 | 0,0 | 34307 | 1385 | 12 (0,0) 0 | **17** | 11 |
| 11 | `va_12e` | 576×88 | 32,303 | 6682 | 1912 | 12 (32,303) 0 | **18** (inferred) |  |
| 12 | `va_13` | 640×400 | 0,0 | 32205 | 1549 | 12 (0,0) 0 | **20** | 13 |
| 13 | `va_14` | 640×400 | 0,0 | 33507 | 1562 | 12 (0,0) 0 | **21** | 14 |
| 14 | `va_15` | 640×400 | 0,0 | 31308 | 1566 | 12 (0,0) 0 | **22** | 15 |
| 15 | `va_16` | 640×400 | 0,0 | 27775 | 1571 | 12 (0,0) 0 | **23** | 16 |
| 16 | `va_17` | 640×400 | 0,0 | 25992 | 1581 | 12 (0,0) 0 | **24** | 17 |
| 17 | `va_18` | 640×400 | 0,0 | 31220 | 1617 | 10 (0,0) 0 | **26** | 18 |
| 18 | `va_19` | 640×400 | 0,0 | 30577 | 1626 | 10 (0,0) 0 | **27** | 19 |
| 19 | `va_20` | 640×400 | 0,0 | 28597 | 1637 | 10 (0,0) 0 | **28** | 20 |
| 20 | `va_21` | 640×400 | 0,0 | 31149 | 1641 | 10 (0,0) 0 | **29** | 21 |
| 21 | `va_22` | 640×400 | 0,0 | 34487 | 1645 | 12 (0,0) 0 | **30** |  |
| 22 | `va_bg01` | 320×200 | 160,48 | 9311 | 65, 165, 279, … (10) | 11 (160,48) 0; 12 (160,48) 0 | **33**, 32, 34 |  |
| 23 | `va_bg02` | 320×200 | 160,48 | 7058 | 113, 173, 183, … (11) | 11 (160,48) 0 | **32**, 33 |  |
| 24 | `va_bg03` | 320×200 | 160,48 | 5970 | 108, 129, 225, … (8) | 11 (160,48) 0; 12 (160,48) 0 | **32**, 33, 34 |  |
| 25 | `va_bg04` | 320×200 | 160,48 | 10490 | 14 | 11 (160,48) 0 | **34** |  |
| 26 | `va_bg05` | 320×200 | 160,48 | 6752 | 412, 516 | 11 (160,48) 0 | **35** |  |
| 27 | `va_bg06` | 320×200 | 160,48 | 7277 | 406, 503, 522 | 11 (160,48) 0 | **35** |  |
| 28 | `va_bg07` | 320×200 | 160,48 | 7141 | 556, 807, 1306 | 11 (160,48) 0 | **39**, 37 |  |
| 29 | `va_bg08` | 320×200 | 160,48 | 12803 | 606 | 11 (160,48) 0 | **40** |  |
| 30 | `va_bg09` | 320×200 | 160,48 | 10864 | 1504 | 11 (160,48) 0 | **34**, 42 |  |
| 31 | `va_ch01` | 320×400 | 320,0 | 10158 | 8, 16, 61, … (32) | 12 (320,0) 1 | **32**, 39, 34, 33, 35, 40, 37 |  |
| 32 | `va_ch02` | 240×378 | 32,22 | 8675 | 119, 175, 185, … (21) | 12 (32,22) 1; 12 (400,22) 1 | **32**, 33, 35, 39, 40 |  |
| 33 | `va_ch03` | 256×400 | 32,0 | 8814 | 125, 131, 143, … (9) | 12 (32,0) 1; 12 (392,0) 1 | **33**, 32 |  |
| 34 | `va_ch04` | 272×360 | 16,40 | 6105 | 33, 66, 166, … (8) | 12 (16,40) 1 | **32**, 33, 34 |  |
| 35 | `va_ch05` | 192×348 | 32,52 | 4846 | 420, 539, 546 | 12 (432,52) 1 | **35** |  |
| 36 | `va_ch06` | 224×362 | 48,38 | 4455 | 415, 1324, 1366, … (6) | 12 (48,38) 1; 12 (400,38) 1 | **39**, 32, 35 |  |
| 37 | `va_ch08` | 192×374 | 48,26 | 7076 | 408, 414, 506, … (8) | 12 (48,26) 1 | **35**, 32, 37, 39 |  |
| 38 | `va_main` | 640×400 | 0,0 | 20099 | 1, 306, 687, … (6) | 11 (0,0) 0; 11 (0,0) 1 | **32**, 39, 35, 33, 34, 37, 40, 4, 42, 44 |  |
| 39 | `va_mw01` | 576×94 | 32,300 | 134 | 2, 34, 67, … (81) | 10 (32,300) 1; 11 (32,300) 1; 12 (32,300) 1 | **32**, 35, 39, 33, 34, 37, 40, 4, 44, 24, 42, 10, 30 |  |
| 40 | `va_mw02` | 640×400 | 0,0 | 121 | 683, 1392, 1556, … (4) | 10 (0,0) 1 | **41** |  |
| 41 | `va_ch02k` | 112×77 | 104,102 | 1377 | 211, 601, 610, … (4) | 10 (104,102) 1; 12 (104,102) 1 | **40**, 33, 39 |  |
| 42 | `va_12` | 640×400 | 0,0 | 32367 | 1520 | 10 (0,0) 0 | **18** | 12 |
| 43 | `va_ch07` | 352×400 | 0,0 | 17662 | 1319, 1431, 1449 | 12 (0,0) 1 | **39** |  |
| 44 | `va_ch09` | 544×384 | 80,16 | 14326 | 1335, 1350, 1356, … (6) | 12 (80,16) 1 | **39**, 32, 34 |  |
| 45 | `va_ch10` | 448×400 | 96,0 | 15264 | 1544 | 12 (96,0) 1 | **42** |  |
| 46 | `va_st01` | 480×186 | 0,0 | 4560 | 1794 | 10 (80,107) 0 | **44** |  |
| 47 | `va_st02` | 328×186 | 0,0 | 2511 | 1796 | 11 (160,107) 0 | **44** |  |
| 48 | `va_st03` | 424×192 | 0,0 | 3750 | 1845 | 10 (112,104) 0 | **44** |  |
| 49 | `va_st04` | 400×188 | 0,0 | 3295 | 1868 | 10 (120,107) 0 | **44** |  |
| 50 | `va_opbac` | 640×400 | 0,0 | 7261 | 1757 | 10 (0,0) 0 | **43** |  |
| 51 | `va_title` | 640×400 | 0,0 | 40501 | 1886 | 12 (0,0) 0 | **2** |  |
| 52 | `logo` | 640×400 | 0,0 | 8017 | 1972 | 10 (0,0) 0 | **3** |  |
| 53 | `va_va` | 208×20 | 0,0 | 457 | 151 | 10 (224,327) 1 | **32** |  |

The archive order is not alphabetical: `va_ch02k`, `va_12`, `va_ch07`, `va_ch09`, `va_ch10`,
the staff credits and the title pictures come after `va_mw02` (added late, inferred). Event
pictures: 22 (`va_01`–`va_22`); the notes count "総ＣＧ数４５".

## 11. The "Graphic Disk" BMPs

`VAGD.LZH` (extracted with 7z to `resources/derived/ibm_bmp/`) holds 22 BMPs, 640×400, 4 bits.
`ibm_bmp_compare.py` (`resources/derived/gfx/ibm_bmp_compare.txt`) matches them against the
decoded pictures; colour indices are identical (identity mapping) and **each BMP's palette
equals (high nibbles) the scenario palette the game uses with that picture** (the low nibble is
0 in some files, a copy of the high one in others).

| BMP | Picture | Differences |
|---|---|---|
| 1–21 | `va_01`–`va_21` | all except 17: the window area (37,303)–(602,390) — the BMPs are clean, the game pictures have the darkened window drawn in |
| 4, 5, 10, 11, 12, 13, 16, 20, 21 | | nothing else |
| 1, 2, 3, 6, 7, 8, 9, 14, 15, 18, 19 | | plus one patch of 462–2 913 pixels above or beside the window (e.g. 14: (552,93)–(594,146), 19: (18,96)–(104,189)): mosaic/retouched areas — the PC-98 pictures are the censored ones |
| 17 | `va_17` | identical (100 %); `va_17` has no window drawn in |
| VA | — | a character design sheet (ヤサカ・ユキ), not in the game (closest: `logo`, 75 %) |

`va_22` has no BMP; `12.BMP` is `va_12` (archive index 42), whose window strip `va_12e` (index
11) matches the BMP's clean bottom.

## 12. Verification

| Check | What | Result |
|---|---|---|
| `gf_verify.py` | the original op 31h (`0315:070D` → `00DD:0216` → each of the four decoders) on random target buffers vs `gf.decode` + `gf.to_planes`, for all 54 pictures: 12 opaque at the file position, 12 transparent, 10 opaque, 11 transparent at a random position | 216/216 bit-exact (`resources/derived/gfx/gf_verify.txt`) |
| `gfx_fx_verify.py` | the original op 32h for effects 10, 15, 20, 30–35 on 6 rectangles (odd heights, widths not multiples of 16), src/dst 12→10, 11→12, 10→12: every byte written to VRAM in order, final planes, the 64 waits of effect 31 | 136/136 (`gfx_fx_verify.txt`) |
| `pal_verify.py` | 20 op 30h/1Ah/2Fh calls with scenario palettes, VSYNC simulated: every DAC load (port order and values) | 20/20 (`pal_verify.txt`) |
| `ibm_bmp_compare.py` | BMPs vs decoded pictures and palettes | §11 |

## 13. Open questions

* The rule choosing effect 30 or 32 (§5) — only a tendency is visible.
* Port 68h ← 08h and INT 18h AX=1B01h/1B00h are interpreted from general PC-98 knowledge, not
  checked on hardware or an emulator.
* Real-machine speed of the CPU-bound effects (and so their apparent duration) is not measured.
* Palettes of pictures other than the 21 event pictures with BMPs come from a file-order walk;
  a walk following the control flow (or running the VM) would settle them.
