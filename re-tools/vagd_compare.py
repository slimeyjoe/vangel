#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""vagd_compare.py - compare the "Graphic Disk" BMPs (VAGD.LZH) with the GDATA.LIB pictures.

  vagd_compare.py [BMPDIR] [--lib GDATA.LIB] [--scb CMD00.SCB]

BMPDIR defaults to resources/derived/ibm_bmp (extract VAGD.LZH there with 7z).  For every BMP:
the GDATA.LIB picture whose pixels agree best under a per-index mapping, the mapping, the number
of differing pixels inside the message-window rectangle x 32..607, y 303..390 and outside it
(with the bounding box of the outside differences), and the scenario palettes that equal the BMP
palette after quantising to 4 bits (BMP values are v*11h or v*10h).  12.BMP is compared with
va_12 + the va_12e overlay.  Needs numpy (research tool, not for a port build).
"""
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source', 'tools'))  # gf, scb, txb
import gf   # noqa: E402
import scb  # noqa: E402

WIN = (32, 303, 608, 391)       # x0, y0, x1, y1 (exclusive) of the message-window rectangle


def read_bmp(path):
    d = open(path, 'rb').read()
    off = struct.unpack_from('<I', d, 10)[0]
    hs, w, h, _, bpp, comp, _, _, _, nc, _ = struct.unpack_from('<IiiHHIIiiII', d, 14)
    assert bpp == 4 and comp == 0, path
    pal = [tuple(d[14 + hs + 4 * i:14 + hs + 4 * i + 3][::-1]) for i in range(nc or 16)]
    stride = ((w * bpp + 31) // 32) * 4
    rows = []
    for y in range(abs(h)):
        a = np.frombuffer(d[off + y * stride:off + y * stride + w // 2], np.uint8)
        rows.append(np.stack([a >> 4, a & 15], 1).reshape(-1))
    img = np.array(rows)
    return (img[::-1] if h > 0 else img), pal, struct.unpack_from('<I', d, 2)[0], len(d)


def screen(pic):
    full = np.full((400, 640), 255, np.uint8)
    a = np.frombuffer(bytes(pic.pixels), np.uint8)[:pic.w * pic.h].reshape(pic.h, pic.w)
    full[pic.y:pic.y + pic.h, pic.x:pic.x + pic.w] = a
    return full


def agreement(b, g):
    m = g != 255
    if not m.any():
        return 0.0, None
    ct = np.zeros((16, 16), int)
    np.add.at(ct, (g[m], b[m]), 1)
    return ct.max(1).sum() / m.sum(), ct.argmax(1)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    bdir = args[0] if args else os.path.join(ROOT, 'resources/derived/ibm_bmp')
    lib_p = argv[argv.index('--lib') + 1] if '--lib' in argv else gf.LIB
    scb_p = argv[argv.index('--scb') + 1] if '--scb' in argv else os.path.join(ROOT, 'resources/original/pc98/CMD00.SCB')
    if lib_p in args:
        args.remove(lib_p)
    lib = open(lib_p, 'rb').read()
    arc = gf.Archive(lib)
    pics = {e[0]: screen(gf.decode(lib, e[1])) for e in arc.entries}
    pals = scb.Scenario(open(scb_p, 'rb').read()).pal
    win = np.zeros((400, 640), bool)
    win[WIN[1]:WIN[3], WIN[0]:WIN[2]] = True
    for f in sorted(os.listdir(bdir), key=lambda s: (len(s), s)):
        if not f.upper().endswith('.BMP'):
            continue
        img, pal, bfsize, size = read_bmp(os.path.join(bdir, f))
        full = [(n, g) for n, g in pics.items() if (g != 255).all()]
        s, name, mp = max((agreement(img, g)[0], n, agreement(img, g)[1]) for n, g in full)
        g = pics[name].copy()
        if name == 'va_12.gf':
            e = pics['va_12e.gf']
            g[e != 255] = e[e != 255]
        d = img != g
        out = d & ~win
        bbox = ''
        if out.any():
            ys, xs = np.nonzero(out)
            bbox = ' bbox (%d,%d)-(%d,%d)' % (xs.min(), ys.min(), xs.max(), ys.max())
        x11 = all(c % 17 == 0 for rgb in pal for c in rgb)
        q = [tuple(c // 17 if x11 else c >> 4 for c in rgb) for rgb in pal]
        same = [i + 1 for i, p in enumerate(pals) if [tuple(t) for t in p] == q]
        print('%-7s %-9s agree %.4f map %s  diff in window %5d outside %5d%s  palette x%s = scenario %s%s' % (
            f, name, s, ''.join('%x' % v for v in mp), (d & win).sum(), out.sum(), bbox,
            '11' if x11 else '10', same or '-', '' if bfsize == size else '  (bfSize %d, file %d)' % (bfsize, size)))


if __name__ == '__main__':
    main(sys.argv)
