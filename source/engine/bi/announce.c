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

/* a page's end: the standard palette, the prompt, an input, the screen cleared */
static void page_end(const uint8_t *prompt)
{
    vg_pal_fade_in(vg.gfx.pal_default, 1);
    vg_bi_line(0, 23, prompt, 0xE1);
    vg_bi_wait_any();
    vg_pal_fade_out(0, 1);
    vg_screen_clear();
}

void vg_bi_announce(void)
{
    const struct lrv_pack_entry *e;
    struct tfile f;
    uint8_t line[0x6E], *data;
    uint32_t size = 0;
    int row = 0, eof = 0;

    vg_pal_fade_out(0, 1);
    vg_screen_clear();
    e = lrv_pack_find(&vg.pak, (const char *)vg.bi.str[VG_BI_ANNOUNCE_FILE], VG_PT_FILE);
    data = e ? lrv_pack_load(&vg.pak, e, &size) : NULL;
    if (!data) {
        /* (drawn while the palette is black: nothing is seen) */
        vg_bi_line(0, 0, vg.bi.str[VG_BI_ANNOUNCE_MISSING], 0xE1);
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
            vg_bi_line(0, row, line, 0xE1);
            if (++row != 23)
                continue;
        }
        row = 0;
        page_end(vg.bi.str[VG_BI_ANNOUNCE_PROMPT]);
    }
    lrv_pack_free(&vg.pak, data, size);
    page_end(vg.bi.str[VG_BI_ANNOUNCE_LAST]);
}
