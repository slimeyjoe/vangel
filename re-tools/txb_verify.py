#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""txb_verify.py - check re-tools/txb.py against M.EXE's own TXB code under mcall (unicorn).

Runs the original txb_load (0724:0018) on CMD00.TXB with the message count of SCB tag 7,
compares its index (0BA1:003E -> per message {u32 offset, u16 length}) with txb.py, then for
every message calls txb_read_msg (0724:0186) and txb_line (0724:0206) line by line with the
same arguments as the message routine 0315:07FC (output limit 79 bytes) and compares every
decoded line byte for byte with txb.decode_line(..., limit=79).

Usage: $EMU_PYTHON -I re-tools/txb_verify.py [pc98|x68k]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcall import M, ROOT  # noqa: E402
import txb  # noqa: E402


def main():
    plat = sys.argv[1] if len(sys.argv) > 1 else 'pc98'
    files = os.path.join(ROOT, 'resources/original', plat)
    data = open(os.path.join(files, 'CMD00.TXB'), 'rb').read()
    t = txb.Txb(data)
    m = M(files=files, trace_ports=False)
    g = m.seg(0x0BA1)
    m.poke(g, 0x16, b'CMD00.TXB\x00')                 # tag 0Ah: text file name
    m.poke(g, 0x52, struct.pack('<H', len(t.messages)))   # tag 7: message count
    ax, _ = m.call(0x0724, 0x0018)
    assert ax == 1, 'txb_load failed'
    ts, to = m.far(g, 0x3E)[0], m.far(g, 0x3E)[1]
    out = m.alloc(0x60)
    bad = 0
    nlines = 0
    for msg in t.messages:
        rs, ro = m.far(ts, to + 4 * msg.index)
        off, ln = struct.unpack('<IH', m.mem(rs, ro, 6))
        if (off, ln) != (msg.offset, msg.length):
            print('index mismatch msg %d: orig %#x/%d txb.py %#x/%d'
                  % (msg.index, off, ln, msg.offset, msg.length))
            bad += 1
        m.call(0x0724, 0x0186, [ro, rs])
        pos = 0
        for i, raw in enumerate((msg.raw + b'\x1a').split(b'\x00')):
            ax, _ = m.call(0x0724, 0x0206, [ro, rs, pos, 0, out, 0x4F])
            got = m.cstr(out, 0, 0x60)
            want = txb.decode_line(raw, t.dic, limit=0x4F)
            nlines += 1
            last = raw == b'\x1a'
            if last:
                # the 1Ah "line" is not 00h-terminated: txb_read_msg reads length+10 bytes into
                # a reused buffer, so the original runs on into the next message; only the
                # first byte (the control code) is used by 0315:07FC.
                got, ax = got[:1], len(raw) + 1
            if got != want:
                print('msg %d line %d differs:\n  orig %s\n  txb  %s' % (msg.index, i, got.hex(), want.hex()))
                bad += 1
            if ax != len(raw) + 1:
                print('msg %d line %d: source length %d, expected %d' % (msg.index, i, ax, len(raw) + 1))
                bad += 1
            pos += ax
            if got[:1] == b'\x1a':
                break
    print('%s: %d messages, %d lines compared, %d mismatches' % (plat, len(t.messages), nlines, bad))
    bad += verify_layout(m, t, ts, to)
    return 1 if bad else 0


def verify_layout(m, t, ts, to):
    """Phase 2: run the message routine 0315:07FC on every message and compare the rows it
    hands to the line drawer 02BE:015F, the page boundaries (02BE:00BC = page shown) and the
    wait mode of each page with txb.layout().  The input poll 0315:0B7C is patched to report a
    key at once; no timer is installed, so timed pages do not wait."""
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_SS, UC_X86_REG_SP, UC_X86_REG_BP
    assert m.call(0x0315, 0x000E)[0] == 1, 'gfx_init'          # window buffers (02BE:0006)
    m.poke(m.seg(0x0315), 0x0B7C, b'\xb8\x01\x00\xcb')        # mov ax,1 / retf
    cur = {'rows': [], 'pages': []}

    def at_line(uc, a, sz, ud):
        ss, sp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_SP)
        off, seg, row, col = struct.unpack('<4H', m.mem(ss, sp + 4, 8))
        if row <= 3:                    # 02BE:015F returns at once for row > 3
            cur['rows'].append((row, m.cstr(seg, off, 200)))

    def at_page(uc, a, sz, ud):
        ss, bp = uc.reg_read(UC_X86_REG_SS), uc.reg_read(UC_X86_REG_BP)
        mode, = struct.unpack('<h', m.mem(ss, bp - 0x1A, 2))
        nbytes, = struct.unpack('<h', m.mem(ss, bp - 0x12, 2))
        cur['pages'].append((cur['rows'], 'timed' if mode == 1 else 'key', nbytes))
        cur['rows'] = []
    for seg, off, f in ((0x02BE, 0x015F, at_line), (0x0315, 0x0ACA, at_page)):
        a = m.lin(m.seg(seg), off)
        m.uc.hook_add(UC_HOOK_CODE, f, begin=a, end=a)
    bad = npages = 0
    for msg in t.messages:
        cur['rows'], cur['pages'] = [], []
        rs, ro = m.far(ts, to + 4 * msg.index)
        m.call(0x0315, 0x07FC, [ro, rs])
        want = txb.layout(msg)
        npages += len(want)
        if cur['pages'] != want or cur['rows']:
            bad += 1
            print('layout of msg %d differs: %d pages, txb.py %d' % (msg.index, len(cur['pages']), len(want)))
            for i, (a, b) in enumerate(zip(cur['pages'], want)):
                if a != b:
                    print('  page %d\n    orig %r\n    txb  %r' % (i, a, b))
                    break
            if os.environ.get('TXB_VERBOSE'):
                for a in cur['pages']:
                    print('   orig', a[1], a[2], [(r, s.decode('cp932')[:12]) for r, s in a[0]])
    print('layout: %d messages, %d pages compared, %d messages differ' % (len(t.messages), npages, bad))
    return bad


if __name__ == '__main__':
    sys.exit(main())
