#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""ibm_bmp_compare.py - compare the IBM "Graphic Disk" BMPs (VAGD.LZH) with GDATA.LIB pictures.

  ibm_bmp_compare.py [BMPDIR]    (default resources/derived/ibm_bmp, from `7z x VAGD.LZH`)

For every 4-bit BMP the best-matching 640x400 .gf picture is found by the share of pixels that
agree under the best colour-index mapping (BMP indices may be ordered differently); prints the
match rate, the bounding box and pixel count of the differing area, and the BMP palette next
to the scenario palette that the game uses with that picture (gf.gf_palettes()).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source', 'tools'))  # gf, scb, txb
import gf  # noqa: E402
import scb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN = (37, 303, 602, 390)      # the message window baked into the PC-98 event pictures


def read_bmp(path):
    d = open(path, 'rb').read()
    if d[:2] != b'BM':
        raise ValueError(path)
    off = struct.unpack_from('<I', d, 10)[0]
    hs, w, h, planes, bpp = struct.unpack_from('<IiiHH', d, 14)
    ncol = struct.unpack_from('<I', d, 46)[0] or (1 << bpp)
    pal = [tuple(d[14 + hs + 4 * i + k] for k in (2, 1, 0)) for i in range(ncol)]
    stride = ((w * bpp + 31) // 32) * 4
    pix = bytearray(w * abs(h))
    for r in range(abs(h)):
        src = off + stride * ((abs(h) - 1 - r) if h > 0 else r)
        for x in range(w):
            b = d[src + x // 2]
            pix[r * w + x] = (b >> 4) if x % 2 == 0 else (b & 15)
    return w, abs(h), pal, bytes(pix)


def mapping(a, b):
    """Best index map a->b (greedy on the co-occurrence matrix) and agreement count."""
    co = [[0] * 16 for _ in range(16)]
    for x, y in zip(a, b):
        co[x][y] += 1
    pairs = sorted(((co[i][j], i, j) for i in range(16) for j in range(16)), reverse=True)
    mp, used = {}, set()
    for c, i, j in pairs:
        if i not in mp and j not in used:
            mp[i] = j
            used.add(j)
    return mp, sum(co[i][mp[i]] for i in mp)


def main(argv):
    bdir = argv[1] if len(argv) > 1 else os.path.join(ROOT, 'resources/derived/ibm_bmp')
    lib = open(gf.LIB, 'rb').read()
    ar = gf.Archive(lib)
    pics = {}
    for name, off, size in ar.entries:
        p = gf.decode(lib, off)
        if p.w == 640 and p.h == 400:
            pics[name.rsplit('.', 1)[0]] = p.pixels
    scbp = os.path.join(ROOT, 'resources/original/pc98/CMD00.SCB')
    spal = scb.Scenario(open(scbp, 'rb').read()).pal
    used = gf.gf_palettes(scbp)
    files = sorted((f for f in os.listdir(bdir) if f.upper().endswith('.BMP')),
                   key=lambda f: (len(f), f))
    for f in files:
        w, h, pal, pix = read_bmp(os.path.join(bdir, f))
        if (w, h) != (640, 400):
            print('%-8s %dx%d: skipped' % (f, w, h))
            continue
        # quick pre-selection on a subsample, then the full comparison
        sub = slice(0, None, 37)
        cand = sorted(pics, key=lambda n: -mapping(pics[n][sub], pix[sub])[1])[:3]
        best = max(cand, key=lambda n: mapping(pics[n], pix)[1])
        mp, agree = mapping(pics[best], pix)
        g = pics[best]
        x0 = y0 = 10 ** 9
        x1 = y1 = -1
        nd = no = 0
        ox0 = oy0 = 10 ** 9
        ox1 = oy1 = -1
        for i in range(640 * 400):
            if mp.get(g[i]) != pix[i]:
                nd += 1
                x, y = i % 640, i // 640
                x0, y0, x1, y1 = min(x0, x), min(y0, y), max(x1, x), max(y1, y)
                if not (WIN[0] <= x <= WIN[2] and WIN[1] <= y <= WIN[3]):
                    no += 1
                    ox0, oy0, ox1, oy1 = min(ox0, x), min(oy0, y), max(ox1, x), max(oy1, y)
        ident = all(mp.get(i, i) == i for i in mp)
        box = '(%d,%d)-(%d,%d)' % (x0, y0, x1, y1) if nd else '-'
        print('%-8s ~ %-8s %6.2f%% equal, %6d px differ in %s, index map %s' % (
            f, best, 100.0 * agree / len(pix), nd, box, 'identity' if ident else
            ' '.join('%x>%x' % (i, mp[i]) for i in sorted(mp) if mp[i] != i)))
        if nd:
            print('         outside the message window %s: %d px differ%s' % (
                WIN, no, ' in (%d,%d)-(%d,%d)' % (ox0, oy0, ox1, oy1) if no else ''))
        pn = used.get(best, [])
        bp = ' '.join('%x%x%x' % tuple(c // 16 for c in pal[i]) for i in range(16))
        print('         BMP palette (>>4): %s' % bp)
        for n in pn:
            print('         scenario P%-2d    : %s' % (n, ' '.join('%x%x%x' % c for c in spal[n - 1])))


if __name__ == '__main__':
    main(sys.argv)
