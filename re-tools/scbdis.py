#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""scbdis.py - readable listing and flow analysis of CMD00.SCB (stdlib only).

  scbdis.py SCB [--txb TXB] [--out FILE]      listing: 1-based statement numbers (as the VM's pc),
                                              infix expressions, labels, menus and messages inline
  scbdis.py SCB --graph                       reachability from the entry statement, subroutines,
                                              unreachable statements, per-opcode counts

Semantics follow docs/re/scenario-format.md (M.EXE segment 001E handlers).  Messages are
printed by number; with --txb and re-tools/txb.py present, their first characters are shown.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scb import Scenario  # noqa: E402

BIN = {5: '+', 6: '-', 7: '*', 8: '/', 9: '%', 10: '&', 11: '|', 12: '^', 13: '==', 14: '!=',
       15: '>', 16: '<'}
BUILTIN = {0: 'INIT', 1: 'OPENING', 2: 'ENDING', 3: 'ANNOUNCE', 4: 'MUSMODE', 5: 'ENDING2'}


class Dis:
    def __init__(self, sc, messages=None):
        self.sc = sc
        self.msg = messages or {}
        self.n = len(sc.stmts)

    def expr(self, i):
        """Expression #i (1-based) as infix text."""
        if not 1 <= i <= len(self.sc.t0c):
            return '?e%d' % i
        e = self.sc.t0c[i - 1]
        if e[0] == 'B':
            kind, v = e[1], e[2]
            if kind & 1:
                return ('%d' % v) if kind & 4 else ('true' if v else 'false')
            if kind & 2:
                return 'v%d' % v + ('' if kind & 4 else '?')
            return '?leaf(%d,%d)' % (kind, v)
        op, l, r = e[1], e[2], e[3]
        if op == 3:
            return '-(%s)' % self.expr(l)
        if op == 4:
            return '~(%s)' % self.expr(l)
        return '(%s %s %s)' % (self.expr(l), BIN.get(op, '?%d' % op), self.expr(r))

    def stmt(self, k):
        """Statement k (1-based): (mnemonic text, successors list, kind)."""
        at, op, a = self.sc.stmts[k - 1]
        nxt = k + 1
        if op == 0x15:
            return 'wait %d.%02ds%s' % (a[0] // 100, a[0] % 100, ' skippable -> v1' if a[1] else ''), [nxt], ''
        if op == 0x16:
            return 'wait_input', [nxt], ''
        if op in (0x17,):
            return 'nop17', [nxt], ''
        if op == 0x18:
            return 'op18', [nxt], ''
        if op == 0x19:
            t = self.msg.get(a[0])
            return 'msg %d%s' % (a[0], ('  ; ' + t) if t else ''), [nxt], ''
        if op == 0x1A:
            return 'op1A %d, %d' % (a[0], a[1]), [nxt], ''
        if op == 0x1B:
            return 'music_play %d, "%s"' % (a[0], a[1]), [nxt], ''
        if op == 0x1C:
            return 'music_fade %d' % a[0], [nxt], ''
        if op == 0x1D:
            return 'save slot(v1)', [nxt], ''
        if op == 0x1E:
            return 'v%d = %s' % (a[1], self.expr(a[0])), [nxt], ''
        if op == 0x1F:
            return 'if %s goto %d else %d' % (self.expr(a[0]), a[1], a[2]), [a[1], a[2]], ''
        if op == 0x20:
            cases = ', '.join('%d:%d' % c for c in a[3])
            return 'switch %s {%s} default %d' % (self.expr(a[1]), cases, a[2]), \
                [t for _, t in a[3]] + [a[2]], ''
        if op == 0x21:
            return 'goto %d' % a[0], [a[0]], ''
        if op == 0x22:
            return 'call %d' % a[0], [a[0], nxt], 'call'
        if op == 0x23:
            return ('return %s' % self.expr(a[0])) if a[0] > 0 else 'return', [], 'ret'
        if op == 0x24:
            ch = self.sc.t44[a[0] - 1][1] if 1 <= a[0] <= len(self.sc.t44) else []
            return 'menu %d [%s] -> v1' % (a[0], ' | '.join(c.decode('cp932', 'replace').strip('\u3000 ')
                                                          for c in ch)), [nxt], ''
        if op == 0x25:
            return 'builtin %s -> v1' % BUILTIN.get(a[0], a[0]), [nxt], ''
        if op == 0x2B:
            return 'nop', [nxt], ''
        if op == 0x2D:
            return 'entry', [nxt], ''
        if op == 0x2E:
            return 'end', [], 'end'
        if op == 0x2F:
            return 'op2F %d' % a[0], [nxt], ''
        if op == 0x30:
            return 'palette %d, pal#%d' % (a[0], a[1]), [nxt], ''
        if op == 0x31:
            return 'load buf%d, (%d,%d), %d, "%s"' % (a[0], a[1], a[2], a[3], a[4]), [nxt], ''
        if op == 0x32:
            return 'copy buf%d (%d,%d %dx%d) -> buf%d (%d,%d) fx %d' % tuple(a), [nxt], ''
        if op == 0x33:
            return 'op33 buf%d' % a[0], [nxt], ''
        if op == 0x34:
            return 'jr %+d  ; -> %d' % (a[0], nxt + a[0]), [nxt + a[0]], ''
        if op == 0x35:
            return 'music_stop', [nxt], ''
        if op == 0x36:
            return 'load slot(v1)', [nxt], ''
        if op == 0x37:
            return 'op37 %d' % a[0], [nxt], ''
        return 'op%02X %r' % (op, a), [nxt], ''

    def flow(self):
        """Reachable statements from the entry and the subroutine entries (call targets)."""
        entry = self.sc.h12
        seen, work, subs = set(), [entry], set()
        while work:
            k = work.pop()
            if k in seen or not 1 <= k <= self.n:
                continue
            seen.add(k)
            _, succ, kind = self.stmt(k)
            if kind == 'call':
                subs.add(succ[0])
            work += succ
        return seen, subs


def load_messages(txb_path):
    try:
        import txb  # noqa: F401
    except ImportError:
        return {}
    try:
        msgs = txb.messages(open(txb_path, 'rb').read())
        return {i: m[:40] for i, m in msgs.items()}
    except Exception:  # noqa: BLE001
        return {}


def main(a):
    if len(a) < 2:
        sys.exit(__doc__)
    sc = Scenario(open(a[1], 'rb').read())
    msgs = {}
    if '--txb' in a:
        msgs = load_messages(a[a.index('--txb') + 1])
    d = Dis(sc, msgs)
    seen, subs = d.flow()
    if '--graph' in a:
        print('entry %d; reachable %d of %d statements; %d subroutines: %s' % (
            sc.h12, len(seen), d.n, len(subs), sorted(subs)))
        un = [k for k in range(1, d.n + 1) if k not in seen]
        runs, s = [], None
        for k in un:
            if s is None or k != runs[-1][1] + 1:
                runs.append([k, k])
            else:
                runs[-1][1] = k
        print('unreachable runs:', ' '.join('%d-%d' % tuple(r) if r[0] != r[1] else str(r[0]) for r in runs))
        return
    targets = set()
    for k in range(1, d.n + 1):
        _, succ, kind = d.stmt(k)
        if len(succ) != 1 or succ[0] != k + 1:
            targets.update(succ)
    out = open(a[a.index('--out') + 1], 'w', encoding='utf-8') if '--out' in a else sys.stdout
    for k in range(1, d.n + 1):
        if k in subs:
            out.write('\n;---- sub_%d\n' % k)
        elif k in targets:
            out.write('L%d:\n' % k)
        txt, _, _ = d.stmt(k)
        out.write('%5d%s  %s\n' % (k, ' ' if k in seen else '!', txt))


if __name__ == '__main__':
    main(sys.argv)
