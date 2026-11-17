# SPDX-License-Identifier: GPL-3.0-or-later
"""textrig.py - M.EXE's text, menus and input under emulation, for check_text, check_menu and
check_input (with $EMU_PYTHON: unicorn).

The machine is re-tools/mcall.py's (gf_verify.GM) with what the text code needs of the PC-98:
  * INT 18h AH=14h, the kanji ROM, answered from the pack's font16 / font8 exactly as the
    engine's lrv_font_rom_glyph reads them (rows 29h/2Ah half-width from font8, 2Bh blank),
    so both sides draw the same glyphs;
  * INT 33h, the MSZ driver: AX=0 a driver is there, AX=3 the pointer and buttons of the
    script, AX=1 / AX=2 logged as the pointer shown / hidden;
  * the keyboard: port 41h holds the byte of the scan code being delivered; the original's
    own INT 09h handler takes it, delivered as a hardware interrupt;
  * the VSYNC: the original's own handler (vector 0Ah: the frame counter, the 16 timer
    slots), delivered as a hardware interrupt.
Time passes only where the original waits: at the end of a turn of each of its wait loops
that found nothing (FRAME_POINTS), as in the engine, whose loops end such a turn with a
frame. There a VSYNC is delivered, then what the script has for the new frame: the mouse's
state and the scan codes, each through INT 09h. Drawing takes no time on either side.

The script's frames count from the start of each run (base). Events of a run are recorded as
(frame, kind, arg, crc): kind show / icon1 / icon0 / restore / invert / ptr, crc the CRC-32 of
the window's 68 x 80 bytes of the four planes of VRAM page 0 (restore: of the whole page).
"""
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))

from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.x86_const import UC_X86_REG_AX, UC_X86_REG_BX, UC_X86_REG_CX, UC_X86_REG_DX, \
    UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_BP, UC_X86_REG_SS, UC_X86_REG_SP, \
    UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_EFLAGS  # noqa: E402
from gf_verify import GM  # noqa: E402
from mcall import SENTINEL, STUB  # noqa: E402
from va98 import Fonts, read_xfnt  # noqa: E402,F401 - the kanji ROM, shared

WIN_OFF, WIN_WB, WIN_H = 0x5FF6, 68, 80
MAX_FRAMES = 100000                 # a run that waits longer is a script that never ends

# (address, predicate name): a turn of a wait loop that found nothing ends here
FRAME_POINTS = {
    (0x0315, 0x0B3F): 'ax_not_1',       # msg_show, timed page: after msg_poll(0)
    (0x0315, 0x0C18): 'ax_not_1',       # msg_wait_key: after msg_poll(0)
    (0x0315, 0x0BB4): 'si_1',           # msg_poll(1): input polled, none of its kinds
    (0x043A, 0x026C): 'left_held',      # input_wait_release(2): the left button still down
    (0x001E, 0x0BED): 'menu_turn',      # menu_loop: nothing taken (not on entering)
}
MENU_ENTRY = (0x001E, 0x0B8A)           # menu_loop's jump to its loop's test on entering
EVENTS = {
    (0x02BE, 0x00C8): 'show',           # win_show, after the copy
    (0x02BE, 0x02CF): 'icon1',          # icon_draw's return
    (0x02BE, 0x02E5): 'icon0',          # icon_erase's return
    (0x02BE, 0x00A8): 'restore',        # win_restore_screen, after the copy
    (0x02BE, 0x029B): 'invert',         # rect_invert, after vram_invert
}


