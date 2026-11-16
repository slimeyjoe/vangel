/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The message file "CRTX" (docs/re/text.md §2): txb_load 0724:0018, txb_index_msg 0724:0119,
 * txb_read_msg 0724:0186, txb_line 0724:0206. The file is kept whole in memory as the pack
 * has it (every byte after the magic inverted) and read the way the original reads its open
 * file: fgetc inverted, EOF becoming 00h. */
#include <string.h>
#include "vg.h"
#include "lrvne/sjis.h"

/* txb_getc (0724:0006): ~fgetc; at the end of the file ~EOF, whose low byte is 0 */
static uint8_t txb_getc(uint32_t pos)
{
    return pos < vg.text.txb.size ? (uint8_t)~vg.text.txb.file[pos] : 0;
}

void vg_txb_free(void)
{
    struct vg_txb *t = &vg.text.txb;
    if (t->file)
        lrv_pack_free(&vg.pak, t->file, t->size);
    if (t->off)
        lrv_free(vg.hal, t->off, (size_t)(t->count + 1) * sizeof *t->off);
    if (t->len)
        lrv_free(vg.hal, t->len, (size_t)(t->count + 1) * sizeof *t->len);
    t->file = NULL;
    t->off = NULL;
    t->len = NULL;
    t->count = 0;
}

int vg_txb_load(const char *name, int count)
{
    struct vg_txb *t = &vg.text.txb;
    const struct lrv_pack_entry *e;
    uint32_t pos;
    int i;

    vg_txb_free();
    e = lrv_pack_find(&vg.pak, name, VG_PT_TEXT);
    if (!e || !(t->file = lrv_pack_load(&vg.pak, e, &t->size)))
        return 0;
    if (t->size < 4 || memcmp(t->file, "CRTX", 4) != 0 || count < 0 || count > VG_TXB_MAX) {
        vg_txb_free();
        return 0;
    }
    t->count = count;
    t->off = lrv_alloc(vg.hal, (size_t)(count + 1) * sizeof *t->off);
    t->len = lrv_alloc(vg.hal, (size_t)(count + 1) * sizeof *t->len);
    if (!t->off || !t->len) {
        vg_txb_free();
        return 0;
    }
    t->off[0] = 0;                      /* entry 0 is NULL in the original: never used */
    t->len[0] = 0;
    pos = 4;
    for (i = 1; i <= count; i++) {
        uint32_t n = 0;
        t->off[i] = pos;
        /* the bytes up to the next 1Ah, which counts. (Past the end the original reads 00h
         * for ever; here the end of the file fails the load.) */
        do {
            if (pos >= t->size) {
                vg_txb_free();
                return 0;
            }
            n++;
        } while (txb_getc(pos++) != 0x1A);
        if (n > 0x1FFF) {
            vg_txb_free();
            return 0;
        }
        t->len[i] = (uint16_t)n;
    }
    {
        const struct lrv_pack_entry *d = lrv_pack_find(&vg.pak, "txbdict", LRV_PT_BLOB);
        if (!d || d->size != sizeof t->dict ||
            lrv_pack_read(&vg.pak, d, 0, t->dict, sizeof t->dict) != sizeof t->dict) {
            vg_txb_free();
            return 0;
        }
    }
    return 1;
}

void vg_txb_read(int n)
{
    struct vg_txb *t = &vg.text.txb;
    uint32_t pos = t->off[n];
    int i, len = t->len[n] + 10;
    for (i = 0; i < len && i < VG_TXB_BUF; i++)
        t->buf[i] = txb_getc(pos + (uint32_t)i);
}

int vg_txb_line(unsigned pos, uint8_t *out, int max)
{
    const struct vg_txb *t = &vg.text.txb;
    const uint8_t *s, *end = t->buf + VG_TXB_BUF;
    uint8_t *d = out;
    int srclen = 1, n = 0, lead = 0;

    if (pos >= VG_TXB_BUF) {
        *d = 0;
        return 1;
    }
    s = t->buf + pos;
    while (s + srclen - 1 < end && s[srclen - 1])
        srclen++;
    if (max > 0) {
        while (s < end && *s) {
            unsigned b = *s;
            *d = (uint8_t)b;
            if (lead) {
                lead = 0;
            } else if (lrv_sjis_is_lead(b)) {
                lead = 1;
            } else if (b >= 0xA0 && b <= 0xDF) {
                d[0] = t->dict[2 * (b - 0xA0)];
                d[1] = t->dict[2 * (b - 0xA0) + 1];
                d++;
                n++;
            } else if (b >= 0x41 && b <= 0x5A) {
                d[0] = t->dict[2 * (64 + b - 0x41)];
                d[1] = t->dict[2 * (64 + b - 0x41) + 1];
                d++;
                n++;
            }
            s++;
            d++;
            if (++n >= max)
                break;
        }
    }
    *d = 0;
    return srclen;
}
