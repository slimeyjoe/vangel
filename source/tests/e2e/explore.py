#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""explore.py TEST_GAME PAK [PLAN ...] [--out DIR] [--check] [--list] [-v]: play the game on
the engine by plans and write the routes tests/check_vm.py plays on both the engine and the
original (tests/e2e/routes; --check writes nothing and fails when a route, or a game.dat a
plan leaves for another, is not the one there: the engine plays differently now).

The engine is tests/test_game.c with the route on stdin: at every wait it prints the state
(the interpreter's pc, the variables, the last menu's choice, ...) and reads what the player
does there. The player knows the wait from the statement before the pc (the scenario,
tools/scb.py): the console's question (25h 0, or before the scenario), a menu (24h: its
number and items), a message page (19h, a key or a timed page), a wait (15h, timed) or an
input (16h), a built-in sequence (25h: the prologue's timed pages, the notice's pages, the
music mode). It answers as the plan says, by default:
  * the question: Y; a key page, an input, a notice page: Return; a timed wait: nothing (the
    time runs out);
  * a menu: the plan's item for this menu at this visit (1-based; the last one given stays;
    without one the items in turn, so a menu that loops until every item was taken ends),
    reached with cursor-down from the item highlighted (the menu's last choice
    when the same statement asked it the time before, else the first), then Return. Each
    press has a frame of nothing after it, so a key's break code comes before the next press;
  * the save menu (41) and the load menu (42): the plan's slots in turn;
  * the investigation (menus 23-37: the four things, in an order of the plan's, one order a
    visit to the room): the item of the next thing of the order;
  * the title (43): the plan's choices in turn; when they are used up the route ends there.
The route is the answers, a line a wait (test_game.c has the words), after a head of
`# key: value` lines (the plan, and what check_vm needs: `sound`). Each plan says what it
must have covered (`expect`: menus, messages, built-ins); a route that misses it is an error.
Exit status 0 when every plan played as expected.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import scb  # noqa: E402
import vgpak  # noqa: E402

RET, DOWN, UP, ESC, SPACE, KEY_Y, KEY_N = 0x1C, 0x3D, 0x3A, 0x00, 0x34, 0x15, 0x2E
THINGS = {'W': '白', 'R': '赤', 'B': '黒', 'D': 'ボード'}    # the investigation's four things
TITLE, SAVE, LOAD = 43, 41, 42
ENDINGS = {211: 1, 210: 2, 212: 3, 213: 4}
MAX_WAITS = 20000


def k(scan):
    return ['k%02X' % scan, '.']


# frames after a song is chosen: playing another fades the one before over 1.5 s (84
# frames), and an entry given while the fade blocks is gone
FADE = 100


def music_all(n=18, gap=FADE):
    """the music mode: every song played in turn (Return, a while, down), then ESC"""
    out = []
    for i in range(n):
        out += k(RET) + ['.'] * gap
        if i + 1 < n:
            out += k(DOWN)
    return out + k(ESC)


def music_mouse(n=18, gap=FADE):
    """the music mode by the mouse: a click on every song's row, then the right button"""
    out = []
    for i in range(n):
        out += ['c320,%d' % (0x30 + 16 * i + 8), '.'] + ['.'] * gap
    return out + ['m320,200,2', 'm320,200,0', '.']


def right():
    return ['m320,200,2', 'm320,200,0', '.']


