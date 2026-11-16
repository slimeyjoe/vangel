#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""saves.py - the original's save file GAME.DAT and the engine's saves, stdlib only.

The engine keeps the original's file byte for byte, as the storage record `game.dat` in its
save directory (docs/re/scenario-format.md §7; engine/game/saves.c), so a GAME.DAT from a
PC-98 disk is a save of the engine and back:

    saves.py show FILE [VARS]          the slots: pc, call stack, variables (VARS: the
                                       scenario's variable count, default 20)
    saves.py import FILE DIR           FILE -> DIR/game.dat (DIR: the engine's --storage, or
                                       its default save directory)
    saves.py export DIR FILE           DIR/game.dat -> FILE

import and export check that the file holds records of the original's layout. The original's
off-by-one is kept: a record holds the unused variable slot and v1..v19, not v20.
"""
import os
import shutil
import struct
import sys


def records(data, nvar=20):
    """[(slot, None | (pc, depth, stack, [(type, value)] of entries 0..n-1))]"""
    size = (nvar + 24) * 3
    out = []
    for k in range(3):
        r = data[k * size:(k + 1) * size]
        if len(r) < 6 or r[:2] != b'SD' or struct.unpack('>H', r[2:4])[0] != size:
            out.append((k + 1, None))
            continue
        r = r + b'\xff' * (size - len(r))
        pc, depth = struct.unpack_from('>HH', r, 4)
        stack = list(struct.unpack_from('>32H', r, 8))
        vars_ = [(r[72 + 3 * i], struct.unpack_from('>h', r, 73 + 3 * i)[0])
                 for i in range(nvar)]
        out.append((k + 1, (pc, depth, stack, vars_)))
    return out


def show(path, nvar=20):
    data = open(path, 'rb').read()
    print('%s: %d bytes' % (path, len(data)))
    for k, rec in records(data, nvar):
        if rec is None:
            print('slot %d: empty or not a record' % k)
            continue
        pc, depth, stack, vars_ = rec
        print('slot %d: pc %d, calls %s' % (k, pc, ' '.join(str(x) for x in stack[:depth])))
        print('  ' + ' '.join('v%d=%d%s' % (i, v, 'b' if t == 10 else '')
                              for i, (t, v) in enumerate(vars_) if i))


def check(path):
    data = open(path, 'rb').read()
    if not any(rec for _, rec in records(data)):
        sys.exit('saves.py: %s holds no save record' % path)


def main(a):
    if len(a) >= 3 and a[1] == 'show':
        show(a[2], int(a[3]) if len(a) > 3 else 20)
    elif len(a) == 4 and a[1] == 'import':
        check(a[2])
        os.makedirs(a[3], exist_ok=True)
        shutil.copyfile(a[2], os.path.join(a[3], 'game.dat'))
    elif len(a) == 4 and a[1] == 'export':
        src = os.path.join(a[2], 'game.dat')
        check(src)
        shutil.copyfile(src, a[3])
    else:
        sys.exit(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
