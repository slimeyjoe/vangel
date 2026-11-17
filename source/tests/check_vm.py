#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_vm.py - the engine against M.EXE end to end: the whole game played on the same
input by both, compared at every wait.

usage: check_vm.py TEST_GAME PAK [ROUTE ...]          (with $EMU_PYTHON: unicorn)

A route (tests/e2e/routes/NAME.route, made by tests/e2e/explore.py) is a line for each wait
the game enters, what the player does from the next frame on (tests/test_game.c has the
words), and a head of `# key: value` lines: `gamedat: NAME` the game.dat the run starts with
(tests/e2e/routes/NAME.dat, built by tools/saves.py), `sound: none` the machine without a
driver. The original (re-tools/va98.py: M.EXE from its start, its own VSYNC and keyboard
handlers, the real PMD.COM) and the engine (tests/test_game.c) each play it; at every wait,
in order, these must be identical:

  * the interpreter: pc, depth, the stack, the variables v0..vn (type and value);
  * the graphics: both VRAM pages, buffer 12, the window's two buffers (CRC-32 of their
    planes), the page shown, the DAC;
  * the skip flag, the last menu's choice, the music layer's song and volume, the pointer;
  * game.dat (CRC-32), and the INT 60h calls since the wait before (AX, and AL after the call
    where the binding reads it: 09h, 17h, 22h; a call equal to the one before it is left out:
    the spin loops call as often as they turn).
    AH=05h is left out: statement 35h's loop reads the measure counter as often as it turns,
    from the moment the song starts, and what it reads first depends on time (the original's
    first read comes after a VSYNC and the driver's first tick); where the loop ends is in
    the variables.

The first wait is the console's question, before the scenario is loaded and the graphics
start: there page 0, the DAC (the original asks on the text screen, the engine in page 0),
the pc and the variables (not set up yet) are not compared. Time is not
compared: the original runs on an instruction time base, the engine on the reference
machine's clocks; the routes give the input at waits, so the state at each wait does not
depend on it. The route's frames count from the frame after the wait's first input poll on
the original (re-tools/va98.py; the music mode draws its list for longer than a frame before
it polls, and a key pressed and let go meanwhile would be lost), from the frame after the
wait began on the engine, which draws in no time.

Without ROUTE arguments every route in tests/e2e/routes is played, in parallel (CHECK_VM_JOBS,
default: the number of CPUs). The original's results are kept between runs (refcache.py).
"""
import hashlib
import multiprocessing
import os
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
ROUTES = os.path.join(HERE, 'e2e', 'routes')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
import refcache  # noqa: E402

FIELDS = ['pc', 'depth', 'stack', 'vars', 'page0', 'page1', 'buf12', 'ws', 'ww', 'disp',
          'dac', 'skip', 'choice', 'mus', 'ptr', 'dat', 'int60']


# at the first wait, the console's question before the scenario is loaded: what the engine
# draws there (the question in page 0, white in the DAC) and the interpreter not yet set up
CONSOLE_SKIP = {'page0', 'dac', 'pc', 'vars'}


def read_route(path):
    head, lines = {}, []
    for ln in open(path):
        ln = ln.rstrip('\n')
        if ln.startswith('#'):
            k, _, v = ln[1:].partition(':')
            if v:
                head[k.strip()] = v.strip()
            continue
        lines.append(ln)
    return head, lines


def fmt_state(n, kind, st, calls):
    return 'sync %d %s %s' % (n, kind, ' '.join('%s=%s' % (k, v) for k, v in [
        ('pc', st['pc']), ('depth', st['depth']),
        ('stack', ','.join(str(x) for x in st['stack'])),
        ('vars', ','.join('%d:%d' % tv for tv in st['vars'])),
        ('page0', '%08x' % st['page0']), ('page1', '%08x' % st['page1']),
        ('buf12', '%08x' % st['buf12']), ('ws', '%08x' % st['win_save']),
        ('ww', '%08x' % st['win_work']), ('disp', st['disp']), ('dac', st['dac']),
        ('skip', st['skip']), ('choice', st['choice']), ('mus', '%s/%d' % st['mus']),
        ('ptr', st['ptr']), ('dat', '-' if st['gamedat'] is None else '%08x' % st['gamedat']),
        ('int60', ','.join(calls) or '-')]))


# what the binding reads of a call's result (sound.md §3): AL of 09h, 17h and 22h; the rest
# of the driver's registers are its own business
READS_AL = (0x09, 0x17, 0x22)


def collapse(calls):
    out = []
    for ax, r in calls:
        if ax >> 8 == 0x05:
            continue
        c = '%04x:%02x' % (ax, r & 0xFF) if ax >> 8 in READS_AL else '%04x' % ax
        if not out or out[-1] != c:
            out.append(c)
    return out


def original(pak, head, lines, gamedat):
    """the route on M.EXE under va98: the lines check_vm compares, and the waits' places"""
    import va98
    out, where = [], []
    fonts = va98.Fonts(pak)

    def policy(m, w):
        st = m.state()
        calls = collapse(m.int60)
        del m.int60[:]
        out.append(fmt_state(w['n'], w['kind'], st, calls))
        where.append(w['where'])
        if w['n'] > len(lines):
            raise va98.Stop
        return lines[w['n'] - 1].split()
    m = va98.VA98(fonts, policy=policy, gamedat=gamedat,
                  sound='none' if head.get('sound') == 'none' else 'pmd')
    try:
        r = m.run()
    except RuntimeError as e:           # a hang (va98's frame limit): the waits until then
        cs, ip = m.uc.reg_read(va98.UC_X86_REG_CS), m.uc.reg_read(va98.UC_X86_REG_IP)
        out.append('hang %s at %04X:%04X, pc %d' % (e, cs - m.base, ip, m.word(m.ds, 0x5A)))
        return {'lines': out, 'where': where, 'frames': m.frame}
    if r == 'exit':
        out.append('exit %d' % m.exit_code)
    else:
        out.append('end')
    return {'lines': out, 'where': where, 'frames': m.frame}


def engine(test, pak, head, lines, gamedat):
    with tempfile.TemporaryDirectory(prefix='vg-check-vm-') as d:
        if gamedat is not None:
            open(os.path.join(d, 'game.dat'), 'wb').write(gamedat)
        rp = os.path.join(d, 'route')
        open(rp, 'w').write(''.join(ln + '\n' for ln in lines))
        args = [test, pak, d, rp]
        if head.get('sound'):
            args.append('sound=' + head['sound'])
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out = [ln for ln in p.stdout.splitlines() if ln.startswith(('sync', 'end', 'exit'))]
        # the engine's own "exit N" after the route's end is not the program's exit
        if 'end' in out:
            out = out[:out.index('end') + 1]
        return out, p.returncode, p.stderr


def fields(line):
    w = line.split()
    return w[:3], dict(x.split('=', 1) for x in w[3:])


def compare(name, ref, got):
    """the first difference, or None"""
    want = ref['lines']
    for i in range(max(len(want), len(got))):
        a = want[i] if i < len(want) else '(nothing)'
        b = got[i] if i < len(got) else '(nothing)'
        if a == b:
            continue
        if not a.startswith('sync') or not b.startswith('sync'):
            return 'record %d: original %s, engine %s' % (i + 1, a[:120], b[:120])
        (ha, fa), (hb, fb) = fields(a), fields(b)
        skip = CONSOLE_SKIP if i == 0 and ref['where'][0] == 'console' else set()
        diff = [k for k in FIELDS if k not in skip and fa.get(k) != fb.get(k)]
        if ha != hb or diff:
            msg = ['wait %d (%s, %s): %s' % (i + 1, ha[2], ref['where'][i] if i < len(
                ref['where']) else '?', ' '.join(ha[2:]) if ha != hb else
                ', '.join(diff) + ' differ')]
            for k in diff[:6]:
                x, y = fa.get(k, ''), fb.get(k, '')
                if ',' in x or ',' in y:
                    lx, ly = x.split(','), y.split(',')
                    j = next((j for j in range(max(len(lx), len(ly)))
                              if lx[j:j + 1] != ly[j:j + 1]), 0)
                    x = '[%d of %d] %s' % (j, len(lx), ','.join(lx[max(0, j - 2):j + 6]))
                    y = '[%d of %d] %s' % (j, len(ly), ','.join(ly[max(0, j - 2):j + 6]))
                msg.append('    %-6s original %s\n           engine   %s' % (k, x[:200], y[:200]))
            return '\n'.join(msg)
    return None


def load_gamedat(head):
    n = head.get('gamedat')
    return open(os.path.join(ROUTES, n), 'rb').read() if n else None


def run_one(job):
    test, pak, path = job
    head, lines = read_route(path)
    gamedat = load_gamedat(head)
    import va98
    fonts = va98.Fonts(pak)
    fh = hashlib.sha256(fonts.raw['font16'] + fonts.raw['font8']).hexdigest()
    args = {'route': '\n'.join(lines), 'head': {k: head[k] for k in sorted(head)},
            'gamedat': None if gamedat is None else '%08x' % zlib.crc32(gamedat),
            'fonts': fh, 'version': 1}
    ref, hit = refcache.get('vm', ['check_vm.py'], None, args,
                            lambda: original(pak, head, lines, gamedat))
    got, rc, err = engine(test, pak, head, lines, gamedat)
    bad = compare(os.path.basename(path), ref, got)
    if bad is None and rc != 0:
        bad = 'the engine ended with %d: %s' % (rc, err.strip()[-400:])
    return os.path.basename(path), len(ref['lines']) - 1, ref['frames'], hit, bad


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    test, pak = argv[1], argv[2]
    paths = argv[3:] or sorted(os.path.join(ROUTES, f) for f in os.listdir(ROUTES)
                               if f.endswith('.route'))
    jobs = int(os.environ.get('CHECK_VM_JOBS') or os.cpu_count() or 1)
    # the longest first: they decide when the pool is done
    paths.sort(key=lambda p: -os.path.getsize(p))
    work = [(test, pak, p) for p in paths]
    res = []

    def report(r):
        name, n, f, hit, msg = r
        res.append(r)
        print('%s: %d waits, %d frames (%s): %s' % (name, n, f, 'stored' if hit else 'computed',
                                                    'identical' if not msg else msg),
              flush=True)
    if jobs > 1 and len(work) > 1:
        with multiprocessing.Pool(min(jobs, len(work))) as pool:
            for r in pool.imap_unordered(run_one, work):
                report(r)
    else:
        for w in work:
            report(run_one(w))
    bad = sum(1 for r in res if r[4])
    waits = sum(r[1] for r in res)
    frames = sum(r[2] for r in res)
    print('check_vm: %d routes, %d waits, %d frames of the original: %s' % (
        len(res), waits, frames, 'identical to the original at every wait' if not bad else
        '%d routes differ' % bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
