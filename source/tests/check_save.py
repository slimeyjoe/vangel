#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_save.py - the engine's GAME.DAT against M.EXE's save_slot and load_slot.

usage: check_save.py TEST_VM                 (with $EMU_PYTHON: unicorn)

The original's save_slot (001E:042C) and load_slot (001E:0577) run under re-tools/mcall.py
(the scenario loaded; game.dat a file of the emulated DOS) and the engine's
(engine/game/saves.c, tests/test_vm.c) on the same interpreter states and files:
  * saves of random states (pc, depth, all 32 stack words, every variable's type and value,
    the unused slot 0 included) into each slot of a new file, of a shorter file (the gap) and
    of a longer one (the rest kept): the whole file compared after each;
  * loads of those records into other states, and of what must load nothing or something
    odd: no file, an empty one, a wrong signature, a wrong size, records cut short after the
    size, in the stack and in the variables (the rest read as EOF), a slot past the end, and
    the three slots of the disk's own GAME.DAT (a previous owner's saves) when it is there:
    the interpreter's whole state compared after each.
"""
import os
import random
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import refcache  # noqa: E402

PC98 = os.path.join(ROOT, 'resources', 'original', 'pc98', 'CMD00.SCB')
DISK = os.path.join(ROOT, 'resources', 'original', 'pc98', 'GAME.DAT')
NVAR = 20
REC = (NVAR + 24) * 3


def rstate(rnd):
    edge = [0, 1, 2, 0x7FFF, 0x8000, 0xFFFF, 0x06CE]
    v = lambda: rnd.choice(edge) if rnd.random() < 0.3 else rnd.randint(0, 0xFFFF)  # noqa
    s16 = lambda x: x - 0x10000 if x & 0x8000 else x  # noqa
    return ('state', v(), rnd.randint(0, 31), [v() for _ in range(32)],
            [(rnd.choice([6, 10, 0, 2, 0x7F, -1, 0x1234]), s16(v())) for _ in range(NVAR + 1)])


def record(rnd, pc=0x500, depth=3):
    b = b'SD' + struct.pack('>HHH', REC, pc, depth)
    b += struct.pack('>32H', *[rnd.randint(0, 0xFFFF) for _ in range(32)])
    for _ in range(NVAR):
        b += struct.pack('>BH', rnd.choice([6, 10, 0xFF]), rnd.randint(0, 0xFFFF))
    return b


def steps():
    rnd = random.Random('check_save 1')
    out = [('gamedat', None)]
    for k in range(3):
        out += [rstate(rnd), ('save', k), ('gamedat?',)]
    for k in (2, 0, 1):
        out += [rstate(rnd), ('load', k), ('dump',)]
    # into a shorter file, a longer one
    out += [('gamedat', b'0123456789'), rstate(rnd), ('save', 2), ('gamedat?',)]
    out += [('gamedat', bytes(range(256)) * 3), rstate(rnd), ('save', 1), ('gamedat?',)]
    out += [rstate(rnd), ('load', 1), ('dump',), ('load', 0), ('dump',)]
    good = record(rnd)
    bad = [None, b'', b'S', b'SX' + good[2:], b'XD' + good[2:],
           good[:2] + struct.pack('>H', REC - 1) + good[4:],
           good[:2] + struct.pack('>H', REC + 1) + good[4:],
           good[:4], good[:5], good[:7], good[:9], good[:40], good[:73], good[:74], good[:75],
           good[:100], good[:-1], good, good + good[:50]]
    for data in bad:
        out += [('gamedat', data), rstate(rnd), ('load', 0), ('dump',)]
    out += [('gamedat', good + good[:10]), rstate(rnd), ('load', 1), ('dump',),
            rstate(rnd), ('load', 2), ('dump',)]
    if os.path.exists(DISK):
        disk = open(DISK, 'rb').read()
        for k in range(3):
            out += [('gamedat', disk), rstate(rnd), ('load', k), ('dump',)]
        out += [rstate(rnd), ('save', 1), ('gamedat?',)]
    return out


def hexb(b):
    return '-' if b is None else b.hex()


def original(st, empty):
    from vmrig import Orig, state_line
    o = Orig(open(PC98, 'rb').read(), files=empty)
    out = []
    for s in st:
        if s[0] == 'gamedat':
            o.set_game_dat(s[1])
        elif s[0] == 'gamedat?':
            out.append('gamedat ' + hexb(o.game_dat()))
        elif s[0] == 'state':
            o.set_state(s[1], s[2], s[3])
            for i, (t, v) in enumerate(s[4]):
                o.set_var(i, t, v)
        elif s[0] == 'save':
            o.save(s[1])
            out.append('saved')
        elif s[0] == 'load':
            o.load(s[1])
            out.append('loaded')
        elif s[0] == 'dump':
            out.append(state_line(o.state()))
    return out


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    st = steps()
    with tempfile.TemporaryDirectory() as tmp:
        empty = os.path.join(tmp, 'empty')
        os.mkdir(empty)
        key = [[s[0]] + [hexb(x) if isinstance(x, (bytes, type(None))) else x for x in s[1:]]
               for s in st]
        want, hit = refcache.get('save', ['check_save.py', 'vmrig.py'], None, {'steps': repr(key)},
                                 lambda: original(st, empty))
        lines = ['scb %s\n' % PC98]
        for s in st:
            if s[0] == 'gamedat':
                lines.append('gamedat %s\n' % hexb(s[1]))
            elif s[0] == 'state':
                lines.append('state %d %d %s\n' % (s[1], s[2], ' '.join(map(str, s[3]))))
                lines += ['var %d %d %d\n' % (i, t, v) for i, (t, v) in enumerate(s[4])]
            elif s[0] in ('save', 'load'):
                lines.append('%s %d\n' % s)
            else:
                lines.append(s[0] + '\n')
        res = subprocess.run([argv[1], empty], input=''.join(lines), capture_output=True,
                             text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_save: test_vm failed (exit %d)' % res.returncode)
    got = [ln for ln in res.stdout.split('\n')
           if ln.startswith(('gamedat', 'state ', 'saved', 'loaded'))]
    bad = 0
    for k, w in enumerate(want):
        g = got[k] if k < len(got) else '(none)'
        if g != w:
            bad += 1
            if bad <= 5:
                print('result %d:\n  original %s\n  engine   %s' % (k, w[:300], g[:300]))
    print('check_save: %d saves, %d loads: %s (reference %s)' % (
        sum(1 for s in st if s[0] == 'save'), sum(1 for s in st if s[0] == 'load'),
        'identical to the original' if not bad else '%d of %d results differ' % (bad, len(want)),
        'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
