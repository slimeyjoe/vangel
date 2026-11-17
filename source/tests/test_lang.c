/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_lang: where the engine draws a translation, for tests/check_lang.py, which compares it
 * with tools/vglayout.py (the reference, lrvne's reflow in Python).
 *
 *   test_lang PAK LANG
 *
 * In language LANG it plays every message (statement 19h), shows every menu (24h), runs the
 * prologue, the staff roll, the notice and the music mode, and asks the console's question;
 * every page wait is answered with RETURN, a timed one runs its time. It prints
 *     msg N                    then per page its lines "line ROW COL U HEX" (U 1: a
 *                              translation's) and "page MODE CELLS", then "v1 V"
 *     menu M                   then the lines of its choices
 *     tl WHERE PAGE ROW COL HEX    a translated line of a built-in or the console
 *     icon N                   message pages that drew under the page-wait icon
 *     done
 * The keyboard's bytes go to the engine's INT 09h handler at the next VSYNC; the music layer
 * is a stand-in that has a driver and plays nothing. */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

static int press;                       /* RETURN at the next VSYNC: 1 make, 2 break */
static int want_y;                      /* Y for the console's question at the next poll */
static int scan = 0x1C;                 /* the key pressed: RETURN, ESC for the music mode */
static int icon_bad, in_msg;            /* (menus have no page-wait icon) */

static void hex(const uint8_t *s, uint32_t n)
{
    uint32_t i;
    for (i = 0; i < n; i++)
        printf("%02x", s[i]);
    if (!n)
        printf("-");
}

static void on_line(void *ctx, int row, int col, const uint8_t *s, uint32_t n, int utf8)
{
    (void)ctx;
    printf("line %d %d %d ", row, col, utf8);
    hex(s, n);
    printf("\n");
}

static void on_text(void *ctx, int where, int page, int row, int col, const uint8_t *s,
                    uint32_t n)
{
    (void)ctx;
    printf("tl %d %d %d %d ", where, page, row, col);
    hex(s, n);
    printf("\n");
}

/* row 3, columns 66-67 of the window: the page-wait icon's cell (msg_icon) */
static int icon_cell_clean(void)
{
    int q, r;
    for (q = 0; q < 4; q++)
        for (r = 0; r < 16; r++) {
            unsigned o = 3 * 0x550 + 66 + 0x88 + (unsigned)r * VG_WIN_WB;
            if (memcmp(vg.gfx.win_work[q] + o, vg.gfx.win_save[q] + o, 2))
                return 0;
        }
    return 1;
}

static void on_event(void *ctx, int event, int arg)
{
    (void)ctx;
    if (event == VG_TEV_SHOW && in_msg && !icon_cell_clean())
        icon_bad++;
    if (event == VG_TEV_PAGE)
        printf("page %d %d\n", arg >> 16, arg & 0xFFFF);
}

static void on_trace(const struct lrv_trace_event *ev)
{
    if (ev->kind == LRV_TR_WAIT && ev->a1 == 0 && ev->a0 == VG_WAIT_KEY)
        press = want_y = 1;
}

static void poll(struct lrv_input *in)
{
    if (want_y) {
        in->keys[0].key = LRV_K_Y;
        in->nkeys = 1;
        want_y = 0;
    }
}

static void tick(void *ctx)
{
    (void)ctx;
    if (press == 1) {
        vg_kbd_isr((uint8_t)scan);
        press = 2;
    } else if (press == 2) {
        vg_kbd_isr((uint8_t)(scan | 0x80));
        press = 0;
    }
}

static int mus_init(void) { return 1; }
static int mus_play(const char *name, int vol) { (void)name; (void)vol; return 1; }
static int mus_fade(int t) { (void)t; return 1; }

int main(int argc, char **argv)
{
    static struct lrv_hal hal;
    struct lrv_video_mode mode = lrv_pc98_video_mode;
    const struct lrv_pack_entry *e;
    uint8_t *scb;
    uint32_t size;
    int i;

    if (argc != 3) {
        fprintf(stderr, "usage: test_lang PAK LANG\n");
        return 2;
    }
    th_hal(&hal, argv[1], NULL, NULL);
    hal.trace = on_trace;
    hal.input_poll = poll;
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    if (lrv_pack_open(&vg.pak, &hal, LRV_PACK_MAIN) != LRV_OK ||
        lrv_screen_init(&vg.screen, &hal, &mode, 2, 1, LRV_MEM_ANY) != LRV_OK)
        return 1;
    lrv_pack_set_lang(&vg.pak, lrv_pack_lang_id(&vg.pak, argv[2]));
    e = lrv_pack_find(&vg.pak, "GDATA.LIB", VG_PT_LIBRARY);
    if (!e || gf_lib_open(&vg.lib, &hal, &vg.pak, e) != LRV_OK)
        return 1;
    e = lrv_pack_find(&vg.pak, "CMD00.SCB", VG_PT_SCENARIO);
    if (!e || !(scb = lrv_pack_load(&vg.pak, e, &size)) || vg_scb_load(scb, size) != VG_EXIT_OK) {
        fprintf(stderr, "test_lang: the scenario does not load\n");
        return 1;
    }
    lrv_sys_init(&vg.sys, &hal, mode.w, mode.h);
    vg_gfx_load_builtin();
    vg_text_load_fonts();
    vg_lang_init();
    if (!vg_lang_active()) {
        fprintf(stderr, "test_lang: the pack has no translation for %s\n", argv[2]);
        return 1;
    }
    vg_bi_load();
    vg.bi.mus.init = mus_init;
    vg.bi.mus.play = mus_play;
    vg.bi.mus.fade_stop = mus_fade;
    if (!vg_txb_load("CMD00.TXB", vg.vm.scb.n_msg)) {
        fprintf(stderr, "test_lang: the message file does not load\n");
        return 1;
    }
    vg_timer_install();
    vg.input.kbd_external = 1;
    if (!vg_input_init(1))
        return 1;
    lrv_sys_add_hook(&vg.sys, LRV_HOOK_TICK, tick, NULL);
    vg_gfx_init();
    vg_pic_load(10, 0, 0, 0, "va_main");
    vg_pic_load(10, 32, 300, 1, "va_mw01");
    vg.text.on_event = on_event;
    vg.text.on_line = on_line;
    vg.text.on_text = on_text;

    in_msg = 1;
    for (i = 1; i <= vg.vm.scb.n_msg; i++) {
        printf("msg %d\n", i);
        printf("v1 %d\n", vg_op19(i));
    }
    in_msg = 0;
    for (i = 1; i <= vg.vm.scb.n_menu; i++) {
        printf("menu %d\n", i);
        vg_op24(-i, &vg.vm.scb.menu[i]);
    }
    vg.text.on_line = NULL;
    vg_builtin(1);
    vg_builtin(2);
    vg_builtin(3);
    scan = 0x00;                        /* ESC */
    vg_builtin(4);
    strcpy(vg.profile.mouse, "ask");
    press = 0;
    vg_console_ask(1);
    printf("icon %d\ndone\n", icon_bad);

    vg_input_term();
    vg_timer_remove();
    vg_txb_free();
    vg_bi_free();
    vg_msg_free();
    vg_lang_free();
    vg_text_free_fonts();
    vg_scb_free();
    lrv_pack_free(&vg.pak, scb, size);
    gf_lib_close(&vg.lib);
    lrv_screen_free(&vg.screen);
    lrv_pack_close(&vg.pak);
    return 0;
}
