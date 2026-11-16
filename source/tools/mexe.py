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
  ank_font(img)            the half-width font: {code: 16 rows} for all 256 codes, read through
                           the far-pointer table at 0ABB:07C0 (text.md §3.2); codes without a
                           glyph of their own point at the blank glyph
"""
import struct

DICT = (0x0B85, 0x0000)
DICT_SIZE = 180
ANK_TABLE = (0x0ABB, 0x07C0)
ANK_GLYPHS = 159                    # codes with a glyph of their own (text.md §3.2)


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
