#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""va98 - Virgin Angel's M.EXE whole, from its start to its exit, on an emulated PC-98: the
reference the engine is played against end to end (source/tests/check_vm.py).

Needs unicorn (run with $EMU_PYTHON). The machine is re-tools/mcall.py's (DOS in Python, the
graphics planes with the GRCG) with what the program needs of the rest of the PC-98:

  * time: an instruction time base. A VSYNC comes every `ipf` instructions; the program's spin
    loops (SPINS: a loop head reached twice within one frame) skip to the next one, which is
    what they would spin for, so waiting costs nothing to emulate. ipf defaults to the
    reference machine's clocks per frame (cpu_per_frame, 177 242) over the 80286's average
    clocks per instruction (IPF_CLOCKS); it decides only how many frames the CPU-bound work
    takes, which the comparison never looks at (it compares at the input waits);
  * the VSYNC interrupt (IRQ 2, vector 0Ah): one interrupt per write to port 64h, when IRQ 2
    is not masked at the master PIC (port 02h) and IF is set; the GDC status (ports 60h/A0h)
    reads bit 5 set once after each VSYNC (dac_set waits for it);
  * the keyboard: port 41h holds the byte being delivered and the program's own INT 09h
    handler takes it, as a hardware interrupt after a VSYNC; make codes, and break codes when
    asked for;
  * INT 18h: AH=14h the kanji ROM, answered from the pack's font16 / font8 as the engine's
    lrv_font_rom_glyph reads them (Fonts); AH=00h a key from the keyboard BIOS (the console's
    question); the rest returns at once;
  * INT 33h, the MSZ driver: AX=0 (present or not), 1/2 the pointer shown / hidden, 3 the
    position and buttons, 4 the position set;
  * INT 60h: the real PMD.COM of the game disk, resident in its own machine (re-tools/
    pmdemu.py: the driver's code, a YM2203 with its timers): the program's INT 60h calls go
    to it, the song the program copies into the music buffer (AH=06h's address, ours) goes
    into the driver's at AH=00h, and the driver's timer interrupts run as the master clock
    (3 993 600 Hz) passes, 3 993 600 / 56.42 clocks a VSYNC; so AH=05h (the measure counter
    statement 35h reads) answers what the real driver answers at that time. sound='none':
    no driver at INT 60h (GAME.BAT's option 4);
  * INT 21h: mcall's (files below `files`, writes to memory). GAME.DAT of the disk (a
    previous owner's saves) is hidden; `gamedat` gives the file the run starts with.

The waits (WAITS): at the entry of each of the original's waits for input or time, at the
point the engine reports the same wait (vg_wait_begin), `policy(machine, wait)` is called
with wait = {'n': number, 'kind': 'key'|'ticks', 'where': name, 'frame': VSYNCs so far}. It
returns what the player does from the first VSYNC after the wait's first input_poll on (a
wait may draw first: the music mode draws its list, longer than a frame; the engine draws in
no time), an entry a VSYNC, in
the words of the engine's tests/test_game.c: '.' nothing; 'kHH' a press of the key of scan
code HH (its make code, its break code at the next VSYNC); 'hHH' / 'uHH' the key held down /
let go (make / break); 'mX,Y,B' the pointer and the buttons (1 left, 2 right) from then on;
'cX,Y' the pointer there and the left button down for one VSYNC. A break or a button's
release due at the next VSYNC happens there even when a new wait begins before it. For the
console's question (INT 18h AH=00h, the keyboard BIOS) the first 'kHH' is the key the BIOS
returns. The policy may raise Stop to end the run there.

    from va98 import VA98, Fonts
    m = VA98(Fonts(pak), policy=fn)
    m.run()              # 'exit' (m.exit_code) or 'stop'
    m.state()            # the program's state (check_vm's comparison)
    m.int60              # [(ax in, ax out)] since the start (pop what was read)

Running it alone plays the game with Return at every key wait (y at the question) and
prints the waits: va98.py PAK [--frames N] [--waits N] [--sound none].
"""
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))

from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, \
    UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_DS, \
    UC_X86_REG_EFLAGS  # noqa: E402
from gf_verify import GM  # noqa: E402
from mcall import Exit, STUB  # noqa: E402

PC98 = os.path.join(ROOT, 'resources', 'original', 'pc98')
CPU_PER_FRAME = 177242          # the profile's cpu_per_frame: an 80286 at 10 MHz
IPF_CLOCKS = 6                  # the 80286's clocks per instruction, about (inferred)
IPF = CPU_PER_FRAME // IPF_CLOCKS
CLOCK = 3993600                 # the OPN's master clock
FRAME_NUM, FRAME_DEN = 5642, 100    # VSYNCs per second, 56.42
FAKESEG = 0xC000                # the driver's stand-in at INT 60h (mapped RAM above the arena)
MUSBUF = FAKESEG + 0x10         # AH=06h: the music buffer (8 KB, PMD's /M8)
MUSBUF_BYTES = 8 * 1024
MAX_IDLE = 100_000              # frames without a wait (half an hour): a hang

# the original's waits, at the point the engine's vg_wait_begin stands for (source/engine)
WAITS = {
    (0x0315, 0x0BD6): ('key', 'msg_key'),       # msg_wait_key (msg.c)
    (0x0315, 0x0B1B): ('ticks', 'msg_timed'),   # msg_show's timed page, the timer started
    (0x001E, 0x0B8A): ('key', 'menu'),          # menu_loop: into its loop (menu.c)
    (0x001E, 0x0862): ('ticks', 'op15'),        # op_15: the timer started (vm.c io_wait)
    (0x001E, 0x08FB): ('key', 'op16'),          # op_16 (vm.c io_wait_input)
    (0x0504, 0x0257): ('key', 'bi_any'),        # bi_wait_any (bi.c)
    (0x0504, 0x04FE): ('ticks', 'op_page'),     # op_pages: a page's 3 s (opening.c)
    (0x0504, 0x0994): ('key', 'musmode'),       # mus_loop (musmode.c)
}
INPUT_POLL = (0x043A, 0x01DA)
# loop heads of the spin loops: a second arrival within one frame waits for the next VSYNC
SPINS = [
    (0x0315, 0x0C07), (0x0315, 0x0B23), (0x0315, 0x0BB4),   # msg: key wait, timed, blocking
    (0x001E, 0x0BED), (0x001E, 0x0865), (0x001E, 0x08FF),   # menu_loop, op_15, op_16
    (0x043A, 0x026C),                                       # input_wait_release: left held
    (0x0504, 0x025B), (0x0504, 0x0501), (0x0504, 0x09A3),   # bi_wait_any, op_pages, mus_loop
    (0x0504, 0x02DF), (0x0504, 0x037D), (0x0504, 0x06E3),   # the wipe, fade c6, dec fade
    (0x0504, 0x082F), (0x0504, 0x0867),                     # the staff roll's counts
    (0x00DD, 0x01DB), (0x00DD, 0x04FE),                     # dac_set, fx31_wait
    (0x0315, 0x04A5), (0x0315, 0x0677),                     # pal_fade_in / _out
    (0x04E4, 0x0199),                                       # mus_fade_stop
]
CONSOLE_CHARS = {0x15: 0x79, 0x2E: 0x6E}        # Y, N (scan codes) -> 'y', 'n'


class Stop(Exception):
    """raised by a policy: the run ends here"""


def read_xfnt(data):
    cw, ch, count = data[5], data[6], struct.unpack_from('<H', data, 8)[0]
    codes = struct.unpack_from('<%dH' % count, data, 12)
    gb = ch * cw // 8
    g = 12 + 2 * count
    return {c: data[g + i * gb:g + (i + 1) * gb] for i, c in enumerate(codes)}


class Fonts:
    """the kanji ROM as lrvne's lrv_font_rom_glyph reads it from the pack's font16 / font8"""

    def __init__(self, pak):
        import vgpak
        p = vgpak.read(pak)
        self.raw = {}
        for name in ('font16', 'font8'):
            e = p.find(name)
            if e is None:
                sys.exit('va98: the pack has no %s' % name)
            self.raw[name] = e.data
        self.font16 = read_xfnt(self.raw['font16'])
        self.font8 = read_xfnt(self.raw['font8'])

    def rom(self, jis):
        row, cell = (jis >> 8) & 0xFF, jis & 0xFF
        out = bytearray(32)
        if row in (0x29, 0x2A, 0x2B):
            g = None if row == 0x2B else self.font8.get(cell if row == 0x29 else
                                                        (cell + 0x80) & 0xFF)
            if g:
                out[0:16] = g[:16]
            return bytes(out)
        g = self.font16.get(jis & 0xFFFF)
        if g:
            out[:] = g[:32]
        return bytes(out)


def to_frames(tokens):
    """the route's words of a wait -> [[action, ..] a VSYNC]: a press's break and a click's
    release come first at the VSYNC after it (the engine's poll does the same)"""
    frames = [[] for _ in tokens]
    for i, t in enumerate(tokens):
        k = t[0]
        if k == '.':
            continue
        if k in 'khu':
            sc = int(t[1:], 16) & 0x7F
            frames[i].append(('break' if k == 'u' else 'make', sc))
            if k == 'k':
                if i + 1 == len(frames):
                    frames.append([])
                frames[i + 1].insert(0, ('break', sc))
        elif k == 'm':
            x, y, b = (int(v) for v in t[1:].split(','))
            frames[i].append(('mouse', x, y, b))
        elif k == 'c':
            x, y = (int(v) for v in t[1:].split(','))
            frames[i].append(('mouse', x, y, None))
            if i + 1 == len(frames):
                frames.append([])
            frames[i + 1].insert(0, ('release',))
        else:
            raise ValueError('va98: no such input %r' % t)
    return frames


def crc_planes(planes):
    c = 0
    for p in planes:
        c = zlib.crc32(bytes(p), c)
    return c


class VA98(GM):
    def __init__(self, fonts, policy=None, files=PC98, gamedat=None, sound='pmd', mouse=True,
                 ipf=IPF, args='cmd00.scb gdata.lib'):
        self.fonts = fonts
        self.policy = policy
        self.sound = sound
        self.has_mouse = mouse
        self.ipf = ipf
        self.frame = 0
        self.waits = 0
        self.kbd_data = 0
        self.mouse = [0, 0, 0]
        self.ptr = 0                    # the pointer shown (INT 33h AX=1 / AX=2)
        self.pending = []               # the player's input, an entry a VSYNC
        self.due = []                   # breaks and releases due at the next VSYNC
        self.polled = False             # input_poll called since the wait began
        self.armed = False              # port 64h written since the last VSYNC
        self.pic_mask = 0
        self.retrace = False
        self.int60 = []
        self.exit_code = None
        self.console = []               # INT 18h AH=00h: the keys returned
        self._why = None
        self._skip = None
        self._in_isr = False
        self._spin_at = {}
        self._wait_frame = 0
        super().__init__(files=files, args=args, trace_ports=False, max_insns=50_000_000)
        self.written.pop('game.dat', None)
        if gamedat is not None:
            self.written['game.dat'] = bytearray(gamedat)
        uc = self.uc
        self._waits = {}
        for (s, o), (kind, where) in WAITS.items():
            lin = self.lin(self.seg(s), o)
            self._waits[lin] = (kind, where)
            uc.hook_add(UC_HOOK_CODE, self._wait_hook, begin=lin, end=lin)
        lin = self.lin(self.seg(INPUT_POLL[0]), INPUT_POLL[1])
        uc.hook_add(UC_HOOK_CODE, self._poll_hook, begin=lin, end=lin)
        for s, o in SPINS:
            lin = self.lin(self.seg(s), o)
            uc.hook_add(UC_HOOK_CODE, self._spin_hook, begin=lin, end=lin)
        self.pmd = None
        if sound == 'pmd':
            import pmdemu
            self.pmd = pmdemu.PMDEmu(os.path.join(files, 'PMD.COM'), opts=pmdemu.VA_OPTS)
            img = bytearray(0x20)
            img[0:7] = b'\xEB\x11PMDGg'         # the signature mus_init looks for at +2
            img[0x13] = 0xCF
            uc.mem_write(FAKESEG * 16, bytes(img))
            uc.mem_write(0x60 * 4, struct.pack('<HH', 0, FAKESEG))
            lin = FAKESEG * 16 + 0x13
            uc.hook_add(UC_HOOK_CODE, self._int60_hook, begin=lin, end=lin)

    # ---- files: the disk's GAME.DAT is not there
    def _path(self, seg, off):
        p, name = super()._path(seg, off)
        if name.lower() == 'game.dat':
            return None, name
        return p, name

    # ---- ports
    def _in(self, uc, port, size, ud):
        if port == 0x41:
            return self.kbd_data
        if port in (0x60, 0xA0):
            v = 0x24 if self.retrace else 0x04
            self.retrace = False
            return v
        if port == 0x02:
            return self.pic_mask
        return super()._in(uc, port, size, ud)

    def _out(self, uc, port, size, value, ud):
        if port == 0x64:
            self.armed = True
        elif port == 0x02:
            self.pic_mask = value & 0xFF
        super()._out(uc, port, size, value, ud)

    # ---- the BIOS and the drivers
    def _stub(self, uc, address, size, ud):
        n = address - STUB * 16
        try:
            if n == 0x18:
                return self._int18()
            if n == 0x33:
                return self._int33()
            if n in (0x09, 0x0A):           # the handlers chain to the BIOS's: nothing
                return
        except Exception as e:              # noqa: BLE001 - raised again by _run
            self._exc = e
            uc.emu_stop()
            return
        return super()._stub(uc, address, size, ud)

    def _int18(self):
        uc = self.uc
        ah = uc.reg_read(UC_X86_REG_AX) >> 8
        if ah == 0x14:
            jis = uc.reg_read(UC_X86_REG_DX)
            bx, cx = uc.reg_read(UC_X86_REG_BX), uc.reg_read(UC_X86_REG_CX)
            size = b'\x01\x02' if (jis >> 8) in (0x29, 0x2A, 0x2B) else b'\x02\x02'
            uc.mem_write(bx * 16 + cx, size + self.fonts.rom(jis))
        elif ah == 0x00:                    # wait for a key: the console's question
            evs = self._ask('key', 'console')
            keys = [int(e[1:], 16) for e in evs if e.startswith('k')]
            if not keys:
                raise RuntimeError('va98: the console waits for a key the policy does not give')
            scan = keys[0]
            self.console.append(scan)
            uc.reg_write(UC_X86_REG_AX, scan << 8 | CONSOLE_CHARS.get(scan, 0))

    def _int33(self):
        uc = self.uc
        ax = uc.reg_read(UC_X86_REG_AX)
        if ax == 0:
            uc.reg_write(UC_X86_REG_AX, 0xFFFF if self.has_mouse else 0)
            uc.reg_write(UC_X86_REG_BX, 2)
            self.ptr = 0
        elif not self.has_mouse:
            return
        elif ax in (1, 2):
            self.ptr = 1 if ax == 1 else 0
        elif ax == 3:
            uc.reg_write(UC_X86_REG_BX, self.mouse[2] & 3)
            uc.reg_write(UC_X86_REG_CX, self.mouse[0])
            uc.reg_write(UC_X86_REG_DX, self.mouse[1])
        elif ax == 4:
            self.mouse[0], self.mouse[1] = uc.reg_read(UC_X86_REG_CX), uc.reg_read(UC_X86_REG_DX)

    def _int60_hook(self, uc, address, size, ud):
        try:
            ax = uc.reg_read(UC_X86_REG_AX)
            ah = ax >> 8
            e = self.pmd
            if ah == 0x06:
                uc.reg_write(UC_X86_REG_DS, MUSBUF)
                uc.reg_write(UC_X86_REG_DX, 0)
                out = ax
            else:
                if ah == 0x00:
                    e.load_music(bytes(uc.mem_read(MUSBUF * 16, MUSBUF_BYTES)))
                    e.mstart()
                    r = e.uc.reg_read(UC_X86_REG_AX), e.uc.reg_read(UC_X86_REG_DX)
                else:
                    r = e.int60(ax, uc.reg_read(UC_X86_REG_DX))
                uc.reg_write(UC_X86_REG_AX, r[0])
                uc.reg_write(UC_X86_REG_DX, r[1])
                out = r[0]
            self.int60.append((ax, out))
        except Exception as e:              # noqa: BLE001
            self._exc = e
            uc.emu_stop()

    def _pmd_time(self):
        """the driver's timer interrupts up to this VSYNC"""
        e = self.pmd
        target = self.frame * CLOCK * FRAME_DEN // FRAME_NUM
        while True:
            nxt = [t for t in (e.tA_next, e.tB_next) if t is not None]
            if not nxt or min(nxt) > target:
                break
            e.step()
        e.clk = max(e.clk, target)
        del e.writes[:]
        del e.bidx[:]

    # ---- the player
    def _ask(self, kind, where):
        self.waits += 1
        self._wait_frame = self.frame
        w = {'n': self.waits, 'kind': kind, 'where': where, 'frame': self.frame}
        evs = list(self.policy(self, w)) if self.policy else []
        return evs

    def _wait_hook(self, uc, address, size, ud):
        if self._in_isr:
            return
        if self._skip == address:
            self._skip = None
            return
        try:
            kind, where = self._waits[address]
            self._set_pending(self._ask(kind, where))
        except Stop:
            self._why = 'stop'
            self._skip = address
            uc.emu_stop()
        except Exception as e:              # noqa: BLE001
            self._exc = e
            uc.emu_stop()

    def _poll_hook(self, uc, address, size, ud):
        if not self._in_isr:
            self.polled = True

    def _spin_hook(self, uc, address, size, ud):
        if self._in_isr:
            return
        if self._spin_at.get(address) == self.frame:
            self._why = 'spin'
            uc.emu_stop()
        else:
            self._spin_at[address] = self.frame

    def _set_pending(self, tokens):
        """the player's input from the next VSYNC on; what was due at the next VSYNC from
        before (a break, a release) stays first"""
        self.due = [a for a in (self.pending[0] if self.pending else [])
                    if a[0] in ('break', 'release')] + self.due
        self.pending = to_frames(tokens)
        self.polled = False

    def _apply(self, actions):
        for a in actions:
            if a[0] == 'make':
                self._kbd(a[1])
            elif a[0] == 'break':
                self._kbd(a[1] | 0x80)
            elif a[0] == 'mouse':
                self.mouse = [a[1], a[2], self.mouse[2] | 1 if a[3] is None else a[3]]
            elif a[0] == 'release':
                self.mouse[2] &= ~1

    # ---- interrupts
    def _deliver(self, vec):
        """a hardware interrupt now: the vector's handler runs to its return"""
        uc = self.uc
        cs, ip = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
        fl = uc.reg_read(UC_X86_REG_EFLAGS) & 0xFFFF
        ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)
        sp = (sp - 6) & 0xFFFF
        uc.mem_write(ss * 16 + sp, struct.pack('<HHH', ip, cs, fl))
        uc.reg_write(UC_X86_REG_SP, sp)
        off, seg = struct.unpack('<HH', self.mem(0, vec * 4, 4))
        uc.reg_write(UC_X86_REG_EFLAGS, fl & ~0x0300)
        uc.reg_write(UC_X86_REG_CS, seg)
        uc.reg_write(UC_X86_REG_IP, off)
        self._in_isr = True
        try:
            self._run_to(cs * 16 + ip)
        finally:
            self._in_isr = False

    def _kbd(self, data):
        self.kbd_data = data & 0xFF
        self._deliver(0x09)

    def _if_set(self):
        """steps on until interrupts are enabled (a cli section: a few instructions)"""
        uc = self.uc
        for _ in range(100000):
            if uc.reg_read(UC_X86_REG_EFLAGS) & 0x200:
                return True
            cs, ip = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
            uc.emu_start(cs * 16 + ip, 0xFFFFF, count=1)
            if self._exc or self._why == 'stop':
                return False
        raise RuntimeError('va98: interrupts stay disabled')

    def _vsync(self):
        self.frame += 1
        if self.frame - self._wait_frame > MAX_IDLE:
            raise RuntimeError('va98: no wait for %d frames' % MAX_IDLE)
        if self.pmd:
            self._pmd_time()
        self.retrace = True
        if not self._if_set():
            return
        if self.armed and not self.pic_mask & 0x04:
            self.armed = False
            self._deliver(0x0A)
        if self.due:
            due, self.due = self.due, []
            self._apply(due)
        if self.pending and self.polled:
            self._apply(self.pending.pop(0))

    # ---- running
    def run(self):
        """the program from where it is (main, after the start-up) to its exit ('exit',
        self.exit_code) or a Stop of the policy ('stop'); run() again goes on from there"""
        uc = self.uc
        while True:
            self._why = None
            cs, ip = uc.reg_read(UC_X86_REG_CS), uc.reg_read(UC_X86_REG_IP)
            uc.emu_start(cs * 16 + ip, 0xFFFFF, count=self.ipf)
            if self._exc:
                e, self._exc = self._exc, None
                if isinstance(e, Exit):
                    self.exit_code = e.args[0]
                    return 'exit'
                raise e
            if self._why == 'stop':
                return 'stop'
            self._vsync()
            if self._why == 'stop':
                return 'stop'
            if self._exc:
                e, self._exc = self._exc, None
                if isinstance(e, Exit):
                    self.exit_code = e.args[0]
                    return 'exit'
                raise e

    # ---- the state
    def far_planes(self, seg, off):
        """four far plane pointers at seg:off -> their 68 x 80 bytes (the window buffers)"""
        out = []
        for q in range(4):
            o, s = struct.unpack('<HH', self.mem(seg, off + 4 * q, 4))
            out.append(self.mem(s, o, 68 * 80) if s else bytes(68 * 80))
        return out

    def vm_vars(self):
        g = self.seg(0x0BA1)
        n = struct.unpack('<h', self.mem(g, 0x42, 2))[0]
        s, o = self.far(g, 0x68)
        out = []
        for i in range(max(0, n) + 1):
            vs, vo = self.far(s, o + 4 * i)
            out.append(struct.unpack('<hh', self.mem(vs, vo, 4)) if vs else (0, 0))
        return out

    def state(self):
        """the program's state as check_vm compares it (the engine's test_game prints the same)"""
        ds, g = self.ds, self.seg(0x0BA1)
        st = {}
        st['pc'] = self.word(ds, 0x5A)
        st['depth'] = struct.unpack('<h', self.mem(ds, 0x5C, 2))[0]
        st['stack'] = list(struct.unpack('<32H', self.mem(self.seg(0x0A9F), 0, 64)))
        st['vars'] = self.vm_vars()
        st['page0'] = crc_planes(self.vram(0))
        st['page1'] = crc_planes(self.vram(1))
        st['buf12'] = crc_planes(self.get_buf(12) if self.mem_planes()[0] else
                                 [bytes(32000)] * 4)
        st['win_save'] = crc_planes(self.far_planes(g, 0x74))
        st['win_work'] = crc_planes(self.far_planes(g, 0x54))
        st['dac'] = ''.join('%x%x%x' % tuple(c) for c in self.dac)
        st['skip'] = self.mem(g, 0, 1)[0]
        st['choice'] = self.word(ds, 0xC4)
        st['mus'] = (self.cstr(ds, 0x1D0, 19).decode('latin-1'), self.word(ds, 0x1CE))
        st['disp'] = self.disp_page
        st['ptr'] = self.ptr
        d = self.written.get('game.dat')
        st['gamedat'] = None if d is None else zlib.crc32(bytes(d))
        return st


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('pak')
    ap.add_argument('--waits', type=int, default=40)
    ap.add_argument('--sound', default='pmd')
    a = ap.parse_args(argv)

    def policy(m, w):
        pc = m.word(m.ds, 0x5A)
        print('%6d %5d %-5s %-10s pc %d' % (w['n'], m.frame, w['kind'], w['where'], pc),
              flush=True)
        if w['n'] > a.waits:
            raise Stop
        if w['where'] == 'console':
            return ['k15']
        return ['k1C'] if w['kind'] == 'key' else []
    m = VA98(Fonts(a.pak), policy=policy, sound=a.sound)
    r = m.run()
    print(r, m.exit_code, 'frames', m.frame, 'int60', len(m.int60))
    print(m.state())


if __name__ == '__main__':
    main(sys.argv[1:])
