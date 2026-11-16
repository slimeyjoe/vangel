/* SPDX-License-Identifier: GPL-3.0-or-later */
/* test_pal: the engine's palette operations (engine/gfx/pal.c) for tests/check_pal.py.
 *
 *   test_pal PAK             runs the statements on stdin, one per line, from the state after
 *                            gfx_init (the default palette current) and the timer installed:
 *                              30 T PAL     op 30h: fade in to PAL (48 hex digits, R G B) over T
 *                              1a W T       op 1Ah: fade out to white (W 1) or black over T
 *                              2f T         op 2Fh: flash over T
 *                              fill         take all 16 timer slots
 *                              free         free them again
 *                            and prints every DAC load as "dac FRAME PAL" (FRAME: VSYNCs since
 *                            the start), then "end FRAME". */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "test_hal.h"

static void on_dac(void *ctx, const uint8_t *pal)
{
    int i;
    (void)ctx;
    printf("dac %u ", vg.sys.frame);
    for (i = 0; i < VG_PAL_BYTES; i++)
        printf("%x", pal[i] & 15);
    printf("\n");
}

static int hexpal(const char *s, uint8_t *pal)
{
    int i;
    if (strlen(s) != VG_PAL_BYTES)
        return 0;
    for (i = 0; i < VG_PAL_BYTES; i++) {
        int c = s[i];
        if (c >= '0' && c <= '9')
            pal[i] = (uint8_t)(c - '0');
        else if (c >= 'a' && c <= 'f')
            pal[i] = (uint8_t)(c - 'a' + 10);
        else
            return 0;
    }
    return 1;
}

int main(int argc, char **argv)
{
    static struct lrv_hal hal;
    struct lrv_video_mode mode = lrv_pc98_video_mode;
    char line[256];
    int held[VG_TIMERS], nheld = 0;

    if (argc != 2) {
        fprintf(stderr, "usage: test_pal PAK < statements\n");
        return 2;
    }
    th_hal(&hal, argv[1], NULL, NULL);
    memset(&vg, 0, sizeof vg);
    vg.hal = &hal;
    if (lrv_pack_open(&vg.pak, &hal, LRV_PACK_MAIN) != LRV_OK)
        return 1;
    if (lrv_screen_init(&vg.screen, &hal, &mode, 2, 1, LRV_MEM_ANY) != LRV_OK)
        return 1;
    lrv_sys_init(&vg.sys, &hal, mode.w, mode.h);
    vg_gfx_load_palettes();
    vg_timer_install();
    vg.gfx.ready = 1;
    memcpy(vg.gfx.pal_cur, vg.gfx.pal_default, VG_PAL_BYTES);
    vg.gfx.on_dac = on_dac;

    while (fgets(line, sizeof line, stdin)) {
        char op[8], hex[64];
        int a, b;
        uint8_t pal[VG_PAL_BYTES];
        if (sscanf(line, "%7s", op) != 1)
            continue;
        if (!strcmp(op, "30") && sscanf(line, "%*s %d %63s", &a, hex) == 2 && hexpal(hex, pal)) {
            vg_pal_op30(pal, a);
        } else if (!strcmp(op, "1a") && sscanf(line, "%*s %d %d", &a, &b) == 2) {
            vg_pal_fade_out(a, b);
        } else if (!strcmp(op, "2f") && sscanf(line, "%*s %d", &a) == 1) {
            vg_pal_flash(a);
        } else if (!strcmp(op, "fill")) {
            while (nheld < VG_TIMERS && (held[nheld] = vg_timer_start(100000)) != 0)
                nheld++;
        } else if (!strcmp(op, "free")) {
            while (nheld > 0)
                vg_timer_free(held[--nheld]);
        } else {
            printf("bad statement %s", line);
        }
    }
    printf("end %u\n", vg.sys.frame);
    vg_timer_remove();
    lrv_screen_free(&vg.screen);
    lrv_pack_close(&vg.pak);
    return 0;
}
