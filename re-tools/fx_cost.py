#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""fx_cost.py - what op 32 (rect_copy and its transitions) costs on the reference machine.

    fx_cost.py consts [-o FILE]      the engine's clock constants (source/engine/gfx/fx_clk.h)
    fx_cost.py parts                 the clocks between consecutive writes, as measured
    fx_cost.py time [CPU_PER_FRAME]  how long the scenario's transitions take (default 177242:
                                     an 80286 at 10 MHz)

The unit is the 80286 clock of re-tools/m286.py. The engine's transitions
(source/engine/gfx/fx.c) are the original's loops written out, and they charge the clocks of
the original's instructions in blocks, each block before the write that ends it. `consts`
makes those blocks:
  * the routines' own blocks (segment 0783, fx31_wait in 00DD): sums of the clock table over
    address ranges of M.EXE, along the straight path through each range. A range ends at a
    write or at a branch; the branches are the engine's (J_TAKEN etc.);
  * the parts whose path depends on the operands, measured by running the original's op 32
    (0315:07CB) under emulation: the head (rect_copy's start to 00DD:059D, where the paths of
    the plane selection join, for each source and destination kind: 10, 11, 12, other), the
    switch (00DD:059D to the routine's first instruction, per effect) and the tail (the
    routine's retf to op 32's return: the rest of the dispatcher, win_snapshot, rect_copy's
    exit). They include mouse_hide with the pointer closed.
tests/check_fx.py compares the engine's clock at every write with the original's under
emulation, so any constant that is wrong shows there. `parts` prints the measured deltas.
"""
import collections
import os
import random
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))

REF_CPF = 177242                    # 10 MHz / 56.42 Hz
ROUTINES = {10: 0x0000, 20: 0x007C, 30: 0x0350, 31: 0x07C0, 32: 0x05DD, 33: 0x0494,
            34: 0x08DA}
RETF = {10: 0x007B, 20: 0x020F, 30: 0x0493, 31: 0x08D9, 32: 0x072B, 33: 0x05D8, 34: 0x09FE}
JOIN = (0x00DD, 0x059D)
FX = 0x0783


class Code:
    """static clock sums over M.EXE's image"""

    def __init__(self):
        import mexe
        from capstone import Cs, CS_ARCH_X86, CS_MODE_16
        exe = os.path.join(ROOT, 'resources/derived/M_unpacked.EXE')
        self.img = mexe.Image(open(exe, 'rb').read()).image
        self.cs = Cs(CS_ARCH_X86, CS_MODE_16)
        self.cs.detail = True

    def insns(self, seg, a, b):
        p = seg * 16
        out = list(self.cs.disasm(self.img[p + a:p + b], a))
        if not out or out[-1].address + out[-1].size != b:
            raise ValueError('%04X:%04X..%04X does not end on an instruction' % (seg, a, b))
        return out

    def blk(self, a, b, seg=FX):
        """clocks of [a, b): every instruction once, a branch in it as not taken"""
        from m286 import clocks
        n = 0
        for i in self.insns(seg, a, b):
            if i.mnemonic.split()[0].startswith('rep'):
                raise ValueError('rep inside %04X:%04X..%04X' % (seg, a, b))
            c, br = clocks(i)
            n += br[1] if br is not None else c
        return n


