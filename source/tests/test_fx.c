/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_fx: the engine's op 32h (engine/gfx/fx.c) for tests/check_fx.py.
 *
 *   test_fx                  reads cases from stdin, one per line:
 *                              SRC SX SY W H DST DX DY EFFECT CPF SRCFILE DSTFILE OUT LOG
 *                            loads the planes in SRCFILE into buffer SRC and those in DSTFILE
 *                            into DST (4 x 32000 bytes each, B R G I; a number other than
 *                            10..12 gets none), runs op 32h with CPF clocks per frame from the
 *                            start of a frame, writes the destination's planes to OUT and every
 *                            write to LOG: records of plane (u8), offset (u16), value (u8), the
 *                            clocks charged before it (u64), the frame and the clocks into it
 *                            (u32 each), little-endian. Prints "ok FRAMES CPU CLOCKS" (the
 *                            same at the return) or an error per case. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

struct logctx {
    FILE *f;
    uint64_t clk0;
    uint32_t frame0;
};

static void put_le(uint8_t *p, uint64_t v, int n)
{
    int i;
    for (i = 0; i < n; i++)
        p[i] = (uint8_t)(v >> (8 * i));
}

static void on_write(void *ctx, int plane, unsigned off, uint8_t value)
{
    struct logctx *l = ctx;
    uint8_t r[20];
    r[0] = (uint8_t)plane;
    put_le(r + 1, off, 2);
    r[3] = value;
    put_le(r + 4, vg.gfx.clk - l->clk0, 8);
    put_le(r + 12, vg.sys.frame - l->frame0, 4);
    put_le(r + 16, vg.sys.cpu, 4);
    fwrite(r, 1, sizeof r, l->f);
}

static struct lrv_surface *buffer(int buf)
{
    if (buf == 10 || buf == 11)
        return &vg.screen.page[buf - 10];
    if (buf == 12)
        return &vg.screen.buffer[0];
    return NULL;
}

static int load(int buf, const char *path)
{
    struct lrv_surface *s = buffer(buf);
    FILE *f;
    int q, ok = 1;
    if (!s)
        return 1;
    f = fopen(path, "rb");
    if (!f)
        return 0;
    for (q = 0; q < 4; q++)
        ok &= fread(s->plane[q], 1, VG_PLANE_BYTES, f) == VG_PLANE_BYTES;
    fclose(f);
    return ok;
}

static int save(const struct lrv_surface *s, const char *path)
{
    FILE *f = fopen(path, "wb");
    int q, ok = f != NULL;
    for (q = 0; ok && q < 4; q++)
        ok &= fwrite(s->plane[q], 1, VG_PLANE_BYTES, f) == VG_PLANE_BYTES;
    if (f)
        ok &= fclose(f) == 0;
    return ok;
}

int main(void)
{
    static struct lrv_hal hal;
    struct lrv_video_mode mode = lrv_pc98_video_mode;
    char line[2048];

    th_hal(&hal, "none", NULL, NULL);
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    if (lrv_screen_init(&vg.screen, &hal, &mode, 2, 1, LRV_MEM_ANY) != LRV_OK)
        return 1;
    lrv_sys_init(&vg.sys, &hal, mode.w, mode.h);
    vg_timer_install();
    vg.gfx.ready = 1;

    while (fgets(line, sizeof line, stdin)) {
        struct vg_rect_op op;
        char sp[400], dp[400], out[400], logp[400];
        unsigned cpf;
        struct logctx l;
        struct lrv_surface *d;
        if (sscanf(line, "%d %d %d %d %d %d %d %d %d %u %399s %399s %399s %399s", &op.src,
                   &op.sx, &op.sy, &op.w, &op.h, &op.dst, &op.dx, &op.dy, &op.effect, &cpf,
                   sp, dp, out, logp) != 14) {
            printf("bad case\n");
            fflush(stdout);
            continue;
        }
        if (!load(op.src, sp) || !load(op.dst, dp)) {
            printf("cannot read the planes\n");
            fflush(stdout);
            continue;
        }
        l.f = fopen(logp, "wb");
        if (!l.f) {
            printf("cannot write %s\n", logp);
            fflush(stdout);
            continue;
        }
        vg.sys.cpu_per_frame = cpf;
        lrv_sys_frame_wait(&vg.sys);            /* the start of a frame */
        l.clk0 = vg.gfx.clk;
        l.frame0 = vg.sys.frame;
        vg.gfx.on_write = on_write;
        vg.gfx.on_write_ctx = &l;
        vg_rect_copy(&op);
        vg.gfx.on_write = NULL;
        fclose(l.f);
        d = buffer(op.dst);
        if (d && !save(d, out)) {
            printf("cannot write %s\n", out);
        } else {
            printf("ok %u %u %llu\n", vg.sys.frame - l.frame0, vg.sys.cpu,
                   (unsigned long long)(vg.gfx.clk - l.clk0));
        }
        fflush(stdout);
    }
    vg_timer_remove();
    lrv_screen_free(&vg.screen);
    return 0;
}
