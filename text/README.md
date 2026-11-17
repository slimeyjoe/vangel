# Translations

Our own translations of Virgin Angel, made from the Japanese: Polish first, then English
(`docs/engine-plan.md`, M8 and M9).

* `translation/vangel_<lang>.tsv`: a translation. It holds keys and our text only, never the
  game's Japanese. The format, the keys and how each kind of text is laid out are in
  [`docs/translation.md`](../docs/translation.md).
* `docs/`: the translators' guides and the story bible (M8).

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
