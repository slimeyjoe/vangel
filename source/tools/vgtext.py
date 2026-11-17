# SPDX-License-Identifier: GPL-3.0-or-later
"""The game's translatable text, its keys, the translation files and the pack's string table
(docs/translation.md has the whole scheme; the engine's side is engine/text/lang.c).

Keys (stable: they name the original text, which never changes):
  m<NNN>.<L>         text   a passage of message NNN (statement 19h's operand, 001-213): the
                            run of non-empty text lines from line L (0-based, the message's
                            lines as txb.py splits them), up to a control line (12h 13h 14h
                            1Ah), an empty line, or the line that closes a speech; speech is
                            stored without its speaker and brackets
  name.<NN>          name   a speaker's name (the rest of a 13h line), numbered in order of
                            first appearance; in the pack it is keyed by its bytes ("n." and
                            their hex), so the engine needs no list of the names
  quote.open/close   fmt    what is put after a speaker's name and after a speech: 「 」
  menu<MM>.<c>       menu   choice c (1-4) of menu MM (statement 24h's operand, 01-43)
  bi.prologue.<p>    bi     page p (0-3) of the prologue (built-in 1)
  bi.staff.<p>       bi     page p (0-10) of the staff roll (built-ins 2 and 5), four lines
  bi.music.heading / bi.music.help / bi.music.<n>
                     bi     the music mode's heading, its help line, song n's title (0-17)
  bi.announce.missing / .prompt / .last
                     bi     the notice's "file not found", its prompt after a page and at
                            the end
  announce.<p>       announce  page p of ANNOUNCE.TXT as the notice shows it
  con.ask / con.yes / con.no / con.loading
                     con    the DOS console's mouse question, its answers, "loading"

A translation file is UTF-8 TSV with a header line naming its columns: `key`, `text` and
optionally `kind` (checked when given); other columns are the translator's. `text` empty = not
translated (the original is shown). Escapes in `text`: \\n a line break, \\p a page break,
\\\\ a backslash. Lines starting with # are comments.

The pack's string table (LRV_PT_STRINGS "text", one per language): "VGTX", u16 version 1, u16
0, u32 count, count x {u32 key offset, u32 text offset} sorted by key (bytes), then the keys
and texts, NUL-terminated (offsets from the table's start). Every name and both quotes are in
it (the original's when untranslated), so a translated passage always has its speaker.
"""
import os
import struct
from collections import OrderedDict, namedtuple

import txb as txbmod

KINDS = ('text', 'name', 'fmt', 'menu', 'bi', 'announce', 'con')
QUOTE_OPEN, QUOTE_CLOSE = b'\x81\x75', b'\x81\x76'       # 「 」 DS:00E6, DS:00EF

# the DOS console's strings (engine/game/console.c; DS:01E4, 0203, 021A, 0233), as shown
CONSOLE = OrderedDict([
    ('con.ask', b'\x83\x7d\x83\x45\x83\x58\x82\xf0\x8e\x67\x97\x70\x82\xb5\x82\xdc\x82\xb7\x82\xa9'
                b'?[Y/N]'),
    ('con.yes', b'\x83\x7d\x83\x45\x83\x58\x82\xf0\x8e\x67\x97\x70\x82\xb5\x82\xdc\x82\xb7'),
    ('con.no', b'\x83\x7d\x83\x45\x83\x58\x82\xf0\x8e\x67\x97\x70\x82\xb5\x82\xdc\x82\xb9\x82\xf1'),
    ('con.loading', b'\x83\x76\x83\x8d\x83\x4f\x83\x89\x83\x80\x82\xcc\x83\x8d\x81\x5b\x83\x68'
                    b'\x92\x86\x82\xc5\x82\xb7...'),
])

