#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""gf_verify.py - check re-tools/gf.py against M.EXE's own picture loader under unicorn (mcall).

For every member of GDATA.LIB the original op 31 routine (0315:070D -> 00DD:0216 -> 015A:xxxx)
is called with an operand block like the scenario's, and the target planes are compared with
gf.decode() + gf.to_planes():
  case A  buffer 12 (memory planes), flag 0, position from the file (x = y = -1), on a buffer
          filled with random bytes                                 (015A:0B0A)
  case B  buffer 12, flag 1 (colour 8 transparent), random background  (015A:1076)
  case C  buffer 10 (VRAM page 0), flag 0, random VRAM              (015A:000A)
  case D  buffer 11 (VRAM page 1), flag 1, random VRAM, explicit x/y  (015A:0554)
Needs $EMU_PYTHON (unicorn).  Usage: gf_verify.py [--quick] [NAME ...]
"""
import os
import random
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcall import M  # noqa: E402
import gf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class GM(M):
    """mcall.M with helpers for the graphics buffers."""

    def mem_planes(self):
        g = self.seg(0x0BA1)
        return [self.word(g, 0x46 + 2 * q) for q in range(4)]

    def get_buf(self, buf):
        if buf == 12:
            return [bytearray(self.mem(s, 0, 32000)) for s in self.mem_planes()]
        return [bytearray(p[:32000]) for p in self.pages[buf - 10]]

    def set_buf(self, buf, planes):
        if buf == 12:
            for s, p in zip(self.mem_planes(), planes):
                self.poke(s, 0, p)
        else:
            for q in range(4):
                self.pages[buf - 10][q][:32000] = planes[q]


def main(argv):
    quick = '--quick' in argv
    names = [a for a in argv[1:] if not a.startswith('--')]
    lib = open(gf.LIB, 'rb').read()
    ar = gf.Archive(lib)
    m = GM(trace_ports=False)
    ax, _ = m.call(0x0315, 0x000E)          # gfx_init: open GDATA.LIB, allocate buffers
    if ax != 1:
        sys.exit('gfx_init failed (%r), ints %r' % (ax, m.ints[:8]))
    op = m.alloc(64)
    rnd = random.Random(1995)
    cases = [('A', 12, 0, None), ('B', 12, 1, None), ('C', 10, 0, None), ('D', 11, 1, 'xy')]
    if quick:
        cases = cases[:2]
    bad = 0
    nok = 0
    t0 = time.time()
    for name, off, size in ar.entries:
        base = name.rsplit('.', 1)[0]
        if names and base not in names:
            continue
        pic = gf.decode(lib, off)
        res = []
        for tag, buf, flag, pos in cases:
            if pos:
                # an explicit position, kept on screen and a multiple of 8
                x = rnd.randrange(0, 640 - pic.w + 1) & ~7
                y = rnd.randrange(0, 400 - pic.h + 1)
            else:
                x = y = -1
            bg = [bytearray(rnd.getrandbits(8) for _ in range(32000)) for _ in range(4)]
            m.set_buf(buf, bg)
            blk = bytearray(0x16)
            blk[0:len(base)] = base.encode('ascii')
            struct.pack_into('<hhhh', blk, 0x0E, flag, buf, x, y)
            m.poke(op, 0, blk)
            r, _ = m.call(0x0315, 0x070D, [0, op])
            got = m.get_buf(buf)
            want = gf.to_planes(pic, [bytearray(p) for p in bg],
                                None if x < 0 else x, None if y < 0 else y, transparent=flag == 1)
            ok = r == 1 and got == want
            if not ok:
                bad += 1
                diff = sum(1 for q in range(4) for i in range(32000) if got[q][i] != want[q][i])
                res.append('%s:FAIL(ret %d, %d bytes differ)' % (tag, r, diff))
            else:
                nok += 1
                res.append('%s:ok' % tag)
        print('%-12s %3dx%-3d at (%3d,%3d) overrun %d  %s' % (name, pic.w, pic.h, pic.x, pic.y,
                                                           pic.overrun, ' '.join(res)), flush=True)
    print('%d cases bit-exact, %d failed (%.0f s)' % (nok, bad, time.time() - t0))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
