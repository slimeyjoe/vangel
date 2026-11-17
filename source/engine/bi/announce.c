/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Built-in 3 ANNOUNCE (0504:0114): the text file announce.txt, page by page, on the
 * 80-column grid (docs/re/platform.md §5.4, text.md §5.2).
 *
 * The file is read as the original's C library reads a file opened "r": text mode, CR LF
 * becomes LF, Ctrl-Z ends it; fgets of at most 82 bytes a line, of which the last is cut (the
 * LF, or a character of a line without one). "#p" at a line's start ends the page, as the 23rd
 * line does; "#e" ends the file. */
#include <string.h>
#include "vg.h"

#define FGETS_N 83                      /* fgets(buf, 83, f) */

struct tfile {
    const uint8_t *d;
    uint32_t n, pos;
};

static int t_getc(struct tfile *f)
{
    int c;
    if (f->pos >= f->n || f->d[f->pos] == 0x1A)
        return -1;
    c = f->d[f->pos++];
    if (c == '\r' && f->pos < f->n && f->d[f->pos] == '\n') {
        f->pos++;
        c = '\n';
    }
    return c;
}

static int t_gets(uint8_t *buf, int n, struct tfile *f)
{
    int i = 0, c;
    while (i < n - 1 && (c = t_getc(f)) >= 0) {
        buf[i++] = (uint8_t)c;
        if (c == '\n')
            break;
    }
    buf[i] = 0;
    return i > 0;
}

/* a page's end: the standard palette, the prompt (key: its translation's), an input, the
 * screen cleared */
static void page_end(const uint8_t *prompt, const char *key)
{
    vg_pal_fade_in(vg.gfx.pal_default, 1);
    vg_bi_text(0, 23, prompt, vg_lang_get("%s", key), 0xE1, 0);
    vg_bi_wait_any();
    vg_pal_fade_out(0, 1);
    vg_screen_clear();
}

/* the end of the file's page p: a translated page (docs/translation.md) is laid out on the 23
 * rows and 80 columns, indentation kept, and drawn now, as many pages as it needs (the prompt
 * after each, the file's last one after the last); an original page was drawn as it was read */
static void page_out(int p, int last)
{
    static struct vg_lay lay;
    const uint8_t *tl = vg_lang_get("announce.%d", p);
    const struct vg_bi *b = &vg.bi;
    int np, pg, k = 0;
    if (!tl) {
        if (last)
            page_end(b->str[VG_BI_ANNOUNCE_LAST], "bi.announce.last");
        else
            page_end(b->str[VG_BI_ANNOUNCE_PROMPT], "bi.announce.prompt");
        return;
    }
    vg_lay(tl, VG_BI_ANNOUNCE_W, VG_BI_ANNOUNCE_H, VG_BI_ANNOUNCE_W, 0, 0, 0, 1, &lay);
    np = lay.npages ? lay.npages : 1;
    for (pg = 0; pg < np && !lrv_sys_quitting(&vg.sys); pg++) {
        for (; k < lay.nlines && lay.line[k].page == pg; k++) {
            const struct vg_lay_line *l = &lay.line[k];
            vg_text_tl(VG_TL_ANNOUNCE, pg, l->row, l->col, l->s, l->n);
            vg_bi_line_utf8(l->col, l->row, l->s, l->n, 0xE1);
        }
        if (last && pg == np - 1)
            page_end(b->str[VG_BI_ANNOUNCE_LAST], "bi.announce.last");
        else
            page_end(b->str[VG_BI_ANNOUNCE_PROMPT], "bi.announce.prompt");
    }
}

void vg_bi_announce(void)
{
    const struct lrv_pack_entry *e;
    struct tfile f;
    uint8_t line[0x6E], *data;
    uint32_t size = 0;
    int row = 0, eof = 0, p = 0;

    vg_pal_fade_out(0, 1);
    vg_screen_clear();
    e = lrv_pack_find(&vg.pak, (const char *)vg.bi.str[VG_BI_ANNOUNCE_FILE], VG_PT_FILE);
    data = e ? lrv_pack_load(&vg.pak, e, &size) : NULL;
    if (!data) {
        /* (drawn while the palette is black: nothing is seen) */
        vg_bi_text(0, 0, vg.bi.str[VG_BI_ANNOUNCE_MISSING], vg_lang_get("bi.announce.missing"),
                   0xE1, 0);
        return;
    }
    f.d = data;
    f.n = size;
    f.pos = 0;
    while (!eof && !lrv_sys_quitting(&vg.sys)) {
        if (!t_gets(line, FGETS_N, &f)) {
            eof = 1;
            continue;
        }
        if (line[0] == '#' && line[1] == 'e') {
            eof = 1;
            continue;
        }
        if (!(line[0] == '#' && line[1] == 'p')) {
            /* (an empty string, from a line that starts with a NUL byte, makes the original
             * clear the byte before its buffer: not modelled) */
            size_t n = strlen((const char *)line);
            if (n)
                line[n - 1] = 0;
            if (!vg_lang_get("announce.%d", p))
                vg_bi_line(0, row, line, 0xE1);
            if (++row != 23)
                continue;
        }
        row = 0;
        page_out(p++, 0);
    }
    lrv_pack_free(&vg.pak, data, size);
    page_out(p, 1);
}
