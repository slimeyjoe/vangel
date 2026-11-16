/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The graphics buffers and the statements that fill them: gfx_init, op 31h (pictures),
 * op 33h (clear), the window's background (win_snapshot, op 18h) and screen_clear.
 * docs/re/graphics.md §1, §4, §6, §8; docs/re/text.md §3.1. */
#include <string.h>
#include "vg.h"

static void need_palette(const char *name, uint8_t *pal)
{
    const struct lrv_pack_entry *e = lrv_pack_find(&vg.pak, name, LRV_PT_BLOB);
    if (!e || e->size != VG_PAL_BYTES ||
        lrv_pack_read(&vg.pak, e, 0, pal, VG_PAL_BYTES) != VG_PAL_BYTES)
        lrv_fatal(vg.hal, "the pack has no palette %s (make pack)", name);
}

void vg_gfx_load_palettes(void)
{
    need_palette("pal.black", vg.gfx.pal_black);
    need_palette("pal.white", vg.gfx.pal_white);
    need_palette("pal.default", vg.gfx.pal_default);
}

void vg_mark_lines(int page, int y0, int y1)
{
    lrv_screen_mark(&vg.screen, page, 0, y0, VG_SCREEN_W, y1);
}

/* vram_clear (00DD:00E3): the GRCG fills both pages with colour 0; page 0 is accessed after */
static void vram_clear(void)
{
    int p;
    for (p = 0; p < 2; p++) {
        lrv_surface_clear(&vg.screen.page[p]);
        vg_mark_lines(p, 0, VG_SCREEN_H);
    }
    lrv_screen_set_access(&vg.screen, 0);
}

void vg_gfx_init(void)
{
    if (!vg.gfx.ready) {
        /* the library is open (vg_machine_open); gfx_alloc's gfx_mode clears the pages; the
         * window buffers are new (zero) */
        vram_clear();
        lrv_surface_clear(&vg.screen.buffer[0]);
        memset(vg.gfx.win_save, 0, sizeof vg.gfx.win_save);
        vg.gfx.ready = 1;
    }
    vg_pal_set(vg.gfx.pal_default);
}

struct lrv_surface *vg_buffer(int buf)
{
    switch (buf) {
    case 10:
    case 11:
        lrv_screen_set_access(&vg.screen, buf - 10);
        return lrv_screen_access(&vg.screen);
    case 12:
        return &vg.screen.buffer[0];
    default:
        return NULL;
    }
}

int vg_pic_load(int buf, int x, int y, int flag, const char *name)
{
    char full[16];
    struct lrv_surface *s;
    struct lrv_rect r;
    int i;

    if (!vg.gfx.ready)
        return 0;
    /* (the pointer is hidden here: the mouse comes with the input, M2) */
    if (name) {
        if (strlen(name) + 4 > sizeof full)
            return 0;
        strcpy(full, name);
        strcat(full, ".gf");
        i = gf_lib_find(&vg.lib, full);
        if (i < 0)
            return 0;
        s = vg_buffer(buf);
        if (s) {
            lrv_rect_clear(&r);
            (void)gf_draw(&vg.lib, i, s, x, y, flag == 1, NULL, &r);
            if (buf != 12 && r.x1 > r.x0)
                lrv_screen_mark_surface(&vg.screen, s, &r);
            lrv_screen_set_access(&vg.screen, 0);
            lrv_sys_trace(&vg.sys, VG_TR_PICTURE, full, 0, buf, x, y, flag);
        }
    }
    vg_win_snapshot();
    return 1;
}

void vg_buf_clear(int buf)
{
    if (buf != 10 && buf != 11 && buf != 12)
        buf = 10;
    if (buf == 12) {
        lrv_surface_clear(&vg.screen.buffer[0]);
        return;
    }
    lrv_screen_set_access(&vg.screen, buf - 10);
    lrv_screen_clear_access(&vg.screen);
    lrv_screen_set_access(&vg.screen, 0);
}

/* win_blit_raw (02EC:0154): 68 x 80 bytes of each plane between the access page at 5FF6h and
 * the save buffer */
static void win_blit(int to_screen)
{
    struct lrv_surface *pg = lrv_screen_access(&vg.screen);
    int q, l;

    for (q = 0; q < 4; q++)
        for (l = 0; l < VG_WIN_H; l++) {
            uint8_t *v = pg->plane[q] + VG_WIN_OFF + l * VG_PLANE_STRIDE;
            uint8_t *b = vg.gfx.win_save[q] + l * VG_WIN_WB;
            if (to_screen)
                memcpy(v, b, VG_WIN_WB);
            else
                memcpy(b, v, VG_WIN_WB);
        }
    if (to_screen)
        lrv_screen_mark_off(&vg.screen, vg.screen.access_page, VG_WIN_OFF, VG_WIN_WB,
                            VG_WIN_H);
}

void vg_win_snapshot(void)
{
    win_blit(0);
}

void vg_win_restore(void)
{
    win_blit(1);
}

void vg_screen_clear(void)
{
    if (!vg.gfx.ready)
        return;
    vram_clear();
    memset(vg.gfx.win_save, 0, sizeof vg.gfx.win_save);
}
