#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a vangel game pack (<game>.pak) from the imported original game.

usage: mkpack.py [--game NAME] [--original DIR] [--fonts DIR] -o GAME.pak

DIR is resources/original/ as `gamedata.py import` fills it (and resources/derived/
M_unpacked.EXE, which the import makes). Every file taken is checked against
resources/inventory.tsv (name and md5); the build stops on anything missing or different. The
dumped copy's saves (GAME.DAT) are never packed: a new install starts without saves.

Contents (the pack format is lrvne's, source/lrvne/include/lrvne/pack.h; this engine's types:
tools/vgpak.py):
  SCENARIO "CMD00.SCB", TEXT "CMD00.TXB", LIBRARY "GDATA.LIB"   byte-exact
  SONG     the 21 songs (VA_Mnn.M / .N) under their file names, byte-exact
  FILE     "ANNOUNCE.TXT", byte-exact
  BLOB     (lrvne's) "ssgtab": PMD.COM's SSG-effect table (lrvne pmd), the drums of part K;
           "txbdict": M.EXE's text dictionary (tools/mexe.py); M.EXE's built-in palettes
           "pal.black", "pal.white", "pal.default" (48 bytes R[16] G[16] B[16]: 0AA8:0000,
           0AA8:0060, 0AA8:0030, the one gfx_init sets)
  FONT     "ank8": M.EXE's own half-width font, all 256 codes, as stored (the engine
           emboldens); "font16" (JIS X 0208, 16x16) and "font8" (JIS X 0201, 8x16) stand in
           for the kanji ROM, from lrvne's xfont (--no-bold), given in --fonts as k16.xfnt and
           ank8rom.xfnt
  META     "profile" (tools/games.py), "lang" per language, and "langs" (the pack writer's);
           "viewer": the palette the scenario shows each picture with (tools/gf.py
           gf_palettes, the first of them), for the picture viewer only (--view; the pictures
           have none of their own), and "default", the palette gfx_init sets (0AA8:0030)

Nothing else of the release is packed: the DOS system, the batch files, the drivers (PMD.COM is
modelled by lrvne, the others are for sound boards not reproduced yet), the mouse driver, the
developers' notes, the PCM banks (for the OPNA setups, later) and the engine itself.
"""
import argparse
import collections
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lrvnepath  # noqa: E402,F401
from lrvne import inventory, pmd, profile, xfont, xpak  # noqa: E402
import games     # noqa: E402
import gf        # noqa: E402
import mexe      # noqa: E402
import scb       # noqa: E402
import vgpak     # noqa: E402

KIND_TYPE = {
    'scenario (CRSC)': ('scenario', vgpak.T_SCENARIO),
    'text (CRTX)': ('text', vgpak.T_TEXT),
    'pictures (GA00)': ('library', vgpak.T_LIBRARY),
    'music (PMD .M)': ('song', vgpak.T_SONG),
    'music (PMD .M, alternate)': ('song', vgpak.T_SONG),
}
FILES = {'ANNOUNCE.TXT': vgpak.T_FILE}


def die(msg):
    sys.exit('mkpack: ' + msg)


def read_checked(row, original):
    full = os.path.join(original, row.get('release'), row.name)
    if not os.path.exists(full):
        die('%s is missing: import the game first (make data SRC=...; docs/game-data.md)' % full)
    with open(full, 'rb') as f:
        data = f.read()
    if row.md5 != inventory.ANY and hashlib.md5(data).hexdigest() != row.md5:
        die('%s differs from the inventory (md5)' % full)
    return data


def read_engine(game):
    eng = game['engine']
    if not os.path.exists(eng['unpacked']):
        die('%s is missing: it is made by the import (make data)' % eng['unpacked'])
    with open(eng['unpacked'], 'rb') as f:
        data = f.read()
    if hashlib.md5(data).hexdigest() != eng['unpacked_md5']:
        die('%s differs from the expected image (md5): import the game again' % eng['unpacked'])
    return mexe.Image(data)


def ank8_table(img):
    t = xfont.FontTable(8, 16)
    for code, rows in mexe.ank_font(img).items():
        t.add_glyph(code, rows)
    return t.build()


def rgb_hex(colours):
    """16 (r, g, b) levels 0..15 -> 48 hex digits"""
    return ''.join('%x%x%x' % c for c in colours)


def viewer_palettes(original, release, img):
    """the META "viewer" text: picture name -> its first scenario palette, and the default"""
    d = os.path.join(original, release)
    sc = scb.Scenario(open(os.path.join(d, 'CMD00.SCB'), 'rb').read())
    lines = []
    b = img.at(0x0AA8, 0x0030, 48)                  # R[16] G[16] B[16]
    lines.append('default=' + rgb_hex((b[i], b[16 + i], b[32 + i]) for i in range(16)))
    pals = gf.gf_palettes(os.path.join(d, 'CMD00.SCB'), os.path.join(d, 'GDATA.LIB'))
    for name in sorted(pals):
        if pals[name]:
            lines.append('%s.gf=%s' % (name, rgb_hex(sc.pal[pals[name][0] - 1])))
    return ('\n'.join(lines) + '\n').encode('ascii')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--original', default=games.ORIG)
    ap.add_argument('--fonts', help='directory with k16.xfnt and ank8rom.xfnt (xfont --no-bold)')
    ap.add_argument('--game', default=games.DEFAULT, choices=sorted(games.GAMES))
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args()
    game = games.GAMES[a.game]
    prof = dict(game['profile'])
    pk = xpak.PackWriter(vgpak.TYPES, langs=list(game['languages']))
    counts = collections.Counter()
    pmd_com = None
    for row in inventory.Inventory.load(games.INVENTORY).rows:
        if row.get('release') != game['release']:
            continue
        name = row.basename
        kind = KIND_TYPE.get(row.get('kind'))
        if kind:
            pk.add(name, kind[1], read_checked(row, a.original))
            counts[kind[0]] += 1
        elif name in FILES:
            pk.add(name, FILES[name], read_checked(row, a.original))
            counts['file'] += 1
        elif name == 'PMD.COM':
            pmd_com = read_checked(row, a.original)
    for want, n in game['counts'].items():
        if counts[want] != n:
            die('expected %d %s files, found %d' % (n, want, counts[want]))
    for key in ('scenario', 'library'):
        if not any(n == prof[key].encode('ascii') for n, _t, _l in pk.names()):
            die('the profile\'s %s %s is not in the pack' % (key, prof[key]))
    if pmd_com is None:
        die('PMD.COM is missing from the inventory\'s release')
    try:
        pk.add('ssgtab', xpak.T_BLOB, pmd.ssg_effect_table(pmd_com))
    except ValueError as e:
        die('PMD.COM: %s' % e)
    img = read_engine(game)
    pk.add('txbdict', xpak.T_BLOB, mexe.text_dictionary(img))
    pk.add('ank8', xpak.T_FONT, ank8_table(img))
    for name, data in mexe.palettes(img).items():
        pk.add(name, xpak.T_BLOB, data)
    counts['blob'] += 5
    pk.add('viewer', xpak.T_META, viewer_palettes(a.original, game['release'], img))
    counts['fonts'] += 1
    for lang, lname in game['languages'].items():
        pk.add('lang', xpak.T_META, ('encoding=cp932\nname=%s\n' % lname).encode('utf-8'),
               lang=lang)
    if a.fonts:
        for name, fname in (('font16', 'k16.xfnt'), ('font8', 'ank8rom.xfnt')):
            f = os.path.join(a.fonts, fname)
            if not os.path.exists(f):
                die('%s is missing (lrvne xfont --no-bold)' % f)
            with open(f, 'rb') as fo:
                pk.add(name, xpak.T_FONT, fo.read())
            counts['fonts'] += 1
    pk.add('profile', xpak.T_META, profile.dumps(prof).encode('utf-8'))
    data = pk.build(dedupe=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    with open(a.output, 'wb') as fo:
        fo.write(data)
    print('%s: %d entries, %d bytes (%s)' % (a.output, len(xpak.read_pack(data).entries),
                                           len(data),
                                           ', '.join('%s %d' % kv for kv in sorted(counts.items()))))


if __name__ == '__main__':
    main()