# The plans. menus: {menu: [item at the 1st visit, 2nd, ...]}; saves / loads / title: the
# items in turn; order: the investigation's orders, a visit each; skip: where a timed wait
# is cut short (('page', n): the prologue's n-th page; ('msg', m): message m's first timed
# page; ('pc', p): the first timed wait at pc p); musmode / announce: the input of the music
# mode / of a notice page; console: 'y' or 'n'; turn: where the items in turn start (0: the
# first item at the first visit, 1: the second, ...); until_menu: the route ends at the first visit
# of this menu; gamedat: the game.dat to start with, from the run of another plan
# (plan, how: 'all' as it was, 'bad' slot 1 damaged and the file cut after it); expect: what
# the route must have reached.
WIN = {8: [1], 18: [1], 19: [2], 21: [2], 38: [2], 39: [1], 40: [2]}
PLANS = {
    # ending No.1, everything watched; the six save points into slots 1, 2, 3, 1, 2, 3
    'end1': dict(menus=WIN, title=[1], saves=[1, 2, 3, 1, 2, 3], order=['WRBD'],
                 expect=dict(endings=[1], builtins=[1])),
    # No.2: survived alone (insulation suit, freezing rounds), waited, refused; the prologue
    # cut short at its first page
    'end2': dict(turn=1, menus={**WIN, **{19: [4], 21: [1], 38: [4], 39: [2]}}, title=[1],
                 order=['RBDW'], skip=[('page', 1)], expect=dict(endings=[2])),
    # No.3: swallowed the drug; the prelude cut short in message 206
    'end3': dict(turn=2, menus={**WIN, **{40: [1]}}, title=[1], order=['BDWR'],
                 skip=[('msg', 206)], expect=dict(endings=[3])),
    # No.3 by losing the fight (buckshot)
    'end3b': dict(turn=3, menus={**WIN, **{38: [1]}}, title=[1], order=['WBRD'],
                  skip=[('msg', 207)], expect=dict(endings=[3])),
    # No.4: no armour (straight to the hospital)
    'end4': dict(turn=1, menus={**WIN, **{18: [2]}}, title=[1], order=['DWRB'],
                 skip=[('msg', 208)], expect=dict(endings=[4])),
    # No.4: the wrong armour (anti-beam)
    'end4b': dict(turn=2, menus={**WIN, **{19: [3]}}, title=[1], order=['RDWB'],
                  skip=[('msg', 209)], expect=dict(endings=[4])),
    # the title's other items: the notice by keys, the music mode by keys (every song), a load
    # without game.dat, the load menu left; the logo cut short
    'title': dict(title=[4, 3, 2, 2], loads=[1, 4], musmode=music_all(),
                  skip=[('pc', 1975)], expect=dict(builtins=[3, 4], msgs=[205])),
    # the same by the mouse: the notice by the left and the right button, the music mode by
    # clicks, left with the right button
    'mouse': dict(title=[4, 3], musmode=music_mouse(), announce=['c320,200', '.'],
                  announce2=right(), expect=dict(builtins=[3, 4])),
    # the mouse not used (N at the question): the notice, the music mode, into the story
    'nomouse': dict(console='n', title=[4, 3, 1], musmode=music_all(4), until_menu=1,
                    expect=dict(builtins=[3, 4], menus=[1])),
    # loads from the saves end1 made: slot 3 (before the confrontation), anti-beam rounds:
    # on to ending No.3
    'load': dict(gamedat=('end1', 'all'), title=[2], loads=[3], menus={38: [3], 39: [2], 40: [2]},
                 expect=dict(endings=[3])),
    # a damaged slot, an empty slot, the menu left
    'load_bad': dict(gamedat=('end1', 'bad'), title=[2, 2, 2], loads=[1, 2, 4],
                     expect=dict(msgs=[205])),
    # no driver (GAME.BAT's option 4): the opening's measure loops, the music mode (which
    # without a driver returns at once: no wait), into the story
    'nosound': dict(sound='none', title=[3, 1], musmode=k(ESC), until_menu=1,
                    expect=dict(builtins=[1], menus=[1])),
}


def plan_menus(plan, menu):
    return plan.get('menus', {}).get(menu, [])


