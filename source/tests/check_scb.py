#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_scb.py - the engine's scenario loader against M.EXE's own.

usage: check_scb.py TEST_VM [SCB ...]      (with $EMU_PYTHON: unicorn)

The original's scb_load (063C:00E8) runs under re-tools/mcall.py, as main calls it, on the
PC-98 CMD00.SCB (and the X68000 one when it is imported, or given as an argument), and on
damaged copies of the PC-98 file: cut short at many points (the end reads as EOF), a wrong
signature, bad section tags, bad text name lengths, counts too small or too large, a variable
without bit 1 in its type, menus of 0 and 5 choices, an expression node of form 2, invalid
opcodes, and every operand check of scenario-format.md §3 broken (and kept at its limit).
A change inside the encrypted part is made to the decrypted bytes, which are then encrypted
again. Compared with the engine's loader (tests/test_vm.c): the result (0, or the exit code)
and, when it loads, every table: header and counts, variables, menus, expression nodes,
palettes, statements with their operands, and the statement execution starts with. Where
the original reads for ever (a string cut short) the engine must refuse the file (exit 2).
Not compared: a menu whose size word is smaller than its strings (the original writes past
its allocation, and the strings are what later allocations leave of them).
"""
import hashlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import refcache  # noqa: E402
from scb import Scenario  # noqa: E402

PC98 = os.path.join(ROOT, 'resources', 'original', 'pc98', 'CMD00.SCB')
X68K = os.path.join(ROOT, 'resources', 'original', 'x68k', 'CMD00.SCB')


def decrypt(raw, body, key):
    s, out = 0, bytearray()
    for b in raw[body:]:
        s ^= (b + key) & 0xFF
        out.append(s)
    return out


def encrypt(plain, key):
    s, out = 0, bytearray()
    for p in plain:
        out.append(((s ^ p) - key) & 0xFF)
        s = p
    return bytes(out)


class Doc:
    """the file: plain header and sections, the decrypted body, the statements' offsets"""

    def __init__(self, raw):
        self.raw = raw
        self.sc = sc = Scenario(raw)
        self.body = sc.body
        self.key = sc.key
        self.plain = decrypt(raw, sc.body, sc.key)
        self.st = [at - sc.body for at, _, _ in sc.stmts]       # statement i+1
        # the tables' starts in the decrypted body
        p = 3 * sc.counts['n_t42']
        self.menus = p
        for ln, items in sc.t44:
            p += 3 + sum(len(x) + 1 for x in items)
        self.exprs = p
        self.expr_at = []
        for e in sc.t0c:
            self.expr_at.append(p)
            p += 6 if e[0] == 'A' else 4

    def first(self, op):
        """the offset and number of the first statement with opcode op"""
        for i, (_, o, _) in enumerate(self.sc.stmts):
            if o == op:
                return self.st[i], i + 1
        raise KeyError(op)

    def build(self, plain=None, head=None):
        head = self.raw[:self.body] if head is None else head
        return bytes(head) + encrypt(self.plain if plain is None else plain, self.key)


def w16(v):
    return bytes([v & 0xFF, (v >> 8) & 0xFF])


