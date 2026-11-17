# Virgin Angel: przewodnik polskiego tłumacza

Ten dokument jest dla każdego, kto tłumaczy lub redaguje polską wersję gry *Virgin Angel*
(Crystal Soft, 1995): dla ludzi i dla modeli.

Opiera się na [TRANSLATION_GUIDE.md](TRANSLATION_GUIDE.md) (zasady wspólne dla wszystkich
języków: pliki, limity silnika, pułapki, zasady wierności, czego nie wolno spłaszczyć) oraz na
[STORY_BIBLE.md](STORY_BIBLE.md) (fabuła, postacie, spoilery). Tamte dokumenty obowiązują w
całości. Tutaj są zasady **dodatkowe** albo **inne** dla polszczyzny. Przy sprzeczności wygrywa
ten dokument.

**Odwołania:** `m083.36` to klucz napisu: komunikat 83, fragment od jego wiersza 36. Japoński
tekst z kluczami daje `make text-template` i `tl.py read` (w `source/`, wynik w `build/`).

**Status (2026-11-17):** faza 0 zakończona. Cały skrypt przeczytany, biblia spisana, dokumenty
sprawdzone przez niezależnego recenzenta z całym skryptem, a redaktor podjął wszystkie decyzje
z §0 (**zatwierdzone**). Następna jest próbka kalibracyjna (§12), po niej przekład. Wpisy
oznaczone „otwarte” (§10) i „do ustalenia” (§14) rozstrzyga się przy tłumaczeniu danej sceny
i wpisuje tutaj.

---

## 0. Decyzje redaktora

Zatwierdzone wcześniej (plan, `docs/engine-plan.md`, i M7, `docs/translation.md`):

| Sprawa | Decyzja |
|---|---|
| Źródło | Tłumaczymy **z japońskiego**. Innego przekładu tej gry nie ma. |
| Kolejność | Najpierw polski, potem angielski. |
| Miejsce | `text/translation/vangel_pl.tsv`, same klucze i przekład, bez japońskiego. |
| Długie teksty | Okno zostaje oryginalne (68×4); dłuższy tekst przechodzi na kolejną stronę. |
| Font | Tekst łaciński rysuje własny font gry 8×16 z M.EXE; polskie litery, cudzysłowy i myślniki są dorysowane w tym samym stylu (`fonts/vangel-latin.txt`). |

**Zatwierdzone przez redaktora 2026-11-17** (wszystkie wiersze poniżej; tam, gdzie przegląd
proponował co innego niż pierwsza wersja, redaktor przyjął propozycję przeglądu):

| # | Sprawa | Decyzja |
|---|---|---|
| D1 | Zapis imion | Hepburn bez znaków długości: Josetsu, Kenzo, Hyoyoku. **Nazwisko pierwsze**: Amano Murakumo, Kusanagi Ken, Yasaka Yuki, Sasame Josetsu. Tylko w tej kolejności widać Ama-no-Murakumo, nazwę miecza (biblia §6), a kartoteki w grze też podają najpierw nazwisko (`m035.18`, `m062.0`) |
| D2 | Honoryfikatywy | **Nie zostawiamy** -san, -chan, -kun ani -sensei. Grzeczność oddają „pan / pani / ty” (§4), ちゃん zdrobnienie (D3) |
| D3 | ちゃん | **Kenuś** (ケンちゃん), **Yukinka** (ユキちゃん, wołacz „Yukinko”), **Mamiś** (マミちゃん, `m052.31`). Gdzie on porzuca ちゃん (`m083.11`), samo „Yuki” |
| D4 | Mowa: nawiasy | `quote.open` = `: „` (dwukropek, spacja, „), `quote.close` = `”`. Mowa wpisana w akapit wygląda tak samo: `Murakumo: „Siema!”` |
| D5 | Wcięcie wielowierszowej mowy w akapicie | kolejne wiersze zaczynamy **twardymi spacjami** (U+00A0) do kolumny za „ (§6.2) |
| D6 | Toan i Biuro | 首都公安局 = **Stołeczne Biuro Ochrony Publicznej**, w skrócie **Toan** (D. Toanu, Ms. w Toanie); potocznie „Biuro”. **Nigdy** „Urząd Bezpieczeństwa”, „bezpieka”, „SB” |
| D7 | 局長 | **szef** (Biura), w zwrocie „szefie”. Przezwisko 能面局長 = **szef Maska**; przy pierwszym użyciu „twarz jak maska nō”. „Dyrektor” to 院長 (Kusanagi). „Kamienna gęba” zostaje dla Kenza (顔面岩) |
| D8 | ボディ・ドラッグ | **żywy narkotyk** (lm. żywe narkotyki; „przerobić kogoś na żywy narkotyk”) |
| D9 | コンバット・ドール | **lalka bojowa** (lm. lalki bojowe); typ **Statue 2H**; メタル女 = „metalowa baba” |
| D10 | バージン・エンジェル | **Virgin Angel** bez tłumaczenia (narkotyk i tytuł gry) |
| D11 | Rodzaj gramatyczny Murakumo | **męski, zawsze** (§3) |
| D12 | Yuki → Murakumo | **„pan”** („panie Amano”, potem „panie Murakumo”) do końca nalotu; **„ty” albo samo „Murakumo”** dokładnie tam, gdzie japoński gubi さん (`m093.26`, `m094.0`, `m149.4`), potem z powrotem „pan”; **stałe „ty”** od `m184`, z powrotem do grzeczności w `m185.17`; あなた = **„kochany”** (`m189.16`, `m201.45`, `m196.107`) |
| D13 | Wulgaryzmy | **bez przekleństw** k…, ch… i pochodnych; poziom „drań”, „gnój”, „sukinsyn”, „cholera”, „szlag”. **Słownictwo seksualne idzie za sceną** (§11), z prawdziwymi wulgaryzmami tam, gdzie ma je oryginał (デカマラ Goryla `m074.47`, オマ○コ, オ○ンチン, slang niewoli) |
| D14 | ホモ | **homo** („Nie jestem homo, więc spokojnie☆”) |
| D15 | エッチ | **figle, figlować** wszędzie, także w przełomie `m100.34` („Figle! O to chodzi!”) i w tytułach utworów: „Figle 1”, „Figle 2”. セックス = „seks” (`m099.35`) |
| D16 | Sceny dla dorosłych (biblia §8) | tłumaczymy jak resztę, z siłą oryginału; sześć fragmentów tłumaczy redaktor (§11) |
| D17 | Błędy oryginału | poprawiamy: imiona (`name.06`, `name.09`, `name.13`, `m096.16`, `m191.29`), mówiący w `m006.29` (Sasame), podmiot w `m208.15`, ubytek w `m195.5`, literówki z przewodnika ogólnego §3 |
| D18 | Napisy końcowe i zapowiedź Crystal Soft | role i treść po polsku; **nazwiska** w zapisie oryginału (kanji), dopóki ktoś nie sprawdzi odczytów |
| D19 | Karty zakończeń (210–213) | zostają **puste**: gra pokazuje własne angielskie `Ｅｎｄｉｎｇ Ｎｏ．１` |
| D20 | Godziny | w mowie urzędowej (Sasame, raport Kenza, ekrany) **z dwukropkiem**: „00:50”, „22:30”; w narracji i potocznie **z kropką**: „o 23.20” |
| D21 | 好き / 愛してる | 好き(だ) = **„kocham cię”**; 愛してる **mocniej**: „kocham cię nad życie”, „kocham cię, słyszysz? kocham” (`m188.133`, `m189.6`; Yuki: `m185.76`, `m185.112`, `m196.30`) |
| D22 | „trasa 137” (`m037.16`) | poprawiamy na **357** |
| D23 | Mowa katakaną | **wielkie litery**: „ŁADNA DZIŚ POGODA...” (`m019.5`), „ŁADNIE MNIE URZĄDZIŁEŚ” (`m168.18`); dwa słówka Murakumo lżej, sylabami: „Dzię-ku-je-my za trud!” (`m002.13`), „Toan, pro-szę pa-ństwa!” (`m003.13`) |

