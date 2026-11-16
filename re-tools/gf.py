#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""gf.py - Virgin Angel GDATA.LIB ("GA00") archive and ".gf" ("GF0") picture decoder, stdlib only.

Specification: docs/re/graphics.md.  Verified bit-exact against M.EXE's decoder (015A:000A and
its three siblings) by re-tools/gf_verify.py.

Archive (0855:000C, 0823:012A):
  0   "GA00"
  4   u32 0
  8   u32 count            (the engine reads the low word)
  12  u32 data base        (the engine ignores it and uses (count + 2) * 16, the same value)
  16  (count + 1) x 16-byte entries: name[8] (NUL padded), ext[3] + 1 pad byte, u32 offset
      (relative to the data base); the extra last entry has name FF..FF and offset = data size
Picture (00DD:0403): "GF0\\0", u16 width, height, x, y, then the compressed stream (a Pi-style
  coder, see decode()).  No palette.

Usage:
  gf.py list [GDATA.LIB]
  gf.py extract [GDATA.LIB] OUTDIR            raw .gf members
  gf.py png [GDATA.LIB] OUTDIR [--scb CMD00.SCB]   PNGs; with --scb the scenario palettes chosen
                                                  by gf_palettes() (else a grey ramp)
  gf.py usage [GDATA.LIB] [--scb CMD00.SCB]  every picture's op 31 uses and palettes
