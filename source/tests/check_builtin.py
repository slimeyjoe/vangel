#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_builtin.py - the engine's built-in sequences against M.EXE's own.

usage: check_builtin.py TEST_BI PAK                 (with $EMU_PYTHON: unicorn)

The original runs under tests/textrig.py (the kanji ROM from the pack's fonts, INT 33h from
a script, its own VSYNC and INT 09h handlers) from the state after its start-up, statement 25h's
routines called directly (segment 0504): OPENING over va_opbac, with no input and with an input
at many points of it (keys, the left and the right button, ESC, the mouse closed, no free
timer); ENDING over va_12 (twice: its palette stays faded) and ENDING2 over va_12 / va_12e;
ANNOUNCE answered by keys and buttons, with the mouse closed and with the file missing; the
music mode played by keys and by the mouse, and without a driver. The music layer's entries
(04E4:0004, 0034, 00F0) are stand-ins that log their calls (the layer is check_snd's).

Time passes only where the original waits, as in the engine: at the end of a turn of a wait
loop that found nothing, the DAC load's wait for the retrace, and the VSYNC counter's spin
loops (FRAME_POINTS below); the drawing takes none. The engine (tests/test_bi.c) replays the
input as the original was given it. Both record, at every VSYNC at which it changed, page 0
(CRC-32 of its four planes) and the DAC; the pointer shown and hidden; the music calls; and at
the end the result flag, pages 0 and 1, buffer 12 and the DAC. The original's runs are kept
between runs (tests/refcache.py).
"""
import hashlib
import os
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import refcache  # noqa: E402
import scb       # noqa: E402

SCANS = {'return': 0x1C, 'space': 0x34, 'esc': 0x00, 'up': 0x3A, 'down': 0x3D, 'left_k': 0x3B,
         'a': 0x1D}

# the built-ins' wait loops: (address, predicate, the policy's name for it)
FRAME_POINTS = {
    (0x0504, 0x02DF): ('ax_not_1', 'wipe'),     # prologue_step: input_check found nothing
    (0x0504, 0x0516): ('ax_not_1', 'page'),     # op_pages: the page's 3 s, nothing
    (0x0504, 0x037D): ('zf', None),             # op_fade_c6: the counter still 0
    (0x0504, 0x06E3): ('zf', None),             # pal_dec_fade: the counter unchanged
    (0x0504, 0x082F): ('jl', None),             # staff_roll: fewer than 360
    (0x0504, 0x0867): ('jl', None),             # staff_roll: fewer than 120
    (0x0504, 0x0281): ('zf', 'any'),            # bi_wait_any: nothing
    (0x0504, 0x0A82): ('always', 'mus'),        # mus_loop: no key event
    (0x00DD, 0x01DF): ('zf', None),             # dac_set: the retrace has not started
    (0x00DD, 0x0510): ('jl', None),             # fx31_wait: the counter moved by less than 2
    (0x0315, 0x04B6): ('zf', None),             # pal_fade_in: the time unchanged
    (0x0315, 0x0688): ('zf', None),             # pal_fade_out: the same
}
DAC_WAIT = ((0x00DD, 0x01D5), (0x00DD, 0x01DB))   # dac_set's two loops
ENTRY = {1: (0x0504, 0x0295), 2: (0x0504, 0x0568), 3: (0x0504, 0x0114), 4: (0x0504, 0x088E),
         5: (0x0504, 0x05CA)}


def make_machine(fonts):
    import textrig
    import vmrig
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EFLAGS

    class BM(vmrig.stubbed(textrig.Machine)):
        def __init__(self):
            super().__init__(fonts)
            self.driver = 1
            self.policy = None
            self.sampling = False
            self._bp = {}
            for (s, o), (pred, kind) in FRAME_POINTS.items():
                lin = self.lin(self.seg(s), o)
                self._bp[lin] = (pred, kind)
                self.uc.hook_add(UC_HOOK_CODE, self._bi_point, begin=lin, end=lin)
            self._dac_lin = [self.lin(self.seg(s), o) for s, o in DAC_WAIT]
            for lin in self._dac_lin:
                self.uc.hook_add(UC_HOOK_CODE, self._dac_hook, begin=lin, end=lin)
            self._dac_phase, self._dac_f = 0, 0
            self.stub(0x04E4, 0x0004, self._mus_init)
            self.stub(0x04E4, 0x0034, self._mus_play)
            self.stub(0x04E4, 0x00F0, self._mus_fade)

        # ---- the music layer's stand-ins
        def _f(self):
            return self.frame - self.fbase

        def _mus_init(self, m, arg):
            self.log.append((self._f(), 'mus', 'init'))
            self.uc.reg_write(vmrig_ax(), self.driver)

        def _mus_play(self, m, arg):
            name = self.cstr(arg(1), arg(0)).decode('latin-1')
            self.log.append((self._f(), 'mus', 'play', name, arg(2)))
            self.uc.reg_write(vmrig_ax(), 1)

        def _mus_fade(self, m, arg):
            self.log.append((self._f(), 'mus', 'fade', arg(0)))
            self.uc.reg_write(vmrig_ax(), 1)

        # ---- dac_set: a VSYNC passes in its wait for the retrace's start
        def _dac_hook(self, uc, address, size, ud):
            if address == self._dac_lin[0]:
                self._dac_phase, self._dac_f = 0, self.frame
            else:
                self._dac_phase = 1

        def _in(self, uc, port, size, ud):
            if port == 0xA0 and self.sampling:
                if self._dac_phase == 1 and self.frame != self._dac_f:
                    return 0x24
                return 0x04
            return super()._in(uc, port, size, ud)

        # ---- the wait loops
        def _bi_point(self, uc, address, size, ud):
            if not self.sampling:           # the set-up: no time
                return
            if address == self._skip_once:
                self._skip_once = None
                return
            pred, kind = self._bp[address]
            fl = uc.reg_read(UC_X86_REG_EFLAGS)
            if pred == 'ax_not_1':
                go = uc.reg_read(vmrig_ax()) != 1
            elif pred == 'zf':
                go = bool(fl & 0x40)
            elif pred == 'jl':
                go = bool(fl & 0x80) != bool(fl & 0x800)
            else:
                go = True
            if not go:
                return
            if kind and self.policy:
                self.policy(self, kind)
            self._stop_why = address
            uc.emu_stop()

        # ---- what a VSYNC sees
        def page_crc0(self, page=0):
            self.sync_pages()
            c = 0
            for q in range(4):
                c = zlib.crc32(bytes(self.pages[page][q][:32000]), c)
            return c

        def buf12_crc(self):
            c = 0
            for s in self.mem_planes():
                c = zlib.crc32(self.mem(s, 0, 32000), c)
            return c

        def dac_hex(self):
            return ''.join('%x' % (self.dac[i][k] & 15) for k in range(3) for i in range(16))

        def _tick(self):
            super()._tick()
            if self.sampling:
                c, d = self.page_crc0(), self.dac_hex()
                if (c, d) != self._last:
                    self._last = (c, d)
                    self.log.append((self.frame - self.fbase, 'v', c, d))

        # ---- the set-up
        def pic(self, buf, x, y, flag, name):
            blk = bytearray(0x16)
            blk[0:len(name)] = name.encode()
            struct.pack_into('<hhhh', blk, 0x0E, flag, buf, x, y)
            self.poke(self.opblk, 0, blk)
            self.call(0x0315, 0x070D, [0, self.opblk])

        def pal(self, packed):
            if not hasattr(self, 'palblk'):
                self.palblk = self.alloc(64)
            self.poke(self.palblk, 0, packed)
            self.call(0x0315, 0x0176, [0, self.palblk, 0])

        def nofile(self):
            self.poke(self.ds, 0x0254, b'announce.xxx\x00')

        def builtin(self, n, sched, policy):
            self.begin(sched)
            self.policy = policy
            self._last = (self.page_crc0(), self.dac_hex())
            self.poke(self.seg(0x0BA1), 0, b'\x00')
            self.sampling = True
            self.run(*ENTRY[n])
            self.sampling = False
            self.policy = None
            v1 = 1 if self.mem(self.seg(0x0BA1), 0, 1)[0] == 1 else 0
            self.log.append((self.frame - self.fbase, 'end', v1, self.page_crc0(0),
                             self.page_crc0(1), self.buf12_crc(), self.dac_hex()))
            return self.log, self.applied

    return BM()


def vmrig_ax():
    from unicorn.x86_const import UC_X86_REG_AX
    return UC_X86_REG_AX


# ---- the player ----------------------------------------------------------------------------

def key(sched, f, name, hold):
    sched.setdefault(f, []).append(('scan', SCANS[name]))
    sched.setdefault(f + hold, []).append(('scan', SCANS[name] | 0x80))


def click(sched, f, x, y, b, hold):
    sched.setdefault(f, []).append(('mouse', x, y, b))
    sched.setdefault(f + hold, []).append(('mouse', x, y, 0))


class Script:
    """answers a wait of `kind` from a list of actions, one at a time: each is scheduled when
    the original waits with nothing pending; an action is (delay, [(dt, event)...])"""

    def __init__(self, kind, actions):
        self.kind = kind
        self.actions = list(actions)

    def __call__(self, m, kind):
        if kind != self.kind or not self.actions:
            return
        now = m.frame - m.fbase
        if any(f > now for f in m.sched):
            return
        delay, evs = self.actions.pop(0)
        for dt, ev in evs:
            m.sched.setdefault(now + delay + dt, []).append(ev)


def k(name, hold=2):
    return [(0, ('scan', SCANS[name])), (hold, ('scan', SCANS[name] | 0x80))]


def mouse(x, y, b=0, hold=0):
    if b and hold:
        return [(0, ('mouse', x, y, b)), (hold, ('mouse', x, y, 0))]
    return [(0, ('mouse', x, y, b))]


def runs(sc):
    """(name, setup, built-in, schedule, policy maker)"""
    def pal(n):
        p = sc.pal[n - 1]
        return 'pal ' + ''.join('%x' % c[i] for i in range(3) for c in p)

    op_scene = ['pic 10 0 0 0 va_opbac', pal(43)]
    out = [('opening', op_scene, 1, {}, None)]
    for f in (3, 40, 151, 333, 777, 1300, 1900, 2600, 3300, 4100):
        s = {}
        key(s, f, 'return', 2)
        out.append(('opening key %d' % f, op_scene, 1, s, None))
    s = {}
    click(s, 900, 100, 100, 1, 3)
    out.append(('opening left', op_scene, 1, s, None))
    s = {}
    click(s, 900, 100, 100, 2, 3)
    key(s, 2222, 'esc', 6)
    out.append(('opening right, esc', op_scene, 1, s, None))
    s = {}
    key(s, 1500, 'space', 1)
    out.append(('opening mouse closed', ['input 1'] + op_scene, 1, s, None))
    out.append(('opening no timer', ['input 3', 'fill'] + op_scene, 1, {}, None))
    s = {}
    key(s, 1200, 'return', 3)
    out.append(('opening no timer, key', op_scene, 1, s, None))

    end_scene = ['free', 'pic 10 0 0 0 va_12', 'pic 11 0 0 0 va_main', pal(18)]
    out.append(('ending', end_scene, 2, {}, None))
    s = {}
    key(s, 500, 'return', 3)
    out.append(('ending again', end_scene, 2, s, None))
    out.append(('ending2', ['pic 10 0 0 0 va_12', 'pic 10 32 303 0 va_12e', pal(18)], 5, {},
                None))

    an_scene = ['pic 10 0 0 0 va_title', pal(2)]
    out.append(('announce keys', an_scene, 3, {},
                lambda: Script('any', [(5, k('return')), (1, k('space', 5)), (30, k('a')),
                                       (2, k('return')), (2, k('return'))])))
    out.append(('announce buttons', an_scene, 3, {},
                lambda: Script('any', [(2, mouse(300, 200, 1, 4)), (9, mouse(10, 10, 2, 2)),
                                       (1, mouse(600, 390, 1, 1)), (3, mouse(5, 5, 2, 9)),
                                       (3, mouse(6, 5, 1, 2))])))
    out.append(('announce esc, mouse closed', ['input 1'] + an_scene, 3, {},
                lambda: Script('any', [(3, k('esc', 4)), (60, mouse(5, 5, 1, 3) + k('return')),
                                       (7, k('up')), (2, k('return')), (2, k('return'))])))
    out.append(('announce missing', ['input 3', 'nofile'] + an_scene, 3, {}, None))

    mus_scene = ['pic 10 0 0 0 va_title', pal(2)]
    keys = [(10, k('down')), (5, k('down')), (5, k('down')), (20, k('return')),
            (40, k('down')), (3, k('space')), (8, k('up')), (2, k('return', 7)),
            (30, k('return')), (4, k('a')), (4, k('left_k'))] + \
        [(2, k('up', 1)) for _ in range(6)] + [(5, k('return')), (50, k('esc', 3))]
    out.append(('music keys', mus_scene, 4, {}, lambda: Script('mus', keys)))
    mice = [(5, mouse(200, 100)), (5, mouse(200, 49)), (5, mouse(200, 48)),
            (5, mouse(200, 64)), (5, mouse(200, 65)), (3, mouse(330, 120, 1, 2)),
            (20, mouse(330, 300)), (2, mouse(330, 330, 1, 6)), (40, mouse(330, 30, 1, 1)),
            (10, k('down')), (5, mouse(331, 30)), (6, k('space')), (5, mouse(400, 300, 2, 2))]
    out.append(('music mouse', mus_scene, 4, {}, lambda: Script('mus', mice)))
    down = [(1, k('down', 1)) for _ in range(20)] + [(3, k('return')), (9, k('esc', 1))]
    out.append(('music bottom, mouse closed', ['input 1'] + mus_scene, 4, {},
                lambda: Script('mus', down)))
    out.append(('music no driver', ['input 3', 'driver 0'] + mus_scene, 4, {}, None))
    out.append(('music no driver, remembered', ['driver 1'], 4, {}, None))
    return out


def original(pak, sc):
    import textrig
    m = make_machine(textrig.Fonts(pak))
    m.start(3)
    res = []
    held = []
    for name, setup, n, sched, pol in runs(sc):
        for c in setup:
            w = c.split()
            if w[0] == 'pic':
                m.pic(int(w[1]), int(w[2]), int(w[3]), int(w[4]), w[5])
            elif w[0] == 'pal':
                m.pal(bytes(int(ch, 16) for ch in w[1]))
            elif w[0] == 'input':
                m.input_mask(int(w[1]))
            elif w[0] == 'fill':
                held = [m.call(0x0752, 0x0026, [1000, 0])[0] for _ in range(16)]
            elif w[0] == 'free':
                for h in held:
                    m.call(0x0752, 0x0043, [h])
                held = []
            elif w[0] == 'driver':
                m.driver = int(w[1])
            elif w[0] == 'nofile':
                m.nofile()
        log, used = m.builtin(n, sched, pol() if pol else None)
        res.append({'name': name, 'log': [list(x) for x in log],
                    'sched': [[f, list(ev)] for f, ev in used]})
    return res


def norm(e):
    """a record as both sides print it"""
    if e[1] == 'ptr':
        return [e[0], 'ptr', e[2]]
    return list(e)


def engine(test, pak, sc, ref):
    cmds = []
    for (name, setup, n, _s, _p), r in zip(runs(sc), ref):
        cmds += setup
        for f, ev in r['sched']:
            if ev[0] == 'scan':
                cmds.append('ev %d scan %02x' % (f, ev[1]))
            else:
                cmds.append('ev %d mouse %d %d %d' % (f, ev[1], ev[2], ev[3]))
        cmds.append('bi %d' % n)
    try:
        # a backstop only: a run that diverged can wait for an input that never comes
        res = subprocess.run([test, pak, '3'], input='\n'.join(cmds) + '\n',
                             capture_output=True, text=True, check=False, timeout=1800)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
        print(out[-1500:])
        sys.exit('check_builtin: test_bi did not end (a run diverged and waits for input)')
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_builtin: test_bi failed (exit %d)' % res.returncode)
    out, log = [], []
    for ln in res.stdout.split('\n'):
        if not ln:
            continue
        if ln == 'end':
            out.append(log)
            log = []
            continue
        w = ln.split()
        f = int(w[0])
        if w[1] == 'v':
            log.append([f, 'v', int(w[2]), w[3]])
        elif w[1] == 'ptr':
            log.append([f, 'ptr', int(w[2])])
        elif w[1] == 'mus':
            log.append([f, 'mus', w[2]] + [int(x) if x.lstrip('-').isdigit() else x
                                           for x in w[3:]])
        elif w[1] == 'end':
            log.append([f, 'end', int(w[2]), int(w[3]), int(w[4]), int(w[5]), w[6]])
        else:
            log.append([f] + w[1:])
    return out


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    test, pak = argv[1], argv[2]
    sc = scb.Scenario(open(os.path.join(refcache.ORIG, 'CMD00.SCB'), 'rb').read())
    import textrig
    fonts = textrig.Fonts(pak)
    fh = hashlib.sha256(fonts.raw['font16'] + fonts.raw['font8']).hexdigest()
    ref, hit = refcache.get('builtin', ['check_builtin.py', 'textrig.py', 'vmrig.py'], None,
                            {'fonts': fh, 'version': 2}, lambda: original(pak, sc))
    got = engine(test, pak, sc, ref)
    bad = frames = 0
    for i, r in enumerate(ref):
        want = [norm(e) for e in r['log']]
        g = got[i] if i < len(got) else []
        frames += want[-1][0] if want else 0
        if g != want:
            bad += 1
            if bad <= 5:
                print('%s: differs' % r['name'])
                for j in range(max(len(want), len(g))):
                    a = g[j] if j < len(g) else None
                    b = want[j] if j < len(want) else None
                    if a != b:
                        print('  record %d: engine %s\n             original %s' % (j, a, b))
                        break
    print('check_builtin: %d runs, %d frames: %s (reference %s)' % (
        len(ref), frames, 'identical to the original, frame by frame' if not bad else
        '%d runs differ' % bad, 'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
