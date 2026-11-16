#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_vmstep.py - the engine's interpreter against M.EXE's vm_step, statement by statement.

usage: check_vmstep.py TEST_VM [--routes N]  (with $EMU_PYTHON: unicorn)

The original's vm_step (001E:0133) runs the scenario under re-tools/mcall.py from its entry
statement, with every subsystem the statements call replaced by a stand-in (tests/vmrig.py,
VMOrig): the picture, copy, palette, window, music and mouse calls are only logged with their
arguments; the waits, messages, menus, built-in sequences and the music position take an
answer. Saves and loads are the original's own, on a game.dat of the emulated DOS. The
answers are chosen while the original runs, by an explorer that prefers what was not tried
yet at that statement (each menu choice, a message or sequence skipped or not, a wait cut
short or not, a song or no sound driver at the busy poll of 35h), over many routes, each
ended after a budget of statements or at 2Eh. A few routes run under re-tools/m286.py, and
the clocks of every statement (vm_step, less the stand-ins and the file's time) are compared
with the engine's charge (engine/vm/vm_clk.h). Each route's answers are then given to the
engine (tests/test_vm.c, `run`) with the same stand-ins, and compared line for line: every
call with its arguments, and after every statement its number, opcode, the next pc, the call
stack and all the variables (types and values). At the end a coverage report: the statements
executed against those reachable from the entry statement.
"""
import collections
import os
import random
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
ROUTES = 40
BUDGET = 6000
TIMED = 4                                   # routes also timed (m286), shorter
TIMED_BUDGET = 2500


def menu_switch(sc, p):
    """switch p decides on the menu just before it (statement 24h, then switch on v1 with a
    case for every choice): its default cannot be taken"""
    _, op, a = sc.stmts[p - 1]
    if op != 0x20 or p < 2 or sc.stmts[p - 2][1] != 0x24:
        return False
    node = sc.t0c[a[1] - 1]
    if node != ('B', 6, 1):                 # the expression is the leaf v1 (int)
        return False
    n = len(sc.t44[sc.stmts[p - 2][2][0] - 1][1])
    return {v for v, _ in a[3]} >= set(range(1, n + 1))


def reachable(sc, menus=False):
    """statements reachable from the entry statement (a call also reaches its next); with
    menus, a menu's switch does not take its default"""
    n = len(sc.stmts)
    seen, todo = set(), [sc.h12]
    while todo:
        p = todo.pop()
        if p in seen or not 1 <= p <= n:
            continue
        seen.add(p)
        _, op, a = sc.stmts[p - 1]
        if op == 0x1F:
            todo += [a[1], a[2]]
        elif op == 0x20:
            todo += ([] if menus and menu_switch(sc, p) else [a[2]]) + [t for _, t in a[3]]
        elif op == 0x21:
            todo.append(a[0])
        elif op == 0x22:
            todo += [a[0], p + 1]
        elif op == 0x34:
            todo.append(p + 1 + a[0])
        elif op not in (0x23, 0x2E):
            todo.append(p + 1)
    return seen


class Explorer:
    """the answers: what was tried least at this statement, ties at random"""

    def __init__(self, seed, tried):
        self.rnd = random.Random('check_vmstep %d' % seed)
        self.tried = tried
        self.sound = seed % 2 == 1          # odd routes: a song plays at the busy poll
        self.measure = 0
        self.steps = 0
        self.budget = BUDGET

    def least(self, pc, options):
        c = [(self.tried[(pc, o)], self.rnd.random(), o) for o in options]
        o = min(c)[2]
        self.tried[(pc, o)] += 1
        return o

    def __call__(self, kind, info):
        from vmrig import Budget
        if self.steps >= self.budget:
            raise Budget()
        if kind == 'menu':
            pc, _, n = info
            return self.least(pc, range(1, n + 1))
        if kind in ('msg', 'builtin'):
            # read to the end the first time, skipped the second, then mostly read
            pc = info[0]
            if self.tried[(pc, 0)] and not self.tried[(pc, 1)] or self.rnd.random() < 0.05:
                self.tried[(pc, 1)] += 1
                return 1
            self.tried[(pc, 0)] += 1
            return 0
        if kind == 'wait':
            pc, t, sk = info
            if self.rnd.random() < 0.01:
                return -1                   # every timer slot busy
            return self.least(pc, (0, 1)) if sk else 0
        if kind == 'musstate':
            return 10 if self.sound else 0
        if kind == 'measure':
            if not self.sound:
                return -1
            self.measure += 1               # the measures count up while the poll runs
            return self.measure - 1
        raise KeyError(kind)


def routes(n, timed):
    """n routes; `timed` of them (the last ones, new seeds) under m286 with their clocks"""
    from vmrig import VMOrig, Budget
    data = open(PC98, 'rb').read()
    tried = collections.Counter()
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for seed in range(n + timed):
            ex = Explorer(seed, tried)
            kw = {}
            if seed >= n:
                from m286 import TM
                ex.budget = TIMED_BUDGET
                kw['machine'] = TM
            o = VMOrig(data, ex, files=tmp, **kw)
            if seed >= n:
                o.m.cpf = 0
            o.set_state(o.m.word(o.g, 2), 0, [0] * 32)
            try:
                while ex.steps < ex.budget and o.step():
                    ex.steps += 1
            except Budget:
                pass
            out.append({'answers': o.answers, 'log': o.log, 'timed': seed >= n})
    return out


def noclk(ln):
    """a statement line without its clocks (field 5)"""
    if not ln.startswith('x '):
        return ln
    f = ln.split(' ', 6)
    return ' '.join(f[:5] + f[6:])


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    n = int(argv[argv.index('--routes') + 1]) if '--routes' in argv else ROUTES
    sc = Scenario(open(PC98, 'rb').read())
    want, hit = refcache.get('vmstep', ['check_vmstep.py', 'vmrig.py'], None,
                             {'routes': n, 'budget': BUDGET, 'timed': TIMED,
                              'timed_budget': TIMED_BUDGET}, lambda: routes(n, TIMED))
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for r in want:
            lines += ['gamedat -\n', 'scb %s\n' % PC98,
                      'run %d %s\n' % (sc.h12, ' '.join(str(a) for a in r['answers']))]
        res = subprocess.run([argv[1], tmp], input=''.join(lines), capture_output=True,
                             text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_vmstep: test_vm failed (exit %d)' % res.returncode)
    got, cur = [], None
    for ln in res.stdout.split('\n'):
        if ln.startswith('entry '):
            cur = []
            got.append(cur)
        elif cur is not None and ln.startswith(('x ', 'c ', 'exit ')):
            cur.append(ln)
    bad, nstmt, ntimed, clk, covered = 0, 0, 0, 0, set()
    for k, r in enumerate(want):
        w = r['log']
        g = got[k] if k < len(got) else []
        same = (lambda a, b: a == b) if r['timed'] else (lambda a, b: noclk(a) == noclk(b))
        for i, a in enumerate(w):
            if a.startswith('x '):
                nstmt += 1
                covered.add(int(a.split()[1]))
                if r['timed']:
                    ntimed += 1
                    clk += int(a.split()[5])
            b = g[i] if i < len(g) else '(none)'
            if not same(a, b):
                bad += 1
                print('route %d, line %d:\n  original %s\n  engine   %s' % (k, i, a[:200],
                                                                       b[:200]))
                for c in w[max(0, i - 3):i]:
                    print('  before   %s' % c[:200])
                break
    reach, menu_reach = reachable(sc), reachable(sc, True)
    missing = sorted(menu_reach - covered)
    print('check_vmstep: %d routes, %d statements run (%d timed, %d clocks), %d of the %d '
          'reachable covered (%d only from the default of a menu\'s switch)%s: %s (reference '
          '%s)' % (
              len(want), nstmt, ntimed, clk, len(covered & reach), len(reach),
              len(reach - menu_reach),
              '; not covered: %s' % ' '.join(map(str, missing[:40])) if missing else '',
                              'identical to the original' if not bad
                              else '%d routes differ' % bad, 'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
