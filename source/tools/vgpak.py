# SPDX-License-Identifier: GPL-3.0-or-later
"""What a vangel pack holds beyond lrvne's own entries (lrvne's xpak module is the pack format):
the engine's entry types. engine/vg.h has the same numbers.

  SCENARIO  the compiled scenario (CMD00.SCB, "CRSC"), byte-exact, under its file name
  TEXT      the message file (CMD00.TXB, "CRTX"), byte-exact
  LIBRARY   the picture library (GDATA.LIB, "GA00"), byte-exact
  SONG      a PMD song (VA_Mnn.M / .N), byte-exact, under its file name
  FILE      another file the engine reads as the original does (ANNOUNCE.TXT)
Data taken out of the original programs at pack time is lrvne's type BLOB: "ssgtab" (PMD.COM's
SSG effects, lrvne pmd), "txbdict" (M.EXE's 90-character text dictionary).
"""
import lrvnepath  # noqa: F401
from lrvne import xpak

T_SCENARIO, T_TEXT, T_LIBRARY, T_SONG, T_FILE = range(xpak.T_ENGINE, xpak.T_ENGINE + 5)
TYPES = xpak.TypeRegistry({T_SCENARIO: 'scenario', T_TEXT: 'text', T_LIBRARY: 'library',
                           T_SONG: 'song', T_FILE: 'file'})


def read(path):
    """the pack in the file `path` (an lrvne xpak.Pack)"""
    with open(path, 'rb') as f:
        return xpak.read_pack(f.read())
