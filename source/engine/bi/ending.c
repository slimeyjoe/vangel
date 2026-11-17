/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Built-ins 2 ENDING (0504:0568) and 5 ENDING2 (0504:05CA): the staff roll over the last
 * picture (docs/re/platform.md §5.3, text.md §5.4).
 *
 * The palette is first brought down towards a darker one (pal_dec_fade 0504:0632: each step
 * decrements whatever differs from the target, then four VSYNCs pass: the DAC load and three
 * more); the working palette is M.EXE's own data, so the change stays for a second roll.
 * Colour 15 becomes 8 on the screen, which leaves 15 to the staff's names. A page of four
 * lines is drawn at double size on page 1 over a copy of the screen's lower part, outlined in
 * black, and shown and taken away with effect 31; it stays 360 VSYNCs, the next comes 120
 * after. Nothing skips it. */
#include <stdlib.h>
#include "vg.h"
#include "lrvne/sjis.h"
#include "lrvne/utf8.h"

/* pal_dec_fade (0504:0632) */
static void dec_fade(uint8_t *p, const uint8_t *t)
{
    int n, i, k;
    for (n = 0; n < 16; n++) {
        for (i = 0; i < 16; i++) {
            if (t[i] != p[i])
                p[i]--;
            if (t[16 + i] != p[16 + i])
                p[16 + i]--;
            if (t[32 + i] != p[32 + i])
                p[32 + i]--;
        }
        vg_pal_set(p);
        for (k = 0; k < 3; k++) {
            uint16_t c = vg.timers.vsync;
            while (vg.timers.vsync == c)
                if (vg_frame())
                    return;
        }
    }
}

/* until abs(the frame counter) reaches n: the counter is the original's int */
static int wait_count(int n)
{
    while (abs((int16_t)vg.timers.vsync) < n)
        if (vg_frame())
            return 1;
    return 0;
}

/* a line of the original's list at slot k (0, 2, 4, 6) of the page block */
static void line_orig(const uint8_t *s, int k)
{
    int i;
    for (i = 0; i < 80 && s[i]; i++) {
        if (lrv_sjis_is_lead(s[i])) {
            vg_vram_kanji_2x(2 * i, k, s[i], s[i + 1]);
            i++;
        } else if ((int8_t)s[i] > 0x20) {
            vg_vram_ank_2x(2 * i, k, s[i], 2);
        }
    }
}

/* a translated line at slot k: a column is 16 pixels, a space takes one */
static void line_tl(const struct vg_lay_line *l, int k)
{
    int c = l->col;
    uint32_t i = 0;
    vg_text_tl(VG_TL_STAFF, l->page, l->row, l->col, l->s, l->n);
    while (i < l->n && c < 40) {
        uint16_t g[16];
        uint32_t cp;
        int w;
        i += (uint32_t)lrv_utf8_decode(l->s + i, &cp);
        if (cp < 0x20)
            continue;
        if (cp == 0x20) {
            c++;
            continue;
        }
        w = vg_lang_glyph(cp, g);
        vg_vram_cell_2x(2 * c, k, g, w);
        c += w;
    }
}

/* one page of the roll: the original's lines (n of them from list) or the translation's
 * lines of page pg; 1 when the program quits */
static int roll_page(const uint8_t *const *list, int n, const struct vg_lay *lay, int pg)
{
    const struct vg_rect_op *r = vg.bi.rect;    /* DS:04CC 04DE 04F0 0502 0514 0526 */
    int k;
    vg_rect_copy(&r[0]);                /* the screen's part to buffer 12, from there to */
    vg_rect_copy(&r[2]);                /* page 1, under the page's lines */
    if (!lay) {
        for (k = 0; k < n; k++) {
            lrv_screen_set_access(&vg.screen, 1);
            line_orig(list[k], 2 * k);
            vg_vram_outline(0, 1, 0x40, 0x80);
            lrv_screen_set_access(&vg.screen, 0);
        }
    } else {
        for (k = 0; k < lay->nlines; k++) {
            if (lay->line[k].page != pg)
                continue;
            lrv_screen_set_access(&vg.screen, 1);
            line_tl(&lay->line[k], 2 * lay->line[k].row);
            vg_vram_outline(0, 1, 0x40, 0x80);
            lrv_screen_set_access(&vg.screen, 0);
        }
    }
    vg_rect_copy(&r[4]);                /* the page to buffer 12, onto the screen */
    vg_rect_copy(&r[3]);
    vg.timers.vsync = 0;
    if (wait_count(360))
        return 1;
    vg_rect_copy(&r[5]);                /* the kept part back */
    vg.timers.vsync = 0;
    return wait_count(120);
}

/* staff_roll (0504:06FA): pages of four lines of the list. A translated page
 * (docs/translation.md) is laid out on four lines of 32 double-size columns, indentation kept,
 * and is as many pages as it needs. */
static void roll(const uint8_t *const *list)
{
    static struct vg_lay lay;
    const struct vg_rect_op *r = vg.bi.rect;
    int p;
    vg_rect_copy(&r[1]);                /* the screen's lower part kept in buffer 12 */
    vg.timers.vsync = 0;
    for (p = 0; *list; p++) {
        const uint8_t *tl = vg_lang_get("bi.staff.%d", p);
        int n, pg;
        for (n = 0; n < 4 && list[n]; n++)
            ;
        if (!tl) {
            if (roll_page(list, n, NULL, 0))
                return;
        } else {
            vg_lay(tl, VG_BI_STAFF_W, VG_BI_STAFF_H, VG_BI_STAFF_W, 0, 0, 0, 1, &lay);
            for (pg = 0; pg < (lay.npages ? lay.npages : 1); pg++)
                if (roll_page(NULL, 0, &lay, pg))
                    return;
        }
        list += n;
    }
    vg_rect_copy(&r[5]);
}

void vg_bi_ending(int which)
{
    vg.timers.vsync = 0;
    vg_mouse_lock(1, 0);
    dec_fade(vg.bi.pal_from[which], vg.bi.pal_to[which]);
    vg_vram_15_to_8();
    vg_pal_set(vg.bi.pal_roll[which]);
    roll(vg.bi.staff);
    vg_pal_fade_out(0, 100);
    vg_screen_clear();
    vg_mouse_lock(0, 1);
}
