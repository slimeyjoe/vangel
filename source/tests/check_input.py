#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_input.py - the engine's keyboard handler and device layer against M.EXE's own.

usage: check_input.py TEST_TEXT PAK                (with $EMU_PYTHON: unicorn)

Under tests/textrig.py, from the original's start-up with the keyboard and the mouse open:
every byte 00h..FFh from the keyboard through its INT 09h handler (0401:0228), each followed
by input_poll (043A:01DA), and runs of several bytes between two polls (the latch keeps the
last: a release after a press loses it, ESC counts when let go); the mouse moved, its buttons
pressed (the right one is not part of "changed"); the keyboard's release step after a key
(043A:0236 mask 1), the mouse's while the left button is held for some frames (mask 2), and
then the same with only the keyboard open and with only the mouse. Every result of
input_poll and the frames each release step took are compared with the engine's
(tests/test_text.c). The original's run is kept between runs (tests/refcache.py).
"""
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import refcache  # noqa: E402


def steps():
    """('isr', byte) ('mouse', x, y, b) ('poll',) ('release', mask, sched) ('input', mask)"""
    rnd = random.Random('check_input')
    out = []
    for b in range(256):
        out += [('isr', b), ('poll',), ('poll',)]
    for _ in range(300):
        for _ in range(rnd.randrange(1, 4)):
            out.append(('isr', rnd.choice([0x00, 0x80, 0x1C, 0x9C, 0x3A, 0xBA, 0x3D, 0xBD,
                                           0x70, 0xF0, rnd.randrange(256)])))
        if rnd.random() < 0.5:
            out.append(('mouse', rnd.choice([0, 5, 639]), rnd.choice([0, 7, 399]),
                        rnd.randrange(4)))
        out.append(('poll',))
    for mask in (3, 1, 2):
        out.append(('input', mask))
        for _ in range(40):
            k = rnd.random()
            if k < 0.3:
                out.append(('isr', rnd.choice([0x1C, 0x00, 0x80, 0x34])))
            elif k < 0.6:
                out.append(('mouse', rnd.randrange(640), rnd.randrange(400), rnd.randrange(4)))
            elif k < 0.8:
                held = rnd.choice([0, 1, 4])
                sched = [[held, ['mouse', 10, 20, 0]]] if held else []
                out.append(('mouse', 10, 20, 1 if held else rnd.choice([0, 2])))
                out.append(('release', rnd.choice([1, 2, 3, 4, 7]), sched))
            out.append(('poll',))
    return out


def original(pak):
    import textrig
    m = textrig.Machine(textrig.Fonts(pak))
    m.start(3)
    res = []
    for s in steps():
        if s[0] == 'isr':
            m.isr(s[1])
        elif s[0] == 'mouse':
            m.mouse = [s[1], s[2], s[3]]
        elif s[0] == 'poll':
            res.append(['poll'] + m.poll())
        elif s[0] == 'release':
            res.append(['release', m.release(s[1], {f: [tuple(ev)] for f, ev in s[2]})])
        elif s[0] == 'input':
            m.input_mask(s[1])
    return res


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    test, pak = argv[1], argv[2]
    ref, hit = refcache.get('input', ['check_input.py', 'textrig.py'], None, {'version': 1},
                            lambda: original(pak))
    cmds = []
    for s in steps():
        if s[0] == 'isr':
            cmds.append('isr %02x' % s[1])
        elif s[0] == 'mouse':
            cmds.append('mouse %d %d %d' % s[1:])
        elif s[0] == 'poll':
            cmds.append('poll')
        elif s[0] == 'release':
            for f, ev in s[2]:
                cmds.append('ev %d mouse %d %d %d' % (f, ev[1], ev[2], ev[3]))
            cmds.append('release %d' % s[1])
        else:
            cmds.append('input %d' % s[1])
    res = subprocess.run([test, pak, '213', '3'], input='\n'.join(cmds) + '\n',
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_input: test_text failed (exit %d)' % res.returncode)
    got = [[ln.split()[0]] + [int(x) for x in ln.split()[1:]]
           for ln in res.stdout.split('\n') if ln.startswith(('poll', 'release'))]
    bad = 0
    for i, r in enumerate(ref):
        g = got[i] if i < len(got) else None
        if g != r:
            bad += 1
            if bad <= 5:
                print('result %d: engine %s, original %s' % (i, g, r))
    print('check_input: %d results (%d polls, %d release steps): %s (reference %s)' % (
        len(ref), sum(1 for r in ref if r[0] == 'poll'), sum(1 for r in ref if r[0] != 'poll'),
        'identical to the original' if not bad and len(got) == len(ref) else
        '%d differ' % max(bad, 1), 'stored' if hit else 'computed'))
    return 1 if bad or len(got) != len(ref) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