---

## 1. Pliki i narzędzia

- `translation/vangel_pl.tsv` ma jeden wiersz na klucz, kolumny `key`, `kind`, `text`.
  Zmieniamy **wyłącznie** `text`. Pusty `text` = nieprzetłumaczone, więc gra pokazuje
  oryginał i plik zawsze daje się zbudować. Własne kolumny tłumacza (np. `note`) narzędzia
  pomijają.
- Japońskiego nie ma w repozytorium. `make text-template` robi `build/tl/template.tsv` (klucz,
  rodzaj, mówiący, wiersze, kolumny, japoński). `tl.py read` robi kopię do czytania: cały
  skrypt komunikat po komunikacie, każdy fragment z kluczem. `tl.py view` stawia polski obok
  japońskiego.
- Tłumaczymy partiami: plik `key<TAB>text` z nagłówkiem, potem `tl.py put`, `tl.py fill`,
  `tl.py check -v` (przewodnik ogólny §1). W tekście `\n` kończy wiersz, `\p` stronę.
- **Co znaczy „przetłumaczone”:** niepusty `text`. Fragmenty bez liter (same kropki, `？？？`)
  też tłumaczymy, interpunkcja według §6.

## 2. Znaki i długości

- **Jedna kolumna:** ASCII, polskie litery `ąćęłńóśźżĄĆĘŁŃÓŚŹŻ`, ISO 8859-1 (`« » é ü °` …),
  `– — … ‘ ’ ‚ “ ” „` i twarda spacja U+00A0. `# $ % & ' " \` rysują się jako zwykłe znaki
  (w oryginale były czymś innym; przewodnik ogólny §2).
- **Dwie kolumny** (japoński font): `☆ ★ ♀ ♂ ○ ◎ ＊`, `『』「」【】`, spacja pełnoszeroka `　`,
  pełnoszerokie litery i cyfry. Używamy ich tylko tam, gdzie §6 każe.
- **Okno:** 68 kolumn × 4 wiersze, czwarty wiersz 66. Japoński znak zajmuje 2 kolumny, polska
  litera 1, więc polski tekst zwykle mieści się w tylu kolumnach co oryginał albo w nieco
  większej liczbie. Mowa z tagiem zaczyna się za „Murakumo: „” (11 kolumn, oryginał miał 10),
  a kolejne wiersze mają to samo wcięcie.
- Dłuższy tekst przechodzi na następną stronę. Nie tniemy treści, żeby tego uniknąć, ale
  **puenta, okrzyk i wyznanie nie mogą się rozpaść na dwie strony**. Wtedy skracamy albo
  przenosimy zdanie do sąsiedniego fragmentu. `tl.py check -v` wypisuje każdy komunikat, który
  ma więcej stron niż oryginał.
- **Menu:** jeden wiersz, najwyżej 68 kolumn. Polskie pozycje zwykle mieszczą się z zapasem.

## 3. Rodzaj gramatyczny i tożsamość

Polski czas przeszły i przymiotniki zdradzają rodzaj, japoński nie. Ta gra niczego nie ukrywa
przed graczem, ale ciało bohatera jest tematem, o którym każdy ma zdanie.

### 3.1 Murakumo
- Jest mężczyzną. **O sobie i o nim zawsze w rodzaju męskim:** „poszedłem”, „byłem
  zmęczony”, „ten agent”. Także w najbardziej kampowych kwestiach i także w zakończeniu nr 3,
  gdy zmieniono mu ciało.
- Kampowość oddajemy **słowami, nie końcówkami**: zdrobnienia („Kenuś”, „Yukinka”), czułe
  wykrzykniki („ojej”, „ach”, „no wiesz”), przeciągnięte samogłoski („Ke-e-nuś”), ☆,
  teatralne didaskalia w nawiasach (§6.5), pieszczotliwe „kochanie”, „skarbie”.
  Nigdy żeńskie formy czasownika.
- Cudze reakcje zostają takie, jakie są: Kenzo „zniewieściały facet” (`m060.7`), Sasame „choć
  na twoim przykładzie widać, że z wyglądu nie da się sądzić” (`m006.10` albo `m007.14`,
  zależnie od gałęzi), Yuki
  „Pan jest mężczyzną, prawda?” (`m015.29`).
- **Goryl bierze go za dziewczynę** (`m074.30`–`m074.50`): mówi do obojga „panienki”,
  „ślicznotki”, a w czasie przeszłym w rodzaju niemęskoosobowym („łaziłyście”). Nie
  „dziewczynki”: to brzmi jak o dzieciach. Po poprawce
  Snake'a (`m074.55`: „Agent z Toanu to facet”) mówi o nim neutralnie.

### 3.2 Reiko i kobieta z prologu
- Reiko to kobieta i jako sekretarka, i jako Fubuki Izumo, więc rodzaj żeński zawsze. Lalka
  bojowa jest „nią” także po zdarciu skóry. Murakumo mówi o niej „metalowa baba”.
- Kobieta z otwarcia (`name.15`, `name.17`, w akapitach 女) zostaje bezimienna: [Kobieta].
  Dziewczyna (娘, `name.16`) też: [Dziewczyna]. Nikt nie nazywa ich Reiko ani Misą.

### 3.3 Reszta
- Hinamura jest mężczyzną (僕). Kandori i Mami są kobietami.
- „？？？” (`m113.3`, `m116.7`) to niewidoczna jeszcze Yuki, a narrator już mówi „drobna kobieta”,
  więc rodzaj żeński wolno.
- Bezdomny C (`m207.9`) mówi jak pyskata kobieta (〜じゃないのさぁ), choć tag tego nie mówi.
  Tag: „Bezdomna C”.
- `m006.29` jest zapisane jako kwestia Murakumo, ale mówi Sasame (zwykłe だ, そうだ z drugiej
  ręki, a Murakumo odpowiada mu grzecznie w `m006.31`). Piszemy „Sasame”.
- `m208.15` ma 女, a chodzi o 娘: przyciągana jest dziewczyna.
- Yuki mówi o sobie w trzeciej osobie, gdy traci panowanie nad sobą („Yuki zaraz…”).
  Zostawiamy to.

## 4. Formy adresatywne

Zasada: japoński styl zwykły → **ty**; です/ます, さん, 先生 wobec obcych i przełożonych →
**pan / pani**; **zmiana** idzie tam, gdzie robi ją japoński, i musi być słyszalna. W wołaczu
imiona zostają w mianowniku („Yuki!”, „Murakumo!”), tytuły idą w wołaczu („szefie”,
„panie doktorze”).

| Kto → do kogo | Forma | Uwagi |
|---|---|---|
| Murakumo → Sasame | „szefie”, pan, uprzejmie z kpiną | za plecami „Maska” (D7); w `m179` i `m183` gniew bez kpiny; raz アンタ (`m179.18`): na jedno zdanie „ty” |
| Sasame → Murakumo | ty, „Murakumo” | 〜たまえ = uprzejmy rozkaz („idź, proszę”, „zechciej…”); w `m183.55` krótkie „Idź.”. Samo ムラクモ, gdy rozkazuje: „Murakumo”; ムラクモ君, gdy jest gładki: „mój drogi Murakumo” (`m045.12`, `m178.6`, `m183.37`) |
| Sasame o innych | „doktor Shinobu”, „Kandori”, „Yasaka Yuki” | 君 przy nazwisku pomijamy |
| Murakumo ↔ Kenzo | ty | Murakumo: „Kenuś”; Kenzo: 貴様 = „ty draniu”, „ty!” |
| Murakumo ↔ Shinobu | ty | ona: „Murakumo”, „ty”. On mówi do niej głównie です/ます z シノブさん; w `m030.45`–`m030.58` i jego mowa, i narracja przechodzą na samo シノブ. Ta zmiana musi być słyszalna: on mówi do niej grzeczniej („Shinobu, proszę cię”, „pani doktor☆”), a w `m030.45`–`m030.58` ostro i bez grzeczności |
| Yuki, Hinamura → Shinobu | „pani doktor” | |
| Shinobu → Yuki | ty, „Yukinka” | |
| Murakumo → Yuki | ty; „Yukinka” → od `m083.11` „Yuki” (`m099.46` to zauważa), raz jeszcze „Yukinka” w `m132.5` | |
| Yuki → Murakumo | D12 | |
| Hinamura ↔ Murakumo | on: pan, „panie Murakumo”; Murakumo: ty, „Hinamura” | |
| Murakumo ↔ Reiko | oboje pan / pani, ona z drwiną; Murakumo przechodzi na „ty” od `m134.3` („Co zrobiłaś mojej partnerce?!”) | Fakty: Reiko raz przed demaskacją mówi zwykłą formą (`m074.9`), a po niej głównie zwykłą z 貴方, z przebłyskami keigo (`m134.6`, `m165.0`). Po demaskacji Reiko mówi „ty”, z wyraźnymi kpiąco-grzecznymi zdaniami na „pan” tam, gdzie wraca keigo, żeby przejście było słychać |
| Murakumo ↔ Kusanagi | oboje pan; Murakumo od `m149` „ty” („konował”) | Kusanagi: 貴方 (`m051.7`) → 君 / ムラクモ君 z ですぞ (`m162.4`) → 貴様 (`m176.74`). Po polsku „panie Murakumo”, protekcjonalnie, a w `m176.74` upadek na „ty” |
| Reiko, Kusanagi → Yuki | ty, „panienko” (お嬢さん) | |
| Murakumo ↔ Mami | on: ty, „Mamiś” (D3); ona: pan, „panie Murakumo”, „pan Amano” (`m070.6`) | |
| Yuki ↔ Mami | najpierw pani („Yasaka Yuki, Wydział Informacji”), potem ty | |
| Murakumo ↔ Goryl, Snake, Shikakura | ty | Shikakura: あんた = „ty” |
| Ochroniarze, bezdomni | ty | |

## 5. Imiona: zapis i odmiana

**Zapis (D1), nazwisko pierwsze:** Amano Murakumo, Yasaka Yuki, Sasame Josetsu, Tanaka Kenzo,
Yata Shinobu, Hinamura, Takama Reiko, Izumo Fubuki, Kusanagi Ken, Inaba Mami, Misaki Misa,
Yajima Takao, Kandori, Shikakura, Goryl (ゴリ), Snake (スネーク i スネイク).

**Odmiana (zatwierdzona):**

| Imię | Odmiana |
|---|---|
| Murakumo, Kenzo, Amano | **nieodmienne** („z Murakumo”, „Kenzo nie ma”), jak zwykle japońskie imiona męskie na -o |
| Sasame | przymiotnikowo jak nazwiska na wymawiane -e: Sasamego, Sasamemu, z Sasamem, o Sasamem. Zwykle z tytułem: „szefa Sasamego” |
| Kusanagi | przymiotnikowo: Kusanagiego, Kusanagiemu, z Kusanagim, o Kusanagim |
| Hinamura, Shikakura, Tanaka | jak rzeczowniki na -a: Hinamury, Hinamurze, Hinamurę, Hinamurą |
| Snake | Snake'a, Snake'owi, Snake'iem, o Snake'u |
| Goryl | Goryla, Gorylowi, Gorylem, o Gorylu |
| Misa | Misy, Misie, Misę, Misą |
| Yuki, Shinobu, Reiko, Fubuki, Mami, Kandori | nieodmienne |
| żeńskie nazwiska (Yasaka, Takama, Izumo, Misaki, Inaba) | nieodmienne |
| Toan | Toanu, Toanowi, w Toanie |
| Kusanagi (szpital) | „szpital Kusanagi”, „w szpitalu Kusanagi” |

## 6. Konwencje zapisu

### 6.1 Interpunkcja
- **Wielokropek:** `...` (trzy kropki ASCII). Oryginalne `…`, `……`, `…………` = `...`; bardzo długie
  pauzy (sześć i więcej znaków) = `......`. Kwestia z samych kropek zostaje kwestią z samych
  kropek: `Murakumo: „......”`.
- `？？？` = `???`, `！！！` = `!!!`, `！？` = `?!`. Pełnoszerokie cyfry i litery = ASCII.
- **Myślnik** to półpauza ze spacjami: `słowo – słowo`. Kwestia urwana kończy się wielokropkiem.
- `～` (przeciągnięcie) zastępujemy powtórzeniem samogłoski („No to cze-eeść”). Tak samo
  oryginalne `#$$$$%`: krzyk to „Aaaaa!” (nie „Kyaaa”, to transliteracja),
  „Ciiiiisza”, „Do widze-e-e-nia”. Zasady dla jęków jeszcze nie ma (§13).

