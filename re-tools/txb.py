#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""txb.py - decoder for Virgin Angel's message file CMD00.TXB ("CRTX"), stdlib only.

Format (M.EXE txb_load 0724:0018, txb_read_msg 0724:0186, txb_line 0724:0206; docs/re/text.md):
  "CRTX" (plain), then every byte is stored inverted (b' = b ^ 0FFh).
  The decoded stream is N messages, each terminated by 1Ah (N = SCB section tag 7).
  A message is a sequence of lines, each terminated by 00h; the last "line" is the single
  byte 1Ah.  Inside a line the byte coding is:
     81-9F, E0-FC   Shift-JIS lead byte: it and the next byte are copied unchanged
     A0-DF          dictionary: 2-byte SJIS character DICT[b - 0A0h]       (64 entries)
     41-5A ('A'-'Z') dictionary: 2-byte SJIS character DICT[64 + b - 41h]  (26 entries)
     anything else  copied as one byte (ASCII, control codes)
  DICT is the 90-character table at 0B85:0000 of the unpacked M.EXE (image offset 0B850h).
  The display routine reads at most 79 output bytes of a line (longer lines are cut).
  Control codes (first byte of a line, see 0315:07FC): 10h/11h ignored, 12h end page and wait
  for a key, 13h speaker name (rest of line), 14h end page and wait a time, 1Ah end of message.

Usage:  txb.py CMD00.TXB [--exe M_unpacked.EXE] [--tsv OUT.tsv] [--raw N]
As a module: Txb(data, dict_bytes).messages -> [Message(index, offset, length, raw, lines)]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'resources/derived/M_unpacked.EXE')
DICT_OFF = 0xB850          # 0B85:0000 relative to the start of the load image
DICT_LEN = 90


def load_dict(exe=EXE):
    d = open(exe, 'rb').read()
    hdr = int.from_bytes(d[8:10], 'little') * 16          # MZ header paragraphs
    t = d[hdr + DICT_OFF:hdr + DICT_OFF + 2 * DICT_LEN]
    return [t[2 * i:2 * i + 2] for i in range(DICT_LEN)]


def is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def decode_line(src, dic, limit=None):
    """Expand one coded line (bytes without its 00h). limit = max output bytes (79 in the
    message routine); the original stops once the output count reaches it."""
    out = bytearray()
    lead = False
    for b in src:
        if limit is not None and len(out) >= limit:
            break
        if lead:
            out.append(b)
            lead = False
        elif is_lead(b):
            out.append(b)
            lead = True
        elif 0xA0 <= b <= 0xDF:
            out += dic[b - 0xA0]
        elif 0x41 <= b <= 0x5A:
            out += dic[64 + b - 0x41]
        else:
            out.append(b)
    return bytes(out)


class Message:
    def __init__(self, index, offset, raw, dic):
        self.index, self.offset, self.raw, self.dic = index, offset, raw, dic
        self.length = len(raw) + 1          # as stored by txb_load: bytes incl. the 1Ah
        self.lines = [decode_line(l, dic) for l in raw.split(b'\x00')]

    def text(self):
        """Visible form: line ends as {n}, control bytes < 20h as {XX}."""
        parts = []
        for l in self.lines:
            s = ''
            i = 0
            while i < len(l):
                b = l[i]
                if b < 0x20:
                    s += '{%02X}' % b
                    i += 1
                elif is_lead(b) and i + 1 < len(l):
                    s += l[i:i + 2].decode('cp932', 'backslashreplace')
                    i += 2
                else:
                    s += chr(b) if b < 0x80 else '{%02X}' % b
                    i += 1
            parts.append(s)
        return '{n}'.join(parts)


QUOTE_OPEN = b'\x81\x75'     # DS:00E6
SPACE = b'\x81\x40'          # DS:00E9
QUOTE_CLOSE = b'\x81\x76'    # DS:00EF/00F3
LINE_LIMIT = 79               # 0315:082E: max output bytes per decoded line
ROWS = 4


