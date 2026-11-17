# Translations

Our own translations of Virgin Angel, made from the Japanese: Polish first, then English
(`docs/engine-plan.md`, M8 and M9).

* `translation/vangel_<lang>.tsv`: a translation. It holds keys and our text only, never the
  game's Japanese. The format, the keys and how each kind of text is laid out are in
  [`docs/translation.md`](../docs/translation.md).
* `docs/`: the translators' guides and the story bible (M8):
  * [`docs/STORY_BIBLE.md`](docs/STORY_BIBLE.md): the plot, the routes and the four endings,
    the characters, what the game is doing, and how the adult scenes are handled (spoilers). Read it first.
  * [`docs/TRANSLATION_GUIDE.md`](docs/TRANSLATION_GUIDE.md): read before changing a line. How text
    gets into the game, the engine's limits, the traps of this script, the fidelity rules, and
    what must not be flattened.
  * [`docs/TRANSLATION_GUIDE_PL.md`](docs/TRANSLATION_GUIDE_PL.md): the rules for Polish (in
    Polish). It holds the decisions awaiting the editor, forms of address, names, conventions,
    voices, wordplay and a glossary.

The Japanese to translate from comes from your own copy of the game (`make data`, `make pack`):

```sh
cd source
make text-template          # ../build/tl/template.tsv: every string with its Japanese
python3 -I tools/tl.py check ../text/translation/vangel_pl.tsv --pak ../build/virginangel.pak -v
make pack                   # packs every translation here
../build/sdl3/vangel --lang pl
```

The template and the reading copies (`tl.py view`, `tl.py read`) are derived game data. Keep
them in `build/`; they never go into the repository.
