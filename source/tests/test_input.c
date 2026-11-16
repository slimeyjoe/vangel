/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_input: the keyboard as the engine models it (engine/bios/input.c), without game data.
 * lrvne delivers key presses and a key-down map per poll; the engine turns every poll's
 * changes into the scan codes a PC-98 keyboard sends (breaks, then makes) and feeds each to
 * the original's INT 09h handler, whose latch keeps the last code (tests/check_input.py
 * compares that handler with the original's). Checked here: what a program polling the
 * latch then sees, frame by frame. */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, \
                                                    #c); } } while (0)

/* the host's input of the next poll */
static struct lrv_input next;

static void poll(struct lrv_input *in)
{
    *in = next;
    next.nkeys = 0;
}

static void press(int key)
{
    next.keys[next.nkeys].key = (uint8_t)key;
    next.nkeys++;
    lrv_key_set(&next, key, 1);
}

static void up(int key)
{
    lrv_key_set(&next, key, 0);
}

/* a frame, then what kbd_poll reads: the event and its code, -1 for no event */
static int frame_read(void)
{
    struct vg_poll p;
    vg_frame();
    memset(&p, 0, sizeof p);
    vg_input_poll(&p);
    return p.kbd.event ? p.kbd.code : -1;
}

int main(void)
{
    static struct lrv_hal hal;
    int k;

    th_hal(&hal, "none", NULL, NULL);
    hal.input_poll = poll;
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    lrv_sys_init(&vg.sys, &hal, 640, 400);
    CHECK(vg_input_init(VG_DEV_KBD) == 1);
    CHECK(frame_read() == -1);

    /* a press is an event at once, its release none; the event is read once */
    press(LRV_K_RETURN);
    CHECK(frame_read() == VG_KEY_RETURN);
    CHECK(frame_read() == -1);
    up(LRV_K_RETURN);
    CHECK(frame_read() == -1);

    /* ESC counts when it is let go */
    press(LRV_K_ESC);
    CHECK(frame_read() == -1);
    CHECK(frame_read() == -1);
    up(LRV_K_ESC);
    CHECK(frame_read() == VG_KEY_ESC);

    /* a tap shorter than a poll: lrvne holds it down for that poll, so it is a press there
     * and a release at the next; ESC's comes with the release */
    press(LRV_K_SPACE);
    up(LRV_K_SPACE);
    CHECK(frame_read() == VG_KEY_SPACE);
    CHECK(frame_read() == -1);
    press(LRV_K_ESC);
    up(LRV_K_ESC);
    CHECK(frame_read() == -1);
    CHECK(frame_read() == VG_KEY_ESC);

    /* pressed and let go while the program does not look: the release overwrote it */
    press(LRV_K_A);
    vg_frame();
    up(LRV_K_A);
    vg_frame();
    CHECK(frame_read() == -1);
    /* ... but held, it is still there when the program looks */
    press(LRV_K_A);
    for (k = 0; k < 5; k++)
        vg_frame();
    CHECK(frame_read() == 0);
    up(LRV_K_A);
    CHECK(frame_read() == -1);

    /* two presses in one poll: the latch keeps the last */
    press(LRV_K_RETURN);
    press(LRV_K_UP);
    CHECK(frame_read() == VG_KEY_UP);
    /* a release and a press in one poll: the release first */
    up(LRV_K_RETURN);
    up(LRV_K_UP);
    press(LRV_K_DOWN);
    CHECK(frame_read() == VG_KEY_DOWN);
    up(LRV_K_DOWN);
    CHECK(frame_read() == -1);

    /* the shift keys come without a press: held, they are a key (with no code) */
    lrv_key_set(&next, LRV_K_SHIFT, 1);
    CHECK(frame_read() == 0);
    lrv_key_set(&next, LRV_K_SHIFT, 0);
    CHECK(frame_read() == -1);

    /* auto-repeat: another press of a held key is another make */
    press(LRV_K_LEFT);
    CHECK(frame_read() == VG_KEY_LEFT);
    CHECK(frame_read() == -1);
    press(LRV_K_LEFT);
    CHECK(frame_read() == VG_KEY_LEFT);
    up(LRV_K_LEFT);
    CHECK(frame_read() == -1);

    /* keys the PC-98 has not: nothing */
    press(LRV_K_F12);
    CHECK(frame_read() == -1);
    up(LRV_K_F12);
    CHECK(frame_read() == -1);

    vg_input_term();
    if (fails) {
        fprintf(stderr, "test_input: %d failed\n", fails);
        return 1;
    }
    printf("test_input: ok\n");
    return 0;
}