def statics(code):
    """name -> clocks, checking that blocks the engine treats as one cost are equal"""
    b = code.blk
    k = collections.OrderedDict()

    def same(name, *ranges):
        v = [b(x, y) for x, y in ranges]
        if len(set(v)) != 1:
            raise ValueError('%s: the ranges cost %s' % (name, v))
        k[name] = v[0]

    # 10: fx_copy
    k['FX10_SETUP'] = b(0x0000, 0x0035)
    same('FX10_PLANE_PRE', (0x0035, 0x003F), (0x0043, 0x004D), (0x0051, 0x005B), (0x005F, 0x0069))
    same('FX10_PLANE_POST', (0x0041, 0x0043), (0x004F, 0x0051), (0x005D, 0x005F), (0x006B, 0x006D))
    k['FX10_LINE_POST'] = b(0x006D, 0x0074)              # then jne
    k['FX10_EXIT'] = b(0x0076, 0x007B)
    # 20: fx_masked
    k['FX20_SETUP'] = b(0x007C, 0x00B4)
    k['FX20_LINE_PRE'] = b(0x00B4, 0x00B9)
    k['FX20_BYTE_PRE'] = b(0x00B9, 0x00D0)
    same('FX20_PIXEL', *[(0x00D0 + 0x1C * p, 0x00E7 + 0x1C * p) for p in range(8)])  # then jne
    k['FX20_PIXEL_OR'] = b(0x00E9, 0x00EC)              # colour 8: or ch, 1
    k['FX20_MASK'] = b(0x01B0, 0x01B4)                  # then je
    k['FX20_MASKED_PRE'] = b(0x01B6, 0x01C0)
    same('FX20_MASKED_AND', (0x01C0, 0x01C5), (0x01C7, 0x01CC), (0x01CE, 0x01D3), (0x01D5, 0x01DA))
    same('FX20_MASKED_OR', (0x01C5, 0x01C7), (0x01CC, 0x01CE), (0x01D3, 0x01D5), (0x01DA, 0x01DC))
    k['FX20_MASKED_END'] = b(0x01DC, 0x01DE)            # jmp
    same('FX20_OPAQUE', (0x01DE, 0x01E3), (0x01E3, 0x01E8), (0x01E8, 0x01ED), (0x01ED, 0x01F2))
    k['FX20_BYTE_POST'] = b(0x01F2, 0x01F5)             # then loop, jmp
    k['FX20_JMP'] = b(0x01F7, 0x01F9)
    k['FX20_LINE_POST'] = b(0x01FC, 0x0205)             # then je (, jmp)
    k['FX20_EXIT'] = b(0x020A, 0x020F)
    # 30: fx_dissolve4
    k['FX30_SETUP'] = b(0x0350, 0x03CB)
    k['FX30_PASS_PRE'] = b(0x03CB, 0x03D6)
    k['FX30_LINE_PRE'] = b(0x03D6, 0x03E6)              # then rep movsw into the temporary
    same('FX30_TMP_PLANE', (0x03E8, 0x03F0), (0x03F2, 0x03FA), (0x03FC, 0x0404))
    k['FX30_TMP_END'] = b(0x0406, 0x0411)
    same('FX30_PLANE_PRE', (0x0411, 0x041A), (0x0428, 0x0431), (0x043F, 0x0448), (0x0456, 0x045F))
    same('FX30_WORD', (0x041A, 0x0425), (0x0431, 0x043C), (0x0448, 0x0453), (0x045F, 0x046A))
    same('FX30_PLANE_POST', (0x0427, 0x0428), (0x043E, 0x043F), (0x0455, 0x0456))
    k['FX30_LINE_POST'] = b(0x046C, 0x047A)             # then loop, jmp
    k['FX30_JMP'] = b(0x047C, 0x047E)
    k['FX30_PASS_POST'] = b(0x0481, 0x0487)             # then loop, jmp
    k['FX30_EXIT'] = b(0x048E, 0x0493)
    # 31: fx_dissolve64, fx31_wait
    k['FX31_SETUP'] = b(0x07C0, 0x07FE)
    k['FX31_STEP_PRE'] = b(0x07FE, 0x082A)
    k['FX31_LINE_PRE'] = b(0x082A, 0x0833)              # then jne
    k['FX31_PLANE0_PRE'] = b(0x0835, 0x0847)
    same('FX31_WORD', (0x0847, 0x0852), (0x0863, 0x086E), (0x087F, 0x088A), (0x089B, 0x08A6))
    same('FX31_PLANE_NEXT', (0x0854, 0x0863), (0x0870, 0x087F), (0x088C, 0x089B))
    k['FX31_PLANE3_POST'] = b(0x08A8, 0x08AB)
    k['FX31_LINE_POST'] = b(0x08AB, 0x08B4)             # then loop, jmp
    k['FX31_JMP'] = b(0x08B6, 0x08B8)
    k['FX31_CALL'] = b(0x08BB, 0x08C7)                  # lcall [bp+22h]: fx31_wait
    k['FX31_WAIT_PRE'] = b(0x04F9, 0x04FE, seg=0x00DD)
    k['FX31_WAIT_READ'] = b(0x04FE, 0x0506, seg=0x00DD)  # ends reading the VSYNC counter
    k['FX31_WAIT_TEST'] = b(0x0506, 0x0510, seg=0x00DD)  # then jl
    k['FX31_WAIT_LAST'] = b(0x0512, 0x0516, seg=0x00DD)  # ends reading the counter again
    k['FX31_WAIT_END'] = b(0x0516, 0x051A, seg=0x00DD)
    k['FX31_STEP_POST'] = b(0x08C7, 0x08CD)             # then loop, jmp
    k['FX31_EXIT'] = b(0x08D4, 0x08D9)
    # 32: fx_checker_tb
    k['FX32_SETUP'] = b(0x05DD, 0x0638)                 # then je (to the next instruction)
    k['FX32_SETUP2'] = b(0x063A, 0x063D)
    k['FX32_ITER_PRE'] = b(0x063D, 0x0653)
    same('FX32_BYTE', *[(0x0653 + 0x18 * p, 0x065C + 0x18 * p) for p in range(4)],
         *[(0x06B9 + 0x18 * p, 0x06C2 + 0x18 * p) for p in range(4)])
    same('FX32_PLANE_NEXT', *[(0x065E + 0x18 * p, 0x066B + 0x18 * p) for p in range(3)],
         *[(0x06C4 + 0x18 * p, 0x06D1 + 0x18 * p) for p in range(3)])
    k['FX32_BOTTOM_PRE'] = b(0x06A6, 0x06B9)
    k['FX32_ITER_POST'] = b(0x070C, 0x071F)             # then loop, jmp
    k['FX32_JMP'] = b(0x0721, 0x0723)
    k['FX32_EXIT'] = b(0x0726, 0x072B)
    # 33: fx_interlace_tb
    k['FX33_SETUP'] = b(0x0494, 0x04E9)                 # then je
    k['FX33_ODD_PRE'] = b(0x04EB, 0x04FE)
    same('FX33_PLANE_NEXT', (0x0500, 0x050C), (0x050E, 0x051A), (0x051C, 0x0528),
         (0x054F, 0x055B), (0x055D, 0x0569), (0x056B, 0x0577),
         (0x058D, 0x0599), (0x059B, 0x05A7), (0x05A9, 0x05B5))
    k['FX33_ODD_POST'] = b(0x052A, 0x0538)
    k['FX33_PAIRS'] = b(0x0538, 0x053D)
    k['FX33_TOP_PRE'] = b(0x053D, 0x054D)
    k['FX33_BOTTOM_PRE'] = b(0x0579, 0x058B)
    k['FX33_PAIR_POST'] = b(0x05B7, 0x05CE)             # then je (, jmp)
    k['FX33_JMP'] = b(0x05D0, 0x05D3)
    k['FX33_EXIT'] = b(0x05D3, 0x05D8)
    # 34: fx_slide_lr
    k['FX34_SETUP'] = b(0x08DA, 0x093C)
    k['FX34_STEP_PRE'] = b(0x093C, 0x0946)
    k['FX34_EVEN_PRE'] = b(0x0946, 0x095B)
    same('FX34_PLANE_NEXT', (0x095D, 0x096B), (0x096D, 0x097B), (0x097D, 0x098B),
         (0x09AD, 0x09BB), (0x09BD, 0x09CB), (0x09CD, 0x09DB))
    k['FX34_ODD_PRE'] = b(0x098D, 0x09AB)
    k['FX34_PAIR_POST'] = b(0x09DD, 0x09E8)             # then loop, jmp
    k['FX34_JMP'] = b(0x09EA, 0x09EC)
    k['FX34_STEP_POST'] = b(0x09EF, 0x09F3)             # then loop, jmp
    k['FX34_EXIT'] = b(0x09FA, 0x09FE)
    return k


