/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The scenario loader: scb_load (063C:00E8) and its readers, docs/re/scenario-format.md §2-3.
 *
 * The original reads the file with fgetc, so its end reads as -1 (EOF): a plain reader
 * (06BB:0021) returns it as it is, the decrypting one (063C:0045) adds it to the key and
 * returns the low byte sign-extended, which is what a byte FFh gives. So a file cut short is
 * read on as if FFh bytes followed, and decides like one; here too. Only where the original
 * would read for ever (a string that never ends) or past its own records, the engine stops:
 *   - a string longer than its record holds: a picture name over 13 bytes (31h), a song name
 *     over 19 (1Bh), the text file's name over 63; a menu string over 1023;
 *   - a count whose table the original's 16-bit allocation size cannot hold, or a negative
 *     one (its loops then read nothing, but the tables are referenced as if they had it);
 * and fails the load, exit code 2. The original's writes over its heap in these cases are
 * not modelled.
 *
 * Every failure of the original ends with exit code 2 (a check's own exit(2), a loader's NULL,
 * or scb_load returning 0), except an allocation of a statement record, exit code 3. */
#include <string.h>
#include "vg.h"

#define VG_TEXT_NAME    63
#define VG_MENU_STR     1023

static const char s_sig[4] = { 'C', 'R', 'S', 'C' };     /* DS:1088 */

struct rd {
    const uint8_t *d;
    uint32_t n, p;
    uint16_t state;                     /* DS:1086 */
    uint16_t key;
    int fail;                           /* 0, or the exit code */
};

/* fgetc */
static int rawc(struct rd *r)
{
    if (r->p >= r->n)
        return -1;
    return r->d[r->p++];
}

/* 06BB:0037: the low bytes of two reads */
static int16_t raww(struct rd *r)
{
    int lo = rawc(r), hi = rawc(r);
    return (int16_t)(uint16_t)((lo & 0xFF) | (hi & 0xFF) << 8);
}

/* scb_getc 063C:0045 */
static int getc_(struct rd *r)
{
    int c = rawc(r);
    if (!r->key)
        return (int8_t)(uint8_t)c;
    r->state ^= (uint16_t)(c + r->key);
    return (int8_t)(uint8_t)r->state;
}

/* scb_getw 063C:0092 */
static int16_t getw_(struct rd *r)
{
    int lo = getc_(r), hi = getc_(r);
    return (int16_t)(uint16_t)((lo & 0xFF) | (hi & 0xFF) << 8);
}

/* ---- pools ------------------------------------------------------------------------------ */

static int oom;                         /* a pool could not grow */

static int grow(void **p, uint32_t *cap, uint32_t need, size_t elem)
{
    uint32_t n = *cap ? *cap : 256;
    void *q;
    if (need <= *cap)
        return 1;
    while (n < need)
        n *= 2;
    q = lrv_alloc(vg.hal, (size_t)n * elem);
    if (!q) {
        oom = 1;
        return 0;
    }
    if (*p) {
        memcpy(q, *p, (size_t)*cap * elem);
        lrv_free(vg.hal, *p, (size_t)*cap * elem);
    }
    *p = q;
    *cap = n;
    return 1;
}

static int put_w(struct vg_scb *s, int16_t v)
{
    if (!grow((void **)&s->w, &s->cap_w, s->nw + 1, sizeof *s->w))
        return 0;
    s->w[s->nw++] = v;
    return 1;
}

/* scb_gets 063C:00C0 into the string pool, at most max bytes; its offset in *at */
static int gets_(struct rd *r, uint32_t *at, int max)
{
    struct vg_scb *s = &vg.vm.scb;
    int c, k = 0;
    *at = s->nstr;
    for (;;) {
        c = getc_(r);
        if (r->fail)
            return 0;
        if (!grow((void **)&s->str, &s->cap_str, s->nstr + 1, 1))
            return 0;
        s->str[s->nstr++] = (char)c;
        if (!c)
            return 1;
        if (++k > max) {
            r->fail = VG_EXIT_LOAD;
            return 0;
        }
    }
}

/* ---- the header and the sections (06BB:01AB, 06BB:00F7) --------------------------------- */

