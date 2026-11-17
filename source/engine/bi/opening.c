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

/* op_pages (0504:03EC) */
static void pages(const struct vg_bi_row *t)
{
    for (;;) {
        int rows, h, cut = 0;
        vg_vram_fill_black(2, 59, 36, 284);     /* op_clear_text: (32, 59)-(607, 342) */
        vg_pal_set(vg.bi.pal_prologue);
        for (rows = 0; t[rows].s; rows++) {
            const uint8_t *s = t[rows].s;
            int len = (int)strlen((const char *)s), x = 40 - len / 2;
            int y = (int16_t)((t[rows].row + 3) * 2), i;
            for (i = 0; i < len; i++) {
                vg.timers.vsync = 0;
                vg.bi.wipe_due = 0;
                if (lrv_sjis_is_lead(s[i])) {
                    vg_vram_kanji_wipe(x + i, y, s[i], s[i + 1], wipe_step);
                    i++;
                }
                if (stop())
                    return;
            }
        }
        h = vg_timer_start(300);
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
        if (cut || t[rows].row < 0)     /* the page's end record: row -1 ends the table */
            return;
        t += rows + 1;
        fade_c6();
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
