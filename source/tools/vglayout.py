# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the engine draws a translation (docs/translation.md): the reference tests/check_lang.py
holds the engine to, and what tools/tl.py reports. Every layout is lrvne's reflow
(lrvne.reflow, the same as the engine's lrvne/src/text/reflow.c) with the language's widths.

msg_pages() models statement 19h's page loop (engine/text/msg.c) with a language's table; with
an empty table it is txb.layout(), the original's (verified against it under emulation).
"""
import lrvnepath  # noqa: F401  (sys.path: lrvne's tools)
from lrvne import reflow

import txb as txbmod
import vgtext
from vgtext import (WIN_W, WIN_H, WIN_LAST, MENU_W, PROLOGUE_W, PROLOGUE_H, STAFF_W, STAFF_H,
                    ANNOUNCE_W, ANNOUNCE_H)


def cols_of(narrow):
    return reflow.columns(narrow)


def width(b, cols):
    return sum(c[3] for c in reflow.chars(b, cols))


def lay(b, cols, w, h, last=None, first_line=0, first_col=0, indent=0, keep=False):
    return reflow.layout_from(b, cols, w, h, last, first_line, first_col, indent, keep)


# ---- the message window ----------------------------------------------------------------------

def msg_pages(lines, n, tab, cols):
    """the pages of message n (its lines: vgtext.message_lines) with the pack table `tab`
    ({key: UTF-8 bytes}; {} = the original): [(rows, mode, cells)], rows = [(row, col, bytes,
    utf8)] as the line drawers get them (rows past 3 are refused and not listed), mode 0 key /
    1 timed, cells what the timed wait counts"""
    lang = bool(tab)
    pages = []
    dlg = mode = row = end = first = nlen = 0
    name = b''
    i = plain = 0
    queue, qnext, qprefix, qtext = [], 0, b'', b''

    def prefix():
        return tab.get(vgtext.name_key_pack(name), b'') + tab.get('quote.open', b'')

    while True:
        rows, shown, nbytes = [], 0, 0
        while row < 4:
            if qnext < len(queue):
                ln = queue[qnext]
                if ln.row != row:
                    row = 4
                    continue
                if qnext == 0 and qprefix:
                    rows.append((row, 0, qprefix, True))
                if ln.end > ln.start:
                    rows.append((row, ln.col, qtext[ln.start:ln.end], True))
                qnext += 1
                row += 1
                shown += 1
                nbytes += ln.col + ln.cols
                continue
            line = lines[i]
            i += 1
            p, plain_line = line, True
            c = line[0] if line else 0
            if c < 0x20:
                if c in (0x10, 0x11):
                    p, plain_line = line[1:], False
                elif c == 0x12:
                    row, first, mode = 4, 0, 0
                    continue
                elif c == 0x13:
                    name = line[1:20]
                    nlen = len(name) // 2 + 1
                    first, dlg = 0, 1
                    continue
                elif c == 0x14:
                    row, first, mode = 4, 0, 1
                    p, plain_line = line[1:], False
                elif c == 0x1A:
                    row, end = 4, 1
                    continue
            if lang and plain > 0:
                plain -= 1
            elif lang and plain_line and vgtext.is_text(line):
                k, cl = 1, dlg == 1 and vgtext.closes(line)
                while not cl and vgtext.is_text(lines[i + k - 1]):
                    cl = dlg == 1 and vgtext.closes(lines[i + k - 1])
                    k += 1
                t = tab.get('m%03d.%d' % (n, i - 1))
                if t is None or (dlg == 1 and vgtext.name_key_pack(name) not in tab):
                    plain = k - 1
                else:
                    i += k - 1
                    qprefix, col, indent = b'', 0, 0
                    if dlg == 1:
                        pfx = prefix()
                        col = indent = width(pfx, cols)
                        if first == 0:
                            qprefix = pfx
                        first = 1
                        if cl:
                            t = t + tab.get('quote.close', b'')
                            dlg = 0
                    qtext = t
                    queue = lay(t, cols, WIN_W, WIN_H, WIN_LAST, row, col, indent)
                    qnext = 0
                    continue
            elif lang and not p and dlg == 1:
                pfx = prefix()
                if first == 0:
                    if row <= 3:
                        rows.append((row, 0, pfx, True))
                    first = 1
                row += 1
                shown += 1
                nbytes += width(pfx, cols)
                continue
            s = p
            if dlg == 1:
                if first == 0:
                    s = name + vgtext.QUOTE_OPEN + p
                    first = 1
                else:
                    s = b'\x81\x40' * nlen + p
                k = s.find(b'\\e')
                if k >= 0 and len(s) - k == 2:
                    s = s[:k] + vgtext.QUOTE_CLOSE
                    dlg = 0
            if s and row <= 3:
                rows.append((row, 0, s, False))
            row += 1
            shown += 1
            nbytes += len(s)
        if shown == 0:
            row = 0
        else:
            pages.append((rows, mode, nbytes))
            row = 0
        if end:
            break
    return pages


def original_pages(msg):
    """txb.layout()'s pages of a txb.Message in msg_pages' form"""
    return [([(r, 0, s, False) for r, s in rows], 1 if wait == 'timed' else 0, nb)
            for rows, wait, nb in txbmod.layout(msg)]


# ---- the rest --------------------------------------------------------------------------------

def menu_col(orig, cols):
    """engine/text/win.c vg_menu_col: 0, or centred on a centred original's text"""
    lead = w = c = 0
    inside = False
    p = 0
    while p < len(orig):
        k = 2 if txbmod.is_lead(orig[p]) and p + 1 < len(orig) else 1
        sp = orig[p:p + k] in (b'\x81\x40', b' ')
        if not inside and sp:
            lead += k
        else:
            inside = True
            c += k
            if not sp:
                w = c
        p += k
    if not lead:
        return 0
    col = int((2 * lead + w - cols) / 2)
    col = min(col, WIN_W - cols)
    return max(col, 0)


def menu_item(orig, t, cols):
    """(column, the bytes drawn, their columns) of a translated menu choice"""
    b, c = reflow.fit(t, cols, MENU_W)
    return menu_col(orig, c), b, c


def bi_centre(col, orig, t, cols):
    """engine/bi/bi.c vg_bi_text's column of a centred translation"""
    c = width(t, cols)
    x = int((2 * col + len(orig) - c) / 2)
    return max(min(x, 80 - c), 0)


def prologue(t, cols):
    """[(page, row, x, bytes)]: centred lines on 8 rows of 72 columns"""
    return [(ln.page, ln.row, 40 - ln.cols // 2, t[ln.start:ln.end])
            for ln in lay(t, cols, PROLOGUE_W, PROLOGUE_H)]


def staff(t, cols):
    return [(ln.page, ln.row, ln.col, t[ln.start:ln.end])
            for ln in lay(t, cols, STAFF_W, STAFF_H, keep=True)]


def announce(t, cols):
    return [(ln.page, ln.row, ln.col, t[ln.start:ln.end])
            for ln in lay(t, cols, ANNOUNCE_W, ANNOUNCE_H, keep=True)]


def pages_of(lines):
    return (lines[-1][0] + 1) if lines else 1
