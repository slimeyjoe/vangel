/* SPDX-License-Identifier: GPL-3.0-or-later */
/* GDATA.LIB and the .gf decoder (docs/re/graphics.md §2-3; the reference model is
 * source/tools/gf.py, verified bit-exact against M.EXE by re-tools/gf_verify.py). */
#include <string.h>
#include "gf.h"
#include "lrvne/core.h"
#include "lrvne/endian.h"

#define GA_HEADER   16
#define GA_ENTRY    16
#define GF_HEADER   12
#define READ_CHUNK  0x0FD2              /* the original reads its file in blocks this big */

int gf_lib_open(struct gf_lib *lib, const struct lrv_hal *hal, const struct lrv_pack *pak,
                const struct lrv_pack_entry *e)
{
    uint8_t head[GA_HEADER];
    uint32_t dir_bytes;
    int i;

    memset(lib, 0, sizeof *lib);
    lib->hal = hal;
    lib->pak = pak;
    lib->e = e;
    if (lrv_pack_read(pak, e, 0, head, sizeof head) != sizeof head || memcmp(head, "GA00", 4))
        return LRV_ERR_FORMAT;
    lib->count = lrv_rd16le(head + 8);  /* the engine reads the low word (0855:000C) */
    lib->base = (uint32_t)(lib->count + 2) * 16;
    dir_bytes = (uint32_t)(lib->count + 1) * GA_ENTRY;
    if (GA_HEADER + dir_bytes > e->size)
        return LRV_ERR_FORMAT;
    lib->dir = lrv_alloc(hal, dir_bytes);
    if (!lib->dir)
        return LRV_ERR_NOMEM;
    if (lrv_pack_read(pak, e, GA_HEADER, lib->dir, dir_bytes) != dir_bytes ||
        lib->dir[lib->count * GA_ENTRY] != 0xFF) {
        gf_lib_close(lib);
        return LRV_ERR_FORMAT;
    }
    for (i = 0; i < lib->count; i++) {
        uint32_t off, size;
        gf_lib_member(lib, i, NULL, &off, &size);
        if (off > e->size || size > e->size - off) {
            gf_lib_close(lib);
            return LRV_ERR_FORMAT;
        }
    }
    return LRV_OK;
}

void gf_lib_close(struct gf_lib *lib)
{
    if (lib->dir)
        lrv_free(lib->hal, lib->dir, (size_t)(lib->count + 1) * GA_ENTRY);
    lib->dir = NULL;
    lib->count = 0;
}

static void member_name(const uint8_t *ent, char *out)
{
    int n = 0, k;
    for (k = 0; k < 8 && ent[k]; k++)
        out[n++] = (char)ent[k];
    if (ent[8]) {
        out[n++] = '.';
        for (k = 8; k < 11 && ent[k]; k++)
            out[n++] = (char)ent[k];
    }
    out[n] = 0;
}

void gf_lib_member(const struct gf_lib *lib, int i, char *name, uint32_t *off, uint32_t *size)
{
    const uint8_t *ent = lib->dir + (size_t)i * GA_ENTRY;
    uint32_t a = lrv_rd32le(ent + 12), b = lrv_rd32le(ent + GA_ENTRY + 12);
    if (name)
        member_name(ent, name);
    if (off)
        *off = lib->base + a;
    if (size)
        *size = b >= a ? b - a : 0;
}

int gf_lib_find(const struct gf_lib *lib, const char *name)
{
    char buf[13];
    int i;
    for (i = 0; i < lib->count; i++) {
        member_name(lib->dir + (size_t)i * GA_ENTRY, buf);
        if (!strcmp(buf, name))
            return i;
    }
    return -1;
}

/* ---- the decoder (gf_core 015A:003D) ------------------------------------------------------ */

struct bits {
    const struct gf_lib *lib;
    uint32_t pos;                       /* the next byte's offset in the library */
    uint8_t chunk[READ_CHUNK];
    uint32_t chunk_pos;                 /* the library offset of chunk[0] */
    uint32_t chunk_len;
    unsigned cur, left;
};

