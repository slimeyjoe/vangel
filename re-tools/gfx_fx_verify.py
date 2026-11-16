#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""gfx_fx_verify.py - check re-tools/gfx_fx.py (op 32 rectangle copy + effects) against M.EXE.

Calls the original op 32 routine (0315:07CB -> 00DD:051A -> 0783:xxxx) under unicorn (mcall)
with random source/destination buffers and compares
  * the sequence of byte writes to VRAM (plane, offset, value) when the destination is VRAM,
  * the final destination planes (also for the memory buffer 12),
  * for effect 31 the write count at each of the 64 waits (a VSYNC is simulated whenever the
    wait loop at 00DD:04FE spins).
Usage: gfx_fx_verify.py      (needs $EMU_PYTHON)
"""
import os
import random
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unicorn import UC_HOOK_CODE  # noqa: E402
from gf_verify import GM  # noqa: E402
import gfx_fx  # noqa: E402


class LM(GM):
    def __init__(self, **kw):
        self.wlog = None
        super().__init__(**kw)

    def _vwrite(self, lin, size, value):
        if self.wlog is not None and not self.grcg_mode & 0x80:
            for i in range(size):
                p, o = self._plane(lin + i)
                self.wlog.append((self.draw_page, p, o, (value >> (8 * i)) & 0xFF))
        super()._vwrite(lin, size, value)


def main():
    m = LM(trace_ports=False)
    if m.call(0x0315, 0x000E)[0] != 1:
        sys.exit('gfx_init failed')
    ds = m.ds
    steps = []

    def vsync(uc, a, s, u):          # the effect-31 wait loop: one VSYNC per spin
        v = m.word(ds, 0x109E)
        m.poke(ds, 0x109E, struct.pack('<H', (v + 1) & 0xFFFF))

    def step(uc, a, s, u):
        steps.append(len(m.wlog) if m.wlog is not None else 0)
    m.uc.hook_add(UC_HOOK_CODE, vsync, begin=m.lin(m.seg(0x00DD), 0x04FE), end=m.lin(m.seg(0x00DD), 0x04FE))
    m.uc.hook_add(UC_HOOK_CODE, step, begin=m.lin(m.seg(0x0783), 0x08BB), end=m.lin(m.seg(0x0783), 0x08BB))
    op = m.alloc(64)
    rnd = random.Random(32)
    geoms = [(0, 0, 640, 400, 0, 0), (160, 48, 320, 200, 160, 48), (32, 0, 248, 400, 32, 0),
             (80, 39, 480, 322, 80, 38), (16, 39, 272, 361, 24, 38), (8, 3, 100, 7, 600, 390)]
    effects = [10, 15, 20, 30, 31, 32, 33, 34, 35]
    bad = ok = 0
    for eff in effects:
        for (sx, sy, w, h, dx, dy) in geoms:
            if eff == 31 and w * h > 100000:
                continue              # slow under emulation; the small rectangles cover it
            for src, dst in ((12, 10), (11, 12), (10, 12)):
                if dst == 12 and eff in (31, 34):
                    continue          # 34 always writes VRAM; 31 covered with dst 10
                sp = [bytearray(rnd.getrandbits(8) for _ in range(32000)) for _ in range(4)]
                dp = [bytearray(rnd.getrandbits(8) for _ in range(32000)) for _ in range(4)]
                m.set_buf(src, sp)
                m.set_buf(dst, dp)
                blk = struct.pack('<9h', src, sx, sy, w, h, dst, dx, dy, eff)
                m.poke(op, 0, blk)
                m.wlog = []
                steps.clear()
                m.call(0x0315, 0x07CB, [0, op])
                got_log = [(p, o, v) for (pg, p, o, v) in m.wlog if pg == (dst - 10)] if dst != 12 else None
                got = m.get_buf(dst)
                m.wlog = None
                want = [bytearray(x) for x in dp]
                log = [] if dst != 12 else None
                wsteps = []
                gfx_fx.copy(sp, want, sx, sy, w, h, dx, dy, eff, log,
                            on_step=lambda k: wsteps.append(len(log) if log is not None else 0))
                good = got == want
                if log is not None:
                    good = good and got_log == log
                if eff == 31 and dst != 12:
                    good = good and steps == wsteps
                tag = 'fx %2d %2d->%2d %3dx%-3d (%3d,%3d)->(%3d,%3d)' % (eff, src, dst, w, h, sx, sy, dx, dy)
                if good:
                    ok += 1
                    print(tag, 'ok', '(%d writes)' % len(log) if log is not None else '', flush=True)
                else:
                    bad += 1
                    nd = sum(1 for q in range(4) for i in range(32000) if got[q][i] != want[q][i])
                    print(tag, 'FAIL: %d bytes differ, log %s/%s' % (
                        nd, len(got_log) if got_log is not None else '-', len(log) if log is not None else '-'), flush=True)
    print('%d cases match, %d failed' % (ok, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
