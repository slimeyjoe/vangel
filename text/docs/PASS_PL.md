# The Polish pass: how to carry on

This is the hand-over for whoever continues the Polish translation. A new session starts here.

**State on 2026-11-17: phase 0 is done.**
- The whole script has been read, and the story bible is written.
- Both guides are written, and an independent review checked them against the whole script.
  Its factual corrections are applied.
- The editor has approved every decision in `TRANSLATION_GUIDE_PL.md` §0 (D1–D23) and the
  glossary.
- No line is translated yet. `text/translation/vangel_pl.tsv` does not exist yet.
- `text/translation/editor_pl.tsv` holds the six passages the editor translates.

**Next: the calibration sample** (`TRANSLATION_GUIDE_PL.md` §12). Then comes the pass, chapter
by chapter, and then a native read-through in play order (`docs/engine-plan.md`, M8).

## Before the first line

1. Read, in this order: `STORY_BIBLE.md` (all of it), `TRANSLATION_GUIDE.md`, and
   `TRANSLATION_GUIDE_PL.md`. They are the product of a full read and a review. Do not skip
   them because the tools look simple.
2. From `source/`, with the game imported (`make data SRC=…`):
   ```sh
   make pack
   make text-template                                  # ../build/tl/template.tsv
   python3 -I tools/tl.py read ../build/virginangel.pak ../build/tl/read \
       --tl ../text/translation/vangel_pl.tsv          # ../build/tl/read/messages.txt
   ```
   Everything in `build/` contains the game's Japanese and is never committed.
3. Once only: create the translation file with every key and an empty text:
   `python3 -I tools/tl.py skeleton ../build/virginangel.pak ../text/translation/vangel_pl.tsv`.

## Order

The story runs in message order, and the scenario runs the chapters in that order
(`docs/re/script-catalog.md`). Translate in that order, so that voices, terms and running
gags are settled where they first appear:

1. **Calibration sample:** `bi.prologue.0`–`3`, `m001`–`m008` (chapter 1), `m013`–`m017`.
   Look at it in the game. The editor reads it, and it becomes the model.
2. `name.*`, `quote.open`, `quote.close` (fixed by the guide's §7 and D4), the title menu,
   save and load (`menu41`–`43`, `m204`, `m205`).
3. Chapters 2–11: `m009`–`m110`, menus 1–19. Chapter 9's love scene includes the editor's six
   rows (below).
4. The raid: `m111`–`m182`, menus 20–40. The exhibit menus 22–37 repeat four items, so use
   `tl.py fill`.
5. The endings: `m183`–`m203`, the ending cards (D19: left empty).
6. The opening: `m206`–`m209` (timed pages).
7. The built-ins (staff roll per D18, music room, notice prompts), `announce.*`, `con.*`.

Translate the twins of a scene together (bible §2.3). Same Japanese, same Polish.

## One chapter, step by step

1. Read the chapter's whole reading copy first, then translate. Callbacks and twins only make
   sense together. Check the bible for what each character knows at that point.
2. Write a batch file outside the repository: a header line `key<TAB>text`, then one row per
   passage. In `text`, `\n` ends a line and `\p` a page. For inline speech, write
   `Name: „…”` by hand, with continuation lines indented by U+00A0 (guide §6.2).
3. From `source/`:
   ```sh
   python3 -I tools/tl.py put ../text/translation/vangel_pl.tsv BATCH.tsv
   python3 -I tools/tl.py fill ../text/translation/vangel_pl.tsv --pak ../build/virginangel.pak
   python3 -I tools/tl.py check ../text/translation/vangel_pl.tsv --pak ../build/virginangel.pak -v
   ```
   `fill` copies a line to identical originals elsewhere, so check that each copy suits its
   other context. Look at every message `check -v` lists as paging more than the original. A
   punch line, cry or confession must not break across pages.
4. `make pack`, then look at the scene in the game (`../build/sdl3/vangel --lang pl`), at
   least where menus, long lines or a joke's timing are at stake.
5. Record every decision later lines depend on in `TRANSLATION_GUIDE_PL.md`: a settled pun
   (§10: replace „otwarte”), a new term (§14), a new voice rule (§9). A decision that lives
   only in the translation file will be contradicted three chapters later.
6. Commit the chapter: the translation file and the guide together. Run `make test` at least
   once a session (`check_lang` packs and plays a pseudo-translation; the real one must also
   build).

## Do not touch

- The six rows `m084.0`, `m085.10`, `m086.0`, `m089.0`, `m090.0`, `m093.45` are the editor's
  (`TRANSLATION_GUIDE_PL.md` §11). The editor translates them in
  `text/translation/editor_pl.tsv` and merges them with
  `tl.py put ../text/translation/vangel_pl.tsv ../text/translation/editor_pl.tsv`. A model
  leaves them as it finds them, whether empty or the editor's: no rewriting, no style pass,
  no `--force` over them. It only runs the mechanical checks.
- `text/translation/editor_pl.tsv` is not packed (`make pack` takes `vangel_*.tsv` only).
- Never copy the game's Japanese into anything tracked.

## Things already settled (keep them)

`TRANSLATION_GUIDE_PL.md` §0 is the list. The ones every scene meets:
- **Names:** surname first, as in "Amano Murakumo". Murakumo and Kenzo are not declined.
- **Speech:** `Murakumo: „…”`.
- **Murakumo's grammatical gender:** always masculine.
- **Diminutives:** Kenuś, Yukinka (plain "Yuki" from `m083.11`), Mamiś.
- **Yuki to Murakumo:** "pan" until the epilogue, except where the Japanese drops さん (D12).
- **Terms:** Toan = Stołeczne Biuro Ochrony Publicznej. The chief is "szef", nicknamed
  "Maska". 「エッチ」 = "figle" everywhere. ホモ = "homo".
- **Swearing:** no expletives. The sexual vocabulary follows the scene.
- **Period:** slang no newer than the mid-1990s.
- **Katakana voices:** written in CAPITALS.

## When the pass is complete

- `tl.py status` shows nothing left except the deliberately empty rows: the ending cards
  (D19) and anything the editor still holds.
- Play every route with `--lang pl` (`tests/e2e/explore.py` plans; `make test` already does
  so with the pseudo-translation).
- Then the editor reads the play-order view and plays. Next are a lint for the guide's rules
  (`TRANSLATION_GUIDE_PL.md` §13) and English (M9).