static int read_header(struct rd *r)
{
    struct vg_scb *s = &vg.vm.scb;
    int i, t;

    for (i = 0; i < 4; i++)
        if (rawc(r) != s_sig[i])
            return 0;
    rawc(r);
    rawc(r);
    for (i = 0; i < 4; i++)
        rawc(r);
    s->size = (uint16_t)raww(r);
    s->size |= (uint32_t)(uint16_t)raww(r) << 16;
    s->h0e = (uint16_t)raww(r);
    s->h0e |= (uint32_t)(uint16_t)raww(r) << 16;
    s->entry = (uint16_t)raww(r);
    s->key = (uint16_t)rawc(r);
    for (;;) {
        t = rawc(r);
        if (r->fail)
            return 0;
        if (t < 0 || t > 0xC || (t >= 1 && t <= 3))
            return 0;
        switch (t) {
        case 0:
            return 1;
        case 4: s->n_stmt = raww(r); break;
        case 5: s->n_menu = raww(r); break;
        case 6: s->n_expr = raww(r); break;
        case 7: s->n_msg = raww(r); break;
        case 8: s->n_pal = raww(r); break;
        case 9: s->n_var = raww(r); break;
        case 0xB: s->n_0b = raww(r); break;
        case 0xC: s->n_0c = raww(r); break;
        case 0xA: {                     /* sec_textname 06BB:00AB */
            int n = raww(r), c, k = 0;
            if (n < 1 || n > 13)
                return 0;
            for (;;) {
                c = rawc(r);
                if (r->fail)
                    return 0;
                if (!c)
                    break;
                if (k >= VG_TEXT_NAME)
                    return 0;
                s->text[k++] = (char)c;
            }
            s->text[k] = 0;
            break;
        }
        }
    }
}

/* a table of n + 1 entries of `elem` bytes when the original's 16-bit size (n + 1) * orig
 * holds it */
static void *table(int n, size_t elem, unsigned orig)
{
    if (n < 0 || (uint32_t)(n + 1) * orig > 0xFFFFu)
        return NULL;
    return lrv_alloc(vg.hal, (size_t)(n + 1) * elem);
}

/* ---- the tables (segment 06DD) ---------------------------------------------------------- */

static int load_vars(struct rd *r)
{
    struct vg_scb *s = &vg.vm.scb;
    int i;
    if (!(s->var = table(s->n_var, sizeof *s->var, 4)))
        return 0;
    for (i = 1; i <= s->n_var; i++) {
        s->var[i].type = (int16_t)getc_(r);
        s->var[i].value = getw_(r);
        if (!(s->var[i].type & 2))
            return 0;
    }
    return 1;
}

static int load_menus(struct rd *r)
{
    struct vg_scb *s = &vg.vm.scb;
    uint32_t cap = 0;
    int i, k;
    if (!(s->menu = table(s->n_menu, sizeof *s->menu, 4)))
        return 0;
    for (i = 1; i <= s->n_menu; i++) {
        int n = getc_(r);
        if (n < 1 || n > VG_MENU_MAX)
            return 0;
        getw_(r);                       /* the strings' size: only allocates */
        s->menu[i].n = n;
        s->menu[i].number = i;
        for (k = 0; k < n; k++) {
            int c, len = 0;
            /* the offset now, a pointer once the pool stops moving */
            s->menu[i].item[k] = (const uint8_t *)(uintptr_t)s->menu_bytes;
            do {
                c = getc_(r);
                if (r->fail || ++len > VG_MENU_STR + 1)
                    return 0;
                if (!grow((void **)&s->menu_str, &cap, s->menu_bytes + 1, 1))
                    return 0;
                s->menu_str[s->menu_bytes++] = (uint8_t)c;
            } while (c);
        }
    }
    for (i = 1; i <= s->n_menu; i++)
        for (k = 0; k < s->menu[i].n; k++)
            s->menu[i].item[k] = s->menu_str + (uintptr_t)s->menu[i].item[k];
    /* the pool keeps its capacity as its size for vg_scb_free */
    s->menu_bytes = cap;
    return 1;
}

