#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_lang.py BUILD PAK FONTS: translated text, with a pseudo-translation of the game
(tools/tl.py pseudo: 0.5x-3x the original's width, Polish letters, full-width characters,
words wider than a line, line and page breaks, long speaker names; about one string in ten
left untranslated, so the original's text and names come next to it; docs/translation.md).

1. Pack: mkpack.py --text pl=pseudo.tsv; the pack's string table holds exactly the file's
   strings, every speaker's name and both quotes (tools/vgtext.py pack_entries).
2. Layout: BUILD/tests/test_lang plays every message, menu and built-in in that language and
   prints where each line is drawn; that equals tools/vglayout.py (lrvne's reflow in Python,
   the original's page loop of txb.layout with the translation's passages), page by page with
   the timed pages' cells. The reference keeps its rules: no line wider than its place (row 3
   of the window stops before the page-wait icon; the prologue's 72 columns, the staff roll's
   32, the notice's 80), no more lines than a page holds, nothing lost (the lines hold every
   character of the text but the spaces and breaks between them, in order). The engine drew
   nothing under the page-wait icon.
3. Play: every plan of tests/e2e/explore.py played on the engine in Japanese and with
   lang=pl on the pseudo pack: the extra pages are answered as the page waits they are, and
   both plays meet the same menus in the same game state (the interpreter, its variables, the
   flags, the music, the palette, game.dat): a translation changes nothing but the text.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', 'tools')
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(HERE, 'e2e'))
import explore  # noqa: E402
import lrvnepath  # noqa: E402,F401
from lrvne import reflow  # noqa: E402
import scb as scbmod  # noqa: E402
import tl  # noqa: E402
import vglayout  # noqa: E402
import vgtext  # noqa: E402

fails = []
STATE = ('pc', 'depth', 'stack', 'vars', 'skip', 'choice', 'mus', 'dat', 'dac', 'disp', 'ptr')


def fail(msg):
    fails.append(msg)
    print('FAIL ' + msg)


def run(cmd, **kw):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)
    if r.returncode:
        sys.exit('%s: exit %d\n%s' % (cmd[0], r.returncode, r.stderr[-2000:]))
    return r


def h(b):
    return b.hex() if b else '-'


# ---- 2. the layout ------------------------------------------------------------------------------

def expected_messages(g, tab):
    out = []
    for m in g.txb.messages:
        out.append('msg %d' % m.index)
        for rows, mode, nb in vglayout.msg_pages(vgtext.message_lines(m, g.dic), m.index, tab,
                                                 g.cols):
            out += ['line %d %d %d %s' % (r, c, int(u), h(b)) for r, c, b, u in rows]
            out.append('page %d %d' % (mode, nb))
        out.append('v1 0')
    return out


def expected_menus(g, tab, sc):
    out = []
    for mi, (_ln, items) in enumerate(sc.t44, 1):
        out.append('menu %d' % mi)
        for i, orig in enumerate(items):
            t = tab.get('menu%02d.%d' % (mi, i + 1))
            if t is None:
                out.append('line %d 0 0 %s' % (i, h(orig)))
            else:
                col, b, _c = vglayout.menu_item(orig, t, g.cols)
                out.append('line %d %d 1 %s' % (i, col, h(b)))
    return out


def expected_builtins(g, tab):
    """{where: set of (page, row, col, hex)} (console: text only)"""
    s = g.strings
    out = {w: set() for w in range(1, 6)}
    for k in s:
        t = tab.get(k)
        if t is None:
            continue
        if k.startswith('bi.prologue.'):
            out[1] |= {(p, r, x, h(b)) for p, r, x, b in vglayout.prologue(t, g.cols)}
        elif k.startswith('bi.staff.'):
            out[2] |= {(p, r, c, h(b)) for p, r, c, b in vglayout.staff(t, g.cols)}
        elif k.startswith('announce.'):
            out[3] |= {(p, r, c, h(b)) for p, r, c, b in vglayout.announce(t, g.cols)}
        elif k == 'bi.music.heading':
            out[4].add((0, 0, vglayout.bi_centre(21, s[k].ja, t, g.cols), h(t)))
        elif k == 'bi.music.help':
            out[4].add((0, 24, 3, h(t)))
        elif re.match(r'bi\.music\.\d+$', k):
            out[4].add((0, int(k.split('.')[-1]) + 3, 20, h(t)))
        elif k in ('bi.announce.prompt', 'bi.announce.last'):
            out[4].add((0, 23, 0, h(t)))
        elif k in ('con.ask', 'con.yes', 'con.loading'):
            out[5].add(h(t))
    return out


