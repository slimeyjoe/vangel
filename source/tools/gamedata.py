#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""The original game data: import it from your copy of the release and check it.

The repository carries none of the game. `import` looks through what you have, keeps the files
whose name and md5 are in resources/inventory.tsv and writes them to
resources/original/<release>/<name> (not committed). Everything else is derived from there by
tools. The work is lrvne's import framework (source/lrvne/tools/README.md); this file adds what
is the game's: its releases and what is derived on import.

usage:
  gamedata.py import [SRC...] [--out DIR]
  gamedata.py check [-q] [--out DIR]
  gamedata.py scan [SRC...]              # print inventory rows for what SRC holds (maintenance)

SRC: any mix of floppy images (D88, raw sector images), archives of them and directories
(searched recursively); CONTAINER::member names one member of an archive. Without SRC the
directories of the LRVNE_MEDIA environment variable are searched. Flux images (SCP, MFI, HFE)
are not read: use the D88s.

Releases in the inventory (column 1; docs/game-data.md):
  pc98   the two 2HD floppies of 1995-03-01 (the game). Required.
  x68k   the X68000 release (one DIM image, Human68k). Optional: research and the typo fix
         only; its files are taken only from a DIM image (the PC-98 copies of the files the two
         share are not the X68000 release). lrvne reads no DIM image yet, so it stays empty.
  ibm    the "Graphic Disk" of 1995-12-13. Optional: the CG gallery.

GAME.DAT holds the saves of the dumped copy: imported as a test input, kind "previous owner's
state", never packed. Its md5 is not checked (the inventory has '-').

After an import, the engine M.EXE is unpacked (EXEPACK, lrvne exepack) to
resources/derived/M_unpacked.EXE and checked by md5: the research tools and the pack read it.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lrvnepath  # noqa: E402,F401
from lrvne import exepack, inventory  # noqa: E402
import games    # noqa: E402

GAME = games.GAMES[os.environ.get('GAME') or games.DEFAULT]


def accept(row, entry):
    """the X68000 release's files only from a DIM image"""
    if row.get('release') == 'x68k':
        return '.dim' in entry.path.lower()
    return True


def scan_row(entry, _data):
    """`scan`: a row per file, the release left for the maintainer to fill in"""
    return {'name': entry.inner_path, 'release': '?', 'disk': '-', 'kind': '?'}


def unpack_engine(dest):
    """resources/derived/M_unpacked.EXE from the imported M.EXE (checked); True if done"""
    eng = GAME['engine']
    src = os.path.join(dest, GAME['release'], eng['name'])
    if not os.path.exists(src):
        return False
    with open(src, 'rb') as f:
        data, _info = exepack.unpack(f.read())
    if hashlib.md5(data).hexdigest() != eng['unpacked_md5']:
        sys.exit('gamedata: the unpacked %s differs from the expected image (md5)' % eng['name'])
    os.makedirs(os.path.dirname(eng['unpacked']), exist_ok=True)
    with open(eng['unpacked'], 'wb') as f:
        f.write(data)
    print('%s: unpacked to %s' % (eng['name'], os.path.relpath(eng['unpacked'], games.ROOT)))
    return True


def main():
    def post_import(_report, dest):
        unpack_engine(dest)

    hooks = inventory.Hooks(
        dest_path=lambda row: row.get('release') + '/' + row.name,
        required=lambda row: row.get('release') not in GAME['optional'],
        group=lambda row: row.get('release'),
        accept=accept, scan_row=scan_row, post_import=post_import)
    return inventory.run_cli(None, games.INVENTORY, games.ORIG, hooks=hooks, prog='gamedata',
                             description=__doc__.split('\n')[0],
                             scan_columns=('release', 'disk', 'name', 'size', 'mtime', 'md5',
                                           'kind'))


if __name__ == '__main__':
    sys.exit(main())
