#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""mcall - call routines of Virgin Angel's M.EXE (PC-98) under unicorn, for verifying models.

Needs unicorn (run with $EMU_PYTHON).  The unpacked MZ
(resources/derived/M_unpacked.EXE, re-tools/exeunpack.py) is loaded as a DOS program (PSP at
segment PSP, image at PSP+10h, relocations applied).  Its Microsoft C start-up runs from the MZ
entry point with a small INT 21h in Python until main (0468:000E) is reached; from then on
`call()` runs any far routine on the initialised C runtime (heap, stdio).

    from mcall import M
    m = M(files='resources/original/pc98', args='cmd00.scb gdata.lib')
    m.call(0x0315, 0x070D, [arg words...])      # far call, cdecl: args pushed right to left
    m.lin(seg, off) / m.mem(seg, off, n) / m.poke(seg, off, data) / m.word(seg, off)
    m.ds                                        # the loaded DGROUP segment (0BAFh + base)
    m.seg(s)                                    # image-relative segment -> loaded segment
    m.vram(page)                                # [B, R, G, I] planes, 32000 bytes each
    m.ports                                     # [(dir, port, value)] port I/O log

What is modelled: INT 21h AH = 06h/07h/08h/0Bh (no key), 09h/02h/40h to stdout (captured in
m.stdout), 19h, 1Ah, 25h/35h (vectors kept in the guest IVT), 2Ah/2Ch, 30h (DOS 3.30), 33h,
3Ch/3Dh/3Eh/3Fh/42h on files below `files` (names case-insensitive, writes go to memory: m.written),
44h (devices 0-4 char devices, files block), 48h/49h/4Ah (a first-fit arena above the program),
4Ch (raises Exit).  Other interrupts with a guest vector of 0 return at once and are logged in
m.ints.  Graphics VRAM A800/B000/B800/E000 are plain planes unless the GRCG (port 7Ch/7Eh) is
on: RMW and TDW writes are modelled.  Ports are logged; reads
return 0 except GDC status (60h/A0h) which toggles VSYNC (bit 5) on every read.
"""
import os
import struct
import sys

from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INTR, UC_HOOK_INSN, UC_HOOK_CODE, \
    UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.x86_const import *  # noqa: F401,F403

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'resources/derived/M_unpacked.EXE')
PSP = 0x0800
MAIN = (0x0468, 0x000E)
DGROUP = 0x0BAF
SENTINEL = 0xF000          # far return target: F000:0000 (hlt)
STUB = 0xF100              # interrupt stubs F100:00nn -> iret, handled in Python


class Exit(Exception):
    pass


class M:
    def __init__(self, files=os.path.join(ROOT, 'resources/original/pc98'),
                 args='cmd00.scb gdata.lib', exe=EXE, trace_ports=True, max_insns=200_000_000):
        self.files = files
        self.uc = uc = Uc(UC_ARCH_X86, UC_MODE_16)
        uc.mem_map(0, 0xA8000)
        uc.mmio_map(0xA8000, 0x18000, self._vr, None, self._vw, None)
        uc.mem_map(0xC0000, 0x20000)
        uc.mmio_map(0xE0000, 0x8000, self._vr_e, None, self._vw_e, None)
        uc.mem_map(0xE8000, 0x18000)
        self.stdout = bytearray()
        self.ints = []
        self.ports = []
        self.trace_ports = trace_ports
        self.written = {}
        self.handles = {}
        self.max_insns = max_insns
        self.grcg_mode = 0
        self.grcg_tile = [0, 0, 0, 0]
        self.grcg_i = 0
        self.vsync = 0
        d = open(exe, 'rb').read()
        hdr = struct.unpack_from('<14H', d, 0)
        nrel, hpar, minalloc, maxalloc, ss, sp, _cs0, ip, cs, relo = (
            hdr[3], hdr[4], hdr[5], hdr[6], hdr[7], hdr[8], hdr[9], hdr[10], hdr[11], hdr[12])
        img = bytearray(d[hpar * 16:])
        self.base = base = PSP + 0x10
        for i in range(nrel):
            o, s = struct.unpack_from('<HH', d, relo + 4 * i)
            lin = s * 16 + o
            v = struct.unpack_from('<H', img, lin)[0]
            struct.pack_into('<H', img, lin, (v + base) & 0xFFFF)
        uc.mem_write(base * 16, bytes(img))
        self.top = base + (len(img) + 15) // 16 + minalloc
        # PSP
        psp = bytearray(256)
        psp[0:2] = b'\xcd\x20'
        struct.pack_into('<H', psp, 2, 0x9FFF)
        tail = (' ' + args).encode('ascii') if args else b''
        psp[0x80] = len(tail)
        psp[0x81:0x81 + len(tail)] = tail
        psp[0x81 + len(tail)] = 0x0D
        # environment just below the PSP
        env = PSP - 0x10
        uc.mem_write(env * 16, b'PATH=A:\\\x00COMSPEC=A:\\COMMAND.COM\x00\x00\x01\x00A:\\M.EXE\x00')
        struct.pack_into('<H', psp, 0x2C, env)
        uc.mem_write(PSP * 16, bytes(psp))
        # memory arena: blocks [(seg, paras, free)]
        self.arena = [(self.top, 0x9FFF - self.top, True)]
        self.prog_paras = self.top - PSP
        # IVT: all vectors to stubs
        for n in range(256):
            uc.mem_write(n * 4, struct.pack('<HH', n, STUB))
        uc.mem_write(STUB * 16, b'\xcf' * 256)               # iret
        uc.mem_write(SENTINEL * 16, b'\xf4')                 # hlt
        uc.hook_add(UC_HOOK_CODE, self._stub, begin=STUB * 16, end=STUB * 16 + 255)
        uc.hook_add(UC_HOOK_INTR, self._intr)
        uc.hook_add(UC_HOOK_INSN, self._in, None, 1, 0, UC_X86_INS_IN)
        uc.hook_add(UC_HOOK_INSN, self._out, None, 1, 0, UC_X86_INS_OUT)
        self.pages = [[bytearray(32768) for _ in range(4)] for _ in range(2)]
        self.draw_page = 0
        self.disp_page = 0
        self.dac = [[0, 0, 0] for _ in range(16)]
        self.dac_i = 0
        self.ds = DGROUP + base
        for r, v in ((UC_X86_REG_CS, cs + base), (UC_X86_REG_IP, ip), (UC_X86_REG_SS, ss + base),
                     (UC_X86_REG_SP, sp), (UC_X86_REG_DS, PSP), (UC_X86_REG_ES, PSP)):
            uc.reg_write(r, v)
        # run the start-up to main
        mlin = (MAIN[0] + base) * 16 + MAIN[1]
        self._run_to(mlin)
        self.main_sp = uc.reg_read(UC_X86_REG_SP)
        self.main_ss = uc.reg_read(UC_X86_REG_SS)

    # ---- memory helpers
    def seg(self, s):
        return s + self.base

    def lin(self, seg, off):
        return seg * 16 + off

    def mem(self, seg, off, n):
        return bytes(self.uc.mem_read(seg * 16 + off, n))

    def poke(self, seg, off, data):
        self.uc.mem_write(seg * 16 + off, bytes(data))

    def word(self, seg, off):
        return struct.unpack('<H', self.mem(seg, off, 2))[0]

    def far(self, seg, off):
        o, s = struct.unpack('<HH', self.mem(seg, off, 4))
        return s, o

    def cstr(self, seg, off, n=256):
        b = self.mem(seg, off, n)
        return b[:b.index(0)] if 0 in b else b

    def alloc(self, nbytes):
        """Paragraph-aligned guest buffer from the DOS arena (returns segment)."""
        seg = self._dos_alloc((nbytes + 15) // 16)
        if seg is None:
            raise MemoryError
        return seg

    # ---- execution
    def _run_to(self, lin):
        uc = self.uc
        self._stop_at = lin
        h = uc.hook_add(UC_HOOK_CODE, self._stopper, begin=lin, end=lin)
        try:
            cs = uc.reg_read(UC_X86_REG_CS)
            ip = uc.reg_read(UC_X86_REG_IP)
            uc.emu_start(cs * 16 + ip, 0xFFFFF, count=self.max_insns)
        finally:
            uc.hook_del(h)
        if self._exc:
            e, self._exc = self._exc, None
            raise e

    _exc = None

    def _stopper(self, uc, address, size, ud):
        if address == self._stop_at:
            uc.emu_stop()

    def call(self, seg, off, args=(), relative=True, ds=None):
        """Far-call seg:off (image-relative unless relative=False) with word args (cdecl).
        Returns (ax, dx)."""
        uc = self.uc
        if relative:
            seg = self.seg(seg)
        sp = self.main_sp - 0x40
        ss = self.main_ss
        words = list(args) + [SENTINEL, 0][::-1]
        # stack after pushes: [ret_ip, ret_cs, arg0, arg1, ...]
        frame = [0, SENTINEL] + [a & 0xFFFF for a in args]
        sp -= 2 * len(frame)
        uc.mem_write(ss * 16 + sp, struct.pack('<%dH' % len(frame), *frame))
        uc.reg_write(UC_X86_REG_SS, ss)
        uc.reg_write(UC_X86_REG_SP, sp)
        uc.reg_write(UC_X86_REG_DS, ds if ds is not None else self.ds)
        uc.reg_write(UC_X86_REG_ES, ds if ds is not None else self.ds)
        uc.reg_write(UC_X86_REG_CS, seg)
        uc.reg_write(UC_X86_REG_IP, off)
        self._run_to(SENTINEL * 16)
        return uc.reg_read(UC_X86_REG_AX), uc.reg_read(UC_X86_REG_DX)

    # ---- video planes with GRCG
    @staticmethod
    def _plane(lin):
        if lin >= 0xE0000:
            return 3, lin - 0xE0000
        return (lin - 0xA8000) >> 15, (lin - 0xA8000) & 0x7FFF

    def _vr(self, uc, off, size, ud):
        return self._vread(0xA8000 + off, size)

    def _vr_e(self, uc, off, size, ud):
        return self._vread(0xE0000 + off, size)

    def _vw(self, uc, off, size, value, ud):
        self._vwrite(0xA8000 + off, size, value)

    def _vw_e(self, uc, off, size, value, ud):
        self._vwrite(0xE0000 + off, size, value)

    def _vread(self, lin, size):
        pg = self.pages[self.draw_page]
        v = 0
        for i in range(size):
            p, o = self._plane(lin + i)
            if self.grcg_mode & 0x80:
                b = 0xFF
                for q in range(4):
                    if not self.grcg_mode & (1 << q):
                        b &= ~(pg[q][o] ^ self.grcg_tile[q]) & 0xFF
            else:
                b = pg[p][o]
            v |= b << (8 * i)
        return v

    def _vwrite(self, lin, size, value):
        pg = self.pages[self.draw_page]
        m = self.grcg_mode
        for i in range(size):
            p, o = self._plane(lin + i)
            b = (value >> (8 * i)) & 0xFF
            if m & 0x80:
                for q in range(4):
                    if m & (1 << q):
                        continue
                    if m & 0x40:
                        pg[q][o] = (pg[q][o] & ~b & 0xFF) | (self.grcg_tile[q] & b)
                    else:
                        pg[q][o] = self.grcg_tile[q]
            else:
                pg[p][o] = b

    def _in(self, uc, port, size, ud):
        v = 0
        if port in (0x60, 0xA0):
            self.vsync ^= 0x20
            v = 0x04 | self.vsync
        if self.trace_ports:
            self.ports.append(('in', port, v))
        return v

    def _out(self, uc, port, size, value, ud):
        if port == 0xA6:
            self.draw_page = value & 1
        elif port == 0xA4:
            self.disp_page = value & 1
        elif port == 0xA8:
            self.dac_i = value & 15
        elif port in (0xAA, 0xAC, 0xAE):
            self.dac[self.dac_i][{0xAC: 0, 0xAA: 1, 0xAE: 2}[port]] = value & 15
        elif port == 0x7C:
            self.grcg_mode = value & 0xFF
            self.grcg_i = 0
        elif port == 0x7E:
            self.grcg_tile[self.grcg_i & 3] = value & 0xFF
            self.grcg_i += 1
        if self.trace_ports:
            self.ports.append(('out', port, value))

    def vram(self, page=None):
        """The four planes (B, R, G, I) of a page (default: the displayed one), 32000 bytes each."""
        pg = self.pages[self.disp_page if page is None else page]
        return [bytes(p[:32000]) for p in pg]

    def screenshot(self, path, page=None):
        """PNG (needs Pillow) of a page with the current DAC (4-bit -> 8-bit)."""
        from PIL import Image
        pl = self.vram(page)
        im = Image.new('P', (640, 400))
        pix = bytearray(640 * 400)
        for o in range(32000):
            b, r, g, i = pl[0][o], pl[1][o], pl[2][o], pl[3][o]
            for k in range(8):
                m = 0x80 >> k
                pix[o * 8 + k] = (1 if b & m else 0) | (2 if r & m else 0) | (4 if g & m else 0) | (8 if i & m else 0)
        im.putdata(pix)
        pal = []
        for r, g, b in self.dac:
            pal += [r * 17, g * 17, b * 17]
        im.putpalette(pal + [0] * (768 - len(pal)))
        im.save(path)

    # ---- DOS
    def _dos_alloc(self, paras):
        for i, (s, n, free) in enumerate(self.arena):
            if free and n >= paras:
                self.arena[i:i + 1] = [(s, paras, False)] + ([(s + paras, n - paras, True)] if n > paras else [])
                return s
        return None

    def _largest(self):
        return max([n for s, n, f in self.arena if f] + [0])

    def _stub(self, uc, address, size, ud):
        n = address - STUB * 16
        # apply pending GRCG writes first
        try:
            if n == 0x21:
                self._int21()
            else:
                ah = uc.reg_read(UC_X86_REG_AX) >> 8
                ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)
                ip, cs = struct.unpack('<HH', bytes(uc.mem_read(ss * 16 + sp, 4)))
                self.ints.append((n, ah, '%04X:%04X' % (cs - self.base, ip)))
        except Exit as e:
            self._exc = e
            uc.emu_stop()

    def _intr(self, uc, intno, ud):
        cs, ip = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
        flags = uc.reg_read(UC_X86_REG_EFLAGS) & 0xFFFF
        sp = (uc.reg_read(UC_X86_REG_SP) - 6) & 0xFFFF
        ss = uc.reg_read(UC_X86_REG_SS)
        uc.mem_write(ss * 16 + sp, struct.pack('<HHH', ip, cs, flags))
        uc.reg_write(UC_X86_REG_SP, sp)
        off, seg = struct.unpack('<HH', bytes(uc.mem_read(intno * 4, 4)))
        uc.reg_write(UC_X86_REG_EFLAGS, flags & ~0x0300)
        uc.reg_write(UC_X86_REG_CS, seg)
        uc.reg_write(UC_X86_REG_IP, off)

    def _cf(self, v):
        uc = self.uc
        ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)
        fl = struct.unpack('<H', bytes(uc.mem_read(ss * 16 + sp + 4, 2)))[0]
        fl = (fl | 1) if v else (fl & ~1)
        uc.mem_write(ss * 16 + sp + 4, struct.pack('<H', fl))

    def _path(self, seg, off):
        name = self.cstr(seg, off).decode('cp932', 'replace')
        name = name.replace('\\', '/').replace('¥', '/').split(':')[-1].split('/')[-1]
        for f in os.listdir(self.files):
            if f.lower() == name.lower():
                return os.path.join(self.files, f), name
        return None, name

    def _int21(self):
        uc = self.uc
        R = lambda r: uc.reg_read(r)  # noqa: E731
        W = uc.reg_write
        ax, bx, cx, dx = R(UC_X86_REG_AX), R(UC_X86_REG_BX), R(UC_X86_REG_CX), R(UC_X86_REG_DX)
        ds, es = R(UC_X86_REG_DS), R(UC_X86_REG_ES)
        ah, al = ax >> 8, ax & 0xFF
        ok = lambda: self._cf(False)  # noqa: E731

        def err(code):
            W(UC_X86_REG_AX, code)
            self._cf(True)
        if ah == 0x30:
            W(UC_X86_REG_AX, 0x1E03)
            W(UC_X86_REG_BX, 0)
            W(UC_X86_REG_CX, 0)
        elif ah in (0x25,):
            uc.mem_write(al * 4, struct.pack('<HH', dx, ds))
        elif ah == 0x35:
            o, s = struct.unpack('<HH', bytes(uc.mem_read(al * 4, 4)))
            W(UC_X86_REG_BX, o)
            W(UC_X86_REG_ES, s)
        elif ah == 0x4A:
            # resize the program block (es = PSP) or an arena block
            if es == PSP:
                want = bx
                free_after = self.arena[0][1] if self.arena and self.arena[0][2] else 0
                avail = self.prog_paras + free_after
                if want > avail:
                    W(UC_X86_REG_BX, avail)
                    return err(8)
                delta = want - self.prog_paras
                self.prog_paras = want
                s, n, f = self.arena[0]
                self.arena[0] = (s + delta, n - delta, f)
                ok()
            else:
                for i, (s, n, f) in enumerate(self.arena):
                    if s == es:
                        nxt = self.arena[i + 1] if i + 1 < len(self.arena) else None
                        room = n + (nxt[1] if nxt and nxt[2] else 0)
                        if bx > room:
                            W(UC_X86_REG_BX, room)
                            return err(8)
                        rest = room - bx
                        new = [(s, bx, False)] + ([(s + bx, rest, True)] if rest else [])
                        self.arena[i:i + (2 if nxt and nxt[2] else 1)] = new
                        return ok()
                err(9)
        elif ah == 0x48:
            s = self._dos_alloc(bx)
            if s is None:
                W(UC_X86_REG_BX, self._largest())
                return err(8)
            W(UC_X86_REG_AX, s)
            ok()
        elif ah == 0x49:
            for i, (s, n, f) in enumerate(self.arena):
                if s == es:
                    self.arena[i] = (s, n, True)
            ok()
        elif ah in (0x02,):
            self.stdout.append(dx & 0xFF)
        elif ah == 0x09:
            b = self.mem(ds, dx, 4096)
            self.stdout += b[:b.index(b'$')]
        elif ah in (0x06, 0x07, 0x08):
            W(UC_X86_REG_AX, ax & 0xFF00)
        elif ah == 0x0B:
            W(UC_X86_REG_AX, ax & 0xFF00)
        elif ah == 0x19:
            W(UC_X86_REG_AX, ax & 0xFF00)
        elif ah == 0x1A:
            self.dta = (ds, dx)
        elif ah == 0x2A:
            W(UC_X86_REG_CX, 1995)
            W(UC_X86_REG_DX, 0x0301)
        elif ah == 0x2C:
            W(UC_X86_REG_CX, 0)
            W(UC_X86_REG_DX, 0)
        elif ah == 0x33:
            W(UC_X86_REG_DX, 0)
        elif ah == 0x44:
            if al == 0:
                W(UC_X86_REG_DX, 0x80D3 if bx < 5 else 0x0002)
                ok()
            else:
                ok()
        elif ah in (0x3D, 0x3C):
            p, name = self._path(ds, dx)
            if ah == 0x3D and p is None and name.lower() not in self.written:
                return err(2)
            if ah == 0x3C:
                self.written[name.lower()] = bytearray()
                data = self.written[name.lower()]
            elif name.lower() in self.written:
                data = self.written[name.lower()]
            else:
                data = bytearray(open(p, 'rb').read())
            h = 5
            while h in self.handles:
                h += 1
            self.handles[h] = {'name': name.lower(), 'data': data, 'pos': 0,
                               'write': ah == 0x3C or (al & 3) != 0}
            W(UC_X86_REG_AX, h)
            ok()
        elif ah == 0x3E:
            f = self.handles.pop(bx, None)
            if f and f['write']:
                self.written[f['name']] = f['data']
            ok()
        elif ah == 0x3F:
            if bx in self.handles:
                f = self.handles[bx]
                b = f['data'][f['pos']:f['pos'] + cx]
                f['pos'] += len(b)
                uc.mem_write(ds * 16 + dx, bytes(b))
                W(UC_X86_REG_AX, len(b))
                ok()
            elif bx == 0:
                W(UC_X86_REG_AX, 0)
                ok()
            else:
                err(6)
        elif ah == 0x40:
            b = self.mem(ds, dx, cx)
            if bx in (1, 2):
                self.stdout += b
            elif bx in self.handles:
                f = self.handles[bx]
                d = f['data']
                p = f['pos']
                if p > len(d):          # written after a seek past the end: DOS extends the
                    d.extend(bytes(p - len(d)))     # file (the gap here: zeros)
                d[p:p + len(b)] = b
                f['pos'] = p + len(b)
            W(UC_X86_REG_AX, cx)
            ok()
        elif ah == 0x42:
            f = self.handles.get(bx)
            if not f:
                return err(6)
            off = (cx << 16 | dx)
            if off & 0x80000000:
                off -= 1 << 32
            p = [0, f['pos'], len(f['data'])][al] + off
            f['pos'] = p
            W(UC_X86_REG_AX, p & 0xFFFF)
            W(UC_X86_REG_DX, p >> 16)
            ok()
        elif ah == 0x4C:
            raise Exit(al)
        else:
            ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)
            ip, cs = struct.unpack('<HH', bytes(uc.mem_read(ss * 16 + sp, 4)))
            self.ints.append((0x21, ah, '%04X:%04X' % (cs - self.base, ip)))
            err(1)


if __name__ == '__main__':
    m = M()
    print('reached main; DS=%04X heap top %04X; unknown ints %r' % (m.ds, m.top, m.ints[:10]))
    print('stdout %r' % bytes(m.stdout))
