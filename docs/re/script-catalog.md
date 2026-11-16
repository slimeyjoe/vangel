# Script catalog: the structure of the game

How `CMD00.SCB` ([scenario-format.md](scenario-format.md)) builds the game: boot, title, the
chapters, the branches and the four endings, the variables, the music cues and the save points.
Statement numbers are 1-based as the VM's pc (`re-tools/scbdis.py` listing); messages are
`CMD00.TXB` numbers ([text.md](text.md)); pictures are `GDATA.LIB` names
([graphics.md](graphics.md)); songs are `VA_Mnn` ([sound.md](sound.md)). Story content is
described only as far as needed to identify scenes. Everything here is read from the scenario
(**verified** by `re-tools/scbdis.py`, `scbsum.py`).

## 1. Layout of the program

| Statements | Role |
|---|---|
| 1–793 | chapters 1–11 as subroutines (with a few helper subroutines) |
| 794–1655 | the main line after chapter 11: the hospital raid, investigation, confrontation, endings' approach (inline in the main program, reached by `goto 794`) |
| 1656–1752 | system subroutines: flag reset, music, save and load menus |
| 1753–1910 | the opening (sub 1753) |
| 1911–1968 | the four ending tails |
| 1969–1978 | the Crystal Soft logo (sub 1969) |
| 1979–2034 | entry (1979), title menu loop (1983), "new game" chain |

2 034 statements; 1 947 reachable from the entry; the 87 unreachable ones are compiler
artifacts (jumps after jumps, empty joins) plus a final `end` (2034) after the main chain.
Messages 1–213 are all used except **20** (a title card 『バージン・エンジェル』) and **136**
(a death scene of the hero, cut from the game). All 54 pictures of the library are used.

## 2. Boot, title and the title menu

```
1979 entry
1980 call 1656        reset flags v12..v18
1981 call 1664        music_fade 1 (fade over 0.01 s = stop), v19 = 0
1982 call 1969        logo: hide pointer, clear, "logo" on screen, palette #3 (time 56), 3.5 s
                      (skippable), fade (op 1Ah 0,56), clear
1983 title:           op 1Ah 0,0; clear buffers 10-12; va_main + va_mw01 into buffer 11;
                      copy to 12 and to the screen; palette #32 (time 100)
1992 menu 43:  1 最初から始める → 2015   2 途中から始める → call 1745, back to 1992
               3 ミュージックモード → MUSMODE, back to 1983
               4 ＣＲＹＳＴＡＬ ＳＯＦＴからのお知らせ → song 21, ANNOUNCE, music off, back to 1983
2015 new game: call 1656; fade; clear; call 1753 (opening); call 1, 56, 198, 279, 350, 425,
               489, 551, 593, 702, 752 (chapters 1-11); goto 794
```

There is no title music: v19/v20 are 0 after the logo (song 21 plays only behind the notice).
**Load** (sub 1745): menu 42 (slots 1–3, 4 = back); `load slot(v1)`; on success execution
continues inside the subroutine that saved; on failure (no file, empty or invalid slot) the next
statement shows message 205 `不正なセーブデータです` and returns to the title menu.

## 3. The opening (sub 1753, 1753–1910)

Pointer hidden; song 1 (オープニング１); `va_opbac` straight to the screen; a loop on statement 35h
(music position) until VA_M01 reaches its third measure (≈3.56 s; [sound.md](sound.md)); 1 s; palette #43 (time
160); 0.8 s; **OPENING** (the prologue pages, [platform.md](platform.md) §5.2). If the player
skips the prologue (v1 true) everything up to 1879 is skipped. Otherwise: the message window
(`va_mw01`), palette #4, a prelude in the slums told in messages 206–209 (the scene with the
mysterious woman; CGs `va_01`–`va_03`; each message's result is tested and a skip jumps to
1879). From 1879: song 18 (オープニング２), the title picture `va_title` and the staff pictures
`va_st01`–`va_st04`, song 19 (タイトル) … then return to the new-game chain.

## 4. Chapters 1–11

Each chapter is a subroutine called once from the new-game chain. "Songs" are the values given
to v20 before `call 1670` (0 = music off).

