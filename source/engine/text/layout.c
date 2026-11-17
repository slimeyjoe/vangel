/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The layout of a translation: lrvne's reflow (lrvne/reflow.h, the same as tools/lrvne/
 * reflow.py) with the language's widths. docs/translation.md has where each kind of text is
 * laid out and how. */
#include <string.h>
#include "vg.h"
#include "lrvne/reflow.h"

static struct lrv_reflow s_r;           /* big: one, not on the stack */

void vg_lay(const uint8_t *text, int width, int height, int last, int first_line, int first_col,
            int indent, int keep_indent, struct vg_lay *out)
{
    struct lrv_reflow_at at;
    int i;
    at.first_line = first_line;
    at.first_col = first_col;
    at.indent = indent;
    at.flags = keep_indent ? LRV_REFLOW_KEEP_INDENT : 0;
    lrv_reflow_layout_from(text, width, height, last, &at, vg_lang_cols, NULL, &s_r);
    memset(out, 0, sizeof *out);
    for (i = 0; i < s_r.nlines && i < VG_LAY_MAX; i++) {
        struct vg_lay_line *l = &out->line[i];
        l->s = text + s_r.line[i].start;
        l->n = s_r.line[i].end - s_r.line[i].start;
        l->page = s_r.line[i].page;
        l->row = s_r.line[i].row;
        l->col = s_r.line[i].col;
        l->cols = s_r.line[i].cols;
    }
    out->nlines = i;
    out->npages = i ? out->line[i - 1].page + 1 : 0;
}

uint32_t vg_lay_fit(const uint8_t *text, int width, int *cols)
{
    return lrv_reflow_fit(text, width, vg_lang_cols, NULL, cols);
}