def rules(g, tab):
    """the reference's own rules: (problems, passages laid out on more pages than the
    original's)"""
    bad = []
    cols = g.cols

    def check(key, t, lines, w, hgt, last=None, keep=False):
        last = w if last is None else last
        per = {}
        for ln in lines:
            per.setdefault(ln.page, []).append(ln)
            cap = (last if ln.row == hgt - 1 else w)
            n = len(reflow.chars(t[ln.start:ln.end], cols))
            if ln.col + ln.cols > cap and n > 1:
                bad.append('%s: page %d row %d: %d columns from %d, wider than %d' % (
                    key, ln.page, ln.row, ln.cols, ln.col, cap))
            if ln.row >= hgt:
                bad.append('%s: row %d of %d' % (key, ln.row, hgt))
        got = b''.join(t[ln.start:ln.end] for ln in lines)
        strip = (lambda x: x.replace(b' ', b'').replace(b'\n', b'').replace(b'\f', b''))
        if strip(got) != strip(t):
            bad.append('%s: characters lost or reordered' % key)

    for k, s in g.strings.items():
        t = tab.get(k)
        if t is None:
            continue
        if s.kind == 'text':
            # the passage from row 0 after a long name: the window's rules hold anywhere
            check(k, t, vglayout.lay(t, cols, vgtext.WIN_W, vgtext.WIN_H, vgtext.WIN_LAST,
                                     0, 17, 17), vgtext.WIN_W, vgtext.WIN_H, vgtext.WIN_LAST)
        elif k.startswith('bi.prologue.'):
            check(k, t, vglayout.lay(t, cols, vgtext.PROLOGUE_W, vgtext.PROLOGUE_H),
                  vgtext.PROLOGUE_W, vgtext.PROLOGUE_H)
        elif k.startswith('bi.staff.'):
            check(k, t, vglayout.lay(t, cols, vgtext.STAFF_W, vgtext.STAFF_H, keep=True),
                  vgtext.STAFF_W, vgtext.STAFF_H)
        elif s.kind == 'announce':
            check(k, t, vglayout.lay(t, cols, vgtext.ANNOUNCE_W, vgtext.ANNOUNCE_H, keep=True),
                  vgtext.ANNOUNCE_W, vgtext.ANNOUNCE_H)
    return bad


def parse_engine(out):
    """(message and menu lines, {where: set}, icon count)"""
    seq, tls, icon = [], {w: set() for w in range(1, 6)}, None
    for ln in out.splitlines():
        f = ln.split()
        if f[0] == 'tl':
            w = int(f[1])
            if w == 5:
                tls[5].add(f[5])
            else:
                tls[w].add((int(f[2]), int(f[3]), int(f[4]), f[5]))
        elif f[0] == 'icon':
            icon = int(f[1])
        elif f[0] != 'done':
            seq.append(ln)
    return seq, tls, icon


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    return min(len(a), len(b)), '(end)' if len(a) < len(b) else a[len(b)], \
        '(end)' if len(b) < len(a) else b[len(a)]


# ---- 3. the plays -------------------------------------------------------------------------------