| # | Sub | Statements | Messages | Menus | Songs | Pictures | Variables | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1–55 | 1–8 | 1, 2 | 3, 4 | va_main, va_bg04, va_ch01, va_ch04 | w v2 (helper 31: show the chief once) | night call to the crime scene; the hero Murakumo |
| 2 | 56 | 56–197 | 9–26 | 3, 4, 5 | 5, 6, 7, 8 | va_04, va_va, va_bg01–03, va_ch01–04 | — | at the bureau (都安) HQ |
| 3 | 198 | 198–278 | 27–36 | 6, 7 | 5, 6, 7 | va_bg02–03, va_ch01–03, va_ch02k | v3 local; **save point** | the information section, Yuki |
| 4 | 279 | 279–349 | 37–43 | 8 | 6 | va_01–03, va_main, va_bg01–02 | **v12** = took the armoury key (menu 8 choice 1) | the key to the armoury |
| 5 | 350 | 350–424 | 44–52 | 9 | 3, 5, 6, 7, 9 | va_bg01–03, 05, 06; va_ch01–03, 05, 06, 08 | **save point** | next morning; Kusanagi hospital |
| 6 | 425 | 425–488 | 53–60 | 10, 11 | 3, 5, 7 | va_bg01–03, va_ch01–04 | **v13** = menu 11 choice 2; reads v12 | back at the bureau |
| 7 | 489 | 489–550 | 61–71 | — | 9, 20 | va_bg02, 05, 06; va_ch01, 02, 05, 08 | reads v13; **save point** | the DNA number |
| 8 | 551 | 551–592 | 72–79 | 12, 13 | 9, 10 | va_bg07, va_ch01, va_ch08 | — | a nurse's testimony; fight |
| 9 | 593 | 593–701 | 80–96 | 14, 15, 16 | 6, 11 | va_05–07, va_main, va_bg08, va_mw02, va_ch01, 02, 02k | v4, v5–v7 local (menu 15 needs all three of v5–v7) | Yuki after the attack; first love scene; `music_fade 200` |
| 10 | 702 | 702–751 | 97–101 | 17 | 5 | va_main, va_bg01–03, va_ch02–04 | **save point** | |
| 11 | 752 | 752–793 | 102–110 | 18, 19 | — | va_bg01, va_ch01, 02, 04 | **v14** = armour (menu 19, only if v12: menu 18 choice 1 goes to the armoury) | preparing the raid |

## 5. The raid and the endings (794–1655, 1911–1968)

```
794   save point (call 1737); music off; song 12
812   menu 20: hide and watch / ambush at the door           (messages 112-115)
835   menu 21: send Yuki home (1) / investigate together (2)
        1: 837-860  investigation alone   (sub 861, messages 121-125), v15 = false
        2: 1045-1053 investigation together (sub 1054, messages 128-133), v15 = true
           subs 861/1054: examine four items (white powder, red file, black file, board) in any
           order; menus 23-37 offer the ones not yet examined (v8-v11 mark them); the loop ends
           when all four are done.
1238  song 13; Reiko attacks (message 134); switch v14 (armour):
        2 (combat armour) or 4 (insulation suit): survive (messages 135-142) → 1301
        none, 1 or 3: captured (143-144), v16 = true → 1588
1301  save point; song 12
1313  menu 38: load special ammunition → v17 (buckshot / armour-piercing / beam / freeze)
1338  menu 39: jump out to stop them (1: v18 = true, message 151) / wait for a chance (2)
      the assault on Yuki: CGs va_08-va_11 (messages 152-161); song 15
1410  menu 40: swallow the drug to wait for a chance (1) → message 163 → 1588 (v16 false)
               refuse (2) → if v15: 1425 else 1447 — the fight, by v17 (1454/1463/1466/1472)
      ... va_12 (message 181)
1526  if (v15 | v18): 1532 epilogue — song 16, CGs va_13-va_17 (messages 183-191) → 1931
      else: → 1911
1588  captured: song 14 (messages 192-194); if v16: message 195 → 1959
                                           else: CGs va_18-va_22 (196-203) → 1950
```