static unsigned next_byte(struct bits *b)
{
    uint32_t total = b->lib->e->size;
    unsigned v;
    if (b->pos >= total) {
        b->pos++;
        return 0;                       /* past the library: the original reads nothing */
    }
    if (b->pos < b->chunk_pos || b->pos >= b->chunk_pos + b->chunk_len) {
        uint32_t n = total - b->pos < READ_CHUNK ? total - b->pos : READ_CHUNK;
        b->chunk_pos = b->pos;
        b->chunk_len = (uint32_t)lrv_pack_read(b->lib->pak, b->lib->e, b->pos, b->chunk, n);
        if (!b->chunk_len) {
            b->pos++;
            return 0;
        }
    }
    v = b->chunk[b->pos - b->chunk_pos];
    b->pos++;
    return v;
}

static inline unsigned bit(struct bits *b)
{
    if (!b->left) {
        b->cur = next_byte(b);
        b->left = 8;
    }
    b->left--;
    return (b->cur >> b->left) & 1;
}

/* One colour in the context of the colour to its left (gf_colour_pair 015A:0315, one half):
 * an index into that colour's move-to-front list (gf_mtf_init 015A:043D). */
static unsigned colour(struct bits *b, uint8_t table[16][16], unsigned prev)
{
    uint8_t *row = table[prev & 15];
    unsigned idx, c;
    if (bit(b))
        idx = bit(b);                                       /* 1x:     0..1  */
    else if (!bit(b))
        idx = 2 + bit(b);                                   /* 00x:    2..3  */
    else if (!bit(b)) {
        idx = 4 + (bit(b) << 1);                            /* 010xx:  4..7  */
        idx |= bit(b);
    } else {
        idx = 8 + (bit(b) << 2);                            /* 011xxx: 8..15 */
        idx |= bit(b) << 1;
        idx |= bit(b);
    }
    c = row[idx];
    memmove(row + 1, row, idx);
    row[0] = (uint8_t)c;
    return c;
}

/* the history: absolute pixel position p (0 = the first of the two lines above the picture)
 * kept in a ring of four lines, which is aligned so a line is contiguous */
struct ring {
    uint8_t buf[GF_RING_BYTES];
    uint32_t size;                      /* 4 * w */
    uint32_t w, first;                  /* first = 2 * w: the picture's first pixel */
    gf_row_fn *row;
    void *ctx;
};

static inline uint8_t get(const struct ring *r, uint32_t p)
{
    return r->buf[p % r->size];
}

static inline void put(struct ring *r, uint32_t p, unsigned c)
{
    uint32_t q = p % r->size;
    r->buf[q] = (uint8_t)c;
    if (p >= r->first && (p - r->first + 1) % r->w == 0)
        r->row(r->ctx, (int)((p - r->first) / r->w), r->buf + q + 1 - r->w, (int)r->w);
}

int gf_decode(const struct gf_lib *lib, int i, struct gf_header *hdr, gf_row_fn *row,
              void *ctx)
{
    static struct bits b;               /* 4 KB: kept off the stack (the Amiga's is small) */
    static struct ring r;
    uint8_t head[GF_HEADER];
    uint8_t table[16][16];
    uint32_t off, size, total, p;
    int last = 0, k;
    unsigned c0, c1;

    gf_lib_member(lib, i, NULL, &off, &size);
    if (lrv_pack_read(lib->pak, lib->e, off, head, sizeof head) != sizeof head)
        return LRV_ERR_IO;
    if (memcmp(head, "GF0\0", 4))
        return LRV_ERR_FORMAT;
    hdr->w = lrv_rd16le(head + 4);
    hdr->h = lrv_rd16le(head + 6);
    hdr->x = lrv_rd16le(head + 8);
    hdr->y = lrv_rd16le(head + 10);
    if (hdr->w <= 0 || hdr->w > GF_MAX_W || hdr->w % 8 || hdr->h <= 0)
        return LRV_ERR_FORMAT;

    memset(&b, 0, sizeof b);
    b.lib = lib;
    b.pos = off + GF_HEADER;
    b.chunk_pos = 0xFFFFFFFFu;
    r.w = (uint32_t)hdr->w;
    r.size = 4 * r.w;
    r.first = 2 * r.w;
    r.row = row;
    r.ctx = ctx;
    for (k = 0; k < 256; k++)
        table[k >> 4][k & 15] = (uint8_t)(((k >> 4) - (k & 15)) & 15);

    /* the first colour pair, repeated over the two lines above the picture */
    c0 = colour(&b, table, 0);
    c1 = colour(&b, table, c0);
    for (p = 0; p < r.first; p += 2) {
        put(&r, p, c0);
        put(&r, p + 1, c1);
    }
    total = r.first + r.w * (uint32_t)hdr->h;
    while (p < total) {
        int id;                         /* the position's identity (the original's SI) */
        uint32_t src, n, cnt, j;
        if (bit(&b)) {
            if (!bit(&b))
                id = -2 * (int)r.w;                         /* 10:  two lines up */
            else if (bit(&b))
                id = -(int)r.w - 1;                         /* 111: up and left */
            else
                id = -(int)r.w + 1;                         /* 110: up and right */
            src = p + (uint32_t)id;
        } else if (bit(&b)) {
            id = -(int)r.w;                                 /* 01:  one line up */
            src = p + (uint32_t)id;
        } else {
            id = -4;                    /* 00: left: 2 back if those two match, else 4 back */
            src = get(&r, p - 2) == get(&r, p - 1) ? p - 2 : p - 4;
        }
        if (id == last) {
            /* the same position twice: literal colour pairs */
            for (;;) {
                unsigned a = colour(&b, table, get(&r, p - 1));
                unsigned c = colour(&b, table, a);
                put(&r, p, a);
                put(&r, p + 1, c);
                p += 2;
                if (p >= total || !bit(&b))
                    break;
            }
            last = 0;
            continue;
        }
        last = id;
        /* the length in 2-pixel units: 0 -> 1; 1^k 0 then k bits -> (1 << k) | bits */
        if (!bit(&b)) {
            n = 1;
        } else {
            int nb = 1;
            while (bit(&b))
                nb++;
            n = 1;
            while (nb--)
                n = n << 1 | bit(&b);
        }
        cnt = 2 * n < total - p ? 2 * n : total - p;
        for (j = 0; j < cnt; j++)       /* one pixel at a time: an overlap repeats */
            put(&r, p + j, get(&r, src + j));
        p += cnt;
    }
    return LRV_OK;
}