As a module: Archive(data), decode(data, offset) -> Picture(w, h, x, y, pixels: bytes w*h of 0..15)
"""
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'resources/original/pc98/GDATA.LIB')
TRANSPARENT = 8          # colour skipped by op 31 with flag 1 (015A:09D6 cmp al,80h)
# pictures always drawn opaque (op 31 flag 0), where colour 8 is a real colour
OPAQUE8 = {'va_%02d' % i for i in range(1, 23)} | {'va_12e', 'va_title', 'logo', 'va_opbac',
                                                  'va_st01', 'va_st02', 'va_st03', 'va_st04'}


class Archive:
    def __init__(self, data):
        if data[:4] != b'GA00':
            raise ValueError('not a GA00 archive')
        self.data = data
        n = struct.unpack_from('<H', data, 8)[0]
        self.base = (n + 2) * 16
        self.entries = []          # (name 'va_main.gf', absolute offset, size)
        offs = []
        for i in range(n + 1):
            e = data[16 + 16 * i:32 + 16 * i]
            offs.append(struct.unpack_from('<I', e, 12)[0])
            if i < n:
                name = e[:8].split(b'\0')[0].decode('ascii')
                ext = e[8:11].split(b'\0')[0].decode('ascii')
                self.entries.append([name + ('.' + ext if ext else ''), self.base + offs[-1]])
        if data[16 + 16 * n] != 0xFF:
            raise ValueError('last entry is not FF')
        for i, e in enumerate(self.entries):
            e.append(offs[i + 1] - offs[i])
        self.entries = [tuple(e) for e in self.entries]

    def find(self, name):
        """Case-sensitive, as 0823:012A (repe cmpsb)."""
        for e in self.entries:
            if e[0] == name:
                return e
        return None

    def member(self, name):
        e = self.find(name)
        return self.data[e[1]:e[1] + e[2]]


class Picture:
    def __init__(self, w, h, x, y, pixels, overrun=0):
        self.w, self.h, self.x, self.y, self.pixels = w, h, x, y, pixels
        self.overrun = overrun     # bytes read past the end of the input (0 for all game files)

    def rows(self):
        return [self.pixels[r * self.w:(r + 1) * self.w] for r in range(self.h)]


def header(data, off=0):
    if data[off:off + 4] != b'GF0\0':
        raise ValueError('not a GF0 picture')
    return struct.unpack_from('<4H', data, off + 4)


def decode(data, off=0, end=None):
    """Decode the GF picture at data[off:].  Returns a Picture with one byte per pixel (0..15,
    PC-98 colour number b + 2r + 4g + 8i).  `end` limits the input (default: len(data)); the
    original keeps reading the archive past the member, so pass the whole archive."""
    w, h, x, y = header(data, off)
    pos = off + 12
    end = len(data) if end is None else end
    st = {'pos': pos, 'byte': 0, 'left': 0, 'over': 0}

    def bit():
        if st['left'] == 0:
            if st['pos'] < end:
                st['byte'] = data[st['pos']]
            else:
                st['byte'] = 0
                st['over'] += 1
            st['pos'] += 1
            st['left'] = 8
        st['left'] -= 1
        b = (st['byte'] >> 7) & 1
        st['byte'] = (st['byte'] << 1) & 0xFF
        return b

    # move-to-front colour table, one row per preceding colour (015A:043D): row r = r, r-1, ...
    table = [[(r - k) & 15 for k in range(16)] for r in range(16)]

    def colour(prev):
        """015A:0315: one colour in the context of the colour to its left."""
        row = table[prev]
        if bit():
            idx = bit()                                  # 1x: index 0 or 1
        elif not bit():
            idx = 2 + bit()                              # 00x: 2..3
        elif not bit():
            idx = 4 + (bit() << 1 | bit())               # 010xx: 4..7
        else:
            idx = 8 + (bit() << 2 | bit() << 1 | bit())  # 011xxx: 8..15
        c = row[idx]
        del row[idx]
        row.insert(0, c)                                 # move to front
        return c

    total = 2 * w + w * h
    buf = bytearray(total + 4 * w + 4)
    # first colour pair (context colour 0), repeated over the two lines above the picture
    c0 = colour(0)
    c1 = colour(c0)
    for i in range(0, 2 * w, 2):
        buf[i], buf[i + 1] = c0, c1
    p = 2 * w
    # position codes: 00 -> left (see below), 01 -> 1 line up, 10 -> 2 lines up,
    # 110 -> 1 up 1 right, 111 -> 1 up 1 left; ids as the original's SI values
    ids = {1: -w, 2: -2 * w, 3: -w + 1, 4: -w - 1}
    prev_pos = 0
    while p < total:
        if bit():
            if not bit():
                pos = 2
            else:
                pos = 4 if bit() else 3
            pid = ids[pos]
            src_off = pid
        else:
            if bit():
                pid = src_off = -w
            else:
                pid = -4
                # 2 pixels left if those two are the same colour, else 4 pixels left
                src_off = -2 if buf[p - 2] == buf[p - 1] else -4
        if pid == prev_pos:
            # same position twice: literal colour pairs
            prev_pos = pid
            while True:
                a = colour(buf[p - 1])
                b = colour(a)
                buf[p], buf[p + 1] = a, b
                p += 2
                if p >= total or not bit():
                    break
            prev_pos = 0
            continue
        prev_pos = pid
        # length in 2-pixel units: 0 -> 1, 1^n 0 b(n) -> (1 << n) | b
        if not bit():
            n = 1
        else:
            k = 1
            while bit():
                k += 1
            n = 1
            for _ in range(k):
                n = n << 1 | bit()
        cnt = min(2 * n, total - p)
        s = p + src_off
        for i in range(cnt):
            buf[p + i] = buf[s + i]
        p += 2 * n if cnt == 2 * n else cnt
    return Picture(w, h, x, y, bytes(buf[2 * w:total]), st['over'])


def to_planes(pic, planes=None, x=None, y=None, transparent=False):
    """Draw a Picture into four 32000-byte planes (B, R, G, I; 80 bytes per line) as the
    engine's flush routines do (015A:0471 opaque, 015A:09BB with colour 8 transparent).
    x is rounded down to a multiple of 8 (x >> 3); lines past 400 are not clipped by the
    original (they wrap into the next plane's memory) and are dropped here."""
    if planes is None:
        planes = [bytearray(32000) for _ in range(4)]
    x = pic.x if x is None else x
    y = pic.y if y is None else y
    bx = x >> 3
    for r in range(pic.h):
        line = pic.pixels[r * pic.w:(r + 1) * pic.w]
        o0 = (y + r) * 80 + bx
        for c in range(pic.w // 8):
            o = o0 + c
            if o >= 32000:
                continue
            v = [0, 0, 0, 0]
            m = 0
            for k in range(8):
                px = line[c * 8 + k]
                bitv = 0x80 >> k
                if transparent and px == TRANSPARENT:
                    m |= bitv
                    continue
                for q in range(4):
                    if px >> q & 1:
                        v[q] |= bitv
            for q in range(4):
                planes[q][o] = (planes[q][o] & m) | v[q] if transparent else v[q]
    return planes


# ---- PNG (stdlib)
def png(path, w, h, pixels, palette):
    """8-bit indexed PNG; palette = 16 (r, g, b) 4-bit levels."""
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b''.join(b'\0' + bytes(pixels[r * w:(r + 1) * w]) for r in range(h))
    plte = b''.join(bytes((r * 17, g * 17, b * 17)) for r, g, b in palette)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 3, 0, 0, 0)))
        f.write(chunk(b'PLTE', plte))
        f.write(chunk(b'IDAT', zlib.compress(raw, 9)))
        f.write(chunk(b'IEND', b''))


