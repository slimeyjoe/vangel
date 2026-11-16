#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""x68dis - Human68k .X executable disassembler (MC68000, capstone based).

  x68dis.py FILE.X [--names NAMES.tsv] [--entry OFF ...] [--range OFF LEN] [--out FILE]
            [--header] [--xref OFF]

The .X file is loaded at base 0, so every relocated longword already holds an image offset
(text starts at 0, data at text_size, bss after data).  Addresses printed are those image
offsets ("t" prefix = text section offset, which is the same number).

Discovery: recursive descent from the entry point, every --entry, every name in the names
file, every `link a6,#n` prologue that follows an rts/rte/jmp/bra or a NUL byte, and every
relocated longword in the data section that points into the text section.

Annotations: Human68k DOS calls (line-F words FFxx), IOCS calls (trap #15 with the number
in d0 from the preceding moveq/move.l), other traps, references to strings, names.
Names file rows: OFF<TAB>name<TAB>comment (hex image offset).
Listings are the game's code: write them under resources/derived/, never into docs/.
"""
import argparse
import re
import struct
import sys

import capstone

DOS = {0x00: 'EXIT', 0x01: 'GETCHAR', 0x02: 'PUTCHAR', 0x06: 'INPOUT', 0x07: 'INKEY', 0x08: 'GETC',
       0x09: 'PRINT', 0x0A: 'GETS', 0x0B: 'KEYSNS', 0x0C: 'KFLUSH', 0x0D: 'FFLUSH', 0x0E: 'CHGDRV',
       0x10: 'CONSNS', 0x19: 'CURDRV', 0x1B: 'FGETC', 0x1D: 'FPUTC', 0x1E: 'FPUTS', 0x1F: 'ALLCLOSE',
       0x20: 'SUPER', 0x21: 'FNCKEY', 0x22: 'KNJCTRL', 0x23: 'CONCTRL', 0x24: 'KEYCTRL',
       0x25: 'INTVCS', 0x27: 'GETTIM2', 0x29: 'NAMESTS', 0x2A: 'GETDATE', 0x2C: 'GETTIME',
       0x30: 'VERNUM', 0x31: 'KEEPPR', 0x33: 'BREAKCK', 0x35: 'INTVCG', 0x36: 'DSKFRE',
       0x37: 'NAMECK', 0x39: 'MKDIR', 0x3A: 'RMDIR', 0x3B: 'CHDIR', 0x3C: 'CREATE', 0x3D: 'OPEN',
       0x3E: 'CLOSE', 0x3F: 'READ', 0x40: 'WRITE', 0x41: 'DELETE', 0x42: 'SEEK', 0x43: 'CHMOD',
       0x44: 'IOCTRL', 0x45: 'DUP', 0x46: 'DUP2', 0x47: 'CURDIR', 0x48: 'MALLOC', 0x49: 'MFREE',
       0x4A: 'SETBLOCK', 0x4B: 'EXEC', 0x4C: 'EXIT2', 0x4D: 'WAIT', 0x4E: 'FILES', 0x4F: 'NFILES',
       0x80: 'SETPDB', 0x81: 'GETPDB', 0x82: 'SETENV', 0x83: 'GETENV', 0x84: 'VERIFYG',
       0x85: 'COMMON', 0x86: 'RENAME', 0x87: 'FILEDATE', 0x88: 'MALLOC2', 0x8A: 'MAKETMP',
       0x8B: 'NEWFILE', 0x8C: 'LOCK', 0x8F: 'ASSIGN', 0xF0: 'EXITVC', 0xF1: 'CTRLVC',
       0xF2: 'ERRJVC', 0xF3: 'DISKRED', 0xF4: 'DISKWRT', 0xF5: 'INDOSFLG', 0xF6: 'SUPER_JSR',
       0xF7: 'BUS_ERR', 0xF8: 'OPEN_PR', 0xF9: 'KILL_PR', 0xFA: 'GET_PR', 0xFB: 'SUSPEND_PR',
       0xFC: 'SLEEP_PR', 0xFD: 'SEND_PR', 0xFE: 'TIME_PR', 0xFF: 'CHANGE_PR'}
for _k in list(DOS):                      # Human68k 2.x/3.x: 50h..7Fh = 80h..AFh
    if 0x80 <= _k <= 0xAF:
        DOS.setdefault(_k - 0x30, DOS[_k])

IOCS = dict(enumerate(
    'B_KEYINP B_KEYSNS B_SFTSNS KEY_INIT BITSNS SKEYSET LEDCTRL LEDSET KEYDLY KEYREP _0A _0B '
    'TVCTRL LEDMOD TGUSEMD DEFCHR CRTMOD CONTRAST HSVTORGB TPALET TPALET2 TCOLOR FNTADR VRAMGET '
    'VRAMPUT FNTGET TEXTGET TEXTPUT CLIPPUT SCROLL B_CURON B_CUROFF B_PUTC B_PRINT B_COLOR '
    'B_LOCATE B_DOWN_S B_UP_S B_UP B_DOWN B_RIGHT B_LEFT B_CLR_ST B_ERA_ST B_INS B_DEL B_CONSOL '
    'B_PUTMES SET232C LOF232C INP232C ISNS232C OSNS232C OUT232C _36 _37 _38 _39 _3A JOYGET '
    'INIT_PRN SNSPRN OUTLPT OUTPRN B_SEEK B_VERIFY B_READDI B_DSKINI B_DRVSNS B_WRITE B_READ '
    'B_RECALI B_ASSIGN B_WRITED B_READID B_BADFMT B_READDL B_FORMAT B_DRVCHK B_EJECT DATEBCD '
    'DATESET TIMEBCD TIMESET DATEGET DATEBIN TIMEGET TIMEBIN DATECNV TIMECNV DATEASC TIMEASC '
    'DAYASC ALARMMOD ALARMSET ALARMGET ADPCMOUT ADPCMINP ADPCMAOT ADPCMAIN ADPCMLOT ADPCMLIN '
    'ADPCMSNS ADPCMMOD OPMSET OPMSNS OPMINTST TIMERDST VDISPST CRTCRAS HSYNCST PRNINTST MS_INIT '
    'MS_CURON MS_CUROF MS_STAT MS_GETDT MS_CURGT MS_CURST MS_LIMIT MS_OFFTM MS_ONTM MS_PATST '
    'MS_SEL MS_SEL2 SKEY_MOD DENSNS ONTIME B_INTVCS B_SUPER B_BPEEK B_WPEEK B_LPEEK B_MEMSTR '
    'B_BPOKE B_WPOKE B_LPOKE B_MEMSET DMAMOVE DMAMOV_A DMAMOV_L DMAMODE BOOTINF ROMVER G_CLR_ON '
    '_91 _92 _93 GPALET _95 _96 _97 _98 _99 _9A _9B _9C _9D _9E _9F SFTJIS JISSFT AKCONV RMACNV '
    'DAKJOB HANJOB _A6 _A7 _A8 _A9 _AA _AB SYS_STAT B_CONMOD OS_CURON OS_CUROF DRAWMODE APAGE '
    'VPAGE HOME WINDOW WIPE PSET POINT LINE BOX FILL CIRCLE PAINT SYMBOL GETGRM PUTGRM SP_INIT '
    'SP_ON SP_OFF SP_CGCLR SP_DEFCG SP_GTPCG SP_REGST SP_REGGT BGSCRLST BGSCRLGT BGCTRLST '
    'BGCTRLGT BGTEXTCL BGTEXTST BGTEXTGT SPALET _D0 _D1 _D2 TXXLINE TXYLINE TXLINE TXBOX TXFILL '
    'TXREV _D9 _DA _DB _DC _DD _DE TXRASCPY'.split()))
IOCS.update({0xFD: 'ABORTRST', 0xFE: 'IPLERR', 0xFF: 'ABORTJOB'})


class X:
    def __init__(self, path):
        d = open(path, 'rb').read()
        assert d[:2] == b'HU', 'not a Human68k .X file'
        (self.base, self.entry, self.tsize, self.dsize, self.bsize, self.rsize,
         self.ssize) = struct.unpack_from('>7I', d, 4)
        self.img = d[0x40:0x40 + self.tsize + self.dsize]
        r = d[0x40 + self.tsize + self.dsize:0x40 + self.tsize + self.dsize + self.rsize]
        self.relocs = set()
        pos, i = 0, 0
        while i < len(r):
            w = struct.unpack_from('>H', r, i)[0]; i += 2
            if w == 1:
                w = struct.unpack_from('>I', r, i)[0]; i += 4
            if w & 1:                     # odd: word relocation (unused by most linkers)
                w &= ~1
            pos += w
            self.relocs.add(pos)
        self.md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_M68K_000)
        self.md.detail = False
        self.names = {}
        self.tables = {}

    def sect(self, a):
        if a < self.tsize: return 't'
        if a < self.tsize + self.dsize: return 'd'
        if a < self.tsize + self.dsize + self.bsize: return 'b'
        return '?'

    def long(self, a): return struct.unpack_from('>I', self.img, a)[0]
    def word(self, a): return struct.unpack_from('>H', self.img, a)[0]

    def cstr(self, a, maxlen=80):
        if not (0 <= a < len(self.img)): return None
        e = self.img.find(b'\0', a, a + 400)
        if e < 0 or e == a: return None
        s = self.img[a:e]
        try:
            t = s.decode('cp932')
        except UnicodeDecodeError:
            return None
        if any(ord(c) < 0x20 and c not in '\r\n\t\x1b' for c in t): return None
        if len(s) < 3: return None
        t = t.replace('\n', '\\n').replace('\r', '\\r').replace('\x1b', '\\e')
        return t[:maxlen]

    def insn(self, a):
        """(size, mnemonic, operands) at a; handles line-F DOS calls."""
        w = self.word(a)
        if w & 0xFF00 == 0xFF00:
            return 2, 'DOS', '_%s' % DOS.get(w & 0xFF, '%02X' % (w & 0xFF))
        for i in self.md.disasm(self.img[a:a + 10], a, 1):
            return i.size, i.mnemonic, i.op_str
        return 2, 'dc.w', '$%04x' % w

    def discover(self, entries):
        code = {}
        work = list(entries)
        while work:
            a = work.pop()
            while 0 <= a < self.tsize and a not in code:
                n, m, o = self.insn(a)
                code[a] = (n, m, o)
                if m == 'dc.w': break
                if m.startswith(('b', 'j', 'db')) and m not in ('btst', 'bset', 'bclr', 'bchg') and '(' not in o:
                    for t in re.findall(r'\$([0-9a-f]+)', o):
                        t = int(t, 16)
                        if t < self.tsize and not t & 1:
                            work.append(t)
                mm = re.match(r'\$([0-9a-f]+)\(pc, d\d\.w\)', o)
                if m == 'jmp' and mm:
                    for t in self.switch(a, int(mm.group(1), 16)):
                        work.append(t)
                if m in ('pea', 'lea') and a + 2 in self.relocs:
                    t = self.long(a + 2)
                    if t < self.tsize and not self.cstr(t): pass
                a += n
                if m in ('rts', 'rte', 'jmp', 'bra', 'bra.s', 'bra.w', 'rtr') or (m == 'DOS' and o in ('_EXIT', '_EXIT2', '_KEEPPR')):
                    break
        return code

    def switch(self, a, tab):
        """GCC switch: moveq #n,d1; cmp.l d1,d0; bhi; add.l d0,d0; move.w tab(pc,d0.l),d1;
        jmp tab(pc,d1.w).  Returns the case targets and records the table."""
        n = None
        for back in range(4, 24, 2):
            w = self.word(a - back)
            if w & 0xF100 == 0x7000:              # moveq #imm,dN
                n = w & 0xFF; break
            if w == 0x0c80:                        # cmpi.l #imm,d0
                n = self.long(a - back + 2); break
        if n is None or n > 512: return []
        ts = []
        for k in range(n + 1):
            v = self.word(tab + 2 * k)
            if v & 0x8000: v -= 0x10000
            ts.append(tab + v)
        self.tables[tab] = ts
        return [t for t in ts if 0 <= t < self.tsize and not t & 1]

    def entries(self):
        e = {self.entry} | {a for a in self.names if a < self.tsize}
        img = self.img
        for a in range(0, self.tsize - 4, 2):
            if img[a:a + 2] == b'\x4e\x56':          # link a6,#
                p = img[a - 2:a] if a >= 2 else b'\x4e\x75'
                if p in (b'\x4e\x75', b'\x4e\x73') or a == 0 or img[a - 1] == 0 or p[0] in (0x60,) or p == b'\x4e\xd0':
                    e.add(a)
            if img[a:a + 4] == b'\x48\xe7' and a >= 2 and img[a - 2:a] == b'\x4e\x75':
                e.add(a)
        for r in self.relocs:
            if self.tsize <= r < self.tsize + self.dsize:
                t = self.long(r)
                if t < self.tsize and t & 1 == 0 and not self.cstr(t):
                    e.add(t)
        return e

    def annotate(self, a, m, o, prev):
        c = []
        if m == 'trap':
            n = int(o.lstrip('#$').replace('$', ''), 16) if '$' in o else int(o.lstrip('#'))
            if n == 15 and prev:
                mm = re.search(r'#\$([0-9a-f]+), d0', prev) or re.search(r'#(\d+), d0', prev)
                if mm:
                    v = int(mm.group(1), 16 if '$' in prev.split(',')[0] else 10) & 0xFF
                    c.append('IOCS _%s' % IOCS.get(v, '%02X' % v))
            elif n != 15:
                c.append('trap #%d' % n)
        for t in re.findall(r'(?<![-\w])\$([0-9a-f]+)(?=\.l|\.w|\(pc|,|$)', o):
            t = int(t, 16)
            if t in self.names: c.append(self.names[t][0])
            elif t >= 0x100 and t < len(self.img) + self.bsize:
                s = self.cstr(t) if t >= self.tsize or m.split('.')[0] in ('pea', 'lea', 'move', 'movea') else None
                if s: c.append('"%s"' % s)
        return '; '.join(c)

    def listing(self, code, out):
        prev = None
        last = None
        for a in sorted(code):
            n, m, o = code[a]
            if last is not None and a != last:
                out.write('\n')
            if a in self.names:
                out.write('\n%s:  ; %s\n' % (self.names[a][0], self.names[a][1]))
            ann = self.annotate(a, m, o, prev)
            hx = self.img[a:a + n].hex()
            out.write('t%05x  %-20s %-8s %-36s%s\n' % (a, hx, m, o, ('; ' + ann) if ann else ''))
            mm = re.match(r'\$([0-9a-f]+)\(pc, d\d\.w\)', o)
            if m == 'jmp' and mm and int(mm.group(1), 16) in self.tables:
                for k, t in enumerate(self.tables[int(mm.group(1), 16)]):
                    nm = self.names.get(t, ('',))[0]
                    out.write('          case %3d (%02xh) -> t%05x %s\n' % (k, k, t, nm))
            prev = '%s %s' % (m, o)
            last = a + n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--names')
    ap.add_argument('--entry', nargs='*', default=[])
    ap.add_argument('--range', nargs=2)
    ap.add_argument('--out')
    ap.add_argument('--header', action='store_true')
    ap.add_argument('--xref', nargs='*', default=[], help='list instructions referencing OFF')
    a = ap.parse_args()
    x = X(a.file)
    if a.names:
        for l in open(a.names, encoding='utf-8'):
            if l.startswith('#') or not l.strip(): continue
            f = l.rstrip('\n').split('\t')
            x.names[int(f[0], 16)] = (f[1], f[2] if len(f) > 2 else '')
    out = open(a.out, 'w', encoding='utf-8') if a.out else sys.stdout
    if a.header:
        out.write('text %05x data %05x (at %05x) bss %05x (at %05x) relocs %d entry t%05x\n' % (
            x.tsize, x.dsize, x.tsize, x.bsize, x.tsize + x.dsize, len(x.relocs), x.entry))
        return
    if a.range:
        s, n = int(a.range[0], 16), int(a.range[1], 16)
        code = {}
        p = s
        while p < s + n:
            i = x.insn(p); code[p] = i; p += i[0]
        x.listing(code, out)
        return
    code = x.discover(x.entries() | {int(e, 16) for e in a.entry})
    if a.xref:
        tg = [int(t, 16) for t in a.xref]
        for p in sorted(code):
            o = code[p][2]
            vals = [int(v, 16) for v in re.findall(r'\$([0-9a-f]+)', o)]
            if any(t in vals for t in tg):
                out.write('t%05x %s %s\n' % (p, code[p][1], o))
        return
    x.listing(code, out)


if __name__ == '__main__':
    main()
