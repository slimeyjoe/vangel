/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_bi: the engine's built-in sequences (engine/bi/) for tests/check_builtin.py, which runs
 * the same on the original under emulation and compares what both record.
 *
 *   test_bi PAK MASK             MASK: the input devices (1 keyboard, 2 mouse); then the
 *                                commands on stdin, one per line:
 *     pic BUF X Y FLAG NAME      op 31h: picture NAME into buffer BUF
 *     pal HEX                    op 30h with t = 0: the palette (48 hex digits, R G B), at
 *                                once (the set-up takes no time)
 *     input MASK                 the input closed and opened again with these devices
 *     fill / free                all 16 timer slots taken / given back
 *     driver 0|1                 what the music layer's init answers (the music mode)
 *     nofile                     announce.txt is not found from now on
 *     ev F scan HH               at frame F of the next run: byte HH from the keyboard
 *     ev F mouse X Y B           ... the mouse at (X, Y), buttons B (1 left, 2 right)
 *     bi N                       statement 25h N
 * A run prints, at every VSYNC where page 0 or the DAC changed, "F v CRC DAC" (frames from the
 * run's start; CRC-32 of page 0's four planes, the DAC as 48 hex digits R G B); "F ptr S" for
 * the pointer shown or hidden; "F mus init|play NAME VOL|fade T" for the music layer's calls;
 * then "F end V1 CRC0 CRC1 CRC12 DAC" (pages 0 and 1, buffer 12) and "end". */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

#define MAXEV 4096

static struct { uint32_t f; int scan, x, y, b; } evs[MAXEV];
static int nev;
static uint32_t base;
static int mx = 320, my = 200, mb;
static int running, driver = 1;
static uint32_t last_crc;
static uint8_t dac[VG_PAL_BYTES], last_dac[VG_PAL_BYTES];

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

static uint32_t surface_crc(const struct lrv_surface *s)
{
    uint32_t c = 0;
    int q;
    for (q = 0; q < 4; q++)
        c = crc32(c, s->plane[q], VG_PLANE_BYTES);
    return c;
}

static void hex(const uint8_t *p, char *out)
{
    int i;
    for (i = 0; i < VG_PAL_BYTES; i++)
        out[i] = "0123456789abcdef"[p[i] & 15];
    out[VG_PAL_BYTES] = 0;
}

static uint32_t now(void)
{
    return vg.sys.frame - base;
}

static void on_dac(void *ctx, const uint8_t *pal)
{
    (void)ctx;
    memcpy(dac, pal, sizeof dac);
}

static void on_pointer(void *ctx, int shown)
{
    (void)ctx;
    if (running)
        printf("%u ptr %d\n", (unsigned)now(), shown);
}

