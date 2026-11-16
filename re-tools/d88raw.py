#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""D88 -> plain sector image; prints the geometry. Usage: d88raw.py IMAGE.d88 OUT.img"""
import struct, sys

def d88(b):
    size = struct.unpack_from('<I', b, 0x1C)[0]
    assert size == len(b), (size, len(b))
    tracks = struct.unpack_from('<164I', b, 0x20)
    out = bytearray(); geo = {}
    for t, off in enumerate(tracks):
        if not off: continue
        p, secs, count = off, [], None
        while count is None or len(secs) < count:
            c, h, r, n, ns, _d, _e, st, ds = struct.unpack_from('<BBBBHBBB5xH', b, p)
            count = ns
            if st not in (0, 0x10): print('track %d sec %d status %02x' % (t, r, st), file=sys.stderr)
            secs.append((r, b[p+16:p+16+ds])); p += 16 + ds
        geo.setdefault((len(secs), len(secs[0][1])), []).append(t)
        for _r, d in sorted(secs): out += d
    return bytes(out), geo

if __name__ == '__main__':
    raw, geo = d88(open(sys.argv[1], 'rb').read())
    for k, v in geo.items(): print('sectors/track %d size %d: %d tracks (%d..%d)' % (k[0], k[1], len(v), v[0], v[-1]))
    open(sys.argv[2], 'wb').write(raw); print(len(raw))
