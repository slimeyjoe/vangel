#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""check_pmd.py - lrvne's PMD module against the real PMD.COM on the game's songs.

usage: check_pmd.py LRV_TEST_PMD PACK               (with $EMU_PYTHON: unicorn)

Each of the release's songs runs on the real driver under emulation (re-tools/pmd_capture.py:
PMD.COM 4.7g on a 26K with GAME.BAT's options for it, which the profile's pmd= gives the
engine) for 30 000 timer interrupts; the last ones with the calls the music layer makes, a
fade-volume ramp (INT 60h AH=19h, as statement 1Ch and the music mode step it) and a stop
(AH=01h). The log, every register write at its master clock and the driver's status after
every interrupt, is replayed by lrvne's test_pmd (lrvne/tests/test_pmd.c, built here as
lrv_test_pmd) on the song and the SSG-effect table as the pack holds them: they must be the
same. The real driver's logs are kept by refcache.py.
"""
import multiprocessing
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 're-tools'))
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import refcache  # noqa: E402
import vgpak     # noqa: E402
from lrvne import xpak  # noqa: E402

PC98 = os.path.join(ROOT, 'resources', 'original', 'pc98')
OPTS = '/DF5 /K /M8 /V0 /E0'            # GAME.BAT, a 26K (docs/re/sound.md §2.2)
IRQS = 30000


def events():
    """the fade ramp: AH=19h from 00h to FFh in steps of 5, every 100 interrupts from 24 000,
    then a stop"""
    ev = ['%d:19%02X' % (24000 + 100 * k, min(255, 5 * k)) for k in range(52)]
    return ev + ['29500:0100']


def capture(song):
    import pmd_capture
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'log')
        argv = [os.path.join(PC98, song), '-o', out, '--pmd', os.path.join(PC98, 'PMD.COM'),
                '--opts', OPTS, '--irqs', str(IRQS)]
        for e in events():
            argv += ['--event', e]
        pmd_capture.main(argv)
        return open(out).read()


def one(job):
    song, test, pack_song, ssgtab = job
    log, hit = refcache.get('pmd', ['check_pmd.py'], None,
                            {'song': song, 'opts': OPTS, 'irqs': IRQS, 'events': events()},
                            lambda: capture(song))
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, data in (('log', log.encode()), ('song', pack_song), ('ssg', ssgtab)):
            p = os.path.join(tmp, name)
            with open(p, 'wb') as f:
                f.write(data)
            paths.append(p)
        res = subprocess.run([test] + paths, capture_output=True, text=True, check=False)
    return song, res.returncode, (res.stdout + res.stderr).strip(), hit


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    pack = xpak.read_pack(open(argv[2], 'rb').read())
    ssg = pack.find('ssgtab', xpak.T_BLOB)
    if not ssg:
        sys.exit('check_pmd: the pack has no ssgtab')
    songs = sorted(f for f in os.listdir(PC98) if f.startswith('VA_M') and f[-2:] in ('.M', '.N'))
    jobs = []
    for s in songs:
        e = pack.find(s, vgpak.T_SONG)
        if not e:
            sys.exit('check_pmd: the pack has no song %s' % s)
        if e.data != open(os.path.join(PC98, s), 'rb').read():
            sys.exit('check_pmd: the pack\'s %s is not the release\'s' % s)
        jobs.append((s, argv[1], e.data, ssg.data))
    with multiprocessing.Pool(min(len(jobs), os.cpu_count() or 1)) as pool:
        results = pool.map(one, jobs)
    bad = 0
    for song, rc, out, hit in results:
        if rc != 0:
            bad += 1
            print('%s: %s' % (song, out[-1500:]))
    print('check_pmd: %d songs x %d interrupts (with a fade ramp and a stop): %s '
          '(reference %s)' % (len(results), IRQS,
                              'the same as the real driver' if not bad else
                              '%d differ' % bad,
                              'stored' if all(r[3] for r in results) else 'computed'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
