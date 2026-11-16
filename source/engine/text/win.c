/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The message window (docs/re/text.md §3.1-§3.3, §4.1): the work buffer and its copies
 * (02BE:00BC, 02BE:00CC), the line drawer win_line (02BE:015F) with its glyphs win_kanji
 * (02EC:0006) and win_ank (02EC:00B1), the page-wait icon (02BE:02A1, 02BE:02D0), a menu
 * choice (02BE:020E) and the inverted bar (02BE:0263 -> 05C3:005B).
 *
 * A glyph row g (16 bits full-width, 8 half-width, the msb leftmost) is emboldened to
 * b = g | g << 1, and written into all four planes of its cell as
 *     dst[r] = dst[r] & ~b[r-1] & ~b[r+1] | b[r]          (b[-1] = b[16] = 0)
 * so the glyph is colour 15 with a black edge above and below it. */
#include <string.h>
#include "vg.h"
#include "lrvne/sjis.h"

/* the work buffer: row r, column c */
#define CELL(r, c)  ((r) * 0x550 + (c) + 0x88)

static void need_font(struct lrv_font *f, const char *name, int w, int h)
{
    if (lrv_font_load(f, &vg.pak, name, w, h) != LRV_OK)
        lrv_fatal(vg.hal, "the pack has no font %s (make pack)", name);
}

void vg_text_load_fonts(void)
{
    need_font(&vg.text.font16, "font16", 16, 16);
    need_font(&vg.text.font8, "font8", 8, 16);
    need_font(&vg.text.ank8, "ank8", 8, 16);
}

void vg_text_free_fonts(void)
{
    lrv_font_free(&vg.text.font16);
    lrv_font_free(&vg.text.font8);
    lrv_font_free(&vg.text.ank8);
}

void vg_text_event(int event, int arg)
{
    if (vg.text.on_event)
        vg.text.on_event(vg.text.on_event_ctx, event, arg);
}

void vg_win_clear(void)
{
    memcpy(vg.gfx.win_work, vg.gfx.win_save, sizeof vg.gfx.win_work);
}

void vg_win_show(void)
{
    struct lrv_surface *pg;
    int q, l;
    vg_mouse_hide();
    pg = lrv_screen_access(&vg.screen);
    for (q = 0; q < 4; q++)
        for (l = 0; l < VG_WIN_H; l++)
            memcpy(pg->plane[q] + VG_WIN_OFF + l * VG_PLANE_STRIDE,
                   vg.gfx.win_work[q] + l * VG_WIN_WB, VG_WIN_WB);
    lrv_screen_mark_off(&vg.screen, vg.screen.access_page, VG_WIN_OFF, VG_WIN_WB, VG_WIN_H);
    vg_text_event(VG_TEV_SHOW, 0);
}

/* the cell's 16 rows, emboldened, into the work buffer at offset off (wb bytes a row) */
static void win_glyph(unsigned off, const uint16_t *b, int wb)
{
    int r, q;
    for (r = 0; r < 16; r++, off += VG_WIN_WB) {
        unsigned above = r > 0 ? b[r - 1] : 0, below = r < 15 ? b[r + 1] : 0;
        for (q = 0; q < 4; q++) {
            uint8_t *d = vg.gfx.win_work[q] + off;
            if (wb == 2) {
                d[0] = (uint8_t)((d[0] & ~(above >> 8) & ~(below >> 8)) | (b[r] >> 8));
                d[1] = (uint8_t)((d[1] & ~above & ~below) | b[r]);
            } else {
                d[0] = (uint8_t)((d[0] & ~above & ~below) | b[r]);
            }
        }
    }
}

/* sjis_to_jis (0A96:0002): the C library's _mbcjmstojis, 0 for a pair that is not one */
static unsigned sjis_to_jis(unsigned lead, unsigned trail)
{
    if (!lrv_sjis_is_lead(lead) || trail < 0x40 || trail == 0x7F || trail > 0xFC)
        return 0;
    return lrv_sjis_to_jis(lead, trail);
}

/* win_kanji (02EC:0006): INT 18h AH=14h, the kanji ROM's pattern of `jis` */
static void win_kanji(unsigned jis, int col, int row)
{
    uint8_t g[32];
    uint16_t b[16];
    int r;
    lrv_font_rom_glyph(&vg.text.font16, &vg.text.font8, jis, g);
    for (r = 0; r < 16; r++)
        b[r] = lrv_glyph_bold16_plain((uint16_t)(g[2 * r] << 8 | g[2 * r + 1]));
    win_glyph((unsigned)CELL(row, col), b, 2);
}