def plays(build, pak, ppak, sc):
    test = os.path.join(build, 'tests', 'test_game')
    order = sorted(explore.PLANS, key=lambda n: explore.PLANS[n].get('gamedat') is not None)
    total = waits_ja = waits_pl = 0
    with tempfile.TemporaryDirectory(prefix='vg-lang-') as d:
        res = {}
        for lang, p in (('ja', pak), ('pl', ppak)):
            out = os.path.join(d, lang)
            os.makedirs(out)
            for name in order:
                lines, player = explore.play(test, p, sc, name, explore.PLANS[name], out,
                                             lang=None if lang == 'ja' else 'pl')
                bad = explore.check(name, explore.PLANS[name], player)
                if bad:
                    fail('play %s %s: %s' % (lang, name, '; '.join(bad)))
                res[(lang, name)] = (len(lines), [(m, tuple(st.get(f) for f in STATE))
                                                  for m, st in player.menu_states])
        for name in order:
            nj, sj = res[('ja', name)]
            npl, sp = res[('pl', name)]
            waits_ja += nj
            waits_pl += npl
            total += len(sj)
            if sj != sp:
                i, x, y = first_diff(sj, sp)
                fail('play %s: menu %d of %d/%d differs:\n  ja %s\n  pl %s' % (
                    name, i, len(sj), len(sp), x, y))
    print('play: %d plans, %d menus met in the same state; %d waits in Japanese, %d with the '
          'pseudo-translation' % (len(order), total, waits_ja, waits_pl))
    if waits_pl <= waits_ja:
        fail('play: the pseudo-translation added no page waits')


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    build, pak, fonts = sys.argv[1:]
    out = os.path.join(build, 'tests', 'lang')
    os.makedirs(out, exist_ok=True)
    tsv, ppak = os.path.join(out, 'pseudo.tsv'), os.path.join(out, 'pseudo.pak')
    py = [sys.executable, '-I']

    # 1. the pack
    print(run(py + [os.path.join(TOOLS, 'tl.py'), 'pseudo', pak, tsv]).stdout.strip())
    print(run(py + [os.path.join(TOOLS, 'mkpack.py'), '--fonts', fonts, '--text', 'pl=' + tsv,
                    '-o', ppak]).stdout.strip())
    g = tl.Game(ppak)
    want, problems = vgtext.load(tsv, g.strings)
    if problems:
        sys.exit('\n'.join(problems))
    want = vgtext.pack_entries(g.strings, want)
    e = g.pack.find('text', lang='pl')
    table = vgtext.read_table(e.data) if e is not None else {}
    if table != {k: v for k, v in want.items()}:
        fail('pack: the string table differs from %s (%d vs %d strings)' % (tsv, len(table),
                                                                           len(want)))
    else:
        print('pack: %d strings in the table, as in the file with the names and quotes' %
              len(table))

    # 2. the layout
    sc = scbmod.Scenario(g.get('CMD00.SCB'))
    r = run([os.path.join(build, 'tests', 'test_lang'), ppak, 'pl'])
    seq, tls, icon = parse_engine(r.stdout)
    ref = expected_messages(g, table) + expected_menus(g, table, sc)
    if seq != ref:
        i, x, y = first_diff(seq, ref)
        fail('layout: the engine and tools/vglayout.py differ at line %d of %d:\n  engine    %s'
             '\n  reference %s' % (i, len(ref), x, y))
    exp = expected_builtins(g, table)
    names = {1: 'prologue', 2: 'staff roll', 3: 'notice', 4: 'music mode and prompts',
             5: 'console'}
    for w in range(1, 6):
        if tls[w] != exp[w]:
            fail('layout: the %s: the engine drew %d lines the reference does not, missed %d '
                 '(e.g. %s)' % (names[w], len(tls[w] - exp[w]), len(exp[w] - tls[w]),
                                sorted(tls[w] ^ exp[w])[:1]))
    if icon != 0:
        fail('layout: %s message pages drew under the page-wait icon' % icon)
    bad = rules(g, table)
    for b in bad[:5]:
        fail('layout rules: ' + b)
    npages = sum(1 for ln in ref if ln.startswith('page'))
    print('layout: %d messages (%d pages), %d menus, %d built-in lines: the engine as the '
          'reference; %d rule problems' % (len(g.txb.messages), npages, len(sc.t44),
                                          sum(len(v) for v in exp.values()), len(bad)))

    # 3. the plays
    plays(build, pak, ppak, sc)
    print('check_lang: %s' % ('FAILED (%d)' % len(fails) if fails else 'ok'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