### 6.2 Mowa
- **Z tagiem:** tłumaczymy samą kwestię. Imię i nawiasy dokłada silnik (D4).
- **W akapicie:** `Imię: „kwestia”` z imieniem z tabeli §7 i tymi samymi nawiasami. Kwestia,
  która w oryginale zajmuje kilka wierszy, łamie się ręcznie (`\n`), a każdy następny wiersz
  zaczyna się twardymi spacjami U+00A0 do kolumny za „ (D5): Murakumo 11, Yuki 7, Sasame 9,
  Shinobu 10, Kenzo 8, Reiko 8, Kusanagi 11, Hinamura 11, Mami 7, Goryl 8. Przykład (`m013.20`):

      Murakumo: „Zanim ta rozpustna lekarka sprowadzi ją na manowce,\n
      ␣␣␣␣␣␣␣␣␣␣␣muszę ją poprowadzić prostą ścieżką damsko-męskich\n
      ␣␣␣␣␣␣␣␣␣␣␣znajomości! Nie mogę tracić czasu!

  a kwestia kończy się dopiero w następnym fragmencie, `m013.24`: `␣␣␣␣␣␣␣␣␣␣␣Naprzód!!!”`.
  (␣ = U+00A0; w pliku to jeden wiersz z `\n`.) Zamykający ” stawiamy tam, gdzie oryginał
  stawia 」, nawet w innym fragmencie. Uwaga na edytory, które zamieniają U+00A0 na zwykłą
  spację: wtedy wcięcie zniknie bez ostrzeżenia.
