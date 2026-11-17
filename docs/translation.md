# Translating Virgin Angel for vangel

How translated text gets into the engine (milestone M7). The engine executes the original
scenario byte for byte; a translation only replaces what is printed. No statement, message or
menu of the game is rewritten, so a translation cannot change the game's logic: the tests play
every route with a translation and check that the game meets every menu in the same state as
in Japanese.

The translations themselves are ours, made from the Japanese: Polish first, then English (M8,
M9; `docs/engine-plan.md`).

## The keys

A key names a piece of the original text. The original never changes, so neither do the keys.

| Key | Kind | What |
|---|---|---|
| `m<NNN>.<L>` | `text` | a passage of message NNN (statement 19h's operand, `001`–`213`) starting at its line L (0-based, the lines as `tools/txb.py` splits a message) |
| `name.<NN>` | `name` | a speaker's name (the rest of a 13h line), numbered by first appearance: 18, misspellings and padding variants included |
| `quote.open`, `quote.close` | `fmt` | what follows a speaker's name and what ends a speech: 「 and 」 in the original |
| `menu<MM>.<c>` | `menu` | choice c (1–4) of menu MM (statement 24h's operand, `01`–`43`) |
| `bi.prologue.<p>` | `bi` | page p (0–3) of the prologue (built-in 1) |
| `bi.staff.<p>` | `bi` | page p (0–10) of the staff roll (built-ins 2 and 5): four lines |
| `bi.music.heading`, `bi.music.help`, `bi.music.<n>` | `bi` | the music mode's heading, its help line, song n's title (0–17) |
| `bi.announce.missing`, `.prompt`, `.last` | `bi` | the notice's "file not found" line, its prompt after a page and at the end |
| `announce.<p>` | `announce` | page p of `ANNOUNCE.TXT` as the notice shows it |
| `con.ask`, `con.yes`, `con.no`, `con.loading` | `con` | the DOS console's mouse question, its two answers, "loading" |

**A passage** is a run of non-empty text lines. It ends at a control line (12h, 13h, 14h, 1Ah),
at an empty line, or after the line that closes a speech (the line ending in `\e`). The game
has 1 954 passages, 377 of them speech. A speech passage is translated without the speaker and
without the brackets: the engine adds them. Empty lines stay as the original's blank rows
between passages. The whole game has 2 125 keys.

## The file

A translation is a UTF-8 TSV file, `text/translation/vangel_<lang>.tsv`, with a header line
naming its columns:

| Column | |
|---|---|
| `key` | the key |
| `kind` | optional, checked when given |
| `text` | the translation; empty = not translated (the original is shown) |

Other columns are the translator's and are ignored. Lines starting with `#` are comments. In
`text`, `\n` ends a line, `\p` ends a page, and `\\` is a backslash. Control characters are
refused.

The repository holds keys and translations only. The Japanese is game data: the template, the
views and the reading copies are made from the player's pack into `build/`.

```sh
cd source
make text-template                       # ../build/tl/template.tsv: key, kind, speaker, rows,
                                         # columns, ja, text
python3 -I tools/tl.py skeleton ../build/virginangel.pak ../text/translation/vangel_pl.tsv
python3 -I tools/tl.py check ../text/translation/vangel_pl.tsv --pak ../build/virginangel.pak -v
make pack                                # packs every ../text/translation/vangel_<lang>.tsv
../build/sdl3/vangel --lang pl
```

`tools/tl.py` has the rest. `layout` shows where the engine draws each string. `view` writes
the file back with the speaker and the Japanese. `put` merges a batch. `fill` copies a
translation to identical originals (menus repeat a lot). `status` counts what is left. `read`
writes a reading copy of the messages.

## Layout

Every text is laid out by lrvne's reflow: `lrv_reflow_layout_from` in the engine, and
`tools/lrvne/reflow.py` as its Python reference. The rules are a greedy word wrap at spaces.
The spaces between words on a line are kept as written; spaces at a break are dropped. A word
wider than a line is cut. `\n` and `\p` are kept. Columns are half-width cells of 8 pixels; a
character is one column when the Latin glyph table has it, otherwise two (see Fonts).

- **The message window.** 68 columns by 4 rows.
  - **Where a passage starts.** The original's page loop runs over the original lines. At the
    first line of a translated passage, the passage's lines are passed over and the translation
    is laid out from the row the original would have started on.
  - **Speech.** In speech the first line starts after the translated name and `quote.open`.
    Every later line is indented to the same column, as the original indents its speech. When
    the passage closes the speech, `quote.close` is put after the text. If the first word does
    not fit after a long name, that line keeps the name alone.
  - **Row 3** is two columns short (66): the page-wait icon's cell.
  - **More pages.** A translation that needs more rows than are left goes on to further pages
    in the page's mode: a key wait, or a timed wait for a page of message 20 or 206–209. `\p`
    ends a page the same way.
  - **Timed pages** last `max(150, cells × 100 / 12)` hundredths of a second, cells being the
    columns drawn (the original counts bytes, which are its columns). A key cuts the message
    short and sets v1 as in the original.
- **Menu choices.** One line, cut at 68 columns. A choice stays at column 0; the title menu's
  choices, which the original centres with leading spaces, are centred on the original's
  centre. The choice's hit rectangle is the original's whole row.
- **Prologue.** A page of 8 rows by 72 columns, each line centred as the original's
  (`x = 40 − columns / 2`). The lines are revealed as the original's: a full-width character
  in 16 steps, a half-width one in 8, at the same time per column. A page that needs more
  rows becomes more pages, each shown 3 s and faded like the original's.
- **Staff roll.** A page of 4 lines of 32 double-size columns (16 pixels each). Indentation at
  the start of a line is kept (the original indents the names with spaces). More lines make
  more pages, each shown as long as the original's.
- **The notice.** A page of 23 rows by 80 columns, indentation kept; more rows make more pages,
  each followed by the prompt.
- **The music mode.** The heading is centred on the original's centre; the titles stay at
  column 20 and the help line at column 3, cut at column 80.
- **The console.** The translation is printed in the original string's place, between its line
  controls.

## Fonts

Translated text is drawn with the game's own look: half-width glyphs 8×16, full-width 16×16,
emboldened one pixel to the left with the window's black edge above and below, as the
original draws its text (`docs/re/text.md` §3.2).

- **`latin8`** (one per pack, keyed by code point), built at pack time by `tools/vgfont.py`:
  - ISO 8859-1 from lrvne's `fonts/x11/8x16.bdf`, the fallback;
  - ASCII from the game's own font in `M.EXE`, except the codes it draws something else for:
    `#` `$` `%` (pieces of a long bar), `&` `'` (the halves of the page-wait arrow), `!` `"` (the
    halves of a two-cell symbol) and `\` (the yen sign);
  - our own glyphs and the Polish letters, `fonts/vangel-latin.txt`. That file holds our own
    glyphs for those seven codes, for `– — … ‘ ’ ‚ “ ” „` and the no-break space, and the
    marks (acute, dot, ogonek, stroke) that make ą ć ę ł ń ó ś ź ż and their capitals out of
    the game's own letters. The file holds only our pixels; the game's are read from the
    player's `M.EXE`.
- **`wide16`** (one per language, keyed by code point): every character of the translation
  that `latin8` lacks, taken through Shift-JIS from the kanji ROM's stand-in (the pack's
  `font16`). A character neither has is an error at pack time.

## In the pack and the engine

`tools/mkpack.py --text LANG=FILE` (any number; `make pack` gives it every file in
`text/translation/`) adds per language:

- `text` (STRINGS, `tools/vgtext.py`): "VGTX", u16 version 1, u16 0, u32 count, then the
  entries sorted by key, each {u32 key offset, u32 text offset}, then the NUL-terminated keys
  and texts. Speakers are keyed by their bytes (`n.` and their hex), so the engine needs no list
  of names. Every name and both quotes are in the table, the original's where the file has
  none, so a translated passage always has its speaker.
- `wide16` (FONT).
- `lang` (META: `encoding=utf-8`, the language's name).

`latin8` is neutral, in every pack.

The language shown is `--lang TAG`. The engine remembers it in the storage record `lang`, so
the next start without `--lang` shows the same language. Otherwise the profile's `lang`
applies: the original's, which has no table. `engine/text/lang.c` looks a key up where the
original prints. Without a translation it prints the original as it was, so a partial
translation shows the rest in Japanese. `engine/text/layout.c` is the reflow with the
language's widths. Where each layout goes in the engine: `text/msg.c` (passages), `text/win.c`
and `text/menu.c` (choices), `bi/opening.c`, `bi/ending.c`, `bi/announce.c`, `bi/musmode.c`,
`game/console.c`. The saves are the original's `GAME.DAT`, unchanged, in any language.

## Tests

`tests/check_lang.py` (in `make test`) uses a pseudo-translation (`tl.py pseudo`). It has
0.5×–3× the original's width, Polish letters, full-width characters, words wider than a line,
line and page breaks, long speaker names, and menu choices longer than their row. About one
string in ten is left untranslated, so the original's passages and names (padded with
full-width spaces) come next to translated ones. The test checks:

1. **The pack.** Its table holds exactly the file's strings, every name and the quotes.
2. **The layout.** `tests/test_lang.c` plays every message, menu and built-in in that language.
   What it draws, page by page and line by line (with the timed pages' cells), equals
   `tools/vglayout.py`: the original's page loop of `txb.layout` with lrvne's reflow in
   Python. With no translation that model is `txb.layout` itself, which was verified against
   the original under emulation. The reference keeps its own rules: no line wider than its
   place, no more lines than a page holds, and nothing lost. Nothing is drawn under the
   page-wait icon.
3. **Play.** Every plan of `tests/e2e/explore.py` is played in Japanese and with
   `--lang pl` on the pseudo pack. Both plays meet the same menus in the same game state:
   the interpreter, its variables, the flags, the music, the palette, `game.dat`.

`make test` also runs the game in that language to the tick limit, which must leave nothing
allocated.