class Player:
    def __init__(self, sc, plan):
        self.sc, self.plan = sc, plan
        self.visits = {}
        self.last_menu = None           # the statement of the last menu, and its choice
        self.titles = list(plan.get('title', [1]))
        self.saves = list(plan.get('saves', [4]))
        self.loads = list(plan.get('loads', [4]))
        self.orders = list(plan.get('order', ['WRBD']))
        self.order = None
        self.skip = set(plan.get('skip', ()))
        self.pages = 0
        self.pcs_cut = set()
        self.notices = 0
        self.msg_timed = set()
        self.seen = {'menus': set(), 'msgs': set(), 'builtins': set(), 'endings': []}

    def stmt(self, pc):
        """the statement the wait is in: (number, opcode, args)"""
        if pc < 2:
            return 0, None, []
        at, op, args = self.sc.stmts[pc - 2]
        return pc - 1, op, args

    def answer(self, kind, st):
        n, op, args = self.stmt(int(st['pc']))
        if n == 0 or (op == 0x25 and args[0] == 0):
            return k(KEY_Y if self.plan.get('console', 'y') == 'y' else KEY_N)
        if op == 0x24:
            return self.menu(n, args[0], st)
        if op == 0x19:
            m = args[0]
            self.seen['msgs'].add(m)
            if m in ENDINGS and ENDINGS[m] not in self.seen['endings']:
                self.seen['endings'].append(ENDINGS[m])
            if kind == 'key':
                return k(RET)
            if m not in self.msg_timed:
                self.msg_timed.add(m)
                if ('msg', m) in self.skip:
                    return k(RET)
            return []
        if op == 0x25:
            b = args[0]
            self.seen['builtins'].add(b)
            if b == 1:
                self.pages += 1
                return k(RET) if ('page', self.pages) in self.skip else []
            if b == 4:
                return list(self.plan.get('musmode', k(ESC)))
            self.notices += 1
            if self.notices == 2 and 'announce2' in self.plan:
                return list(self.plan['announce2'])
            return list(self.plan.get('announce', k(RET)))
        if op == 0x16:
            return k(RET)
        pc = n + 1
        if ('pc', pc) in self.skip and pc not in self.pcs_cut:
            self.pcs_cut.add(pc)
            return k(RET)
        return []                       # 15h and anything timed: the time runs out

    def menu(self, n, menu, st):
        self.seen['menus'].add(menu)
        items = [x.decode('cp932', 'replace') for x in self.sc.t44[menu - 1][1]]
        v = self.visits[menu] = self.visits.get(menu, 0) + 1
        if menu == self.plan.get('until_menu'):
            return None
        if menu == TITLE:
            if not self.titles:
                return None
            pick = self.titles.pop(0)
        elif menu == SAVE:
            pick = self.saves.pop(0) if self.saves else 4
        elif menu == LOAD:
            pick = self.loads.pop(0) if self.loads else 4
        elif 23 <= menu <= 37:
            if menu == 23 or self.order is None:
                self.order = list(self.orders.pop(0) if self.orders else 'WRBD')
            want = [c for c in self.order if any(THINGS[c] in x for x in items)]
            c = want[0]
            self.order.remove(c)
            pick = 1 + next(i for i, x in enumerate(items) if THINGS[c] in x)
        else:
            picks = plan_menus(self.plan, menu)
            turn = self.plan.get('turn', 0)
            pick = picks[min(v, len(picks)) - 1] if picks else (v - 1 + turn) % len(items) + 1
        cnt = len(items)
        cur = 0
        if self.last_menu == n:
            c = int(st['choice'])
            cur = c - 1 if 1 <= c <= cnt else 0
        self.last_menu = n
        return k(DOWN) * ((pick - 1 - cur) % cnt) + k(RET)


def parse(line):
    w = line.split()
    return int(w[1]), w[2], dict(x.split('=', 1) for x in w[3:])


RECORD = (20 + 24) * 3                  # a slot of game.dat (tools/saves.py)


def gamedat_for(out, how):
    """the game.dat a plan starts with, from another plan's"""
    src, kind = how
    data = open(os.path.join(out, src + '.end.dat'), 'rb').read()
    if kind == 'bad':                   # slot 1's size wrong; slots 2 and 3 not in the file
        rec = bytearray(data[:RECORD])
        rec[3] ^= 0x01
        data = bytes(rec)
    return data


