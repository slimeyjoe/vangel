/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The keyboard (0401:0228 the INT 09h handler, 0401:0317 kbd_poll), the joystick stub and the
 * device layer of segment 043A: input_init, input_poll, input_wait_release.
 * docs/re/platform.md §3. */
#include <string.h>
#include "vg.h"

/* ---- the keyboard ------------------------------------------------------------------------- */

void vg_kbd_isr(uint8_t data)
{
    /* the scan code without the release bit; the flag is bit 7 of -data: 1 for the make codes
     * 01h..7Fh and for 80h, the release of ESC (scan code 0), 0 otherwise */
    vg.input.kbd_scan = (uint8_t)(data & 0x7F);
    vg.input.kbd_make = (uint8_t)(((uint8_t)-data >> 7) & 1);
}

/* The keyboard of one poll (vg.sys.in) as the codes it sent: the keys let go since the poll
 * fed before (break codes, in scan-code order), then the presses of the poll in their order,
 * then keys held now that came without a press (the shift keys and the locks). */
static void kbd_feed_poll(void)
{
    uint8_t now[LRV_PC98_KEYMAP_BYTES], made[LRV_PC98_KEYMAP_BYTES];
    struct lrv_keypress k;
    int i, s;

    lrv_pc98_keymap(&vg.sys.in, 0, now);
    memset(made, 0, sizeof made);
    for (s = 0; s < 0x80; s++)
        if (lrv_pc98_key_down(vg.input.kbd_down, s) && !lrv_pc98_key_down(now, s))
            vg_kbd_isr((uint8_t)(s | 0x80));
    for (i = 0; i < vg.sys.in.nkeys; i++) {
        s = lrv_pc98_scan(vg.sys.in.keys[i].key, 0);
        if (s == LRV_PC98_K_NONE || s >= 0x80)
            continue;
        vg_kbd_isr((uint8_t)s);
        made[s >> 3] |= (uint8_t)(1u << (s & 7));
    }
    for (s = 0; s < 0x80; s++)
        if (lrv_pc98_key_down(now, s) && !lrv_pc98_key_down(vg.input.kbd_down, s) &&
            !lrv_pc98_key_down(made, s))
            vg_kbd_isr((uint8_t)s);
    memcpy(vg.input.kbd_down, now, sizeof now);
    /* the presses were taken here; lrvne's queue of them is not used */
    while (lrv_sys_key_read(&vg.sys, &k))
        ;
}

/* Feeds the polls not fed yet: the one of frame n (the poll lrv_sys_frame_wait made when the
 * frame count became n). Called by the tick hook (for the poll before) and by every read of
 * the keyboard (for the latest), so each poll goes through the latch once, in order, whether
 * the program reads the keyboard then or not. */
static void kbd_feed(uint32_t n)
{
    if (vg.input.kbd_external || n < 1 || n + 1 <= vg.input.kbd_fed ||
        lrv_sys_quitting(&vg.sys))
        return;
    kbd_feed_poll();
    vg.input.kbd_fed = n + 1;
}

static void kbd_tick(void *ctx)
{
    (void)ctx;
    kbd_feed(vg.sys.frame - 1);
}

/* kbd_open (0401:030A): the handler replaces INT 09h */
static int kbd_open(void)
{
    vg.input.kbd_scan = 0;
    vg.input.kbd_make = 0;
    lrv_pc98_keymap(&vg.sys.in, 0, vg.input.kbd_down);
    vg.input.kbd_fed = vg.sys.frame + 1;            /* what is held now is not a press */
    if (lrv_sys_add_hook(&vg.sys, LRV_HOOK_TICK, kbd_tick, NULL) != LRV_OK)
        return 0;
    return 1;
}

static void kbd_close(void)
{
    lrv_sys_remove_hook(&vg.sys, LRV_HOOK_TICK, kbd_tick, NULL);
}

