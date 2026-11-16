#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_gf.py - the engine's picture decoder against M.EXE's own picture loader.

usage: check_gf.py TEST_GF PAK [NAME ...]        (with $EMU_PYTHON: unicorn)

For every picture of GDATA.LIB, four cases of op 31h (docs/re/graphics.md §3-4), each over a
background of random bytes:
  A  buffer 12 (memory planes), flag 0, the file's position     (015A:0B0A)
  B  buffer 12, flag 1 (colour 8 transparent)                     (015A:1076)
  C  buffer 10 (VRAM page 0), flag 0                              (015A:000A)
  D  buffer 11 (VRAM page 1), flag 1, an explicit position        (015A:0554)
The original runs under re-tools/mcall.py (pic_load 0315:070D, as the scenario's op 31h calls
it); the engine is tests/test_gf.c over the same background. The original's results are kept
between runs (tests/refcache.py): a digest of the planes per case; on a difference the case is
run again under emulation to say how many bytes differ.
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
import gf        # noqa: E402

CASES = (('A', 12, 0, False), ('B', 12, 1, False), ('C', 10, 0, False), ('D', 11, 1, True))
PLANE = 32000


def case_inputs(name, w, h, tag, explicit):
    """the background and position of a case: derived from the picture and the case only"""
    rnd = random.Random('%s/%s' % (name, tag))
    bg = bytes(rnd.getrandbits(8) for _ in range(4 * PLANE))
    if explicit:
        x = rnd.randrange(0, 640 - w + 1) & ~7
        y = rnd.randrange(0, 400 - h + 1)
    else:
        x = y = -1
    return bg, x, y


class Original:
    """M.EXE under mcall, with gfx_init done (made on first use)"""

    def __init__(self):
        from mcall import M
        self.m = M(trace_ports=False)
        ax, _ = self.m.call(0x0315, 0x000E)         # gfx_init: open GDATA.LIB, allocate buffers
        if ax != 1:
            sys.exit('check_gf: gfx_init failed under emulation (%r)' % ax)
        self.op = self.m.alloc(64)

    def _mem_planes(self):
        g = self.m.seg(0x0BA1)
        return [self.m.word(g, 0x46 + 2 * q) for q in range(4)]

    def run(self, name, buf, flag, x, y, bg):
        m = self.m
        planes = [bg[q * PLANE:(q + 1) * PLANE] for q in range(4)]
        if buf == 12:
            for s, p in zip(self._mem_planes(), planes):
                m.poke(s, 0, p)
        else:
            for q in range(4):
                m.pages[buf - 10][q][:PLANE] = planes[q]
        blk = bytearray(0x16)
        base = name.rsplit('.', 1)[0].encode('ascii')
        blk[0:len(base)] = base
        struct.pack_into('<hhhh', blk, 0x0E, flag, buf, x, y)
        m.poke(self.op, 0, bytes(blk))
        r, _ = m.call(0x0315, 0x070D, [0, self.op])
        if r != 1:
            raise RuntimeError('pic_load(%s) returned %d' % (name, r))
        if buf == 12:
            return b''.join(bytes(m.mem(s, 0, PLANE)) for s in self._mem_planes())
        return b''.join(bytes(m.pages[buf - 10][q][:PLANE]) for q in range(4))


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    test_gf, pak = argv[1], argv[2]
    only = set(argv[3:])
    lib = open(gf.LIB, 'rb').read()
    ar = gf.Archive(lib)
    orig = []                                       # an Original, made when needed

    def original():
        if not orig:
            orig.append(Original())
        return orig[0]

    cases = []
    for name, off, _size in ar.entries:
        if only and name not in only and name.rsplit('.', 1)[0] not in only:
            continue
        w, h, _x, _y = gf.header(lib, off)
        for tag, buf, flag, explicit in CASES:
            bg, x, y = case_inputs(name, w, h, tag, explicit)
            cases.append((name, tag, buf, flag, x, y, bg))

    def reference(c):
        name, tag, buf, flag, x, y, bg = c
        return original().run(name, buf, flag, x, y, bg)

    stored = 0
    want = {}
    for c in cases:
        name, tag, buf, flag, x, y, _bg = c
        args = {'name': name, 'case': tag, 'buf': buf, 'flag': flag, 'x': x, 'y': y}
        digest, hit = refcache.get('gf', ['check_gf.py'], None, args,
                                   lambda c=c: hashlib.sha256(reference(c)).hexdigest())
        want[(name, tag)] = digest
        stored += hit

    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for i, (name, tag, buf, flag, x, y, bg) in enumerate(cases):
            bgp, outp = os.path.join(tmp, 'bg%d' % i), os.path.join(tmp, 'out%d' % i)
            with open(bgp, 'wb') as f:
                f.write(bg)
            lines.append('%s %d %d %d %s %s\n' % (name, x, y, flag, bgp, outp))
        res = subprocess.run([test_gf, pak], input=''.join(lines), capture_output=True,
                             text=True, check=False)
        status = res.stdout.split('\n')
        if res.returncode != 0 or len(status) < len(cases):
            print(res.stdout + res.stderr)
            sys.exit('check_gf: test_gf failed (exit %d)' % res.returncode)
        for i, c in enumerate(cases):
            name, tag = c[0], c[1]
            outp = os.path.join(tmp, 'out%d' % i)
            got = open(outp, 'rb').read() if os.path.exists(outp) else b''
            if status[i] == 'ok' and hashlib.sha256(got).hexdigest() == want[(name, tag)]:
                continue
            bad += 1
            ref = reference(c)
            diff = sum(1 for a, b in zip(got, ref) if a != b) + abs(len(got) - len(ref))
            print('%-12s %s: %s, %d bytes differ from the original' % (name, tag, status[i], diff))
    n = len(cases)
    print('check_gf: %d pictures x %d cases: %d identical to the original, %d differ '
          '(%d references stored)' % (n // len(CASES), len(CASES), n - bad, bad, stored))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
