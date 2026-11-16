/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_vm: the scenario loader, expressions, saves and the interpreter (engine/vm/,
 * engine/game/saves.c) for tests/check_scb.py, check_expr.py, check_save.py and
 * check_vmstep.py, which give the original the same input under emulation.
 *
 *   test_vm STORAGE < commands      STORAGE: the directory of game.dat; one command a line:
 *     scb FILE              loads FILE as the scenario: "scb RC", then with RC 0 the tables
 *                           (see dump_scb)
 *     node I FORM K A B     expression node I := (FORM, K, A, B)
 *     var I TYPE VALUE      variable I (0..n) := (TYPE, VALUE)
 *     state PC DEPTH S0..S31  the interpreter's pc, depth and stack
 *     expr N                "expr V", or "exit C" when the program ends
 *     save K / load K       save_slot / load_slot K (0..2)
 *     gamedat HEX | -       game.dat := these bytes / no game.dat
 *     gamedat?              "gamedat HEX" or "gamedat -"
 *     dump                  "state PC DEPTH S0..S31 T0 V0 .. Tn-1 Vn-1" (variables 0..n)
 *     run PC ANSWERS...     the interpreter from PC with the subsystems stood in for (below)
 *                           until 2Eh, the end of the program, or answers run out; prints a
 *                           line per statement and per call (check_vmstep.py has the format)
 * Stand-ins: each call prints "c NAME ARGS"; those that need an answer take the next one:
 * wait (15h): 0 ends by the timer, 1 cut short, -1 no free timer; msg, builtin: the result
 * flag; menu: the choice; music_state, music_measure: the value. The rest answer nothing. */
#include <stdio.h>
#include <string.h>
#include <setjmp.h>
#include "vg.h"
#include "test_hal.h"

#define MAXANS 65536

static long ans[MAXANS];
static int nans, ians;
static jmp_buf out_of_answers;

static long answer(void)
{
    if (ians >= nans)
        longjmp(out_of_answers, 1);
    return ans[ians++];
}

static void print_str(const char *s)
{
    const unsigned char *p = (const unsigned char *)s;
    if (!*p)
        printf(" -");
    else
        printf(" ");
    while (*p)
        printf("%02x", *p++);
}

static void dump_scb(void)
{
    const struct vg_scb *s = &vg.vm.scb;
    int i, k;
    printf("h %u %u %d %d %d %d %d %d %d %d %u %u", s->entry, s->key, s->n_stmt, s->n_menu,
           s->n_expr, s->n_msg, s->n_pal, s->n_var, s->n_0b, s->n_0c, (unsigned)s->size,
           (unsigned)s->h0e);
    print_str(s->text);
    printf("\n");
    for (i = 1; i <= s->n_var; i++)
        printf("v %d %d %d\n", i, s->var[i].type, s->var[i].value);
    for (i = 1; i <= s->n_menu; i++) {
        printf("m %d %d", i, s->menu[i].n);
        for (k = 0; k < s->menu[i].n; k++)
            print_str((const char *)s->menu[i].item[k]);
        printf("\n");
    }
    for (i = 1; i <= s->n_expr; i++)
        if (s->expr[i].form == 0)
            printf("e %d 0 %d %d %d\n", i, s->expr[i].k, s->expr[i].a, s->expr[i].b);
        else
            printf("e %d 1 %d %d\n", i, s->expr[i].k, s->expr[i].a);
    for (i = 1; i <= s->n_pal; i++) {
        printf("p %d ", i);
        for (k = 0; k < 48; k++)
            printf("%x", s->pal[i][k]);
        printf("\n");
    }
    for (i = 1; i <= s->n_stmt; i++) {
        const struct vg_stmt *st = &s->stmt[i];
        const int16_t *a = s->w + st->at;
        int n;
        switch (st->op) {
        case 0x15: case 0x1A: case 0x1E: case 0x30: n = 2; break;
        case 0x19: case 0x1B: case 0x1C: case 0x21: case 0x22: case 0x23: case 0x24: case 0x25:
        case 0x2F: case 0x33: case 0x34: case 0x37: n = 1; break;
        case 0x1F: n = 3; break;
        case 0x20: n = 2 + 2 * st->n; break;
        case 0x31: n = 4; break;
        case 0x32: n = 9; break;
        default: n = 0;
        }
        printf("s %d %02x", i, st->op);
        if (st->op == 0x20)
            printf(" n%d", st->n);
        for (k = 0; k < n; k++)
            printf(" %d", a[k]);
        if (st->op == 0x31 || st->op == 0x1B)
            print_str(s->str + st->str);
        printf("\n");
    }
}