- **Szept i myśli w nawiasach** (`ムラクモ（いま話しづらいなら…）`, `ユキ（………ありがとう………）`):
  `Murakumo: (Jeśli teraz trudno ci mówić, zadzwoń później.)` — nawias zamiast cudzysłowu,
  jak w oryginale.
- **Głos nagrany** (terminal na biurku: `m037`, `m045`; w oryginale `『』`): **« »**, np.
  `Sasame: «Dzień dobry, Murakumo. Znowu spóźniony.»`, a cytaty w nagraniu w „ ”. Bloki
  zeznań z raportu Kenza (`m037.9`–`m038.3`) też w « ».
- **Cytat w kwestii** (`『ケンちゃん』`, `『住む世界が違う』`): « », czyli polski cudzysłów
  wewnętrzny: „Przestań mówić do mnie «Kenuś»!”.

### 6.3 『』 poza mową
- Nazwy i terminy przy pierwszym użyciu: „ ” (`『首都公安局』` → „Stołeczne Biuro Ochrony
  Publicznej”, `『ＵＩＡ・氷翼』` → „UIA – Lodowe Skrzydło”). Potem bez cudzysłowu.
- Słowa przytoczone w narracji (`『しな』`, `『住む世界が違う』`, `『処女だ！！』`): „ ”.
- **Dźwięki** (`『バタン！！』`, `『ガン！ガン！』`, `『ポカリ☆☆』`): bez cudzysłowu, jako osobny
  fragment: „Trzask!!”, „Bach! Bach!”, „Bęc☆☆”.

### 6.4 Narracja
- Narracja Murakumo w **czasie przeszłym**, w pierwszej osobie, potocznie i szybko. Komentarze
  do czytelnika i stałe fakty w teraźniejszym („Te slumsy nazywają Trzynastką.”). Japońskiego
  mieszania czasów nie kopiujemy na chybił trafił.
- **Walki i sceny erotyczne** oryginał pisze blokami w czasie teraźniejszym (`m075`–`m078`,
  `m165`–`m176`). Tam cały fragment może iść w czasie teraźniejszym narracyjnym, bo czas
  przeszły je usypia (przewodnik ogólny §4.5).
- W walkach czasowniki dokładne i krótkie: „wykręciłem nadgarstek”, „kopnąłem w krocze”,
  „uderzyłem otwartą dłonią w szczękę”.
- `ボク` / `僕`: jedno „ja”. Różnica w piśmie nic nie znaczy.

### 6.5 Didaskalia, symbole, cenzura
- ☆ zostaje tam, gdzie stoi (2 kolumny), także w kwestiach Reiko i Yuki.
- Didaskalia w nawiasach krótko, jak w oryginale: rzeczowniki i dźwięki, nie przymiotniki ani
  słowa z dzisiejszych memów: （しょぼん） „(chlip)”, （ぷんぷん） „(fuk, fuk)”, （汗汗汗） „(pot, pot,
  pot)”, （汗タラリ） „(kropla potu)”, （ニヤリ） „(uśmieszek)”, （にこっ☆） „(uśmiech☆)”,
  （ほえ～ほえ～） „(ślinka)”, （かっくん） „(oklapł)” (`m042.6`), （怒々々々） „(grr, grr, grr)”,
  （発想の飛躍） „(skok myślowy)”, （もがもが） „(szamotanina)”, （小声で） „(półgłosem)”,
  （くっそう～） „(niech to szlag)”, （おいおい） „(no bez przesady)”, （エッヘン） „(ehem)”, （タメ息）
  „(westchnienie)”.
- Grawlix `○♀♀＠＊☆♂だ！` (`m045.20`) = `○♀♀＠＊☆♂!`; Sasame cytuje go identycznie (`m045.22`).
- `○` to cenzura epoki, w słowach wulgarnych i klinicznych tak samo (オマ○コ, クリ○リス, アヌ○).
  Zostaje `○` w polskim odpowiedniku (§11).
- Szum ze znaków (`m100.48` duszony Hinamura, `m116.7` stłumiony krzyk) zostaje szumem ze znaków.

### 6.6 Epoka
- Gra jest z 1995 roku, akcja dzieje się w latach 2080. Slang **nie nowszy niż połowa lat 90.**
  Modne japońskie zapożyczenia bohatera (ナイスボディー, ブルー, ノーマル, アイデンティティ,
  ダークネスな建物) oddajemy modnymi zapożyczeniami z tamtych lat, nie dzisiejszymi
  (przewodnik ogólny §4.15).
- „Siema!” albo „Cześć!”, nie „Siemka” (to lata 2000.). パーソナルデッキ = „dek”, słowo polskiego
  cyberpunku tamtych lat.

### 6.7 Mowa katakaną
- To barwa głosu, nie pisownia (przewodnik ogólny §4.14): wielkie litery (D23).

### 6.8 Liczby i miary
- Godziny według D20. „2 m”, „180 cm”, „2 km”. ４５口径 = „czterdziestkapiątka” albo
  „kaliber .45”, ３８口径 = „kaliber .38”.
- 65 700 godzin, ze spacją. „Klasa B”.
- Ekrany wyszukiwania (`m035.18`, `m062.0`, `m104.29`): układ i nawiasy `【】` zostają, treść po
  polsku, a etykiety z dwukropkiem: `Nazwisko: Misaki Misa   Płeć: kobieta   Wiek: 23`.

## 7. Tagi mówiących

| Klucz | JP | PL |
|---|---|---|
| `name.00`, `name.09` | ムラクモ, ムラウモ | Murakumo |
| `name.01` | ケンゾウ | Kenzo |
| `name.02` | ササメ | Sasame |
| `name.03` | ヒナムラ | Hinamura |
| `name.04` | ユキ | Yuki |
| `name.05`, `name.06` | シノブ, シノフ | Shinobu |
| `name.07` | レイコ | Reiko |
| `name.08` | クサナギ | Kusanagi |
| `name.10` | マミ | Mami |
| `name.11` | ゴリ | Goryl |
| `name.12`, `name.13` | スネーク, スネイク | Snake |
| `name.14` | シカクラ | Shikakura |
| `name.15`, `name.17` | 女 | Kobieta |
| `name.16` | 娘 | Dziewczyna |
| `quote.open` / `quote.close` | 「 / 」 | `: „` / `”` (D4) |

Imiona w akapitach: te same, oraz カンドリ = Kandori, ミサ = Misa, 警官 = Policjant, 警備員Ａ/Ｂ =
Ochroniarz A / Ochroniarz B, ホームレスＡ/Ｂ/Ｃ = Bezdomny A / Bezdomny B / Bezdomna C, ？？？ = ???.
`m006.29` = Sasame (§3.3). `m179.10` ma tag
`name.08`, a mówi Sasame. Tego nie da się poprawić w przekładzie (przewodnik ogólny §3).

## 8. Menu

Oryginał formułuje wybory jako decyzje bohatera. Proponuję pierwszą osobę czasu
teraźniejszego tam, gdzie oryginał jest zdaniem („Idę prosto do szefa”), i rzeczownik tam,
gdzie jest etykietą („Pancerz kuloodporny”). Bez wcięć i bez wyrównywania spacjami.

