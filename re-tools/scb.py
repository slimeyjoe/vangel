#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""scb.py - parser for Virgin Angel's compiled scenario CMD00.SCB ("CRSC"), stdlib only.

Format (from M.EXE's loader, seg 06BBh/06DDh/063Ch; docs/re/scenario-format.md):
  plain:     "CRSC" 01 01 "DOS " u32 filesize, u32 ?, u16 ?, u8 key
  plain:     sections: tag byte; 0 = end; 4..0Ch = u16 count (0Ah = u16 len + C string)
  encrypted (key != 0): every following byte b is returned as  state ^= (b + key); b' = state & 0FFh
             (state starts at 0; bytes are sign-extended by the reader, words little endian)
  tables, in this order: T42 (count tag 9), T44 (tag 5), T0C (tag 6), T0A palettes (tag 8),
             statements (tag 4).

Usage:  scb.py FILE.SCB [--dump]       (summary, or every table and statement)
As a module: Scenario(open(...).read()) -> .header, .counts, .t42, .t44, .t0c, .pal, .stmts
"""
import struct
import sys

TAGS = {4: 'n_stmt', 5: 'n_t44', 6: 'n_t0c', 7: 'n_t52', 8: 'n_pal', 9: 'n_t42', 0xB: 'n_d4',
        0xC: 'n_04'}

# opcode -> operand layout: b = signed byte, B = bool byte (!=0), 1 = bool byte (==1),
# w = word, s = string, P = palette byte, L = list (op 20h), x = invalid
OPS = {
    0x15: 'wB', 0x16: '', 0x17: '', 0x18: '', 0x19: 'w', 0x1A: 'Bw', 0x1B: 'ws', 0x1C: 'w',
    0x1D: '', 0x1E: 'wb', 0x1F: 'www', 0x20: 'L', 0x21: 'w', 0x22: 'w', 0x23: 'w', 0x24: 'w',
    0x25: 'b', 0x26: 'x', 0x27: 'x', 0x28: 'x', 0x29: 'x', 0x2A: 'x', 0x2B: '', 0x2D: '',
    0x2E: '', 0x2F: 'w', 0x30: 'wP', 0x31: 'bwwbs', 0x32: 'bwwwwbwwb', 0x33: 'b', 0x34: 'b',
    0x35: '', 0x36: '', 0x37: '1',
}


class Reader:
    def __init__(self, data, pos=0):
        self.d, self.p, self.key, self.state = data, pos, 0, 0

    def raw(self):
        if self.p >= len(self.d):
            raise EOFError('end of file at %#x' % self.p)
        c = self.d[self.p]
        self.p += 1
        return c

    def c(self):
        """scb_getc: decrypted byte, sign-extended as the original (cwde)."""
        b = self.raw()
        if self.key:
            self.state ^= (b + self.key)
            b = self.state & 0xFF
        return b - 256 if b & 0x80 else b

    def w(self):
        lo = self.c() & 0xFF
        hi = self.c() & 0xFF
        v = lo | hi << 8
        return v - 0x10000 if v & 0x8000 else v

    def s(self):
        out = bytearray()
        while True:
            b = self.c() & 0xFF
            if not b:
                return bytes(out)
            out.append(b)


class Scenario:
    def __init__(self, data):
        r = Reader(data)
        if data[:4] != b'CRSC':
            raise ValueError('not a CRSC file')
        r.p = 4
        self.version = (r.raw(), r.raw())
        self.system = bytes(r.raw() for _ in range(4))
        self.size, self.h0e = struct.unpack_from('<II', data, r.p)
        r.p += 8
        self.h12 = struct.unpack_from('<H', data, r.p)[0]
        r.p += 2
        self.key = r.raw()
        self.counts = {}
        self.textfile = None
        while True:
            t = r.raw()
            if t == 0:
                break
            if t == 0xA:
                n = r.raw() | r.raw() << 8
                b = bytearray()
                while True:
                    c = r.raw()
                    if not c:
                        break
                    b.append(c)
                self.textfile = b.decode('cp932')
                continue
            if t not in TAGS:
                raise ValueError('bad section tag %#x at %#x' % (t, r.p - 1))
            self.counts[TAGS[t]] = r.raw() | r.raw() << 8
        self.body = r.p
        r.key = self.key
        n = self.counts
        self.t42 = [(r.c(), r.w()) for _ in range(n['n_t42'])]
        self.t44 = []
        for _ in range(n['n_t44']):
            k = r.c()
            if not 1 <= k <= 4:
                raise ValueError('T44 entry with %d strings at %#x' % (k, r.p))
            ln = r.w()
            self.t44.append((ln, [r.s() for _ in range(k)]))
        self.t0c = []
        for _ in range(n['n_t0c']):
            k = r.c()
            if k == 0:
                self.t0c.append(('A', r.c(), r.w(), r.w()))
            elif k == 1:
                self.t0c.append(('B', r.c(), r.w()))
            else:
                raise ValueError('T0C type %d at %#x' % (k, r.p))
        self.pal = []
        for _ in range(n['n_pal']):
            nib = []
            for i in range(24):
                b = r.c() & 0xFF
                nib += [b >> 4, b & 15]
            # 16 entries x (c0, c1, c2) in the order read: e[i] = nib[3i], nib[3i+1], nib[3i+2]
            self.pal.append([tuple(nib[3 * i:3 * i + 3]) for i in range(16)])
        self.stmts = []
        for i in range(n['n_stmt']):
            at = r.p
            op = r.c() & 0xFF
            if op not in OPS or OPS[op] == 'x':
                raise ValueError('statement %d: bad opcode %#x at %#x' % (i, op, at))
            args = []
            for f in OPS[op]:
                if f == 'b' or f == 'P':
                    args.append(r.c())
                elif f == 'B':
                    args.append(int(r.c() != 0))
                elif f == '1':
                    args.append(int(r.c() == 1))
                elif f == 'w':
                    args.append(r.w())
                elif f == 's':
                    args.append(r.s().decode('cp932', 'replace'))
                elif f == 'L':
                    args.append(r.c())
                    args.append(r.w())
                    k = r.c()
                    args.append(r.w())
                    args.append([(r.w(), r.w()) for _ in range(k)])
            self.stmts.append((at, op, args))
        self.end = r.p


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    sc = Scenario(open(a[1], 'rb').read())
    print('version %r system %r size %d h0e %#x h12 %#x key %#x text %r' % (
        sc.version, sc.system, sc.size, sc.h0e, sc.h12, sc.key, sc.textfile))
    print('counts', sc.counts, 'body at %#x, end %#x of %#x' % (sc.body, sc.end, len(open(a[1], 'rb').read())))
    from collections import Counter
    print('opcodes', sorted(Counter('%02x' % s[1] for s in sc.stmts).items()))
    if '--dump' in a:
        for i, e in enumerate(sc.t42):
            print('T42 %3d %r' % (i, e))
        for i, e in enumerate(sc.t44):
            print('T44 %3d %d %r' % (i, e[0], [x.decode('cp932', 'replace') for x in e[1]]))
        for i, e in enumerate(sc.t0c):
            print('T0C %3d %r' % (i, e))
        for i, p in enumerate(sc.pal):
            print('PAL %2d %s' % (i, ' '.join('%x%x%x' % c for c in p)))
        for i, (at, op, args) in enumerate(sc.stmts):
            print('S %4d @%05x %02x %r' % (i, at, op, args))


if __name__ == '__main__':
    main(sys.argv)
