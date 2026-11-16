# SPDX-License-Identifier: GPL-3.0-or-later
"""Puts the lrvne tools (the submodule source/lrvne) on the module path: `import lrvnepath`
before `from lrvne import ...`. The tools run with `python3 -I`, which reads no PYTHONPATH."""
import os
import sys

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lrvne', 'tools')
if not os.path.isdir(os.path.join(TOOLS, 'lrvne')):
    sys.exit('the lrvne submodule is missing (source/lrvne): git submodule update --init')
sys.path.insert(0, os.path.normpath(TOOLS))