# the layouts (docs/translation.md): columns, lines a page, the last line's columns
WIN_W, WIN_H, WIN_LAST = 68, 4, 66          # the message window; the icon cell ends row 3
MENU_W = 68
PROLOGUE_W, PROLOGUE_H = 72, 8
STAFF_W, STAFF_H = 32, 4
ANNOUNCE_W, ANNOUNCE_H = 80, 23
MUSIC_COL = {'heading': 21, 'help': 3, 'title': 20}

S = namedtuple('S', 'kind ja info')         # a string of the game: kind, original (cp932), info


# ---- the message file ----------------------------------------------------------------------

def message_lines(msg, dic):
    """the lines msg_show reads (txb_line with its limit of 79), the final 1Ah one included"""
    return [txbmod.decode_line(ln, dic, txbmod.LINE_LIMIT)
            for ln in (msg.raw + b'\x1a').split(b'\x00')]


def is_text(line):
    """a line a passage is made of: not empty, not a control line (nor 10h/11h's)"""
    return bool(line) and line[0] not in (0x10, 0x11, 0x12, 0x13, 0x14, 0x1A)


def closes(line):
    """the line closes a speech: its first \\e is its last two bytes (msg_show's strstr)"""
    k = line.find(b'\\e')
    return k >= 0 and k == len(line) - 2


Unit = namedtuple('Unit', 'line lines speech closes name')


def units(lines):
    """the passages of a message's lines: Unit(first line, its lines, in speech, closes the
    speech, the speaker's name bytes or None)"""
    out, dlg, name, i = [], 0, None, 0
    while i < len(lines):
        ln = lines[i]
        if ln[:1] == b'\x13':
            dlg, name = 1, ln[1:]
        if not is_text(ln):
            i += 1
            continue
        start, speech, j = i, dlg, i
        while True:
            cl = dlg and closes(lines[j])
            if cl:
                dlg = 0
            j += 1
            if cl or j >= len(lines) or not is_text(lines[j]):
                break
        out.append(Unit(start, lines[start:j], bool(speech), bool(speech and not dlg),
                        name if speech else None))
        i = j
    return out


def unit_ja(u):
    """the passage's original as a translation would hold it: lines joined by \\n, the
    closing \\e left out"""
    ls = list(u.lines)
    if u.closes:
        ls[-1] = ls[-1][:-2]
    return b'\n'.join(ls)


def name_key_pack(name):
    return 'n.' + name.hex().upper()


# ---- the built-ins -------------------------------------------------------------------------

def _strs(d):
    p, out = 0, []
    while p < len(d):
        n = struct.unpack_from('<H', d, p)[0]
        p += 2
        if n == 0xFFFF:
            out.append(None)
            continue
        out.append(d[p:p + n])
        p += n
    return out


def prologue_pages(blob):
    """the prologue's pages: [[line, ...], ...] (the rows of a page are 0, 1, ... in order)"""
    pages, cur, p = [], [], 0
    while p < len(blob):
        row = struct.unpack_from('<h', blob, p)[0]
        n = struct.unpack_from('<H', blob, p + 2)[0]
        p += 4
        if n == 0xFFFF:
            pages.append(cur)
            cur = []
            if row < 0:
                break
            continue
        cur.append(blob[p:p + n])
        p += n
    return pages


def staff_pages(blob):
    lines = [s for s in _strs(blob) if s is not None]
    return [lines[i:i + 4] for i in range(0, len(lines), 4)]


def music(blob):
    """the music mode's song titles"""
    s = _strs(blob)
    return [s[i + 1] for i in range(0, len(s) - 1, 2) if s[i] is not None]


def announce_pages(data):
    """the notice's pages as built-in 3 shows them (engine/bi/announce.c): [(lines, last)]:
    text mode (CR LF -> LF, ^Z ends), fgets of 82 bytes with the last one cut, #p ends a page,
    #e the file, 23 lines a page; the final page (possibly empty) ends with the last prompt"""
    text = data.split(b'\x1a', 1)[0].replace(b'\r\n', b'\n')
    pages, cur, p = [], [], 0
    while p < len(text):
        e = text.find(b'\n', p, p + 82)
        q = e + 1 if e >= 0 else min(p + 82, len(text))
        ln, p = text[p:q], q
        if ln[:2] == b'#e':
            break
        if ln[:2] == b'#p':
            pages.append((cur, False))
            cur = []
            continue
        cur.append(ln[:-1])
        if len(cur) == 23:
            pages.append((cur, False))
            cur = []
    pages.append((cur, True))
    return pages


