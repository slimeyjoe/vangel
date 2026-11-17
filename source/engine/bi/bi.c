/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The built-in sequences: their data from the pack, statement 25h's table (0AB1:0000), and
 * what they share: the 80-column text line (0504:007C) and the input tests (0504:039C,
 * 0504:0257). docs/re/platform.md §5, text.md §5.1. */
#include <string.h>
#include "vg.h"
#include "lrvne/sjis.h"

/* ---- the data ----------------------------------------------------------------------------- */

static uint8_t *need(int k, const char *name, uint32_t *size)
{
    const struct lrv_pack_entry *e = lrv_pack_find(&vg.pak, name, LRV_PT_BLOB);
    uint8_t *d = e ? lrv_pack_load(&vg.pak, e, size) : NULL;
    if (!d)
        lrv_fatal(vg.hal, "the pack has no %s (make pack)", name);
    vg.bi.blob[k] = d;
    vg.bi.blob_size[k] = *size;
    return d;
}

static void need_pal(const char *name, uint8_t *dst)
{
    const struct lrv_pack_entry *e = lrv_pack_find(&vg.pak, name, LRV_PT_BLOB);
    if (!e || e->size != VG_PAL_BYTES || lrv_pack_read(&vg.pak, e, 0, dst, VG_PAL_BYTES) !=
        VG_PAL_BYTES)
        lrv_fatal(vg.hal, "the pack has no %s (make pack)", name);
}

/* A string of a table at *pos: a u16 length and its bytes (FFFFh: NULL). It is made a C
 * string where it lies (moved a byte down over its length's high byte). */
static const uint8_t *str_at(uint8_t *d, uint32_t size, uint32_t *pos, const char *name)
{
    uint32_t n;
    uint8_t *p = d + *pos;
    if (*pos + 2 > size)
        lrv_fatal(vg.hal, "the pack's %s is damaged", name);
    n = (uint32_t)(p[0] | p[1] << 8);
    *pos += 2;
    if (n == 0xFFFF)
        return NULL;
    if (*pos + n > size)
        lrv_fatal(vg.hal, "the pack's %s is damaged", name);
    memmove(p + 1, p + 2, n);
    p[n + 1] = 0;
    *pos += n;
    return p + 1;
}

void vg_bi_load(void)
{
    struct vg_bi *b = &vg.bi;
    uint32_t size, pos;
    uint8_t *d;
    int i;

    d = need(0, "bi.prologue", &size);
    for (pos = 0, i = 0; ; i++) {
        if (i == VG_BI_PROLOGUE_MAX || pos + 2 > size)
            lrv_fatal(vg.hal, "the pack's bi.prologue is damaged");
        b->prologue[i].row = (int16_t)(d[pos] | d[pos + 1] << 8);
        pos += 2;
        b->prologue[i].s = str_at(d, size, &pos, "bi.prologue");
        if (!b->prologue[i].s && b->prologue[i].row < 0)
            break;
    }
    d = need(1, "bi.staff", &size);
    for (pos = 0, i = 0; ; i++) {
        if (i == VG_BI_STAFF_MAX)
            lrv_fatal(vg.hal, "the pack's bi.staff is damaged");
        if (!(b->staff[i] = str_at(d, size, &pos, "bi.staff")))
            break;
    }
    d = need(2, "bi.music", &size);
    for (pos = 0, i = 0; ; i++) {
        if (i == VG_BI_SONGS_MAX)
            lrv_fatal(vg.hal, "the pack's bi.music is damaged");
        if (!(b->song[i].file = str_at(d, size, &pos, "bi.music")))
            break;
        b->song[i].title = str_at(d, size, &pos, "bi.music");
        if (!b->song[i].title)
            lrv_fatal(vg.hal, "the pack's bi.music is damaged");
    }
    d = need(3, "bi.strings", &size);
    for (pos = 0, i = 0; i < VG_BI_STRS; i++)
        if (!(b->str[i] = str_at(d, size, &pos, "bi.strings")))
            lrv_fatal(vg.hal, "the pack's bi.strings is damaged");
    {
        const struct lrv_pack_entry *e = lrv_pack_find(&vg.pak, "bi.rects", LRV_PT_BLOB);
        uint8_t r[VG_BI_RECTS * 18];
        if (!e || e->size != sizeof r || lrv_pack_read(&vg.pak, e, 0, r, sizeof r) != sizeof r)
            lrv_fatal(vg.hal, "the pack has no bi.rects (make pack)");
        for (i = 0; i < VG_BI_RECTS; i++) {
            int v[9], k;
            for (k = 0; k < 9; k++)
                v[k] = (int16_t)(r[18 * i + 2 * k] | r[18 * i + 2 * k + 1] << 8);
            b->rect[i].src = v[0];
            b->rect[i].sx = v[1];
            b->rect[i].sy = v[2];
            b->rect[i].w = v[3];
            b->rect[i].h = v[4];
            b->rect[i].dst = v[5];
            b->rect[i].dx = v[6];
            b->rect[i].dy = v[7];
            b->rect[i].effect = v[8];
        }
    }
    need_pal("pal.prologue", b->pal_prologue);
    need_pal("pal.end1.from", b->pal_from[0]);
    need_pal("pal.end1.to", b->pal_to[0]);
    need_pal("pal.end1.roll", b->pal_roll[0]);
    need_pal("pal.end2.from", b->pal_from[1]);
    need_pal("pal.end2.to", b->pal_to[1]);
    need_pal("pal.end2.roll", b->pal_roll[1]);
    b->mus.init = vg_mus_init;
    b->mus.play = vg_mus_play;
    b->mus.fade_stop = vg_mus_fade_stop;
}