Menu mówią głosem bohatera i niosą żarty: `menu03.1` (能面局長), `menu11.1` (貞操の危機だ！,
„cnota w niebezpieczeństwie!”), `menu11.2` (しなを作り, jak w `m001.32`). `menu40.2` i jego
wypowiedziane powtórzenie w `m164.0` / `m166.0` to ta sama kwestia i dostają te same słowa.

**Stałe pozycje:**

| Klucz | JP | PL |
|---|---|---|
| `menu43.1`–`4` | 最初から始める / 途中から始める / ミュージックモード / ＣＲＹＳＴＡＬ ＳＯＦＴからのお知らせ | Nowa gra / Wczytaj grę / Muzyka / Komunikat Crystal Soft |
| `menu41.1`–`4` | １番にセーブする … / セーブしない | Zapisz w miejscu 1 … 3 / Nie zapisuj |
| `menu42.1`–`4` | １番をロードする … / ［メニューに戻る］ | Wczytaj z miejsca 1 … 3 / [Powrót do menu] |
| `m204.0`, `m205.0` | セーブしますか？ / 不正なセーブデータです | Zapisać grę? / Nieprawidłowy zapis. |
| `menu19.1`–`4` | 防弾用 / 格闘用 / 対ビーム粒子用個人装甲 / 絶縁スーツ | Pancerz kuloodporny / Pancerz do walki wręcz / Pancerz antywiązkowy / Kombinezon izolacyjny |
| `menu38.1`–`4` | 散弾 / 徹甲弾 / ビーム粒子弾 / 冷凍弾 を装填する | Ładuję śrut / Ładuję pociski przeciwpancerne / Ładuję pociski wiązkowe / Ładuję pocisk zamrażający |
| `menu22`–`37` | 白い結晶の粉 / 赤い / 黒いデータ・ファイル / 壁に掛けられたボード を調べる | Sprawdzam biały krystaliczny proszek / czerwony plik danych / czarny plik danych / tablicę na ścianie |
| `menu40.2` | テメーラ！ブチ殺す、死んでも飲むか！ | Gnoje! Pozabijam! Prędzej zdechnę, niż to połknę! |

Oryginał pisze `ボードをを` (podwójne を). To literówka, której przekład nie powtarza.

## 9. Głosy po polsku

| Postać | Polszczyzna |
|---|---|
| Murakumo (powierzchnia) | Lekko, bezczelnie, kokieteryjnie: „Kenuś☆”, „Siema!”, „ojej”, „no wiesz”, przeciągnięte samogłoski, didaskalia. Do Sasamego uprzejmie z kpiną („Tak jest, szefie, już lecę☆”). Kłamie gładko i bez przekonania. |
| Murakumo (gniew, walka) | Krótko i twardo: „Ty gnoju!”, „Pozabijam!”, „Łapy precz!”. Kampowe znaczniki znikają. |
| Murakumo (powaga) | Prosto, bez ozdobników: `m030.45` „A jak nie dla zabawy? Jak na serio? To wtedy nawet taki jak ja może być?!” (ボクでも przygotowuje `m031.3`), `m185.28` „Ciebie kocham, rozumiesz?! Jak raz to za mało, mogę to powtarzać sto razy, tysiąc razy!” (好き = „kocham”, D21; お前 to jego jedyne szorstko-czułe „ty” do niej, stąd nacisk na „ciebie”). |
| Yuki | Grzecznie, poważnie, ciepło: „Przepraszam!”, „Proszę mi dać dane.”, „Nie mogę darować przestępstw, w których kobiety traktuje się jak narzędzia do seksu.” (`m027.8`; 道具 = „narzędzie”, a 玩具 Reiko = „zabawka”, i te słowa się nie mieszają). Nie dziecinnie: jej przeprosiny to poczucie winy, nie słodycz. Do końca nalotu grzecznie (D12), swobodnie dopiero w epilogu. ずるい zawsze **„nie fair”** („To nie fair...”, `m029.19`, `m118.22`, `m191.37`). |
| Sasame | Chłodno, dokładnie, pełnymi zdaniami, z suchą ironią: „Twoje zawieszenie skończyło się dziś o 00:00. Zostałeś o tym powiadomiony.” `m008.10`: „Na bezpańskiego psa bez obroży trzeba zapolować.” `m098.29`: „Ciało owszem.” `m183.55`: „Idź. Nie jestem już twoim szefem ani przełożonym. Jestem dla ciebie obcym człowiekiem.” Nigdy ciepło przed `m179` i nigdy złowrogo. |
| Shinobu | Na przemian ciepło-zaczepnie i szorstko po koleżeńsku: „Żadne «ojej»! Szukam cię po całym Biurze, a ty się wleczesz! Rusz się!” (`m016.5`); do Hinamury „Hinamura! Nic nie widziałeś, jasne?!”. |
| Kenzo | Głośno, urzędowo, z oburzeniem (cytuje powitanie Murakumo, więc idzie za §6.7): „Murakumo! Jakie «siema»?! Co zawieszony agent robi na miejscu zbrodni?!” Na nagraniu (`m037`) jak protokół: „Świadek zeznaje, co następuje.” |
| Hinamura | Uprzejmie, z przytykiem: „Pan na nadgodzinach? Jutro będzie padać.” Jąkanie: „To... to... to... to...” (`m019.0`). |
| Reiko (maska) | Lodowato uprzejma sekretarka: „Nazywam się Takama Reiko, jestem sekretarką doktora Kusanagiego Kena.” Drwina pod spodem: „Hm, hm... Partacz z Toanu.” (`m052.48`), „Och, przepraszam, nie zauważyłam. Ohoho...” (`m079.10`). |
| Reiko (bez maski) | `m134.23`: „Tak. To ja jestem Fubuki Izumo. Doktor Kusanagi przywrócił mnie do życia. I dał mi najsilniejsze ciało, jakie istnieje!” Potem salonowa dominatorka: ☆, „Hi, hi, hi”, piskliwe キャハハ (`m134.46`), a rozkazy w damskich formach: 眺めてらして☆ (`m150.19`), 嘘おっしゃい (`m154.1`), 見えなくてよ (`m154.17`), 御上げ (`m157.12`). Okrucieństwo z salonu, nie szczekanie: „Niechże pan sobie popatrzy☆”, „Proszę nie kłamać!”, „Jakoś nie wygląda pani na zawiedzioną”. Raz mówi jak maszyna (`m168.18`, D23). |
| Kusanagi | Napuszony, kliniczny: „Mięsień obszerny boczny i półścięgnisty uszkodzone. Tętnica udowa pęknięta. Kość udowa złamana. Cztery tygodnie leczenia, powiedziałbym.” (`m148.1`). Do Murakumo „panie Murakumo”. Gdy traci twarz: „Moja twarz! Twarz genialnego lekarza!”. |
| Mami | Cicho, z wahaniem: „Ja... przepraszam! Ja nic nie wiem!” |
| Goryl | Prymitywnie, lubieżnie, bełkotliwie i przeciągle, jak komiksowy osiłek (Murakumo: 漫画みたいな奴): „Ihihihi, panienki, jak będziecie tu tak łazić, to zaraz będziecie piszczeć.” Groźby: „Ale tobą cisnę!” (nie „Ale cię rzucę!”, to brzmi jak zerwanie). |
| Snake | Krótko i chłodno: „Bez nakazu ani rusz, co?”; potem tylko krzyk. |
| Shikakura | Spokojnie, z rozbawieniem: „Ha, ha, ha! Podobasz mi się.” |
| Bezdomni | A i B lekko po wiejsku, bez konkretnej gwary: „Co jest, ludzie?”, „Patrzajcie no!”. C jak pyskata baba. |
| Kobieta (otwarcie) | Ten sam głos co Reiko bez maski: władcze damskie formy rozkazu (お見せっ, お言い, 覚悟おし = „Szykuj się.”; tę samą formę ma Shinobu, `m058.31` お行き), nie archaizm. |