# ---- every string ---------------------------------------------------------------------------

def game_strings(get):
    """OrderedDict key -> S(kind, original bytes, info) of every translatable string; get(name)
    returns the bytes of a pack entry (CMD00.TXB, CMD00.SCB, txbdict, bi.*, ANNOUNCE.TXT) or
    None"""
    import scb as scbmod
    out = OrderedDict()
    d = get('txbdict')
    dic = [d[2 * i:2 * i + 2] for i in range(len(d) // 2)]
    t = txbmod.Txb(get('CMD00.TXB'), dic)
    names = OrderedDict()
    for m in t.messages:
        for u in units(message_lines(m, dic)):
            out['m%03d.%d' % (m.index, u.line)] = S('text', unit_ja(u), dict(
                msg=m.index, line=u.line, speech=u.speech, closes=u.closes, name=u.name,
                rows=len(u.lines)))
        for ln in message_lines(m, dic):
            if ln[:1] == b'\x13':
                names.setdefault(ln[1:], len(names))
    for name, i in names.items():
        out['name.%02d' % i] = S('name', name, dict(pack=name_key_pack(name)))
    out['quote.open'] = S('fmt', QUOTE_OPEN, {})
    out['quote.close'] = S('fmt', QUOTE_CLOSE, {})
    sc = scbmod.Scenario(get('CMD00.SCB'))
    for mi, (_ln, items) in enumerate(sc.t44, 1):
        for c, s in enumerate(items, 1):
            out['menu%02d.%d' % (mi, c)] = S('menu', s, dict(menu=mi, choice=c))
    for p, lines in enumerate(prologue_pages(get('bi.prologue'))):
        out['bi.prologue.%d' % p] = S('bi', b'\n'.join(lines), dict(rows=len(lines)))
    for p, lines in enumerate(staff_pages(get('bi.staff'))):
        out['bi.staff.%d' % p] = S('bi', b'\n'.join(lines), dict(rows=len(lines)))
    bs = _strs(get('bi.strings'))
    out['bi.music.heading'] = S('bi', bs[4], {})
    out['bi.music.help'] = S('bi', bs[5], {})
    for n, title in enumerate(music(get('bi.music'))):
        out['bi.music.%d' % n] = S('bi', title, {})
    out['bi.announce.missing'] = S('bi', bs[1], {})
    out['bi.announce.prompt'] = S('bi', bs[2], {})
    out['bi.announce.last'] = S('bi', bs[3], {})
    ann = get('ANNOUNCE.TXT')
    if ann is not None:
        for p, (lines, _last) in enumerate(announce_pages(ann)):
            out['announce.%d' % p] = S('announce', b'\n'.join(lines), dict(rows=len(lines)))
    for k, s in CONSOLE.items():
        out[k] = S('con', s, {})
    return out


def pack_getter(pack):
    """get() for game_strings over an lrvne xpak.Pack"""
    def get(name):
        e = pack.find(name)
        return e.data if e is not None else None
    return get


def ja_text(b):
    """an original as text (Shift-JIS), for the template and the checks"""
    return b.decode('cp932', 'backslashreplace')


# ---- translation files ----------------------------------------------------------------------

def unescape(s):
    """the text of a `text` cell: \\n, \\p, \\\\ (ValueError on another escape)"""
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == '\\':
            if i + 1 >= len(s):
                raise ValueError('a lone backslash at the end')
            e = s[i + 1]
            if e == 'n':
                out.append('\n')
            elif e == 'p':
                out.append('\f')
            elif e == '\\':
                out.append('\\')
            else:
                raise ValueError('unknown escape \\%s' % e)
            i += 2
            continue
        if ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0:
            raise ValueError('control character U+%04X' % ord(c))
        out.append(c)
        i += 1
    return ''.join(out)


def escape(s):
    return s.replace('\\', '\\\\').replace('\n', '\\n').replace('\f', '\\p')


def read_tsv(path):
    """(header columns, rows as dicts, problems) of a TSV file"""
    rows, problems, head = [], [], None
    with open(path, encoding='utf-8') as f:
        for no, ln in enumerate(f, 1):
            ln = ln.rstrip('\n').rstrip('\r')
            if not ln or ln.startswith('#'):
                continue
            cells = ln.split('\t')
            if head is None:
                head = cells
                continue
            if len(cells) > len(head):
                problems.append('%s:%d: %d cells, the header has %d' % (path, no, len(cells),
                                                                        len(head)))
                continue
            cells += [''] * (len(head) - len(cells))
            r = dict(zip(head, cells))
            r['_line'] = no
            rows.append(r)
    if head is None or 'key' not in head or 'text' not in head:
        problems.append('%s: the header must name the columns key and text' % path)
    return head or [], rows, problems


def load(path, strings=None):
    """the translations of a file: ({key: text (str)}, problems); with strings
    (game_strings) the keys and kinds are checked"""
    _head, rows, problems = read_tsv(path)
    out = {}
    for r in rows:
        k, t = r.get('key', ''), r.get('text', '')
        where = '%s:%d: %s' % (path, r['_line'], k)
        if strings is not None:
            if k not in strings:
                problems.append('%s: not a key of the game' % where)
                continue
            if r.get('kind') and r['kind'] != strings[k].kind:
                problems.append('%s: kind %s, the key\'s is %s' % (where, r['kind'],
                                                                   strings[k].kind))
        if k in out:
            problems.append('%s: given twice' % where)
            continue
        if not t:
            continue
        try:
            out[k] = unescape(t)
        except ValueError as e:
            problems.append('%s: %s' % (where, e))
    return out, problems


def write_tsv(path, head, rows):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\t'.join(head) + '\n')
        for r in rows:
            f.write('\t'.join(str(r.get(h, '')) for h in head) + '\n')


# ---- the pack's table -----------------------------------------------------------------------

def pack_entries(strings, tl):
    """{pack key: UTF-8 bytes} of a language: the translations, and every name and quote
    (the original's when untranslated)"""
    out = {}
    for k, s in strings.items():
        if s.kind in ('name', 'fmt'):
            t = tl.get(k) or ja_text(s.ja)
            out[s.info['pack'] if s.kind == 'name' else k] = t.encode('utf-8')
        elif k in tl:
            out[k] = tl[k].encode('utf-8')
    return out


def table_bytes(entries):
    """the VGTX table of {key (str): text (bytes)}"""
    keys = sorted(entries, key=lambda k: k.encode('ascii'))
    head = b'VGTX' + struct.pack('<HHI', 1, 0, len(keys))
    data = bytearray()
    base = len(head) + 8 * len(keys)
    index = bytearray()
    for k in keys:
        ko = base + len(data)
        data += k.encode('ascii') + b'\0'
        to = base + len(data)
        data += entries[k] + b'\0'
        index += struct.pack('<II', ko, to)
    return head + bytes(index) + bytes(data)


def read_table(data):
    """{key: text bytes} of a VGTX table"""
    if data[:4] != b'VGTX' or struct.unpack_from('<H', data, 4)[0] != 1:
        raise ValueError('not a VGTX table')
    n = struct.unpack_from('<I', data, 8)[0]
    out = {}
    for i in range(n):
        ko, to = struct.unpack_from('<II', data, 12 + 8 * i)
        k = data[ko:data.index(b'\0', ko)].decode('ascii')
        out[k] = data[to:data.index(b'\0', to)]
    return out