static void dump_state(void)
{
    const struct vg_vm *m = &vg.vm;
    int i;
    printf("state %u %d", m->pc, m->depth);
    for (i = 0; i < VG_CALL_STACK; i++)
        printf(" %u", m->stack[i]);
    for (i = 0; i <= m->scb.n_var; i++)
        printf(" %d %d", m->var[i].type, m->var[i].value);
    printf("\n");
}

/* ---- the stand-ins ------------------------------------------------------------------------ */

static int t_wait(int t, int sk)
{
    long a;
    printf("c wait %d %d\n", t, sk);
    a = answer();
    if (a < 0)
        return -1;
    if (a)
        vg.text.skip = 1;
    return 0;
}
static void t_wait_input(void) { printf("c input\n"); }
static void t_win_restore(void) { printf("c restore\n"); }
static void t_msg(int n)
{
    printf("c msg %d\n", n);
    vg.text.skip = (uint8_t)answer();
}
static void t_fade_out(int w, int t) { printf("c fadeout %d %d\n", w, t); }
static void t_music_play(int v, const char *name)
{
    printf("c play %d", v);
    print_str(name);
    printf("\n");
}
static int t_music_state(void)
{
    printf("c musstate\n");
    return (int)answer();
}
static void t_music_fade(int t) { printf("c musfade %d\n", t); }
static int t_menu(long stmt, const struct vg_menu *m)
{
    int r;
    printf("c menu %d\n", m->n);
    r = (int)answer();
    /* op_24's own memory of the last menu (the stand-in replaces vg_op24) */
    vg.text.menu_last = stmt;
    vg.text.menu_choice = r;
    return r;
}
static void t_builtin(int n)
{
    printf("c builtin %d\n", n);
    vg.text.skip = (uint8_t)answer();
}
static void t_flash(int t) { printf("c flash %d\n", t); }
static void t_palette(const uint8_t *pal, int t)
{
    int k;
    printf("c palette %d ", t);
    if (!pal)
        printf("-");
    else
        for (k = 0; k < 48; k++)
            printf("%x", pal[k]);
    printf("\n");
}
static void t_pic_load(int b, int x, int y, int f, const char *name)
{
    printf("c pic %d %d %d %d", b, x, y, f);
    print_str(name);
    printf("\n");
}
static void t_rect_copy(const struct vg_rect_op *o)
{
    printf("c copy %d %d %d %d %d %d %d %d %d\n", o->src, o->sx, o->sy, o->w, o->h, o->dst,
           o->dx, o->dy, o->effect);
}
static void t_clear(int b) { printf("c clear %d\n", b); }
static int t_music_measure(void) { printf("c measure\n"); return (int)answer(); }
static void t_mouse_lock(int l, int s) { printf("c lock %d %d\n", l, s); }

static const struct vg_vm_io test_io = {
    t_wait, t_wait_input, t_win_restore, t_msg, t_fade_out, t_music_play, t_music_state,
    t_music_fade, t_menu, t_builtin, t_flash, t_palette, t_pic_load, t_rect_copy, t_clear,
    t_music_measure, t_mouse_lock
};

static uint64_t clk0;

static void on_step(void *ctx, unsigned pc)
{
    const struct vg_vm *m = &vg.vm;
    int i;
    (void)ctx;
    printf("x %u %02x %u %d %llu", pc, m->scb.stmt[pc].op, m->pc, m->depth,
           (unsigned long long)(m->clk - clk0));
    for (i = 0; i < m->depth && i < VG_CALL_STACK; i++)
        printf(" %u", m->stack[i]);
    printf(" |");
    for (i = 0; i <= m->scb.n_var; i++)
        printf(" %d:%d", m->var[i].type, m->var[i].value);
    printf("\n");
    clk0 = m->clk;
}

static const char *storage;

static void gamedat_path(char *path, size_t n)
{
    snprintf(path, n, "%s/game.dat", storage);
}

static uint8_t *read_file(const char *path, uint32_t *size)
{
    FILE *f = fopen(path, "rb");
    uint8_t *d;
    long n;
    if (!f)
        return NULL;
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    d = malloc((size_t)n + 1);
    if (!d || fread(d, 1, (size_t)n, f) != (size_t)n) {
        fclose(f);
        free(d);
        return NULL;
    }
    fclose(f);
    *size = (uint32_t)n;
    return d;
}

