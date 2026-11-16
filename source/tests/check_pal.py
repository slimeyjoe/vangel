#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_pal.py - the engine's palette operations against M.EXE's own.

usage: check_pal.py TEST_PAL PAK                 (with $EMU_PYTHON: unicorn, capstone)

A sequence of op 30h (0315:0176), op 1Ah (0315:04E2) and op 2Fh (0315:06C2) with the
scenario's palettes, every time the scenario uses and to white and black, then the same with
all 16 timer slots taken (the fades are skipped, the palette is set at once). (Op 2Fh with
t below 2 is not among them: the original ends there, run-time error R6003, as _aFldiv
divides by t / 2 = 0; the engine does the same.) The original
runs from the state after gfx_init and the timer's installation under re-tools/m286.py: an
80286 at the profile's speed, the VSYNC interrupt advancing the timer slots, the GDC status
showing the retrace for its first 40 of 440 lines. Every DAC load (ports A8h, AEh, ACh, AAh
for colours 0..15, in that order) is compared with the engine's (tests/test_pal.c): its
palette and the VSYNC it comes after. The original's result is kept between runs
(tests/refcache.py).
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import refcache  # noqa: E402
import scb       # noqa: E402

REF_CPF = 177242
SEQ = [('30', 32, 0), ('1a', 0, 40), ('30', 10, 100), ('2f', 30), ('1a', 1, 100),
       ('30', 34, 1), ('30', 44, 160), ('1a', 0, 0), ('30', 3, 56), ('1a', 1, 0),
       ('30', 2, 100), ('1a', 0, 150), ('30', 41, 150), ('2f', 30), ('1a', 0, 180),
       ('30', 30, 30), ('1a', 1, 80), ('30', 42, 100), ('30', 39, 0), ('1a', 0, 56),
       ('30', 33, 40), ('2f', 2), ('2f', 3), ('1a', 0, 1), ('30', 4, 2), ('1a', 1, 1),
       ('30', 8, 1),
       ('fill',), ('30', 5, 100), ('1a', 1, 50), ('2f', 30), ('30', 6, 100), ('free',),
       ('30', 7, 30)]


def packed(pal):
    return bytes([c[0] for c in pal] + [c[1] for c in pal] + [c[2] for c in pal])


def hexpal(b):
    return ''.join('%x' % v for v in b)


def original(sc):
    from unicorn import UC_HOOK_CODE  # noqa: F401
    from m286 import TM

    class PM(TM):
        def _out(self, uc, port, size, value, ud):
            if port == 0xA8 and (value & 15) == 0 and self.timing:
                self.loads.append([self.frame, []])
            if port in (0xA8, 0xAA, 0xAC, 0xAE) and self.timing and self.loads:
                self.loads[-1][1].append((port, value))
            super()._out(uc, port, size, value, ud)

    m = PM(cpu_per_frame=REF_CPF, trace_ports=False)
    m.loads = []
    m.timing = False
    if m.call(0x0315, 0x000E)[0] != 1:
        sys.exit('check_pal: gfx_init failed under emulation')
    m.call(0x0752, 0x0002)              # the timer: INT 0Ah, the slots
    m.timing = True
    m.cyc = 0
    f0 = m.frame
    buf = m.alloc(64)
    held = []
    for s in SEQ:
        if s[0] == '30':
            m.poke(buf, 0, packed(sc.pal[s[1] - 1]))
            m.call(0x0315, 0x0176, [0, buf, s[2]])
        elif s[0] == '1a':
            m.call(0x0315, 0x04E2, [s[1], s[2]])
        elif s[0] == '2f':
            m.call(0x0315, 0x06C2, [s[1]])
        elif s[0] == 'fill':
            m.timing = False
            while True:
                h = m.call(0x0752, 0x0026, [100000 & 0xFFFF, 100000 >> 16])[0]
                if not h:
                    break
                held.append(h)
            m.timing = True
        elif s[0] == 'free':
            m.timing = False
            for h in held:
                m.call(0x0752, 0x0043, [h])
            held = []
            m.timing = True
    out = []
    for frame, ports in m.loads:
        if len(ports) != 64 or [p for p, _v in ports] != [0xA8, 0xAE, 0xAC, 0xAA] * 16 or \
                [v for p, v in ports if p == 0xA8] != list(range(16)):
            out.append('bad DAC load at %d' % (frame - f0))
            continue
        r = [v for p, v in ports if p == 0xAC]
        g = [v for p, v in ports if p == 0xAA]
        b = [v for p, v in ports if p == 0xAE]
        out.append('dac %d %s' % (frame - f0, hexpal(bytes(x & 15 for x in r + g + b))))
    out.append('end %d' % (m.frame - f0))
    return out


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    test_pal, pak = argv[1], argv[2]
    sc = scb.Scenario(open(os.path.join(refcache.ORIG, 'CMD00.SCB'), 'rb').read())
    want, hit = refcache.get('pal', ['check_pal.py'], None, {'seq': [list(s) for s in SEQ]},
                             lambda: original(sc))
    lines = []
    for s in SEQ:
        if s[0] == '30':
            lines.append('30 %d %s\n' % (s[2], hexpal(packed(sc.pal[s[1] - 1]))))
        else:
            lines.append(' '.join(str(x) for x in s) + '\n')
    res = subprocess.run([test_pal, pak], input=''.join(lines), capture_output=True, text=True,
                         check=False)
    got = [ln for ln in res.stdout.split('\n') if ln]
    if res.returncode != 0:
        print(res.stdout + res.stderr)
        sys.exit('check_pal: test_pal failed (exit %d)' % res.returncode)
    bad = 0
    for k in range(max(len(got), len(want))):
        a = got[k] if k < len(got) else '(none)'
        b = want[k] if k < len(want) else '(none)'
        if a != b:
            bad += 1
            if bad <= 5:
                print('load %d: engine %s, original %s' % (k, a, b))
    n = len(want) - 1
    print('check_pal: %d statements, %d DAC loads: %s (reference %s)' % (
        len(SEQ), n, 'identical to the original, frame by frame' if not bad else
        '%d lines differ' % bad, 'stored' if hit else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
