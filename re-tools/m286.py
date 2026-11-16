#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""m286.py - M.EXE under mcall with time: 80286 clock counts and a VSYNC every frame's worth.

The original runs its transitions as fast as the CPU goes, so the time they take is a property
of the machine. This module measures it in one unit: clocks of an 80286 without wait states,
from Intel's 80286 clock-count table (real mode), counted per executed instruction. A `rep`
string instruction is counted per iteration (unicorn reports each one). Whether a conditional
jump or `loop` is taken is decided from the flags and CX before it runs (a jump to the next
instruction, as 0783:0638 has, costs the taken clocks when taken).

    from m286 import TM
    m = TM(cpu_per_frame=177242)
    m.call(...)                   # as mcall.M.call, with time running (m.timing = False
                                  # stops it: set-up calls whose time does not matter)
    m.frame, m.cyc                # VSYNCs since the start; clocks since the last one
    m.writes                      # with m.log_writes(...): [(plane, off, value, frame, cyc)]
    m.stamp_at[lin] = key         # m.stamps[key]: m.total when the instruction at lin is
                                  # first reached (before its own clocks)

Time: every `cpu_per_frame` clocks a VSYNC happens: the frame counter DS:109E and the 16
timer slots advance as the handler 075A:00A6 does (its own clocks are not counted, as the
engine's tick costs none). The GDC status (ports 60h/A0h) reads bit 5 as set during the
first RETRACE_LINES/LINES of a frame. The original's spin loops do not spin through emulated
time: at a loop head reached a second time within one frame (a spin), the clock jumps to the
point the loop waits for (the retrace's end or the next VSYNC). With cpu_per_frame = 0 there
is no CPU time: only the spin loops advance frames, and the GDC status toggles as in mcall.

The clock table is a model of the reference machine. The engine charges the same clocks at
the same points (source/engine/gfx/fx.c), so its picture after any number of clocks equals
the original's. Instructions outside the table raise KeyError.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capstone import Cs, CS_ARCH_X86, CS_MODE_16  # noqa: E402
from capstone.x86 import X86_OP_REG, X86_OP_IMM, X86_OP_MEM  # noqa: E402
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_WRITE  # noqa: E402
from gf_verify import GM  # noqa: E402

LINES = 440                 # lines of a 400-line frame, blanking included (24.83 kHz / 56.42 Hz)
RETRACE_LINES = 40

# the spin loops: head address -> what they wait for ('retrace_end' or 'vsync')
SPINS = {
    (0x00DD, 0x01D5): 'retrace_end',    # dac_set: while in retrace
    (0x00DD, 0x01DB): 'vsync',          # dac_set: until a retrace starts
    (0x00DD, 0x04FE): 'vsync',          # fx31_wait: until the counter moved by 2
    (0x0315, 0x04A5): 'vsync',          # pal_fade_in: until the elapsed time changes
    (0x0315, 0x0677): 'vsync',          # pal_fade_out: the same
}

ALU = {'add', 'sub', 'and', 'or', 'xor', 'adc', 'sbb'}
SHIFT = {'shl', 'sal', 'shr', 'sar', 'rol', 'ror', 'rcl', 'rcr'}
JCC = {'je', 'jne', 'jl', 'jle', 'jg', 'jge', 'jb', 'jbe', 'ja', 'jae', 'js', 'jns', 'jo',
       'jno', 'jp', 'jnp'}
LOOPS = {'loop', 'loope', 'loopne', 'jcxz'}
SREGS = {'es', 'cs', 'ss', 'ds'}
# rep string instructions: (clocks with no iteration, clocks per iteration)
REP = {'movsb': (5, 4), 'movsw': (5, 4), 'stosb': (4, 3), 'stosw': (4, 3), 'lodsb': (5, 4),
       'lodsw': (5, 4), 'scasb': (5, 8), 'scasw': (5, 8), 'cmpsb': (5, 9), 'cmpsw': (5, 9)}
STRING = {'movsb': 5, 'movsw': 5, 'stosb': 3, 'stosw': 3, 'lodsb': 5, 'lodsw': 5, 'scasb': 7,
          'scasw': 7, 'cmpsb': 8, 'cmpsw': 8}
FIXED = {'cld': 2, 'std': 2, 'cli': 3, 'sti': 2, 'clc': 2, 'stc': 2, 'cmc': 2, 'nop': 3,
         'cbw': 2, 'cwde': 2, 'cwd': 2, 'cdq': 2, 'lahf': 2, 'sahf': 2, 'xlatb': 5, 'pushf': 3,
         'pushfw': 3, 'popf': 5, 'popfw': 5, 'pusha': 17, 'pushaw': 17, 'popa': 19,
         'popaw': 19, 'leave': 5, 'iret': 17, 'hlt': 2, 'int': 23, 'daa': 3, 'das': 3,
         'aaa': 3, 'aas': 3, 'aam': 16, 'aad': 14, 'in': 5, 'out': 3, 'lea': 3, 'lds': 7,
         'les': 7}


def _taken(mn, fl, cx):
    """whether a conditional jump or loop is taken, from FLAGS and CX before it"""
    cf, zf, sf, of, pf = fl & 1, (fl >> 6) & 1, (fl >> 7) & 1, (fl >> 11) & 1, (fl >> 2) & 1
    if mn == 'loop':
        return (cx - 1) & 0xFFFF != 0
    if mn == 'loope':
        return (cx - 1) & 0xFFFF != 0 and zf
    if mn == 'loopne':
        return (cx - 1) & 0xFFFF != 0 and not zf
    if mn == 'jcxz':
        return cx == 0
    return bool({'je': zf, 'jne': not zf, 'jl': sf != of, 'jge': sf == of,
                 'jle': zf or sf != of, 'jg': not zf and sf == of, 'jb': cf, 'jae': not cf,
                 'jbe': cf or zf, 'ja': not cf and not zf, 'js': sf, 'jns': not sf, 'jo': of,
                 'jno': not of, 'jp': pf, 'jnp': not pf}[mn])


def _kinds(insn):
    out = []
    for op in insn.operands:
        if op.type == X86_OP_REG:
            out.append('s' if insn.reg_name(op.reg) in SREGS else 'r')
        elif op.type == X86_OP_IMM:
            out.append('i')
        elif op.type == X86_OP_MEM:
            out.append('m')
    return ''.join(out)


def clocks(insn, cl=0):
    """(clocks, branch) of one executed instruction (not a rep string one); cl is CL before
    it, for shifts by CL. branch = (taken, not taken) for a conditional jump or loop, whose
    clocks are then those of the outcome."""
    mn = insn.mnemonic
    k = _kinds(insn)
    parts = mn.split()
    if parts[0] in ('rep', 'repe', 'repne', 'repz', 'repnz'):
        raise AssertionError('rep is handled by the caller')
    if mn in JCC:
        return 0, (7, 3)
    if mn in LOOPS:
        return 0, (8, 4)
    if mn in FIXED:
        return FIXED[mn], None
    if mn in STRING:
        return STRING[mn], None
    if mn == 'mov':
        return {'rr': 2, 'rm': 5, 'mr': 3, 'ri': 2, 'mi': 3, 'sr': 2, 'sm': 5, 'rs': 2,
                'ms': 3}[k], None
    if mn in ALU:
        return {'rr': 2, 'rm': 7, 'mr': 7, 'ri': 3, 'mi': 7}[k], None
    if mn == 'cmp':
        return {'rr': 2, 'rm': 6, 'mr': 7, 'ri': 3, 'mi': 6}[k], None
    if mn == 'test':
        return {'rr': 2, 'rm': 6, 'mr': 6, 'ri': 3, 'mi': 6}[k], None
    if mn in ('inc', 'dec', 'neg', 'not'):
        return {'r': 2, 'm': 7}[k], None
    if mn in SHIFT:
        op0 = insn.opcode[0]
        if op0 in (0xD0, 0xD1):
            n = 1
        elif op0 in (0xD2, 0xD3):
            n = cl & 31
        else:
            n = insn.operands[1].imm & 31
        if n == 1 and op0 in (0xD0, 0xD1):
            return (2 if k[0] == 'r' else 7), None
        return (5 + n if k[0] == 'r' else 8 + n), None
    if mn == 'imul' and len(insn.operands) == 3:
        return (21 if k[1] == 'r' else 24), None
    if mn in ('mul', 'imul'):
        w = insn.operands[0].size
        return ({1: 13, 2: 21}[w] + (3 if k == 'm' else 0)), None
    if mn == 'div':
        w = insn.operands[0].size
        return ({1: 14, 2: 22}[w] + (3 if k == 'm' else 0)), None
    if mn == 'idiv':
        w = insn.operands[0].size
        return ({1: 17, 2: 25}[w] + (3 if k == 'm' else 0)), None
    if mn == 'xchg':
        return (3 if 'm' not in k else 5), None
    if mn == 'push':
        return {'r': 3, 's': 3, 'i': 3, 'm': 5}[k], None
    if mn == 'pop':
        return {'r': 5, 's': 5, 'm': 5}[k], None
    if mn == 'enter':
        lvl = insn.operands[1].imm
        return (11 if lvl == 0 else 15 if lvl == 1 else 12 + 4 * (lvl - 1)), None
    if mn == 'jmp':
        return {'i': 7, 'r': 7, 'm': 11}[k], None
    if mn == 'ljmp':
        return {'ii': 11, 'm': 15}[k], None
    if mn == 'call':
        return {'i': 7, 'r': 7, 'm': 11}[k], None
    if mn == 'lcall':
        return {'ii': 13, 'm': 16}[k], None
    if mn in ('ret', 'retn'):
        return 11, None
    if mn in ('retf', 'lret'):
        return 15, None
    raise KeyError('no clock count for %r (%s)' % (mn, insn.op_str))


class TM(GM):
    """mcall's machine with 80286 time (see the module's description)."""

    def __init__(self, cpu_per_frame=0, **kw):
        self.cpf = cpu_per_frame
        self.timing = False             # off while mcall starts the C runtime
        self.frame = 0
        self.cyc = 0
        self.total = 0                  # clocks since the start, frames included
        self._wlog = None
        self._cs = Cs(CS_ARCH_X86, CS_MODE_16)
        self._cs.detail = True
        self._dec = {}
        self._rep = None                # address of the rep instruction iterating
        self._spin = {}
        self._spin_last = None
        self.stamp_at = {}              # linear address -> key: m.stamps[key] = m.total there
        self.stamps = {}
        super().__init__(**kw)
        self._spins = {self.lin(self.seg(s), o): what for (s, o), what in SPINS.items()}
        self.uc.hook_add(UC_HOOK_CODE, self._clock)
        self.timing = True

    # ---- time
    def _vsync(self):
        self.frame += 1
        ds = self.ds
        v = self.word(ds, 0x109E)
        self.poke(ds, 0x109E, struct.pack('<H', (v + 1) & 0xFFFF))
        tseg = self.seg(0x0B91)
        for b in range(0, 0x100, 0x10):
            act, done, cnt, tgt = struct.unpack('<HHii', self.mem(tseg, b, 12))
            if act == 1 and done != 1:
                cnt += 1
                self.poke(tseg, b + 4, struct.pack('<i', cnt))
                if cnt >= tgt:
                    self.poke(tseg, b + 2, struct.pack('<H', 1))

    def _advance(self, n):
        self.total += n
        self.cyc += n
        while self.cpf and self.cyc >= self.cpf:
            self.cyc -= self.cpf
            self._vsync()

    def _retrace(self):
        return self.cpf * RETRACE_LINES // LINES

    def wait_vsync(self):
        """Time passes to the next VSYNC."""
        if self.cpf:
            self._advance(self.cpf - self.cyc)
        else:
            self._vsync()

    def _insn(self, address, size):
        d = self._dec.get(address)
        if d is None or d.size != size:
            code = bytes(self.uc.mem_read(address, size))
            d = next(self._cs.disasm(code, address))
            self._dec[address] = d
        return d

    def _clock(self, uc, address, size, ud):
        if not self.timing:
            return
        key = self.stamp_at.get(address)
        if key is not None:                             # before this instruction's clocks
            self.stamps.setdefault(key, self.total)
        what = self._spins.get(address)
        if what is not None:
            key = (address, self.frame)
            if self._spin_last == key:                  # back at the head: it spins
                if what == 'vsync':
                    self.wait_vsync()
                elif self.cpf and self.cyc < self._retrace():
                    self._advance(self._retrace() - self.cyc)
            self._spin_last = (address, self.frame)
        d = self._insn(address, size)
        if d.prefix[0] in (0xF2, 0xF3) and d.mnemonic.split()[0].startswith('rep'):
            base, per = REP[d.mnemonic.split()[-1]]
            cx = uc.reg_read(_CX)
            n = (per if cx else 0) + (0 if self._rep == address else base)
            self._rep = address if cx else None
            self._advance(n)
            return
        self._rep = None
        n, br = clocks(d, uc.reg_read(_CL) if d.opcode[0] in (0xD2, 0xD3) else 0)
        if br is not None:
            n += br[0] if _taken(d.mnemonic, uc.reg_read(_FLAGS), uc.reg_read(_CX)) else br[1]
        self._advance(n)

    def _in(self, uc, port, size, ud):
        if port in (0x60, 0xA0) and self.cpf and self.timing:
            v = 0x04 | (0x20 if self.cyc < self._retrace() else 0)
            if self.trace_ports:
                self.ports.append(('in', port, v))
            return v
        return super()._in(uc, port, size, ud)

    # ---- the writes into a destination
    def log_writes(self, buf):
        """Log every byte written into buffer buf (10, 11: VRAM page; 12: the memory planes)
        from now on into self.writes as (plane, offset, value, frame, cyc). None stops."""
        if getattr(self, '_wh', None) is not None:
            self.uc.hook_del(self._wh)
            self._wh = None
        self._wlog = buf
        self.writes = []
        if buf == 12:
            segs = self.mem_planes()
            lo = [s * 16 for s in segs]

            def hook(uc, access, address, size, value, ud):
                for q in range(4):
                    if lo[q] <= address < lo[q] + 32000:
                        for i in range(size):
                            self.writes.append((q, address - lo[q] + i,
                                                (value >> (8 * i)) & 0xFF, self.frame, self.cyc))
            self._wh = self.uc.hook_add(UC_HOOK_MEM_WRITE, hook, begin=min(lo),
                                        end=max(lo) + 32000)

    def _vwrite(self, lin, size, value):
        if self._wlog in (10, 11) and self.draw_page == self._wlog - 10 and \
                not self.grcg_mode & 0x80:
            for i in range(size):
                p, o = self._plane(lin + i)
                self.writes.append((p, o, (value >> (8 * i)) & 0xFF, self.frame, self.cyc))
        super()._vwrite(lin, size, value)


from unicorn.x86_const import UC_X86_REG_CX as _CX, UC_X86_REG_CL as _CL, \
    UC_X86_REG_EFLAGS as _FLAGS  # noqa: E402
