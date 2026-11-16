# SPDX-License-Identifier: GPL-3.0-or-later
"""refcache.py: the reference results of the emulator checks (check_gf, ...), kept between
runs.

The original program under emulation (re-tools/mcall.py) gives the same result for the same
inputs, and none of them is the engine: the code that computes it, the imported game's files,
the fonts (when a check uses them) and the call's arguments. A result is stored under a fingerprint of the first three
and a hash of the arguments, so a change to the engine reuses it and a change to any input is
a miss. Validity is decided by content only (never by file times), so it does not matter when
or how fast anything ran.

Entries are build/refcache/<kind>/<fingerprint>/<args hash>.pickle.gz (REFCACHE_DIR overrides
build/refcache). They are derived from the game and stay in build/. Only the current
fingerprint's directory of a kind is kept. Writes are atomic (a temporary file in the same
directory, then a rename), an entry that cannot be read is computed again.

REFCACHE selects the mode:
  on       (default) use a stored result, compute and store a missing one
  off      always compute, store nothing
  refresh  always compute, store the result
  verify   always compute; fail if a stored result differs (non-determinism, or an input the
           key misses), then store it
"""
import gzip
import hashlib
import os
import pickle
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
ORIG = os.path.join(ROOT, 'resources', 'original', 'pc98')
TOOLS = os.path.join(ROOT, 'source', 'tools')
RETOOLS = os.path.join(ROOT, 're-tools')
FORMAT = 1
MODES = ('on', 'off', 'refresh', 'verify')

_fingerprints = {}


class RefcacheError(Exception):
    """not SystemExit: raised in a multiprocessing worker, that would end the worker and leave
    the pool waiting for its result for ever; an Exception reaches the parent"""


def mode():
    m = os.environ.get('REFCACHE', 'on') or 'on'
    if m not in MODES:
        raise RefcacheError('refcache: REFCACHE=%s: not one of %s' % (m, ', '.join(MODES)))
    return m


def _files(h, top, names=None):
    """every file under top (or the given names in it), with its path relative to top"""
    paths = []
    for d, dirs, files in os.walk(top):
        dirs.sort()
        paths += [os.path.join(d, f) for f in files]
    for p in sorted(paths):
        rel = os.path.relpath(p, top)
        if names is not None and rel not in names:
            continue
        data = open(p, 'rb').read()
        h.update(b'%d:%s:%d:' % (len(rel.encode()), rel.encode(), len(data)))
        h.update(data)


def fingerprint(sources, fonts=None):
    """the code (re-tools, the decoders in source/tools, this module, the checker modules
    `sources`), unicorn and Python, the game's files and the fonts (None: the check draws no
    text); computed once per process"""
    k = (tuple(sources), os.path.abspath(fonts) if fonts else None)
    if k not in _fingerprints:
        if fonts is not None and not os.path.isfile(os.path.join(fonts, 'k16.xfnt')):
            # the harness would quietly draw stand-in glyphs: never a reference
            raise RefcacheError('refcache: no k16.xfnt in %s' % fonts)
        import unicorn
        h = hashlib.sha256(b'refcache %d\n' % FORMAT)
        h.update(('unicorn %s python %d.%d\n' % ((unicorn.__version__,) + sys.version_info[:2]))
                 .encode())
        _files(h, RETOOLS, {n for n in os.listdir(RETOOLS) if n.endswith('.py')})
        _files(h, TOOLS, {n for n in os.listdir(TOOLS) if n.endswith('.py')})
        _files(h, HERE, set(sources) | {'refcache.py'})
        _files(h, ORIG)
        if fonts is not None:
            _files(h, fonts)
        _fingerprints[k] = h.hexdigest()[:32]
    return _fingerprints[k]


def _canon(v):
    """a canonical text of the arguments: dicts (str keys, sorted), lists, str, int, bool, None.
    No tuples: emulated() tells a tuple from a list, so the caller encodes them itself."""
    if v is None or isinstance(v, bool):
        return repr(v)
    if isinstance(v, int):
        return 'i%d' % v
    if isinstance(v, str):
        return 's' + repr(v)
    if isinstance(v, list):
        return '[' + ','.join(_canon(x) for x in v) + ']'
    if isinstance(v, dict):
        if not all(isinstance(x, str) for x in v):
            raise TypeError('refcache: dict keys must be str')
        return '{' + ','.join('%r:%s' % (x, _canon(v[x])) for x in sorted(v)) + '}'
    raise TypeError('refcache: %s in the arguments' % type(v).__name__)


def _plain(v):
    if v is None or isinstance(v, (bool, int, float, str, bytes)):
        return True
    if isinstance(v, (list, tuple)):
        return all(_plain(x) for x in v)
    if isinstance(v, dict):
        return all(isinstance(x, str) and _plain(y) for x, y in v.items())
    return False


def _load(path):
    with gzip.open(path, 'rb') as f:
        return pickle.load(f)


def _store(d, path, value):
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as f:
            pickle.dump(value, f, protocol=4)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def get(kind, sources, fonts, args, compute):
    # fonts: the fonts directory, or None for a check that draws no text
    """compute() for these arguments, or its stored result. Returns (result, 1 if stored)."""
    m = mode()
    if m == 'off':
        return compute(), 0
    top = os.path.join(os.environ.get('REFCACHE_DIR') or os.path.join(ROOT, 'build', 'refcache'),
                       kind)
    fp = fingerprint(sources, fonts)
    d = os.path.join(top, fp)
    path = os.path.join(d, hashlib.sha256(_canon(args).encode()).hexdigest()[:32] + '.pickle.gz')
    stored = None
    if m in ('on', 'verify') and os.path.exists(path):
        try:
            stored = _load(path)
        except (OSError, EOFError, pickle.UnpicklingError, ValueError) as e:
            print('refcache: %s unreadable (%s): computed again' % (path, e), file=sys.stderr)
    if m == 'on' and stored is not None:
        return stored, 1
    value = compute()
    if not _plain(value):
        raise TypeError('refcache: %s result is not plain data' % kind)
    if m == 'verify' and stored is not None and stored != value:
        raise RefcacheError('refcache: verify: the stored %s result %s differs from the one '
                         'computed now' % (kind, path))
    try:
        _store(d, path, value)
        # only the current fingerprint is kept (another one is code or data since changed)
        for other in os.listdir(top):
            if other != fp:
                shutil.rmtree(os.path.join(top, other), ignore_errors=True)
    except OSError as e:                # a run of other code removed the directory meanwhile
        print('refcache: %s not stored (%s)' % (path, e), file=sys.stderr)
    return value, 0
