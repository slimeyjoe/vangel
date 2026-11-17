# SPDX-License-Identifier: GPL-3.0-or-later
"""Data the pack takes out of the original engine M.EXE (its EXEPACK-unpacked image,
resources/derived/M_unpacked.EXE; tools/gamedata.py makes it on import).

Addresses are SEG:OFF of the load image (image-relative segments), as in docs/re/.

  Image(data)              the unpacked MZ file; .image is the load image
  Image.at(seg, off, n)    n bytes at SEG:OFF
  Image.far(seg, off)      the far pointer stored at SEG:OFF, as an image offset
  text_dictionary(img)     the 90 two-byte Shift-JIS characters of the TXB coding (0B85:0000,
                           docs/re/text.md §2.4), 180 bytes
  palettes(img)            the built-in palettes, 48 bytes R[16] G[16] B[16] each, by pack name:
                           pal.black 0AA8:0000, pal.white 0AA8:0060, pal.default 0AA8:0030
                           (the one gfx_init sets; docs/re/graphics.md §7.1)
  fx31_order(img)          effect 31's 64 cells, 0783:0730 (a permutation of 0..63;
                           graphics.md §5)
  ank_font(img)            the half-width font: {code: 16 rows} for all 256 codes, read through
                           the far-pointer table at 0ABB:07C0 (text.md §3.2); codes without a
                           glyph of their own point at the blank glyph
  builtin(img)             the data of the built-in sequences (platform.md §5), by pack name
                           (below)

The built-ins' entries. A string is a u16 length and its bytes; length FFFFh is the NULL
pointer that ends the original's tables.
  bi.prologue      the prologue's pages, 0ABB:0416: {s16 row, string} records; a NULL string
                   ends a page, its row < 0 the table
  bi.staff         the staff roll's lines, 0ABB:04B2: strings, NULL-ended
  bi.music         the music mode's songs, 0ABB:0728: {file, title} string pairs, NULL-ended
  bi.strings       announce.txt's name (DS:0254), ANNOUNCE's "file missing" (0ABB:0000), its
                   prompts after a page (0ABB:0023) and at the end (0ABB:0046), the music
                   mode's heading (0ABB:06B6) and help line (0ABB:06DD)
  bi.rects         the staff roll's six rectangle copies (operands of op 32h), DGROUP
                   04CC..0537: 9 s16 each (src, sx, sy, w, h, dst, dx, dy, effect)
  pal.prologue     0ABB:0566; pal.end1.from / .to / .roll 0ABB:0596 / 05C6 / 05F6 (ENDING);
                   pal.end2.from / .to / .roll 0ABB:0626 / 0656 / 0686 (ENDING2)
"""
import struct

DICT = (0x0B85, 0x0000)
DICT_SIZE = 180
ANK_TABLE = (0x0ABB, 0x07C0)
ANK_GLYPHS = 159                    # codes with a glyph of their own (text.md §3.2)
BI = 0x0ABB                         # the built-ins' data segment
DGROUP = 0x0BAF


class Image:
    def __init__(self, data):
        if data[:2] != b'MZ':
            raise ValueError('not an MZ executable (the unpacked M.EXE is expected)')
        head = struct.unpack_from('<H', data, 8)[0] * 16
        self.image = data[head:]

    def at(self, seg, off, n):
        p = seg * 16 + off
        if p + n > len(self.image):
            raise ValueError('%04X:%04X+%d is outside the image' % (seg, off, n))
        return self.image[p:p + n]

    def far(self, seg, off):
        o, s = struct.unpack('<HH', self.at(seg, off, 4))
        return s * 16 + o


def text_dictionary(img):
    return img.at(DICT[0], DICT[1], DICT_SIZE)


PALETTES = (('pal.black', 0x0000), ('pal.default', 0x0030), ('pal.white', 0x0060))


def palettes(img):
    out = {}
    for name, off in PALETTES:
        p = img.at(0x0AA8, off, 48)
        if max(p) > 15:
            raise ValueError('%s at 0AA8:%04X is not a palette' % (name, off))
        out[name] = p
    if set(out['pal.black']) != {0} or set(out['pal.white']) != {15}:
        raise ValueError('the black and white palettes are not where M.EXE 1995-03-01 has them')
    return out


