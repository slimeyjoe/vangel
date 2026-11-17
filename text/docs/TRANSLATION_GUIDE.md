# Virgin Angel translation: editor's guide

Read this before you change a line of `translation/vangel_<lang>.tsv`, whether you are a person
or a model. It covers:

1. where the text lives and how it gets into the game;
2. the engine's limits (verified by the tests);
3. traps in how this game stores its text;
4. fidelity rules;
5. what a translation of this game must not flatten;
6. voices, terms, adult content and a checklist.

Companions: **[STORY_BIBLE.md](STORY_BIBLE.md)** (plot, characters, what the game is doing;
spoilers, so read it first) and the language guides, which add to this one and win where they
differ: **[TRANSLATION_GUIDE_PL.md](TRANSLATION_GUIDE_PL.md)**.

A reference like `m083.36` is a string's key (`docs/translation.md`): message 83, the passage
that starts at its line 36.

---

## 0. Where the text lives

- `translation/vangel_<lang>.tsv` is the master copy of a translation. It has one row per
  key, with the columns `key`, `kind` and `text`. Other columns are the translator's own and the
  tools ignore them. An empty `text` means "not translated", and the game shows the original
  there. The file holds **no Japanese**. The original stays in the game's files, which everyone
  imports from their own copy (`docs/game-data.md`).
- The engine runs the original scenario unchanged and swaps a string for its translation when
  it is printed. Nothing a translation contains can change what the game does: the tests play
  every route with a translation and compare the game state at every menu with Japanese. An
  unknown key fails the build.
- Translate from the **Japanese**. There is no earlier translation of this game to lean on.
- The keys are fixed (`docs/translation.md`). There are 1 954 passages (`m<NNN>.<L>`), 18
  speaker names (`name.NN`), the two speech brackets (`quote.open`, `quote.close`), 106 menu
  choices, 38 built-in texts (prologue, staff roll, music room, the notice's prompts), the
  three pages of the notice and four console messages: 2 125 keys in all.

## 1. Quick start: changing lines safely

From `source/`, with the game imported and the pack built (`make data SRC=…`, `make pack`):

```sh
make text-template                       # ../build/tl/template.tsv: key, kind, speaker, rows,
                                         # columns, the Japanese, the text
python3 -I tools/tl.py read ../build/virginangel.pak ../build/tl/read \
    --tl ../text/translation/vangel_pl.tsv
                                         # ../build/tl/read/messages.txt: every message in
                                         # order, every passage with its key and speaker
python3 -I tools/tl.py view --pak ../build/virginangel.pak \
    ../text/translation/vangel_pl.tsv ../build/tl/view-pl.tsv
                                         # the translation with the speaker and the Japanese
```

Write new lines as a small batch: a header line `key<TAB>text`, then one row per string. Merge
it. Only the `text` cells of the master file change, and an entry that is already translated
differently is refused unless you pass `--force`:

```sh
python3 -I tools/tl.py put ../text/translation/vangel_pl.tsv batch.tsv
python3 -I tools/tl.py fill ../text/translation/vangel_pl.tsv --pak ../build/virginangel.pak
                                         # copies a translation to untranslated strings with
                                         # the same Japanese (the twins, the menus)
python3 -I tools/tl.py check ../text/translation/vangel_pl.tsv --pak ../build/virginangel.pak -v
                                         # bad keys, characters no font has, and every message,
                                         # menu or built-in that pages more than the original
                                         # or is cut
python3 -I tools/tl.py layout --pak ../build/virginangel.pak \
    ../text/translation/vangel_pl.tsv m030.45   # where exactly each line of a key lands
make pack
../build/sdl3/vangel --lang pl           # look at it in the game
make test                                # everything still passes
```

In `text`, `\n` ends a line, `\p` ends a page and `\\` is a backslash. Control characters are
refused. Never commit anything from `build/`: the template, the views and the reading copies
contain the game's text.

## 2. Engine limits (verified: `source/tests/check_lang.py`, `docs/translation.md`)

- **A character** takes 1 column (8 pixels) if the Latin table `latin8` has it. That covers
  ASCII, ISO 8859-1 (so `é à ü « » ° ·` …), the Polish letters, `– — … ‘ ’ ‚ “ ” „` and the
  no-break space. Anything else that Shift-JIS can write is drawn from the Japanese font at 16
  pixels, **2 columns**: `☆ ★ ♀ ♂ ○ ◎ ＊ 『』「」【】`, full-width letters, digits and spaces
  (`　`), kana and kanji. A character neither font has stops the build.
- **The game's own ASCII is not ASCII.** In the original, `#` `$` `%` are the pieces of a long
  bar, `&` `'` draw the page-wait arrow, and `\` is a yen sign. In a translation these codes are
  drawn as the ordinary characters, with our own glyphs. The original's `#$$$$%` (a long drawn-out
  sound, `m019.5`, `m025.8`, `m052.43`) has no equivalent; write the long sound with letters.