def cases():
    raw = open(PC98, 'rb').read()
    d = Doc(raw)
    sc = d.sc
    out = [('pc98', raw)]

    def body(name, fn):
        p = bytearray(d.plain)
        fn(p)
        out.append((name, d.build(p)))

    def head(name, fn):
        h = bytearray(raw[:d.body])
        fn(h)
        out.append((name, d.build(head=h)))

    # cut short
    n = len(raw)
    for cut in sorted({0, 2, 4, 6, 0x0E, 0x14, 0x15, 0x18, d.body - 1, d.body, d.body + 1,
                       d.body + 30, d.body + d.menus + 1, d.body + d.menus + 40,
                       d.body + d.exprs + 3, d.body + d.exprs + 700,
                       d.body + d.st[0] - 5, d.body + d.st[0], d.body + d.st[0] + 1,
                       d.body + d.st[100], d.body + d.st[1000] + 2, d.body + d.st[2000],
                       n - 40, n - 3, n - 1}):
        out.append(('cut %d' % cut, raw[:cut]))
    head('signature', lambda h: h.__setitem__(3, ord('D')))
    head('key 0', lambda h: h.__setitem__(0x14, 0))

    # sections (plain, from 15h: tag, word ... ; 0Ah: word n, C string)
    tags, p = [], 0x15
    while raw[p]:
        tags.append(p)
        p += 1 + (2 + raw[p + 3:].index(0) + 1 if raw[p] == 0xA else 2)
    end = p
    for t in (1, 2, 3, 0xD, 0xFF):
        head('tag %02x' % t, lambda h, t=t: h.__setitem__(slice(end, end + 1), bytes([t, 0])))
    name = [q for q in tags if raw[q] == 0xA][0]
    for ln in (0, 1, 13, 14, -1):
        head('text name length %d' % ln,
             lambda h, ln=ln: h.__setitem__(slice(name + 1, name + 3), w16(ln)))
    counts = {raw[q]: q for q in tags if raw[q] != 0xA}
    for tag, delta, what in ((4, -1, 'statements'), (4, -100, 'statements'),
                             (4, 1, 'statements'), (7, -100, 'messages'), (7, 0x7FFF, 'messages'),
                             (5, -1, 'menus'), (6, -1, 'expressions'), (6, -400, 'expressions'),
                             (8, -1, 'palettes'), (9, -1, 'variables'), (9, 1, 'variables'),
                             (0xB, 1000, 'tag 0Bh'), (0xC, -61, 'tag 0Ch')):
        q = counts[tag]
        v = raw[q + 1] | raw[q + 2] << 8
        nv = (v + delta) & 0xFFFF if delta != 0x7FFF else 0x7FFF
        head('%s %+d' % (what, delta),
             lambda h, q=q, nv=nv: h.__setitem__(slice(q + 1, q + 3), w16(nv)))
    head('variables 0', lambda h: h.__setitem__(slice(counts[9] + 1, counts[9] + 3), w16(0)))
    head('variables -1', lambda h: h.__setitem__(slice(counts[9] + 1, counts[9] + 3),
                                                  w16(0xFFFF)))
    head('entry 1', lambda h: h.__setitem__(slice(0x12, 0x14), w16(1)))
    head('entry 0', lambda h: h.__setitem__(slice(0x12, 0x14), w16(0)))
    head('entry 3000', lambda h: h.__setitem__(slice(0x12, 0x14), w16(3000)))

    # the tables
    body('variable type 4', lambda p: p.__setitem__(3, 4))
    body('variable type 2', lambda p: p.__setitem__(3, 2))
    body('variable type -1', lambda p: p.__setitem__(3, 0xFF))
    body('menu of 0', lambda p: p.__setitem__(d.menus, 0))
    body('menu of 5', lambda p: p.__setitem__(d.menus, 5))
    body('expression form 2', lambda p: p.__setitem__(d.exprs, 2))
    body('expression form -1', lambda p: p.__setitem__(d.exprs, 0xFF))
    body('expression op -3', lambda p: p.__setitem__(d.expr_at[0] + 1, 0xFD)
         if p[d.expr_at[0]] == 0 else None)

    # statements
    def stmt(name, op, off, data):
        at, i = d.first(op)

        def fn(p):
            p[at + off:at + off + len(data)] = data
        body('%s (statement %d)' % (name, i), fn)
    at1 = d.st[10]
    for op in (0x00, 0x14, 0x26, 0x2A, 0x2C, 0x38, 0x7F, 0x80, 0xFF):
        body('opcode %02x' % op, lambda p, op=op: p.__setitem__(at1, op))
    nmsg, nexpr, nmenu, npal = (sc.counts['n_t52'], sc.counts['n_t0c'], sc.counts['n_t44'],
                                sc.counts['n_pal'])
    for v in (0, nmsg, nmsg + 1, -1):
        stmt('19h message %d' % v, 0x19, 1, w16(v))
    for v in (0, nexpr, nexpr + 1, -1):
        stmt('1Eh expr %d' % v, 0x1E, 1, w16(v))
    for v in (0, 1, 0x7F, 0x80):
        stmt('1Eh variable %d' % v, 0x1E, 3, bytes([v]))
    for v in (0, nexpr + 1, -2):
        stmt('1Fh expr %d' % v, 0x1F, 1, w16(v))
    for t, e in ((-1, 5), (5, -1), (0, 5), (0, 0), (5, 0), (0x7FFF, 0x7FFF)):
        stmt('1Fh then %d else %d' % (t, e), 0x1F, 3, w16(t) + w16(e))
    for v in (0, nexpr + 1, -1):
        stmt('20h expr %d' % v, 0x20, 2, w16(v))
    for v in (0, 1, 15, 16, 0x80):
        stmt('20h cases %d' % v, 0x20, 4, bytes([v]))
    for v in (0, -1, 0x7FFF):
        stmt('20h default %d' % v, 0x20, 5, w16(v))
    for v in (0, nexpr, nexpr + 1, -1):
        stmt('23h expr %d' % v, 0x23, 1, w16(v))
    for v in (0, 1, nmenu, nmenu + 1, -1):
        stmt('24h menu %d' % v, 0x24, 1, w16(v))
    for v in (0, 1, 2, npal):
        stmt('30h palette %d' % v, 0x30, 3, bytes([v]))
    for v in (0, 2, 0xFF):
        stmt('37h flag %d' % v, 0x37, 1, bytes([v]))
        stmt('15h skippable %d' % v, 0x15, 3, bytes([v]))
        stmt('1Ah white %d' % v, 0x1A, 1, bytes([v]))
    stmt('25h n -1', 0x25, 1, b'\xff')
    stmt('34h -128', 0x34, 1, b'\x80')
    stmt('31h name of 13', 0x31, 7, b'ABCDEFGHIJKLM\0')
    stmt('1Bh name of 19', 0x1B, 3, b'ABCDEFGHIJKLMNOPQRS\0')
    return out