static int load_exprs(struct rd *r)
{
    struct vg_scb *s = &vg.vm.scb;
    int i;
    if (!(s->expr = table(s->n_expr, sizeof *s->expr, 12)))
        return 0;
    for (i = 1; i <= s->n_expr; i++) {
        struct vg_expr *e = &s->expr[i];
        e->form = (int16_t)getc_(r);
        if (e->form == 0) {
            e->k = (int16_t)getc_(r);
            e->a = getw_(r);
            e->b = getw_(r);
        } else if (e->form == 1) {
            e->k = (int16_t)getc_(r);
            e->a = getw_(r);
        } else {
            return 0;
        }
    }
    return 1;
}

/* scb_read_palette 06DD:03F5: 24 bytes, 48 nibbles high first, colour i = R, G, B */
static int load_palettes(struct rd *r)
{
    struct vg_scb *s = &vg.vm.scb;
    int i, k, c;
    if (!(s->pal = table(s->n_pal, sizeof *s->pal, 48)))
        return 0;
    for (i = 1; i <= s->n_pal; i++) {
        uint8_t nib[48];
        for (k = 0; k < 24; k++) {
            c = getc_(r) & 0xFF;
            nib[2 * k] = (uint8_t)(c >> 4);
            nib[2 * k + 1] = (uint8_t)(c & 15);
        }
        for (k = 0; k < 16; k++) {
            s->pal[i][k] = nib[3 * k];
            s->pal[i][16 + k] = nib[3 * k + 1];
            s->pal[i][32 + k] = nib[3 * k + 2];
        }
    }
    return 1;
}

/* ---- the statements (063C:011E and the loaders of table 0B77:0000) ---------------------- */

/* 0 = invalid (NULL), else 1; r->fail for the reader's own failures */
static int load_stmt(struct rd *r, struct vg_stmt *st)
{
    struct vg_scb *s = &vg.vm.scb;
    int op = getc_(r), a, b, c, i;
    int16_t w;

    if (op < 0)
        return 0;
    st->op = (uint8_t)op;
    st->at = s->nw;
    switch (op) {
    case 0x16: case 0x17: case 0x18: case 0x1D: case 0x2B: case 0x2D: case 0x2E: case 0x35:
    case 0x36:
        return 1;
    case 0x15:                          /* time, skippable */
        w = getw_(r);
        return put_w(s, w) && put_w(s, getc_(r) != 0);
    case 0x19:                          /* message */
        w = getw_(r);
        if (w < 0 || w > s->n_msg)
            return 0;
        return put_w(s, w);
    case 0x1A:                          /* to white, time */
        a = getc_(r) != 0;
        return put_w(s, (int16_t)a) && put_w(s, getw_(r));
    case 0x1B:                          /* volume, song */
        if (!put_w(s, getw_(r)))
            return 0;
        return gets_(r, &st->str, 19);
    case 0x1C: case 0x21: case 0x22: case 0x2F:
        return put_w(s, getw_(r));
    case 0x1E:                          /* expr, variable */
        w = getw_(r);
        if (w < 0 || w > s->n_expr)
            return 0;
        a = getc_(r);
        if (a < 1)
            return 0;
        return put_w(s, w) && put_w(s, (int16_t)a);
    case 0x1F: {                        /* expr, then, else */
        int16_t t, e;
        w = getw_(r);
        if (w < 0 || w > s->n_expr)
            return 0;
        t = getw_(r);
        e = getw_(r);
        if (t < 0 || e < 0 || (t == 0 && e > 0))
            return 0;
        return put_w(s, w) && put_w(s, t) && put_w(s, e);
    }
    case 0x20: {                        /* (ignored), expr, n, default, n x (value, target) */
        int16_t def;
        getc_(r);
        w = getw_(r);
        if (w < 0 || w > s->n_expr)
            return 0;
        a = getc_(r);
        if (a < 1 || a > VG_CASES_MAX)
            return 0;
        def = getw_(r);
        if (def < 0)
            return 0;
        st->n = (uint8_t)a;
        if (!put_w(s, w) || !put_w(s, def))
            return 0;
        for (i = 0; i < a; i++) {
            int16_t v = getw_(r);
            if (!put_w(s, v) || !put_w(s, getw_(r)))
                return 0;
        }
        return 1;
    }
    case 0x23:                          /* expr (0: none) */
        w = getw_(r);
        if (w < 0 || w > s->n_expr)
            return 0;
        return put_w(s, w);
    case 0x24:                          /* menu */
        w = getw_(r);
        if (w < 1 || w > s->n_menu)
            return 0;
        return put_w(s, w);
    case 0x25: case 0x33: case 0x34:    /* builtin; buffer; displacement */
        return put_w(s, (int16_t)getc_(r));
    case 0x37:                          /* flag == 1 */
        return put_w(s, getc_(r) == 1);
    case 0x30:                          /* time, palette (unsigned; <= 1: none) */
        w = getw_(r);
        a = getc_(r) & 0xFF;
        return put_w(s, w) && put_w(s, (int16_t)(a <= 1 ? 0 : a));
    case 0x31:                          /* buffer, x, y, flag, name */
        a = getc_(r);
        if (!put_w(s, (int16_t)a))
            return 0;
        w = getw_(r);
        if (!put_w(s, w) || !put_w(s, getw_(r)))
            return 0;
        b = getc_(r);
        if (!put_w(s, (int16_t)b))
            return 0;
        return gets_(r, &st->str, 13);
    case 0x32:                          /* src, sx, sy, w, h, dst, dx, dy, effect */
        a = getc_(r);
        if (!put_w(s, (int16_t)a))
            return 0;
        for (i = 0; i < 4; i++)
            if (!put_w(s, getw_(r)))
                return 0;
        b = getc_(r);
        if (!put_w(s, (int16_t)b))
            return 0;
        for (i = 0; i < 2; i++)
            if (!put_w(s, getw_(r)))
                return 0;
        c = getc_(r);
        return put_w(s, (int16_t)c);
    default:                            /* 26h-2Ah, 2Ch, anything not in the table */
        return 0;
    }
}