**Echa.** Pełna lista: biblia §6. Każde echo dostaje jedno polskie
brzmienie, wpisane tutaj przy pierwszym przekładzie.
- 自分を責めるな (`m081.44` → `m083.11` → `m185.28`): „przestań się obwiniać”.
- ストレス: zawsze „stres”.
- オモチャ / 玩具: zawsze „zabawka”; 道具 (Yuki): „narzędzie”.
- 住む世界が違う: „inne światy” (`m018.19`: „Wy żyjecie w zupełnie innych światach.”; `m031.5`:
  słowa Shinobu o „innych światach” nabrały innego znaczenia). W `m018.19`:
  „ona jest z innego świata niż ty”.
- 甘いコーヒー: zawsze „słodka kawa” (na gałęzi „zostaw ją”, `m032`, i w nalocie, `m118`;
  w `m029.16` jest zwykła kawa).
- **Bliźniaki, nie echa** (różne gałęzie, gracz widzi jedno z dwojga): `m029.5` / `m032.14`:
  „Śledztwa często stają w martwym punkcie. Człowiek się głowi, szamocze, miota, a i tak prowadzi
  je dalej. Na tym polega nasza robota.” W `m032.14`–`m032.20` zdanie jest rozcięte milczeniem
  Yuki i ma dopisek 時々は泣くこともネ☆, więc polskie zdanie musi dać się rozciąć w tym samym
  miejscu. `m061.16` to parafraza (付き物): Yuki: „Przecież śledztwa zawsze kiedyś stają w
  martwym punkcie!” → `m061.24` „...To przecież moje słowa z wczoraj!”. `m031.3` = `m033.3`:
  „...W slumsach się urodziłem, w slumsach wychowałem, w slumsach zabijałem.”
- `m185.28` i `m202.16`: to samo brzmienie, różni się tylko końcówka, jak w oryginale
  (言い続けたっていい / 言い続けてやる): „Ciebie kocham, rozumiesz?! Jak raz to za mało, mogę to
  powtarzać sto razy, tysiąc razy!” / „…będę to powtarzał sto razy, tysiąc razy!”.
- `m017.0` = `m057.62`: „Shinobu, ucho! Ucho!! Au! Au! Au! Au! Boli!!”.

**Śmiechy i okrzyki:**

| JP | PL |
|---|---|
| ハハハ, あははは | Ha, ha, ha! |
| オホホホ, おほほほ, おっほほほ (Reiko) | Ohohoho! |
| うふふ, ウフフ (Reiko, kobieta; ウフフフ też Kusanagi, `m159.16`) | Hi, hi, hi (Kusanagi: He, he, he...) |
| キャハハハ (Reiko, `m134.46`; Yuki ma キャハ☆ w `m042.12`) | Hi-hi-hiii! (piskliwy, dziewczęcy; wyniosły jest オホホ) |
| フフフ (Reiko, `m052.48`) | Hm, hm... (stłumione parsknięcie pogardy) |
| クククク (Kusanagi, Hinamura) | He, he, he... |
| ムフフ, えへへ (Murakumo) | He, he, he☆ |
| イヒヒヒ, ぐひひぃ (Goryl) | Ihihihi! |
| わははは (Shikakura) | Ha, ha, ha! |
| ちっ, チッ | Tss! |
| くそっ, チクショ | Cholera...! / Szlag...! |
| うげ～ | Bleee... |
| 破！ | Ha! |
| ムッキィィィ | Grrr! |
| ぐはっ, ぐはぁ | Gha! / Aagh! |
| ウギャアアア | Aaaaargh! |

## 10. Gry słów — kandydaci

Zasada (przewodnik ogólny §5): żart, którego nie da się przenieść, zastępujemy żartem tej
samej wielkości w tym samym miejscu. Wpisy bez dopisku są zatwierdzone (2026-11-17); „otwarte”
= do rozstrzygnięcia przy tłumaczeniu sceny, z wpisem tutaj.

| Klucze | Oryginał | Polski |
|---|---|---|
| `m005.28`–`m005.35` | 穴堀工事 (roboty drogowe) / 穴掘り z rudą | „trzy rozkopane ulice” → „Na twojej trasie nikt nic nie rozkopywał. Rozkopywałeś najwyżej jedną rudą panienkę.” — otwarte, do wygładzenia |
| `m018.23`, `m042.6` | 暴れん坊将軍 (serial, przydomek penisa) | **„Rozbrykany Szogun”** (暴れん坊 to rozrabiaka); „Rozbrykany Szogun ma dziś zamknięte☆” |
| `m021.9` | 天にも昇る天使な気分 | „Czujesz się jak anioł w siódmym niebie.” |
| `m012.8` | 現場百回 | „Śledczy wraca na miejsce zbrodni sto razy!” (nie bezosobowo: „wraca się na miejsce zbrodni” brzmi jak przysłowie o mordercy) |
| `m019.5` | イイテンキダナ katakaną | „ŁADNA DZIŚ POGODA...” (D23) |
| `m036.2`–`m036.5` | 明日は雨だ / 人で天気予報 | „Pan na nadgodzinach? Jutro będzie padać.” – „Nie rób sobie ze mnie barometru.” |
| `m048.23` | 耳年増 | „stara plotkara” (w kontekście: „wiesz od Yuki” i przytyk do wieku) |
| `m053.29`, `m053.52` | 叩くとホコリが出る | 叩く i ホコリ zostają: „jak go przetrzepać, poleci kurz” → „Powiedziałem tylko, że jak Kusanagiego przetrzepać, poleci kurz.” – „Czyli mam trzepać, tak?” |
| `m059.5`–`m060.1` | ホモに目覚めて / お尻を貸せ | „Czyżby Kenzo odkrył w sobie geja?” – „Jestem normalny, Kenuś, tyłka ci nie pożyczę☆” |
| `m063.16`–`m064.2` | お尻 | „Wcale nie patrzyłem na żadne pupy!” – „Na jakie pupy?” |
| `m074.17`–`m074.26` | 脳味噌まで筋肉増強剤 / スネークより早く抜いても | „Sterydy wstrzykuje sobie nawet do mózgu.” / „Możesz wyciągnąć broń szybciej niż Snake, ale szybciej nie strzelisz.” |
| `m075.27` | 男を辞めるなら良い医者 | „Jakbyś chciał przestać być facetem, znam dobrego lekarza☆” |
| `m075.65`, `m076.67` | 南国系の笑み | „uśmiech jak z tropików” |
| `m100.30`–`m100.44` | エッチしてればストレス知らず (gałąź Shinobu) | „Pan przy tych swoich figlach stresu nie zna.” – „Figle! O to chodzi!” (D15) |
| `m110.9` | 面倒だ！全部もって行け | „Eee, za dużo zachodu! Biorę wszystko!” (面倒 to kłopot, nie czas) |
| `m170.27`, `m174.10`; `m170.29`, `m175.0` | フェラチオ / 射精する | „Jakbyś mi robiła laskę!” (D13; ta sama rodzina słów co `m157.2`, bo to echo); „Ściągnąłem spust i spuściłem jej w mózg pocisk przeciwpancerny...” (`m175.0`: „ołów”) |
| `m176.77` | 歯医者でも開業 | „Otwórz gabinet dentystyczny. Twoja gęba nada się na eksponat.” |
| `m179.34` | 神様に感謝 | „Szefie! Niech pan dziękuje Bogu, że akurat nie władam prawą ręką!” |
| `m193.42` | 胸の前で手が組めない | „Z takimi nie da się nawet założyć rąk na piersi.” |
| `m045.12`–`m045.24` | przewidziane przekleństwo | jak w oryginale, grawlix bez zmian (§6.5) |

