#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_snd.py - the engine's music layer against M.EXE's (segments 04E4 and 048F).

usage: check_snd.py TEST_SND PACK              (with $EMU_PYTHON: unicorn)

The original's music layer runs under re-tools/sndcall.py (mcall with a stand-in resident PMD at
INT 60h; a VSYNC at each turn of the fade's wait loop) and the engine's (engine/snd/mus.c,
tests/test_snd.c, on a stand-in that answers the same) on the same commands: GAME.BAT's
setups without a driver and with PMD on each board type (PMD.COM, PMDB2, PMD86, PMD without a
board), the initialisation, plays (the same name, another case, .n songs, names without or
with several dots, missing files, odd volumes), stops, measure queries, fades of many lengths
(none free timer, no timer, t = 0), the termination. After each call both report the return
value, every INT 60h call with the frames passed before it, every file tried, and the layer's
state: g_mus_ok, g_pmd_present, g_pmd_state, g_pmd_board, g_mus_vol, g_mus_name and the
music buffer.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
import refcache  # noqa: E402

PC98 = os.path.join(ROOT, 'resources', 'original', 'pc98')


def commands():
    c = ['setup none', 'timer', 'state', 'measure', 'init', 'state', 'measure',
         'play va_m01.m 100', 'fade 320', 'stop', 'term', 'init']
    for b in ('0', '1', '2', 'FF'):
        c += ['setup ' + b, 'timer', 'state', 'measure', 'play va_m01.m 100', 'stop', 'init',
              'init', 'state', 'measure', 'play va_m01.m 100', 'state']
        for n in (0, 4, 1, 0x7FFF, 0xFFFE, 0xFFFF):
            c += ['measure= %d' % n, 'measure']
        c += ['play va_m01.m 100', 'play VA_M01.M 100', 'play va_m02.m 75', 'play va_m02 50',
              'play va_m02.m.x 100', 'play va_m03.m 100', 'fade 320', 'state', 'measure',
              'fade 200', 'stop',
              'play va_m04.m 50', 'fade 150', 'play va_m05.m 1', 'fade 1', 'play va_m06.m 0',
              'fade 2', 'play va_m07.m 200', 'fade 30', 'play va_m08.m -1', 'fade 10',
              'play va_m09.m 99', 'fade -5', 'play va_m10.m 25', 'fade 1000',
              'play va_m99.m 100', 'state', 'measure', 'play va_m99.m 100', 'fade 100',
              'play va_m11.m 100', 'play .m 100', 'play va_m14 100', 'play x 100',
              'play va_m12.m 100', 'stop', 'stop', 'play va_m13.m 100', 'term', 'state',
              'measure', 'play va_m13.m 100', 'fade 50', 'init', 'play va_m13.m 100',
              'play va_m15.m 100', 'slots 15', 'fade 20', 'play va_m16.m 100', 'slots 1',
              'fade 320', 'play va_m17.m 100', 'term']
        # without the timer; then t = 0, which divides by zero (the end of that machine)
        c += ['setup ' + b, 'init', 'play va_m18.m 100', 'fade 320', 'play va_m19.m 100',
              'timer', 'fade 0']
    return c


def fnv(data):
    h = 0xcbf29ce484222325
    for x in data:
        h = ((h ^ x) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def original(cmds):
    from sndcall import SndM
    from mcall import Exit
    files = {f.lower() for f in os.listdir(PC98)}
    out = []
    m = None
    dead = False
    for cmd in cmds:
        w = cmd.split()
        op = w[0]
        if op == 'setup':
            if w[1] == 'none':
                m = SndM(pmd=False)
            else:
                m = SndM(board=int(w[1], 16), pps=False, pps_flag=0)
            dead = False
            continue
        if dead:
            continue
        if op == 'timer':
            m.c(0x0752, 0x0002)
            m.drain()
            continue
        if op == 'slots':
            for _ in range(int(w[1])):
                m.c(0x0752, 0x0026, [1000, 0])
            m.drain()
            continue
        if op == 'measure=':
            m.measure = int(w[1])
            continue
        try:
            if op == 'init':
                r = m.c(0x04E4, 0x0004)
            elif op == 'term':
                m.c(0x04E4, 0x0021)
                r = 0
            elif op == 'stop':
                r = m.c(0x04E4, 0x00A7)
            elif op == 'state':
                r = m.c(0x04E4, 0x01D8)
            elif op == 'measure':
                r = m.c(0x04E4, 0x01E9)
            elif op == 'play':
                r = m.play(w[1], int(w[2]) & 0xFFFF)
            elif op == 'fade':
                r = m.c(0x04E4, 0x00F0, [int(w[1]) & 0xFFFF])
            else:
                raise SystemExit('check_snd: bad command %r' % cmd)
            out.append('R %d' % r)
        except Exit as e:
            out.append('exit %d' % e.args[0])
            dead = True
        calls, opens = m.drain()
        out.append('calls' + ''.join(
            (' %02X:%02X@%d' % (ah, al, v)) if ah in (0x19, 0x1E) else (' %02X@%d' % (ah, v))
            for i, ah, al, v in calls))
        out.append('opens' + ''.join(' %s%s' % (o, '+' if o.lower() in files else '-')
                                     for o in opens))
        name = bytes(m.uc.mem_read(m.lin(m.ds, 0x01D0), 19)).split(b'\0')[0].decode('cp932')
        out.append('st %d %d %02X %d %d %s %016x' % (
            m.word(m.ds, 0x01CC), m.word(m.ds, 0x01B2), m.word(m.ds, 0x17A6),
            s16(m.word(m.ds, 0x17A4)), s16(m.word(m.ds, 0x01CE)), name or '-',
            fnv(bytes(m.uc.mem_read(m.musbuf, 8192)))))
    return out


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    cmds = commands()
    want, hit = refcache.get('snd', ['check_snd.py'], None, {'commands': cmds},
                             lambda: original(cmds))
    res = subprocess.run([argv[1], argv[2]], input=''.join(c + '\n' for c in cmds),
                         capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stdout[-2000:] + res.stderr)
        sys.exit('check_snd: test_snd failed (exit %d)' % res.returncode)
    got = [ln for ln in res.stdout.split('\n') if ln]
    bad = 0
    for k in range(max(len(want), len(got))):
        w = want[k] if k < len(want) else '(none)'
        g = got[k] if k < len(got) else '(none)'
        if g != w:
            bad += 1
            if bad <= 5:
                print('line %d:\n  original %s\n  engine   %s' % (k, w[:400], g[:400]))
    ncalls = sum(ln.count('@') for ln in want if ln.startswith('calls'))
    print('check_snd: %d commands, %d driver calls: %s (reference %s)' % (
        len(cmds), ncalls,
        'identical to the original' if not bad else '%d of %d lines differ' % (bad, len(want)),
        'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