void vg_bi_free(void)
{
    int k;
    for (k = 0; k < 4; k++)
        if (vg.bi.blob[k])
            lrv_pack_free(&vg.pak, vg.bi.blob[k], vg.bi.blob_size[k]);
    memset(&vg.bi, 0, sizeof vg.bi);
}

/* ---- statement 25h ------------------------------------------------------------------------ */

void vg_builtin(int n)
{
    switch (n) {
    case 0:                             /* INIT: the question again, for the next input_init */
        if (vg_console_ask(0))
            vg.input.want |= VG_DEV_MOUSE;
        else
            vg.input.want &= ~(unsigned)VG_DEV_MOUSE;
        break;
    case 1:
        vg_bi_opening();
        break;
    case 2:
        vg_bi_ending(0);
        break;
    case 3:
        vg_bi_announce();
        break;
    case 4:
        vg_bi_musmode();
        break;
    case 5:
        vg_bi_ending(1);
        break;
    default:
        break;
    }
}

/* ---- what the sequences share ------------------------------------------------------------- */

void vg_bi_line(int col, int row, const uint8_t *s, int attr)
{
    int mode = attr == 0xE1 ? 1 : 0, i;
    for (i = 0; s[i]; i++) {
        if (lrv_sjis_is_lead(s[i])) {
            vg_vram_kanji(col + i, 16 * row, s[i], s[i + 1], mode);
            i++;
        } else if (s[i] > 0x20) {
            vg_vram_ank(col + i, 16 * row, s[i], mode);
        }
        if (i + 1 >= 80)
            break;
    }
}

int vg_bi_input_check(int wait)
{
    struct vg_poll p;
    for (;;) {
        memset(&p, 0, sizeof p);
        if (!vg_input_poll(&p))
            return 0;
        if (p.kbd.event == 1) {
            vg_input_release(VG_DEV_KBD);
            return 1;
        }
        if (p.mouse.left == 1) {
            vg_input_release(VG_DEV_MOUSE);
            return 1;
        }
        if (p.joy.b != 0) {
            vg_input_release(VG_DEV_JOY);
            return 1;
        }
        if (wait != 1 || vg_frame())
            return 0;
    }
}

void vg_bi_wait_any(void)
{
    struct vg_poll p;
    vg_wait_begin(VG_WAIT_KEY);
    for (;;) {
        memset(&p, 0, sizeof p);
        if (!vg_input_poll(&p))
            break;
        if (p.kbd.event == 1) {
            vg_input_release(VG_DEV_KBD);
            break;
        }
        if (p.mouse.left == 1 || p.mouse.right == 1) {
            vg_input_release(VG_DEV_MOUSE);
            break;
        }
        if (p.joy.b != 0) {
            vg_input_release(VG_DEV_JOY);
            break;
        }
        if (vg_frame())
            break;
    }
    vg_wait_end(VG_WAIT_KEY);
}
