/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The picture library ("GA00", GDATA.LIB) and its pictures ("GF0", .gf): docs/re/graphics.md
 * §2-3. The decoder is M.EXE's gf_core (015A:003D), the output its flush routines (015A:0471
 * opaque, 015A:09BB with colour 8 transparent). */
#ifndef VG_GFX_GF_H
#define VG_GFX_GF_H

#include <stdint.h>
#include "lrvne/hal.h"
#include "lrvne/pack.h"
#include "lrvne/surface.h"

#define GF_MAX_W        640             /* the original's line ring holds no wider picture */
#define GF_RING_BYTES   (4 * GF_MAX_W)  /* the decoder's history: four lines */
#define GF_TRANSPARENT  8               /* the colour flag 1 leaves out (015A:09D6) */

/* The library: its directory, read once; the pictures are read from the pack entry as the
 * original reads them from the file, the decoder taking bytes past a member's end (they are
 * the next member's; past the library's end it gets zeros). */
struct gf_lib {
    const struct lrv_hal *hal;
    const struct lrv_pack *pak;
    const struct lrv_pack_entry *e;
    int count;                          /* pictures */
    uint32_t base;                      /* the data base: (count + 2) * 16 (0855:015F) */
    uint8_t *dir;                       /* (count + 1) x 16 bytes of entries */
};

struct gf_header {
    int w, h;                           /* pixels; w a multiple of 8 */
    int x, y;                           /* the position the file gives */
};

/* Opens the library in pack entry e: LRV_OK, LRV_ERR_FORMAT (no "GA00", no final FFh entry,
 * an entry outside the data), LRV_ERR_NOMEM. */
int  gf_lib_open(struct gf_lib *lib, const struct lrv_hal *hal, const struct lrv_pack *pak,
                 const struct lrv_pack_entry *e);
void gf_lib_close(struct gf_lib *lib);
/* The member named `name` ("va_main.gf"; compared case-sensitively, as 0823:012A): its index,
 * or -1. */
int  gf_lib_find(const struct gf_lib *lib, const char *name);
/* Member i: its name ("name.ext") into buf (13 bytes), its offset in the library and its size. */
void gf_lib_member(const struct gf_lib *lib, int i, char *name, uint32_t *off, uint32_t *size);

/* The pixels of a picture's lines, one byte (0..15) each, as the decoder completes them. */
typedef void gf_row_fn(void *ctx, int row, const uint8_t *pixels, int w);

/* Decodes member i: its header into *hdr, every line to row(). LRV_OK, LRV_ERR_FORMAT (no
 * "GF0", w not a multiple of 8 or above GF_MAX_W), LRV_ERR_IO. */
int  gf_decode(const struct gf_lib *lib, int i, struct gf_header *hdr, gf_row_fn *row,
               void *ctx);

/* Draws member i into a planar surface (a VRAM page or buffer 12), as op 31h's decoders do: at
 * (x, y), or at the file's position (each of x, y = -1; a file value outside the screen is 0);
 * x is taken in whole bytes (x >> 3); lines past the surface's end are left out. transparent:
 * colour 8 keeps what is there. The rectangle drawn (columns of 8 pixels) goes to *drawn when
 * it is not NULL. LRV_OK or the errors of gf_decode. */
int  gf_draw(const struct gf_lib *lib, int i, struct lrv_surface *dst, int x, int y,
             int transparent, struct gf_header *hdr, struct lrv_rect *drawn);

#endif