class Op32:
    """the original's op 32 under the timed machine"""

    def __init__(self, cpu_per_frame=10 ** 12):
        from m286 import TM
        self.m = m = TM(cpu_per_frame=cpu_per_frame, trace_ports=False)
        m.timing = False
        if m.call(0x0315, 0x000E)[0] != 1:
            sys.exit('gfx_init failed under emulation')
        m.timing = True
        self.op = m.alloc(64)
        pts = [JOIN] + [(FX, o) for o in ROUTINES.values()] + [(FX, o) for o in RETF.values()]
        for s, o in pts:
            m.stamp_at[m.lin(m.seg(s), o)] = (s, o)

    def run(self, src, sx, sy, w, h, dst, dx, dy, eff, sp=None, dp=None, log=True):
        """op 32 on planes sp/dp (random when None); returns (clocks, writes, stamps), the
        writes as (plane, offset, value, clock) and the stamps counted from rect_copy's start;
        self.frames: the writes as (plane, offset, value, frame, clocks into it)"""
        m = self.m
        rnd = random.Random('%r' % ((src, sx, sy, w, h, dst, dx, dy, eff),))
        for b, p in ((src, sp), (dst, dp)):
            if b in (10, 11, 12):
                m.set_buf(b, p or [bytearray(rnd.getrandbits(8) for _ in range(32000))
                                   for _ in range(4)])
        m.poke(self.op, 0, struct.pack('<9h', src, sx, sy, w, h, dst, dx, dy, eff))
        m.stamps = {}
        if log:
            m.log_writes(dst if dst in (10, 11, 12) else 10)
        m.cyc = 0                       # op 32 starts a frame (as the engine's test does)
        t0 = m.total
        f0, c0 = m.frame, m.cyc
        m.call(0x0315, 0x07CB, [0, self.op])
        t = m.total - t0
        ws = [(q, o, v, (f - f0) * m.cpf + c - c0) for (q, o, v, f, c) in m.writes] if log else []
        self.frames = [(q, o, v, f - f0, c) for (q, o, v, f, c) in m.writes] if log else []
        self.end = (m.frame - f0, m.cyc)
        m.log_writes(None)
        return t, ws, {k: v - t0 for k, v in m.stamps.items()}


