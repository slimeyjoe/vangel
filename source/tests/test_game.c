/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_game: the whole engine, the game played from its start on a route, for
 * tests/check_vm.py, which plays the same route on the original under emulation
 * (re-tools/va98.py) and compares what both print.
 *
 *   test_game PAK STORAGE ROUTE [sound=pmd26k|none] [lang=TAG]
 *
 * STORAGE: the directory of game.dat (the file the run starts with, if any). ROUTE (a file, or
 * - for stdin: a line is read when its wait comes, after the wait's state is printed, so a
 * player can decide it there; tests/e2e/explore.py): a line
 * for each wait the game enters (LRV_TR_WAIT), in order: what the player does from the first
 * frame after the wait was entered on, an entry a frame, separated by spaces:
 *     .        nothing
 *     kHH      a press of the key of PC-98 scan code HH (down for that frame's poll: the make
 *              code, then the break code at the next poll)
 *     hHH      the key held down from now on; uHH let go
 *     mX,Y,B   the pointer at (X, Y) and the buttons B (1 left, 2 right) from now on
 *     cX,Y     the pointer at (X, Y), the left button down for one frame
 * At each wait it prints "sync N KIND" and the state (check_vm.py's FIELDS, va98.py's
 * VA98.state): the interpreter, the CRC-32 of both pages, buffer 12 and the window's buffers,
 * the DAC, the flags, the music, the pointer, game.dat, and the INT 60h calls since the wait
 * before (AX, and AL after 09h, 17h, 22h; a call equal to the one before it and AH=05h left
 * out: check_vm.py says why). When the route has no
 * line for a wait the run quits there ("end"). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

#define MAXLINE 65536
#define MAXFRAMES 4096
#define MAXCALLS 65536

static FILE *route;
static const char *storage;
static char sound[16];
static int nwait, quitting;

static struct { char kind; int a, b, c; } frames[MAXFRAMES];
static int nframes, iframe;
static int mx = 0, my = 0, mb = 0, release_click;
static uint8_t held[LRV_KEYMAP_BYTES];

static uint16_t calls[MAXCALLS][2];
static int ncalls;
static uint16_t (*driver)(uint16_t ax);

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

static uint32_t win_crc(uint8_t (*w)[VG_WIN_BYTES])
{
    uint32_t c = 0;
    int q;
    for (q = 0; q < 4; q++)
        c = crc32(c, w[q], VG_WIN_BYTES);
    return c;
}

/* ---- the driver's calls ---------------------------------------------------------------- */

static uint16_t logged_int60(uint16_t ax)
{
    uint16_t r = driver(ax), ah = ax >> 8, k = ah == 0x09 || ah == 0x17 || ah == 0x22 ?
                                                  (uint16_t)(r & 0xFF) : 0;
    if (ah != 0x05 && ncalls < MAXCALLS &&
        !(ncalls && calls[ncalls - 1][0] == ax && calls[ncalls - 1][1] == k)) {
        calls[ncalls][0] = ax;
        calls[ncalls][1] = k;
        ncalls++;
    }
    return r;
}

/* ---- the state ------------------------------------------------------------------------- */

static void print_state(void)
{
    const struct vg_vm *m = &vg.vm;
    char path[1024];
    uint8_t *dat;
    FILE *f;
    long n;
    int i;

    printf(" pc=%u depth=%d stack=", m->pc, m->depth);
    for (i = 0; i < VG_CALL_STACK; i++)
        printf("%s%u", i ? "," : "", m->stack[i]);
    printf(" vars=");
    if (m->var)
        for (i = 0; i <= m->scb.n_var; i++)
            printf("%s%d:%d", i ? "," : "", m->var[i].type, m->var[i].value);
    else
        printf("0:0");
    printf(" page0=%08x page1=%08x buf12=%08x ws=%08x ww=%08x disp=%d dac=",
           (unsigned)surface_crc(&vg.screen.page[0]), (unsigned)surface_crc(&vg.screen.page[1]),
           (unsigned)surface_crc(&vg.screen.buffer[0]), (unsigned)win_crc(vg.gfx.win_save),
           (unsigned)win_crc(vg.gfx.win_work), vg.screen.display_page);
    for (i = 0; i < VG_PAL_BYTES; i++)
        printf("%x", vg.screen.rgb[i] & 15);
    printf(" skip=%d choice=%d mus=%s/%d ptr=%d dat=", vg.text.skip, vg.text.menu_choice,
           vg.mus.name, vg.mus.vol, vg.input.ptr_shown);
    snprintf(path, sizeof path, "%s/game.dat", storage);
    f = fopen(path, "rb");
    if (f && fseek(f, 0, SEEK_END) == 0 && (n = ftell(f)) >= 0) {
        dat = malloc((size_t)n + 1);
        rewind(f);
        if (dat && fread(dat, 1, (size_t)n, f) == (size_t)n)
            printf("%08x", (unsigned)crc32(0, dat, (size_t)n));
        else
            printf("?");
        free(dat);
    } else {
        printf("-");
    }
    if (f)
        fclose(f);
    printf(" int60=");
    for (i = 0; i < ncalls; i++) {
        unsigned ah = calls[i][0] >> 8u;
        printf("%s%04x", i ? "," : "", calls[i][0]);
        if (ah == 0x09 || ah == 0x17 || ah == 0x22)
            printf(":%02x", calls[i][1] & 0xFFu);
    }
    if (!ncalls)
        printf("-");
    ncalls = 0;
    printf("\n");
    fflush(stdout);
}

