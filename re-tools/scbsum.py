#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""scbsum.py - per-subroutine summary of CMD00.SCB for the script catalog (stdlib only).
  scbsum.py SCB      one block per subroutine (and the main program): statements, callers,
                     callees, messages, menus, pictures, songs (v20 values), variables
                     read/written, built-ins, saves, gotos leaving the routine."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source', 'tools'))  # gf, scb, txb
from scb import Scenario
from scbdis import Dis

def main(a):
    sc = Scenario(open(a[1], 'rb').read())
    d = Dis(sc)
    seen, subs = d.flow()
    entries = sorted(subs | {sc.h12})
    # body of a routine: statements reachable from its entry without following calls/returns
    owner = {}
    callers = {}
    for e in entries:
        work, body = [e], set()
        while work:
            k = work.pop()
            if k in body or not 1 <= k <= d.n:
                continue
            body.add(k)
            txt, succ, kind = d.stmt(k)
            if kind == 'call':
                callers.setdefault(succ[0], set()).add(e)
                work.append(succ[1])
            else:
                work += succ
        owner[e] = body
    for e in entries:
        body = sorted(owner[e])
        info = {'msg': [], 'menu': [], 'pic': [], 'song': [], 'w': set(), 'r': set(), 'bi': [], 'call': [], 'out': [], 'other': []}
        for k in body:
            txt, succ, kind = d.stmt(k)
            op = sc.stmts[k - 1][1]
            args = sc.stmts[k - 1][2]
            if op == 0x19: info['msg'].append(args[0])
            elif op == 0x24: info['menu'].append(args[0])
            elif op == 0x31: info['pic'].append(args[4])
            elif op == 0x25: info['bi'].append(txt.split()[1])
            elif op == 0x22: info['call'].append(args[0])
            elif op in (0x1D, 0x36, 0x2E, 0x1B, 0x35, 0x1C): info['other'].append(txt)
            m = re.match(r'v(\d+) = (.*)', txt)
            if m:
                info['w'].add(int(m.group(1)))
                if m.group(1) == '20':
                    info['song'].append(m.group(2))
                rest = m.group(2)
            else:
                rest = txt
            for x in re.findall(r'v(\d+)', rest):
                info['r'].add(int(x))
            for s in succ:
                if kind != 'call' and s not in owner[e] and 1 <= s <= d.n:
                    info['out'].append(s)
        rng = '%d-%d' % (body[0], body[-1])
        print('== %s %d  [%d stmts, %s] callers %s' % ('MAIN' if e == sc.h12 else 'sub', e, len(body), rng, sorted(callers.get(e, []))))
        def short(l):
            l = list(l)
            return ('%d..%d (%d)' % (min(l), max(l), len(l))) if len(l) > 6 else str(l)
        print('   msgs %s menus %s' % (short(info['msg']) if info['msg'] else '-', info['menu']))
        pics = sorted(set(info['pic']))
        print('   pics %s' % ' '.join(pics))
        print('   songs %s  calls %s' % (info['song'], sorted(set(info['call']))))
        print('   vars w %s r %s  builtins %s other %s out %s' % (sorted(info['w']), sorted(info['r']), info['bi'], info['other'], sorted(set(info['out']))[:10]))

main(sys.argv)
