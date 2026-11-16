/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_gf: the engine's picture decoder (engine/gfx/gf.c) for tests/check_gf.py.
 *
 *   test_gf PAK              reads cases from stdin, one per line:
 *                              NAME X Y FLAG BACKGROUND OUT
 *                            draws picture NAME (e.g. va_main.gf) of the pack's library at
 *                            (X, Y) (-1: the file's) with FLAG (1: colour 8 transparent) over
 *                            the four planes in file BACKGROUND (4 x 32000 bytes, B R G I) and
 *                            writes the planes to OUT; prints "ok" or an error per case. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

int main(int argc, char **argv)
{
    static uint8_t planes[4][VG_PLANE_BYTES];
    struct lrv_hal hal;
    struct lrv_pack pak;
    struct gf_lib lib;
    const struct lrv_pack_entry *e;
    struct lrv_surface s;
    char line[1024];
    int q;

    if (argc != 2) {
        fprintf(stderr, "usage: test_gf PAK < cases\n");
        return 2;
    }
    th_hal(&hal, argv[1], NULL, NULL);
    if (lrv_pack_open(&pak, &hal, LRV_PACK_MAIN) != LRV_OK)
        return 1;
    e = lrv_pack_find(&pak, "GDATA.LIB", VG_PT_LIBRARY);
    if (!e || gf_lib_open(&lib, &hal, &pak, e) != LRV_OK) {
        fprintf(stderr, "test_gf: no picture library in the pack\n");
        return 1;
    }
    memset(&s, 0, sizeof s);
    s.format = LRV_FMT_PLANAR4;
    s.w = VG_SCREEN_W;
    s.h = VG_SCREEN_H;
    s.stride = VG_PLANE_STRIDE;
    for (q = 0; q < 4; q++)
        s.plane[q] = planes[q];
    while (fgets(line, sizeof line, stdin)) {
        char name[64], bg[400], out[400];
        int x, y, flag, i, rc;
        FILE *f;
        if (sscanf(line, "%63s %d %d %d %399s %399s", name, &x, &y, &flag, bg, out) != 6) {
            printf("bad case\n");
            continue;
        }
        i = gf_lib_find(&lib, name);
        f = fopen(bg, "rb");
        if (i < 0 || !f || fread(planes, 1, sizeof planes, f) != sizeof planes) {
            printf("no picture or background\n");
            if (f)
                fclose(f);
            continue;
        }
        fclose(f);
        rc = gf_draw(&lib, i, &s, x, y, flag == 1, NULL, NULL);
        f = fopen(out, "wb");
        if (!f || fwrite(planes, 1, sizeof planes, f) != sizeof planes) {
            printf("cannot write %s\n", out);
        } else {
            printf(rc == LRV_OK ? "ok\n" : "decoder error %d\n", rc);
        }
        if (f)
            fclose(f);
        fflush(stdout);
    }
    gf_lib_close(&lib);
    lrv_pack_close(&pak);
    return 0;
}