| Ending | Tail | Condition | Staff roll | Message |
|---|---|---|---|---|
| No.1 | 1931–1949 | raid survived, refused the drug, and (Yuki was a partner or the hero jumped out) | **ENDING** (song 17 スタッフロール) | 211 `＊＊＊Ｅｎｄｉｎｇ Ｎｏ．１＊＊＊` |
| No.2 | 1911–1930 | raid survived, refused the drug, alone and waited | **ENDING2** (song 17), `va_12e` | 210 `… Ｎｏ．２…` |
| No.3 | 1950–1958 | swallowed the drug | — (CGs va_18–va_22) | 212 `… Ｎｏ．３…` |
| No.4 | 1959–1968 | wrong or no armour: captured by Reiko | — | 213 `… Ｎｏ．４…` |

Every tail fades out (op 1Ah 0,100), turns the music off and jumps back to the title loop
(1983). The only `end` statement on a reachable path (1444, the default of the ammunition
switch) cannot be reached in practice: v17 always holds a menu result 1–4.

## 6. Variables

| Var | Type | Role |
|---|---|---|
| v1 | int/bool | result register: menu choice, return value, "skipped" flags ([scenario-format.md](scenario-format.md) §5.3) |
| v2 | int | chapter 1: the chief's picture shown |
| v3, v4 | bool | chapter-local (3, 9) |
| v5–v7 | int | chapter 9: which of three actions were done |
| v8–v11 | int | the four investigation items (subs 861/1054) |
| v12 | bool | has the armoury key (chapter 4); enables the armoury in chapter 11 |
| v13 | bool | chapter 6: menu 11 choice 2; read in chapter 7 |
| v14 | int | armour chosen (0 none, 1 bulletproof, 2 combat, 3 anti-beam, 4 insulation) |
| v15 | bool | Yuki investigates with the hero (menu 21 choice 2) |
| v16 | bool | captured by Reiko (wrong armour) |
| v17 | int | special ammunition (menu 38) |
| v18 | bool | the hero jumped out to stop the assault (menu 39 choice 1) |
| v19 | int | song now playing (0 = none) — kept by sub 1670 |
| v20 | int | song requested; argument of sub 1670; **not saved** ([scenario-format.md](scenario-format.md) §7) |

Sub 1656 (new game) resets v12–v18; v2–v11 are set where used.

## 7. Music cues

Sub **1670** plays song v20 unless it is already playing (v19 == v20): `music_fade 320` (sub
1667), v19 = v20, then `music_play 100, "va_mNN.m"` for v20 = 1..21 (v20 = 0 or > 21: nothing,
so `v20 = 0; call 1670` means "fade out and stay silent"). Sub 1664 (`music_fade 1`, v19 = 0)
stops at boot. After each save point v19 is set to 0 to force a restart (below).

Use of the songs (v20 values in the scenario; titles from the music mode, [platform.md](platform.md)
§5.5): 1 opening, 2 the epilogue love scene, 3–7 character themes (ムラクモ, ササメ, 捜査, ユキ,
シノブ), 8, 9 hospital, 10 battle, 11 love scene, 12 hospital 2 (the raid), 13 Reiko, 14
ending 1 theme (va_12 / captured), 15 negotiation, 16 ending 2 theme (epilogue), 17 staff roll,
18 opening 2, 19 title (in the opening only), 20 (chapter 7), 21 behind the notice. Exact
song ↔ title mapping per file: [sound.md](sound.md).

Every save point is followed by `v19 = 0` and a song request (or music off), so after a load —
which resumes right after the `save` statement — sub 1670 always restarts the right song even
though v20 is not saved and the load routine does not touch the music ([scenario-format.md](scenario-format.md)
§7). The `v19 = 0` writes listed for chapters 3, 5, 7, 10 and the raid are exactly these.

## 8. Save points

Sub **1737**: message 204 `セーブしますか？`, menu 41 (slots 1–3, 4 = don't save),
`save slot(v1)`. Called at statements 198 (chapter 3), 350 (chapter 5), 498 (chapter 7), 706 (chapter 10), 794
(start of the raid) and 1301 (before the confrontation): six save points; a save resumes right after the
`save` statement inside sub 1737 and returns into the caller.