## 11. Sceny dla dorosłych

- Biblia §8 wymienia wszystkie sceny i ich zakresy kluczy. Tłumaczymy je jak resztę gry, z tą
  samą dosłownością co po japońsku: bez pruderyjnych eufemizmów i bez przelicytowania. Farsa
  zostaje farsą (Shinobu, `m018`), czułość czułością (park, noc poślubna), okrucieństwo
  okrucieństwem (laboratorium, niewola, otwarcie).
- Słownictwo idzie za sceną (D13), jak w oryginale, który nie jest ani kliniczny, ani po prostu
  wulgarny (biblia §8):
  - park płochliwie i miękko (女性自身, ピンクの突起, キスの雨), z klinicznymi zapożyczeniami
    (ヴァギナ, ラビア);
  - laboratorium groteskowo (双頭の魔物, イモムシ, 肉穴, 凶器; nasienie to 汚物);
  - noc poślubna kwieciście (珊瑚の粒, 花びら, 愛の泉, 男のくさび; nasienie to 熱い思い);
  - niewola pornograficznym slangiem w ustach Yuki (ザーメン, チン○ン, ハメられ);
  - otwarcie słownikiem S&M (華芯, 愛汁, 黄金の雫);
  - オチンチン Reiko po polsku słowem z pokoju dziecięcego, bo umniejsza.
- `○` to cenzura epoki, także w słowach klinicznych (クリ○リス, アヌ○): zostaje `○` w polskim
  odpowiedniku.
- Dźwięki w zdaniach (`『チュパッ』と…`) i jęki należą do tego rejestru (§13).
- **Sześć fragmentów tłumaczy redaktor:** `m084.0`, `m085.10`, `m086.0`, `m089.0`, `m090.0`,
  `m093.45` (scena w parku; narracja porównuje ciało Yuki do dziewczęcego albo dziecięcego).
  Plik: `translation/editor_pl.tsv` (same klucze, nie trafia do paczki); japoński do czytania:
  `build/tl/editor_pl_ja.tsv`. Po przetłumaczeniu: `tl.py put ../text/translation/vangel_pl.tsv
  ../text/translation/editor_pl.tsv`. Model tych wierszy nie pisze ani nie poprawia, sprawdza
  je tylko mechanicznie (`tl.py check`).
- 美少女 i 少女の香り (`m158.23`, `m184.45`, `m186.0`) to zwykłe określenia młodej kobiety:
  „piękna dziewczyna”, „dziewczęcy zapach”.
- Kto tłumaczy `m202.7`–`m202.16`, musi użyć brzmienia `m185.28` (§9, echa).

## 12. Próbka kalibracyjna

Do przetłumaczenia na próbę, po decyzjach z §0: prolog (`bi.prologue.0`–`3`), rozdział 1
(`m001`–`m008`: Kenzo, Sasame, narracja, mowa w akapicie i z tagiem) i pierwsze spotkanie z
Yuki i Shinobu (`m013`–`m017`). Cel: sprawdzić w grze nawiasy (D4), wcięcia (D5), zdrobnienia
(D3), ton Murakumo w obu rejestrach i długości. Po uwagach redaktora próbka staje się
wzorcem.

## 13. Otwarte sprawy

- Zasada dla jęków i dźwięków w zdaniach scen erotycznych.
- Erotyczna część słownika (§14, „do ustalenia”).
- Gry słów oznaczone „otwarte” w §10.
- Lint dla zasad tego przewodnika: imiona w mowie w akapicie zgodne z `name.NN`, nawiasy,
  twarde spacje we wcięciach, rodzaj męski Murakumo, echa z §9, zakazane słowa z D6 i D13,
  zmiana „Yukinka” → „Yuki” od `m083.11` (poza `m132.5`), „pan” Yuki według D12.
- Słownik niżej rośnie w trakcie przekładu; każdy nowy termin trafia tu z kluczem.

## 14. Słownik terminów

Zatwierdzony razem z §0 (2026-11-17); wpisy „do ustalenia” i „otwarte” czekają na scenę.

