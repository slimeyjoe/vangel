#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Translation files for vangel (docs/translation.md): the keys, a pseudo-translation, the
translator's check.

  tl.py template PAK OUT.tsv            every string of the game: key, kind, speaker, rows,
                                        columns and the Japanese (derived game data: keep it in
                                        build/ or resources/derived/, never in the repository)
  tl.py skeleton PAK OUT.tsv            every key with an empty `text`: a translation's start
  tl.py pseudo PAK OUT.tsv [--seed N]   a pseudo-translation (the engine's test): every string,
                                        about one in ten left untranslated
  tl.py check FILE --pak PAK [-v]       keys, escapes, characters (a glyph for each), and the
                                        layout: passages and pages that need more pages than the
                                        original, menu choices and lines that are cut; -v lists
                                        them
  tl.py layout FILE --pak PAK [KEY...]  where the engine draws each string (or those given)
  tl.py view FILE --pak PAK OUT.tsv     the file with `speaker` and `ja` written back from the
                                        game, for reading and searching (derived game data)
  tl.py put FILE BATCH.tsv [--force]    merge a batch (columns key, text) into FILE: only the
                                        `text` cells change; an entry translated differently is
                                        refused without --force
  tl.py fill FILE --pak PAK [-n]        give every untranslated string the translation of one
                                        with the same Japanese and kind; -n only reports
  tl.py status FILE --pak PAK           progress per kind: strings, translated, left
  tl.py read PAK OUTDIR [--tl FILE]     a reading copy (derived game data): the messages in
                                        order, a passage a block with its key, speaker, the
                                        Japanese and the translation

PAK is a pack made by `make pack` (the game's text is taken from it; the Latin glyphs, latin8,
and the kanji ROM's stand-in, font16, too).
"""
import argparse
import os
import random
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lrvnepath  # noqa: E402,F401

import txb as txbmod  # noqa: E402
import vgfont  # noqa: E402
import vglayout  # noqa: E402
import vgpak  # noqa: E402
import vgtext  # noqa: E402

ja = vgtext.ja_text


class Game:
    """the game's strings and fonts from a pack"""

    def __init__(self, pak_path):
        self.pack = vgpak.read(pak_path)
        self.get = vgtext.pack_getter(self.pack)
        self.strings = vgtext.game_strings(self.get)
        e = self.pack.find('latin8')
        if e is None:
            sys.exit('tl: %s has no latin8 (make pack)' % pak_path)
        self.narrow = set(vgfont.read_table(e.data))
        e = self.pack.find('font16')
        self.font16 = vgfont.read_table(e.data) if e is not None else {}
        self.cols = vglayout.cols_of(self.narrow)
        d = self.get('txbdict')
        self.dic = [d[2 * i:2 * i + 2] for i in range(len(d) // 2)]
        self.txb = txbmod.Txb(self.get('CMD00.TXB'), self.dic)

    def speaker(self, s):
        if s.kind != 'text' or not s.info['speech']:
            return ''
        for k, v in self.strings.items():
            if v.kind == 'name' and v.ja == s.info['name']:
                return k
        return ''


def cols_sjis(b):
    n = p = 0
    while p < len(b):
        k = 2 if txbmod.is_lead(b[p]) and p + 1 < len(b) else 1
        n += k
        p += k
    return n


def widest(b):
    return max((cols_sjis(x) for x in b.split(b'\n')), default=0)


# ---- template, skeleton, view ----------------------------------------------------------------

def cmd_template(a):
    g = Game(a.pak)
    rows = []
    for k, s in g.strings.items():
        rows.append(dict(key=k, kind=s.kind, speaker=g.speaker(s),
                         rows=s.ja.count(b'\n') + 1, columns=widest(s.ja),
                         ja=vgtext.escape(ja(s.ja)), text=''))
    vgtext.write_tsv(a.out, ['key', 'kind', 'speaker', 'rows', 'columns', 'ja', 'text'], rows)
    print('%s: %d strings' % (a.out, len(rows)))


def cmd_skeleton(a):
    g = Game(a.pak)
    vgtext.write_tsv(a.out, ['key', 'kind', 'text'],
                     [dict(key=k, kind=s.kind) for k, s in g.strings.items()])
    print('%s: %d keys' % (a.out, len(g.strings)))


def cmd_view(a):
    g = Game(a.pak)
    head, rows, problems = vgtext.read_tsv(a.file)
    if problems:
        sys.exit('\n'.join(problems))
    out = []
    for r in rows:
        s = g.strings.get(r['key'])
        r = dict(r)
        r['speaker'] = g.speaker(s) if s else ''
        r['ja'] = vgtext.escape(ja(s.ja)) if s else ''
        out.append(r)
    head = [h for h in head if h not in ('speaker', 'ja')]
    head = head[:-1] + ['speaker', 'ja'] + head[-1:] if head[-1:] == ['text'] else \
        head + ['speaker', 'ja']
    vgtext.write_tsv(a.out, head, out)
    print('%s: %d rows' % (a.out, len(out)))


# ---- the pseudo-translation -------------------------------------------------------------------

LETTERS = 'abcdefghijklmnoprstuwyzABCDEGHKLMNOPRSTWZąćęłńóśźżĄĆĘŁŃÓŚŹŻ'
PUNCT = ',.!?;:–—…„”’'
WIDE = '漢字★「」'


def pseudo_word(r, n):
    w = ''.join(r.choice(LETTERS) for _ in range(n))
    x = r.random()
    if x < 0.04:
        w = r.choice(WIDE) + w
    elif x < 0.12:
        w += r.choice(PUNCT)
    return w


def pseudo_text(r, cols, lines_ok=True, pages_ok=True):
    """words up to about `cols` columns, line breaks and a page break now and then"""
    out, w = [], 0
    while w < cols:
        if r.random() < 0.02:
            word = pseudo_word(r, r.randint(70, 90))       # wider than any line
        else:
            word = pseudo_word(r, r.randint(1, 9))
        out.append(word)
        w += len(word) + 1
        x = r.random()
        if lines_ok and x < 0.05:
            out.append('\n')
        elif pages_ok and x < 0.06:
            out.append('\f')
    s = ' '.join(out).replace(' \n ', '\n').replace(' \f ', '\f').strip(' ')
    return s or 'x'


def pseudo(s, r):
    k = s.kind
    base = max(widest(s.ja), 4) * max(1, s.ja.count(b'\n') + 1)
    f = r.uniform(0.5, 3.0)
    if k == 'name':
        return pseudo_word(r, r.choice((3, 5, 8, 14)))
    if k == 'fmt':
        return ': „' if s.ja == vgtext.QUOTE_OPEN else '”'
    if k == 'menu':
        return pseudo_text(r, int(cols_sjis(s.ja) * f), False, False)
    if k == 'con':
        return pseudo_text(r, int(cols_sjis(s.ja) * f), False, False)
    if k == 'text':
        return pseudo_text(r, int(base * f))
    if k == 'announce':
        lines = []
        for ln in s.ja.split(b'\n'):
            n = int(cols_sjis(ln) * f)
            lines.append(('  ' if r.random() < 0.3 else '') + (pseudo_text(r, n, False, False)
                                                               if n else ''))
        return '\n'.join(lines)
    # the built-ins
    if s.ja.count(b'\n'):
        lines = []
        for ln in s.ja.split(b'\n'):
            n = int(cols_sjis(ln.strip()) * f)
            lead = ' ' * r.choice((0, 0, 4, 9))     # kept on the staff roll's pages
            lines.append(lead + pseudo_text(r, n, False, False) if n else '')
        if r.random() < 0.3:
            lines.insert(r.randint(0, len(lines)), pseudo_text(r, 30, False, False))
        return '\n'.join(lines)
    return pseudo_text(r, int(cols_sjis(s.ja.strip()) * f), False, False)


def cmd_pseudo(a):
    """every string, but about one in ten left untranslated (the original is shown there,
    next to translated text, with the original's names)"""
    g = Game(a.pak)
    r = random.Random(a.seed)
    rows = []
    for k, s in g.strings.items():
        t = pseudo(s, r)
        if s.kind != 'fmt' and r.random() < 0.1:
            t = ''
        rows.append(dict(key=k, kind=s.kind, text=vgtext.escape(t)))
    vgtext.write_tsv(a.out, ['key', 'kind', 'text'], rows)
    print('%s: %d strings, %d translated (seed %d)' % (a.out, len(rows),
                                                      sum(1 for x in rows if x['text']), a.seed))


# ---- check and layout ---------------------------------------------------------------------------

def table_of(g, tl):
    return vgtext.pack_entries(g.strings, tl)


def layouts(g, tab, keys=None):
    """{key: (description lines, problems)} of the translated strings"""
    out = OrderedDict()
    cols = g.cols
    want = set(keys) if keys else None

    def put(k, lines, problems=()):
        if want is None or k in want:
            out[k] = (lines, list(problems))

    for m in g.txb.messages:
        lines = vgtext.message_lines(m, g.dic)
        mine = [k for k in tab if k.startswith('m%03d.' % m.index)]
        if not mine:
            continue
        tp = vglayout.msg_pages(lines, m.index, tab, cols)
        op = vglayout.msg_pages(lines, m.index, {}, cols)
        desc = []
        for pg, (rows, mode, nb) in enumerate(tp):
            desc.append('page %d %s %d cells' % (pg, 'timed' if mode else 'key', nb))
            for row, col, b, u in rows:
                desc.append('  %d:%02d %s' % (row, col, b.decode('utf-8') if u else ja(b)))
        probs = []
        if len(tp) > len(op):
            probs.append('%d pages, the original %d' % (len(tp), len(op)))
        for rows, _mode, _nb in tp:
            for row, col, b, u in rows:
                if u and col + vglayout.width(b, cols) > (vgtext.WIN_LAST if row == 3 else
                                                          vgtext.WIN_W):
                    probs.append('row %d is %d columns wide' % (row, col + vglayout.width(
                        b, cols)))
        put('message %03d' % m.index, desc, probs)
    for k, s in g.strings.items():
        t = tab.get(k)
        if t is None or s.kind in ('text', 'name', 'fmt'):
            continue
        probs, desc = [], []
        if s.kind == 'menu':
            col, b, c = vglayout.menu_item(s.ja, t, cols)
            desc.append('col %d: %s' % (col, b.decode('utf-8')))
            if b != t:
                probs.append('cut at %d columns' % vgtext.MENU_W)
        elif k.startswith('bi.prologue.'):
            ls = vglayout.prologue(t, cols)
            desc += ['page %d row %d x %d: %s' % (p, r, x, b.decode('utf-8'))
                     for p, r, x, b in ls]
            if vglayout.pages_of(ls) > 1:
                probs.append('%d pages, the original 1' % vglayout.pages_of(ls))
        elif k.startswith('bi.staff.'):
            ls = vglayout.staff(t, cols)
            desc += ['page %d row %d col %d: %s' % (p, r, c, b.decode('utf-8'))
                     for p, r, c, b in ls]
            if vglayout.pages_of(ls) > 1:
                probs.append('%d pages, the original 1' % vglayout.pages_of(ls))
        elif s.kind == 'announce':
            ls = vglayout.announce(t, cols)
            desc += ['page %d row %d col %d: %s' % (p, r, c, b.decode('utf-8'))
                     for p, r, c, b in ls]
            if vglayout.pages_of(ls) > 1:
                probs.append('%d pages, the original 1' % vglayout.pages_of(ls))
        elif k.startswith('bi.') or s.kind == 'con':
            col = {'bi.music.heading': 21, 'bi.music.help': 3}.get(k, 20 if k.startswith(
                'bi.music.') else 0)
            if k == 'bi.music.heading':
                col = vglayout.bi_centre(21, s.ja, t, cols)
            w = vglayout.width(t, cols)
            desc.append('col %d: %s' % (col, t.decode('utf-8')))
            if col + w > 80:
                probs.append('cut at column 80 (%d wide from %d)' % (w, col))
        put(k, desc, probs)
    return out


def missing_glyphs(g, tab):
    chars = ''.join(b.decode('utf-8') for b in tab.values())
    try:
        vgfont.wide16(chars, g.font16, g.narrow)
    except vgfont.FontError as e:
        return str(e)
    return None


def cmd_check(a):
    g = Game(a.pak)
    tl, problems = vgtext.load(a.file, g.strings)
    tab = table_of(g, tl)
    miss = missing_glyphs(g, tab)
    if miss:
        problems.append(miss)
    lay = layouts(g, tab)
    if a.v:
        for k, (_desc, probs) in lay.items():
            for p in probs:
                print('%s: %s' % (k, p))
    kinds = Counter(g.strings[k].kind for k in tl)
    print('%s: %d of %d strings translated (%s)' % (
        a.file, len(tl), len(g.strings), ', '.join('%s %d' % kv for kv in sorted(kinds.items()))))
    print('layout: %d strings or messages need attention (-v lists them)' %
          sum(1 for _d, p in lay.values() if p))
    for p in problems:
        print('ERROR ' + p)
    return 1 if problems else 0


def cmd_layout(a):
    g = Game(a.pak)
    tl, problems = vgtext.load(a.file, g.strings)
    if problems:
        sys.exit('\n'.join(problems))
    for k, (desc, probs) in layouts(g, table_of(g, tl), a.keys or None).items():
        print(k + (' (%s)' % '; '.join(probs) if probs else ''))
        for d in desc:
            print('  ' + d)


# ---- put, fill, status, read --------------------------------------------------------------------

def cmd_put(a):
    head, rows, problems = vgtext.read_tsv(a.file)
    _bh, batch, bp = vgtext.read_tsv(a.batch)
    if problems or bp:
        sys.exit('\n'.join(problems + bp))
    by = {r['key']: r for r in rows}
    changed = refused = 0
    for b in batch:
        r = by.get(b['key'])
        if r is None:
            print('not in %s: %s' % (a.file, b['key']))
            refused += 1
            continue
        if r['text'] and r['text'] != b['text'] and not a.force:
            print('translated differently: %s (--force replaces it)' % b['key'])
            refused += 1
            continue
        if r['text'] != b['text']:
            r['text'] = b['text']
            changed += 1
    vgtext.write_tsv(a.file, head, rows)
    print('%s: %d changed, %d refused' % (a.file, changed, refused))
    return 1 if refused else 0


def cmd_fill(a):
    g = Game(a.pak)
    head, rows, problems = vgtext.read_tsv(a.file)
    if problems:
        sys.exit('\n'.join(problems))
    known = {}
    for r in rows:
        s = g.strings.get(r['key'])
        if s and r['text']:
            known.setdefault((s.kind, s.ja), r['text'])
    n = 0
    for r in rows:
        s = g.strings.get(r['key'])
        if s and not r['text'] and (s.kind, s.ja) in known:
            n += 1
            if a.n:
                print('%s <- %s' % (r['key'], known[(s.kind, s.ja)]))
            else:
                r['text'] = known[(s.kind, s.ja)]
    if not a.n:
        vgtext.write_tsv(a.file, head, rows)
    print('%s: %d filled%s' % (a.file, n, ' (not written: -n)' if a.n else ''))


def cmd_status(a):
    g = Game(a.pak)
    tl, problems = vgtext.load(a.file, g.strings)
    total, done = Counter(), Counter()
    for k, s in g.strings.items():
        total[s.kind] += 1
        done[s.kind] += k in tl
    for kind in vgtext.KINDS:
        if total[kind]:
            print('%-9s %5d strings, %5d translated, %5d left' % (
                kind, total[kind], done[kind], total[kind] - done[kind]))
    for p in problems:
        print('ERROR ' + p)
    return 1 if problems else 0


def cmd_read(a):
    g = Game(a.pak)
    tl = {}
    if a.tl:
        tl, problems = vgtext.load(a.tl, g.strings)
        if problems:
            sys.exit('\n'.join(problems))
    os.makedirs(a.outdir, exist_ok=True)
    path = os.path.join(a.outdir, 'messages.txt')
    with open(path, 'w', encoding='utf-8') as f:
        for m in g.txb.messages:
            f.write('==== message %03d\n' % m.index)
            for k, s in g.strings.items():
                if s.kind != 'text' or s.info['msg'] != m.index:
                    continue
                spk = g.speaker(s)
                f.write('-- %s%s\n' % (k, ' [%s %s]' % (spk, ja(s.info['name'])) if spk else ''))
                f.write(ja(s.ja) + '\n')
                if k in tl:
                    f.write('>> ' + tl[k].replace('\n', '\n>> ') + '\n')
    print(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('template')
    p.add_argument('pak')
    p.add_argument('out')
    p = sub.add_parser('skeleton')
    p.add_argument('pak')
    p.add_argument('out')
    p = sub.add_parser('pseudo')
    p.add_argument('pak')
    p.add_argument('out')
    p.add_argument('--seed', type=int, default=1)
    p = sub.add_parser('check')
    p.add_argument('file')
    p.add_argument('--pak', required=True)
    p.add_argument('-v', action='store_true')
    p = sub.add_parser('layout')
    p.add_argument('file')
    p.add_argument('keys', nargs='*')
    p.add_argument('--pak', required=True)
    p = sub.add_parser('view')
    p.add_argument('file')
    p.add_argument('out')
    p.add_argument('--pak', required=True)
    p = sub.add_parser('put')
    p.add_argument('file')
    p.add_argument('batch')
    p.add_argument('--force', action='store_true')
    p = sub.add_parser('fill')
    p.add_argument('file')
    p.add_argument('--pak', required=True)
    p.add_argument('-n', action='store_true')
    p = sub.add_parser('status')
    p.add_argument('file')
    p.add_argument('--pak', required=True)
    p = sub.add_parser('read')
    p.add_argument('pak')
    p.add_argument('outdir')
    p.add_argument('--tl')
    a = ap.parse_args(argv)
    return globals()['cmd_' + a.cmd](a) or 0


if __name__ == '__main__':
    sys.exit(main())
