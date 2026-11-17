/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Built-in 4 MUSMODE (0504:088E): the music mode, a list of the songs to play (docs/re/
 * platform.md §5.5, sound.md §4).
 *
 * Without a sound driver it refuses at once, and keeps refusing. Otherwise the list is drawn on
 * the 80-column grid, the selection inverse; UP and DOWN move it (no wrap), RETURN or SPACE
 * play the song (a song playing is faded out first, 1.5 s), ESC leaves (the song is faded out).
 * The mouse: a reading that changed moves the selection to the row under the pointer, the left
 * button plays it, the right button leaves. A turn without a key ends with a frame. */
#include <string.h>
#include "vg.h"

/* mus_select (0504:089D): redraws what changed */
static void mus_select(int sel)
{
    struct vg_bi *b = &vg.bi;
    int i;
    if (sel < 0 || b->mus_count - 1 < sel || b->mus_shown == sel)
        return;
    vg_mouse_hide();
    if (b->mus_shown == -1) {
        vg_bi_line(21, 0, b->str[VG_BI_MUSIC_HEADING], 0xE1);
        for (i = 0; i < b->mus_count; i++)
            vg_bi_line(20, i + 3, b->song[i].title, i == sel ? 0xE5 : 0xE1);
        vg_bi_line(3, 24, b->str[VG_BI_MUSIC_HELP], 0xE1);
    } else {
        vg_bi_line(20, b->mus_shown + 3, b->song[b->mus_shown].title, 0xE1);
        vg_bi_line(20, sel + 3, b->song[sel].title, 0xE5);
    }
    b->mus_shown = sel;
    vg_mouse_show();
}

/* mus_loop (0504:0994) */
static void mus_loop(void)
{
    struct vg_bi *b = &vg.bi;
    struct vg_poll p;
    int played = -1, sel = 0, quit = 0;

    memset(&p, 0, sizeof p);            /* (the original's record is not cleared) */
    vg_wait_begin(VG_WAIT_KEY);
    while (!quit) {
        mus_select(sel);
        vg_input_poll(&p);
        if (p.mouse.changed == 1) {
            int prev = sel, y = p.mouse.y, k, top;
            vg_input_release(VG_DEV_MOUSE);
            sel = prev;
            for (k = 0, top = 0x30; k < b->mus_count; k++, top += 16)
                if (y > top && top + 16 > y) {
                    sel = k;
                    break;
                }
            if (p.mouse.left == 1) {
                p.kbd.event = 1;
                p.kbd.code = VG_KEY_RETURN;
            } else if (p.mouse.right == 1) {
                quit = 1;
                continue;
            }
        }
        if (p.joy.b & 0x10) {
            p.kbd.event = 1;
            p.kbd.code = VG_KEY_RETURN;
            vg_input_release(VG_DEV_JOY);
        } else if (p.joy.b & 0x20) {
            quit = 1;
            vg_input_release(VG_DEV_JOY);
            continue;
        }
        if (p.joy.a & 1) {
            p.kbd.event = 1;
            p.kbd.code = VG_KEY_UP;
            vg_input_release(VG_DEV_JOY);
        } else if (p.joy.a & 2) {
            p.kbd.event = 1;
            p.kbd.code = VG_KEY_DOWN;
            vg_input_release(VG_DEV_JOY);
        }
        if (p.kbd.event != 1) {
            if (vg_frame())
                quit = 1;
            continue;
        }
        switch (p.kbd.code) {
        case VG_KEY_ESC:
            quit = 1;
            break;
        case VG_KEY_RETURN:
        case VG_KEY_SPACE:
            if (played == 0)
                b->mus.fade_stop(150);
            b->mus.play((const char *)b->song[sel].file, 100);
            played = 0;
            break;
        case VG_KEY_UP:
            if (sel > 0)
                sel--;
            break;
        case VG_KEY_DOWN:
            if (b->mus_count - 1 > sel)
                sel++;
            break;
        default:
            break;
        }
        vg_input_release(VG_DEV_KBD);
    }
    vg_wait_end(VG_WAIT_KEY);
    vg_input_release(VG_DEV_KBD);
    if (played == 0)
        b->mus.fade_stop(150);
}

void vg_bi_musmode(void)
{
    struct vg_bi *b = &vg.bi;
    vg_gfx_init();
    if (b->mus_mode != 2) {             /* mus_main (0504:0B0F) */
        if (b->mus.init() != 1) {
            b->mus_mode = 2;
        } else {
            for (b->mus_count = 0; b->song[b->mus_count].file; b->mus_count++)
                ;
            b->mus_mode = 1;
            b->mus_shown = -1;
            mus_loop();
        }
    }
    vg_gfx_init();
}