class Machine(GM):
    def __init__(self, fonts):
        self.fonts = fonts
        self.kbd_data = 0
        self.mouse = [320, 200, 0]      # x, y, buttons (bit 0 left, bit 1 right)
        self.frame = 0
        self.fbase = 0
        self.sched = {}                 # frame (relative) -> [('scan', d) | ('mouse', x, y, b)]
        self.log = []                   # (frame, kind, arg, crc)
        self.on_page = None             # policy: (machine, wait kind) at a page's first wait
        self.page_waiting = False
        self._stop_why = None
        self._skip_once = None
        self._menu_entry = False
        super().__init__(trace_ports=False)
        uc = self.uc
        self._fp = {}
        for (s, o), what in FRAME_POINTS.items():
            lin = self.lin(self.seg(s), o)
            self._fp[lin] = (what, (s, o))
            uc.hook_add(UC_HOOK_CODE, self._frame_point, begin=lin, end=lin)
        self._ev = {}
        for (s, o), what in EVENTS.items():
            lin = self.lin(self.seg(s), o)
            self._ev[lin] = what
            uc.hook_add(UC_HOOK_CODE, self._event, begin=lin, end=lin)
        lin = self.lin(self.seg(MENU_ENTRY[0]), MENU_ENTRY[1])
        uc.hook_add(UC_HOOK_CODE, self._menu_enter, begin=lin, end=lin)

    # ---- the BIOS and the drivers
    def _in(self, uc, port, size, ud):
        if port == 0x41:
            return self.kbd_data
        return super()._in(uc, port, size, ud)

    def _stub(self, uc, address, size, ud):
        n = address - STUB * 16
        if n == 0x18:
            ax = uc.reg_read(UC_X86_REG_AX)
            if ax >> 8 == 0x14:
                jis = uc.reg_read(UC_X86_REG_DX)
                bx, cx = uc.reg_read(UC_X86_REG_BX), uc.reg_read(UC_X86_REG_CX)
                g = self.fonts.rom(jis)
                size_bytes = b'\x01\x02' if (jis >> 8) in (0x29, 0x2A, 0x2B) else b'\x02\x02'
                uc.mem_write(bx * 16 + cx, size_bytes + g)
            return
        if n == 0x33:
            ax = uc.reg_read(UC_X86_REG_AX)
            if ax == 0:
                uc.reg_write(UC_X86_REG_AX, 0xFFFF)
                uc.reg_write(UC_X86_REG_BX, 2)
            elif ax in (1, 2):
                self.log.append((self.frame - self.fbase, 'ptr', 1 if ax == 1 else 0, 0))
            elif ax == 3:
                uc.reg_write(UC_X86_REG_BX, self.mouse[2] & 3)
                uc.reg_write(UC_X86_REG_CX, self.mouse[0])
                uc.reg_write(UC_X86_REG_DX, self.mouse[1])
            return
        if n == 0x0A:                   # the VSYNC handler chains to the BIOS's: nothing
            return
        return super()._stub(uc, address, size, ud)

    # ---- the records
    def window_crc(self):
        pg = self.pages[0]
        c = 0
        for q in range(4):
            p = pg[q]
            for line in range(WIN_H):
                o = WIN_OFF + line * 80
                c = zlib.crc32(bytes(p[o:o + WIN_WB]), c)
        return c

    def page_crc(self):
        c = 0
        for q in range(4):
            c = zlib.crc32(bytes(self.pages[0][q][:32000]), c)
        return c

    def _event(self, uc, address, size, ud):
        what = self._ev[address]
        f = self.frame - self.fbase
        if what == 'restore':
            self.log.append((f, what, 0, self.page_crc()))
        elif what == 'invert':
            es, bx = uc.reg_read(UC_X86_REG_ES), uc.reg_read(UC_X86_REG_BX)
            y0 = struct.unpack('<h', self.mem(es, bx + 4, 2))[0]
            self.log.append((f, what, y0, self.window_crc()))
        else:
            self.log.append((f, what, 0, self.window_crc()))
            if what == 'show':
                self.page_waiting = True

    def _menu_enter(self, uc, address, size, ud):
        self._menu_entry = True

    def _frame_point(self, uc, address, size, ud):
        if address == self._skip_once:
            self._skip_once = None
            return
        what, so = self._fp[address]
        if what == 'ax_not_1':
            go = uc.reg_read(UC_X86_REG_AX) != 1
        elif what == 'si_1':
            go = uc.reg_read(UC_X86_REG_SI) == 1
        elif what == 'left_held':
            ss, bp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_BP)
            go = struct.unpack('<H', self.mem(ss, (bp - 0x10) & 0xFFFF, 2))[0] == 1
        else:                           # menu_turn
            go = uc.reg_read(UC_X86_REG_DI) == 0 and not self._menu_entry
            self._menu_entry = False
        if not go:
            return
        if self.page_waiting and self.on_page:
            self.page_waiting = False
            kind = {(0x0315, 0x0B3F): 'timed', (0x0315, 0x0C18): 'key',
                    (0x0315, 0x0BB4): 'block'}.get(so)
            if kind:
                self.on_page(self, kind)
        self._stop_why = address
        uc.emu_stop()

    # ---- interrupts
    def _deliver(self, vec):
        """a hardware interrupt now: the vector's handler runs and returns here"""
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
        back = cs * 16 + ip
        save = self._skip_once
        self._skip_once = None
        self._run_to(back)
        self._skip_once = save

    def isr_kbd(self, data):
        self.kbd_data = data & 0xFF
        self._deliver(0x09)

    def _tick(self):
        """a VSYNC, then the script's events of the new frame"""
        self.frame += 1
        self._deliver(0x0A)
        f = self.frame - self.fbase
        for ev in self.sched.pop(f, []):
            self.applied.append((f, ev))
            if ev[0] == 'mouse':
                self.mouse = [ev[1], ev[2], ev[3]]
            else:
                self.isr_kbd(ev[1])

    def run(self, seg, off, args=()):
        """a far call of seg:off as mcall's call(), with time and interrupts"""
        uc = self.uc
        seg = self.seg(seg)
        sp = self.main_sp - 0x40
        frame = [0, SENTINEL] + [a & 0xFFFF for a in args]
        sp -= 2 * len(frame)
        uc.mem_write(self.main_ss * 16 + sp, struct.pack('<%dH' % len(frame), *frame))
        for r, v in ((UC_X86_REG_SS, self.main_ss), (UC_X86_REG_SP, sp),
                     (UC_X86_REG_DS, self.ds), (UC_X86_REG_ES, self.ds),
                     (UC_X86_REG_CS, seg), (UC_X86_REG_IP, off)):
            uc.reg_write(r, v)
        while True:
            self._stop_why = None
            self._run_to(SENTINEL * 16)
            if self._stop_why is None:
                if uc.reg_read(UC_X86_REG_CS) * 16 + uc.reg_read(UC_X86_REG_IP) != \
                        SENTINEL * 16:
                    raise RuntimeError('textrig: the emulation stopped short of the routine\'s '
                                       'end (mcall\'s instruction limit: a hang)')
                break
            self._skip_once = self._stop_why
            if self.frame - self.fbase > MAX_FRAMES:
                raise RuntimeError('textrig: no end after %d frames: the script never lets '
                                   'the original go on' % MAX_FRAMES)
            self._tick()
        return uc.reg_read(UC_X86_REG_AX), uc.reg_read(UC_X86_REG_DX)

    # ---- the game's state
    def start(self, mask=3):
        """the scenario and the text loaded, the timer, the input and the graphics initialised
        as run_game does"""
        g = self.seg(0x0BA1)
        name = self.alloc(32)
        self.poke(name, 0, b'CMD00.SCB\x00rb\x00')
        ax, dx = self.call(0x0886, 0x039A, [0, name, 10, name])
        self.poke(g, 0x64, struct.pack('<HH', ax, dx))
        assert self.call(0x063C, 0x00E8)[0] == 1, 'scb_load'
        assert self.call(0x0724, 0x0018)[0] == 1, 'txb_load'
        assert self.call(0x0752, 0x0002)[0] == 1, 'timer_init'
        self.poke(self.ds, 0x110, struct.pack('<H', mask))
        assert self.call(0x043A, 0x0008)[0] == 1, 'input_init'
        assert self.call(0x0315, 0x000E)[0] == 1, 'gfx_init'
        self.opblk = self.alloc(64)
        self.recblk = self.alloc(32)

    def scene(self):
        """va_main and the window's frame va_mw01, as the scenario's first scene"""
        for nm, flag, x, y in (('va_main', 0, 0, 0), ('va_mw01', 1, 32, 300)):
            blk = bytearray(0x16)
            blk[0:len(nm)] = nm.encode()
            struct.pack_into('<hhhh', blk, 0x0E, flag, 10, x, y)
            self.poke(self.opblk, 0, blk)
            assert self.call(0x0315, 0x070D, [0, self.opblk])[0] == 1, nm

    def input_mask(self, mask):
        self.call(0x043A, 0x0066)
        self.poke(self.ds, 0x110, struct.pack('<H', mask))
        assert self.call(0x043A, 0x0008)[0] == 1, 'input_init'

    def timers_fill(self):
        self.held = [self.call(0x0752, 0x0026, [1000, 0])[0] for _ in range(16)]

    def timers_free(self):
        for h in self.held:
            self.call(0x0752, 0x0043, [h])

    def v1(self):
        """the scenario's result register as ops 19h and 24h write it: 0BA1:0068 -> +4 ->
        {type, value}"""
        s, o = self.far(self.seg(0x0BA1), 0x68)
        s, o = self.far(s, o + 4)
        return struct.unpack('<hh', self.mem(s, o, 4))

    def begin(self, sched):
        self.fbase = self.frame
        self.sched = {f: list(evs) for f, evs in sched.items()}
        self.log = []
        self.applied = []
        self.page_waiting = False

    def op19(self, n, sched=None):
        """statement 19h n; returns (v1, log, the script's events as they were applied)"""
        self.begin(sched or {})
        self.poke(self.opblk, 0x20, struct.pack('<H', n))
        self.run(0x001E, 0x0965, [0x20, self.opblk])
        return self.v1()[1], self.log, self.applied

    def op24(self, menu, stmt, sched=None):
        """statement 24h of menu `menu` (1-based); stmt picks the operand block: the same stmt
        is the same statement"""
        self.begin(sched or {})
        off = 0x30 + 2 * stmt
        self.poke(self.opblk, off, struct.pack('<H', menu))
        self.run(0x001E, 0x0A8D, [off, self.opblk])
        return self.v1()[1], self.log, self.applied

    def isr(self, data):
        """a byte from the keyboard now, at the top level"""
        uc = self.uc
        uc.reg_write(UC_X86_REG_SS, self.main_ss)
        uc.reg_write(UC_X86_REG_SP, self.main_sp - 0x40)
        uc.reg_write(UC_X86_REG_CS, SENTINEL)
        uc.reg_write(UC_X86_REG_IP, 0)
        self.isr_kbd(data)

    def poll(self):
        """input_poll (043A:01DA): its result and the record's words 2..24"""
        self.poke(self.recblk, 0, bytes(26))   # (a device that is not open leaves its
        ax = self.call(0x043A, 0x01DA, [0, self.recblk])[0]     # "changed" as it was)
        w = struct.unpack('<13h', self.mem(self.recblk, 0, 26))
        return [ax] + list(w[1:13])

    def release(self, mask, sched=None):
        """input_wait_release (043A:0236); the frames it took"""
        self.begin(sched or {})
        self.run(0x043A, 0x0236, [mask])
        return self.frame - self.fbase

    def menu_items(self, menu):
        g = self.seg(0x0BA1)
        ms, mo = self.far(g, 0x12)
        rs, ro = self.far(ms, mo + 4 * menu)
        n = self.word(rs, ro)
        out = []
        for i in range(n):
            s, o = self.far(rs, ro + 2 + 4 * i)
            out.append(self.cstr(s, o))
        return out