def fx31_order(img):
    t = img.at(0x0783, 0x0730, 64)
    if sorted(t) != list(range(64)):
        raise ValueError('0783:0730 is not effect 31\'s order (not a permutation of 0..63)')
    return t


def ank_font(img):
    glyphs = {}
    for code in range(256):
        p = img.far(ANK_TABLE[0], ANK_TABLE[1] + 4 * code)
        glyphs[code] = list(img.image[p:p + 16])
    blank = glyphs[0]
    own = sum(1 for c in range(256) if glyphs[c] != blank)
    if any(glyphs[0]) or own != ANK_GLYPHS:
        raise ValueError('the half-width font table does not look like M.EXE 1995-03-01\'s '
                         '(%d glyphs of their own, %d expected)' % (own, ANK_GLYPHS))
    return glyphs


def _cstr(img, p):
    e = img.image.index(b'\0', p)
    return img.image[p:e]


def _s(b):
    return struct.pack('<H', len(b)) + b


_NULL = b'\xff\xff'

BI_PALETTES = (('pal.prologue', 0x0566), ('pal.end1.from', 0x0596), ('pal.end1.to', 0x05C6),
               ('pal.end1.roll', 0x05F6), ('pal.end2.from', 0x0626), ('pal.end2.to', 0x0656),
               ('pal.end2.roll', 0x0686))


def builtin(img):
    out = {}
    # the prologue: 4 pages
    off, rec, pages = 0x0416, b'', 0
    while True:
        row = struct.unpack('<h', img.at(BI, off, 2))[0]
        if img.at(BI, off + 2, 4) == bytes(4):
            rec += struct.pack('<h', row) + _NULL
            pages += 1
            off += 6
            if row < 0:
                break
            continue
        rec += struct.pack('<h', row) + _s(_cstr(img, img.far(BI, off + 2)))
        off += 6
    if pages != 4 or off != 0x04B2:
        raise ValueError('0ABB:0416 is not the prologue\'s page table')
    out['bi.prologue'] = rec
    # the staff roll: 44 lines
    off, rec, n = 0x04B2, b'', 0
    while img.at(BI, off, 4) != bytes(4):
        rec += _s(_cstr(img, img.far(BI, off)))
        off += 4
        n += 1
    if n != 44:
        raise ValueError('0ABB:04B2 is not the staff roll (%d lines)' % n)
    out['bi.staff'] = rec + _NULL
    # the music mode: 18 songs
    off, rec, n = 0x0728, b'', 0
    while img.at(BI, off, 4) != bytes(4):
        f = _cstr(img, img.far(BI, off))
        if not f.lower().endswith(b'.m'):
            raise ValueError('0ABB:0728 is not the music mode\'s song list')
        rec += _s(f) + _s(_cstr(img, img.far(BI, off + 4)))
        off += 8
        n += 1
    if n != 18:
        raise ValueError('0ABB:0728 is not the music mode\'s song list (%d songs)' % n)
    out['bi.music'] = rec + _NULL
    name = _cstr(img, DGROUP * 16 + 0x0254)
    if name.lower() != b'announce.txt':
        raise ValueError('DS:0254 is not ANNOUNCE\'s file name')
    out['bi.strings'] = b''.join(_s(x) for x in (
        name, _cstr(img, BI * 16 + 0x0000), _cstr(img, BI * 16 + 0x0023),
        _cstr(img, BI * 16 + 0x0046), _cstr(img, BI * 16 + 0x06B6),
        _cstr(img, BI * 16 + 0x06DD)))
    rects = img.at(DGROUP, 0x04CC, 6 * 18)
    for k in range(6):
        r = struct.unpack_from('<9h', rects, 18 * k)
        if r[3:5] != (512, 130) or r[8] not in (10, 31):
            raise ValueError('DS:04CC is not the staff roll\'s rectangle copies')
    out['bi.rects'] = rects
    for pname, poff in BI_PALETTES:
        p = img.at(BI, poff, 48)
        if max(p) > 15:
            raise ValueError('%s at 0ABB:%04X is not a palette' % (pname, poff))
        out[pname] = p
    return out