def play(test, pak, sc, name, plan, out, verbose=0):
    """the plan on the engine: (route lines, the player); the game.dat the run ends with is
    kept as OUT/NAME.end.dat when another plan starts from it"""
    p = Player(sc, plan)
    lines = []
    with tempfile.TemporaryDirectory(prefix='vg-explore-') as d:
        if plan.get('gamedat'):
            data = gamedat_for(out, plan['gamedat'])
            open(os.path.join(d, 'game.dat'), 'wb').write(data)
            open(os.path.join(out, name + '.dat'), 'wb').write(data)
        args = [test, pak, d, '-']
        if plan.get('sound'):
            args.append('sound=' + plan['sound'])
        e = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                             bufsize=1)
        try:
            for ln in e.stdout:
                if not ln.startswith('sync'):
                    continue
                n, kind, st = parse(ln)
                a = p.answer(kind, st)
                if verbose:
                    print('%s %5d %-5s pc %-5s %s' % (name, n, kind, st['pc'],
                                                      ' '.join(a) if a is not None else
                                                      'end'), flush=True)
                if a is None:
                    break
                if n > MAX_WAITS:
                    raise SystemExit('explore: %s: no end after %d waits (pc %s)' % (
                        name, MAX_WAITS, st['pc']))
                lines.append(' '.join(a))
                e.stdin.write(lines[-1] + '\n')
                e.stdin.flush()
        finally:
            e.stdin.close()
            e.wait()
        if any(q.get('gamedat', ('',))[0] == name for q in PLANS.values()):
            src = os.path.join(d, 'game.dat')
            open(os.path.join(out, name + '.end.dat'), 'wb').write(open(src, 'rb').read())
    return lines, p


def check(name, plan, p):
    exp = plan.get('expect', {})
    bad = []
    for key in ('endings',):
        if key in exp and p.seen[key] != exp[key]:
            bad.append('%s %s, expected %s' % (key, p.seen[key], exp[key]))
    for key in ('menus', 'msgs', 'builtins'):
        miss = set(exp.get(key, ())) - p.seen[key]
        if miss:
            bad.append('%s not reached: %s' % (key, sorted(miss)))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('test')
    ap.add_argument('pak')
    ap.add_argument('plans', nargs='*')
    ap.add_argument('--out', default=os.path.join(HERE, 'routes'))
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--check', action='store_true',
                    help='write nothing: fail when a route differs from the one in --out')
    ap.add_argument('-v', action='count', default=0)
    a = ap.parse_args()
    if a.list:
        print(' '.join(PLANS))
        return 0
    data = vgpak.read(a.pak).find('CMD00.SCB')
    sc = scb.Scenario(data.data if data else
                      open(os.path.join(ROOT, 'resources', 'original', 'pc98', 'CMD00.SCB'),
                           'rb').read())
    rc = 0
    seen = {'menus': set(), 'msgs': set(), 'builtins': set(), 'endings': set()}
    for name in a.plans or list(PLANS):
        plan = PLANS[name]
        out = a.out
        if a.check:
            out = tempfile.mkdtemp(prefix='vg-explore-check-')
            for f in os.listdir(a.out):         # the game.dat files a plan starts from
                if f.endswith('.dat'):
                    shutil.copy(os.path.join(a.out, f), out)
        os.makedirs(out, exist_ok=True)
        lines, p = play(a.test, a.pak, sc, name, plan, out, a.v)
        bad = check(name, plan, p)
        for key in seen:
            seen[key] |= set(p.seen[key])
        text = '# plan: %s\n' % name
        if plan.get('sound'):
            text += '# sound: %s\n' % plan['sound']
        if plan.get('gamedat'):
            text += '# gamedat: %s.dat\n' % name
        text += ''.join(ln + '\n' for ln in lines)
        path = os.path.join(a.out, name + '.route')
        if a.check:
            for f in os.listdir(out):
                if f.endswith('.dat') and (not os.path.exists(os.path.join(a.out, f)) or
                                           open(os.path.join(a.out, f), 'rb').read() !=
                                           open(os.path.join(out, f), 'rb').read()):
                    bad.append('%s differs from the one in %s' % (f, a.out))
            shutil.rmtree(out, ignore_errors=True)
            if not os.path.exists(path) or open(path).read() != text:
                bad.append('the route differs from %s (make e2e-routes)' % path)
        else:
            open(path, 'w').write(text)
        print('%s: %d waits; menus %d, messages %d, built-ins %s, endings %s%s' % (
            name, len(lines), len(p.seen['menus']), len(p.seen['msgs']),
            sorted(p.seen['builtins']), p.seen['endings'], ''.join('; ' + b for b in bad)))
        if bad:
            rc = 1
    print('all plans: menus %d %s, messages %d, endings %s' % (
        len(seen['menus']), sorted(set(range(1, 44)) - seen['menus']), len(seen['msgs']),
        sorted(seen['endings'])))
    return rc


if __name__ == '__main__':
    sys.exit(main())
