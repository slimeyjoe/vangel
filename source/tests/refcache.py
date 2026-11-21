# SPDX-License-Identifier: GPL-3.0-or-later
"""refcache.py: the reference results of the emulator checks (check_gf, ...), kept between
runs: lrvne's refcache (source/lrvne/tools/lrvne/refcache.py) with what this engine's
references depend on.

The original program under emulation (re-tools/mcall.py) gives the same result for the same
inputs, and none of them is the engine: the code that computes it, the imported game's files,
the fonts (when a check uses them), the emulator and the call's arguments. lrvne keys a result
on the modules of this repository the check had loaded when it computed it (so an edit of a
tool no reference uses, e.g. the translation tools, keeps the results), on `sources` (the
checker modules, named by the check), on the game's files and the fonts, and on unicorn's
version.

Entries are build/refcache/<kind>/... (REFCACHE_DIR overrides build/refcache). They are
derived from the game and stay in build/. REFCACHE selects the mode: on (default), off,
refresh, verify (lrvne's refcache says what they do).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
ORIG = os.path.join(ROOT, 'resources', 'original', 'pc98')
sys.path.insert(0, os.path.join(ROOT, 'source', 'tools'))
import lrvnepath  # noqa: E402,F401
from lrvne import refcache as _lrc  # noqa: E402

RefcacheError = _lrc.RefcacheError
_cache = None


def cache():
    global _cache
    if _cache is None:
        import unicorn
        _cache = _lrc.Cache(os.environ.get('REFCACHE_DIR') or os.path.join(ROOT, 'build', 'refcache'),
                            code_roots=[ROOT], data=[ORIG],
                            salt='unicorn %s' % unicorn.__version__)
    return _cache


def mode():
    return cache().mode()


def get(kind, sources, fonts, args, compute):
    """compute() for these arguments, or its stored result: (result, 1 if stored). sources: the
    checker modules (in tests/) the result depends on; fonts: the fonts directory, or None for a
    check that draws no text."""
    if fonts is not None and not os.path.isfile(os.path.join(fonts, 'k16.xfnt')):
        # the harness would quietly draw stand-in glyphs: never a reference
        raise RefcacheError('refcache: no k16.xfnt in %s' % fonts)
    value, hit = cache().get(kind, args, compute,
                             code_files=[os.path.join(HERE, s) for s in sources],
                             data=[fonts] if fonts is not None else [])
    return value, int(hit)
