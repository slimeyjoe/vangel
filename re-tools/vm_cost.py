#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""vm_cost.py - what the interpreter spends on a statement, on the reference machine.

    vm_cost.py consts [-o FILE]     the engine's clock constants (source/engine/vm/vm_clk.h)
    vm_cost.py show                 the same, printed

The unit is the 80286 clock of re-tools/m286.py. The original's vm_step (001E:0133) runs one
statement under m286 with the subsystems replaced by stand-ins whose time is not counted
(source/tests/vmrig.py: the pictures, the palette, the window, the music, the waits' timer and
input calls, the menus' drawing and loop, the built-in sequences; save_slot and load_slot,
whose time is the file's). What is left is the interpreter's: the fetch, the dispatch, the
handler's own instructions on the path it took, and expr_eval.

Expression nodes are measured alone: expr_eval of a leaf, and of an operator over two literal
leaves less the leaves. A statement path is measured on a statement of the scenario whose
record is set to take it (its expression a literal leaf), less that leaf. Paths with a loop
(switch: one turn per case compared) give their base and the turn. tests/check_vmstep.py
compares the engine's charge with the original's clocks on whole routes, so a wrong constant
shows there.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'source', 'tests'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))

PC98 = os.path.join(ROOT, 'resources', 'original', 'pc98', 'CMD00.SCB')


class Rig:
    def __init__(self, files):
        from m286 import TM
        from vmrig import VMOrig
        from scb import Scenario
        self.sc = Scenario(open(PC98, 'rb').read())
        self.queue = []
        self.o = VMOrig(open(PC98, 'rb').read(), lambda kind, info: self.queue.pop(0),
                        machine=TM, files=files)
        self.m = self.o.m
        self.m.cpf = 0                          # no frames: only the clocks

    def first(self, op):
        for i, (_, o, _) in enumerate(self.sc.stmts, 1):
            if o == op:
                return i
        raise KeyError(op)

    def rec(self, n):
        return self.o.table(0xD0, n)

    def poke_w(self, n, k, v):
        s, o = self.rec(n)
        self.m.poke(s, o + 2 + 2 * k, struct.pack('<h', v))

    def eval_clk(self, n):
        t = self.m.total
        r = self.o.expr(n)
        assert r[0] == 'expr', r
        return self.m.total - t

    def step_clk(self, n, answers=(), depth=2):
        """vm_step of statement n; its clocks"""
        o, m = self.o, self.m
        o.set_state(n, depth, [1000 + k for k in range(32)])
        self.queue = list(answers)
        t = m.total
        m.excl_ret = None
        m.call(0x001E, 0x0133)
        assert not self.queue, self.queue
        return m.total - t


