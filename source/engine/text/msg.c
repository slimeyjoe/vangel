/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Statement 19h: the page loop msg_show (0315:07FC), its waits msg_wait_key (0315:0BD6) and
 * the timed page, and the input test msg_poll (0315:0B7C). docs/re/text.md §3.4, §3.5.
 *
 * The original's waits are busy loops that test a timer slot and poll the input; here each
 * turn that finds nothing ends with a frame (vg_frame), so the input is seen at every VSYNC
 * and the timers advance as the original's do. Times are in hundredths of a second
 * (timer_start: t * 564 / 1000 frames): the icon blinks every 0.8 s, a timed page lasts at
 * least 1.5 s.
 *
 * A translation (docs/translation.md) replaces passages: at the first line of a run of text
 * lines that has one, the run's lines are passed over and the translation is laid out from the
 * row the run would have started on (lrvne's reflow: the speaker's name and the open quote
 * before it, a hanging indent, the close quote after a speech that ends there, row 3 two
 * columns short of the page-wait icon). Its lines then take the place of the original's in the
 * same page loop: a full page is shown and waited for in the current mode, a page break of
 * the translation ends a page as a full one does, and a timed page lasts by the cells drawn.
 * Everything else (the control lines, the empty lines, the waits, the skip flag) is the
 * original's. */
#include <stdio.h>
#include <string.h>
#include "vg.h"

static const uint8_t s_quote_open[] = { 0x81, 0x75, 0 };    /* 「 DS:00E6 */
static const uint8_t s_space[] = { 0x81, 0x40, 0 };         /* full-width space DS:00E9 */
static const uint8_t s_close_mark[] = { '\\', 'e', 0 };     /* DS:00EC */
static const uint8_t s_quote_close[] = { 0x81, 0x76 };      /* 」 DS:00EF */

static size_t ustrlen(const uint8_t *s)
{
    return strlen((const char *)s);
}

int vg_msg_poll(int block)
{
    struct vg_poll p;
    if (!block)
        vg_mouse_lock(1, 0);
    for (;;) {
        memset(&p, 0, sizeof p);
        if (!vg_input_poll(&p))
            return 0;
        if (p.kbd.event == 1) {
            vg_input_release(VG_DEV_KBD);
            return 1;
        }
        if (p.mouse.left == 1) {
            vg_input_release(VG_DEV_MOUSE);
            return 1;
        }
        if (p.joy.b != 0) {
            vg_input_release(VG_DEV_JOY);
            return 1;
        }
        if (block != 1 || vg_frame())
            return 0;
    }
}

/* msg_wait_key: the icon off, 0.8 s, on, 0.8 s, ... until an input; without a free timer the
 * icon stays and the wait blocks */
static void msg_wait_key(void)
{
    int shown = 0, got = 0, h;
    vg_wait_begin(VG_WAIT_KEY);
    while (!got) {
        vg_icon(shown >= 1);
        h = vg_timer_start(80);
        if (!h) {
            vg_icon(1);
            vg_msg_poll(1);
            break;
        }
        for (;;) {
            if (vg_timer_done(h))
                break;
            if (vg_msg_poll(0) == 1) {
                got = 1;
                break;
            }
            if (vg_frame()) {
                got = 1;
                break;
            }
        }
        vg_timer_free(h);
        shown = shown < 1;
    }
    vg_wait_end(VG_WAIT_KEY);
    vg_icon(0);
}

/* the timed page: max(150, nbytes * 100 / 12) hundredths, cut short by an input, which sets
 * the skip flag and ends the message; 1 when it was cut */
static int msg_wait_timed(int nbytes)
{
    int t, h, cut = 0;
    if (nbytes < 1)
        return 0;
    t = (int16_t)(nbytes * 100) / 12;
    if (t < 150)
        t = 150;
    h = vg_timer_start(t);
    if (!h)
        return 0;
    vg_wait_begin(VG_WAIT_TICKS);
    for (;;) {
        if (vg_timer_done(h))
            break;
        if (vg_msg_poll(0) == 1) {
            vg.text.skip = 1;
            cut = 1;
            break;
        }
        if (vg_frame()) {
            cut = 1;
            break;
        }
    }
    vg_wait_end(VG_WAIT_TICKS);
    vg_timer_free(h);
    return cut;
}

