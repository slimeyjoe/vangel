#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_menu.py - the engine's statement 24h against M.EXE's own: all 43 menus.

usage: check_menu.py TEST_TEXT PAK                 (with $EMU_PYTHON: unicorn)

The original runs under tests/textrig.py as in check_text.py. Every menu of the scenario's
table is run by statement 24h (001E:0A8D) several times: chosen with the keyboard (UP and
DOWN with their wrap-around, keys that do nothing, RETURN), with the mouse (the pointer over
the choices and outside them, a left click held some frames, the right button), with the
pointer already on a choice when the menu appears, and the same statement again (which
starts on its last choice). The input is fixed in advance per run (frames from its start).
Both sides record every bar inverted and the window's pixels then, the menu drawn and erased,
the pointer shown and hidden, at the same frame, and the result v1 (tests/test_text.c). The
original's run is kept between runs (tests/refcache.py).
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
from check_text import compare  # noqa: E402

KEYS = {'return': 0x1C, 'up': 0x3A, 'down': 0x3D, 'left': 0x3B, 'space': 0x34, 'esc': 0x00,
        'a': 0x1D}


def choice_xy(rnd, i):
    return rnd.randrange(48, 592), 307 + 20 * i + rnd.randrange(0, 20)


def script(menu, n, how, seed):
    """{frame: [event]} for one run of a menu of n choices"""
    rnd = random.Random('check_menu %d %s %s' % (menu, how, seed))
    sched = {}
    f = 1

    def add(fr, ev):
        sched.setdefault(fr, []).append(ev)

    def key(name):
        nonlocal f
        add(f, ('scan', KEYS[name]))
        add(f + 1, ('scan', KEYS[name] | 0x80))
        f += 2 + rnd.choice([0, 0, 1, 5])

    if how == 'keys':
        for _ in range(rnd.randrange(0, 9)):
            key(rnd.choice(['up', 'down', 'down', 'up', 'left', 'space', 'a', 'esc']))
        key('return')
    elif how == 'mouse':
        b = 0
        for _ in range(rnd.randrange(1, 7)):
            if rnd.random() < 0.7:
                x, y = choice_xy(rnd, rnd.randrange(0, 4))
            else:
                x, y = rnd.randrange(0, 640), rnd.randrange(0, 400)
            b = 2 if rnd.random() < 0.2 else 0
            add(f, ('mouse', x, y, b))
            f += rnd.choice([1, 2, 6])
        add(f, ('mouse', x, y, 1))
        add(f + rnd.choice([1, 3, 8]), ('mouse', x, y, 0))
    elif how == 'both':
        for _ in range(rnd.randrange(2, 8)):
            if rnd.random() < 0.5:
                x, y = choice_xy(rnd, rnd.randrange(0, n))
                add(f, ('mouse', x, y, 0))
                f += 1
            else:
                key(rnd.choice(['up', 'down']))
        key('return')
    return sched


def runs(nmenus):
    """(menu, stmt, how, seed, pointer before)"""
    out = []
    for m in range(1, nmenus + 1):
        out.append((m, 1, 'keys', 0, None))
        out.append((m, 1, 'keys', 1, None))       # the same statement: its last choice
        out.append((m, 2, 'mouse', 0, None))
        out.append((m, 3, 'both', 0, 'on'))      # the pointer on a choice before
    return out


def original(nmenus):
    import textrig
    m = textrig.Machine(textrig.Fonts(PAK))
    m.start(3)
    m.scene()
    res = []
    for menu, stmt, how, seed, before in runs(nmenus):
        items = m.menu_items(menu)
        sched = script(menu, len(items), how, seed)
        if before:
            rnd = random.Random('check_menu before %d' % menu)
            x, y = choice_xy(rnd, rnd.randrange(0, len(items)))
            m.mouse = before = [x, y, 0]
        v1, log, used = m.op24(menu, stmt, sched)
        res.append({'name': 'menu%d.%s.%d' % (menu, how, seed), 'v1': v1,
                    'log': [list(x) for x in log], 'items': [i.hex() for i in items],
                    'stmt': stmt, 'before': before,
                    'sched': [[f, list(ev)] for f, ev in used]})
    return res


def engine(test, pak, count, ref):
    cmds = ['scene']
    for r in ref:
        for f, ev in r['sched']:
            if ev[0] == 'scan':
                cmds.append('ev %d scan %02x' % (f, ev[1]))
            else:
                cmds.append('ev %d mouse %d %d %d' % (f, ev[1], ev[2], ev[3]))
        if r['before']:
            cmds.append('mouse %d %d %d' % tuple(r['before']))
        cmds.append('menu %d %s' % (r['stmt'], ' '.join(r['items'])))
    res = subprocess.run([test, pak, str(count), '3'], input='\n'.join(cmds) + '\n',
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_menu: test_text failed (exit %d)' % res.returncode)
    out, log = [], []
    for ln in res.stdout.split('\n'):
        if ln.startswith('v1 '):
            out.append({'v1': int(ln[3:]), 'log': log})
            log = []
        elif ln and ln != 'end':
            f, kind, arg, crc = ln.split()
            log.append([int(f), kind, int(arg), int(crc)])
    return out


PAK = None


def main(argv):
    global PAK
    if len(argv) != 3:
        sys.exit(__doc__)
    test, PAK = argv[1], argv[2]
    sc = scb.Scenario(open(os.path.join(refcache.ORIG, 'CMD00.SCB'), 'rb').read())
    nmenus, count = sc.counts['n_t44'], sc.counts['n_t52']
    import textrig
    fonts = textrig.Fonts(PAK)
    fh = hashlib.sha256(fonts.raw['font16'] + fonts.raw['font8']).hexdigest()
    ref, hit = refcache.get('menu', ['check_menu.py', 'check_text.py', 'textrig.py'], None,
                            {'menus': nmenus, 'fonts': fh, 'version': 2},
                            lambda: original(nmenus))
    got = engine(test, PAK, count, ref)
    bad, events = compare('menu', ref, got)
    print('check_menu: %d menus, %d runs, %d events: %s (reference %s)' % (
        nmenus, len(ref), events, 'identical to the original' if not bad else
        '%d runs differ' % bad, 'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