| JP | PL | Uwagi |
|---|---|---|
| 首都公安局 / 都安 | Stołeczne Biuro Ochrony Publicznej / Toan | D6; potocznie „Biuro”; `bi.prologue.3`, `m001.20` |
| 局長 / 能面局長 | szef / szef Maska | D7 |
| 人権課 | Wydział Praw Człowieka | wydział Murakumo; ironia nazwy zostaje |
| 情報課 | Wydział Informacji | |
| 鑑識課 / 鑑識 | Wydział Kryminalistyki / kryminalistyka | |
| 防テロ課 | Wydział Antyterrorystyczny | |
| 火器管理室 | zbrojownia | |
| 捜査員 | agent (Toanu) | |
| 新人 | nowa, świeżo przyjęta | o Yuki |
| 謹慎 | zawieszenie | „jestem na zawieszeniu” |
| 契約書 / ６５７００時間 | umowa / 65 700 godzin | |
| 終身刑 / 仮出所 | dożywocie / warunkowe zwolnienie | |
| 殺人許可証 / Ｂ級 | licencja na zabijanie / klasy B | |
| 警視庁 | policja stołeczna, „policja” | bez nazw polskich komend |
| 特殊突撃部隊 | Specjalny Oddział Szturmowy (policji) | |
| 制服警官 | mundurowi | |
| 捜査令状 | nakaz | |
| 公務執行妨害 | utrudnianie czynności służbowych | `m079.7` |
| 指名手配 / 職務質問 | list gończy / legitymowanie | |
| ボディ・ドラッグ / セックス・ドラッグ | żywy narkotyk / seks-narkotyk | D8 |
| 人体改造 | przeróbka ciała; 人体改造手術 = operacja przerabiająca ciało | |
| 奴隷市 / 人身売買 | targ niewolników / handel ludźmi | |
| フリー・セックスゾーン | Strefa Wolnego Seksu | |
| バージン・エンジェル | Virgin Angel | D10 |
| 媚薬 | afrodyzjak | |
| コンバット・ドール / スタチュウ２Ｈ | lalka bojowa / Statue 2H | D9 |
| メタル女 / ゼンマイ仕掛のメタル女 | metalowa baba / nakręcana metalowa baba | |
| 人工皮膚 / 軽チタン装甲 / 対光学兵器用コーティング | sztuczna skóra / pancerz z lekkiego tytanu / powłoka chroniąca przed bronią optyczną | wskazówki, biblia §2.2 |
| スタンガン | paralizator | |
| 個人装甲 | pancerz osobisty | menu 19 w §8 |
| 絶縁スーツ | kombinezon izolacyjny (do prac kablowych) | |
| 特殊弾丸 | amunicja specjalna | |
| 散弾 | śrut | „kulki łożyskowe” (`m110.2`) |
| 徹甲弾 (też 鉄鋼弾, `m040.10`, `m109.4`) | pocisk przeciwpancerny | 鉄鋼弾 to literówka |
| ビーム粒子弾 | pocisk wiązkowy | |
| 冷凍弾 / プロトタイプ | pocisk zamrażający / prototyp | jest tylko jeden (`m109.4`) |
| ４５口径 / ３８口径 | czterdziestkapiątka, kaliber .45 / kaliber .38 | |
| ニードルガン | pistolet igłowy | |
| トンファー | tonfa | |
| 掌打 / 手刀 / 金的 | uderzenie otwartą dłonią / cios kantem dłoni / krocze | |
| ＤＮＡナンバー | numer DNA | |
| パーソナルデッキ | dek | §6.6 |
| 復元ＣＧ | komputerowa rekonstrukcja twarzy | |
| データバンク | bank danych | |
| 検死 / 検死医 | sekcja zwłok / lekarka sądowa | |
| 脳死 / 拒否反応 | śmierć mózgu / odrzucenie | |
| 有機コンピューター | komputer organiczny | `m099.24` |
| 脳移植 | przeszczep mózgu | |
| マインド・コントロール / バイオＡＩチップ | kontrola umysłu / bioczip SI | |
| ウロボロス計画 / 新世紀宇宙開発計画 | projekt Uroboros / Program Kosmiczny Nowego Stulecia | |
| プリズンプロジェクト | projekt „Więzienie” | |
| 浦和国際ホテル / 浦和国際会議 | Międzynarodowy Hotel Urawa / konferencja w Urawie | |
| ＮＡＳＡ | NASA | |
| ＵＩＡ・氷翼 | UIA – Lodowe Skrzydło | alternatywa „Hyoyoku” |
| 国際派遣軍 機甲陸兵団 特殊陸戦部隊 少将 | Międzynarodowe Siły Ekspedycyjne, Korpus Pancerny Wojsk Lądowych, Specjalna Jednostka Lądowa, generał dywizji | `m062.0` |
| 新宿都庁ビル爆破未遂事件 / 宇宙開発局襲撃事件 | próba wysadzenia ratusza w Shinjuku / atak na Agencję Rozwoju Kosmosu | |
| １３号地スラム街 | slumsy Trzynastki (na sztucznym lądzie nr 13) | |
| ビックバード | Big Bird (lotnisko) | |
| 人工工業島郡 | sztuczne wyspy przemysłowe | |
| 旧荒川湾岸地区Ｄブロック | dawna dzielnica nadbrzeżna Arakawa, blok D | Arakawa to rzeka, nie zatoka |
| 首都高速 / 湾岸線 / ルート３５７ | autostrada stołeczna / trasa nadbrzeżna / trasa 357 | |
| 草薙病院 / 院長 | szpital Kusanagi / dyrektor (szpitala) | |
| 旧病棟 | stare skrzydło | |
| 資料室 / 実験室 | archiwum / laboratorium | |
| 電子ロック | zamek elektroniczny | |
| 脳外科 / 人体機械工学 | neurochirurgia / inżynieria biomechaniczna | |
| 看護婦 / 準看護婦 / 正規の看護婦 | pielęgniarka / pielęgniarka stażystka / dyplomowana pielęgniarka | `m072.15` |
| カルテ / 火葬 | karta choroby / kremacja | |
| ボディ・ドラッグ調整カルテ | karty dostrajania żywych narkotyków | `m122.0` |
| 機械への、脳移植後のストレス発散状況について | O rozładowywaniu stresu po przeszczepie mózgu do maszyny | `m123.0` |
| 襲撃計画 / 内通者 | plan ataku / wtyczka | |
| 静止衛星 | satelita geostacjonarny | `m179.26` |
| 二個中隊 | dwie kompanie | |
| 森林公園 / コテージ | park leśny / domek z bali | `m081.3` |
| ロッジ / 暖炉 | chata / kominek | epilog |
| 死亡届 / 戸籍 / 森林管理官の第二種免許 | akt zgonu / nowy wpis do rejestru rodzinnego / licencja leśniczego drugiego stopnia | `m183.50`; „rejestr rodzinny”, nie „metryka”, żeby trzymał się z 籍こそ入れていない (`m184.17`) |
| 籍を入れる | wpisać do rejestru rodzinnego | `m184.17`, w parze z 戸籍 |
| 整形医 | chirurg plastyczny | `m184.8` |
| 合成皮膚 / イバラのアザ | sztuczna skóra / znamię jak pnącze cierni | `m185.53` |
| 住む世界が違う | żyć w innych światach | §9, echa |
| 甘いコーヒー | słodka kawa | §9, echa |
| ずるい | nie fair | §9, Yuki |
| チェリーのような舌 | język jak wisienka | `m035.6`, `m061.27`, `m126.17`, a celowo także w laboratorium i zakończeniach (`m157.26`, `m157.43`, `m184.40`, `m188.128`, `m196.9`): ten sam obraz |
| 能面顔 | twarz jak maska (nō) | D7 |
| 顔面岩 (Kenzo) | „kamienna gęba” | `m037.3`, `m039.0` |
| 薮医者 / ヤブ医者 | konował | |
| ヘボ公安 | partacz z Toanu | `m052.48` |
| 耳年増 | stara plotkara | §10 |
| 昔取った杵柄 | „stara szkoła” / „ręka nie zapomina” | `m119.7` |
| トカゲの尻尾 | jaszczurka za ogon | `m105.23`: „Złapałeś jaszczurkę za ogon, a już się puszysz.”; wątek ogona (`m101.8`, `m125.0`, biblia §6) |
| 尻尾を掴む | złapać za ogon | `m101.8`, `m125.0`; echo, biblia §6 |
| ストレス | stres | jedno słowo wszędzie: `m065.49`, `m099.13`, `m100.18`, `m123.0`, `m208.11` |
| 道具 / 玩具, オモチャ | narzędzie / zabawka | Yuki: kobiety jako narzędzia (`m027.8`, `m118.5`); Reiko: zabawka (`m153.39`, `m157.12`); オモチャ: pistolet, Reiko, Yuki (`m165.34`, `m176.3`, `m198.26`, `m202.4`) |
| 自分を責めるな | przestań się obwiniać | `m081.44`, `m083.11`, `m185.28` |
| 好き / 愛してる | kocham cię / kocham cię nad życie | D21 |
| 女性自身, 蜜壷, 肉ヒダ | do ustalenia (§11) | |
| 菊門, 菊の花びら | do ustalenia (§11) | chryzantema to po polsku cmentarz: nie dosłownie |
| 性交玩具, セックス奴隷, 調教, 御主人様 | do ustalenia (§11) | 玩具 = zabawka (wyżej) |
| ザーメン, スペルマ, 精子 | do ustalenia (§11) | trzy rejestry, nie jedno słowo |
| 愛液, 愛汁 | do ustalenia (§11) | |
| イク | do ustalenia (§11) | |
| えっち１ / えっち２ (tytuły utworów) | Figle 1 / Figle 2 | D15 |
