#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""scb_verify.py - compare source/tools/scb.py with the original scenario loader of M.EXE.

Needs unicorn ($EMU_PYTHON).  Runs scb_load (063C:00E8) under re-tools/mcall.py
on CMD00.SCB and compares, entry by entry, the tables it builds in memory with scb.py's parse:
header (entry statement, key, counts), variables (type, value), menus (choice count, strings),
expression nodes (all 12 bytes), palettes (the three 16-byte component arrays) and statements
(opcode word and, for the opcodes whose record layout is fixed, every operand field).

  scb_verify.py [SCB ...]      default: the PC-98 and X68000 CMD00.SCB
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source', 'tools'))  # gf, scb, txb
from mcall import M, ROOT  # noqa: E402
from scb import Scenario  # noqa: E402

G = 0x0BA1


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def verify(path):
    data = open(path, 'rb').read()
    sc = Scenario(data)
    m = M(files=os.path.dirname(path))
    buf = m.alloc(64)
    name = os.path.basename(path).encode() + b'\0'
    m.poke(buf, 0, name + b'rb\0')
    ax, dx = m.call(0x886, 0x39A, [0, buf, len(name), buf])
    g = m.seg(G)
    m.poke(g, 0x64, struct.pack('<HH', ax, dx))
    ok, _ = m.call(0x63C, 0xE8)
    bad = []

    def check(what, a, b):
        if a != b:
            bad.append('%s: original %r, scb.py %r' % (what, a, b))
    check('load result', ok, 1)
    check('entry', m.word(g, 2), sc.h12)
    check('key', m.word(g, 0x10), sc.key)
    for off, key in ((0x0E, 'n_stmt'), (0x44, 'n_t44'), (0x0C, 'n_t0c'), (0x52, 'n_t52'), (0x0A, 'n_pal'),
                     (0x42, 'n_t42'), (0xD4, 'n_d4'), (0x04, 'n_04')):
        check('count %s' % key, m.word(g, off), sc.counts[key])

    def table(off, i):
        s, o = m.far(g, off)
        return m.far(s, o + 4 * i)
    for i, (t, v) in enumerate(sc.t42, 1):
        s, o = table(0x68, i)
        check('var %d' % i, (m.word(s, o) & 0xFF, s16(m.word(s, o + 2))), (t & 0xFF, v))
    for i, (ln, choices) in enumerate(sc.t44, 1):
        s, o = table(0x12, i)
        n = m.word(s, o)
        got = [m.cstr(*m.far(s, o + 2 + 4 * k)) for k in range(n)]
        check('menu %d' % i, got, choices)
    for i, e in enumerate(sc.t0c, 1):
        s, o = table(0x88, i)
        r = struct.unpack('<6H', m.mem(s, o, 12))
        if e[0] == 'A':
            check('expr %d' % i, (r[0], r[1], s16(r[2]), s16(r[3])), (0xA, e[1], e[2], e[3]))
        else:
            check('expr %d' % i, (r[0], r[4], s16(r[5])), (0xB, e[1] & 0xFFFF if e[1] >= 0 else e[1] & 0xFFFF, e[2]))
    for i, p in enumerate(sc.pal, 1):
        s, o = table(0x84, i)
        b = m.mem(s, o, 48)
        check('palette %d' % i, [(b[k], b[16 + k], b[32 + k]) for k in range(16)], p)
    nst = 0
    for i, (at, op, a) in enumerate(sc.stmts, 1):
        s, o = table(0xD0, i)
        check('stmt %d opcode' % i, m.word(s, o), op)
        w = lambda k: s16(m.word(s, o + 2 + 2 * k))  # noqa: E731
        if op in (0x19, 0x1C, 0x21, 0x22, 0x23, 0x24, 0x2F, 0x33, 0x34):
            check('stmt %d' % i, w(0), a[0])
        elif op == 0x1E:
            check('stmt %d' % i, (w(1), w(0)), (a[0], a[1]))
        elif op == 0x1F:
            check('stmt %d' % i, (w(2), w(0), w(1)), tuple(a))
        elif op == 0x15:
            check('stmt %d' % i, (w(0), w(1)), tuple(a))
        elif op == 0x32:
            check('stmt %d' % i, tuple(w(k) for k in range(9)), tuple(a))
        elif op == 0x20:
            n = w(1)
            got = (w(0), w(0x22), [(w(2 + k), w(0x12 + k)) for k in range(n)])
            check('stmt %d' % i, got, (a[1], a[2], a[3]))
        else:
            continue
        nst += 1
    print('%s: %d vars, %d menus, %d expressions, %d palettes, %d statements (%d with operands '
          'compared): %d mismatches' % (path, len(sc.t42), len(sc.t44), len(sc.t0c), len(sc.pal),
                                        len(sc.stmts), nst, len(bad)))
    for b in bad[:20]:
        print('  ' + b)
    return not bad


def main(a):
    paths = a[1:] or [os.path.join(ROOT, 'resources/original/pc98/CMD00.SCB'),
                      os.path.join(ROOT, 'resources/original/x68k/CMD00.SCB')]
    ok = all([verify(p) for p in paths])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main(sys.argv)
