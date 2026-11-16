/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The palette: dac_set, pal_set and the fades of ops 30h, 1Ah and 2Fh (docs/re/graphics.md
 * §7). A palette is 48 bytes R[16] G[16] B[16] of 4-bit levels.
 *
 * Time: dac_set waits for the start of a vertical retrace, which is the next VSYNC whenever it
 * is called (called during a retrace it waits for the next one: the fades call it right after
 * a VSYNC, within the retrace), so here it is a frame. A fade recomputes its offset once per
 * VSYNC from its timer slot and loads the DAC only when the offset changed. Their arithmetic
 * between the waits is far below a frame and is not charged. */
#include <string.h>
#include "vg.h"

void vg_dac_set(const uint8_t *pal)
{
    uint8_t rgb[VG_PAL_BYTES];
    int i;

    lrv_sys_frame_wait(&vg.sys);
    for (i = 0; i < 16; i++) {
        rgb[3 * i] = pal[i];
        rgb[3 * i + 1] = pal[16 + i];
        rgb[3 * i + 2] = pal[32 + i];
    }
    lrv_screen_set_palette(&vg.screen, rgb);
    if (vg.gfx.on_dac)
        vg.gfx.on_dac(vg.gfx.on_dac_ctx, pal);
}

void vg_pal_set(const uint8_t *pal)
{
    if (!vg.gfx.ready)
        return;
    memmove(vg.gfx.pal_cur, pal, VG_PAL_BYTES);
    vg_dac_set(vg.gfx.pal_cur);
}

static int pal_max(const uint8_t *pal)
{
    int i, m = 0;
    for (i = 0; i < VG_PAL_BYTES; i++)
        if (pal[i] > m)
            m = pal[i];
    return m;
}

static int pal_min(const uint8_t *pal)
{
    int i, m = 15;
    for (i = 0; i < VG_PAL_BYTES; i++)
        if (pal[i] < m)
            m = pal[i];
    return m;
}

/* s * a / t as the fades compute it: 32-bit, toward zero */
static int step(int s, int32_t a, int32_t t)
{
    return (int)((int32_t)((uint32_t)(int32_t)s * (uint32_t)a) / t);
}

/* the fades' loop: once per VSYNC until the slot is done, d = offset(elapsed); a DAC load when
 * d differs from *last (a static kept across calls) */
static void fade(const uint8_t *base, int h, int s, int32_t t, int in, int *last)
{
    uint8_t tmp[VG_PAL_BYTES];

    while (!vg_timer_done(h)) {
        int32_t e = vg_timer_elapsed(h);
        int d;
        if (e == -1)
            break;
        if (t == 0)                     /* op 2Fh with t below 2: _aFldiv divides by 0 */
            vg_runtime_error(VG_R6003);
        d = in ? step(s, t - e, t) : step(s, e, t);
        if (d != *last) {
            *last = d;
            lrv_pal_shift(tmp, base, VG_PAL_BYTES, d, 15);  /* 0315:0202 */
            vg_dac_set(tmp);
        }
        while (vg_timer_elapsed(h) == e)        /* until the next VSYNC */
            lrv_sys_frame_wait(&vg.sys);
    }
    vg_timer_free(h);
}

void vg_pal_fade_in(const uint8_t *pal, int t)
{
    uint8_t target[VG_PAL_BYTES];
    int h, s;

    if (!vg.gfx.ready)
        return;
    memmove(target, pal, VG_PAL_BYTES);
    h = vg_timer_start(t);
    if (h) {
        s = pal_min(vg.gfx.pal_cur) == 15 ? 15 - pal_min(target) : -pal_max(target);
        fade(target, h, s, t, 1, &vg.gfx.fade_in_last);
    }
    vg_pal_set(target);
}

void vg_pal_op30(const uint8_t *pal, int t)
{
    uint8_t target[VG_PAL_BYTES];
    if (!vg.gfx.ready)
        return;
    memmove(target, pal, VG_PAL_BYTES);
    if (t > 0)
        vg_pal_fade_in(target, t);
    vg_pal_set(target);
}

void vg_pal_fade_out(int to_white, int t)
{
    const uint8_t *end = to_white ? vg.gfx.pal_white : vg.gfx.pal_black;
    uint8_t base[VG_PAL_BYTES];
    int h;

    if (!vg.gfx.ready)
        return;
    if (t >= 1 && (h = vg_timer_start(t)) != 0) {
        memcpy(base, vg.gfx.pal_cur, VG_PAL_BYTES);
        fade(base, h, to_white ? 15 - pal_min(base) : -pal_max(base), t, 0,
             &vg.gfx.fade_out_last);
    }
    vg_pal_set(end);
}

void vg_pal_flash(int t)
{
    uint8_t saved[VG_PAL_BYTES];
    int half = t / 2;                   /* cdq; sub ax, dx; sar ax, 1: toward zero */

    memcpy(saved, vg.gfx.pal_cur, VG_PAL_BYTES);
    vg_pal_fade_out(1, half);
    vg_pal_fade_in(saved, half);
    vg_pal_set(saved);
}
