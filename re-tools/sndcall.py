#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""sndcall - exercise M.EXE's sound layer (segments 048F/04E4) under re-tools/mcall.py with a fake
resident PMD at INT 60h (and optionally a fake PPSDRV at INT 64h), logging every driver call.

Used for docs/re/sound.md.  Run:  $EMU_PYTHON -I re-tools/sndcall.py
It prints, for each scenario, the INT 60h/64h calls (AX, DX) and the files the game tried to open.

The fake PMD answers like PMD 4.7g (INT 60h as in lrvne docs/pmd.md):
AH=06h -> DS:DX = 8 KB music buffer, AH=22h -> AL=/M (8), AH=09h -> AL = board type
(0 = PMD.COM, 1 = PMDB2, 2 = PMD86, FFh = PMD without board), AH=17h -> AL = pps flag,
AH=05h -> AX = measure counter (self.measure).  The VSYNC interrupt is simulated by advancing the
engine's timer slots (0B91:0000, see 075A:00A6) once per pass through the fade's polling loop.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcall import M, UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_AX, UC_X86_REG_DX, UC_X86_REG_DS, UC_X86_REG_CX  # noqa: E402

FAKESEG = 0xC000     # fake PMD code (C000-DFFF is mapped RAM in mcall, outside the DOS arena)
PPSSEG = 0xC100


class SndM(M):
    def __init__(self, board=0, pmd=True, pps=False, pps_flag=0, **kw):
        super().__init__(**kw)
        self.board, self.pps_flag = board, pps_flag
        self.calls = []
        self.opens = []
        self.measure = 0
        uc = self.uc
        if pmd:
            # EB 11 'P' 'M' 'D' 47 67 ... ; entry at +13h = IRET (handled in a code hook first)
            img = bytearray(0x20)
            img[0:7] = b'\xEB\x11PMDGg'
            img[0x13] = 0xCF
            uc.mem_write(FAKESEG * 16, bytes(img))
            uc.mem_write(0x60 * 4, struct.pack('<HH', 0, FAKESEG))
            uc.hook_add(UC_HOOK_CODE, self._pmd, begin=FAKESEG * 16 + 0x13, end=FAKESEG * 16 + 0x13)
        if pps:
            img = bytearray(0x20)
            img[0:5] = b'\xEB\x07PMP'
            img[0x09] = 0xCF
            uc.mem_write(PPSSEG * 16, bytes(img))
            uc.mem_write(0x64 * 4, struct.pack('<HH', 0, PPSSEG))
            uc.hook_add(UC_HOOK_CODE, self._pps, begin=PPSSEG * 16 + 0x09, end=PPSSEG * 16 + 0x09)
        self.musbuf = (FAKESEG + 0x10) * 16      # DS:DX returned by AH=06h = (FAKESEG+10h):0000
        # simulated VSYNC: once per pass through mus_fade_stop's busy-wait loop (04E4:0199)
        lin = self.lin(self.seg(0x04E4), 0x0199)
        uc.hook_add(UC_HOOK_CODE, self._vsync, begin=lin, end=lin)
        self.vsyncs = 0
        orig = self._int21

        def int21():
            ax = uc.reg_read(UC_X86_REG_AX)
            if ax >> 8 == 0x3D:
                ds, dx = uc.reg_read(UC_X86_REG_DS), uc.reg_read(UC_X86_REG_DX)
                self.opens.append(self.cstr(ds, dx).decode('cp932', 'replace'))
            return orig()
        self._int21 = int21

    def _pmd(self, uc, address, size, ud):
        ax, dx = uc.reg_read(UC_X86_REG_AX), uc.reg_read(UC_X86_REG_DX)
        ah, al = ax >> 8, ax & 0xFF
        self.calls.append(('60', ah, al, self.vsyncs))
        if ah == 0x06:
            uc.reg_write(UC_X86_REG_DS, FAKESEG + 0x10)
            uc.reg_write(UC_X86_REG_DX, 0)
        elif ah == 0x22:
            uc.reg_write(UC_X86_REG_AX, (ax & 0xFF00) | 8)
            uc.reg_write(UC_X86_REG_DX, (dx & 0xFF00) | 0)
        elif ah == 0x09:
            uc.reg_write(UC_X86_REG_AX, 0x4700 | (self.board & 0xFF))
            uc.reg_write(UC_X86_REG_DX, 0x4767)
        elif ah == 0x17:
            uc.reg_write(UC_X86_REG_AX, (ax & 0xFF00) | self.pps_flag)
        elif ah == 0x05:
            uc.reg_write(UC_X86_REG_AX, self.measure)

    def _pps(self, uc, address, size, ud):
        ax = uc.reg_read(UC_X86_REG_AX)
        self.calls.append(('64', ax >> 8, ax & 0xFF, self.vsyncs))
        if ax >> 8 == 0x04:
            uc.reg_write(UC_X86_REG_DS, 0x9200)
            uc.reg_write(UC_X86_REG_DX, 0x0000)
            uc.reg_write(UC_X86_REG_CX, 0xF000)

    def _vsync(self, uc, address, size, ud):
        self.vsyncs += 1
        base = self.lin(self.seg(0x0B91), 0)
        for i in range(16):
            s = base + 16 * i
            used, done, cnt, tgt = struct.unpack('<HHII', bytes(uc.mem_read(s, 12)))
            if used == 1 and done != 1:
                cnt += 1
                uc.mem_write(s + 4, struct.pack('<I', cnt))
                if struct.unpack('<i', struct.pack('<I', tgt))[0] <= cnt:
                    uc.mem_write(s + 2, struct.pack('<H', 1))

    def c(self, seg, off, args=()):
        """far call, return AX as a signed 16-bit value"""
        ax = self.call(seg, off, args)[0]
        return ax - 0x10000 if ax & 0x8000 else ax

    def sstr(self, s):
        """put a NUL-terminated string in guest memory, return (off, seg) for a far arg"""
        seg = self.alloc(len(s) + 1)
        self.poke(seg, 0, s.encode() + b'\0')
        return seg

    def play(self, name, vol=100):
        seg = self.sstr(name)
        return self.c(0x04E4, 0x0034, [0, seg, vol])

    def drain(self):
        c, o = self.calls, self.opens
        self.calls, self.opens = [], []
        return c, o


