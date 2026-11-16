# SPDX-License-Identifier: GPL-3.0-or-later
"""vmrig.py - M.EXE's scenario loader, expressions, saves and interpreter under emulation, for
the checks of M3 (check_scb, check_expr, check_save, check_vmstep).

    o = Orig(data)                 the original's start-up to main, then fopen + scb_load
                                   (063C:00E8) of `data` as main does it; o.rc: 0, or the
                                   exit code (2, 3), or 'hang' (no end in max_insns)
    o.dump_scb()                   the tables as test_vm.c's dump_scb prints them
    o.var(i) / o.set_var(i, t, v)  variable table entry i (0BA1:0068)
    o.set_node(i, form, k, a, b)   expression node i (0BA1:0088; 12-byte records)
    o.expr(n)                      expr_eval (0000:0089): ('expr', v) or ('exit', code); after
                                   an exit the machine is started and loaded again
    o.state() / o.set_state(...)   pc DS:005A, depth DS:005C, the stack 0A9F:0000
    o.save(k) / o.load(k)          save_slot (001E:042C) / load_slot (001E:0577), game.dat
                                   in the emulated DOS's memory (o.m.written)

The original's memory is read the way re-tools/scb_verify.py reads it; the records' layouts
are those of its statement loaders (063C), in scenario-format.md §6.
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))

from mcall import M, Exit, SENTINEL  # noqa: E402
from unicorn.x86_const import UC_X86_REG_CS, UC_X86_REG_IP  # noqa: E402

G = 0x0BA1
STACK = 0x0A9F
NAME = 'scenario.scb'


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def hexs(b):
    return b.hex() if b else '-'


class Orig:
    def __init__(self, data, max_insns=20_000_000, machine=M, **kw):
        self._args, self._kw = (data, max_insns, machine), kw
        self.m = m = machine(**kw)
        m.max_insns = max_insns
        self.g = m.seg(G)
        m.written[NAME] = bytearray(data)
        buf = m.alloc(64)
        name = NAME.encode() + b'\0'
        m.poke(buf, 0, name + b'rb\0')
        ax, dx = m.call(0x886, 0x39A, [0, buf, len(name), buf])
        m.poke(self.g, 0x64, struct.pack('<HH', ax, dx))
        self.rc = self.call(0x63C, 0xE8, again=False)
        if self.rc == ('ret', 1):
            self.rc = 0
        elif self.rc == ('ret', 0):
            self.rc = 2
        elif self.rc[0] == 'exit':
            self.rc = self.rc[1]
        else:
            self.rc = 'hang'

    def call(self, seg, off, args=(), again=True):
        """('ret', ax) or ('exit', code) or ('hang',); after an exit, with `again`, the
        machine is started and loaded again"""
        m = self.m
        try:
            ax, _ = m.call(seg, off, args)
        except Exit as e:
            # after the C library's exit() the machine is not what it was (vectors put
            # back, streams closed; unicorn delivers no second divide error): the next call
            # runs on a machine started and loaded again
            if again:
                self.__init__(*self._args, **self._kw)
            return ('exit', e.args[0])
        if m.uc.reg_read(UC_X86_REG_CS) * 16 + m.uc.reg_read(UC_X86_REG_IP) != SENTINEL * 16:
            return ('hang',)
        return ('ret', ax)

    # ---- the tables
    def word(self, off):
        return self.m.word(self.g, off)

    def table(self, off, i):
        s, o = self.m.far(self.g, off)
        return self.m.far(s, o + 4 * i)

    def count(self, off):
        return s16(self.word(off))

    def dump_scb(self):
        m, out = self.m, []
        text = m.cstr(self.g, 0x16, 64)
        out.append('h %d %d %d %d %d %d %d %d %d %d %d %d %s' % (
            self.word(2), self.word(0x10), self.count(0x0E), self.count(0x44),
            self.count(0x0C), self.count(0x52), self.count(0x0A), self.count(0x42),
            self.count(0xD4), self.count(0x04),
            self.word(6) | self.word(8) << 16, self.word(0x70) | self.word(0x72) << 16,
            hexs(text)))
        for i in range(1, self.count(0x42) + 1):
            out.append('v %d %d %d' % ((i,) + self.var(i)))
        for i in range(1, self.count(0x44) + 1):
            s, o = self.table(0x12, i)
            n = m.word(s, o)
            items = [hexs(m.cstr(*m.far(s, o + 2 + 4 * k), n=1024)) for k in range(n)]
            out.append(' '.join(['m %d %d' % (i, n)] + items))
        for i in range(1, self.count(0x0C) + 1):
            s, o = self.table(0x88, i)
            r = struct.unpack('<6H', m.mem(s, o, 12))
            if r[0] == 0xA:
                out.append('e %d 0 %d %d %d' % (i, s16(r[1]), s16(r[2]), s16(r[3])))
            else:
                out.append('e %d 1 %d %d' % (i, s16(r[4]), s16(r[5])))
        pals = {}
        for i in range(1, self.count(0x0A) + 1):
            s, o = self.table(0x84, i)
            pals[(s, o)] = i
            out.append('p %d %s' % (i, ''.join('%x' % (b & 15) for b in m.mem(s, o, 48))))
        for i in range(1, self.count(0x0E) + 1):
            s, o = self.table(0xD0, i)
            op = m.word(s, o)

            def w(k):
                return s16(m.word(s, o + 2 + 2 * k))
            if op in (0x15, 0x1A):
                a = [w(0), w(1)]
            elif op in (0x19, 0x1C, 0x21, 0x22, 0x23, 0x24, 0x25, 0x2F, 0x33, 0x34, 0x37):
                a = [w(0)]
            elif op == 0x1B:
                a = [w(10)]
            elif op == 0x1E:
                a = [w(1), w(0)]
            elif op == 0x1F:
                a = [w(2), w(0), w(1)]
            elif op == 0x20:
                n = w(1)
                a = ['n%d' % n, w(0), w(34)]
                for k in range(n):
                    a += [w(2 + k), w(18 + k)]
            elif op == 0x30:
                ptr = (m.word(s, o + 4), m.word(s, o + 2))
                a = [w(2), 0 if ptr == (0, 0) else pals.get(ptr, 'x')]
            elif op == 0x31:
                a = [w(8), w(9), w(10), w(7)]
            elif op == 0x32:
                a = [w(k) for k in range(9)]
            else:
                a = []
            line = 's %d %02x' % (i, op) + ''.join(' %s' % x for x in a)
            if op in (0x31, 0x1B):
                line += ' ' + hexs(m.cstr(s, o + 2, 64))
            out.append(line)
        return out

    # ---- the interpreter's state
    def var(self, i):
        s, o = self.table(0x68, i)
        return s16(self.m.word(s, o)), s16(self.m.word(s, o + 2))

    def set_var(self, i, t, v):
        s, o = self.table(0x68, i)
        self.m.poke(s, o, struct.pack('<hh', t, v))

    def set_node(self, i, form, k, a, b):
        s, o = self.table(0x88, i)
        if form == 0:
            rec = struct.pack('<6h', 0xA, k, a, b, 0, 0)
        else:
            rec = struct.pack('<6h', 0xB, 0, 0, 0, k, a)
        self.m.poke(s, o, rec)

    def expr(self, n):
        r = self.call(0x0000, 0x0089, [n & 0xFFFF])
        return ('expr', s16(r[1])) if r[0] == 'ret' else r

    def state(self):
        m, ds = self.m, self.m.ds
        stack = struct.unpack('<32H', m.mem(m.seg(STACK), 0, 64))
        nv = self.count(0x42)
        return (m.word(ds, 0x5A), s16(m.word(ds, 0x5C)), list(stack),
                [self.var(i) for i in range(nv + 1)])

    def set_state(self, pc, depth, stack):
        m, ds = self.m, self.m.ds
        m.poke(ds, 0x5A, struct.pack('<H', pc & 0xFFFF))
        m.poke(ds, 0x5C, struct.pack('<H', depth & 0xFFFF))
        m.poke(m.seg(STACK), 0, struct.pack('<32H', *[x & 0xFFFF for x in stack]))

    def save(self, k):
        return self.call(0x001E, 0x042C, [k])

    def load(self, k):
        return self.call(0x001E, 0x0577, [k])

    def game_dat(self):
        d = self.m.written.get('game.dat')
        return None if d is None else bytes(d)

    def set_game_dat(self, data):
        if data is None:
            self.m.written.pop('game.dat', None)
        else:
            self.m.written['game.dat'] = bytearray(data)


def state_line(st):
    pc, depth, stack, vars_ = st
    return 'state %d %d %s %s' % (pc, depth, ' '.join(str(x) for x in stack),
                                  ' '.join('%d %d' % tv for tv in vars_))


# ---- the interpreter with its subsystems stood in for (check_vmstep) ------------------------

def stubbed(base):
    """`base` (mcall.M, m286.TM) whose far routines can be replaced by Python: stub(seg, off,
    fn) writes INT n; RETF at the routine's entry, and fn(m, args) runs in its place (args:
    the caller's words on the stack, a function returning word k); fn may set AX/DX."""
    from mcall import Exit as _Exit
    from unicorn.x86_const import UC_X86_REG_SS, UC_X86_REG_SP

    class S(base):
        def __init__(self, *a, **kw):
            self.handlers = {}
            self.excl = set()
            self.excl_ret = None
            super().__init__(*a, **kw)

        def stub(self, seg, off, fn):
            n = 0xC0 + len(self.handlers)
            self.handlers[n] = fn
            lin = self.lin(self.seg(seg), off)
            self.uc.mem_write(lin, bytes([0xCD, n, 0xCB]))
            self.excl.add(lin)

        def exclude(self, seg, off):
            """with time (m286): the routine's clocks, from its entry to its return, are not
            counted (the stand-ins are excluded so)"""
            self.excl.add(self.lin(self.seg(seg), off))

        def _clock(self, uc, address, size, ud):
            if self.excl_ret is not None:
                if address != self.excl_ret:
                    return
                self.excl_ret = None
            elif address in self.excl:
                ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)
                ip, cs = struct.unpack('<HH', bytes(uc.mem_read(ss * 16 + sp, 4)))
                self.excl_ret = cs * 16 + ip
                return
            super()._clock(uc, address, size, ud)

        def _stub(self, uc, address, size, ud):
            n = address - 0xF100 * 16
            fn = self.handlers.get(n)
            if fn is None:
                return super()._stub(uc, address, size, ud)
            ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)

            def arg(k):
                return struct.unpack('<H', bytes(uc.mem_read(ss * 16 + sp + 10 + 2 * k, 2)))[0]
            try:
                fn(self, arg)
            except _Exit as e:
                self._exc = e
                uc.emu_stop()
            except Exception as e:          # noqa: BLE001 - raised again by mcall's _run_to
                self._exc = e
                uc.emu_stop()
    return S