GREY = [(i, i, i) for i in range(16)]


def gf_palettes(scb_path, lib_path=LIB):
    """picture name -> list of 1-based scenario palette numbers (op 30 operand) it is on
    screen with (gf_usage), most frequent first.  va_12e (the window-less bottom strip of
    va_12, pasted over it at statement 1911, reached by a jump) gets va_12's palettes."""
    seen = gf_usage(scb_path, lib_path)[1]
    out = {k: [p for p, n in sorted(v.items(), key=lambda t: (-t[1], t[0]))]
           for k, v in seen.items()}
    if 'va_12e' not in out and 'va_12' in out:
        out['va_12e'] = out['va_12']
    return out


def gf_usage(scb_path, lib_path=LIB):
    """Walk the statements in file order (control flow ignored) tracking which pictures cover
    which rectangles of buffers 10/11/12 (op 31 adds a layer, an opaque layer hides what it
    covers; op 32 copies the layers inside its source rectangle; op 33 clears) and the palette
    state (op 30 sets palette P, op 1A makes the screen black/white until the next op 30).
    Statement numbers are 1-based (the VM's numbering; scb.py --dump index + 1).
    Returns (list of op 31 uses, {name: {P: count}} for the palettes P seen while the picture
    is in buffer 10 and the screen is not faded out).  A heuristic: it is exact only for straight-line code."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import scb
    sc = scb.Scenario(open(scb_path, 'rb').read())
    data = open(lib_path, 'rb').read()
    ar = Archive(data)
    dims = {e[0].rsplit('.', 1)[0]: header(data, e[1]) for e in ar.entries}
    bufs = {10: [], 11: [], 12: []}            # layers: [name, x0, y0, x1, y1, opaque]
    pal, dark = None, True
    seen = {}
    uses = []

    def inside(l, r):
        return l[1] >= r[0] and l[2] >= r[1] and l[3] <= r[2] and l[4] <= r[3]

    def add(b, layer):
        if layer[5]:
            bufs[b] = [l for l in bufs[b] if not inside(l, layer[1:5])]
        bufs[b].append(layer)

    def note():
        if pal and not dark:
            for l in bufs[10]:
                d = seen.setdefault(l[0], {})
                d[pal] = d.get(pal, 0) + 1
    for i, (at, op, a) in enumerate(sc.stmts):
        if op == 0x31:
            b, x, y, flag, name = a
            w, h, hx, hy = dims.get(name, (0, 0, 0, 0))
            x = hx if x == -1 else x
            y = hy if y == -1 else y
            uses.append({'stmt': i + 1, 'name': name, 'buf': b, 'x': x, 'y': y, 'flag': flag})
            if b in bufs:
                add(b, [name, x & ~7, y, (x & ~7) + w, y + h, flag == 0])
                if b == 10:
                    note()
        elif op == 0x32:
            sb, sx, sy, w, h, db, dx, dy, fx = a
            if sb in bufs and db in bufs:
                r = (sx, sy, sx + w, sy + h)
                new = []
                for l in bufs[sb]:
                    x0, y0 = max(l[1], r[0]), max(l[2], r[1])
                    x1, y1 = min(l[3], r[2]), min(l[4], r[3])
                    if x0 < x1 and y0 < y1:
                        new.append([l[0], x0 - sx + dx, y0 - sy + dy, x1 - sx + dx,
                                    y1 - sy + dy, l[5] or (x0, y0, x1, y1) == r])
                # the copy replaces the destination rectangle
                dr = (dx, dy, dx + w, dy + h)
                bufs[db] = [l for l in bufs[db] if not inside(l, dr)]
                bufs[db] += new
                if db == 10:
                    note()
        elif op == 0x33:
            bufs[a[0] if a[0] in bufs else 10] = []
        elif op == 0x30:
            pal, dark = a[1], False
            note()
        elif op == 0x1A:
            dark = True
    return uses, seen


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd = argv[1]
    rest = [a for a in argv[2:] if not a.startswith('--')]
    scbp = None
    if '--scb' in argv:
        scbp = argv[argv.index('--scb') + 1]
        rest = [a for a in rest if a != scbp]
    lib = rest[0] if rest and rest[0].lower().endswith('.lib') else LIB
    if rest and rest[0] == lib:
        rest = rest[1:]
    data = open(lib, 'rb').read()
    ar = Archive(data)
    if cmd == 'list':
        print('%d members, data base %#x' % (len(ar.entries), ar.base))
        for name, off, size in ar.entries:
            w, h, x, y = header(data, off)
            print('%-12s %#8x %7d  %3dx%-3d at (%3d,%3d)' % (name, off, size, w, h, x, y))
    elif cmd == 'extract':
        os.makedirs(rest[0], exist_ok=True)
        for name, off, size in ar.entries:
            open(os.path.join(rest[0], name), 'wb').write(data[off:off + size])
    elif cmd == 'png':
        out = rest[0]
        os.makedirs(out, exist_ok=True)
        pals = {}
        scpal = None
        if scbp:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import scb
            scpal = scb.Scenario(open(scbp, 'rb').read()).pal
            pals = gf_palettes(scbp, lib)
        for name, off, size in ar.entries:
            pic = decode(data, off)
            base = name.rsplit('.', 1)[0]
            used = pals.get(base, [])
            if not used:
                png(os.path.join(out, base + '.png'), pic.w, pic.h, pic.pixels, GREY)
                print('%-12s grey (no palette found)' % name)
                continue
            cols = sorted(set(pic.pixels) - ({TRANSPARENT} if base not in OPAQUE8 else set()))
            done, kept = set(), []
            for k, pn in enumerate(used):
                key = tuple(scpal[pn - 1][c] for c in cols)
                if key in done:
                    continue           # renders identically to a palette already written
                done.add(key)
                kept.append(pn)
                fn = base + ('.png' if k == 0 else '_p%02d.png' % pn)
                png(os.path.join(out, fn), pic.w, pic.h, pic.pixels, scpal[pn - 1])
            print('%-12s palettes %s, written %s' % (name, used, kept))
    elif cmd == 'usage':
        scbp = scbp or os.path.join(ROOT, 'resources/original/pc98/CMD00.SCB')
        uses, seen = gf_usage(scbp, lib)
        for name, off, size in ar.entries:
            base = name.rsplit('.', 1)[0]
            w, h, x, y = header(data, off)
            us = [u for u in uses if u['name'] == base]
            combos = sorted(set((u['buf'], u['x'], u['y'], u['flag']) for u in us))
            print('%-9s %3dx%-3d (%3d,%3d) %3d uses  pal %-14s %s  stmts %s' % (
                base, w, h, x, y, len(us),
                ','.join('%d' % p for p, n in sorted(seen.get(base, {}).items(),
                                                     key=lambda t: (-t[1], t[0]))) or '-',
                ' '.join('b%d(%d,%d)f%d' % c for c in combos),
                ','.join(str(u['stmt']) for u in us[:8]) + (',...' if len(us) > 8 else '')))
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv)