def entry_of(dump):
    """main's choice (§1 step 6): the header's entry when it is a statement 2Dh, else 1"""
    h = dump[0].split()
    entry, n = int(h[1]), int(h[3])
    for ln in dump:
        if ln.startswith('s %d ' % entry):
            if 1 <= entry <= n and ln.split()[2] == '2d':
                return entry
    return 1


def original(datas, empty):
    from vmrig import Orig
    out = []
    for data in datas:
        o = Orig(data, files=empty)
        if o.rc == 0:
            dump = o.dump_scb()
            out.append(['scb 0'] + dump + ['entry %d' % entry_of(dump)])
        else:
            out.append(['scb %s' % o.rc])
    return out


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    test_vm = argv[1]
    cs = cases()
    extra = argv[2:] or ([X68K] if os.path.exists(X68K) else [])
    for p in extra:
        cs.append((os.path.basename(os.path.dirname(p)) + '/' + os.path.basename(p),
                   open(p, 'rb').read()))
    with tempfile.TemporaryDirectory() as tmp:
        empty = os.path.join(tmp, 'empty')
        os.mkdir(empty)
        want, hit = refcache.get(
            'scb', ['check_scb.py', 'vmrig.py'], None,
            {'cases': [[n, hashlib.sha256(b).hexdigest()] for n, b in cs]},
            lambda: original([b for _, b in cs], empty))
        lines = []
        for k, (name, data) in enumerate(cs):
            p = os.path.join(tmp, 'c%d.scb' % k)
            with open(p, 'wb') as f:
                f.write(data)
            lines.append('scb %s\n' % p)
        res = subprocess.run([test_vm, empty], input=''.join(lines), capture_output=True,
                             text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_scb: test_vm failed (exit %d)' % res.returncode)
    got, cur = [], None
    for ln in res.stdout.split('\n'):
        if ln.startswith('scb '):
            cur = [ln]
            got.append(cur)
        elif ln and cur is not None:
            cur.append(ln)
    bad = loaded = hang = 0
    for k, (name, _) in enumerate(cs):
        w = want[k] if k < len(want) else ['(none)']
        g = got[k] if k < len(got) else ['(none)']
        if w == ['scb hang']:
            hang += 1
            ok = g == ['scb 2']
        else:
            ok = w == g
        loaded += w[0] == 'scb 0'
        if not ok:
            bad += 1
            print('%s: original %s, engine %s' % (name, w[0], g[0]))
            for a, b in zip(w, g):
                if a != b:
                    print('  original %s\n  engine   %s' % (a[:150], b[:150]))
                    break
    print('check_scb: %d files (%d load, %d the original reads for ever): %s (reference %s)' %
          (len(cs), loaded, hang, 'identical to the original' if not bad else '%d differ' % bad,
           'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