/* ---- translated passages ------------------------------------------------------------------ */

static uint8_t *s_tbuf;                 /* a passage with its close quote */
static size_t s_tcap;

static const uint8_t *with_close(const uint8_t *t, const uint8_t *close)
{
    size_t n = ustrlen(t), m = ustrlen(close);
    if (n + m + 1 > s_tcap) {
        if (s_tbuf)
            lrv_free(vg.hal, s_tbuf, s_tcap);
        s_tcap = n + m + 64;
        s_tbuf = lrv_xalloc(vg.hal, s_tcap);
    }
    memcpy(s_tbuf, t, n);
    memcpy(s_tbuf + n, close, m + 1);
    return s_tbuf;
}

/* a line a passage is made of: not empty, not a control line */
static int is_text(const uint8_t *l)
{
    return l[0] && !(l[0] >= 0x10 && l[0] <= 0x14) && l[0] != 0x1A;
}

/* the line closes a speech: its first \e ends it */
static int closes(const uint8_t *l)
{
    const char *m = strstr((const char *)l, (const char *)s_close_mark);
    return m && ustrlen(l) - (size_t)((const uint8_t *)m - l) == 2;
}

/* the speaker's name and the open quote, translated */
static void prefix_of(const uint8_t *name, uint8_t *out, size_t cap)
{
    const uint8_t *nm = vg_lang_name(name), *q = vg_lang_get("quote.open");
    snprintf((char *)out, cap, "%s%s", nm ? (const char *)nm : "", q ? (const char *)q : "");
}

struct passage {
    struct vg_lay lay;
    int next;                           /* the next line to draw */
    uint8_t prefix[128];                /* drawn before line 0 (a new speech's name) */
};
static struct passage s_q;

