#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_buf.py - the engine's buffer statements against M.EXE's own.

usage: check_buf.py TEST_BUF PAK                 (with $EMU_PYTHON: unicorn)

A sequence of op 31h (pic_load 0315:070D), op 32h (rect_copy 0315:07CB), op 33h (gfx_clear
0315:01BE), op 18h (win_restore 02BE:0097) and screen_clear (0315:0132) over random buffers:
a room composed as the scenario does it, the window's background taken after each op 31h
and op 32h and put back by op 18h, a picture that is not in the library, buffer numbers
other than 10..12 (op 31h draws nothing; op 32h takes VRAM through whatever page port A6h
selects, op 33h clears page 0), effect 34 into "buffer 12" (VRAM), and the clears. After
each group the three buffers and the window's background are compared with the engine's
(tests/test_buf.c). The original runs under re-tools/mcall.py; its results are kept between
runs (tests/refcache.py).
"""
import hashlib
import os
import random
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import refcache  # noqa: E402

PLANE = 32000
WIN = 0x1540
SEQ = [
    ('load', 1),
    ('31', 11, 0, 0, 0, 'va_main'), ('31', 11, 160, 48, 0, 'va_bg01'),
    ('32', 11, 0, 0, 640, 400, 12, 0, 0, 10), ('31', 12, 320, 0, 1, 'va_ch01'),
    ('31', 12, 32, 300, 1, 'va_mw01'), ('32', 12, 0, 0, 640, 400, 10, 0, 0, 10),
    ('dump',),
    ('load', 2), ('18',), ('dump',),
    ('31', 10, -1, -1, 1, 'va_va'), ('dump',),
    ('31', 13, 0, 0, 0, 'va_main'), ('31', 10, 0, 0, 0, 'nosuch'), ('dump',),
    ('33', 11), ('33', 12), ('33', 99), ('dump',),
    ('load', 3),
    ('32', 11, 0, 0, 64, 8, 13, 0, 0, 10), ('32', 13, 0, 0, 64, 8, 12, 0, 0, 10),
    ('32', 12, 0, 0, 64, 8, 12, 8, 0, 34), ('32', 12, 16, 300, 200, 40, 10, 48, 307, 20),
    ('dump',),
    ('clear',), ('dump',),
]


def contents(seed):
    rnd = random.Random('check_buf %d' % seed)
    return bytes(rnd.getrandbits(8) for _ in range(3 * 4 * PLANE))


def original():
    from gf_verify import GM
    m = GM(trace_ports=False)
    if m.call(0x0315, 0x000E)[0] != 1:
        sys.exit('check_buf: gfx_init failed under emulation')
    blk = m.alloc(64)
    g = m.seg(0x0BA1)
    out = []
    for s in SEQ:
        if s[0] == 'load':
            b = contents(s[1])
            for n in range(3):
                planes = [b[(4 * n + q) * PLANE:(4 * n + q + 1) * PLANE] for q in range(4)]
                m.set_buf((10, 11, 12)[n], planes)
            out.append('load 1')
        elif s[0] == '31':
            d = bytearray(0x16)
            d[0:len(s[5])] = s[5].encode('ascii')
            struct.pack_into('<hhhh', d, 0x0E, s[4], s[1], s[2], s[3])
            m.poke(blk, 0, bytes(d))
            out.append('31 %d' % m.call(0x0315, 0x070D, [0, blk])[0])
        elif s[0] == '32':
            m.poke(blk, 0, struct.pack('<9h', *s[1:]))
            out.append('32 %d' % m.call(0x0315, 0x07CB, [0, blk])[0])
        elif s[0] == '33':
            m.call(0x0315, 0x01BE, [s[1]])
            out.append('33')
        elif s[0] == '18':
            m.call(0x02BE, 0x0097)
            out.append('18')
        elif s[0] == 'clear':
            m.call(0x0315, 0x0132)
            out.append('clear')
        elif s[0] == 'dump':
            h = hashlib.sha256()
            for n in (10, 11, 12):
                for p in m.get_buf(n):
                    h.update(bytes(p))
            for q in range(4):
                sg, off = m.word(g, 0x74 + 4 * q + 2), m.word(g, 0x74 + 4 * q)
                h.update(m.mem(sg, off, WIN))
            out.append('dump ' + h.hexdigest())
    return out


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    test_buf, pak = argv[1], argv[2]
    want, hit = refcache.get('buf', ['check_buf.py'], None, {'seq': [list(s) for s in SEQ]},
                             original)
    with tempfile.TemporaryDirectory() as tmp:
        lines, dumps = [], []
        for s in SEQ:
            if s[0] == 'load':
                p = os.path.join(tmp, 'load%d' % s[1])
                with open(p, 'wb') as f:
                    f.write(contents(s[1]))
                lines.append('load %s\n' % p)
            elif s[0] == 'dump':
                p = os.path.join(tmp, 'dump%d' % len(dumps))
                dumps.append(p)
                lines.append('dump %s\n' % p)
            else:
                lines.append(' '.join(str(x) for x in s) + '\n')
        res = subprocess.run([test_buf, pak], input=''.join(lines), capture_output=True,
                             text=True, check=False)
        if res.returncode != 0:
            print(res.stdout + res.stderr)
            sys.exit('check_buf: test_buf failed (exit %d)' % res.returncode)
        got, k = [], 0
        for ln in res.stdout.split('\n'):
            if not ln:
                continue
            if ln == 'dump 1':
                ln = 'dump ' + hashlib.sha256(open(dumps[k], 'rb').read()).hexdigest()
                k += 1
            got.append(ln)
    bad = 0
    for i, s in enumerate(SEQ):
        a = got[i] if i < len(got) else '(none)'
        if a != want[i]:
            bad += 1
            print('statement %d %r: engine %s, original %s' % (i, s, a, want[i]))
    print('check_buf: %d statements, %d dumps: %s (reference %s)' % (
        len(SEQ), sum(1 for s in SEQ if s[0] == 'dump'),
        'identical to the original' if not bad else '%d differ' % bad,
        'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
