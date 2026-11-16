/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_buf: the engine's buffer statements (engine/gfx/buf.c, fx.c) for tests/check_buf.py.
 *
 *   test_buf PAK             runs the statements on stdin, one per line, after gfx_init:
 *                              load FILE    the four planes of page 0, page 1 and buffer 12
 *                                           (3 x 4 x 32000 bytes) from FILE
 *                              31 BUF X Y FLAG NAME    op 31h
 *                              32 SRC SX SY W H DST DX DY EFFECT    op 32h
 *                              33 BUF       op 33h
 *                              18           op 18h
 *                              clear        screen_clear
 *                              dump FILE    the three buffers and the window's background
 *                                           (4 x 1540h bytes) to FILE
 *                            and prints the result of each op ("31 1", ...). */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

static struct lrv_surface *buf_n(int n)
{
    return n < 2 ? &vg.screen.page[n] : &vg.screen.buffer[0];
}

static int io(const char *path, int write)
{
    FILE *f = fopen(path, write ? "wb" : "rb");
    int n, q, ok = f != NULL;
    for (n = 0; ok && n < 3; n++)
        for (q = 0; ok && q < 4; q++)
            ok = (write ? fwrite(buf_n(n)->plane[q], 1, VG_PLANE_BYTES, f)
                        : fread(buf_n(n)->plane[q], 1, VG_PLANE_BYTES, f)) == VG_PLANE_BYTES;
    if (ok && write)
        ok = fwrite(vg.gfx.win_save, 1, sizeof vg.gfx.win_save, f) == sizeof vg.gfx.win_save;
    if (f)
        ok &= fclose(f) == 0;
    return ok;
}

int main(int argc, char **argv)
{
    static struct lrv_hal hal;
    struct lrv_video_mode mode = lrv_pc98_video_mode;
    const struct lrv_pack_entry *e;
    char line[512];

    if (argc != 2) {
        fprintf(stderr, "usage: test_buf PAK < statements\n");
        return 2;
    }
    th_hal(&hal, argv[1], NULL, NULL);
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    if (lrv_pack_open(&vg.pak, &hal, LRV_PACK_MAIN) != LRV_OK ||
        lrv_screen_init(&vg.screen, &hal, &mode, 2, 1, LRV_MEM_ANY) != LRV_OK)
        return 1;
    e = lrv_pack_find(&vg.pak, "GDATA.LIB", VG_PT_LIBRARY);
    if (!e || gf_lib_open(&vg.lib, &hal, &vg.pak, e) != LRV_OK)
        return 1;
    lrv_sys_init(&vg.sys, &hal, mode.w, mode.h);
    vg_gfx_load_palettes();
    vg_timer_install();
    vg_gfx_init();

    while (fgets(line, sizeof line, stdin)) {
        char op[8], name[64], path[512];
        struct vg_rect_op r;
        int a, b, c, d;
        if (sscanf(line, "%7s", op) != 1)
            continue;
        if (!strcmp(op, "load") && sscanf(line, "%*s %511s", path) == 1) {
            printf("load %d\n", io(path, 0));
        } else if (!strcmp(op, "dump") && sscanf(line, "%*s %511s", path) == 1) {
            printf("dump %d\n", io(path, 1));
        } else if (!strcmp(op, "31") &&
                   sscanf(line, "%*s %d %d %d %d %63s", &a, &b, &c, &d, name) == 5) {
            printf("31 %d\n", vg_pic_load(a, b, c, d, name));
        } else if (!strcmp(op, "32") &&
                   sscanf(line, "%*s %d %d %d %d %d %d %d %d %d", &r.src, &r.sx, &r.sy, &r.w,
                          &r.h, &r.dst, &r.dx, &r.dy, &r.effect) == 9) {
            printf("32 %d\n", vg_rect_copy(&r));
        } else if (!strcmp(op, "33") && sscanf(line, "%*s %d", &a) == 1) {
            vg_buf_clear(a);
            printf("33\n");
        } else if (!strcmp(op, "18")) {
            vg_win_restore();
            printf("18\n");
        } else if (!strcmp(op, "clear")) {
            vg_screen_clear();
            printf("clear\n");
        } else {
            printf("bad statement %s", line);
        }
        fflush(stdout);
    }
    vg_timer_remove();
    gf_lib_close(&vg.lib);
    lrv_screen_free(&vg.screen);
    lrv_pack_close(&vg.pak);
    return 0;
}