- **The message window** is 68 columns by 4 rows. **Row 3 holds 66**; the page-wait icon sits in
  its last two cells. Text is wrapped greedily at ASCII spaces. Spaces at a break are dropped,
  **and so are ASCII spaces at the start of a line**. A word wider than a line is cut.
- **A passage** is laid out from the row where the original's would start. Tagged speech starts
  after the translated name and `quote.open`, every later line is indented to the same column,
  and `quote.close` follows the last word.
- **A text that does not fit** continues on another page after a key press. The opening's
  messages 206–209 are timed pages instead: they last
  `max(1.5 s, columns ÷ 12 per second)`, so a longer text stays up longer by itself. Some extra
  paging is unavoidable and accepted, **but not where it breaks a punch line, a cry or a reveal
  in two**. `tl.py check -v` lists every message that pages more than its original.
- **You cannot merge or split passages.** One key is one passage, and the scenario decides where
  the player presses a key between passages. If a sentence must move from one passage into the
  next to read well, move it, and keep both non-empty.
- **Menu choices** are one line, cut at 68 columns. They stay at column 0, except the title
  menu (43), whose choices are centred on the original's centre. A choice's hit area is the
  original's whole row.
- **Prologue** (`bi.prologue.*`): 8 rows of 72 columns per page, each line centred. **Staff
  roll** (`bi.staff.*`): 4 lines of 32 double-size columns; indentation at the start of a line
  is kept. **Notice** (`announce.*`): 23 rows of 80 columns; indentation is kept. **Music room**:
  titles from column 20 and the help line from column 3, cut at column 80. More rows than a page
  holds make more pages; check lists them.
- **Indentation inside the message window**, where you need it, is made with characters that
  are not ASCII spaces: the full-width space `　` (2 columns) or the no-break space U+00A0 (1
  column). Both are kept at the start of a line.

## 3. Traps in how this game stores its text (each found in the read)

