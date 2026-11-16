#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Print runs of printable ASCII/Shift-JIS text with their offsets. Usage: sjstrings.py FILE [MINLEN]"""
import sys
b = open(sys.argv[1], 'rb').read(); mn = int(sys.argv[2]) if len(sys.argv) > 2 else 6
i = 0; start = None; out = bytearray()
def flush(end):
    global out, start
    if start is not None and len(out) >= mn:
        print('%06x %s' % (start, out.decode('cp932', 'replace')))
    out = bytearray(); start = None
while i < len(b):
    c = b[i]
    if (0x81 <= c <= 0x9f or 0xe0 <= c <= 0xfc) and i+1 < len(b) and 0x40 <= b[i+1] <= 0xfc and b[i+1] != 0x7f:
        if start is None: start = i
        out += b[i:i+2]; i += 2; continue
    if 0x20 <= c < 0x7f or 0xa1 <= c <= 0xdf:
        if start is None: start = i
        out.append(c); i += 1; continue
    flush(i); i += 1
flush(i)