/* ---- the route ------------------------------------------------------------------------- */

/* the next line: the frames of the wait just entered; 0 at the route's end */
static int read_wait(void)
{
    static char line[MAXLINE];
    char *t;
    nframes = iframe = 0;
    if (!fgets(line, sizeof line, route))
        return 0;
    for (t = strtok(line, " \t\r\n"); t && nframes < MAXFRAMES; t = strtok(NULL, " \t\r\n")) {
        unsigned u = 0;
        int a = 0, b = 0, c = 0, ok;
        char k = t[0];
        if (k == 'k' || k == 'h' || k == 'u') {
            ok = sscanf(t + 1, "%x", &u) == 1 && u < 0x80;
            a = (int)u;
        } else if (k == 'm') {
            ok = sscanf(t + 1, "%d,%d,%d", &a, &b, &c) == 3;
        } else if (k == 'c') {
            ok = sscanf(t + 1, "%d,%d", &a, &b) == 2;
        } else {
            ok = k == '.';
        }
        if (ok) {
            frames[nframes].kind = k;
            frames[nframes].a = a;
            frames[nframes].b = b;
            frames[nframes].c = c;
            nframes++;
        } else {
            fprintf(stderr, "test_game: wait %d: no such input \"%s\"\n", nwait, t);
            exit(2);
        }
    }
    return 1;
}

static void on_trace(const struct lrv_trace_event *ev)
{
    if (ev->kind != LRV_TR_WAIT || ev->a1 != 0 || quitting)
        return;
    if (vg.mus.int60 && vg.mus.int60 != logged_int60) {
        driver = vg.mus.int60;
        vg.mus.int60 = logged_int60;
    }
    nwait++;
    printf("sync %d %s", nwait, ev->a0 == VG_WAIT_TICKS ? "ticks" : "key");
    print_state();
    if (!read_wait()) {
        printf("end\n");
        fflush(stdout);
        quitting = 1;
        lrv_sys_request_quit(&vg.sys);
    }
}

static int key_of_scan(int scan)
{
    int k;
    for (k = 1; k < LRV_K_COUNT; k++)
        if (lrv_pc98_scan(k, 0) == scan)
            return k;
    fprintf(stderr, "test_game: no key sends scan code %02X\n", scan);
    exit(2);
}

static void poll(struct lrv_input *in)
{
    memcpy(in->down, held, sizeof held);
    if (release_click) {
        mb &= ~1;
        release_click = 0;
    }
    if (iframe < nframes) {
        int a = frames[iframe].a;
        switch (frames[iframe].kind) {
        case 'k':
            in->keys[0].key = (uint8_t)key_of_scan(a);
            in->nkeys = 1;
            break;
        case 'h':
            lrv_key_set(in, key_of_scan(a), 1);
            break;
        case 'u':
            lrv_key_set(in, key_of_scan(a), 0);
            break;
        case 'm':
            mx = a;
            my = frames[iframe].b;
            mb = frames[iframe].c;
            break;
        case 'c':
            mx = a;
            my = frames[iframe].b;
            mb |= 1;
            release_click = 1;
            break;
        default:
            break;
        }
        memcpy(held, in->down, sizeof held);
        iframe++;
    }
    in->mouse_abs = 1;
    in->mouse_x = mx;
    in->mouse_y = my;
    in->buttons = (unsigned)mb;
}

static void profile_hook(struct vg_profile *p)
{
    if (sound[0])
        strcpy(p->sound, sound);
}

int main(int argc, char **argv)
{
    struct lrv_hal hal;
    struct lrv_run_cfg cfg;
    struct vg_options opt;
    int i, rc;

    if (argc < 4) {
        fprintf(stderr, "usage: test_game PAK STORAGE ROUTE [sound=S] [lang=TAG]\n");
        return 2;
    }
    storage = argv[2];
    route = strcmp(argv[3], "-") ? fopen(argv[3], "r") : stdin;
    if (!route) {
        fprintf(stderr, "test_game: cannot read %s\n", argv[3]);
        return 2;
    }
    memset(&cfg, 0, sizeof cfg);
    for (i = 4; i < argc; i++) {
        if (!strncmp(argv[i], "sound=", 6))
            snprintf(sound, sizeof sound, "%s", argv[i] + 6);
        else if (!strncmp(argv[i], "lang=", 5))
            cfg.lang = argv[i] + 5;
    }
    crc_init();
    th_hal(&hal, argv[1], NULL, storage);
    hal.trace = on_trace;
    hal.input_poll = poll;
    vg_profile_hook = profile_hook;
    memset(&opt, 0, sizeof opt);
    rc = vg_run(&hal, &cfg, &opt);
    printf("exit %d\n", rc);
    if (route != stdin)
        fclose(route);
    return 0;
}