/* kbd_poll (0401:0317) */
static void kbd_read(struct vg_reading_kbd *r)
{
    kbd_feed(vg.sys.frame);
    r->event = 0;
    r->code = 0;
    if (vg.input.kbd_make != 1)
        return;
    vg.input.kbd_make = 0;
    r->event = 1;
    switch (vg.input.kbd_scan) {
    case LRV_PC98_K_ESC:    r->code = VG_KEY_ESC; break;
    case LRV_PC98_K_RETURN: r->code = VG_KEY_RETURN; break;
    case LRV_PC98_K_SPACE:  r->code = VG_KEY_SPACE; break;
    case LRV_PC98_K_UP:     r->code = VG_KEY_UP; break;
    case LRV_PC98_K_LEFT:   r->code = VG_KEY_LEFT; break;
    case LRV_PC98_K_RIGHT:  r->code = VG_KEY_RIGHT; break;
    case LRV_PC98_K_DOWN:   r->code = VG_KEY_DOWN; break;
    default: break;
    }
}

/* ---- the device layer (043A) -------------------------------------------------------------- */

int vg_input_init(unsigned want)
{
    struct vg_input *in = &vg.input;
    if (in->ready == 1)
        return 1;
    in->want = want;
    in->open = 0;
    if ((want & VG_DEV_KBD) && kbd_open())
        in->open |= VG_DEV_KBD;
    if ((want & VG_DEV_MOUSE) && vg_mouse_open())
        in->open |= VG_DEV_MOUSE;
    /* the joystick (0401:0004) never opens */
    if (!in->open)
        return 0;
    in->ready = 1;
    return 1;
}

void vg_input_term(void)
{
    struct vg_input *in = &vg.input;
    if (in->ready != 1)
        return;
    if (in->open & VG_DEV_KBD)
        kbd_close();
    if (in->open & VG_DEV_MOUSE)
        vg_mouse_close();
    in->open = 0;
    in->ready = 0;
}

/* input_kbd (043A:017A), input_joy (043A:011A), input_mouse (043A:009A): the reading, whether
 * it differs from the previous one, and 1 when the device is open (else a zero reading) */
static int input_kbd(struct vg_reading_kbd *r)
{
    struct vg_reading_kbd *l = &vg.input.kbd_last;
    if (!(vg.input.open & VG_DEV_KBD)) {
        r->event = r->code = 0;
        return 0;
    }
    kbd_read(r);
    r->changed = r->event != l->event || r->code != l->code;
    *l = *r;
    return 1;
}

static int input_joy(struct vg_reading_joy *r)
{
    r->a = r->b = 0;                    /* never open */
    (void)vg.input.joy_last;
    return 0;
}

static int input_mouse(struct vg_reading_mouse *r)
{
    struct vg_reading_mouse *l = &vg.input.mouse_last;
    if (!(vg.input.open & VG_DEV_MOUSE)) {
        r->x = r->y = r->zero = r->right = r->left = 0;
        return 0;
    }
    vg_mouse_read(r);
    /* the right button is not part of the comparison */
    r->changed = r->x != l->x || r->y != l->y || r->left != l->left || r->zero != l->zero;
    *l = *r;
    return 1;
}

int vg_input_poll(struct vg_poll *p)
{
    int k, j, m;
    if (vg.input.ready != 1)
        return 0;
    k = input_kbd(&p->kbd);
    j = input_joy(&p->joy);
    m = input_mouse(&p->mouse);
    return k == 1 || j == 1 || m == 1;
}

void vg_input_release(unsigned mask)
{
    if (mask & VG_DEV_KBD) {
        struct vg_reading_kbd r;
        while (input_kbd(&r) == 1 && r.event == 1)
            ;
    }
    if (mask & VG_DEV_MOUSE) {
        struct vg_reading_mouse r;
        while (input_mouse(&r) == 1 && r.left == 1)
            if (vg_frame())
                break;
    }
    if (mask & VG_DEV_JOY) {
        struct vg_reading_joy r;
        while (input_joy(&r) == 1 && (r.a || r.b))
            ;
    }
}

int vg_frame(void)
{
    lrv_sys_frame_wait(&vg.sys);
    return lrv_sys_quitting(&vg.sys);
}
