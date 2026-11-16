#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""gfx_pal.py - model of Virgin Angel's palette operations (ops 30, 1A, 2F), stdlib only.

A palette is 16 (r, g, b) tuples of 4-bit levels (scb.py's Scenario.pal entries, nibble order
R, G, B).  The engine keeps it as 48 bytes R[16] G[16] B[16] and programs the analog palette
with  out A8h,i / AEh,B / ACh,R / AAh,G  for i = 0..15 at the start of a VSYNC (00DD:01D0).

Fades shift every component by the same signed amount d and clamp to 0..15 (0315:0202); d is
recomputed once per VSYNC from the elapsed time.  The functions return the list of palettes
the original writes to the DAC, in order, given the VSYNC count (ticks) - see
docs/re/graphics.md section 5; re-tools/pal_verify.py checks them against the original.
"""

BLACK = [(0, 0, 0)] * 16
WHITE = [(15, 15, 15)] * 16


class State:
    """The engine's palette state: the current palette (0BA1:00A0) and the two statics that
    remember the last fade offset (DS:00DE for fade-in, DS:00E0 for fade-out; 0 at start)."""

    def __init__(self):
        self.cur = list(BLACK)
        self.last_in = 0
        self.last_out = 0


def shift(pal, d):
    """0315:0202: clamp(c + d); d > 14 gives white, d < -14 black (whole table copies)."""
    if d > 14:
        return list(WHITE)
    if d < -14:
        return list(BLACK)
    cl = lambda v: 15 if v > 15 else (0 if v < 0 else v)  # noqa: E731
    return [(cl(r + d), cl(g + d), cl(b + d)) for r, g, b in pal]


def _tdiv(a, b):
    """C long division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def ticks_for(t):
    """VSYNCs until a timer of t hundredths of a second expires (075A:011E/00A6): the counter
    is compared after each VSYNC, so at least one."""
    return max(t * 564 // 1000, 1)


def elapsed(k):
    """075A:01F7: hundredths of a second after k VSYNCs."""
    return k * 1000 // 564


def set_pal(st, pal, out):
    """0315:0144: store as current and program it."""
    st.cur = list(pal)
    out.append(list(pal))


def fade_in_core(st, pal, t, out):
    """0315:031E: fade from black (or from white when the current palette is all white) to
    `pal` over t/100 s, then set `pal` (0315:0144)."""
    if all(c == (15, 15, 15) for c in st.cur):
        s = 15 - min(min(c) for c in pal)
    else:
        s = -max(max(c) for c in pal)
    for k in range(ticks_for(t)):
        d = _tdiv(s * (t - elapsed(k)), t)
        if d != st.last_in:
            st.last_in = d
            out.append(shift(pal, d))
    set_pal(st, pal, out)


def fade_in(st, pal, t, out):
    """op 30 (0315:0176): t > 0: fade_in_core; then set `pal` (again)."""
    if t > 0:
        fade_in_core(st, pal, t, out)
    set_pal(st, pal, out)


def fade_out(st, to_white, t, out):
    """op 1A (0315:04E2): fade the current palette to black (to_white = 0) or white over
    t/100 s; t < 1: set black/white at once."""
    end = WHITE if to_white else BLACK
    if t >= 1:
        base = st.cur
        if to_white:
            s = 15 - min(min(c) for c in base)
        else:
            s = -max(max(c) for c in base)
        for k in range(ticks_for(t)):
            d = _tdiv(s * elapsed(k), t)
            if d != st.last_out:
                st.last_out = d
                out.append(shift(base, d))
    set_pal(st, end, out)


def flash(st, t, out):
    """op 2F (0315:06C2): fade to white in t/2, back to the saved palette in t/2."""
    saved = list(st.cur)
    half = _tdiv(t, 2)
    fade_out(st, 1, half, out)
    fade_in_core(st, saved, half, out)
    set_pal(st, saved, out)
