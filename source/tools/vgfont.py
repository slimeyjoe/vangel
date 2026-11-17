# SPDX-License-Identifier: GPL-3.0-or-later
"""The fonts of translated text (docs/translation.md), built at pack time.

latin8  the half-width glyphs, keyed by code point, 8x16, not emboldened (the engine emboldens
        them as it does the game's own): in this order, a later one replacing an earlier
          - ISO 8859-1 from lrvne's fonts/x11/8x16.bdf, the fallback;
          - ASCII 21h-7Eh from the game's own font (M.EXE, the pack's ank8), except the codes
            that are not Latin there (# $ % & ' ! " \\: bar pieces, the page-wait arrow,
            the halves of a two-cell symbol, the yen sign) and the space;
          - our own glyphs and the Polish letters, fonts/vangel-latin.txt: a glyph of its own,
            or a mark on one of the game's letters
        A character is one column when latin8 has it, otherwise two.
wide16  a language's full-width glyphs, keyed by code point, 16x16: every character of its
        translation that latin8 lacks, from the kanji ROM's stand-in (the pack's font16, keyed
        by JIS X 0208) through Shift-JIS; the full-width space is blank. A character neither
        has is an error.
"""
import os
import re

import lrvnepath  # noqa: F401  (sys.path: lrvne's tools)
from lrvne import xfont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
OWN = os.path.join(ROOT, 'fonts', 'vangel-latin.txt')
FALLBACK = os.path.join(ROOT, 'source', 'lrvne', 'fonts', 'x11', '8x16.bdf')

NOT_LATIN = set(b'!#$%&\'"\\')      # the game's font draws something else for these


class FontError(Exception):
    pass


def own_glyphs(path=OWN):
    """({code: rows} of the glyphs of their own, {code: (base char, mark rows)})"""
    data = open(path, 'rb').read()
    _w, rows = xfont.parse_art(data)
    marks = {}
    for ln in data.decode('utf-8').splitlines():
        m = re.match(r'U\+([0-9A-Fa-f]+)\s+\S+\s+mark on (\S)\s*$', ln)
        if m:
            marks[int(m.group(1), 16)] = m.group(2)
    own = {c: r for c, r in rows.items() if c not in marks}
    for c, rr in rows.items():
        if len(rr) != 16:
            raise FontError('%s: U+%04X has %d rows' % (path, c, len(rr)))
    return own, {c: (b, rows[c]) for c, b in marks.items()}


def latin8(ank, own_path=OWN, fallback=FALLBACK):
    """the latin8 glyph table {code point: 16 rows}; ank = the game's font {code: rows}"""
    t = xfont.FontTable(8, 16)
    t.add_bdf(xfont.read_font_file(fallback))
    glyphs = dict(t.glyphs)
    for c in range(0x21, 0x7F):
        if c not in NOT_LATIN and c in ank:
            glyphs[c] = list(ank[c])
    glyphs[0x20] = [0] * 16
    own, marks = own_glyphs(own_path)
    glyphs.update(own)
    for c, (base, rows) in marks.items():
        b = ank.get(ord(base))
        if b is None:
            raise FontError('U+%04X: the game\'s font has no %s' % (c, base))
        glyphs[c] = [x | y for x, y in zip(b, rows)]
    return glyphs


def build(glyphs, cell_w):
    t = xfont.FontTable(cell_w, 16)
    for c, rows in sorted(glyphs.items()):
        t.add_glyph(c, rows)
    return t.build()


def sjis_to_jis(lead, trail):
    """the JIS X 0208 code of a Shift-JIS pair"""
    row = (lead - (0x70 if lead < 0xA0 else 0xB0)) * 2
    if trail < 0x9F:
        row -= 1
        col = trail - (0x1F if trail < 0x7F else 0x20)
    else:
        col = trail - 0x7E
    return row << 8 | col


def wide_code(ch):
    """the JIS X 0208 code of a full-width character, None when Shift-JIS has none"""
    try:
        b = ch.encode('cp932')
    except UnicodeEncodeError:
        return None
    if len(b) != 2:
        return None
    return sjis_to_jis(b[0], b[1])


def wide16(chars, font16, narrow):
    """{code point: rows} of the characters of `chars` that are not in `narrow`, from font16
    ({JIS code: rows}); raises FontError naming those that neither has"""
    out, missing = {}, []
    for ch in sorted(set(chars)):
        cp = ord(ch)
        if cp < 0x20 or cp in narrow:
            continue
        if cp == 0x3000:                # the full-width space (the names' padding): blank
            out[cp] = [0] * 16
            continue
        j = wide_code(ch)
        if j is None or j not in font16:
            missing.append('U+%04X %s' % (cp, ch))
            continue
        out[cp] = font16[j]
    if missing:
        raise FontError('no glyph for ' + ', '.join(missing))
    return out


def read_table(data):
    """{code: rows} of an XFNT table"""
    return xfont.read_xfnt(data)[3]