class Budget(Exception):
    """the route's answers or statements ran out"""


class VMOrig(Orig):
    """the original's vm_step with the subsystems of tests/test_vm.c's stand-ins replaced;
    `ask(kind, info)` decides each answer (and may raise Budget); every call and statement is
    logged in self.log in test_vm.c's format, the answers in self.answers"""

    MENU_DRAW, MENU_LOOP = (0x0315, 0x0C4F), (0x001E, 0x0B2B)
    BUILTINS = [(0x0504, 0x0004), (0x0504, 0x0295), (0x0504, 0x0568), (0x0504, 0x0114),
                (0x0504, 0x088E), (0x0504, 0x05CA)]

    def __init__(self, data, ask, machine=None, **kw):
        from mcall import M as _M
        self.ask = ask
        super().__init__(data, machine=stubbed(machine or _M), **kw)
        self.log = []
        self.answers = []
        self.cut = 0
        m = self.m
        S = m.stub
        S(0x0752, 0x0026, self._timer_start)
        S(0x0752, 0x0076, self._timer_done)
        S(0x0752, 0x0043, lambda m, a: None)                       # timer_free
        S(0x043A, 0x01DA, self._input_poll)
        S(0x043A, 0x0236, lambda m, a: None)                       # input_wait_release
        S(0x0315, 0x07F5, lambda m, a: self.call_log('restore'))
        S(0x0315, 0x07FC, self._msg)
        S(0x0315, 0x04E2, lambda m, a: self.call_log('fadeout %d %d' % (s16(a(0)), s16(a(1)))))
        S(0x04E4, 0x0034, self._play)
        S(0x04E4, 0x01D8, self._musstate)
        S(0x04E4, 0x00F0, lambda m, a: self.call_log('musfade %d' % s16(a(0))))
        S(0x04E4, 0x01E9, self._measure)
        S(*self.MENU_DRAW, self._menu_draw)
        S(*self.MENU_LOOP, self._menu_loop)
        S(0x0315, 0x0EA8, lambda m, a: None)                       # menu_erase
        for k, (sg, of) in enumerate(self.BUILTINS):
            S(sg, of, lambda m, a, k=k: self._builtin(k))
        S(0x0315, 0x06C2, lambda m, a: self.call_log('flash %d' % s16(a(0))))
        S(0x0315, 0x0176, self._palette)
        S(0x0315, 0x070D, self._pic)
        S(0x0315, 0x07CB, self._copy)
        S(0x0315, 0x01BE, lambda m, a: self.call_log('clear %d' % s16(a(0))))
        S(0x043A, 0x02B5, lambda m, a: self.call_log('lock %d %d' % (s16(a(0)), s16(a(1)))))
        # their own: the file's time is not the interpreter's
        if hasattr(m, 'exclude'):
            m.exclude(0x001E, 0x042C)               # save_slot
            m.exclude(0x001E, 0x0577)               # load_slot

    # ---- helpers
    def call_log(self, s):
        self.log.append('c ' + s)

    def answer(self, kind, info=None):
        v = self.ask(kind, info)
        self.answers.append(v)
        return v

    def cur(self):
        """(statement number, opcode, word getter) of the statement being run"""
        m = self.m
        pc = m.word(m.ds, 0x5A) - 1
        s, o = self.table(0xD0, pc)
        return pc, m.word(s, o), (lambda k: s16(m.word(s, o + 2 + 2 * k)))

    def ret(self, ax, dx=0):
        from unicorn.x86_const import UC_X86_REG_AX, UC_X86_REG_DX
        self.m.uc.reg_write(UC_X86_REG_AX, ax & 0xFFFF)
        self.m.uc.reg_write(UC_X86_REG_DX, dx & 0xFFFF)

    def set_flag(self, v):
        self.m.poke(self.g, 0, bytes([v & 0xFF]))

    # ---- the stand-ins
    def _timer_start(self, m, a):
        pc, op, w = self.cur()
        self.call_log('wait %d %d' % (w(0), w(1)))
        a = self.answer('wait', (pc, w(0), w(1)))
        self.cut = a == 1
        self.ret(0 if a < 0 else 1)

    def _timer_done(self, m, a):
        self.ret(0 if self.cut else 1)

    def _input_poll(self, m, a):
        pc, op, w = self.cur()
        if op == 0x16:
            self.call_log('input')
        rec = bytearray(26)
        rec[0x0A] = 1                               # a key event
        m.poke(a(1), a(0), rec)
        self.cut = 0
        self.ret(1)

    def _msg(self, m, a):
        pc, op, w = self.cur()
        self.call_log('msg %d' % w(0))
        self.set_flag(self.answer('msg', (pc, w(0))))

    def _play(self, m, a):
        name = m.cstr(a(1), a(0), 64)
        self.call_log('play %d %s' % (s16(a(2)), hexs(name)))

    def _musstate(self, m, a):
        pc, op, w = self.cur()
        self.call_log('musstate')
        self.ret(self.answer('musstate', pc))

    def _measure(self, m, a):
        pc, op, w = self.cur()
        self.call_log('measure')
        self.ret(self.answer('measure', pc))

    def _menu_draw(self, m, a):
        n = m.word(a(1), a(0))
        self.call_log('menu %d' % n)
        m.poke(a(3), a(2), struct.pack('<H', n))
        self.menu_n = n

    def _menu_loop(self, m, a):
        pc, op, w = self.cur()
        v = self.answer('menu', (pc, w(0), self.menu_n))
        m.poke(a(1), a(0) + 2, struct.pack('<H', (v - 1) & 0xFFFF))

    def _builtin(self, k):
        pc, op, w = self.cur()
        self.call_log('builtin %d' % k)
        self.set_flag(self.answer('builtin', (pc, k)))

    def _palette(self, m, a):
        sg, of = a(1), a(0)
        pal = '-' if (sg, of) == (0, 0) else ''.join('%x' % (b & 15) for b in m.mem(sg, of, 48))
        self.call_log('palette %d %s' % (s16(a(2)), pal))

    def _pic(self, m, a):
        rec = m.mem(a(1), a(0), 0x16)
        flag, buf, x, y = struct.unpack_from('<4h', rec, 0x0E)
        name = rec[:0x0E]
        name = name[:name.index(0)] if 0 in name else name
        self.call_log('pic %d %d %d %d %s' % (buf, x, y, flag, hexs(name)))

    def _copy(self, m, a):
        v = struct.unpack('<9h', m.mem(a(1), a(0), 18))
        self.call_log('copy ' + ' '.join(str(x) for x in v))

    # ---- running
    def step(self):
        """vm_step (001E:0133) once; the statement's line in self.log; 0 after 2Eh or an
        exit (self.exit), else 1"""
        m = self.m
        pc0 = m.word(m.ds, 0x5A)
        s, o = self.table(0xD0, pc0)
        op = m.word(s, o)
        clk0 = getattr(m, 'total', 0)
        m.excl_ret = None
        try:
            r = m.call(0x001E, 0x0133)[0]
        except Exit as e:
            self.log.append('exit %d' % e.args[0])
            return 0
        pc, depth, stack, vars_ = self.state()
        self.log.append('x %d %02x %d %d %d%s |%s' % (
            pc0, op, pc, depth, getattr(m, 'total', 0) - clk0,
            ''.join(' %d' % x for x in stack[:max(0, min(depth, 32))]),
            ''.join(' %d:%d' % tv for tv in vars_)))
        return r