static int load_stmts(struct rd *r)
{
    struct vg_scb *s = &vg.vm.scb;
    int i;
    if (!(s->stmt = table(s->n_stmt, sizeof *s->stmt, 4)))
        return VG_EXIT_LOAD;
    for (i = 1; i <= s->n_stmt; i++) {
        int ok = load_stmt(r, &s->stmt[i]);
        if (r->fail)
            return r->fail;
        if (!ok)                        /* stmt_alloc's malloc: exit(3) */
            return oom ? VG_EXIT_MEMORY : VG_EXIT_LOAD;
    }
    return VG_EXIT_OK;
}

int vg_scb_load(const uint8_t *data, uint32_t size)
{
    struct vg_scb *s = &vg.vm.scb;
    struct rd r;
    int rc;

    vg_scb_free();
    oom = 0;
    strcpy(s->text, "scenario.txb");    /* init_names 0468:0191 */
    memset(&r, 0, sizeof r);
    r.d = data;
    r.n = size;
    if (!read_header(&r))
        return VG_EXIT_LOAD;
    r.key = s->key;
    if (!load_vars(&r) || r.fail || !load_menus(&r) || r.fail || !load_exprs(&r) || r.fail ||
        !load_palettes(&r) || r.fail)
        return VG_EXIT_LOAD;
    rc = load_stmts(&r);
    return rc;
}

void vg_scb_free(void)
{
    struct vg_scb *s = &vg.vm.scb;
    const struct lrv_hal *h = vg.hal;
    if (s->var)
        lrv_free(h, s->var, (size_t)(s->n_var + 1) * sizeof *s->var);
    if (s->menu)
        lrv_free(h, s->menu, (size_t)(s->n_menu + 1) * sizeof *s->menu);
    if (s->expr)
        lrv_free(h, s->expr, (size_t)(s->n_expr + 1) * sizeof *s->expr);
    if (s->pal)
        lrv_free(h, s->pal, (size_t)(s->n_pal + 1) * sizeof *s->pal);
    if (s->stmt)
        lrv_free(h, s->stmt, (size_t)(s->n_stmt + 1) * sizeof *s->stmt);
    if (s->w)
        lrv_free(h, s->w, (size_t)s->cap_w * sizeof *s->w);
    if (s->str)
        lrv_free(h, s->str, s->cap_str);
    if (s->menu_str)
        lrv_free(h, s->menu_str, s->menu_bytes);
    memset(s, 0, sizeof *s);
}
