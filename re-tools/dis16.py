#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""dis16 - small reusable 16-bit real-mode disassembly helper (capstone based).

Loads a plain (unpacked) MZ executable at load base 0 -- relocations are *not*
applied, so every relocated word already holds the segment value relative to
base 0 -- and offers

  * linear disassembly of a range,
  * recursive-descent code discovery (near/far calls, jumps, simple
    `jmp/call cs:[bx+table]` jump tables),
  * a names file  (SEG:OFF<TAB>name<TAB>comment)  used to label a listing,
  * a masked "shape" of a function (opcodes without address operands), used
    by advbios_map.py to match functions between two builds.

As a tool:

  dis16.py IMAGE.EXE [--names names.tsv] [--entry SEG:OFF ...]
           [--range SEG:OFF LEN] [--raw] [--out listing.txt]

  --raw     treat the input as a header-less blob loaded at 0000:0000
            (e.g. *.TCM plug-ins)
  --range   only print a linear disassembly of that range
  default   recursive descent from the MZ entry point, all --entry points and
            every code address in the names file (comment not starting 'data')

Addresses are always SEG:OFF relative to load base 0.  Listings are the
game's code: write them to resources/derived/listing/, never into docs/.
"""
import argparse
import struct
import sys

import capstone
from capstone import x86_const as X

_md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
_md.detail = True
_md.skipdata = False


def u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def parse_addr(s):
    seg, off = s.split(':')
    return int(seg, 16), int(off, 16)


class Image:
    """A real-mode image loaded at segment 0."""

    def __init__(self, data, entry=None, relocs=(), stack=None, segs=(0,)):
        self.data = bytes(data)
        self.entry = entry            # (seg, off) or None
        self.relocs = sorted(relocs)  # linear offsets of relocated words
        self.relset = set(self.relocs)
        self.stack = stack
        self.segs = sorted(set(segs))  # known segment values (paragraphs)

    @classmethod
    def load_mz(cls, path):
        d = open(path, 'rb').read()
        if d[:2] != b'MZ':
            raise ValueError('%s: not an MZ file' % path)
        last, pages, nrel, hdr, _mn, _mx, ss, sp, _ck, ip, cs, relo = \
            struct.unpack_from('<12H', d, 2)
        size = pages * 512 - ((512 - last) if last else 0)
        img = d[hdr * 16:size]
        rel = []
        segs = {0, cs}
        for i in range(nrel):
            o, s = struct.unpack_from('<HH', d, relo + i * 4)
            lin = s * 16 + o
            rel.append(lin)
            segs.add(u16(img, lin))
        return cls(img, (cs, ip), rel, (ss, sp), segs)

    @classmethod
    def load_raw(cls, path):
        return cls(open(path, 'rb').read(), (0, 0))

    # -- address helpers ---------------------------------------------------
    def seg_of(self, lin):
        """Greatest known segment whose base is <= lin."""
        best = 0
        for s in self.segs:
            if s * 16 <= lin:
                best = s
        return best

    def fmt(self, lin, seg=None):
        if seg is None:
            seg = self.seg_of(lin)
        return '%04X:%04X' % (seg, lin - seg * 16)

    def lin(self, seg, off):
        return seg * 16 + off

    def u8(self, lin):
        return self.data[lin]

    def u16(self, lin):
        return u16(self.data, lin)

    # -- disassembly -------------------------------------------------------
    def insn(self, lin, seg=None):
        """Decode one instruction at linear address; returns capstone insn
        (address field = offset within seg) or None."""
        if seg is None:
            seg = self.seg_of(lin)
        for i in _md.disasm(self.data[lin:lin + 16], lin - seg * 16, 1):
            return i
        return None

    def linear(self, lin, length, seg=None):
        if seg is None:
            seg = self.seg_of(lin)
        end = lin + length
        while lin < end:
            i = self.insn(lin, seg)
            if i is None:
                yield lin, None
                lin += 1
                continue
            yield lin, i
            lin += i.size


FLOW_END = {X.X86_INS_RET, X.X86_INS_RETF, X.X86_INS_IRET, X.X86_INS_JMP,
            X.X86_INS_LJMP, X.X86_INS_RETFQ, X.X86_INS_IRETD}


class Analysis:
    """Recursive-descent code discovery."""

    def __init__(self, img):
        self.img = img
        self.insns = {}       # lin -> (seg, size, mnemonic, op_str)
        self.funcs = {}       # lin -> seg   (call targets / entries)
        self.labels = set()   # jump targets
        self.xrefs = {}       # lin target -> set(lin source)
        self.tables = {}      # lin table -> [targets]
        self.func_of = {}     # insn lin -> function lin

    def add_xref(self, dst, src):
        self.xrefs.setdefault(dst, set()).add(src)

    def explore(self, seg, off, is_func=True):
        img = self.img
        start = seg * 16 + off
        if is_func:
            self.funcs.setdefault(start, seg)
        work = [(start, start)]
        while work:
            lin, fn = work.pop()
            while True:
                if lin in self.insns or lin >= len(img.data):
                    break
                i = img.insn(lin, seg)
                if i is None:
                    break
                self.insns[lin] = (seg, i.size, i.mnemonic, i.op_str)
                self.func_of[lin] = fn
                nxt = lin + i.size
                ops = i.operands
                iid = i.id
                grp = i.groups
                if iid in (X.X86_INS_CALL, X.X86_INS_JMP) or \
                        X.X86_GRP_JUMP in grp or iid in (
                        X.X86_INS_LOOP, X.X86_INS_LOOPE, X.X86_INS_LOOPNE,
                        X.X86_INS_JCXZ):
                    if ops and ops[0].type == X.X86_OP_IMM:
                        tgt = seg * 16 + (ops[0].imm & 0xFFFF)
                        self.add_xref(tgt, lin)
                        if iid == X.X86_INS_CALL:
                            self.funcs.setdefault(tgt, seg)
                            work.append((tgt, tgt))
                        else:
                            self.labels.add(tgt)
                            work.append((tgt, fn))
                    elif ops and ops[0].type == X.X86_OP_MEM:
                        self._table(i, lin, seg, fn, work,
                                    iid == X.X86_INS_CALL)
                elif iid in (X.X86_INS_LCALL, X.X86_INS_LJMP):
                    # far immediate: bytes  9A/EA off16 seg16
                    b = img.data[lin:lin + 5]
                    if b[0] in (0x9A, 0xEA):
                        toff, tseg = struct.unpack_from('<HH', b, 1)
                        if (lin + 3) in img.relset or tseg in img.segs:
                            tgt = tseg * 16 + toff
                            self.add_xref(tgt, lin)
                            self.funcs.setdefault(tgt, tseg)
                            # explore in the other segment (shared state)
                            self.explore(tseg, toff, True)
                if iid in FLOW_END:
                    break
                lin = nxt

    def _table(self, i, lin, seg, fn, work, is_call):
        """jmp/call word ptr cs:[reg*? + disp] -> read a table of near words."""
        op = i.operands[0]
        m = op.mem
        if m.segment != X.X86_REG_CS or m.disp == 0:
            return
        if op.size != 2 or (m.base == 0 and m.index == 0):
            return
        img = self.img
        tab = seg * 16 + (m.disp & 0xFFFF)
        out = []
        p = tab
        lo = None
        while p + 2 <= len(img.data):
            if p != tab and (p in self.insns or p in self.tables):
                break
            if lo is not None and p >= lo:
                break
            off = img.u16(p)
            tgt = seg * 16 + off
            if tgt >= len(img.data) or abs(tgt - tab) > 0x4000:
                break
            j = img.insn(tgt, seg)
            if j is None:
                break
            out.append(tgt)
            if tgt > tab and (lo is None or tgt < lo):
                lo = tgt
            p += 2
            if len(out) >= 256:
                break
        self.tables[tab] = out
        for t in out:
            self.add_xref(t, lin)
            if is_call:
                self.funcs.setdefault(t, seg)
                work.append((t, t))
            else:
                self.labels.add(t)
                work.append((t, t))
                self.funcs.setdefault(t, seg)

    # -- function extents and shapes --------------------------------------
    def func_insns(self, fn):
        """Sorted instruction addresses belonging to function fn."""
        return sorted(a for a, f in self.func_of.items() if f == fn)

    def shape(self, fn, limit=400):
        """Address-independent signature of a function: for each instruction
        the opcode bytes with displacement/immediate operands masked."""
        img = self.img
        out = []
        for a in self.func_insns(fn)[:limit]:
            seg = self.insns[a][0]
            i = img.insn(a, seg)
            out.append(mask_insn(i))
        return tuple(out)


def mask_insn(i):
    """Mnemonic + operand kinds; immediates kept when small (<0x100) because
    they are rarely addresses, memory displacements and branch targets
    dropped."""
    parts = [i.mnemonic]
    for op in i.operands:
        if op.type == X.X86_OP_REG:
            parts.append(i.reg_name(op.reg))
        elif op.type == X.X86_OP_IMM:
            if X.X86_GRP_JUMP in i.groups or i.id in (
                    X.X86_INS_CALL, X.X86_INS_LCALL, X.X86_INS_LJMP,
                    X.X86_INS_LOOP, X.X86_INS_JCXZ, X.X86_INS_JMP):
                parts.append('T')
            else:
                v = op.imm & 0xFFFF
                parts.append('#%x' % v if v < 0x100 else '#')
        elif op.type == X.X86_OP_MEM:
            m = op.mem
            parts.append('[%s+%s%s]' % (
                i.reg_name(m.base) if m.base else '',
                i.reg_name(m.index) if m.index else '',
                '+d' if m.disp else ''))
    return ' '.join(parts)


# -- names file -----------------------------------------------------------
def load_names(path):
    """-> {(seg, off): (name, comment)}"""
    names = {}
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        f = line.split('\t')
        seg, off = parse_addr(f[0])
        names[(seg, off)] = (f[1] if len(f) > 1 else '',
                             f[2] if len(f) > 2 else '')
    return names


def listing(img, an, names=None, out=sys.stdout):
    names = names or {}
    lin_names = {s * 16 + o: v for (s, o), v in names.items()}
    prev_end = None
    for a in sorted(an.insns):
        seg, size, mn, ops = an.insns[a]
        if prev_end is not None and a != prev_end:
            out.write('\n')
        if a in an.funcs or a in lin_names:
            nm = lin_names.get(a, ('sub_%04X_%04X' % (seg, a - seg * 16), ''))
            out.write('\n; ---- %s  %s\n' % (nm[0], nm[1]))
            xr = sorted(an.xrefs.get(a, ()))
            if xr:
                out.write(';      xrefs: %s\n' % ' '.join(
                    img.fmt(x) for x in xr[:12]))
        elif a in an.labels:
            out.write('  loc_%04X:\n' % (a - seg * 16))
        raw = img.data[a:a + size].hex()
        out.write('%s  %-16s %-7s %s\n' % (img.fmt(a, seg), raw, mn, ops))
        prev_end = a + size


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('image')
    ap.add_argument('--raw', action='store_true')
    ap.add_argument('--names')
    ap.add_argument('--entry', action='append', default=[])
    ap.add_argument('--range', nargs=2, metavar=('SEG:OFF', 'LEN'))
    ap.add_argument('--out')
    a = ap.parse_args()
    img = Image.load_raw(a.image) if a.raw else Image.load_mz(a.image)
    out = open(a.out, 'w', encoding='utf-8') if a.out else sys.stdout
    if a.range:
        seg, off = parse_addr(a.range[0])
        for lin, i in img.linear(seg * 16 + off, int(a.range[1], 0), seg):
            if i is None:
                out.write('%s  %02x               db\n' % (
                    img.fmt(lin, seg), img.data[lin]))
            else:
                out.write('%s  %-16s %-7s %s\n' % (
                    img.fmt(lin, seg), i.bytes.hex(), i.mnemonic, i.op_str))
        return
    an = Analysis(img)
    names = load_names(a.names) if a.names else {}
    if img.entry:
        an.explore(*img.entry)
    for e in a.entry:
        an.explore(*parse_addr(e))
    for (seg, off), (nm, cm) in names.items():
        if not cm.startswith('data') and seg * 16 + off < len(img.data):
            an.explore(seg, off)
    listing(img, an, names, out)


if __name__ == '__main__':
    main()
