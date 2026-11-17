/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The graphics of M.EXE (docs/re/graphics.md): the three buffers, the statements that draw
 * (op 31h pictures, op 32h rectangle copies and their transitions, op 33h clear, op 18h the
 * window's background) and the palette (op 30h fade in, op 1Ah fade out, op 2Fh flash).
 *
 * Buffers: 10 = VRAM page 0 (the only one shown), 11 = VRAM page 1, 12 = four planes in main
 * memory. The original reaches the VRAM pages through the access page (port A6h); so does
 * the engine (the screen's access page), which matters where the original takes "VRAM" for an
 * unknown buffer number: whatever page A6h selects.
 *
 * Time: what the original runs as fast as the CPU goes (the transitions) charges the clocks of
 * the original's instructions to lrv_sys_cpu, so that a frame passes whenever the reference
 * machine (the profile's cpu_per_frame) would have spent one; the unit is an 80286 clock
 * (re-tools/m286.py, gfx/fx_clk.h). What the original times by the VSYNC (fades, DAC loads,
 * effect 31) waits for frames. */
#ifndef VG_GFX_GFX_H
#define VG_GFX_GFX_H

#include <stdint.h>
#include "lrvne/surface.h"

#define VG_PAL_BYTES    (16 * 3)        /* a palette: R[16] G[16] B[16], 0..15 a gun */

/* the message window's rectangle (docs/re/text.md §3.1): 68 bytes x 80 lines at 5FF6h */
#define VG_WIN_OFF      0x5FF6
#define VG_WIN_WB       68
#define VG_WIN_H        80
#define VG_WIN_BYTES    (VG_WIN_WB * VG_WIN_H)      /* 1540h per plane */

/* the operands of op 32h (ld_32 063C:0355) */
struct vg_rect_op {
    int src, sx, sy, w, h, dst, dx, dy, effect;
};

/* a write into a transition's destination, for the tests: plane, offset, value */
typedef void vg_write_fn(void *ctx, int plane, unsigned off, uint8_t value);

struct vg_gfx {
    int ready;                          /* g_gfx_ready DS:00CE */
    uint8_t pal_cur[VG_PAL_BYTES];      /* g_pal_cur 0BA1:00A0 */
    int fade_in_last, fade_out_last;    /* DS:00DE, DS:00E0 */
    uint8_t pal_black[VG_PAL_BYTES];    /* 0AA8:0000, 0AA8:0060, 0AA8:0030 (from the pack) */
    uint8_t pal_white[VG_PAL_BYTES];
    uint8_t pal_default[VG_PAL_BYTES];
    uint8_t fx31_order[64];             /* effect 31's cells by step 64..1, 0783:0730 (pack) */
    uint8_t win_save[4][VG_WIN_BYTES];  /* the window's background, 0BA1:0074 */
    uint8_t win_work[4][VG_WIN_BYTES];  /* the page being composed, 0BA1:0054 */
    uint16_t fx31_last;                 /* DS:172C */
    uint64_t clk;                       /* clocks charged since the start (tests) */
    vg_write_fn *on_write;              /* tests: every write of a transition */
    void *on_write_ctx;
    /* tests: every DAC load, with the 48 bytes loaded */
    void (*on_dac)(void *ctx, const uint8_t *pal);
    void *on_dac_ctx;
};

/* buf.c */
/* gfx_init (0315:000E): the first call readies the graphics (clears both pages, the window's
 * background) and sets the default palette; a later call sets the default palette and clears
 * both pages again (gfx_mode; buffer 12 and the window's background stay). The palettes and effect 31's
 * order come from the pack (vg_gfx_load_builtin, at start-up; fatal when missing). */
void vg_gfx_init(void);
void vg_gfx_load_builtin(void);
/* The planes of a buffer as op 31h / 33h see them, selecting the access page for 10 and 11;
 * NULL for another number. */
struct lrv_surface *vg_buffer(int buf);
/* op 31h (pic_load 0315:070D): picture `name` (without ".gf") into buffer buf at (x, y), -1:
 * the file's; flag 1 leaves colour 8 out. Then the window's background is taken from the
 * screen. 1, or 0 when the graphics are not ready or there is no such picture. */
int  vg_pic_load(int buf, int x, int y, int flag, const char *name);
/* op 33h (gfx_clear 0315:01BE): buffer 10, 11 or 12 to colour 0 (another number: 10). */
void vg_buf_clear(int buf);
/* win_snapshot (02BE:00AC) and win_restore_screen (02BE:009C, op 18h) */
void vg_win_snapshot(void);
void vg_win_restore(void);
/* screen_clear (0315:0132): page 0 and the window's background to colour 0 */
void vg_screen_clear(void);
/* Marks lines [y0, y1) of VRAM page `page` for the next present (the whole width). */
void vg_mark_lines(int page, int y0, int y1);

/* fx.c: op 32h (rect_copy 0315:07CB): 1, or 0 when the graphics are not ready */
int  vg_rect_copy(const struct vg_rect_op *op);
/* Charges n clocks of the reference machine: frames pass as they are spent. */
void vg_cpu(uint32_t n);

/* glyph.c: segment 05C3, into the access page (docs/re/text.md §5.1, §5.3, §5.4) */
/* vram_kanji (05C3:00CD) / vram_ank (05C3:01E9): the character emboldened at byte column x,
 * line y, all four planes; mode 0 inverse (black on white), 1 opaque (white on black), 2 OR-ed
 * in (white, the background kept) */
void vg_vram_kanji(int x, int y, unsigned lead, unsigned trail, int mode);
void vg_vram_ank(int x, int y, unsigned ch, int mode);
/* vram_kanji_wipe (05C3:02F9): at byte column x, text row row (16 lines), revealed from the
 * left in 16 steps into planes R and G, step() after each */
void vg_vram_kanji_wipe(int x, int row, unsigned lead, unsigned trail, void (*step)(void));
/* vram_kanji_2x (05C3:03A9) / vram_ank_2x (05C3:04DB): the glyph at double size (32 x 32,
 * 16 x 32) in colour 15 at byte column x, line 16 * row + 1 */
void vg_vram_kanji_2x(int x, int row, unsigned lead, unsigned trail);
void vg_vram_ank_2x(int x, int row, unsigned ch, int mode);
/* vram_15_to_8 (05C3:0588): every pixel of colour 15 becomes colour 8 */
void vg_vram_15_to_8(void);
/* vram_outline (05C3:05E2): around the colour-15 pixels of `words` words a line from (byte x,
 * line y), h lines, the pixels beside them that are not colour 15 become colour 0 */
void vg_vram_outline(int x, int y, int words, int h);
/* vram_fill_black (05C3:0753): colour 0, from word column xw of line y, ww words, h lines */
void vg_vram_fill_black(int xw, int y, int ww, int h);

/* pal.c */
/* dac_set (00DD:01D0): waits for the next vertical retrace, then loads pal into the DAC */
void vg_dac_set(const uint8_t *pal);
/* pal_set (0315:0144): pal becomes the current palette and is loaded */
void vg_pal_set(const uint8_t *pal);
/* pal_fade_in (0315:031E): from black (white when the current palette is all white) to pal
 * over t/100 s, then pal_set(pal) */
void vg_pal_fade_in(const uint8_t *pal, int t);
/* op 30h (0315:0176): t > 0: vg_pal_fade_in; then pal_set(pal) */
void vg_pal_op30(const uint8_t *pal, int t);
/* op 1Ah (0315:04E2): the current palette to black (to_white 0) or white over t/100 s */
void vg_pal_fade_out(int to_white, int t);
/* op 2Fh (0315:06C2): to white in t/2, back to the palette before in t/2 */
void vg_pal_flash(int t);

#endif