| Trap | What it is | What to do |
|---|---|---|
| **Two kinds of speech** | Tagged speech (`[name.04 ユキ　　]` in the reading copy) gets its name and brackets from the engine: you translate only what is said. Far more speech is **inline**, `ユキ　　「はい！」`, inside an ordinary passage. There the name and the brackets are part of the text you translate. | Inline speech: write the name exactly as `name.NN` translates it, and the brackets exactly as `quote.open` / `quote.close`, so that the two kinds look identical on screen. Inline speech running over several lines is indented by hand (§2, last point; the language guide fixes how). |
| **Recorded voices** | On the deck, `ササメ『…』` and `ケンゾウ「…」` followed by `『…』` blocks (`m037`, `m045`): a recording, not a person in the room. | Keep a visible difference from live speech; the language guide fixes the marks. |
| **Names table** | `name.NN` are numbered by first appearance and include the original's typos and variants: `name.06` シノフ (= Shinobu), `name.09` ムラウモ (= Murakumo), `name.13` スネイク (= Snake, as `name.12`), `name.15` / `name.17` 女 (the same woman, padded differently). Inline speech has typos too: `m096.16` モラクモ, `m191.29` ムラムモ. | Translate every variant as the correct name. These are slips, not characterisation. |
| **A wrong tag** | `m179.10` is tagged クサナギ (`name.08`), but the speaker is Sasame: Kusanagi is dead, and Sasame holds out his hand. | A translation cannot fix it, because `name.08` is one key for all of Kusanagi's lines. Leave it; it is a candidate for the opt-in typo fix (M10). |
| **Twins** | Many scenes exist once per route, with most lines the same (bible §2.3). | Same Japanese, same translation (`tl.py fill`). Translate the twins of a scene together and keep their differences. |
| **Unreachable** | Message 20 (a title card) and message 136 (the combat-armour copy of Reiko's taunt) are never shown. | Translate them as their twins (136 = 140 = 144). |
| **The exhibit menus** | Menus 22–37 offer the same four items in every order. Menu 22 is unreachable. | One translation per item, identical in all of them (`fill`). |
| **Aligned menus** | Menu 38 pads its items with full-width spaces so that the verb ending lines up (`散弾　　　　　を装填する`). | Alignment is not needed if the verb comes first in your language. Do not copy the padding. |
| **The title menu** | Menu 43 pads its items to centre them; the engine centres translated items itself. | Write the items without padding. |
| **Symbols** | ☆ after a word is the hero's flirtatious tone. `○♀♀＠＊☆♂` (`m045.20`, `m045.22`) is a swear word nobody may print, and the second copy is Sasame quoting the first. `○` is the period's censorship mark, in vulgar and clinical words alike (オマ○コ, クリ○リス, アヌ○). Garbled symbol rows stand for noise (`m100.48` Hinamura being throttled, `m116.7` a muffled cry). Bracketed stage directions: `（しょぼん）`, `（汗汗汗）`. | Keep ☆ and the symbol rows (they are 2-column characters). The two grawlixes stay identical. Translate the stage directions into short bracketed words. Censoring: the language guide. |
| **『』 does four jobs** | Names and terms at first mention (『首都公安局』), quoted words and thoughts (『住む世界が違う』), sound effects (『バタン！！』), recorded voices (above). | Map each job separately (language guide). Do not turn every 『』 into the same quotation marks. |
| **Centred texts** | Some passages are centred with full-width spaces (`m027.51` 【該当者なし】, the ending cards 210–213). | Keep the centring with full-width spaces (ASCII spaces at the start of a line are dropped). |
| **The console** | `con.ask` ends in `[Y/N]`. The game reads the **Y** and **N** keys. | Keep `[Y/N]` and the letters Y and N, whatever the words for yes and no. |
| **The music room's help line** | It names keys: cursor up and down, Space or Return, ESC. | Name the same keys. |
| **Real names and a phone number** | The staff roll and the notice name real people (in kanji) and give the 1995 support BBS's number. | The language guide decides between romanisation (readings must be verified, not guessed) and keeping them as written. The number stays as it is. |
| **The shared and rare characters** | `ヘボ公安め` etc. are ordinary; but `!"` in `m001.29` is a stray character in the original (its `"` is not a quote). | Ignore the stray `"`. |
| **A wrong inline name** | `m006.29` is written `ムラクモ「…」`, but it is Sasame's line: plain だ and hearsay (そうだ), and Murakumo answers him politely at `m006.31`. | Inline names are text, so the translation can fix it: write Sasame's name. |
| **A wrong subject** | `m208.15` writes 女 (the woman) where 娘 (the girl) is meant: the girl is the one pulled close. | Translate what is meant. |
| **Dropped characters** | `m195.5` reads `…に／らったの☆` across a line break: にしてもらったの with characters missing. | Translate the complete sentence. |
| **Slips in the text** | 都案 for 都安 (`m002.19`), コンダット for コンバット (`m168.14`), 氏名手配 for 指名手配 (`m062.26`), 被害車 for 被害者 (`m037.31`), 鉄鋼弾 for 徹甲弾 (`m040.10`, `m109.4`), ボードをを in menus 22–37. | Translate what is meant; do not reproduce the slip. |

## 4. Fidelity rules

The source is colloquial, fast and elliptical Japanese, much of it the narrator's inner voice.
These are the ways such text is most often misread, with examples from this game:

1. **Rhetorical negatives are affirmatives.** `〜じゃないか`, `〜じゃないの`, `〜ないかね` assert.
   `m035.24` 「…有名な大型総合病院じゃないか！」 is "That's that big famous hospital!", not a
   question. `m108.3` 「あるじゃないの、あるじゃないの」 is "There it is!"
2. **Who does what to whom.** Subjects are dropped; take them from the scene, not from the
   nearest noun. In `m030.38` it is Yuki who was attacked, and `らしい` marks it as what Shinobu
   has gathered, not what Yuki told her. In `m198.38` it is Yuki who agreed to the operation.
3. **Giving and receiving verbs** (`〜てくれる`, `〜てもらう`, `〜てあげる`) carry the direction of a
   favour. `m021.12`: Shinobu *asks* for time. `m184.8`: Shinobu *arranged* the surgeon.
4. **Sentence-final particles carry the tone.** The hero's katakana `ネ`, `ナ`, `ヨ`, his `〜のね`,
   `〜だよん`, ☆; Shinobu's switch between `〜わ` and `おい！`; Reiko's `〜ですわ` and `〜おし`. A
   translation that keeps the content and drops them makes everyone sound alike.
5. **Narration tense.** Japanese narration mixes `〜た` and the present freely. Pick one base tense
   (the language guide says which), and do not copy the mixing at random. But the fights and the
   sex scenes run in present-tense blocks (`m075`–`m078`, `m165`–`m176`): a historic present for
   a whole passage keeps their speed, and a blanket past tense deadens them.
6. **Quoted and reported speech** (`〜って`, `〜だと`, `〜とか`): hearsay stays hearsay. The
   witnesses' description of the killer is what *they* said (`m005.71`, `m007.14`). Misa's words
   reach us through Mami (`m072.1`).
7. **Politeness shifts are events.** Render each shift where it happens, and only there:
   - Yuki: アマノ先輩 → ムラクモさん, kept with です/ます through the raid and the rescue; the bare
     ムラクモ only at peaks (`m093.26`, `m094.0`, `m149.4`); steady casual speech only in the
     epilogue (`m184.29`), still mixed with さん, once polite again under stress (`m185.17`); last
     of all, あなた (`m189.16`, `m201.45`, 貴方 `m196.107`). Bible §5.
   - Murakumo to Yuki: ユキちゃん → ユキ and キミ at `m083.11` (Shinobu remarks on it, `m099.46`),
     with one relapse to ユキちゃん (`m132.5`).
   - Murakumo to Shinobu: mostly です/ます and シノブさん. In `m030.45`–`m030.58` his speech and the
     narration both drop it (シノブ).
   - Murakumo to Sasame: one アンタ (`m179.18`).
   - Murakumo to Reiko: polite (`m063.6`, `m079.7`), then テメエ (`m134.3`).
   - Reiko: plain speech once before the reveal (`m074.9`); after it, plain speech with 貴方 and
     flashes of keigo (`m134.6`, `m165.0`).
   - Kusanagi to Murakumo: 貴方 (`m051.7`) → 君 or ムラクモ君 with ですぞ (`m162.4`) → 貴様
     (`m176.74`).
   - Sasame: bare ムラクモ when he commands, ムラクモ君 when he is smooth (`m045.12`, `m178.6`,
     `m183.37`); `〜たまえ` gives way to a plain `行きなさい` at the farewell (`m183.55`).
8. **Set phrases and proverbs** are not literal: 現場百回 (`m012.8`), 昔取った杵柄 (`m119.7`), 叩くと
   ホコリが出る (`m053.29`, "has skeletons in the closet"), 耳年増 (`m048.23`), 奥歯に物の詰まった言い方
   (`m008.36`), トカゲの尻尾 (`m105.23`). Find the idiom. Where a joke hangs on the literal sense,
   see §5 on wordplay.
9. **Onomatopoeia and mimetics** are words, not noise: `ふらふら`, `タジタジ`, `ニコニコ`, `ジロリ`,
   `ワナワナ`, `ツカツカ`. Translate what they mean. Only real sound effects, written alone (often in
   『』: `『バタン！！』`, `『ガン！ガン！』`, `カチッ、カチッ`), become sounds.
10. **Do not explain.** If the Japanese leaves something unsaid (who left the key, what Sasame
    knew, why the wedding is unregistered), the translation leaves it unsaid in the same place.
11. **Do not improve the hero, or anyone.** Murakumo is lecherous, crude and pushy. He forces a
    kiss on Yuki twice (`m082`, `m118.18`), and the text knows it ("ずるい"). His jokes about
    sex, gays, mutilation and women's bodies are as crude as they are and no cruder. Translate
    what is there, at the strength it is there. The same goes for jokes that have aged badly.
12. **Numbers, names and places must match everywhere**: 65 700 hours (`m005.20`, `m057.18`,
    `m103.27`); 00:50, 23:20, 22:30, 23:05 (the timeline); 27–28 years old and 180 cm; three
    months; Route 357 (`m037.16` writes "137"; the language guide decides whether to correct
    it); D block; 2 km; 20:00;
    the four armours, four rounds and four dolls; class-B licence; .45 and .38 calibres; four
    weeks; a month and a half.
13. **好き and 愛してる are two steps.** Murakumo says 好き(だ) from `m083.52` to `m202.16`, and
    愛してる only at the wedding-night climax (`m188.133`, `m189.6`). Yuki says 愛してる earlier
    (`m185.76`, `m185.112`; drugged, `m196.30`). The language guide decides how the escalation
    survives; one phrase for both erases it.
14. **Katakana speech is a voice quality**, not a spelling. That covers Hinamura's robotic
    weather report (`m019.5`), Reiko turning into a machine (`m168.18`), and Murakumo's
    mock-official ゴクロウさん and デース (`m002.13`, `m003.13`). Give each a device the reader
    hears.
15. **The period.** A 1995 game set in the 2080s. Slang no newer than the mid-1990s in the
    target language. The hero's trendy bubble-era loanwords (ナイスボディー, ブルー, ノーマル,
    アイデンティティ, ダークネスな建物) want the loanword slang of that time, not of today.
