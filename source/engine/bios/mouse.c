/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The mouse: M.EXE's calls of the MSZ driver (INT 33h, 0401:001A..01BE; docs/re/platform.md
 * §3.3) and the driver itself as far as the game sees it: the pointer's position and buttons
 * (lrvne's pointer, 640x400, which is the driver's default range), show and hide, and the
 * pointer drawn over the displayed page.
 *
 * MSZ's own pointer shape is not known (docs/lrvne-fit.md); the engine draws an arrow of its
 * own, white with a black outline, hot spot at its tip. It is an overlay: it exists in the
 * picture presented, never in VRAM, so drawing under it needs no hiding. The original hides it
 * around every VRAM access because MSZ draws it into VRAM; the engine keeps those calls, as
 * they decide when the pointer is visible. */
#include <string.h>
#include "vg.h"

#define PTR_W 2                         /* bytes */
#define PTR_H 16

/* the arrow: ink (white) and outline (black), 16 pixels a row, the leftmost the msb */
static const uint16_t ptr_ink[PTR_H] = {
    0x0000, 0x4000, 0x6000, 0x7000, 0x7800, 0x7C00, 0x7E00, 0x7F00,
    0x7F80, 0x7C00, 0x6C00, 0x4600, 0x0600, 0x0300, 0x0300, 0x0000
};
static const uint16_t ptr_mask[PTR_H] = {
    0xC000, 0xE000, 0xF000, 0xF800, 0xFC00, 0xFE00, 0xFF00, 0xFF80,
    0xFFC0, 0xFFC0, 0xFE00, 0xEF00, 0xCF00, 0x0780, 0x0780, 0x0300
};

static struct {
    int valid, col, y, w, h;
    uint8_t under[4][PTR_H][PTR_W + 1];
} ptr;

static void ptr_mark(struct lrv_surface *pg, struct lrv_rect *dirty)
{
    struct lrv_rect r;
    r.x0 = ptr.col * 8;
    r.x1 = (ptr.col + ptr.w) * 8;
    r.y0 = ptr.y;
    r.y1 = ptr.y + ptr.h;
    lrv_rect_clip(&r, pg);
    lrv_rect_union(dirty, &r);
}

static void ptr_apply(void *ctx, struct lrv_surface *pg, struct lrv_rect *dirty)
{
    int x = vg.sys.mouse_x, y = vg.sys.mouse_y, sh = x & 7, r, b, p;
    (void)ctx;
    ptr.valid = 0;
    if (!vg.input.ptr_shown || !(vg.input.open & VG_DEV_MOUSE))
        return;
    ptr.col = x >> 3;
    ptr.y = y;
    ptr.w = PTR_W + (sh ? 1 : 0);
    if (ptr.col + ptr.w > pg->stride)
        ptr.w = pg->stride - ptr.col;
    ptr.h = y + PTR_H > pg->h ? pg->h - y : PTR_H;
    for (r = 0; r < ptr.h; r++) {
        uint32_t ink = (uint32_t)ptr_ink[r] << 8 >> sh, mask = (uint32_t)ptr_mask[r] << 8 >> sh;
        for (b = 0; b < ptr.w; b++) {
            int sft = 16 - 8 * b;
            uint8_t m = (uint8_t)(mask >> sft), i = (uint8_t)(ink >> sft);
            for (p = 0; p < 4; p++) {
                uint8_t *d = pg->plane[p] + (y + r) * pg->stride + ptr.col + b;
                ptr.under[p][r][b] = *d;
                *d = (uint8_t)((*d & ~m) | (i & m));
            }
        }
    }
    ptr.valid = 1;
    ptr_mark(pg, dirty);
}

static void ptr_restore(void *ctx, struct lrv_surface *pg, struct lrv_rect *dirty)
{
    int r, b, p;
    (void)ctx;
    if (!ptr.valid)
        return;
    for (r = 0; r < ptr.h; r++)
        for (b = 0; b < ptr.w; b++)
            for (p = 0; p < 4; p++)
                pg->plane[p][(ptr.y + r) * pg->stride + ptr.col + b] = ptr.under[p][r][b];
    ptr.valid = 0;
    ptr_mark(pg, dirty);
}

/* INT 33h AX=1 / AX=2 */
static void int33_show(int show)
{
    vg.input.ptr_shown = show;
    if (vg.input.on_pointer)
        vg.input.on_pointer(vg.input.on_pointer_ctx, show);
}

int vg_mouse_open(void)
{
    /* AX=0 resets the driver (the pointer is then hidden); AX=FDh BX=1 and AX=FFh BX=0Fh are
     * MSZ's own functions, whose effect is not known */
    vg.input.ptr_shown = 0;
    if (!vg.input.ptr_overlay) {
        if (lrv_screen_add_overlay(&vg.screen, ptr_apply, ptr_restore, NULL) != LRV_OK)
            return 0;
        vg.input.ptr_overlay = 1;
    }
    return 1;
}

void vg_mouse_close(void)
{
    vg_mouse_show_raw(0);
}

void vg_mouse_read(struct vg_reading_mouse *m)
{
    unsigned bt = vg.sys.in.buttons;
    if (vg.input.ptr_shown == 0)
        vg_mouse_show_raw(1);
    m->x = vg.sys.mouse_x;
    m->y = vg.sys.mouse_y;
    m->left = (bt & LRV_BTN_L) ? 1 : 0;
    m->right = (bt & LRV_BTN_R) ? 1 : 0;
    m->zero = 0;
}

void vg_mouse_show_raw(int show)
{
    if (vg.input.ptr_locked == 1)
        return;
    if (show == 1 && vg.input.ptr_shown == 0)
        int33_show(1);
    else if (show == 0 && vg.input.ptr_shown == 1)
        int33_show(0);
}

void vg_mouse_show(void)
{
    if (vg.input.open & VG_DEV_MOUSE)
        vg_mouse_show_raw(1);
}

void vg_mouse_hide(void)
{
    if (vg.input.open & VG_DEV_MOUSE)
        vg_mouse_show_raw(0);
}

void vg_mouse_lock(int lock, int show)
{
    if (!(vg.input.open & VG_DEV_MOUSE))
        return;
    if (lock != 1) {
        vg.input.ptr_locked = 0;
        return;
    }
    vg.input.ptr_locked = 1;
    if (show == 1 && vg.input.ptr_shown == 0)
        int33_show(1);
    else if (show == 0 && vg.input.ptr_shown == 1)
        int33_show(0);
}
