#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""text_render.py - render message pages and a menu with M.EXE's own text code under mcall.

Sets up the scene the way the scenario does at its first message (gfx_init 0315:000E, op 31
va_main to buffer 10, op 31 va_mw01 at (32,300) transparent, scenario palette 34, then the
window snapshot 02BE:00AC), loads CMD00.SCB/CMD00.TXB with the original loaders and calls the
message routine 0315:07FC.  Patches: the input poll 0315:0B7C returns 1 at once ("key pressed").
INT 18h AH=14h (KCG pattern read) is answered from the 16x16 XFNT font named by
$VA_KANJI_FONT (default resources/derived/fonts/k16.xfnt) if present, else with a
stand-in pattern.  A PNG is written whenever a page has been shown (0315:0ACF) and when the
page-wait icon is up (0315:0C3E); for the menu, 0315:0C4F draws the choices of a T44 menu and
choice 2 is highlighted with 02BE:0263 as the menu loop does.

Output (game imagery, git-ignored): resources/derived/text/*.png and a geometry log on stdout.
Usage: $EMU_PYTHON -I re-tools/text_render.py [MSG [MENU]]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcall import M, ROOT  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX  # noqa
import gf  # noqa: E402
import scb  # noqa: E402

OUT = os.path.join(ROOT, 'resources/derived/text')
FONT = os.environ.get('VA_KANJI_FONT', os.path.join(ROOT, 'resources/derived/fonts/k16.xfnt'))


def read_xfnt(path):
    d = open(path, 'rb').read()
    cw, ch, count = d[5], d[6], struct.unpack_from('<H', d, 8)[0]
    codes = struct.unpack_from('<%dH' % count, d, 12)
    gb = ch * cw // 8
    g = 12 + 2 * count
    return {c: d[g + i * gb:g + (i + 1) * gb] for i, c in enumerate(codes)}


class TM(M):
    def __init__(self, **kw):
        self.k16 = read_xfnt(FONT) if os.path.exists(FONT) else None
        self.kcg = []
        super().__init__(**kw)

    def _stub(self, uc, address, size, ud):
        n = address - 0xF100 * 16
        if n == 0x18:
            ax = uc.reg_read(UC_X86_REG_AX)
            if ax >> 8 == 0x14:
                jis = uc.reg_read(UC_X86_REG_DX)
                bx, cx = uc.reg_read(UC_X86_REG_BX), uc.reg_read(UC_X86_REG_CX)
                g = self.k16.get(jis) if self.k16 else None
                if g is None:   # stand-in: frame + hashed interior
                    h = (jis * 2654435761) & 0xFFFFFFFF
                    rows = []
                    for r in range(16):
                        v = 0x7FFE if r in (1, 14) else 0x4002 | (((h >> (r % 13)) & 0x3FF) << 3)
                        rows += [v >> 8, v & 0xFF]
                    g = bytes(rows)
                self.kcg.append(jis)
                uc.mem_write(bx * 16 + cx, b'\x02\x02' + g)
            self.ints.append((0x18, ax >> 8, ''))
            return
        return super()._stub(uc, address, size, ud)


def main(argv):
    msg = int(argv[1]) if len(argv) > 1 else 1
    menu = int(argv[2]) if len(argv) > 2 else 3
    os.makedirs(OUT, exist_ok=True)
    m = TM(trace_ports=False)
    g = m.seg(0x0BA1)
    # scenario + text
    name = m.alloc(32)
    m.poke(name, 0, b'CMD00.SCB\x00rb\x00')
    ax, dx = m.call(0x0886, 0x039A, [0, name, 10, name])
    m.poke(g, 0x64, struct.pack('<HH', ax, dx))
    assert m.call(0x063C, 0x00E8)[0] == 1, 'scb_load'
    assert m.call(0x0724, 0x0018)[0] == 1, 'txb_load'
    assert m.call(0x0315, 0x000E)[0] == 1, 'gfx_init'
    # scene: va_main (buffer 10), va_mw01 at (32,300) with colour 8 transparent, palette 34
    op = m.alloc(64)
    for nm, flag, x, y in (('va_main', 0, 0, 0), ('va_mw01', 1, 32, 300)):
        blk = bytearray(0x16)
        blk[0:len(nm)] = nm.encode()
        struct.pack_into('<hhhh', blk, 0x0E, flag, 10, x, y)
        m.poke(op, 0, blk)
        assert m.call(0x0315, 0x070D, [0, op])[0] == 1, nm
    pal = scb.Scenario(open(os.path.join(ROOT, 'resources/original/pc98/CMD00.SCB'), 'rb').read()).pal
    m.dac = [list(c) for c in pal[33]]
    m.call(0x02BE, 0x00AC)                       # snapshot the window area (0BA1:0074)
    m.screenshot(os.path.join(OUT, 'scene.png'))
    # input poll -> "pressed"
    m.poke(m.seg(0x0315), 0x0B7C, b'\xb8\x01\x00\xcb')
    shots = []

    def hook(uc, address, size, ud):
        tag = 'icon' if address == m.lin(m.seg(0x0315), 0x0C3E) else 'page'
        p = os.path.join(OUT, 'msg%03d_%02d_%s.png' % (msg, len(shots), tag))
        m.screenshot(p)
        shots.append(p)
    for off in (0x0ACF, 0x0C3E):
        a = m.lin(m.seg(0x0315), off)
        m.uc.hook_add(UC_HOOK_CODE, hook, begin=a, end=a)
    ts, to = m.far(g, 0x3E)
    rs, ro = m.far(ts, to + 4 * msg)
    m.kcg.clear()
    m.call(0x0315, 0x07FC, [ro, rs])
    print('message %d: %d screenshots, %d KCG reads, first %s' % (
        msg, len(shots), len(m.kcg), ' '.join('%04X' % j for j in m.kcg[:8])))
    m.screenshot(os.path.join(OUT, 'msg%03d_end.png' % msg))
    # a menu: T44 entry `menu` (1-based, as op 24's operand)
    ms, mo = m.far(g, 0x12)
    rs, ro = m.far(ms, mo + 4 * menu)
    st = m.alloc(0x40)
    m.call(0x0315, 0x0C4F, [ro, rs, 0, st])
    n = m.word(st, 0)
    rects = [struct.unpack('<4h', m.mem(st, 4 + 8 * i, 8)) for i in range(n)]
    print('menu %d: %d choices, rects (x0,x1,y0,y1) %r' % (menu, n, rects))
    m.screenshot(os.path.join(OUT, 'menu%02d.png' % menu))
    m.call(0x02BE, 0x0263, [4 + 8 * 1, st])      # highlight choice 2
    m.screenshot(os.path.join(OUT, 'menu%02d_sel2.png' % menu))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
