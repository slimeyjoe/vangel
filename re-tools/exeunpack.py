#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""exeunpack.py - undo Microsoft EXEPACK on an MZ executable (M.EXE).

Usage:  python3 -I re-tools/exeunpack.py IN.EXE OUT.EXE

EXEPACK replaces the load image with a compressed one and puts a small unpacker at the entry
point. The unpacker segment (initial CS) starts with a header:

    +00 real IP   +02 real CS   +04 (work)   +06 unpacker size   +08 real SP   +0A real SS
    +0C unpacked size in paragraphs   [+0E skip length]   "RB"

The compressed data is read backwards from the end of the packed image: each record ends in a
command byte, B0/B1 = fill (count word, then one value byte before it), B2/B3 = copy (count
word, then the bytes before it); the odd command is the last. The relocations follow the
unpacker's error message "Packed file is corrupt" as 16 groups (segment 0000h, 1000h, ...),
each a count word and that many offset words. The output is a plain MZ file with the same
image and an ordinary relocation table. Stdlib only; the input is only read.
"""
import struct
import sys


def _w(d, o):
    return struct.unpack_from('<H', d, o)[0]


def unpack(d):
    """Return (plain MZ bytes, info dict) for an EXEPACK-compressed MZ image."""
    if d[:2] not in (b'MZ', b'ZM'):
        raise ValueError('not an MZ executable')
    hdr_end = _w(d, 8) * 16
    stub = hdr_end + _w(d, 0x16) * 16
    ip, cs, _work, stub_size, sp, ss, paras = struct.unpack_from('<7H', d, stub)
    sig = stub + 14
    skip = 1
    if d[sig:sig + 2] != b'RB':
        skip = _w(d, sig)
        sig += 2
    if d[sig:sig + 2] != b'RB':
        raise ValueError('no EXEPACK header at the entry segment')

    packed = d[hdr_end:stub]
    out = bytearray(paras * 16)
    out[:len(packed)] = packed
    src = len(packed) - (skip - 1) * 16
    dst = len(out)
    while out[src - 1] == 0xFF:                 # padding before the last record
        src -= 1
    while True:
        cmd = out[src - 1]
        count = _w(out, src - 3)
        src -= 3
        op = cmd & 0xFE
        if op == 0xB0:
            src -= 1
            dst -= count
            out[dst:dst + count] = bytes([out[src]]) * count
        elif op == 0xB2:
            src -= count
            dst -= count
            out[dst:dst + count] = out[src:src + count]
        else:
            raise ValueError('unknown EXEPACK command %02Xh' % cmd)
        if cmd & 1:
            break

    msg = d.find(b'Packed file is corrupt', stub, stub + stub_size)
    if msg < 0:
        raise ValueError('EXEPACK relocation table not found')
    p = msg + len(b'Packed file is corrupt')
    relocs = []
    for group in range(16):
        n = _w(d, p)
        p += 2
        for _ in range(n):
            relocs.append((_w(d, p), group << 12))
            p += 2
    if p != stub + stub_size:
        raise ValueError('relocation table ends at %Xh, the unpacker at %Xh'
                         % (p, stub + stub_size))

    head = (0x1C + 4 * len(relocs) + 0x1FF) & ~0x1FF
    total = head + len(out)
    mz = bytearray(head)
    struct.pack_into('<2s13H', mz, 0, b'MZ', total & 0x1FF, (total + 0x1FF) // 0x200,
                     len(relocs), head // 16, _w(d, 0x0A), _w(d, 0x0C), ss, sp, 0, ip, cs,
                     0x1C, 0)
    for i, (off, seg) in enumerate(relocs):
        struct.pack_into('<HH', mz, 0x1C + 4 * i, off, seg)
    info = {'image': len(out), 'relocs': len(relocs), 'cs:ip': '%04X:%04X' % (cs, ip),
            'ss:sp': '%04X:%04X' % (ss, sp)}
    return bytes(mz) + bytes(out), info


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    with open(argv[1], 'rb') as f:
        data, info = unpack(f.read())
    with open(argv[2], 'wb') as f:
        f.write(data)
    print('EXEPACK: ' + ', '.join('%s %s' % kv for kv in info.items()))


if __name__ == '__main__':
    main(sys.argv)
