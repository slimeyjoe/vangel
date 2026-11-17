/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Built-in 1 OPENING (0504:0295): the prologue, pages of centred text revealed character by
 * character on a black screen (docs/re/platform.md §5.2, text.md §5.3).
 *
 * Each full-width character is wiped in from the left in 16 steps (05C3:02F9); after each step
 * prologue_step (0504:02C8) lets a VSYNC pass on every second step, polling the input while it
 * waits: an input sets the skip flag, which ends the sequence once the character is drawn. A
 * page stays 3 s (an input ends it and the sequence); colour 6, the text's, then fades out by
 * one level a step, a step every two VSYNCs (the DAC load's and the counter's). */
#include <string.h>
#include "vg.h"
#include "lrvne/sjis.h"
#include "lrvne/utf8.h"

/* prologue_step (0504:02C8) */
static void wipe_step(void)
{
    struct vg_bi *b = &vg.bi;
    while (vg.timers.vsync == b->wipe_due) {
        if (vg_bi_input_check(0) == 1) {
            vg.text.skip = 1;
            break;
        }
        if (vg_frame())
            break;
    }
    if (b->wipe_steps++ & 1)
        b->wipe_due++;
}

/* op_fade_c6 (0504:030E): colour 6 of the prologue's palette down to black, 16 steps */
static void fade_c6(void)
{
    uint8_t p[VG_PAL_BYTES];
    int k;
    memcpy(p, vg.bi.pal_prologue, sizeof p);
    for (k = 0; k < 16; k++) {
        if (p[6])
            p[6]--;
        if (p[16 + 6])
            p[16 + 6]--;
        if (p[32 + 6])
            p[32 + 6]--;
        vg_pal_set(p);
        vg.timers.vsync = 0;
        while (vg.timers.vsync == 0)
            if (vg_frame())
                return;
    }
}

static int stop(void)
{
    return vg.text.skip == 1 || lrv_sys_quitting(&vg.sys);
}

/* a page's 3 s: an input ends it and the sequence; 1 then */
static int page_wait(void)
{
    int h = vg_timer_start(300), cut = 0;
    if (h) {
        vg_wait_begin(VG_WAIT_TICKS);
        for (;;) {
            if (vg_timer_done(h))
                break;
            if (vg_bi_input_check(0) == 1) {
                vg.text.skip = 1;
                cut = 1;
                break;
            }
            if (vg_frame()) {
                cut = 1;
                break;
            }
        }
        vg_wait_end(VG_WAIT_TICKS);
        vg_timer_free(h);
    }
    return cut;
}

/* op_clear_text (32, 59)-(607, 342) and the prologue's palette */
static void page_clear(void)
{
    vg_vram_fill_black(2, 59, 36, 284);
    vg_pal_set(vg.bi.pal_prologue);
}

/* the rows of a page of the table; 1 when the sequence stops */
static int draw_rows(const struct vg_bi_row *t, int rows)
{
    int k;
    for (k = 0; k < rows; k++) {
        const uint8_t *s = t[k].s;
        int len = (int)strlen((const char *)s), x = 40 - len / 2;
        int y = (int16_t)((t[k].row + 3) * 2), i;
        for (i = 0; i < len; i++) {
            vg.timers.vsync = 0;
            vg.bi.wipe_due = 0;
            if (lrv_sjis_is_lead(s[i])) {
                vg_vram_kanji_wipe(x + i, y, s[i], s[i + 1], wipe_step);
                i++;
            }
            if (stop())
                return 1;
        }
    }
    return 0;
}

/* a translated line on row `row`, centred as the original's; 1 when the sequence stops */
static int draw_tl(const struct vg_lay_line *l)
{
    int col = 40 - l->cols / 2, y = (l->row + 3) * 2;
    uint32_t i = 0;
    vg_text_tl(VG_TL_PROLOGUE, l->page, l->row, col, l->s, l->n);
    while (i < l->n) {
        uint16_t g[16];
        uint32_t cp;
        int w;
        i += (uint32_t)lrv_utf8_decode(l->s + i, &cp);
        vg.timers.vsync = 0;
        vg.bi.wipe_due = 0;
        if (cp == 0x20) {
            col++;
        } else if (cp > 0x20) {
            w = vg_lang_glyph(cp, g);
            vg_vram_cell_wipe(col, y, g, w, wipe_step);
            col += w;
        }
        if (stop())
            return 1;
    }
    return 0;
}

/* op_pages (0504:03EC); a translated page (docs/translation.md) is laid out on the 8 rows and
 * 72 columns the page's area holds, a line centred as the original's, and is as many pages as
 * it needs, each wiped in, waited for and faded as the original's */
static void pages(const struct vg_bi_row *t)
{
    static struct vg_lay lay;
    int p;
    for (p = 0; ; p++) {
        const uint8_t *tl = vg_lang_get("bi.prologue.%d", p);
        int rows, last, np, pg, k = 0;
        for (rows = 0; t[rows].s; rows++)
            ;
        last = t[rows].row < 0;         /* the page's end record: row -1 ends the table */
        if (tl) {
            vg_lay(tl, VG_BI_PROLOGUE_W, VG_BI_PROLOGUE_H, VG_BI_PROLOGUE_W, 0, 0, 0, 0, &lay);
            np = lay.npages ? lay.npages : 1;
        } else {
            np = 1;
        }
        for (pg = 0; pg < np; pg++) {
            page_clear();
            if (!tl) {
                if (draw_rows(t, rows))
                    return;
            } else {
                for (; k < lay.nlines && lay.line[k].page == pg; k++)
                    if (draw_tl(&lay.line[k]))
                        return;
            }
            if (page_wait() || (last && pg == np - 1))
                return;
            fade_c6();
        }
        t += rows + 1;
    }
}

void vg_bi_opening(void)
{
    vg_mouse_lock(1, 0);
    pages(vg.bi.prologue);
    vg_pal_fade_out(0, 100);
    vg_screen_clear();
    vg_mouse_lock(0, 1);
}