int main(int argc, char **argv)
{
    static struct lrv_hal hal;
    static char line[1 << 20];
    jmp_buf here;

    if (argc != 2) {
        fprintf(stderr, "usage: test_vm STORAGE < commands\n");
        return 2;
    }
    storage = argv[1];
    th_hal(&hal, NULL, NULL, argv[1]);
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    strcpy(vg.profile.base.id, "test");

    while (fgets(line, sizeof line, stdin)) {
        char op[16];
        int i, a, b, c, d;
        if (sscanf(line, "%15s", op) != 1)
            continue;
        vg.exit_to = &here;
        if (setjmp(here)) {
            printf("exit %d\n", vg.exit_code);
            fflush(stdout);
            continue;
        }
        if (!strcmp(op, "scb")) {
            char path[1024];
            uint8_t *data;
            uint32_t size;
            if (sscanf(line, "%*s %1023s", path) != 1 || !(data = read_file(path, &size)))
                return 1;
            a = vg_scb_load(data, size);
            free(data);
            printf("scb %d\n", a);
            if (a == 0) {
                dump_scb();
                vg_vm_init(vg_vm_entry());
                vg.vm.io = &test_io;
                printf("entry %u\n", vg.vm.pc);
            }
        } else if (!strcmp(op, "node") && sscanf(line, "%*s %d %d %d %d %d", &i, &a, &b, &c,
                                                 &d) == 5) {
            vg.vm.scb.expr[i].form = (int16_t)a;
            vg.vm.scb.expr[i].k = (int16_t)b;
            vg.vm.scb.expr[i].a = (int16_t)c;
            vg.vm.scb.expr[i].b = (int16_t)d;
        } else if (!strcmp(op, "var") && sscanf(line, "%*s %d %d %d", &i, &a, &b) == 3) {
            vg.vm.var[i].type = (int16_t)a;
            vg.vm.var[i].value = (int16_t)b;
        } else if (!strcmp(op, "state")) {
            char *p = line + 5;
            int n;
            unsigned v;
            if (sscanf(p, "%d %d%n", &a, &b, &n) != 2)
                return 1;
            vg.vm.pc = (uint16_t)a;
            vg.vm.depth = (int16_t)b;
            p += n;
            for (i = 0; i < VG_CALL_STACK && sscanf(p, "%u%n", &v, &n) == 1; i++, p += n)
                vg.vm.stack[i] = (uint16_t)v;
        } else if (!strcmp(op, "expr") && sscanf(line, "%*s %d", &a) == 1) {
            printf("expr %d\n", vg_expr_eval(a));
        } else if (!strcmp(op, "save") && sscanf(line, "%*s %d", &a) == 1) {
            vg_save_slot(a);
            printf("saved\n");
        } else if (!strcmp(op, "load") && sscanf(line, "%*s %d", &a) == 1) {
            vg_load_slot(a);
            printf("loaded\n");
        } else if (!strcmp(op, "gamedat")) {
            char path[1100], hex[3] = { 0 };
            const char *p = line + 8;
            FILE *f;
            gamedat_path(path, sizeof path);
            remove(path);
            if (*p != '-') {
                if (!(f = fopen(path, "wb")))
                    return 1;
                while (p[0] && p[1] && p[0] != '\n') {
                    unsigned v;
                    hex[0] = p[0];
                    hex[1] = p[1];
                    sscanf(hex, "%x", &v);
                    fputc((int)v, f);
                    p += 2;
                }
                fclose(f);
            }
        } else if (!strcmp(op, "gamedat?")) {
            char path[1100];
            uint8_t *data;
            uint32_t size, k;
            gamedat_path(path, sizeof path);
            if (!(data = read_file(path, &size))) {
                printf("gamedat -\n");
            } else {
                printf("gamedat ");
                for (k = 0; k < size; k++)
                    printf("%02x", data[k]);
                printf("\n");
                free(data);
            }
        } else if (!strcmp(op, "dump")) {
            dump_state();
        } else if (!strcmp(op, "run")) {
            char *p = line + 3;
            int n;
            long v;
            if (sscanf(p, "%d%n", &a, &n) != 1)
                return 1;
            p += n;
            for (nans = 0; nans < MAXANS && sscanf(p, "%ld%n", &v, &n) == 1; p += n)
                ans[nans++] = v;
            ians = 0;
            vg.vm.pc = (uint16_t)a;
            vg.vm.on_step = on_step;
            clk0 = vg.vm.clk;
            if (setjmp(out_of_answers)) {
                printf("end answers\n");
            } else {
                while (vg_vm_step())
                    ;
                printf("end 2e\n");
            }
            vg.vm.on_step = NULL;
        } else {
            printf("bad command %s", line);
        }
        fflush(stdout);
    }
    vg.exit_to = NULL;
    vg_vm_free();
    vg_scb_free();
    return 0;
}
