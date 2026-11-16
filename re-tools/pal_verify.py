#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""pal_verify.py - check re-tools/gfx_pal.py against M.EXE's palette code under unicorn.

Runs a sequence of op 30 (0315:0176), op 1A (0315:04E2) and op 2F (0315:06C2) calls with
scenario palettes and compares every palette written to the DAC (ports A8h/AAh/ACh/AEh, in
the original's port order) with the model.  The VSYNC interrupt is simulated: the timer is
initialised (0752:0002) and one VSYNC tick (075A:00A6's slot update) is applied each time a
fade's wait loop (0315:04A5, 0315:0677) spins.
Usage: pal_verify.py      (needs $EMU_PYTHON)
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unicorn import UC_HOOK_CODE  # noqa: E402
from gf_verify import GM  # noqa: E402
import gfx_pal  # noqa: E402
import scb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pack(pal):
    return bytes([c[0] for c in pal] + [c[1] for c in pal] + [c[2] for c in pal])


def main():
    sc = scb.Scenario(open(os.path.join(ROOT, 'resources/original/pc98/CMD00.SCB'), 'rb').read())
    m = GM(trace_ports=True)
    if m.call(0x0315, 0x000E)[0] != 1:
        sys.exit('gfx_init failed')
    m.call(0x0752, 0x0002)                     # timer init (hooks INT 0Ah)
    tseg = m.seg(0x0B91)

    def tick(uc, a, s, u):                     # 075A:00A6 for every slot
        for b in range(0, 0x100, 0x10):
            act, done, cnt, tgt = struct.unpack('<HHii', m.mem(tseg, b, 12))
            if act == 1 and done != 1:
                cnt += 1
                m.poke(tseg, b + 4, struct.pack('<i', cnt))
                if cnt >= tgt:
                    m.poke(tseg, b + 2, struct.pack('<H', 1))
    for off in (0x04A5, 0x0677):
        a = m.lin(m.seg(0x0315), off)
        m.uc.hook_add(UC_HOOK_CODE, tick, begin=a, end=a)

    st = gfx_pal.State()
    g = m.seg(0x0BA1)
    cur = m.mem(g, 0xA0, 48)
    st.cur = [(cur[i], cur[16 + i], cur[32 + i]) for i in range(16)]
    st.last_in, st.last_out = m.word(m.ds, 0xDE), m.word(m.ds, 0xE0)
    pbuf = m.alloc(64)
    seq = [('30', 32, 0), ('1a', 0, 40), ('30', 10, 100), ('2f', 30), ('1a', 1, 100),
           ('30', 34, 1), ('30', 44, 160), ('1a', 0, 0), ('30', 3, 56), ('1a', 1, 0),
           ('30', 2, 100), ('1a', 0, 150), ('30', 41, 150), ('2f', 30), ('1a', 0, 180),
           ('30', 30, 30), ('1a', 1, 80), ('30', 42, 100), ('30', 39, 0), ('1a', 0, 56)]
    bad = 0
    for s in seq:
        m.ports.clear()
        want = []
        if s[0] == '30':
            pal = sc.pal[s[1] - 1]
            m.poke(pbuf, 0, pack(pal))
            m.call(0x0315, 0x0176, [0, pbuf, s[2]])
            gfx_pal.fade_in(st, pal, s[2], want)
        elif s[0] == '1a':
            m.call(0x0315, 0x04E2, [s[1], s[2]])
            gfx_pal.fade_out(st, s[1], s[2], want)
        else:
            m.call(0x0315, 0x06C2, [s[1]])
            gfx_pal.flash(st, s[1], want)
        outs = [(p, v) for d, p, v in m.ports if d == 'out' and p in (0xA8, 0xAA, 0xAC, 0xAE)]
        got = []
        ok_order = True
        for i in range(0, len(outs), 64):
            grp = outs[i:i + 64]
            pal = []
            for j in range(16):
                q = grp[4 * j:4 * j + 4]
                if [p for p, v in q] != [0xA8, 0xAE, 0xAC, 0xAA] or q[0][1] != j:
                    ok_order = False
                pal.append((q[2][1], q[3][1], q[1][1]))
            got.append(pal)
        good = ok_order and got == want and len(outs) % 64 == 0
        bad += not good
        print('%-14s %3d DAC loads  %s' % (repr(s), len(got), 'ok' if good else
                                          'FAIL (model %d loads)' % len(want)), flush=True)
    print('%d sequences, %d failed' % (len(seq), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
