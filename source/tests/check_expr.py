#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_expr.py - the engine's expressions against M.EXE's expr_eval (0000:0089).

usage: check_expr.py TEST_VM                 (with $EMU_PYTHON: unicorn)

Random expression trees over random variable states, evaluated by the original under
re-tools/mcall.py (the scenario loaded, its node table and variables overwritten) and by the
engine (tests/test_vm.c): every operator (3..16) and leaf kind the scenario uses, values at
the edges of 16 bits (overflow, -32768 / -1, division and remainder by zero, which end the
program with R6003, exit code 255), variable leaves whose kind disagrees with the variable's
type, and what ends the program with exit(4): operators and leaf kinds that do not exist,
node numbers outside the table. Compared: the value, or the exit code.
"""
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import refcache  # noqa: E402

PC98 = os.path.join(ROOT, 'resources', 'original', 'pc98', 'CMD00.SCB')
CASES = 800
NVAR = 20                                   # VA's variables (v0 is the unused slot)
NEXPR = 430
EDGE = [-32768, -32767, -2, -1, 0, 0, 1, 2, 3, 7, 255, 256, 32767]


def value(rnd):
    return rnd.choice(EDGE) if rnd.random() < 0.6 else rnd.randint(-32768, 32767)


def case(rnd):
    """(variables, nodes, root): the root is node 1 except for a few out of range"""
    vars_ = [(rnd.choice([6, 10, 6, 10, 2, 14, 0x46]), value(rnd)) for _ in range(NVAR + 1)]
    nodes = []

    def gen(depth):
        n = len(nodes) + 1
        nodes.append(None)
        if depth == 0 or rnd.random() < 0.3:
            r = rnd.random()
            if r < 0.9:
                kind = rnd.choice([5, 6, 9, 10])
            else:
                kind = rnd.choice([0, 1, 2, 3, 4, 7, 8, 11, 12, 13, 14, 15, -1, 0x45])
            v = rnd.randint(0, NVAR) if kind & 2 and not kind & 1 else value(rnd)
            nodes[n - 1] = (1, kind, v, 0)
            return n
        r = rnd.random()
        op = rnd.randint(3, 16) if r < 0.96 else rnd.choice([0, 1, 2, 17, -3])
        if op in (8, 9) and rnd.random() < 0.5:     # divisions with an edge divisor
            a = gen(depth - 1)
            b = len(nodes) + 1
            nodes.append((1, 5, rnd.choice([0, -1, 1, 2]), 0))
            nodes[n - 1] = (0, op, a, b)
            return n
        a = gen(depth - 1)
        b = gen(depth - 1) if op not in (3, 4) else rnd.choice([0, 9999])
        if rnd.random() < 0.02:
            a = rnd.choice([0, NEXPR + 1, -5])
        nodes[n - 1] = (0, op, a, b)
        return n
    gen(rnd.randint(0, 5))
    root = 1 if rnd.random() < 0.97 else rnd.choice([0, NEXPR + 1, -1, NEXPR])
    return vars_, nodes, root


def cases():
    rnd = random.Random('check_expr 1')
    return [case(rnd) for _ in range(CASES)]


def original(cs, empty):
    from vmrig import Orig
    o = Orig(open(PC98, 'rb').read(), files=empty)
    out = []
    for vars_, nodes, root in cs:
        for i, (t, v) in enumerate(vars_):
            o.set_var(i, t, v)
        for i, nd in enumerate(nodes, 1):
            o.set_node(i, *nd)
        r = o.expr(root)
        out.append('%s %d' % r if r[0] != 'hang' else 'hang')
    return out


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    cs = cases()
    with tempfile.TemporaryDirectory() as tmp:
        empty = os.path.join(tmp, 'empty')
        os.mkdir(empty)
        want, hit = refcache.get('expr', ['check_expr.py', 'vmrig.py'], None,
                                 {'cases': CASES, 'seed': 1}, lambda: original(cs, empty))
        lines = ['scb %s\n' % PC98]
        for vars_, nodes, root in cs:
            lines += ['var %d %d %d\n' % (i, t, v) for i, (t, v) in enumerate(vars_)]
            lines += ['node %d %d %d %d %d\n' % ((i,) + nd) for i, nd in enumerate(nodes, 1)]
            lines.append('expr %d\n' % root)
        res = subprocess.run([argv[1], empty], input=''.join(lines), capture_output=True,
                             text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_expr: test_vm failed (exit %d)' % res.returncode)
    got = [ln for ln in res.stdout.split('\n') if ln.startswith(('expr ', 'exit '))]
    bad = 0
    kinds = {}
    for k, w in enumerate(want):
        g = got[k] if k < len(got) else '(none)'
        kinds[w.split()[0] + (' ' + w.split()[1] if w.startswith('exit') else '')] = \
            kinds.get(w.split()[0] + (' ' + w.split()[1] if w.startswith('exit') else ''), 0) + 1
        if g != w:
            bad += 1
            if bad <= 10:
                print('case %d: original %s, engine %s; nodes %r root %d' % (
                    k, w, g, cs[k][1], cs[k][2]))
    print('check_expr: %d expressions (%s): %s (reference %s)' % (
        len(want), ', '.join('%s %d' % kv for kv in sorted(kinds.items())),
        'identical to the original' if not bad else '%d differ' % bad,
        'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