int vg_msg_show(int n)
{
    uint8_t line[VG_MSG_LINE + 16], name[20], buf[256], scan[VG_MSG_LINE + 16];
    int dlg = 0, mode = 0, row = 0, end = 0, first = 0, nlen = 0, shown, nbytes;
    int lineno = 0, plain = 0, lang = vg_lang_active();
    unsigned pos = 0;

    s_q.lay.nlines = s_q.next = 0;
    vg_win_clear();
    vg_txb_read(n);
    do {
        shown = 0;
        nbytes = 0;
        while (row < 4) {
            const uint8_t *p, *s;
            if (s_q.next < s_q.lay.nlines) {   /* a translated passage's next line */
                const struct vg_lay_line *l = &s_q.lay.line[s_q.next];
                if (l->row != row) {            /* its page break: the page ends here */
                    row = 4;
                    continue;
                }
                if (s_q.next == 0 && s_q.prefix[0])
                    vg_win_utf8(s_q.prefix, (uint32_t)ustrlen(s_q.prefix), row, 0);
                if (l->n)
                    vg_win_utf8(l->s, l->n, row, l->col);
                s_q.next++;
                row++;
                shown++;
                nbytes += l->col + l->cols;
                continue;
            }
            pos += (unsigned)vg_txb_line(pos, line, VG_MSG_LINE);
            lineno++;
            p = line;
            if (line[0] < 0x20) {
                switch (line[0]) {
                case 0x10: case 0x11:           /* dropped */
                    p = line + 1;
                    break;
                case 0x12:                      /* end of page: wait for the player */
                    row = 4;
                    first = 0;
                    mode = 0;
                    continue;
                case 0x13:                      /* the speaker */
                    strncpy((char *)name, (const char *)line + 1, sizeof name - 1);
                    name[sizeof name - 1] = 0;
                    nlen = (int)(ustrlen(name) / 2) + 1;
                    first = 0;
                    dlg = 1;
                    continue;
                case 0x14:                      /* end of page: wait a time; the rest of the
                                                 * line is drawn as row 4 (refused) */
                    row = 4;
                    first = 0;
                    mode = 1;
                    p = line + 1;
                    break;
                case 0x1A:                      /* end of message */
                    row = 4;
                    end = 1;
                    continue;
                default:                        /* text */
                    break;
                }
            }
            if (lang && plain > 0) {
                plain--;                        /* a line of an untranslated passage */
            } else if (lang && p == line && is_text(line)) {
                /* the first line of a passage: its lines, and its translation */
                const uint8_t *t;
                unsigned at = pos;
                int k = 1, cl = dlg == 1 && closes(line);
                while (!cl) {
                    int len = vg_txb_line(at, scan, VG_MSG_LINE);
                    if (!is_text(scan))
                        break;
                    at += (unsigned)len;
                    k++;
                    cl = dlg == 1 && closes(scan);
                }
                t = vg_lang_get("m%03d.%d", n, lineno - 1);
                if (!t || (dlg == 1 && !vg_lang_name(name))) {
                    plain = k - 1;
                } else {
                    uint8_t pfx[128];
                    int indent = 0, col = 0;
                    pos = at;
                    lineno += k - 1;
                    s_q.prefix[0] = 0;
                    if (dlg == 1) {
                        prefix_of(name, pfx, sizeof pfx);
                        indent = col = vg_lang_width(pfx, 0);
                        if (first == 0)
                            memcpy(s_q.prefix, pfx, sizeof pfx);
                        first = 1;
                        if (cl) {
                            const uint8_t *q = vg_lang_get("quote.close");
                            t = with_close(t, q ? q : (const uint8_t *)"");
                            dlg = 0;
                        }
                    }
                    vg_lay(t, VG_WIN_COLS, VG_WIN_ROWS, VG_WIN_COLS - 2, row, col, indent, 0,
                           &s_q.lay);
                    s_q.next = 0;
                    continue;
                }
            } else if (lang && !p[0] && dlg == 1) {
                /* an empty line in a speech: the translated name, or the indent */
                uint8_t pfx[128];
                prefix_of(name, pfx, sizeof pfx);
                if (first == 0) {
                    vg_win_utf8(pfx, (uint32_t)ustrlen(pfx), row, 0);
                    first = 1;
                }
                row++;
                shown++;
                nbytes += vg_lang_width(pfx, 0);
                continue;
            }
            s = p;
            if (dlg == 1) {
                if (first == 0) {
                    strcpy((char *)buf, (const char *)name);
                    strcat((char *)buf, (const char *)s_quote_open);
                    strcat((char *)buf, (const char *)p);
                    first = 1;
                } else if (first == 1) {
                    int k;
                    buf[0] = 0;
                    for (k = 0; k < nlen; k++)
                        strcat((char *)buf, (const char *)s_space);
                    strcat((char *)buf, (const char *)p);
                }
                s = buf;
                /* a line ending in \e: those two bytes become 」 and the speech ends */
                {
                    const char *m = strstr((const char *)buf, (const char *)s_close_mark);
                    if (m && ustrlen(buf) - (size_t)((const uint8_t *)m - buf) == 2) {
                        buf[m - (const char *)buf] = s_quote_close[0];
                        buf[m - (const char *)buf + 1] = s_quote_close[1];
                        dlg = 0;
                    }
                }
            }
            if (s[0])
                vg_win_line(s, row, 0);
            row++;
            shown++;
            nbytes += (int)ustrlen(s);
        }
        if (shown == 0) {
            row = 0;
            continue;
        }
        vg_win_show();
        vg_win_clear();
        row = 0;
        vg_text_event(VG_TEV_PAGE, mode << 16 | (nbytes & 0xFFFF));
        if (mode == 0) {
            msg_wait_key();
        } else if (mode == 1) {
            if (msg_wait_timed(nbytes))
                break;
        }
    } while (end != 1 && !lrv_sys_quitting(&vg.sys));
    vg_win_restore();
    vg_text_event(VG_TEV_RESTORE, 0);
    vg_mouse_lock(0, 0);
    return 1;
}

void vg_msg_free(void)
{
    if (s_tbuf)
        lrv_free(vg.hal, s_tbuf, s_tcap);
    s_tbuf = NULL;
    s_tcap = 0;
}

int vg_op19(int n)
{
    vg.text.skip = 0;
    vg_msg_show(n);
    return vg.text.skip == 1;
}
