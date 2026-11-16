/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_text: the engine's text, menus and input (engine/text/, engine/bios/) for
 * tests/check_text.py and tests/check_menu.py, which run the same statements on the original
 * under emulation (tests/textrig.py) and compare what both record.
 *
 *   test_text PAK COUNT MASK     COUNT: the messages of the text file (the scenario's tag 7),
 *                                MASK: the input devices (1 keyboard, 2 mouse); then the
 *                                commands on stdin, one per line:
 *     scene                      va_main and va_mw01 drawn as the first scene
 *     input MASK                 the input closed and opened again with these devices
 *     fill / free                all 16 timer slots taken / given back
 *     ev F scan HH               at frame F of the next run: byte HH from the keyboard
 *     ev F mouse X Y B           ... the mouse at (X, Y), buttons B (1 left, 2 right)
 *     mouse X Y B                the mouse there now (before a run)
 *     msg N                      statement 19h N
 *     menu STMT HEX...           statement 24h of statement STMT with these choices (hex)
 *     isr HH                     byte HH from the keyboard now (INT 09h)
 *     poll                       input_poll: prints "poll R" and the reading: joystick,
 *                                keyboard, mouse (changed and values)
 *     release MASK               input_wait_release: prints "release F", the frames it took
 * A run prints its events "F kind arg crc" (frames from its start; tests/textrig.py has the
 * kinds), then "v1 V" and "end". The keyboard's bytes go straight to the engine's INT 09h
 * handler (vg_kbd_isr); the mouse through the HAL's poll, as the frame's input. */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

#define MAXEV 4096

static struct { uint32_t f; int scan, x, y, b; } evs[MAXEV];
static int nev;
static uint32_t base;
static int mx = 320, my = 200, mb;

static uint32_t crc_table[256];

static void crc_init(void)
{
    uint32_t i, c;
    int k;
    for (i = 0; i < 256; i++) {
        c = i;
        for (k = 0; k < 8; k++)
            c = c & 1 ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        crc_table[i] = c;
    }
}

static uint32_t crc32(uint32_t c, const uint8_t *p, size_t n)
{
    c = ~c;
    while (n--)
        c = crc_table[(c ^ *p++) & 0xFF] ^ (c >> 8);
    return ~c;
}

static uint32_t window_crc(void)
{
    uint32_t c = 0;
    int q, l;
    for (q = 0; q < 4; q++)
        for (l = 0; l < VG_WIN_H; l++)
            c = crc32(c, vg.screen.page[0].plane[q] + VG_WIN_OFF + l * VG_PLANE_STRIDE,
                      VG_WIN_WB);
    return c;
}

static uint32_t page_crc(void)
{
    uint32_t c = 0;
    int q;
    for (q = 0; q < 4; q++)
        c = crc32(c, vg.screen.page[0].plane[q], VG_PLANE_BYTES);
    return c;
}

static void on_event(void *ctx, int event, int arg)
{
    static const char *const names[] = { "", "show", "icon1", "icon0", "restore", "invert" };
    uint32_t f = vg.sys.frame - base;
    (void)ctx;
    printf("%u %s %d %u\n", (unsigned)f, names[event], arg,
           (unsigned)(event == VG_TEV_RESTORE ? page_crc() : window_crc()));
}

static void on_pointer(void *ctx, int shown)
{
    (void)ctx;
    printf("%u ptr %d 0\n", (unsigned)(vg.sys.frame - base), shown);
}

/* the script's events of the new frame (after the timer's tick: the VSYNC first) */
static void tick(void *ctx)
{
    uint32_t f = vg.sys.frame - base;
    int i;
    (void)ctx;
    for (i = 0; i < nev; i++) {
        if (evs[i].f != f)
            continue;
        if (evs[i].scan >= 0) {
            vg_kbd_isr((uint8_t)evs[i].scan);
        } else {
            mx = evs[i].x;
            my = evs[i].y;
            mb = evs[i].b;
        }
    }
}

static void poll(struct lrv_input *in)
{
    in->mouse_abs = 1;
    in->mouse_x = mx;
    in->mouse_y = my;
    in->buttons = (unsigned)mb;
}

static int hexstr(const char *s, uint8_t *out, int max)
{
    int n = 0;
    unsigned v;
    while (s[0] && s[1] && n < max - 1 && sscanf(s, "%2x", &v) == 1) {
        out[n++] = (uint8_t)v;
        s += 2;
    }
    out[n] = 0;
    return n;
}

int main(int argc, char **argv)
{
    static struct lrv_hal hal;
    static char line[2048];
    static uint8_t items[VG_MENU_MAX][256];
    struct lrv_video_mode mode = lrv_pc98_video_mode;
    const struct lrv_pack_entry *e;
    int held[VG_TIMERS], count, mask, i;

    if (argc != 4) {
        fprintf(stderr, "usage: test_text PAK COUNT MASK < commands\n");
        return 2;
    }
    count = atoi(argv[2]);
    mask = atoi(argv[3]);
    crc_init();
    th_hal(&hal, argv[1], NULL, NULL);
    hal.input_poll = poll;
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    if (lrv_pack_open(&vg.pak, &hal, LRV_PACK_MAIN) != LRV_OK ||
        lrv_screen_init(&vg.screen, &hal, &mode, 2, 1, LRV_MEM_ANY) != LRV_OK)
        return 1;
    e = lrv_pack_find(&vg.pak, "GDATA.LIB", VG_PT_LIBRARY);
    if (!e || gf_lib_open(&vg.lib, &hal, &vg.pak, e) != LRV_OK)
        return 1;
    lrv_sys_init(&vg.sys, &hal, mode.w, mode.h);
    vg_gfx_load_builtin();
    vg_text_load_fonts();
    if (!vg_txb_load("CMD00.TXB", count)) {
        fprintf(stderr, "test_text: the message file does not load\n");
        return 1;
    }
    vg_timer_install();
    vg.input.kbd_external = 1;
    if (!vg_input_init((unsigned)mask))
        return 1;
    lrv_sys_add_hook(&vg.sys, LRV_HOOK_TICK, tick, NULL);
    vg_gfx_init();
    vg.text.on_event = on_event;
    vg.input.on_pointer = on_pointer;

    while (fgets(line, sizeof line, stdin)) {
        char op[16];
        int a, b, c, d, f;
        unsigned ux;
        if (sscanf(line, "%15s", op) != 1)
            continue;
        if (!strcmp(op, "scene")) {
            vg_pic_load(10, 0, 0, 0, "va_main");
            vg_pic_load(10, 32, 300, 1, "va_mw01");
        } else if (!strcmp(op, "input") && sscanf(line, "%*s %d", &a) == 1) {
            vg_input_term();
            vg_input_init((unsigned)a);
        } else if (!strcmp(op, "fill")) {
            for (i = 0; i < VG_TIMERS; i++)
                held[i] = vg_timer_start(1000);
        } else if (!strcmp(op, "free")) {
            for (i = 0; i < VG_TIMERS; i++)
                vg_timer_free(held[i]);
        } else if (!strcmp(op, "ev")) {
            if (nev >= MAXEV)
                return 1;
            if (sscanf(line, "%*s %d scan %x", &f, &ux) == 2) {
                a = (int)ux;
                evs[nev].f = (uint32_t)f;
                evs[nev++].scan = a;
            } else if (sscanf(line, "%*s %d mouse %d %d %d", &f, &a, &b, &c) == 4) {
                evs[nev].f = (uint32_t)f;
                evs[nev].scan = -1;
                evs[nev].x = a;
                evs[nev].y = b;
                evs[nev++].b = c;
            }
        } else if (!strcmp(op, "mouse") && sscanf(line, "%*s %d %d %d", &a, &b, &c) == 3) {
            vg.sys.mouse_x = vg.sys.in.mouse_x = mx = a;
            vg.sys.mouse_y = vg.sys.in.mouse_y = my = b;
            vg.sys.in.buttons = (unsigned)(mb = c);
        } else if (!strcmp(op, "isr") && sscanf(line, "%*s %x", &ux) == 1) {
            vg_kbd_isr((uint8_t)ux);
        } else if (!strcmp(op, "poll")) {
            struct vg_poll p;
            memset(&p, 0, sizeof p);
            a = vg_input_poll(&p);
            printf("poll %d %d %d %d %d %d %d %d %d %d %d %d %d\n", a, p.joy.changed, p.joy.a,
                   p.joy.b, p.kbd.changed, p.kbd.event, p.kbd.code, p.mouse.changed, p.mouse.x,
                   p.mouse.y, p.mouse.right, p.mouse.left, p.mouse.zero);
        } else if (!strcmp(op, "release") && sscanf(line, "%*s %d", &a) == 1) {
            base = vg.sys.frame;
            vg_input_release((unsigned)a);
            printf("release %u\n", (unsigned)(vg.sys.frame - base));
            nev = 0;
        } else if (!strcmp(op, "msg") && sscanf(line, "%*s %d", &a) == 1) {
            base = vg.sys.frame;
            d = vg_op19(a);
            printf("v1 %d\nend\n", d);
            nev = 0;
        } else if (!strcmp(op, "menu")) {
            struct vg_menu m;
            char *p = line;
            long stmt;
            if (sscanf(line, "%*s %ld", &stmt) != 1)
                return 1;
            memset(&m, 0, sizeof m);
            p = strchr(p, ' ');
            p = p ? strchr(p + 1, ' ') : NULL;
            while (p && m.n < VG_MENU_MAX) {
                char hex[600];
                if (sscanf(p, " %599s", hex) != 1)
                    break;
                hexstr(hex, items[m.n], (int)sizeof items[0]);
                m.item[m.n] = items[m.n];
                m.n++;
                p = strchr(p + 1, ' ');
            }
            base = vg.sys.frame;
            d = vg_op24(stmt, &m);
            printf("v1 %d\nend\n", d);
            nev = 0;
        } else {
            printf("bad command %s", line);
        }
        fflush(stdout);
    }
    vg_input_term();
    vg_timer_remove();
    vg_txb_free();
    vg_text_free_fonts();
    gf_lib_close(&vg.lib);
    lrv_screen_free(&vg.screen);
    lrv_pack_close(&vg.pak);
    return 0;
}
