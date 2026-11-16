#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""madis - annotated disassembly of Virgin Angel's PC-98 engine M.EXE (after EXEPACK removal).

  madis.py [--names 'docs/re/listing/m-names*.tsv'] [--out FILE] [--func SEG:OFF ...]

Loads resources/derived/M_unpacked.EXE (re-tools/exeunpack.py output), runs dis16's recursive
descent from the entry point, the names file's code addresses and the far-call targets, and
writes a listing in which
  * far/near call targets carry their names,
  * immediates and [disp] operands that point into DGROUP (segment 0BAFh) carry the global's
    name or, for a C string, the string text (Shift-JIS decoded),
  * every function header carries its callers.
Names file rows: SEG:OFF<TAB>name<TAB>comment for code, DS:OFF<TAB>name<TAB>comment for
globals.  --func prints only the given functions (with their callees' names).
The listing is the game's code: write it to resources/derived/listing/, never into docs/.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dis16  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'resources/derived/M_unpacked.EXE')
DGROUP = 0x0BAF


def load_names(path):
    import glob
    code, data = {}, {}
    paths = sorted(glob.glob(path)) if path else []
    for line in (ln for pth in paths for ln in open(pth, encoding='utf-8')):
        if not line.strip() or line.startswith('#'):
            continue
        f = line.rstrip('\n').split('\t')
        while len(f) < 3:
            f.append('')
        a, n, c = f[0], f[1], f[2]
        s, o = a.split(':')
        if s.upper() == 'DS':
            data[(DGROUP, int(o, 16))] = (n, c)
        elif c.startswith('data') or n.startswith('g_'):
            data[(int(s, 16), int(o, 16))] = (n, c)
        else:
            code[(int(s, 16), int(o, 16))] = (n, c)
    return code, data


def cstring(img, off):
    lin = DGROUP * 16 + off
    if lin >= len(img.data):
        return None
    b = bytearray()
    i = lin
    while i < len(img.data) and img.data[i] and len(b) < 70:
        b.append(img.data[i])
        i += 1
    if len(b) < 2 or (i < len(img.data) and img.data[i] != 0):
        return None
    try:
        t = b.decode('cp932')
    except UnicodeDecodeError:
        return None
    if sum(1 for ch in t if ch.isprintable()) < len(t) - 1:
        return None
    return t


SEGPTR = {}   # DGROUP offset of a relocated segment word -> segment value


def init_segptr(img):
    base = DGROUP * 16
    for lin in img.relocs:
        if lin >= base:
            SEGPTR[lin - base] = img.u16(lin)


def data_label(img, dnames, off, seg=DGROUP):
    if (seg, off) in dnames:
        return dnames[(seg, off)][0]
    best = None
    for (sg, k) in dnames:
        if sg == seg and k < off <= k + 0x40 and (best is None or k > best):
            best = k
    if best is not None:
        return '%s+%X' % (dnames[(seg, best)][0], off - best)
    return None


ES = [None]


def annotate(img, cnames, dnames, seg, mn, ops):
    notes = []
    m = re.match(r'0x([0-9a-f]+), 0x([0-9a-f]+)$', ops)
    if mn in ('lcall', 'ljmp') and m:
        t = (int(m.group(1), 16), int(m.group(2), 16))
        notes.append(cnames.get(t, ('sub_%04X_%04X' % t, ''))[0])
    elif mn in ('call', 'jmp') and re.match(r'0x[0-9a-f]+$', ops):
        t = (seg, int(ops, 16))
        if t in cnames:
            notes.append(cnames[t][0])
        elif mn == 'call':
            notes.append('sub_%04X_%04X' % t)
    else:
        for mm in re.finditer(r'(?<![ec]s:)\[(0x[0-9a-f]+)\]', ops):
            v = int(mm.group(1), 16)
            lab = data_label(img, dnames, v)
            if mn == 'mov' and ops.startswith('es,') and v in SEGPTR:
                lab = (lab + '=' if lab else '') + 'seg %04X' % SEGPTR[v]
            notes.append(lab or 'DS:%04X' % v)
        for mm in re.finditer(r'es:\[(0x[0-9a-f]+)\]', ops):
            if ES[0] is not None:
                v = int(mm.group(1), 16)
                lab = data_label(img, dnames, v, ES[0])
                notes.append(lab or '%04X:%04X' % (ES[0], v))
        if mn in ('push', 'mov') and not notes:
            mm = re.search(r'(?:^|, )0x([0-9a-f]{3,4})$', ops)
            if mm:
                v = int(mm.group(1), 16)
                if v in dnames:
                    notes.append('&' + dnames[v][0])
                else:
                    s = cstring(img, v)
                    if s:
                        notes.append('"%s"' % s)
    return '  ; ' + ', '.join(notes) if notes else ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--names', default=os.path.join(ROOT, 'docs/re/listing/m-names*.tsv'),
                    help='names file(s), a glob (default: every docs/re/listing/m-names*.tsv)')
    ap.add_argument('--exe', default=EXE)
    ap.add_argument('--out')
    ap.add_argument('--func', action='append', default=[])
    a = ap.parse_args()
    cnames, dnames = load_names(a.names)
    img = dis16.Image.load_mz(a.exe)
    init_segptr(img)
    an = dis16.Analysis(img) if hasattr(dis16, 'Analysis') else None
    if an is None:
        raise SystemExit('dis16 has no Analysis class')
    if img.entry:
        an.explore(*img.entry)
    for (s, o), (n, c) in cnames.items():
        if not c.startswith('data'):
            an.explore(s, o)
    # far call targets found by scanning relocated lcall operands
    changed = True
    while changed:
        changed = False
        for lin, (seg, size, mn, ops) in list(an.insns.items()):
            m = re.match(r'0x([0-9a-f]+), 0x([0-9a-f]+)$', ops)
            if mn == 'lcall' and m:
                t = int(m.group(1), 16) * 16 + int(m.group(2), 16)
                if t not in an.funcs:
                    an.explore(int(m.group(1), 16), int(m.group(2), 16))
                    changed = True
    out = open(a.out, 'w', encoding='utf-8') if a.out else sys.stdout
    lin_names = {s * 16 + o: v for (s, o), v in cnames.items()}
    want = None
    if a.func:
        want = set()
        for f in a.func:
            s, o = dis16.parse_addr(f)
            want.add(s * 16 + o)
    funcs = sorted(an.funcs)
    cur = None
    prev_end = None
    for addr in sorted(an.insns):
        seg, size, mn, ops = an.insns[addr]
        if addr in an.funcs:
            cur = addr
        if want is not None and cur not in want:
            continue
        if prev_end is not None and addr != prev_end:
            out.write('\n')
        if addr in an.funcs or addr in lin_names:
            nm = lin_names.get(addr, ('sub_%04X_%04X' % (seg, addr - seg * 16), ''))
            out.write('\n; ---- %s  %s\n' % (nm[0], nm[1]))
            xr = sorted(an.xrefs.get(addr, ()))
            if xr:
                callers = []
                for x in xr[:16]:
                    f = max((ff for ff in funcs if ff <= x), default=None)
                    fs = img.fmt(x)
                    if f is not None and f in lin_names:
                        fs += '(%s)' % lin_names[f][0]
                    callers.append(fs)
                out.write(';      xrefs: %s\n' % ' '.join(callers))
        elif addr in an.labels:
            out.write('  loc_%04X:\n' % (addr - seg * 16))
        raw = img.data[addr:addr + size].hex()
        if addr in an.funcs or addr in an.labels:
            ES[0] = None
        note = annotate(img, cnames, dnames, seg, mn, ops)
        m = re.match(r'es, word ptr \[(0x[0-9a-f]+)\]$', ops)
        if mn == 'mov' and m and int(m.group(1), 16) in SEGPTR:
            ES[0] = SEGPTR[int(m.group(1), 16)]
        elif re.match(r'es\b', ops) and mn in ('mov', 'pop') or mn == 'les':
            ES[0] = None
        out.write('%s  %-14s %-7s %s%s\n' % (img.fmt(addr, seg), raw[:14], mn, ops, note))
        prev_end = addr + size
    if want is None:
        sys.stderr.write('%d functions, %d instructions\n' % (len(an.funcs), len(an.insns)))


if __name__ == '__main__':
    main()
