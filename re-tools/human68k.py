#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Human68k (X68000) 2HD floppy: list/extract files.  Usage: human68k.py IMG [OUTDIR]
Geometry from the Hudson boot sector (big-endian BPB at 0x12): 1024-byte sectors, 1 sector per
cluster, 2 FATs, 1 reserved sector, 0xC0 root entries, 1232 sectors, 2 sectors per FAT.
FAT12 packing and directory entries as MS-DOS (little endian); names: 8+3 and 10 more name bytes
at +0x0C (Human68k long names)."""
import os, struct, sys

def main():
    img = open(sys.argv[1], 'rb').read()
    bps, spc, nfat, res, nroot, tot, media, spf = struct.unpack_from('>HBBHHHBB', img, 0x12)
    print('bps %d spc %d nfat %d res %d root %d total %d media %02x spf %d' % (bps, spc, nfat, res, nroot, tot, media, spf))
    fat = img[res*bps:(res+spf)*bps]
    root = (res + nfat*spf) * bps
    data = root + nroot*32
    def chain(c):
        while 2 <= c < 0xFF0:
            yield c
            o = c*3//2; v = fat[o] | fat[o+1] << 8
            c = (v >> 4) if c & 1 else (v & 0xFFF)
    def walk(off, n, path):
        for i in range(n):
            e = img[off+i*32:off+i*32+32]
            if e[0] in (0, 0xE5): continue
            name = (e[0:8] + e[12:22]).rstrip(b'\0 ').decode('cp932', 'replace')
            ext = e[8:11].rstrip(b' ').decode('cp932', 'replace')
            attr = e[11]; clus, size = struct.unpack_from('<HI', e, 26)
            full = path + name + ('.' + ext if ext else '')
            if attr & 0x08: continue
            if attr & 0x10:
                if name in ('.', '..'): continue
                print('%-30s <DIR>' % full)
                buf = b''.join(img[data+(c-2)*bps*spc:data+(c-1)*bps*spc] for c in chain(clus))
                sub(buf, full + '/')
                continue
            buf = b''.join(img[data+(c-2)*bps*spc:data+(c-1)*bps*spc] for c in chain(clus))[:size]
            t, d = struct.unpack_from('<HH', e, 22)
            print('%-30s %8d  %04d-%02d-%02d attr %02x' % (full, size, 1980+(d>>9), (d>>5)&15, d&31, attr))
            if len(sys.argv) > 2:
                p = os.path.join(sys.argv[2], full); os.makedirs(os.path.dirname(p), exist_ok=True)
                open(p, 'wb').write(buf)
    def sub(buf, path):
        nonlocal img
        saved = img; img = buf; walk(0, len(buf)//32, path); img = saved
    walk(root, nroot, '')

main()