16. **The menus are in his voice** and carry jokes: `menu03.1` (能面局長), `menu11.1`
    (貞操の危機だ！), `menu11.2` (しなを作り, echoing `m001.32`). `menu40.2` and its spoken
    repeat in `m164.0` / `m166.0` are the same line and get the same words.
17. **Erotic vocabulary follows the scene** (bible §8): coy, grotesque, flowery, porn slang or
    S&M, as the original is. Sound words inside sentences (`『チュパッ』と吸い上げる`) and the
    moans are part of that register. The language guide holds the glossary.
18. **The narrator's gaze stays** (bible §6): the indignation and the prurience side by side,
    and the language of possession in the healing scene.

## 5. What a translation must not flatten

- **The hero's two registers.** The camp, flirtatious surface and the street fighter under it
  are both his own voice, and they alternate within a scene (`m074`–`m078`). Neither may swallow
  the other. When he is serious (`m030.45`, `m035.30`, `m083.11`, `m118.25`, `m183`, `m185`) the
  camp markers vanish. That is the signal, so keep it.
- **His body without commentary.** He is a man with breasts who says he is straight; the others
  react, and the text never resolves anything (bible §5). Do not add words that make him a woman,
  a cross-dresser or a gay man, and do not make the others' reactions kinder or crueller than
  they are. Grammatical gender, where a language has it, is masculine for him always.