def fmt(calls):
    return ' '.join('INT%s/%02X%s' % (i, ah, (':%02X' % al) if ah in (0x19, 0x1E) else '') +
                    (('@v%d' % v) if v else '') for i, ah, al, v in calls)


def main():
    pc98 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'resources', 'original', 'pc98')

    print('--- no driver at INT 60h (GAME.BAT option 4)')
    m = SndM(pmd=False)
    print('mus_init ->', m.c(0x04E4, 0x0004), ' mus_state ->', hex(m.c(0x04E4, 0x01D8)),
          ' mus_measure ->', m.c(0x04E4, 0x01E9), ' play ->', m.play('va_m01.m'),
          ' fade ->', m.c(0x04E4, 0x00F0, [320]))
    print('   calls/opens:', m.drain())

    for board, label in ((0, 'PMD.COM (26K/86 via PMD.COM)'), (2, 'PMD86'), (1, 'PMDB2'),
                         (0xFF, 'PMD.COM without a board')):
        print('--- fake PMD, AH=09h AL=%02X: %s' % (board, label))
        m = SndM(board=board, pps=(board == 0), pps_flag=1 if board == 0 else 0)
        m.c(0x0752, 0x0002)                       # timer init (VSYNC), as run_game does
        r = m.c(0x04E4, 0x0004)
        c, o = m.drain()
        print('mus_init ->', r, fmt(c), ' board var DS:17A4 =', hex(m.word(m.ds, 0x17A4)))
        for name in ('va_m01.m', 'va_m01.m', 'va_m02.m', 'va_m03.m'):
            r = m.play(name)
            c, o = m.drain()
            st = m.c(0x04E4, 0x01D8)
            extra = ''
            if o:
                want = open(os.path.join(pc98, o[-1].upper()), 'rb').read() if os.path.exists(
                    os.path.join(pc98, o[-1].upper())) else None
                got = bytes(m.uc.mem_read(m.musbuf, len(want))) if want else None
                extra = ' buffer==file:%s' % (got == want)
            print('play(%s) -> %s state=%02X opens=%s %s%s' % (name, r, st, o, fmt(c), extra))
        m.measure = 4
        print('mus_measure (PMD measure=4) ->', m.c(0x04E4, 0x01E9), fmt(m.drain()[0]))
        v0 = m.vsyncs
        m.c(0x04E4, 0x00F0, [320])
        c, o = m.drain()
        vols = [al for i, ah, al, v in c if ah == 0x19]
        print('fade(320): %d VSYNCs, %d AH=19h writes, AL first..last %s ... %s, then %s; state=%02X' % (
            m.vsyncs - v0, len(vols), vols[:6], vols[-4:], fmt(c[-1:]), m.c(0x04E4, 0x01D8)))
        print('mus_measure after stop ->', m.c(0x04E4, 0x01E9))
        if board == 0:
            tab = {}
            for v in (0, 1, 25, 50, 75, 99, 100):
                m.c(0x048F, 0x0227, [v])
                tab[v] = '%02X' % m.drain()[0][-1][2]
            print('pmd_set_vol(vol%) -> AH=19h AL:', tab)
            m.play('va_m04.m')
            m.drain()
            r = m.c(0x04E4, 0x0021)
            print('mus_term while playing ->', fmt(m.drain()[0][-1:]))


if __name__ == '__main__':
    main()