/* win_ank (02EC:00B1): ank_glyph (0504:0B52), the game's own font */
static void win_ank(unsigned ch, int col, int row)
{
    const uint8_t *g = lrv_font_glyph(&vg.text.ank8, ch & 0xFF);
    uint16_t b[16];
    int r;
    for (r = 0; r < 16; r++)
        b[r] = lrv_glyph_bold8_plain(g ? g[r] : 0);
    win_glyph((unsigned)CELL(row, col), b, 1);
}

int vg_win_line(const uint8_t *s, int row, int col)
{
    vg_mouse_hide();
    /* (INT 18h AX=1B01h: the KCG's access mode; nothing to do) */
    if (row > 3 || row < 0 || col > 0x43)
        return 0;
    vg_mouse_hide();
    while (*s) {
        if (lrv_sjis_is_lead(*s)) {
            win_kanji(sjis_to_jis(s[0], s[1]), col, row);
            s += 2;
            col += 2;
        } else {
            win_ank(*s, col, row);
            s++;
            col++;
        }
        if (col > 0x43)
            break;
    }
    vg_mouse_show();
    return 1;
}

/* vram_ank (05C3:01E9) in mode 2: the glyph of ch, emboldened, OR-ed into all four planes of
 * VRAM at byte column x, line y */
static void vram_ank_or(int x, int y, unsigned ch)
{
    struct lrv_surface *pg = lrv_screen_access(&vg.screen);
    const uint8_t *g = lrv_font_glyph(&vg.text.ank8, ch);
    uint8_t b[16];
    struct lrv_rect dirty;
    int r;
    for (r = 0; r < 16; r++)
        b[r] = lrv_glyph_bold8_plain(g ? g[r] : 0);
    lrv_rect_clear(&dirty);
    lrv_glyph_blit(pg, x, y, b, 1, 16, 15, LRV_GLYPH_CLEAR, 15, &dirty);
    lrv_screen_mark_surface(&vg.screen, pg, &dirty);
}

void vg_icon(int on)
{
    if (on == 1) {
        /* icon_draw: the halves of the return-key arrow, '&' and '\'' of the game's font */
        vram_ank_or(72, 369, 0x26);
        vram_ank_or(73, 369, 0x27);
        vg_text_event(VG_TEV_ICON_ON, 0);
    } else {
        /* icon_erase -> win_restore_cell (02EC:0227): row 3, columns 66-67 of the work buffer
         * (which by then holds the background again: msg_show clears it before the wait) */
        struct lrv_surface *pg = lrv_screen_access(&vg.screen);
        unsigned vo = 3 * 0x640 + 0xA0 + VG_WIN_OFF + 66, wo = (unsigned)CELL(3, 66);
        int r, q;
        for (r = 0; r < 16; r++)
            for (q = 0; q < 4; q++)
                memcpy(pg->plane[q] + vo + r * VG_PLANE_STRIDE,
                       vg.gfx.win_work[q] + wo + r * VG_WIN_WB, 2);
        lrv_screen_mark_off(&vg.screen, vg.screen.access_page, (int)vo, 2, 16);
        vg_text_event(VG_TEV_ICON_OFF, 0);
    }
}

void vg_rect_invert(const struct vg_menu_rect *rc)
{
    struct lrv_surface *pg;
    int h = rc->y1 - rc->y0 + 1, x = rc->x0 / 8, words = (rc->x1 / 8 - x + 1) >> 1, l, k, q;
    unsigned off = (unsigned)(rc->y0 * VG_PLANE_STRIDE + x);
    vg_mouse_hide();
    pg = lrv_screen_access(&vg.screen);
    /* vram_invert (05C3:005B): NOT word by word, all four planes, line by line */
    for (l = 0; l < h; l++)
        for (q = 0; q < 4; q++)
            for (k = 0; k < 2 * words; k++) {
                unsigned o = off + (unsigned)(l * VG_PLANE_STRIDE + k);
                if (o < VG_PLANE_BYTES)
                    pg->plane[q][o] = (uint8_t)~pg->plane[q][o];
            }
    if (words > 0 && h > 0)
        lrv_screen_mark_off(&vg.screen, vg.screen.access_page, (int)off, 2 * words, h);
    vg_text_event(VG_TEV_INVERT, rc->y0);
}

int vg_menu_choice(const uint8_t *s, struct vg_menu_rect *r, int i)
{
    if (vg_win_line(s, i, 0) != 1)
        return 0;
    r->x0 = 0x30;
    r->x1 = 0x24F;
    r->y0 = 20 * i + 0x133;
    r->y1 = r->y0 + 0x13;
    return 1;
}
