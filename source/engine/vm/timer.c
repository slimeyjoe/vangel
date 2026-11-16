/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The VSYNC timer: docs/re/platform.md §2, M.EXE segments 0752 (the wrappers, which check
 * that the timer is installed) and 075A (the slots and the handler). */
#include <string.h>
#include "vg.h"

/* 075A:00A6, once per VSYNC */
static void timer_tick(void *ctx)
{
    struct vg_timers *tm = ctx;
    int i;

    tm->vsync++;
    for (i = 0; i < VG_TIMERS; i++) {
        struct vg_timer *s = &tm->slot[i];
        if (s->used && !s->done) {
            s->elapsed++;
            if (s->elapsed >= s->target)
                s->done = 1;
        }
    }
}

void vg_timer_install(void)
{
    struct vg_timers *tm = &vg.timers;
    if (tm->installed)
        return;
    memset(tm->slot, 0, sizeof tm->slot);
    tm->busy = 0;
    if (lrv_sys_add_hook(&vg.sys, LRV_HOOK_TICK, timer_tick, tm) != LRV_OK)
        lrv_fatal(vg.hal, "the timer cannot be installed");
    tm->installed = 1;
}

void vg_timer_remove(void)
{
    if (!vg.timers.installed)
        return;
    lrv_sys_remove_hook(&vg.sys, LRV_HOOK_TICK, timer_tick, &vg.timers);
    vg.timers.installed = 0;
}

/* a * b / c as _aFlmul and _aFldiv do it: a 32-bit product, a division toward zero */
static int32_t mul_div(int32_t a, int32_t b, int32_t c)
{
    return (int32_t)((uint32_t)a * (uint32_t)b) / c;
}

static struct vg_timer *slot_of(int h)
{
    if (!vg.timers.installed || h < 1 || h > VG_TIMERS || !vg.timers.slot[h - 1].used)
        return NULL;
    return &vg.timers.slot[h - 1];
}

int vg_timer_start(int32_t t)
{
    struct vg_timers *tm = &vg.timers;
    int i;

    if (!tm->installed || tm->busy == VG_TIMERS)
        return 0;
    for (i = 0; i < VG_TIMERS; i++) {
        struct vg_timer *s = &tm->slot[i];
        if (s->used)
            continue;
        s->used = 1;
        s->done = 0;
        s->elapsed = 0;
        s->target = mul_div(t, 564, 1000);
        s->t = t;
        tm->busy++;
        return i + 1;
    }
    return 0;
}

int vg_timer_done(int h)
{
    struct vg_timer *s = slot_of(h);
    return s ? s->done : 0;
}

int32_t vg_timer_elapsed(int h)
{
    struct vg_timer *s = slot_of(h);
    if (!s)
        return -1;
    return s->done ? s->t : mul_div(s->elapsed, 1000, 564);
}

int vg_timer_free(int h)
{
    struct vg_timer *s = slot_of(h);
    if (!s)
        return 0;
    s->used = 0;
    vg.timers.busy--;
    return 1;
}
