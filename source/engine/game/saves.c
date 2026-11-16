/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The save file GAME.DAT: save_slot (001E:042C) and load_slot (001E:0577),
 * docs/re/scenario-format.md §7. Byte for byte the original's file, kept as the storage
 * record "game.dat" (read whole, changed, written whole: the original's fopen "r+b").
 *
 * A record: "SD", its size (variables + 24) * 3, pc, the call depth, the 32 stack words and
 * then (type byte, value) of the variable table's entries 0 .. n-1: entry 0 is the unused slot
 * and the last variable is never saved nor loaded (the original's off-by-one). Words are
 * big-endian. A slot k lies at offset size * k (the low word of the product, sign-extended).
 *
 * Loading reads as fgetc does: past the end of the file every read is -1, and a word from two
 * such reads is (-1 << 8) + -1, 16-bit. The record is taken only when it starts with "SD"
 * and its size; after that it is read whole, whatever follows. Saving past the end of a
 * shorter file fills the gap with zeros (DOS leaves the clusters' old contents there). */
#include <string.h>
#include "vg.h"

#define SAVE_KEY        "game.dat"
#define SAVE_MAX        (3 * 0x8000)

int vg_save_record_size(void)
{
    return (int16_t)((vg.vm.scb.n_var + 24) * 3);
}

static int slot_offset(int slot)
{
    return (int16_t)(vg_save_record_size() * slot);
}

/* the whole file, in a buffer of SAVE_MAX bytes (lrv_free) */
static uint8_t *file_buf(size_t *len)
{
    uint8_t *buf = lrv_xalloc(vg.hal, SAVE_MAX);
    *len = 0;
    if (vg.hal->storage_read(SAVE_KEY, buf, SAVE_MAX, len) != LRV_OK)
        *len = 0;
    return buf;
}

static int storage_ready(void)
{
    static int opened;
    if (!opened) {
        if (vg.hal->storage_open(vg.profile.base.id[0] ? vg.profile.base.id : VG_NAME) != 0) {
            lrv_log(vg.hal, LRV_LOG_WARN, "the saves cannot be opened");
            return 0;
        }
        opened = 1;
    }
    return 1;
}

void vg_save_slot(int slot)
{
    struct vg_vm *m = &vg.vm;
    size_t len, end, cap = 72 + 3 * (size_t)m->scb.n_var;
    uint8_t *rec, *f;
    int n = 0, i, size = vg_save_record_size(), off = slot_offset(slot);

#define PUT8(v)  (rec[n++] = (uint8_t)(v))
#define PUT16(v) (PUT8((uint16_t)(v) >> 8), PUT8(v))
    if (!storage_ready() || off < 0 || !(rec = lrv_alloc(vg.hal, cap)))
        return;
    PUT8('S');
    PUT8('D');
    PUT16(size);
    PUT16(m->pc);
    PUT16(m->depth);
    for (i = 0; i < VG_CALL_STACK; i++)
        PUT16(m->stack[i]);
    for (i = 0; i < m->scb.n_var; i++) {
        PUT8(m->var[i].type);
        PUT16(m->var[i].value);
    }
#undef PUT8
#undef PUT16
    f = file_buf(&len);
    end = (size_t)off + (size_t)n;
    if (end > SAVE_MAX) {
        lrv_free(vg.hal, f, SAVE_MAX);
        lrv_free(vg.hal, rec, cap);
        return;
    }
    if (len < (size_t)off)
        memset(f + len, 0, (size_t)off - len);
    memcpy(f + off, rec, (size_t)n);
    lrv_free(vg.hal, rec, cap);
    if (end < len)
        end = len;
    if (vg.hal->storage_write(SAVE_KEY, f, end) != LRV_OK)
        lrv_log(vg.hal, LRV_LOG_WARN, "the save could not be written");
    lrv_free(vg.hal, f, SAVE_MAX);
}

struct rdf {
    const uint8_t *d;
    size_t n, p;
};

static int fgetc_(struct rdf *r)
{
    return r->p < r->n ? r->d[r->p++] : -1;
}

static uint16_t fget_be16(struct rdf *r)     /* 001E:0406 */
{
    uint16_t hi = (uint16_t)(fgetc_(r) << 8);
    return (uint16_t)(hi + (uint16_t)fgetc_(r));
}

void vg_load_slot(int slot)
{
    struct vg_vm *m = &vg.vm;
    struct rdf r;
    size_t len;
    uint8_t *f;
    int i, off = slot_offset(slot);

    if (!storage_ready())
        return;
    r.d = f = file_buf(&len);
    r.n = len;
    /* (no file: fopen fails; an empty one reads EOF: either way nothing is loaded) */
    r.p = off < 0 ? len : (size_t)off;
    if (fgetc_(&r) != 'S' || fgetc_(&r) != 'D' ||
        fget_be16(&r) != (uint16_t)vg_save_record_size()) {
        lrv_free(vg.hal, f, SAVE_MAX);
        return;
    }
    m->pc = fget_be16(&r);
    m->depth = (int16_t)fget_be16(&r);
    for (i = 0; i < VG_CALL_STACK; i++)
        m->stack[i] = fget_be16(&r);
    for (i = 0; i < m->scb.n_var; i++) {
        m->var[i].type = (int16_t)fgetc_(&r);
        m->var[i].value = (int16_t)fget_be16(&r);
    }
    lrv_free(vg.hal, f, SAVE_MAX);
}