- **Sasame's opacity.** Until `m179` he is cold, exact and possibly an enemy. His lines must
  allow the second reading (he knew) and announce nothing (`m008.10`, `m022.32`, `m053.46`,
  `m098.29`, `m105.7`). After that the coldness cracks in one line at the rescue (`m179.10`
  よく、生きていてくれた, under Kusanagi's wrong tag), in deeds, and in one sentence of regret
  (`m183.41`).
- **Reiko until `m134.23`.** An insolent secretary with too much protectiveness for her doctor.
  Nothing she says before the reveal may sound mechanical, murderous or strong. The narration
  plants its cracks (`m063.0` 目が笑っていない, `m065.41` 無機質), and she overreacts in
  `m065.45`–`m065.56`. Keep exactly those, literally.
- **Yuki's earnestness.** She is not a cute rookie for comic relief. Her lines about women as
  objects state the theme, and her apologies come from guilt about her sister. Do not make her
  childish. She is an adult who is shy (bible §5).
- **The echoes** listed in the bible (§6) come back within a playthrough, and each gets one
  rendering, used every time. Route twins are a different thing: they are translated alike but
  carry no recall (bible §6). Where an echo differs slightly in the Japanese (`m185.28` /
  `m202.16`, the last verb), the translations differ in the same place.
- **The narrator's gaze.** He condemns what is done to women and enjoys looking at it, in the
  same scenes (bible §6). Keep both. Do not tilt the lab or captivity narration toward pity.
- **The clues of the raid** (bible §2.2): the blue-white flash, the fist (after the first
  impression of a blunt instrument, `m005.58`), light titanium,
  anti-optical coating, the stun gun, "prototype, only one round". Exactly as clear as in
  Japanese.
- **Tone at the deaths and the assault.** The quips over Snake's hand, Reiko's head and
  Kusanagi's cheek stay quips. The lines of grief after the assault (`m180`–`m182`) are plain.
- **Wordplay.** The bible's §7 lists the routines. Where a pun cannot cross, build a different
  joke of the same size on the same spot, keeping what the scene needs from it: who is annoyed
  at whom, what is learned. Never explain a joke, never drop the beat and never add a footnote.
  Decisions go in the language guide's table so that later lines that call back agree.
- **Japan and its future as home ground.** Tokyo in katakana, reclaimed lots, the
  Metropolitan Police, family registers, a period-TV joke: the hero's ordinary world. Do not
  relocate it or gloss it in dialogue. The invented future terms (body drug, combat doll, Toan,
  Uroboros) are as matter-of-fact as the real ones.

## 6. Voices (full dossiers: STORY_BIBLE §5)

| Voice | Japanese | Carry over as |
|---|---|---|
| Murakumo, surface | ボク, ☆, `〜のね`, katakana `ネ ナ ヨ`, drawn vowels, bracketed stage directions | playful, flirtatious, childish, theatrical; light in the mouth |
| Murakumo, angry or fighting | テメエ, ブチ殺す, 貴様ら, `〜ゼ` | short, hard, street |
| Murakumo, serious | plain, no markers | plain, no markers |
| Murakumo, narration | first person, quick, asides to the reader, exact in fights | a raconteur; precise verbs in the action |
| Yuki | です/ます and ムラクモさん through the raid; bare name only at peaks; casual and あなた in the epilogue; third-person ユキ when overwhelmed | earnest, polite, warm; never childish |
| Sasame | 私, 君/キミ, `〜かね`, `〜たまえ`, contract language | cold, precise, faintly ironic; a superior who never raises his voice |
| Shinobu | feminine `〜わ` / gruff `おい！お前` | a warm, bossy, older woman who swears like a colleague |
| Kenzo | 貴様, 俺, exclamation marks; stiff officialese on the deck | loud, offended, upright |
| Hinamura | polite, cheeky | a junior who gets his digs in |
| Reiko, mask | わたくし, `〜ですわ`, オホホ | icy courtesy over contempt |
| Reiko, unmasked | plain speech with 貴方, keigo flashes, ☆, うふふ, a shrill キャハハ; ladylike imperatives (`〜てらして`, `おっしゃい`, `〜なくてよ`, `お〜っ`, `〜おし`) | a mock-genteel dominatrix: drawing-room cruelty, never barking; once, a soldier's finality; once, a machine (`m168.18`) |
| Kusanagi | `〜ですな`, `〜ですぞ`, 貴方 → 君 → 貴様, clinical terms, ウフフ | a pompous surgeon enjoying himself, until his face is shot |
| Mami | timid polite | frightened, tearful |
| Gori | `イヒヒ`, `〜のだぁ`, `ちゃるぅ`, `痛えじゃねいか`, lewd | a slurred, drawling cartoon brute |
| Snake | curt; then screaming | cool, then nothing but pain |
| Shikakura | `あんた`, laconic | an old hand, amused |
| the homeless | A and B rustic `だべ`, `〜べ`; C brassy woman's speech (`m207.9`) | a light rustic colouring, not a specific dialect; C a loud woman |
| the woman (opening) | Reiko's voice: `お見せっ`, `お言い`, `覚悟おし` | the same voice as Reiko unmasked |

## 7. Terms

The locked spellings and terms are in the language guide's glossary. Decide a term once, there,
with the keys of its first and its trickiest occurrence. `tl.py check` cannot know your
glossary, so search the template for the Japanese before you settle a rendering.

## 8. Adult content

The explicit sexual passages (STORY_BIBLE §8: 499 passages and menus 14–16) are translated like
the rest, at the strength of the original: no prudish euphemism and no added crudeness. Six
narration passages of the park scene, in which the text compares Yuki's body to a girl's or a
child's (`m084.0`, `m085.10`, `m086.0`, `m089.0`, `m090.0`, `m093.45`), are translated by the
editor, per language, in `translation/editor_<lang>.tsv` (not packed; merged with `tl.py put`).
A model leaves these rows as it finds them and only runs the mechanical checks on them.

## 9. Checklist for every change

1. Read the scene in the reading copy: the passages before and after, the speakers, and which
   twin you are in. Know who speaks to whom and what they know at that point.
2. Check the bible for the characters and for anything the line echoes.
3. Translate from the Japanese. Check the speaker (tagged or inline), the register and the
   politeness level.
4. Same Japanese elsewhere? (Search the template.) Same translation, or a reason.
5. `tl.py put`, `tl.py fill`, then `tl.py check -v`. Extra pages and cut items are yours to look
   at, one by one.
6. Build the pack and read the scene in the game.
7. `make test`.

## 10. Open items

- A lint for the language guides' rules (names in inline speech against `name.NN`, quote marks,
  the echoes, grammatical gender of the hero, forbidden characters) does not exist yet; `tl.py
  check` covers only what the engine needs. Neither does a list of originals translated in more
  than one way.
- A helper that lays out multi-line inline speech with its hanging indent (§3) would save
  hand work.
- This guide and the bible were reviewed independently against the whole script on
  2026-11-17. The factual corrections and the rules above (§3 last rows, §4 rules 5, 7, 13–18,
  §5) came out of that review.
- Line references by key are stable; the bible and the guides do not use line numbers.
