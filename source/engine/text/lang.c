/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The language's text (text.h; docs/translation.md). The table, tools/vgtext.py: "VGTX", u16
 * version 1, u16 0, u32 count, count x {u32 key offset, u32 text offset} sorted by key, then
 * the NUL-terminated keys and texts (UTF-8). A key is looked up where the original prints the
 * text; without a translation the original is printed as it was. */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "lrvne/endian.h"
#include "lrvne/utf8.h"

#define HEAD 12

static struct vg_lang *L(void)
{
    return &vg.text.lang;
}

void vg_lang_free(void)
{
    struct vg_lang *l = L();
    if (l->tab)
        lrv_pack_free(&vg.pak, l->tab, l->size);
    lrv_font_free(&l->latin8);
    lrv_font_free(&l->wide16);
    memset(l, 0, sizeof *l);
}

static int table_ok(const uint8_t *t, uint32_t size, uint32_t *count)
{
    uint32_t n, i;
    if (size < HEAD || memcmp(t, "VGTX", 4) || lrv_rd16le(t + 4) != 1)
        return 0;
    n = lrv_rd32le(t + 8);
    if (n > (size - HEAD) / 8 || t[size - 1] != 0)
        return 0;
    for (i = 0; i < n; i++) {
        uint32_t k = lrv_rd32le(t + HEAD + 8 * i), x = lrv_rd32le(t + HEAD + 8 * i + 4);
        if (k < HEAD + 8 * n || k >= size || x < HEAD + 8 * n || x >= size)
            return 0;
        if (i && strcmp((const char *)t + lrv_rd32le(t + HEAD + 8 * (i - 1)),
                        (const char *)t + k) >= 0)
            return 0;
    }
    *count = n;
    return 1;
}

void vg_lang_init(void)
{
    struct vg_lang *l = L();
    const struct lrv_pack_entry *e;
    vg_lang_free();
    /* only the selected language's own table: the original's language has none */
    if (!vg.pak.lang || !(e = lrv_pack_find(&vg.pak, "text", LRV_PT_STRINGS)) ||
        e->lang != vg.pak.lang)
        return;
    l->tab = lrv_pack_load(&vg.pak, e, &l->size);
    if (!l->tab || !table_ok(l->tab, l->size, &l->count) ||
        lrv_font_load(&l->latin8, &vg.pak, "latin8", 8, 16) != LRV_OK ||
        lrv_font_load(&l->wide16, &vg.pak, "wide16", 16, 16) != LRV_OK) {
        lrv_log(vg.hal, LRV_LOG_ERROR, "lang: the language's table or fonts are missing or "
                "damaged (make pack): the original text is shown");
        vg_lang_free();
        return;
    }
    lrv_log(vg.hal, LRV_LOG_INFO, "lang: %s, %u strings", lrv_pack_lang_tag(&vg.pak,
            vg.pak.lang), (unsigned)l->count);
}

int vg_lang_active(void)
{
    return L()->tab != NULL;
}

static const uint8_t *find(const char *key)
{
    const struct vg_lang *l = L();
    uint32_t lo = 0, hi = l->count;
    if (!l->tab)
        return NULL;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2;
        const uint8_t *e = l->tab + HEAD + 8 * mid;
        int c = strcmp((const char *)l->tab + lrv_rd32le(e), key);
        if (!c)
            return l->tab + lrv_rd32le(e + 4);
        if (c < 0)
            lo = mid + 1;
        else
            hi = mid;
    }
    return NULL;
}

const uint8_t *vg_lang_get(const char *fmt, ...)
{
    char key[64];
    va_list ap;
    if (!L()->tab)
        return NULL;
    va_start(ap, fmt);
    vsnprintf(key, sizeof key, fmt, ap);
    va_end(ap);
    return find(key);
}

const uint8_t *vg_lang_name(const uint8_t *name)
{
    static const char hex[] = "0123456789ABCDEF";
    char key[64];
    size_t i, n = strlen((const char *)name);
    if (n > (sizeof key - 3) / 2)
        return NULL;
    key[0] = 'n';
    key[1] = '.';
    for (i = 0; i < n; i++) {
        key[2 + 2 * i] = hex[name[i] >> 4];
        key[3 + 2 * i] = hex[name[i] & 15];
    }
    key[2 + 2 * n] = 0;
    return find(key);
}

int vg_lang_cols(void *ctx, uint32_t cp)
{
    (void)ctx;
    if (cp < 0x20)
        return 0;
    return cp <= 0xFFFF && lrv_font_glyph(&L()->latin8, cp) ? 1 : 2;
}

int vg_lang_glyph(uint32_t cp, uint16_t rows[16])
{
    const uint8_t *g;
    int r;
    if (cp <= 0xFFFF && (g = lrv_font_glyph(&L()->latin8, cp)) != NULL) {
        for (r = 0; r < 16; r++)
            rows[r] = g[r];
        return 1;
    }
    g = cp <= 0xFFFF ? lrv_font_glyph(&L()->wide16, cp) : NULL;
    for (r = 0; r < 16; r++)
        rows[r] = (uint16_t)(g ? g[2 * r] << 8 | g[2 * r + 1] : 0);
    return 2;
}

int vg_lang_width(const uint8_t *s, uint32_t n)
{
    uint32_t i = 0;
    int w = 0;
    while (s[i] && (!n || i < n)) {
        uint32_t cp;
        i += (uint32_t)lrv_utf8_decode(s + i, &cp);
        w += vg_lang_cols(NULL, cp);
    }
    return w;
}
