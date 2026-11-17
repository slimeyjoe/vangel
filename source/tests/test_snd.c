/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_snd: the music layer and the PMD binding (engine/snd/mus.c) on a stand-in driver, for
 * tests/check_snd.py, which runs the original's (segments 04E4 and 048F) on re-tools/sndcall.py's
 * stand-in with the same commands. The stand-in answers as sndcall's does: AH=22h AL = 8,
 * AH=09h AX = 47xxh with the board, AH=17h AL = 0, AH=05h AX = the measure counter given.
 *
 *   test_snd PACK < commands      the songs are the pack's; one command a line:
 *     setup none | setup BOARD    a new machine: no driver at INT 60h, or the stand-in with
 *                                 AH=09h's AL = BOARD (hex: 0 PMD.COM, 1 PMDB2, 2 PMD86, FF
 *                                 none); the timer not installed, no frame passed
 *     timer                       timer_init
 *     slots N                     N timer slots taken (timer_start(1000))
 *     measure= N                  what AH=05h answers from now on
 *     init | term | stop | state | measure     mus_init, ... : "R VALUE"
 *     play NAME VOL | fade T      mus_play, mus_fade_stop: "R VALUE" or "exit C"
 * After each of the last two kinds: "calls ..." (each INT 60h: AH, AL for 19h and 1Eh, the
 * frames passed before it), "opens ..." (each file tried: name, + found / - not), "st OK
 * PRESENT STATE BOARD VOL NAME BUF" (BUF: FNV-1a 64 of the whole music buffer). */
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include "vg.h"
#include "test_hal.h"

#define BUF_KB 8

static uint8_t musbuf[BUF_KB * 1024];
static int board;
static uint16_t measure;
static char calls[1 << 16], opens[4096];

static void cat(char *dst, size_t size, const char *s)
{
    size_t n = strlen(dst);
    if (n + strlen(s) + 1 < size)
        strcpy(dst + n, s);
}

static uint16_t fake_int60(uint16_t ax)
{
    char b[32];
    unsigned ah = ax >> 8, al = ax & 0xFFu;
    if (ah == 0x19 || ah == 0x1E)
        snprintf(b, sizeof b, " %02X:%02X@%u", ah, al, (unsigned)th_frames);
    else
        snprintf(b, sizeof b, " %02X@%u", ah, (unsigned)th_frames);
    cat(calls, sizeof calls, b);
    switch (ah) {
    case 0x22: return (uint16_t)((ax & 0xFF00u) | BUF_KB);
    case 0x09: return (uint16_t)(0x4700u | (unsigned)(board & 0xFF));
    case 0x17: return (uint16_t)(ax & 0xFF00u);
    case 0x05: return measure;
    default:   return ax;
    }
}

static void on_open(const char *name, int found)
{
    cat(opens, sizeof opens, " ");
    cat(opens, sizeof opens, name);
    cat(opens, sizeof opens, found ? "+" : "-");
}

static uint64_t fnv(const uint8_t *p, size_t n)
{
    uint64_t h = 0xcbf29ce484222325ull;
    while (n--)
        h = (h ^ *p++) * 0x100000001b3ull;
    return h;
}

static void report(void)
{
    const struct vg_mus *m = &vg.mus;
    printf("calls%s\nopens%s\n", calls, opens);
    printf("st %d %d %02X %d %d %s %016llx\n", m->ok, m->present, m->state, m->board, m->vol,
           m->name[0] ? m->name : "-", (unsigned long long)fnv(musbuf, sizeof musbuf));
    calls[0] = opens[0] = 0;
}

static void new_machine(int resident, int b)
{
    vg_timer_remove();
    memset(&vg.mus, 0, sizeof vg.mus);
    memset(&vg.timers, 0, sizeof vg.timers);
    memset(musbuf, 0, sizeof musbuf);
    vg.mus.buf = musbuf;
    vg.mus.buf_size = sizeof musbuf;
    vg.mus.int60 = fake_int60;
    vg.mus.on_open = on_open;
    vg.mus.resident = resident;
    strcpy(vg.mus.name, "none");
    board = b;
    measure = 0;
    th_frames = 0;
    calls[0] = opens[0] = 0;
}

int main(int argc, char **argv)
{
    static struct lrv_hal hal;
    static char line[4096];
    static int held[VG_TIMERS];
    jmp_buf here;

    if (argc != 2) {
        fprintf(stderr, "usage: test_snd PACK < commands\n");
        return 2;
    }
    th_hal(&hal, argv[1], NULL, NULL);
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    if (lrv_pack_open(&vg.pak, &hal, LRV_PACK_MAIN) != LRV_OK) {
        fprintf(stderr, "test_snd: cannot open %s\n", argv[1]);
        return 1;
    }
    lrv_sys_init(&vg.sys, &hal, VG_SCREEN_W, VG_SCREEN_H);
    new_machine(0, 0);

    while (fgets(line, sizeof line, stdin)) {
        char op[16], name[256];
        int a, k;
        volatile int r = 0;       /* set again after a longjmp */
        unsigned u;
        if (sscanf(line, "%15s", op) != 1)
            continue;
        vg.exit_to = &here;
        if (setjmp(here)) {
            printf("exit %d\n", vg.exit_code);
            report();
            fflush(stdout);
            continue;
        }
        if (!strcmp(op, "setup")) {
            if (sscanf(line, "%*s %x", &u) == 1)
                new_machine(1, u == 0xFF ? 0xFF : (int)u);
            else
                new_machine(0, 0);
            continue;
        } else if (!strcmp(op, "timer")) {
            vg_timer_install();
            continue;
        } else if (!strcmp(op, "slots") && sscanf(line, "%*s %d", &a) == 1) {
            for (k = 0; k < a && k < VG_TIMERS; k++)
                held[k] = vg_timer_start(1000);
            continue;
        } else if (!strcmp(op, "measure=") && sscanf(line, "%*s %u", &u) == 1) {
            measure = (uint16_t)u;
            continue;
        } else if (!strcmp(op, "init")) {
            r = vg_mus_init();
        } else if (!strcmp(op, "term")) {
            vg_mus_term();
        } else if (!strcmp(op, "stop")) {
            r = vg_mus_stop();
        } else if (!strcmp(op, "state")) {
            r = vg_mus_state();
        } else if (!strcmp(op, "measure")) {
            r = vg_mus_measure();
        } else if (!strcmp(op, "play") && sscanf(line, "%*s %255s %d", name, &a) == 2) {
            r = vg_mus_play(name, a);
        } else if (!strcmp(op, "fade") && sscanf(line, "%*s %d", &a) == 1) {
            r = vg_mus_fade_stop(a);
        } else {
            fprintf(stderr, "test_snd: bad command: %s", line);
            return 2;
        }
        printf("R %d\n", r);
        report();
        fflush(stdout);
    }
    (void)held;
    vg.exit_to = NULL;
    vg_timer_remove();
    lrv_pack_close(&vg.pak);
    return 0;
}
