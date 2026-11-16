# SPDX-License-Identifier: GPL-3.0-or-later
"""The games the vangel tools know: everything that is a fact about one game and not about the
engine. The engine itself (source/engine) names no game; it reads the profile mkpack.py writes
from this table into the pack (engine/game/profile.c has the keys).

Per game:
  profile     the pack's "profile" entry: id (the pack's and the save directory's name), title,
              lang (the language of the original text), the scenario and picture library the
              original's command line names (GAME.BAT: m cmd00.scb b:\\gdata.lib), the sound
              setup, the mouse question, and cpu_per_frame (the reference machine's speed in
              instructions per VSYNC, the time base of the transitions that run at CPU speed)
  languages   {tag: name} of the languages the original has
  release     the inventory's release of the game; `optional` the other releases, which only
              extras and the research use
  engine      the original engine M.EXE: the md5 of the file and of its EXEPACK-unpacked image
              (resources/derived/M_unpacked.EXE, which the research tools and the pack read)
  counts      how many files of each kind the pack must end up with
"""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
ORIG = os.path.join(ROOT, 'resources', 'original')
DERIVED = os.path.join(ROOT, 'resources', 'derived')
INVENTORY = os.path.join(ROOT, 'resources', 'inventory.tsv')

GAMES = {
    'virginangel': {
        'profile': {
            'id': 'virginangel',
            'title': 'Virgin Angel',
            'lang': 'ja',
            'scenario': 'CMD00.SCB',
            'library': 'GDATA.LIB',
            'sound': 'pmd26k',
            'mouse': 'ask',
            # not yet measured: set in M1 from the instruction counts of the effect loops
            # (docs/engine-plan.md, decisions)
            'cpu_per_frame': 0,
        },
        'languages': {'ja': '日本語'},
        'release': 'pc98',
        'optional': ('x68k', 'ibm'),
        'engine': {
            'name': 'M.EXE',
            'md5': '8b7a109562baa02175d1057b50e9d845',
            'unpacked_md5': '7fa44410603292af65d116ca366856a9',
            'unpacked': os.path.join(DERIVED, 'M_unpacked.EXE'),
        },
        'counts': {'scenario': 1, 'text': 1, 'library': 1, 'song': 21},
    },
}
DEFAULT = 'virginangel'

LANG_NAMES = {'ja': '日本語', 'en': 'English', 'pl': 'Polski'}
UNCHECKED = "previous owner's state"
