/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Statement 24h: op_24 (001E:0A8D), menu_draw (0315:0C4F), menu_update (0315:0CC9) and
 * menu_loop (001E:0B2B). docs/re/text.md §4.
 *
 * The choices are drawn into the window like a page; the current one is marked by inverting
 * its bar in VRAM. The mouse selects the choice under the pointer whenever its reading
 * changes, the left button takes the current one; UP / DOWN move with wrap-around, RETURN
 * takes it. There is no cancel. */
#include <string.h>
#include "vg.h"

/* the menu's state as menu_draw leaves it (the original's 0x24-byte record) */
struct menu_state {
    int n, sel;
    struct vg_menu_rect r[VG_MENU_MAX];
};

static int menu_draw(const struct vg_menu *m, struct menu_state *st)
{
    int i;
    vg_win_clear();
    for (i = 0; i < m->n; i++)
        if (!vg_menu_choice(m->item[i], &st->r[i], i))
            return 0;
    st->n = m->n;
    st->sel = 0;
    vg_win_show();
    return 1;
}

static int hit(const struct vg_menu_rect *r, int x, int y)
{
    return r->x0 <= x && x <= r->x1 && r->y0 <= y && y <= r->y1;
}

static void menu_update(struct menu_state *st, const struct vg_poll *p)
{
    int cur = st->sel, sel = cur, i;

    if (p->mouse.changed == 1) {
        for (i = 0; i < st->n; i++) {
            if (i == cur || !hit(&st->r[i], p->mouse.x, p->mouse.y))
                continue;
            if (cur != -1)
                vg_rect_invert(&st->r[cur]);
            vg_rect_invert(&st->r[i]);
            sel = i;
            break;
        }
    }
    if (p->kbd.event == 1) {
        int d = 0;
        switch (p->kbd.code & 0x1FF) {
        case VG_KEY_UP:   d = -1; break;
        case VG_KEY_DOWN: d = 1; break;
        default: break;
        }
        if (sel == -1) {
            vg_rect_invert(&st->r[0]);
            sel = 0;
        } else if (d) {
            vg_rect_invert(&st->r[sel]);
            sel = (d + st->n + sel) % st->n;
            vg_rect_invert(&st->r[sel]);
        }
        vg_input_release(VG_DEV_KBD);
    }
    /* (the joystick's up and down, p->joy.a, never come: it does not open) */
    st->sel = sel;
}

static void menu_loop(struct menu_state *st)
{
    struct vg_poll p;
    int done = 0;

    if (st->sel == -1) {
        memset(&p, 0, sizeof p);
        vg_input_poll(&p);
        menu_update(st, &p);
        if (st->sel == -1) {
            st->sel = 0;
            vg_rect_invert(&st->r[0]);
        }
    } else {
        vg_rect_invert(&st->r[st->sel]);
    }
    vg_wait_begin(VG_WAIT_KEY);
    for (;;) {
        memset(&p, 0, sizeof p);
        if (vg_input_poll(&p) != 1)
            break;
        menu_update(st, &p);
        if (p.kbd.event == 1 && (p.kbd.code & 0x1FF) == VG_KEY_RETURN) {
            vg_input_release(VG_DEV_KBD);
            done = 1;
        }
        if (p.mouse.left == 1) {
            vg_input_release(VG_DEV_MOUSE);
            done = 1;
        }
        if (p.joy.b & 0x10) {
            vg_input_release(VG_DEV_JOY);
            done = 1;
        }
        if (done || vg_frame())
            break;
    }
    vg_wait_end(VG_WAIT_KEY);
}

int vg_op24(long stmt, const struct vg_menu *m)
{
    struct menu_state st;
    int si;

    memset(&st, 0, sizeof st);
    if (stmt == vg.text.menu_last) {
        si = vg.text.menu_choice;
    } else {
        si = 0;
        vg.text.menu_last = stmt;
    }
    menu_draw(m, &st);
    st.sel = si - 1;
    menu_loop(&st);
    si = st.sel + 1;
    vg.text.menu_choice = si;
    if (si < 1 || st.n < si)
        si = 1;
    vg_win_restore();                   /* menu_erase: op 18h */
    vg_text_event(VG_TEV_RESTORE, 0);
    return si;
}
