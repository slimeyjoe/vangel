/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The direct VRAM routines of segment 05C3 that the built-in sequences use (docs/re/text.md
 * §5.1, §5.3, §5.4; platform.md §5): glyphs from the kanji ROM and the game's half-width font
 * written into the access page, the prologue's wipe, the staff roll's double-size glyphs, its
 * colour change and its outline, and a GRCG fill.
 *
 * Addresses are as the original's: a plane offset y * 80 + x of the page selected by port A6h
 * (the screen's access page). The GRCG accesses are modelled by what they do to the four
 * planes: RMW with tiles FFh sets the data's pixels to colour 15, with tiles 0 to colour 0; a
 * compare read with tiles FFh gives the pixels of colour 15. Offsets are 16-bit, as in the
 * original's segment; a byte past the 32 000 of a plane (memory that is never shown) reads as
 * 0 and is not written. */
#include <string.h>
#include "vg.h"

static struct lrv_surface *page(void)
{
    return lrv_screen_access(&vg.screen);
}

static void mark(unsigned off, int wb, int h)
{
    lrv_screen_mark_off(&vg.screen, vg.screen.access_page, (int)(off & 0xFFFF), wb, h);
}

static uint8_t *at(struct lrv_surface *pg, int q, unsigned off)
{
    off &= 0xFFFF;
    return off < VG_PLANE_BYTES ? pg->plane[q] + off : NULL;
}

/* a byte written into plane q (direct access) */
static void put(struct lrv_surface *pg, int q, unsigned off, uint8_t v)
{
    uint8_t *p = at(pg, q, off);
    if (p)
        *p = v;
}

/* the GRCG's compare read with tiles FFh: the pixels of colour 15 */
static uint8_t is15(struct lrv_surface *pg, unsigned off)
{
    uint8_t m = 0xFF;
    int q;
    for (q = 0; q < 4; q++) {
        uint8_t *p = at(pg, q, off);
        m &= p ? *p : 0;
    }
    return m;
}

/* an RMW write of data d, tiles FFh (to = 15) or 0 (to = 0) */
static void rmw(struct lrv_surface *pg, unsigned off, uint8_t d, int to)
{
    int q;
    for (q = 0; q < 4; q++) {
        uint8_t *p = at(pg, q, off);
        if (p)
            *p = (uint8_t)(to ? *p | d : *p & ~d);
    }
}

/* INT 18h AH=14h for the Shift-JIS character lead, trail: 16 rows of 16 bits, the msb left */
static void rom16(unsigned lead, unsigned trail, uint16_t row[16])
{
    uint8_t g[32];
    int r;
    vg_kanji_rom(lead, trail, g);
    for (r = 0; r < 16; r++)
        row[r] = (uint16_t)(g[2 * r] << 8 | g[2 * r + 1]);
}

/* ank_glyph (0504:0B52): the game's half-width font */
static void ank16(unsigned ch, uint8_t row[16])
{
    const uint8_t *g = lrv_font_glyph(&vg.text.ank8, ch & 0xFF);
    if (g)
        memcpy(row, g, 16);
    else
        memset(row, 0, 16);
}

void vg_vram_kanji(int x, int y, unsigned lead, unsigned trail, int mode)
{
    struct lrv_surface *pg = page();
    uint16_t b[16];
    unsigned off = (unsigned)(y * VG_PLANE_STRIDE + x);
    int r, q;
    rom16(lead, trail, b);
    for (r = 0; r < 16; r++) {
        b[r] = lrv_glyph_bold16_plain(b[r]);
        if (mode == 0)
            b[r] = (uint16_t)~b[r];
    }
    for (q = 0; q < 4; q++)
        for (r = 0; r < 16; r++) {
            unsigned o = off + (unsigned)(r * VG_PLANE_STRIDE);
            uint8_t *p0 = at(pg, q, o), *p1 = at(pg, q, o + 1);
            uint8_t h = (uint8_t)(b[r] >> 8), l = (uint8_t)b[r];
            if (mode == 2) {
                if (p0)
                    *p0 |= h;
                if (p1)
                    *p1 |= l;
            } else {
                if (p0)
                    *p0 = h;
                if (p1)
                    *p1 = l;
            }
        }
    mark(off, 2, 16);
}

void vg_vram_ank(int x, int y, unsigned ch, int mode)
{
    struct lrv_surface *pg = page();
    uint8_t b[16];
    unsigned off = (unsigned)(y * VG_PLANE_STRIDE + x);
    int r, q;
    ank16(ch, b);
    for (r = 0; r < 16; r++) {
        b[r] = lrv_glyph_bold8_plain(b[r]);
        if (mode == 0)
            b[r] = (uint8_t)~b[r];
    }
    for (q = 0; q < 4; q++)
        for (r = 0; r < 16; r++) {
            uint8_t *p = at(pg, q, off + (unsigned)(r * VG_PLANE_STRIDE));
            if (p)
                *p = mode == 2 ? (uint8_t)(*p | b[r]) : b[r];
        }
    mark(off, 1, 16);
}

void vg_vram_kanji_wipe(int x, int row, unsigned lead, unsigned trail, void (*step)(void))
{
    struct lrv_surface *pg;
    uint16_t b[16];
    unsigned off = (unsigned)(row * 16 * VG_PLANE_STRIDE + x);
    uint16_t mask = 0x8000;
    int k, r, q;
    rom16(lead, trail, b);
    for (r = 0; r < 16; r++)
        b[r] = lrv_glyph_bold16_plain(b[r]);
    for (k = 0; k < 16; k++) {
        pg = page();
        for (q = 1; q <= 2; q++)        /* planes R and G only, written opaque */
            for (r = 0; r < 16; r++) {
                unsigned o = off + (unsigned)(r * VG_PLANE_STRIDE);
                uint16_t v = b[r] & mask;
                put(pg, q, o, (uint8_t)(v >> 8));
                put(pg, q, o + 1, (uint8_t)v);
            }
        mark(off, 2, 16);
        step();
        mask = (uint16_t)(mask >> 1 | 0x8000);  /* sar: one more column */
    }
}

/* each bit of the n-bit v twice: 2n bits, the msb left */
static uint32_t doubled(uint32_t v, int n)
{
    uint32_t d = 0;
    int i;
    for (i = n - 1; i >= 0; i--)
        d = d << 2 | ((v >> i) & 1) * 3u;
    return d;
}

void vg_vram_kanji_2x(int x, int row, unsigned lead, unsigned trail)
{
    struct lrv_surface *pg = page();
    uint16_t g[16];
    unsigned off = (unsigned)(row * 16 * VG_PLANE_STRIDE + x + VG_PLANE_STRIDE);
    int r, k, i;
    rom16(lead, trail, g);              /* no emboldening here */
    for (r = 0; r < 16; r++) {
        uint32_t d = doubled(g[r], 16);
        for (k = 0; k < 2; k++) {
            unsigned o = off + (unsigned)((2 * r + k) * VG_PLANE_STRIDE);
            for (i = 0; i < 4; i++)
                rmw(pg, o + (unsigned)i, (uint8_t)(d >> (24 - 8 * i)), 1);
        }
    }
    mark(off, 4, 32);
}

void vg_vram_ank_2x(int x, int row, unsigned ch, int mode)
{
    struct lrv_surface *pg = page();
    uint8_t g[16];
    unsigned off = (unsigned)(row * 16 * VG_PLANE_STRIDE + x + VG_PLANE_STRIDE);
    int r, k;
    ank16(ch, g);
    for (r = 0; r < 16; r++) {
        uint16_t d = (uint16_t)doubled(g[r], 8);
        for (k = 0; k < 2; k++) {
            /* mode 0 inverts the first of the two lines only, as the original does */
            uint16_t v = (uint16_t)(mode == 0 && k == 0 ? ~d : d);
            unsigned o = off + (unsigned)((2 * r + k) * VG_PLANE_STRIDE);
            rmw(pg, o, (uint8_t)(v >> 8), 1);
            rmw(pg, o + 1, (uint8_t)v, 1);
        }
    }
    mark(off, 2, 32);
}

/* ---- a translation's glyphs (docs/translation.md): the same routines for a glyph given as its
 * rows, 8 bits (w 1) or 16 (w 2) wide, the msb leftmost, not emboldened ------------------ */

void vg_vram_cell(int x, int y, const uint16_t g[16], int w, int mode)
{
    struct lrv_surface *pg = page();
    uint16_t b[16];
    unsigned off = (unsigned)(y * VG_PLANE_STRIDE + x);
    int r, q, k;
    for (r = 0; r < 16; r++) {
        b[r] = w == 2 ? lrv_glyph_bold16_plain(g[r]) : lrv_glyph_bold8_plain((uint8_t)g[r]);
        if (mode == 0)
            b[r] = (uint16_t)(w == 2 ? ~b[r] : (uint8_t)~b[r]);
    }
    for (q = 0; q < 4; q++)
        for (r = 0; r < 16; r++)
            for (k = 0; k < w; k++) {
                uint8_t *p = at(pg, q, off + (unsigned)(r * VG_PLANE_STRIDE + k));
                uint8_t v = (uint8_t)(w == 2 ? (k ? b[r] : b[r] >> 8) : b[r]);
                if (p)
                    *p = mode == 2 ? (uint8_t)(*p | v) : v;
            }
    mark(off, w, 16);
}

void vg_vram_cell_wipe(int x, int row, const uint16_t g[16], int w, void (*step)(void))
{
    struct lrv_surface *pg;
    uint16_t b[16], mask = 0x8000;
    unsigned off = (unsigned)(row * 16 * VG_PLANE_STRIDE + x);
    int k, r, q, steps = 8 * w;
    for (r = 0; r < 16; r++)            /* left-aligned in 16 bits */
        b[r] = (uint16_t)(w == 2 ? lrv_glyph_bold16_plain(g[r]) :
                          lrv_glyph_bold8_plain((uint8_t)g[r]) << 8);
    for (k = 0; k < steps; k++) {
        pg = page();
        for (q = 1; q <= 2; q++)        /* planes R and G only, written opaque */
            for (r = 0; r < 16; r++) {
                unsigned o = off + (unsigned)(r * VG_PLANE_STRIDE);
                uint16_t v = b[r] & mask;
                put(pg, q, o, (uint8_t)(v >> 8));
                if (w == 2)
                    put(pg, q, o + 1, (uint8_t)v);
            }
        mark(off, w, 16);
        step();
        mask = (uint16_t)(mask >> 1 | 0x8000);
    }
}

void vg_vram_cell_2x(int x, int row, const uint16_t g[16], int w)
{
    struct lrv_surface *pg = page();
    unsigned off = (unsigned)(row * 16 * VG_PLANE_STRIDE + x + VG_PLANE_STRIDE);
    int r, k, i;
    for (r = 0; r < 16; r++) {          /* not emboldened, as the roll's own glyphs */
        uint32_t d = doubled(g[r], 8 * w);
        for (k = 0; k < 2; k++) {
            unsigned o = off + (unsigned)((2 * r + k) * VG_PLANE_STRIDE);
            for (i = 0; i < 2 * w; i++)
                rmw(pg, o + (unsigned)i, (uint8_t)(d >> (8 * (2 * w - 1 - i))), 1);
        }
    }
    mark(off, 2 * w, 32);
}

void vg_vram_15_to_8(void)
{
    struct lrv_surface *pg = page();
    unsigned o;
    for (o = 0; o < VG_PLANE_BYTES; o++) {
        uint8_t m = (uint8_t)(pg->plane[0][o] & pg->plane[1][o] & pg->plane[2][o] &
                              pg->plane[3][o]);
        pg->plane[0][o] &= (uint8_t)~m;
        pg->plane[1][o] &= (uint8_t)~m;
        pg->plane[2][o] &= (uint8_t)~m;
    }
    vg_mark_lines(vg.screen.access_page, 0, VG_SCREEN_H);
}

/* the colour-15 pixels of the word at off as the original reads it (the left byte low) */
static unsigned word15(struct lrv_surface *pg, unsigned off)
{
    return is15(pg, off) | (unsigned)is15(pg, off + 1) << 8;
}

void vg_vram_outline(int x, int y, int words, int h)
{
    struct lrv_surface *pg = page();
    unsigned base = (unsigned)(VG_PLANE_STRIDE * y + x);
    int l, k;
    /* the lines above and below a word's text: the text widened by a pixel each way */
    for (l = 0; l < h; l++)
        for (k = 0; k < words; k++) {
            unsigned o = base + (unsigned)(l * VG_PLANE_STRIDE + 2 * k), w, up, dn, v, d;
            w = word15(pg, o);
            if (!w)
                continue;
            up = ~word15(pg, o - VG_PLANE_STRIDE) & 0xFFFF;
            dn = ~word15(pg, o + VG_PLANE_STRIDE) & 0xFFFF;
            v = (w >> 8 | w << 8) & 0xFFFF;         /* the pixels in order, the msb left */
            v = (v | v << 1 | v >> 1) & 0xFFFF;
            d = (v >> 8 | v << 8) & 0xFFFF;
            rmw(pg, o - VG_PLANE_STRIDE, (uint8_t)(d & up), 0);
            rmw(pg, o - VG_PLANE_STRIDE + 1, (uint8_t)((d & up) >> 8), 0);
            rmw(pg, o + VG_PLANE_STRIDE, (uint8_t)(d & dn), 0);
            rmw(pg, o + VG_PLANE_STRIDE + 1, (uint8_t)((d & dn) >> 8), 0);
        }
    /* across the words' edges: the pixel beside a word's first and last, on its line and the
     * lines above and below */
    for (l = 0; l < h; l++)
        for (k = 0; k < words; k++) {
            unsigned o = base + (unsigned)(l * VG_PLANE_STRIDE + 2 * k), t;
            uint8_t nl, nul, ndl, nr, nur, ndr;
            t = word15(pg, o) & 0x0180;
            if (!t)
                continue;
            nl = (uint8_t)~is15(pg, o - 1);
            nul = (uint8_t)~is15(pg, o - 81);
            ndl = (uint8_t)~is15(pg, o + 79);
            nr = (uint8_t)~is15(pg, o + 2);
            nur = (uint8_t)~is15(pg, o - 78);
            ndr = (uint8_t)~is15(pg, o + 82);
            if (t & 0x80) {
                rmw(pg, o - 1, nl & 1, 0);
                rmw(pg, o - 81, nul & 1, 0);
                rmw(pg, o + 79, ndl & 1, 0);
            }
            if (t & 0x100) {
                rmw(pg, o + 2, nr & 0x80, 0);
                rmw(pg, o - 78, nur & 0x80, 0);
                rmw(pg, o + 82, ndr & 0x80, 0);
            }
        }
    mark(base - VG_PLANE_STRIDE, 2 * words + 3, h + 2);
}

void vg_vram_fill_black(int xw, int y, int ww, int h)
{
    struct lrv_surface *pg = page();
    unsigned off = (unsigned)(y * VG_PLANE_STRIDE + 2 * xw);
    int l, k;
    for (l = 0; l < h; l++)
        for (k = 0; k < 2 * ww; k++)
            rmw(pg, off + (unsigned)(l * VG_PLANE_STRIDE + k), 0xFF, 0);
    mark(off, 2 * ww, h);
}
