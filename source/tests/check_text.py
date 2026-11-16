#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_text.py - the engine's statement 19h against M.EXE's own: every message, every page.

usage: check_text.py TEST_TEXT PAK                 (with $EMU_PYTHON: unicorn)

The original runs under tests/textrig.py from the state after its start-up (scenario, text,
timer, input with keyboard and mouse, graphics) over the first scene (va_main, va_mw01).
Every one of the 213 messages is shown by statement 19h (001E:0965), and the player answers
each page a while after it appears: RETURN, SPACE, SHIFT, a letter, ESC (which counts when it
is let go), a left click held some frames (the release step waits for it), a right click (no
effect) followed by RETURN, pointer moves; timed pages are left to run out. Then the timed
messages again with an input cutting one of their pages short (v1 = 1), messages with all 16
timer slots taken (the icon stays, the timed pages do not wait), and messages with the mouse
not opened. The input of every frame is recorded as it was given and replayed into the engine
(tests/test_text.c); both record every page shown, the icon going on and off, the text erased
and the pointer shown and hidden, at the same frame and with the same pixels (CRC-32 of the
window, of page 0 when the text is erased), and v1. The original's run is kept between runs
(tests/refcache.py).
"""
import hashlib
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import refcache  # noqa: E402
import scb       # noqa: E402

TIMED = [20, 206, 207, 208, 209]
SCANS = {'return': 0x1C, 'space': 0x34, 'shift': 0x70, 'a': 0x1D, 'esc': 0x00, 'up': 0x3A}


class Policy:
    """the player: an answer to each page a while after it appears"""

    def __init__(self, seed, cut=None):
        self.rnd = random.Random('check_text %s' % seed)
        self.cut = cut                  # (timed page, delay): an input cuts it short
        self.timed = 0

    def add(self, m, f, ev):
        m.sched.setdefault(f, []).append(ev)

    def key(self, m, f, name, hold):
        self.add(m, f, ('scan', SCANS[name]))
        self.add(m, f + hold, ('scan', SCANS[name] | 0x80))

    def move(self, m, f, b=0):
        x, y = self.rnd.randrange(0, 640), self.rnd.randrange(0, 400)
        self.add(m, f, ('mouse', x, y, b))
        return x, y

    def __call__(self, m, kind):
        r = self.rnd
        now = m.frame - m.fbase
        if kind == 'timed':
            self.timed += 1
            if self.cut and self.timed == self.cut[0]:
                self.key(m, now + self.cut[1], 'return', 2)
            elif r.random() < 0.4:              # nothing that cuts it short
                x, y = self.move(m, now + r.randrange(1, 30), 2)
                self.add(m, now + r.randrange(31, 40), ('mouse', x, y, 0))
            return
        d = now + r.choice([1, 2, 3, 5, 8, 13, 30, 44, 45, 46, 60, 89, 90, 91, 135, 200])
        if r.random() < 0.3:
            self.move(m, now + r.randrange(1, d - now + 1))
        what = r.choice(['return', 'return', 'space', 'shift', 'a', 'esc', 'left', 'left',
                         'right', 'up'])
        if what == 'left':
            x, y = self.move(m, d, 1)
            self.add(m, d + r.choice([1, 2, 7]), ('mouse', x, y, 0))
        elif what == 'right':
            x, y = self.move(m, d, 2)
            self.add(m, d + 3, ('mouse', x, y, 0))
            self.key(m, d + 10, 'return', 1)
        elif what == 'esc':
            self.key(m, d, 'esc', r.choice([1, 4, 30]))
        else:
            self.key(m, d, what, r.choice([1, 3, 9]))


def runs(count):
    """(name, setup commands, message, policy)"""
    out = [('msg%d' % n, [], n, Policy(n)) for n in range(1, count + 1)]
    for i, n in enumerate(TIMED):
        out.append(('cut%d' % n, [], n, Policy('cut %d' % n, cut=(1 + i % 3, 5 + 17 * i))))
    out.append(('full1', ['fill'], 1, Policy('full 1')))
    out.append(('full206', [], 206, Policy('full 206')))
    out.append(('full208', ['free'], 208, Policy('full 208')))
    out.append(('kbd3', ['input 1'], 3, Policy('kbd 3')))
    out.append(('kbd4', ['input 3'], 4, Policy('kbd 4')))
    return out


def original(pak, count):
    import textrig
    m = textrig.Machine(textrig.Fonts(pak))
    m.start(3)
    m.scene()
    res = []
    for name, setup, n, pol in runs(count):
        for c in setup:
            if c == 'fill':
                m.timers_fill()
            elif c == 'free':
                m.timers_free()
            else:
                m.input_mask(int(c.split()[1]))
        m.on_page = pol
        v1, log, used = m.op19(n)
        sched = [[f, list(ev)] for f, ev in used]
        res.append({'name': name, 'v1': v1, 'log': [list(x) for x in log], 'sched': sched})
    return res


def engine(test, pak, count, ref):
    cmds = ['scene']
    for (name, setup, n, _pol), r in zip(runs(count), ref):
        cmds += setup
        for f, ev in r['sched']:
            if ev[0] == 'scan':
                cmds.append('ev %d scan %02x' % (f, ev[1]))
            else:
                cmds.append('ev %d mouse %d %d %d' % (f, ev[1], ev[2], ev[3]))
        cmds.append('msg %d' % n)
    res = subprocess.run([test, pak, str(count), '3'], input='\n'.join(cmds) + '\n',
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_text: test_text failed (exit %d)' % res.returncode)
    out, log = [], []
    for ln in res.stdout.split('\n'):
        if ln.startswith('v1 '):
            out.append({'v1': int(ln[3:]), 'log': log})
            log = []
        elif ln and ln != 'end':
            f, kind, arg, crc = ln.split()
            log.append([int(f), kind, int(arg), int(crc)])
    return out


def compare(kind, ref, got):
    bad = 0
    events = 0
    for i, r in enumerate(ref):
        g = got[i] if i < len(got) else {'v1': None, 'log': []}
        events += len(r['log'])
        if g['v1'] != r['v1'] or g['log'] != r['log']:
            bad += 1
            if bad <= 5:
                print('%s %s: differs (v1 engine %s, original %s)' % (kind, r['name'], g['v1'],
                                                                     r['v1']))
                for k in range(max(len(r['log']), len(g['log']))):
                    a = g['log'][k] if k < len(g['log']) else None
                    b = r['log'][k] if k < len(r['log']) else None
                    if a != b:
                        print('  event %d: engine %s, original %s' % (k, a, b))
                        break
    return bad, events


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    test, pak = argv[1], argv[2]
    sc = scb.Scenario(open(os.path.join(refcache.ORIG, 'CMD00.SCB'), 'rb').read())
    count = sc.counts['n_t52']
    import textrig
    fonts = textrig.Fonts(pak)
    fh = hashlib.sha256(fonts.raw['font16'] + fonts.raw['font8']).hexdigest()
    ref, hit = refcache.get('text', ['check_text.py', 'textrig.py'], None,
                            {'count': count, 'fonts': fh, 'version': 2},
                            lambda: original(pak, count))
    got = engine(test, pak, count, ref)
    bad, events = compare('run', ref, got)
    pages = sum(1 for r in ref for e in r['log'] if e[1] == 'show')
    first = sum(1 for r in ref[:count] for e in r['log'] if e[1] == 'show')
    print('check_text: %d runs, %d pages (%d of them the %d messages once), %d events: %s '
          '(reference %s)' % (
        len(ref), pages, first, count, events, 'identical to the original' if not bad else
        '%d runs differ' % bad, 'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
