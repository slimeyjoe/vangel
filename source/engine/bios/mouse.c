/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The mouse: M.EXE's calls of the MSZ driver (INT 33h, 0401:001A..01BE; docs/re/platform.md
 * §3.3) and the driver itself as far as the game sees it: the pointer's position and buttons
 * (lrvne's pointer, 640x400, which is the driver's default range), show and hide, and the
 * pointer drawn over the displayed page.
 *
 * MSZ's own pointer shape is not known (docs/lrvne-fit.md); the engine draws an arrow of its
 * own, white with a black outline, hot spot at its tip. It is an overlay (lrvne's
 * struct lrv_pointer): it exists in the picture presented, never in VRAM, so drawing under it
 * needs no hiding. The original hides it around every VRAM access because MSZ draws it into
 * VRAM; the engine keeps those calls, as they decide when the pointer is visible. */
#include <string.h>
#include "vg.h"

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
static const struct lrv_pointer_shape ptr_shape = { ptr_ink, ptr_mask, PTR_H, 0, 0, 15, 0 };

/* lrvne's pointer overlay, seen while the driver shows it and the mouse is open */
static struct lrv_pointer ptr;

static void ptr_apply(void *ctx, struct lrv_surface *pg, struct lrv_rect *dirty)
{
    (void)ctx;
    ptr.x = vg.sys.mouse_x;
    ptr.y = vg.sys.mouse_y;
    ptr.shown = vg.input.ptr_shown && (vg.input.open & VG_DEV_MOUSE);
    lrv_pointer_apply(&ptr, pg, dirty);
}

static void ptr_restore(void *ctx, struct lrv_surface *pg, struct lrv_rect *dirty)
{
    (void)ctx;
    lrv_pointer_restore(&ptr, pg, dirty);
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
        lrv_pointer_init(&ptr, &ptr_shape);
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