def measure(files):
    r = Rig(files)
    o = r.o
    c = {}
    # ---- expressions: node 1 the expression, 2 and 3 its leaves
    lit = lambda i, v: o.set_node(i, 1, 5, v, 0)  # noqa: E731
    o.set_var(5, 6, 3)
    for name, kind, v in (('LIT_INT', 5, 7), ('LIT_BOOL', 9, 2), ('VAR_INT', 6, 5),
                          ('VAR_BOOL', 10, 5)):
        o.set_node(1, 1, kind, v, 0)
        c['LEAF_' + name] = r.eval_clk(1)
    L = c['LEAF_LIT_INT']
    for name, op in (('NEG', 3), ('NOT', 4)):
        o.set_node(1, 0, op, 2, 0)
        lit(2, 5)
        c['EXPR_' + name] = r.eval_clk(1) - L
    for name, op, a, b in (('ADD', 5, 3, 4), ('SUB', 6, 3, 4), ('MUL', 7, 3, 4),
                           ('DIV', 8, 9, 4), ('MOD', 9, 9, 4), ('AND', 10, 3, 6),
                           ('OR', 11, 3, 6), ('XOR', 12, 3, 6),
                           ('EQ_T', 13, 3, 3), ('EQ_F', 13, 3, 4), ('NE_T', 14, 3, 4),
                           ('NE_F', 14, 3, 3), ('GT_T', 15, 4, 3), ('GT_F', 15, 3, 3),
                           ('LT_T', 16, 3, 4), ('LT_F', 16, 3, 3)):
        o.set_node(1, 0, op, 2, 3)
        lit(2, a)
        lit(3, b)
        c['EXPR_' + name] = r.eval_clk(1) - 2 * L
    # ---- statements; node 1 a literal leaf the records point at
    spare = [i for i, (_, op, _) in enumerate(r.sc.stmts, 1) if op == 0x2B][1:]

    def one(op):
        """a statement of opcode op; one made from a 2Bh record (no operands) for 17h and
        18h, which the scenario does not have"""
        try:
            return r.first(op)
        except KeyError:
            n = spare.pop()
            s, off = r.rec(n)
            r.m.poke(s, off, struct.pack('<H', op))
            return n

    def with_lit(n, k, v):
        o.set_node(1, 1, 5, v, 0)
        r.poke_w(n, k, 1)
    n = one(0x15)
    r.poke_w(n, 0, 0)
    r.poke_w(n, 1, 0)
    c['15_ZERO'] = r.step_clk(n)
    r.poke_w(n, 0, 50)
    c['15_NOTIMER'] = r.step_clk(n, [-1])
    c['15_DONE'] = r.step_clk(n, [0])
    r.poke_w(n, 1, 1)
    c['15_CUT'] = r.step_clk(n, [1])
    c['16'] = r.step_clk(one(0x16))
    for op in (0x18, 0x1A, 0x1B, 0x21, 0x2F, 0x31, 0x32, 0x33, 0x34):
        c['%02X' % op] = r.step_clk(one(op))
    c['19_0'] = r.step_clk(one(0x19), [0])
    c['19_1'] = r.step_clk(one(0x19), [1])
    c['1C_IDLE'] = r.step_clk(one(0x1C), [0])
    c['1C_PLAY'] = r.step_clk(one(0x1C), [10])
    for op, name in ((0x1D, '1D'), (0x36, '36')):
        n = one(op)
        o.set_var(1, 6, 0)
        c[name + '_OUT'] = r.step_clk(n)
        o.set_var(1, 6, 1)
        c[name + ('_SAVE' if op == 0x1D else '_LOAD')] = r.step_clk(n)
    n = one(0x1E)
    with_lit(n, 1, 9)
    s, off = r.rec(n)
    var = r.m.word(s, off + 2)
    o.set_var(var, 6, 0)
    c['1E_INT'] = r.step_clk(n) - L
    o.set_var(var, 10, 0)
    c['1E_BOOL'] = r.step_clk(n) - L
    n = one(0x1F)
    with_lit(n, 2, 1)
    c['1F_T'] = r.step_clk(n) - L
    with_lit(n, 2, 0)
    c['1F_F'] = r.step_clk(n) - L
    n = one(0x20)
    s, off = r.rec(n)
    ncase = r.m.word(s, off + 4)
    vals = [struct.unpack('<h', r.m.mem(s, off + 6 + 2 * k, 2))[0] for k in range(ncase)]
    with_lit(n, 0, vals[0])
    c['20_CASE'] = r.step_clk(n) - L
    with_lit(n, 0, vals[1])
    c['20_PER'] = r.step_clk(n) - L - c['20_CASE']
    with_lit(n, 0, max(vals) + 100)
    c['20_DEF'] = r.step_clk(n) - L - ncase * c['20_PER']
    c['22'] = r.step_clk(one(0x22), depth=0)
    n = one(0x23)
    with_lit(n, 0, 4)
    c['23_EXPR'] = r.step_clk(n) - L
    r.poke_w(n, 0, 0)
    c['23_NONE'] = r.step_clk(n)
    n = one(0x24)
    r.m.poke(r.m.ds, 0xC0, b'\0\0\0\0')
    c['24_NEW'] = r.step_clk(n, [1])
    c['24_SAME'] = r.step_clk(n, [1])
    n = one(0x25)
    c['25_0'] = r.step_clk(n, [0])
    c['25_1'] = r.step_clk(n, [1])
    r.poke_w(n, 0, 6)
    c['25_NULL'] = r.step_clk(n)
    for op, name in ((0x2B, '2B'), (0x30, '30'), (0x35, '35')):
        c[name] = r.step_clk(one(op), [0] if op == 0x35 else [])
    n = one(0x2E)
    c['2E'] = r.step_clk(n)
    n = one(0x37)
    r.poke_w(n, 0, 0)
    c['37_0'] = r.step_clk(n)
    r.poke_w(n, 0, 1)
    c['37_1'] = r.step_clk(n)
    c['17'] = r.step_clk(one(0x17))
    return c