KINDS = (10, 11, 12, 13)


def dynamics():
    o = Op32()
    head = []
    for s in KINDS:
        row = []
        for d in KINDS:
            _t, _w, st = o.run(s, 0, 0, 16, 1, d, 0, 0, 10, log=False)
            row.append(st[JOIN])
        head.append(row)
    switch, tail = {}, {}
    for e in (10, 20, 21, 30, 31, 32, 33, 34, 40):
        r = ROUTINES.get(e, 0)
        t, _w, st = o.run(12, 0, 0, 16, 2, 10, 0, 0, e, log=False)
        switch[e] = st[(FX, r)] - st[JOIN]
        tail[e] = t - st[(FX, RETF.get(e, RETF[10]))]
    return head, switch, tail


def consts(out):
    code = Code()
    k = statics(code)
    head, switch, tail = dynamics()
    assert switch[21] == switch[20] == switch[30] == switch[32] == switch[33] == switch[34], switch
    assert switch[40] == switch[10], switch
    assert tail[10] == tail[20] == tail[21] == tail[30] == tail[32] == tail[33] == tail[40], tail
    w = out.write
    w('/* SPDX-License-Identifier: GPL-3.0-or-later */\n')
    w('/* Clocks of M.EXE\'s op 32 on an 80286 without wait states, made by\n'
      ' * re-tools/fx_cost.py consts (the clock table: re-tools/m286.py). Do not edit. */\n')
    w('#ifndef VG_GFX_FX_CLK_H\n#define VG_GFX_FX_CLK_H\n\n')
    w('/* branches and string instructions */\n')
    w('#define J_TAKEN            7     /* jcc, jmp short */\n')
    w('#define J_NOT              3\n')
    w('#define LOOP_TAKEN         8\n')
    w('#define LOOP_NOT           4\n')
    w('#define REP_MOVS           5     /* rep movsw of n words: REP_MOVS + n * REP_MOVS_EACH */\n')
    w('#define REP_MOVS_EACH      4\n\n')
    w('/* rect_copy\'s start to 00DD:059D, by source and destination kind: 10, 11, 12, other */\n')
    w('#define FX_HEAD { \\\n')
    for i, row in enumerate(head):
        w('    { %s }%s \\\n' % (', '.join('%d' % v for v in row), ',' if i < 3 else ''))
    w('}\n')
    w('/* 00DD:059D to the routine; the routine\'s retf to op 32\'s return (with win_snapshot) */\n')
    w('#define FX_SWITCH_OTHER    %d  /* a code below 20 or above 34 */\n' % switch[10])
    w('#define FX_SWITCH_TABLE    %d  /* 20..34 through the table, except 31 */\n' % switch[20])
    w('#define FX_SWITCH_31       %d\n' % switch[31])
    w('#define FX_TAIL            %d\n' % tail[10])
    w('#define FX_TAIL_31         %d\n' % tail[31])
    w('#define FX_TAIL_34         %d\n\n' % tail[34])
    w('/* the routines (segment 0783; fx31_wait 00DD:04F9) */\n')
    for name, v in k.items():
        w('#define %-18s %d\n' % (name, v))
    w('\n#endif\n')


