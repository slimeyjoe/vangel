#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""gfx_fx.py - model of Virgin Angel's op 32 rectangle copy and its effects, stdlib only.

Buffers are four planes (B, R, G, I) of 640x400 1-bit pixels, 80 bytes per line, bit 7 = the
leftmost pixel (buffer 10 = VRAM page 0, 11 = VRAM page 1, 12 = a copy in main memory).
copy(src, dst, sx, sy, w, h, dx, dy, effect, log=None) performs 00DD:051A's dispatch and the
0783:xxxx routine on bytearray planes and, if `log` is a list, appends every byte write to the
destination in the original's order as (plane, offset, value) - read-modify-write instructions
(and/or) log two writes, word instructions two byte writes (low byte first).  steps() yields
the points where the original waits (effect 31 only).  docs/re/graphics.md describes the
effects; re-tools/gfx_fx_verify.py checks this model against the original code.
"""

EFFECTS = {20: 'fx_masked', 30: 'fx_dissolve4', 31: 'fx_dissolve64', 32: 'fx_checker_tb',
           33: 'fx_interlace_tb', 34: 'fx_slide_lr'}

# 0783:0730..076F: the 64 cells of effect 31, indexed by the step counter 64..1
FX31_ORDER = bytes.fromhex('3c0e333f2f202508042c192d210f063827001811132b3b2e283907172616231032'
                           '353e1d0d3d05032a0b1e3609291b01020a153724141c0c1f121a303134223a')


def ror16(v, n=1):
    n &= 15
    return ((v >> n) | (v << (16 - n))) & 0xFFFF


def rol8(v):
    return ((v << 1) | (v >> 7)) & 0xFF


class _W:
    """Destination writer that logs byte writes."""

    def __init__(self, planes, log):
        self.p, self.log = planes, log

    def put(self, q, o, v):
        o &= 0xFFFF
        if o < len(self.p[q]):
            self.p[q][o] = v
        if self.log is not None:
            self.log.append((q, o, v))

    def get(self, q, o):
        o &= 0xFFFF
        return self.p[q][o] if o < len(self.p[q]) else 0


def _rd(planes, q, o):
    o &= 0xFFFF
    return planes[q][o] if o < len(planes[q]) else 0


def copy(src, dst, sx, sy, w, h, dx, dy, effect, log=None, on_step=None):
    so = sy * 80 + (sx >> 3)
    do = dy * 80 + (dx >> 3)
    W = _W(dst, log)
    if effect == 20:
        _fx20(src, W, so, do, w, h)
    elif effect == 30:
        _fx30(src, W, so, do, w, h)
    elif effect == 31:
        _fx31(src, W, so, do, w, h, on_step)
    elif effect == 32:
        _fx32(src, W, so, do, w, h)
    elif effect == 33:
        _fx33(src, W, so, do, w, h)
    elif effect == 34:
        _fx34(src, W, so, do, w, h)
    else:                      # every other code (10, 21..29, <20, >34): plain copy
        _copy(src, W, so, do, w, h)


def _line(src, W, s, d, nw):
    """rep movsw of nw words, four planes in order (0783:0035)."""
    for q in range(4):
        for k in range(2 * nw):
            W.put(q, d + k, _rd(src, q, s + k))


def _copy(src, W, so, do, w, h):
    nw = (w + 7) >> 4                  # 0783:002C: words, i.e. w rounded to 16 pixels
    for i in range(h):
        _line(src, W, so + 80 * i, do + 80 * i, nw)


def _fx20(src, W, so, do, w, h):
    """0783:007C: copy, colour 8 transparent, byte by byte."""
    nb = (w + 7) >> 3
    for i in range(h):
        for c in range(nb):
            s, d = so + 80 * i + c, do + 80 * i + c
            v = [_rd(src, q, s) for q in range(4)]
            m = 0
            for k in range(8):
                col = sum(((v[q] >> (7 - k)) & 1) << q for q in range(4))
                if col == 8:
                    m |= 0x80 >> k
            if m:
                for q in range(4):
                    a = W.get(q, d) & m
                    W.put(q, d, a)
                    W.put(q, d, a | (v[q] & ~m & 0xFF))
            else:
                for q in range(4):
                    W.put(q, d, v[q])


def _fx30(src, W, so, do, w, h):
    """0783:0350: 4 passes over the rectangle; pass p, line i copies the pixels whose
    x mod 4 == (p + i) mod 4 (masks 8888h ror (p + i))."""
    nw = (w + 7) >> 4
    dxp = 0x8888
    for p in range(4):
        m = dxp
        for i in range(h):
            s, d = so + 80 * i, do + 80 * i
            tmp = [[_rd(src, q, s + k) for k in range(2 * nw)] for q in range(4)]
            for q in range(4):
                for k in range(nw):
                    lo, hi = m & 0xFF, m >> 8
                    W.put(q, d + 2 * k, (tmp[q][2 * k] & lo) | (W.get(q, d + 2 * k) & ~lo & 0xFF))
                    W.put(q, d + 2 * k + 1,
                          (tmp[q][2 * k + 1] & hi) | (W.get(q, d + 2 * k + 1) & ~hi & 0xFF))
            m = ror16(m)
        dxp = ror16(dxp)


def _fx31(src, W, so, do, w, h, on_step=None):
    """0783:07C0: 64 steps; step for counter c = 64..1 takes cell b = FX31_ORDER[c - 1]:
    pixel column bit (b & 7) of every byte (mask 0101h << (b & 7)), on the lines whose
    (h - i) & 7 == (b >> 3) & 7; after each step the callback waits >= 2 VSYNCs."""
    nw = (w + 7) >> 4
    for c in range(64, 0, -1):
        b = FX31_ORDER[c - 1]
        mask = 0x0101 << (b & 7)
        phase = (b >> 3) & 7
        for i in range(h):
            if ((h - i) & 7) != phase:
                continue
            s, d = so + 80 * i, do + 80 * i
            for q in range(4):
                for k in range(nw):
                    lo, hi = mask & 0xFF, mask >> 8
                    W.put(q, d + 2 * k, (_rd(src, q, s + 2 * k) & lo) | (W.get(q, d + 2 * k) & ~lo & 0xFF))
                    W.put(q, d + 2 * k + 1,
                          (_rd(src, q, s + 2 * k + 1) & hi) | (W.get(q, d + 2 * k + 1) & ~hi & 0xFF))
        if on_step:
            on_step(64 - c)


def _fx32(src, W, so, do, w, h):
    """0783:05DD: h iterations; iteration i writes line i (from the top) and line h-1-i (from
    the bottom) with byte masks AAh/55h alternating per iteration: dst = src & m | dst & ~m."""
    nb = (w + 7) >> 3
    dl, dh = 0x55, 0xAA
    for i in range(h):
        dl, dh = rol8(dl), rol8(dh)
        for ln in (i, h - 1 - i):
            s, d = so + 80 * ln, do + 80 * ln
            for q in range(4):
                for k in range(nb):
                    W.put(q, d + k, (_rd(src, q, s + k) & dl) | (W.get(q, d + k) & dh))


def _fx33(src, W, so, do, w, h):
    """0783:0494: odd h: last line first; then pairs (top line 2k, bottom line h'-1-2k)."""
    nw = (w + 7) >> 4
    top, bot = 0, h - 1
    if h & 1:
        _line(src, W, so + 80 * bot, do + 80 * bot, nw)
        h -= 1
        bot -= 1
    for k in range(h >> 1):
        _line(src, W, so + 80 * top, do + 80 * top, nw)
        _line(src, W, so + 80 * bot, do + 80 * bot, nw)
        top += 2
        bot -= 2


def _fx34(src, W, so, do, w, h):
    """0783:08DA: nb/2 steps; step k (1..): even lines get the rightmost 2k bytes of the
    source line at their left edge, odd lines the leftmost 2k bytes at their right edge.
    Destination segments are always A800/B000/B800/E000 (VRAM, the A6h access page)."""
    nb = (w + 7) >> 3
    for k in range(1, (nb >> 1) + 1):
        n = 2 * k
        for j in range(h >> 1):
            a, b = 2 * j, 2 * j + 1
            for q in range(4):
                for t in range(n):
                    W.put(q, do + 80 * a + t, _rd(src, q, so + 80 * a + nb - n + t))
            for q in range(4):
                for t in range(n):
                    W.put(q, do + 80 * b + nb - n + t, _rd(src, q, so + 80 * b + t))