ORDER = ['LEAF_LIT_INT', 'LEAF_LIT_BOOL', 'LEAF_VAR_INT', 'LEAF_VAR_BOOL', 'EXPR_NEG',
         'EXPR_NOT', 'EXPR_ADD', 'EXPR_SUB', 'EXPR_MUL', 'EXPR_DIV', 'EXPR_MOD', 'EXPR_AND',
         'EXPR_OR', 'EXPR_XOR', 'EXPR_EQ_T', 'EXPR_EQ_F', 'EXPR_NE_T', 'EXPR_NE_F', 'EXPR_GT_T',
         'EXPR_GT_F', 'EXPR_LT_T', 'EXPR_LT_F',
         '15_ZERO', '15_NOTIMER', '15_DONE', '15_CUT', '16', '17', '18', '19_0', '19_1', '1A',
         '1B', '1C_IDLE', '1C_PLAY', '1D_OUT', '1D_SAVE', '1E_INT', '1E_BOOL', '1F_T', '1F_F',
         '20_CASE', '20_DEF', '20_PER', '21', '22', '23_EXPR', '23_NONE', '24_NEW', '24_SAME',
         '25_0', '25_1', '25_NULL', '2B', '2E', '2F', '30', '31', '32', '33', '34', '35',
         '36_OUT', '36_LOAD', '37_0', '37_1']


def consts(c, out):
    w = out.write
    w('/* SPDX-License-Identifier: GPL-3.0-or-later */\n')
    w('/* Made by re-tools/vm_cost.py consts: what the original\'s interpreter spends, in 80286\n'
      ' * clocks (re-tools/m286.py), on an expression node (its expr_eval from entry to return)\n'
      ' * and on a statement by the path it takes (vm_step from entry to return, less the\n'
      ' * subsystems it calls and expr_eval). _PER: a switch\'s turn per case compared. */\n')
    w('#ifndef VG_VM_VM_CLK_H\n#define VG_VM_VM_CLK_H\n\n')
    for k in ORDER:
        if k == '15_ZERO':
            w('\n')
        w('#define VG_CLK_%-15s %d\n' % (k, c[k]))
    w('\n/* expr_leaf\'s paths by the kind\'s bits */\n'
      'static inline unsigned vg_clk_leaf(int k)\n{\n'
      '    if ((k & 1) && (k & 4)) return VG_CLK_LEAF_LIT_INT;\n'
      '    if ((k & 1) && (k & 8)) return VG_CLK_LEAF_LIT_BOOL;\n'
      '    if ((k & 2) && (k & 4)) return VG_CLK_LEAF_VAR_INT;\n'
      '    return VG_CLK_LEAF_VAR_BOOL;\n}\n\n#endif\n')


def main(argv):
    import tempfile
    if len(argv) < 2 or argv[1] not in ('consts', 'show'):
        sys.exit(__doc__)
    with tempfile.TemporaryDirectory() as tmp:
        c = measure(tmp)
    if argv[1] == 'show':
        for k in ORDER:
            print('%-15s %d' % (k, c[k]))
        return 0
    out = argv[argv.index('-o') + 1] if '-o' in argv else None
    if out:
        with open(out, 'w') as f:
            consts(c, f)
    else:
        consts(c, sys.stdout)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