def layout(msg, dic=None):  # noqa: C901
    """Model of the message routine 0315:07FC: split a Message into pages.
    Returns [(rows, wait, nbytes)] with rows = [(row, bytes)] (rows passed to the line drawer
    02BE:015F; empty rows are counted but not drawn), wait = 'key' or 'timed' (code 14h; the
    original waits max(150, nbytes*100//12) ms), nbytes = sum of the row lengths."""
    dic = dic or msg.dic
    lines = [decode_line(l, dic, LINE_LIMIT) for l in (msg.raw + b'\x1a').split(b'\x00')]
    pages = []
    dlg = first = mode = end = 0
    name = b''
    nlen = 0
    it = iter(lines)
    while not end:
        rows = []
        row = drawn = nbytes = 0
        while row < ROWS:
            line = next(it)
            c = line[0] if line else 0
            if 0x10 <= c <= 0x1A and c not in (0x15, 0x16, 0x17, 0x18, 0x19):
                if c in (0x10, 0x11):
                    line = line[1:]
                elif c == 0x12:
                    row, first, mode = ROWS, 0, 0
                    continue
                elif c == 0x13:
                    name = line[1:]
                    nlen = len(name) // 2 + 1
                    first, dlg = 0, 1
                    continue
                elif c == 0x14:
                    # 0315:090A: unlike 12h this falls through into the text path with the
                    # rest of the line (normally empty) as row 4: the line drawer refuses
                    # row > 3, but the row still counts as shown (the page is shown and
                    # waited for even if nothing new is on it), its length counts for the
                    # wait time, and in a speech block it consumes the name prefix.
                    row, first, mode = ROWS, 0, 1
                    line = line[1:]
                else:                       # 1Ah
                    row, end = ROWS, 1
                    continue
            if dlg:
                if not first:
                    s = name + QUOTE_OPEN + line
                    first = 1
                else:
                    s = SPACE * nlen + line
                k = s.find(b'\\e')
                if k >= 0 and len(s) - k == 2:
                    s = s[:k] + QUOTE_CLOSE
                    dlg = 0
            else:
                s = line
            if s and row < ROWS:
                rows.append((row, s))
            row += 1
            drawn += 1
            nbytes += len(s)
        if drawn:
            pages.append((rows, 'timed' if mode else 'key', nbytes))
    return pages


class Txb:
    def __init__(self, data, dic=None):
        if data[:4] != b'CRTX':
            raise ValueError('not a CRTX file')
        self.dic = dic or load_dict()
        body = bytes(b ^ 0xFF for b in data[4:])
        self.messages = []
        pos = 0
        n = 1
        while pos < len(body):
            end = body.find(b'\x1a', pos)
            if end < 0:
                self.trailer = body[pos:]
                break
            self.messages.append(Message(n, pos + 4, body[pos:end], self.dic))
            pos = end + 1
            n += 1
        else:
            self.trailer = b''


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('txb')
    ap.add_argument('--exe', default=EXE)
    ap.add_argument('--tsv')
    ap.add_argument('--raw', type=int, help='hex dump of the decoded lines of message N')
    a = ap.parse_args(argv)
    t = Txb(open(a.txb, 'rb').read(), load_dict(a.exe))
    if a.raw:
        m = t.messages[a.raw - 1]
        for l in m.lines:
            print(l.hex(' '))
        return
    if a.tsv:
        with open(a.tsv, 'w', encoding='utf-8') as f:
            f.write('index\toffset\tlength\ttext\n')
            for m in t.messages:
                f.write('%d\t0x%05X\t%d\t%s\n' % (m.index, m.offset, m.length, m.text()))
    long = sum(1 for m in t.messages for l in m.lines if len(l) > 79)
    print('%d messages, trailer %d bytes, decoded lines longer than 79 bytes: %d'
          % (len(t.messages), len(t.trailer), long))


if __name__ == '__main__':
    main(sys.argv[1:])