def parts():
    o = Op32()
    for e in (10, 20, 30, 31, 32, 33, 34):
        for (w, h) in ((48, 3), (80, 4), (24, 5)):
            t, ws, st = o.run(12, 0, 0, w, h, 10, 0, 0, e)
            ent = st[(FX, ROUTINES[e])]
            cl = [c for (_q, _o, _v, c) in ws]
            d = [cl[0] - ent] + [b - a for a, b in zip(cl, cl[1:])]
            ret = st[(FX, RETF[e])]
            print('effect %d %3dx%d: %d clocks; entry->first write %d, last write->retf %d' % (
                e, w, h, t, d[0], ret - cl[-1]))
            print('   deltas %s' % ' '.join(str(x) for x in d[1:60]))
            print('   %s' % collections.Counter(d[1:]).most_common(10))


def time(cpf):
    o = Op32()
    print('transitions at %d clocks per frame (%.2f MHz):' % (cpf, cpf * 56.42 / 1e6))
    for (src, sx, sy, w, h, dst, dx, dy, e, what) in (
            (11, 0, 0, 640, 400, 12, 0, 0, 10, 'copy 11->12, full screen'),
            (12, 0, 0, 640, 400, 10, 0, 0, 30, 'dissolve, full screen'),
            (12, 160, 48, 320, 200, 10, 160, 48, 30, 'dissolve, the background window'),
            (12, 0, 0, 640, 400, 10, 0, 0, 32, 'top and bottom, full screen'),
            (12, 0, 0, 640, 400, 10, 0, 0, 33, 'interlace, full screen'),
            (12, 0, 0, 640, 400, 10, 0, 0, 20, 'masked copy, full screen'),
            (12, 80, 39, 480, 322, 10, 80, 38, 34, 'slide (#1899)')):
        t, _w, _s = o.run(src, sx, sy, w, h, dst, dx, dy, e, log=False)
        print('  effect %2d %-34s %9d clocks  %6.1f frames  %5.2f s' % (
            e, what, t, t / cpf, t / cpf / 56.42))


def main(argv):
    if len(argv) >= 2 and argv[1] == 'consts':
        if len(argv) == 4 and argv[2] == '-o':
            with open(argv[3], 'w') as f:
                consts(f)
        else:
            consts(sys.stdout)
    elif len(argv) >= 2 and argv[1] == 'parts':
        parts()
    elif len(argv) >= 2 and argv[1] == 'time':
        time(int(argv[2]) if len(argv) > 2 else REF_CPF)
    else:
        sys.exit(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