/* ---- output (gf_flush_vram 015A:0471, gf_flush_vram_t 015A:09BB) -------------------------- */

struct draw {
    struct lrv_surface *dst;
    uint32_t off0;                      /* byte offset of the picture's first line */
    int transparent;
};

static void draw_row(void *ctx, int row, const uint8_t *px, int w)
{
    const struct draw *d = ctx;
    uint32_t plane_bytes = lrv_surface_plane_bytes(d->dst);
    uint32_t o = d->off0 + (uint32_t)row * (uint32_t)d->dst->stride;
    int c, k, q;
    for (c = 0; c < w / 8; c++, o++, px += 8) {
        unsigned v[4] = { 0, 0, 0, 0 }, m = 0;
        if (o >= plane_bytes)
            continue;                   /* the original runs on past its planes */
        for (k = 0; k < 8; k++) {
            unsigned bitv = 0x80u >> k;
            if (d->transparent && px[k] == GF_TRANSPARENT) {
                m |= bitv;
                continue;
            }
            for (q = 0; q < 4; q++)
                if (px[k] >> q & 1)
                    v[q] |= bitv;
        }
        for (q = 0; q < 4; q++) {
            uint8_t *t = d->dst->plane[q] + o;
            *t = (uint8_t)(d->transparent ? (*t & m) | v[q] : v[q]);
        }
    }
}

int gf_draw(const struct gf_lib *lib, int i, struct lrv_surface *dst, int x, int y,
            int transparent, struct gf_header *hdr, struct lrv_rect *drawn)
{
    struct gf_header h;
    struct draw d;
    uint8_t head[GF_HEADER];
    uint32_t off, size;
    int rc;

    /* the position first: the decoder writes lines as it completes them */
    gf_lib_member(lib, i, NULL, &off, &size);
    if (lrv_pack_read(lib->pak, lib->e, off, head, sizeof head) != sizeof head)
        return LRV_ERR_IO;
    if (x == -1) {
        x = lrv_rd16le(head + 8);
        if (x > 639)
            x = 0;
    }
    if (y == -1) {
        y = lrv_rd16le(head + 10);
        if (y > 399)
            y = 0;
    }
    d.dst = dst;
    d.off0 = (uint32_t)y * (uint32_t)dst->stride + (uint32_t)(x >> 3);
    d.transparent = transparent;
    rc = gf_decode(lib, i, &h, draw_row, &d);
    if (hdr)
        *hdr = h;
    if (rc == LRV_OK && drawn) {
        lrv_rect_clear(drawn);
        lrv_rect_add(drawn, x >> 3, y, (x >> 3) + h.w / 8, y + h.h);
        lrv_rect_clip(drawn, dst);
    }
    return rc;
}