/* the VSYNC: what changed, then the script's events of the new frame */
static void tick(void *ctx)
{
    uint32_t f = now(), c;
    int i;
    (void)ctx;
    if (running) {
        c = surface_crc(&vg.screen.page[0]);
        if (c != last_crc || memcmp(dac, last_dac, sizeof dac)) {
            char h[VG_PAL_BYTES + 1];
            hex(dac, h);
            printf("%u v %u %s\n", (unsigned)f, (unsigned)c, h);
            last_crc = c;
            memcpy(last_dac, dac, sizeof dac);
        }
    }
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

/* the music layer as the music mode calls it */
static int mus_init(void)
{
    printf("%u mus init\n", (unsigned)now());
    return driver;
}

static int mus_play(const char *name, int vol)
{
    printf("%u mus play %s %d\n", (unsigned)now(), name, vol);
    return 1;
}

static int mus_fade(int t)
{
    printf("%u mus fade %d\n", (unsigned)now(), t);
    return 1;
}

static int unhex(const char *s, uint8_t *out, int n)
{
    int i;
    for (i = 0; i < n; i++) {
        char c = s[i];
        if (c >= '0' && c <= '9')
            out[i] = (uint8_t)(c - '0');
        else if (c >= 'a' && c <= 'f')
            out[i] = (uint8_t)(c - 'a' + 10);
        else
            return 0;
    }
    return 1;
}

int main(int argc, char **argv)
{
    static struct lrv_hal hal;
    static char line[2048];
    static const uint8_t nofile[] = "announce.xxx";
    struct lrv_video_mode mode = lrv_pc98_video_mode;
    const struct lrv_pack_entry *e;
    int held[VG_TIMERS], mask, i;

    if (argc != 3) {
        fprintf(stderr, "usage: test_bi PAK MASK < commands\n");
        return 2;
    }
    mask = atoi(argv[2]);
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
    vg_bi_load();
    vg.bi.mus.init = mus_init;
    vg.bi.mus.play = mus_play;
    vg.bi.mus.fade_stop = mus_fade;
    vg_timer_install();
    vg.input.kbd_external = 1;
    if (!vg_input_init((unsigned)mask))
        return 1;
    lrv_sys_add_hook(&vg.sys, LRV_HOOK_TICK, tick, NULL);
    vg.gfx.on_dac = on_dac;
    vg.input.on_pointer = on_pointer;
    vg_gfx_init();
    memcpy(dac, vg.gfx.pal_cur, sizeof dac);
    vg.timers.vsync = 0;                /* the original's start-up takes no time in the rig */

    while (fgets(line, sizeof line, stdin)) {
        char op[16], name[64];
        int a, b, c, d, f;
        unsigned ux;
        if (sscanf(line, "%15s", op) != 1)
            continue;
        if (!strcmp(op, "pic") && sscanf(line, "%*s %d %d %d %d %63s", &a, &b, &c, &d,
                                         name) == 5) {
            vg_pic_load(a, b, c, d, name);
        } else if (!strcmp(op, "pal") && sscanf(line, "%*s %63s", name) == 1 &&
                   strlen(name) == VG_PAL_BYTES) {
            uint8_t p[VG_PAL_BYTES];
            uint8_t rgb[VG_PAL_BYTES];
            if (!unhex(name, p, VG_PAL_BYTES))
                return 1;
            /* op 30h with t = 0 as pal_set does it, without the wait for the retrace: the
             * set-up takes no time on either side */
            memcpy(vg.gfx.pal_cur, p, VG_PAL_BYTES);
            for (i = 0; i < 16; i++) {
                rgb[3 * i] = p[i];
                rgb[3 * i + 1] = p[16 + i];
                rgb[3 * i + 2] = p[32 + i];
            }
            lrv_screen_set_palette(&vg.screen, rgb);
            memcpy(dac, p, sizeof dac);
        } else if (!strcmp(op, "input") && sscanf(line, "%*s %d", &a) == 1) {
            vg_input_term();
            vg_input_init((unsigned)a);
        } else if (!strcmp(op, "fill")) {
            for (i = 0; i < VG_TIMERS; i++)
                held[i] = vg_timer_start(1000);
        } else if (!strcmp(op, "free")) {
            for (i = 0; i < VG_TIMERS; i++)
                vg_timer_free(held[i]);
        } else if (!strcmp(op, "driver") && sscanf(line, "%*s %d", &a) == 1) {
            driver = a;
        } else if (!strcmp(op, "nofile")) {
            vg.bi.str[VG_BI_ANNOUNCE_FILE] = nofile;
        } else if (!strcmp(op, "ev")) {
            if (nev >= MAXEV)
                return 1;
            if (sscanf(line, "%*s %d scan %x", &f, &ux) == 2) {
                evs[nev].f = (uint32_t)f;
                evs[nev++].scan = (int)ux;
            } else if (sscanf(line, "%*s %d mouse %d %d %d", &f, &a, &b, &c) == 4) {
                evs[nev].f = (uint32_t)f;
                evs[nev].scan = -1;
                evs[nev].x = a;
                evs[nev].y = b;
                evs[nev++].b = c;
            }
        } else if (!strcmp(op, "bi") && sscanf(line, "%*s %d", &a) == 1) {
            char h[VG_PAL_BYTES + 1];
            base = vg.sys.frame;
            last_crc = surface_crc(&vg.screen.page[0]);
            memcpy(last_dac, dac, sizeof dac);
            running = 1;
            vg.text.skip = 0;
            vg_builtin(a);
            running = 0;
            hex(dac, h);
            printf("%u end %d %u %u %u %s\nend\n", (unsigned)now(), vg.text.skip == 1,
                   (unsigned)surface_crc(&vg.screen.page[0]),
                   (unsigned)surface_crc(&vg.screen.page[1]),
                   (unsigned)surface_crc(&vg.screen.buffer[0]), h);
            nev = 0;
        } else {
            printf("bad command %s", line);
        }
        fflush(stdout);
    }
    vg_input_term();
    vg_timer_remove();
    vg_bi_free();
    vg_text_free_fonts();
    gf_lib_close(&vg.lib);
    lrv_screen_free(&vg.screen);
    lrv_pack_close(&vg.pak);
    return 0;
}
