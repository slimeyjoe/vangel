#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_fx.py - the engine's op 32h (rectangle copy, transitions) against M.EXE's own.

usage: check_fx.py TEST_FX PAK [EFFECT ...]          (with $EMU_PYTHON: unicorn, capstone)

136 cases (docs/re/graphics.md §5, as re-tools/gfx_fx_verify.py): effects 10, 15, 20, 30-35
on six rectangles (full screen, the background window, odd heights, widths not multiples of
16, one reaching past the right edge), from 12 to 10, 11 to 12 and 10 to 12, over random
planes. The original runs under re-tools/m286.py (rect_copy 0315:07CB, 80286 clocks); the
engine is tests/test_fx.c on the same planes. Compared per case:
  * every write to the destination, in order, with its time: the clocks since op 32 began at
    the instruction that writes it. A frame is cut whenever the clocks reach cpu_per_frame,
    so equal clocks at every write mean the same picture at every frame for any speed. The
    engine runs at the profile's speed and at 997 clocks per frame (cuts everywhere);
  * effect 31, which waits for VSYNCs, by frame and clocks into the frame at both speeds;
  * the final destination planes, and the time at op 32's return.
The original's results are kept between runs (tests/refcache.py) as digests; a difference
is run again under emulation to name the first write that differs.
"""
import hashlib
import multiprocessing
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
REF_CPF = 177242
CUT_CPF = 997
NO_VSYNC = 10 ** 12
GEOMS = ((0, 0, 640, 400, 0, 0), (160, 48, 320, 200, 160, 48), (32, 0, 248, 400, 32, 0),
         (80, 39, 480, 322, 80, 38), (16, 39, 272, 361, 24, 38), (8, 3, 100, 7, 600, 390))
EFFECTS = (10, 15, 20, 30, 31, 32, 33, 34, 35)
PAIRS = ((12, 10), (11, 12), (10, 12))
REC = struct.Struct('<BHBQII')


def cases(only):
    out = []
    for e in EFFECTS:
        if only and e not in only:
            continue
        for (sx, sy, w, h, dx, dy) in GEOMS:
            if e == 31 and w * h > 100000:
                continue                # slow under emulation; the small rectangles cover it
            for src, dst in PAIRS:
                if dst == 12 and e in (31, 34):
                    continue            # 34 always writes VRAM; 31 covered with dst 10
                out.append((src, sx, sy, w, h, dst, dx, dy, e))
    return out


def planes(case):
    rnd = random.Random('check_fx %r' % (case,))
    return (bytes(rnd.getrandbits(8) for _ in range(4 * PLANE)),
            bytes(rnd.getrandbits(8) for _ in range(4 * PLANE)))


def digest(items, fmt):
    h = hashlib.sha256()
    s = struct.Struct(fmt)
    for t in items:
        h.update(s.pack(*t))
    return h.hexdigest()


_op = {}


def original(case, cpf):
    """the original's op 32: (writes, final planes, end); the writes as (plane, offset,
    value, clocks) when cpf is None (no VSYNC), else (plane, offset, value, frame, clocks)"""
    from fx_cost import Op32
    key = cpf or NO_VSYNC
    if key not in _op:
        _op[key] = Op32(cpu_per_frame=key)
    o = _op[key]
    sp, dp = planes(case)
    split = lambda b: [bytearray(b[q * PLANE:(q + 1) * PLANE]) for q in range(4)]  # noqa: E731
    t, ws, _st = o.run(*case, sp=split(sp), dp=split(dp))
    final = b''.join(bytes(p) for p in o.m.get_buf(case[5]))
    if cpf is None:
        return ws, final, t
    return o.frames, final, o.end


def reference(args):
    case, cpf = args
    ws, final, end = original(case, cpf)
    fmt = '<BHBQ' if cpf is None else '<BHBII'
    return {'writes': digest(ws, fmt), 'n': len(ws), 'final': hashlib.sha256(final).hexdigest(),
            'end': list(end) if isinstance(end, tuple) else end}


def ref_cached(args):
    case, cpf = args
    a = {'case': list(case), 'cpf': cpf}
    return refcache.get('fx', ['check_fx.py'], None, a, lambda: reference(args))


def runs(cs):
    """(case, cpf of the reference, cpf of the engine run): for effect 31 the reference is
    timed; for the others it has no VSYNC and serves both engine speeds"""
    out = []
    for c in cs:
        if c[8] == 31:
            out += [(c, REF_CPF, REF_CPF), (c, CUT_CPF, CUT_CPF)]
        else:
            out += [(c, None, REF_CPF), (c, None, CUT_CPF)]
    return out


def engine_records(path):
    data = open(path, 'rb').read()
    return [REC.unpack_from(data, i) for i in range(0, len(data), REC.size)]


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    if len(argv) < 3:
        sys.exit(__doc__)
    test_fx, pak = argv[1], argv[2]
    only = {int(a) for a in argv[3:]}
    cs = cases(only)
    plan = runs(cs)
    refs = sorted({(c, r) for c, r, _e in plan})
    with multiprocessing.Pool(min(len(refs), os.cpu_count() or 1)) as pool:
        got = pool.map(ref_cached, refs, chunksize=1)
    want = {k: v for k, (v, _hit) in zip(refs, got)}
    stored = sum(hit for _v, hit in got)

    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for i, (c, _r, cpf) in enumerate(plan):
            sp, dp = planes(c)
            p = [os.path.join(tmp, '%s%d' % (k, i)) for k in ('s', 'd', 'out', 'log')]
            for path, b in ((p[0], sp), (p[1], dp)):
                with open(path, 'wb') as f:
                    f.write(b)
            lines.append('%d %d %d %d %d %d %d %d %d %d %s %s %s %s\n' % (c + (cpf,) + tuple(p)))
        res = subprocess.run([test_fx, pak], input=''.join(lines), capture_output=True, text=True,
                             check=False)
        status = res.stdout.split('\n')
        if res.returncode != 0 or len(status) < len(plan):
            print(res.stdout + res.stderr)
            sys.exit('check_fx: test_fx failed (exit %d)' % res.returncode)
        for i, (c, r, cpf) in enumerate(plan):
            w = want[(c, r)]
            st = status[i].split()
            out = os.path.join(tmp, 'out%d' % i)
            recs = engine_records(os.path.join(tmp, 'log%d' % i))
            if r is None:
                items = [(q, o, v, clk) for (q, o, v, clk, _f, _c) in recs]
                cuts = all(f * cpf + cc == clk for (_q, _o, _v, clk, f, cc) in recs)
                end_ok = len(st) == 4 and int(st[1]) * cpf + int(st[2]) == w['end'] and \
                    int(st[3]) == w['end']
                wd = digest(items, '<BHBQ')
            else:
                items = [(q, o, v, f, cc) for (q, o, v, _clk, f, cc) in recs]
                cuts = True
                end_ok = len(st) == 4 and [int(st[1]), int(st[2])] == w['end']
                wd = digest(items, '<BHBII')
            final = hashlib.sha256(open(out, 'rb').read()).hexdigest() if os.path.exists(out) else ''
            if st[:1] == ['ok'] and wd == w['writes'] and cuts and end_ok and final == w['final']:
                continue
            bad += 1
            tag = 'effect %2d %2d->%2d %3dx%-3d (%3d,%3d)->(%3d,%3d) at %d clocks/frame' % (
                c[8], c[0], c[5], c[3], c[4], c[1], c[2], c[6], c[7], cpf)
            print('%s: %s' % (tag, explain(c, r, items, st, w, cuts, final)))
    n = len(plan)
    print('check_fx: %d cases, %d runs: %d identical to the original, %d differ '
          '(%d references stored)' % (len(cs), n, n - bad, bad, stored))
    return 1 if bad else 0


def explain(case, cpf, items, st, w, cuts, final):
    if st[:1] != ['ok']:
        return ' '.join(st) or 'no result'
    if not cuts:
        return 'the frames of the writes do not add up to their clocks'
    if len(items) != w['n']:
        msg = '%d writes, the original %d' % (len(items), w['n'])
    else:
        msg = '%d writes' % len(items)
    ws, _final, end = original(case, cpf)
    for k, (a, b) in enumerate(zip(items, ws)):
        if tuple(a) != tuple(b):
            return '%s; write %d differs: engine %r, original %r (the one before: %r)' % (
                msg, k, a, b, ws[k - 1] if k else None)
    if len(items) != len(ws):
        return msg
    if final != w['final']:
        return '%s; the final planes differ' % msg
    return '%s; the end differs: engine %s, original %r' % (msg, ' '.join(st[1:]), end)


if __name__ == '__main__':
    sys.exit(main(sys.argv))
