/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The VSYNC timer (docs/re/platform.md §2): M.EXE's handler of the vertical retrace interrupt
 * (075A:00A6) counts frames in DS:109E and advances 16 timer slots (0B91:0000); waits of the
 * scenario, fades and music fades take a slot. Here the handler is a tick hook of the frame:
 * one lrvne frame is one VSYNC. */
#ifndef VG_VM_TIMER_H
#define VG_VM_TIMER_H

#include <stdint.h>

#define VG_TIMERS 16

struct vg_timer {
    int used, done;
    int32_t elapsed;                    /* VSYNCs since the start */
    int32_t target;                     /* t * 564 / 1000: done when elapsed >= target */
    int32_t t;                          /* the time asked for, 1/100 s */
};

struct vg_timers {
    int installed;                      /* DS:109A */
    int busy;                           /* slots in use, DS:109C */
    uint16_t vsync;                     /* the frame counter DS:109E */
    struct vg_timer slot[VG_TIMERS];
};

/* 075A:000E: clears the slots and starts counting (the tick hook); the counter keeps its
 * value. vg_timer_remove (075A:0080) stops it. */
void vg_timer_install(void);
void vg_timer_remove(void);
/* 075A:011E: a slot for t hundredths of a second; its handle (slot + 1), or 0 when all are
 * busy or the timer is not installed. */
int     vg_timer_start(int32_t t);
/* 075A:025E: 1 once the slot's time is up (0 for a bad handle). */
int     vg_timer_done(int h);
/* 075A:01F7: the time since the start in 1/100 s (elapsed * 1000 / 564), t once done; -1 for a
 * bad handle or when the timer is not installed. */
int32_t vg_timer_elapsed(int h);
/* 075A:01B4: frees the slot; 1, or 0 for a bad handle. */
int     vg_timer_free(int h);

#endif
