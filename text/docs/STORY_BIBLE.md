# Virgin Angel: story bible

> **Spoiler warning.** This document gives away the whole plot: who the killer is, what the
> bureau chief knew, and all four endings. It is for translators and editors, so that the
> translation stays faithful to what the story is doing.

**Companions:** [TRANSLATION_GUIDE.md](TRANSLATION_GUIDE.md) (rules for every language) and
[TRANSLATION_GUIDE_PL.md](TRANSLATION_GUIDE_PL.md) (Polish).

**References.** `m083.36` is a string's key: message 83, the passage starting at its line 36.
`menu19.2` is choice 2 of menu 19. `name.07` is a speaker's name, and `bi.prologue.1` is a
built-in text. The keys are the ones the translation files use (`docs/translation.md`).
`python3 -I tools/tl.py read` (in `source/`) writes a reading copy of every message, with its
keys, into `build/`. `make text-template` writes the Japanese next to every key. Read a scene
there before you touch it. Message and statement numbers are those of
`docs/re/script-catalog.md`, which describes how the scenario branches.

**Sources.** The whole script was read once, in message order, from those reading copies
(2026-11-17). The routes were checked against the scenario listing (`re-tools/scbdis.py`). The
game is *Virgin Angel* (Crystal Soft, 1995, PC-9801). Anything the text does not state is marked
*(inference)*. Names are spelled as the guides spell them, and the Japanese is given once.

**Adult content.** This is an adult title. A quarter of its passages are explicit sexual
scenes, and most of those are scenes of sexual violence. They are described here by their
place and their function in the story (§8), and they are translated like the rest of the
script. §8 also names the six passages the editor translates.

---

## 1. At a glance

- **Genre:** a linear visual novel with a few choices. It is a police thriller in a cyberpunk
  Tokyo, told in the first person by a clowning hero. It has about 78 000 characters of
  Japanese: 1 954 passages, of which 377 are tagged speech. Many more passages hold speech
  written inline (§2.3). There are 43 menus, a prologue, a staff roll and a music room.
- **Setting:** Tokyo (トーキョウ, written in katakana), in the 2080s (`bi.prologue.0`). The
  city has smog, slums on reclaimed land in the bay, and a 24-hour airport with silent jets.
  Mafia trafficking is rampant, there is terrorism against the space programme, and the police
  leadership is in bed with organised crime. "Free sex zones" exist.
- **Hero:** Murakumo Amano (アマノ・ムラクモ), the narrator. He was born in the slums and was
  a street-gang killer. He was sentenced to life at eighteen. Now he is a bought-and-paid-for
  investigator of the Metropolitan Public Security Bureau, called "Toan" for short (首都公安局,
  通称 都安). He is a womaniser who injects female hormones and has breasts. He is camp and
  flippant on the surface and lethal underneath.
- **Plot in one sentence:** a nurse is raped and beaten to death in the street by a woman
  with impossible strength. The trail leads to a private hospital where terrorists' brains are
  put into military combat robots, kept sane by sex with surgically altered women. The hero's
  new partner, the earnest rookie Yuki, pays for the investigation with her body.
- **Structure:** eleven chapters, then a night raid on the hospital. The choices made in the
  raid lead to one of **four endings** (§2.2). Six save points.
- **Tone:** banter, slapstick and sex jokes for the first half. But the opening has already
  shown the murder before the title, so the comedy plays over a horror the player has seen.
  Under it is a story about women made into objects; Yuki says it outright in `m027.8` and
  `m118.5`, and the narration that condemns it also enjoys it (§6). From the raid on it is a
  horror story, and only one ending gives it a soft landing.

---

## 2. Structure and routing

### 2.1 Chapters and messages

| Part | Messages | What happens | Menus |
|---|---|---|---|
| Opening | 206–209 (timed pages), then the title pictures | the murder of the nurse in the slums, seen from outside (skipped with the prologue) | — |
| Prologue | `bi.prologue.0`–`3` | the world: Tokyo in the 2080s, "body drugs", Toan | — |
| Ch. 1 | 1–8 | 00:50, the crime scene on Route 357; Kenzo; Sasame | 1 (walk around first), 2 (ask about the culprit's looks / the weapon) |
| Ch. 2 | 9–26 | the bureau; Hinamura, Yuki, Shinobu; the drug is "Virgin Angel"; the Uroboros conference | 3, 4, 5 (the order of visits) |
| Ch. 3 | 27–36 | six hours of search, no match; Shinobu tells Yuki's past; Murakumo snaps at her; the victim found | 6 (stay with Yuki / leave her alone) |
| Ch. 4 | 37–43 | Kenzo's report of the taxi driver; the armoury key on his desk; he drives Yuki home | 8 (look into the armoury / put the key on the chief's desk) |
| Ch. 5 | 44–52 | next morning; Kusanagi Hospital; Reiko, Dr Kusanagi, the nurse Mami | 9 (the order of visits) |
| Ch. 6 | 53–60 | the mafia lead is dead; Kusanagi's reputation; the key; Shinobu tells Yuki his past; Mami telephones | 10, 11 (avoid Kenzo / tease him) |
| Ch. 7 | 61–71 | the killer's DNA belongs to Fubuki Izumo, a terrorist shot dead three months ago at that hospital; the second visit; Mami talks | — |
| Ch. 8 | 72–79 | the old wing; Reiko's guards Gori and Snake; the fight | 12, 13 (how to fight) |
| Ch. 9 | 80–96 | the forest park; Yuki's sister; the first love scene | 14, 15, 16 (sexual choices; 16 appears when all three of 15 are done) |
| Ch. 10 | 97–101 | Sasame on the terrorists; Shinobu and Hinamura on brain transplants | 17 (Yuki / Shinobu) |
| Ch. 11 | 102–110 | the arms dealer Shikakura; the power bills; the investigation is shut down; the armoury | 18, 19 (armour) |
| The raid | 111–182 | the old wing at night; the files; Reiko unmasked; the lab; the assault on Yuki; the fight; Sasame arrives | 20, 21, 22–37 (the four exhibits), 38 (ammunition), 39, 40 |
| Ending No.1 | 183–191, 211 | epilogue in Hokkaido | — |
| Ending No.2 | 210 | the raid's end, no epilogue | — |
| Endings No.3, No.4 | 192–203, 212, 213 | captured | — |
| System | 204, 205; menus 41, 42, 43 | save question, bad save, slots, title menu | |

Message 20 (a title card) and message 136 are never shown. Message 136 is the combat-armour
branch's copy of Reiko's taunt, which is shown as `m140` and `m144` on the other branches.

### 2.2 The raid and the four endings

```
menu 20  hide and watch (113–115) / wait at the door and seize the intruder (116–117): it is Yuki
menu 21  send her back (118–125, alone)  /  investigate together (126–133)         -> v15
         the four exhibits, in any order: menus 23-37, the same four items
134      Reiko attacks; switch on the armour chosen in menu 19:
           combat armour  135, 137, 138  -> survives
           insulation suit 139–142       -> survives
           none, bulletproof, anti-beam  143–144 -> captured: Ending No.4
145      menu 38: the ammunition; 146–150 the lab; Yuki drugged
         menu 39  jump out to stop it (151, -> v18) / wait for a chance (152)
153–162  the assault on Yuki; Kusanagi offers the pill
         menu 40  swallow it (163) -> captured: Ending No.3
                  refuse: 164–165 (Yuki was a partner) or 166–167 (alone)
168–175  the fight, by ammunition:
           buckshot 168–169, beam 171–172 -> captured: Ending No.3
           armour-piercing 170, freezing 173–175 -> Reiko destroyed
176–182  Kusanagi's needle gun; Sasame and the assault unit; Yuki
         Yuki was a partner OR he jumped out  -> Ending No.1 (183–191)
         otherwise                            -> Ending No.2 (staff roll after 182)
captured: 192–194, then 195 (No.4: caught by the first blow) or 196–203 (No.3)
```

The text plants the clues for every choice. The taxi driver saw a "blue-white flash"
(`m037.29`), so Reiko's blow is electric: the insulation suit stops it. The blow was a fist
(`m006.26`, `m007.7`), so the armour that absorbs blows stops it too. The first look at the body
(`m005.58`) says 鈍器, a blunt instrument; that first impression stays as written. The robot's skin is light
titanium with an anti-optical coating (`m104.34`, `m145.14`), so armour-piercing rounds go
through, beam rounds are scattered and buckshot only staggers her. A translation must keep each
of these clues as clear as it is in the Japanese and **no clearer**: "flash" stays a flash,
and the coating stays "anti-optical".

### 2.3 How the text is built (this shapes the translation)

- **Most of the text is the hero's narration**: first person, untagged, mixing what he sees,
  what he thinks and asides to the reader.
- **Speech is written two ways.** A tagged speech (13h control: `[name.00 ムラクモ]` in the
  reading copy) has its name and brackets drawn by the engine. Far more speech is written
  **inline** in an ordinary passage, `ムラクモ「よう！」`, with the name and brackets as text. The
  translator writes these names and brackets by hand. Both kinds alternate within a scene.
- **Twins.** Many scenes exist in two or three versions, one per route, with most of their
  lines the same: 6/7, 23/24/25, 31/33, 32/34, 75/76, 77/78, 113–115/116–117, 119/126, 120/127,
  121–124/128–131, 125/133, 135/139/143, 136/140/144, 137/141, 138/142, 164/166, 165/167 and
  others. The same Japanese gets the same translation. The differences are deliberate and stay.
- **The deck.** At his desk the hero's "personal deck" plays recorded messages. Kenzo's report
  (`m037`) and Sasame's lecture (`m045`) are written `name『…』`: a recorded voice, not a person
  in the room.
- **The four exhibits** of the raid are offered by 15 menus (23–37) with the same four items in
  every possible order. Menu 22 holds the same four items and is never used.

---

## 3. The case, step by step

**Before.** The murder in the opening (206–209): in the night slums of reclaimed lot 13, a tall
woman in a leather suit (女) has a young woman in a yellow dress (娘) at her mercy. The young
woman begs to be let go. She swears to keep "the secret", and says she cannot bear to be given
every day to "men like monsters". The woman humiliates her before a crowd of homeless people,
rapes her on the bonnet of a taxi, and says why: "I am stressed, I have to torment you to
death or it won't stop" (`m208.11`). Neither is named. They are Reiko and Misa (below).

**Ch. 1.** His suspension ended at midnight, and three seconds later he was called out
(`m005.10`). He reaches Route 357 at 00:50, late.
Kenzo, big and stiff, rages at being called "Ken-chan". Sasame, the bureau chief with a face
like a Noh mask, briefs him. The victim was dragged out of a taxi at a red light, raped on its
bonnet and killed with two blows of a bare fist. The skull is dented like a fist print. The
killer was a woman of 27 or 28, 180 cm tall, with long blonde hair and sunglasses, and she rode
off on a motorbike toward the old Arakawa bay district. Military "combat dolls" have that
strength but not the will to stage a public rape. Sasame: "A wild dog without a collar must be
hunted" (`m008.10`). Murakumo slips away to chase girls in a drug bar.

**Ch. 2–3.** At the bureau Murakumo is given the victim's identity to find, and Yuki Yasaka, a
rookie at the information section, as his partner. Shinobu, the forensic doctor and his
occasional lover, warns him off Yuki: "she lives in another world". The victim was a body drug
modified to secrete "Virgin Angel", an expensive aphrodisiac narcotic. A six-hour DNA search of
prostitutes' records finds nothing. Yuki blames herself. Shinobu tells Murakumo that Yuki was
attacked by men in the slums as a girl and only just escaped. He answers, angry: "So if it's not
a game, if it's serious, then even I would do?!" (`m030.45`), then grabs the face reconstruction and leaves. Born,
raised and a killer in the slums: now he understands "another world" differently (`m031.3`).
With the face, the search finds the victim: **Misa Misaki**, 23, a nurse at the private
**Kusanagi Hospital** in the old Arakawa bay district.

**Ch. 4.** Kenzo's recorded report gives the taxi driver's account, including a blue-white
flash. Murakumo finds the armoury key lying on his desk *(inference: Sasame put it there; see
ch. 6 and 11)* and drives Yuki home without laying a finger on her, which surprises him.

**Ch. 5.** At the hospital: Reiko Takama, the director's tall, beautiful secretary; Dr Ken
Kusanagi, the young, haughty director; the nurse Mami Inaba, who keeps looking at Reiko before
she answers. Misa had resigned two months earlier, they say. Murakumo slips Mami his card.
Reiko, under her breath: "Useless security clown" (`m052.48`). That makes it personal.

**Ch. 6.** The mafia had nothing to do with it. Kusanagi is an authority on brain surgery and
human-machine engineering. He is suspected of illegal operations and terrorist links, and he
is protected by business and politicians. A terrorist group is planning something with body
drugs. If the hero returned the key, Sasame shows him which drawer he keeps it in (`m055`).
Shinobu tells Yuki who Murakumo is (`m057`): a slum gang member who killed a policeman at
eighteen. Sasame bought him out of a life sentence for 65 700 hours of service, twelve hours a
day for fifteen years, in a job where under 60% survive a year. Shinobu gives Murakumo her
blessing, a little jealous. Mami asks to meet him.

**Ch. 7.** The killer's DNA belongs to **Fubuki Izumo**, 27, a former major general of the
International Expeditionary Force and a member of the anti-Uroboros terror group **UIA Hyōyoku**
(氷翼, "Ice Wing"). She was shot dead three months ago near the Urawa International Hotel, the
venue of the coming Uroboros conference, and she died at Kusanagi Hospital. Murakumo puts his
theory to Reiko's face: a dying brain moved into a combat doll. Reiko laughs too hard and has
them thrown out. Mami says that Misa, the day before she "resigned", had seen something
terrible in the disused old wing. Misa was a week from qualifying as a nurse and never came to
the gate that evening.

**Ch. 8.** At the old wing Reiko's "guards" attack: four thugs, among them Gori, 2 m tall with
armour plates under his skin, and Snake, a famous fast gun. Gori thinks Murakumo is a girl.
Yuki, untrained, freezes while Gori tears at her uniform. Murakumo drops Gori by shaking his
brain and shoots Snake's hand off. Reiko: "Oh, I didn't notice."

**Ch. 9.** In a forest park by the bay Yuki tells him about her sister. Mafia traffickers
attacked them both near the slums when Yuki was in high school. The sister let herself be
taken to save her, was made a body drug, was sold from hand to hand and died last year a
wreck. That is why Yuki joined Toan. He kisses her to stop her breaking. Then comes the first
love scene, by a small log cottage (§8). There is no intercourse: it ends in her first orgasm
(`m093.48`), and she is still a virgin when the raid begins (`m153.8`). Afterwards she cries with relief: perhaps even she can
be made happy.

**Ch. 10–11.** Sasame: UIA means to disrupt the conference. The killer's body was cremated:
"The body, yes" (`m098.29`). Shinobu and Hinamura: a brain in a machine dies of rejection and
stress, which drugs can hold off for a while, and stress only if the brain is constantly fed
the most instinctive acts. Sex with a body drug would do it. On the Yuki branch Murakumo gets there himself (`m099.35`);
on the Shinobu branch Hinamura's jab gives it to him (`m100.30`). The arms dealer Shikakura,
in prison, talks over a recorded video link. Murakumo holds a handwritten note up to the
camera: the bureau is ready to buy twenty years of his sentence (`m103.31`). Half a year ago,
Shikakura says, he sold four Statue 2H combat dolls to a masked UIA man who looked like
Kusanagi (`m103.36`). Yuki finds the old wing's power
peaks after Fubuki's death and three other UIA fanatics dead at the hospital. Then Sasame shuts
the investigation down from 20:00 and forbids anyone to come within 2 km of the hospital.
Murakumo arms himself and goes in alone that night.

**The raid.** Yuki has followed him. The files show the drug, Kusanagi's "adjustment charts"
of the body-drug women (Misa among them), recordings of the dolls with those women, and a plan
to attack the conference with four dolls. Kusanagi is a UIA leader. Yuki screams in the hall.
Reiko has struck her down: "I am Fubuki Izumo. Dr Kusanagi brought me back to life, with the
strongest body there is" (`m134.23`). Bullets do not stop her, and an electric punch fells him.
With the right armour he wakes hours later and drags himself to the lab, where Kusanagi
diagnoses his broken thigh with relish. Yuki, drugged, is fitted with an artificial penis and
raped by Reiko and Kusanagi in front of him; Kusanagi takes her virginity (`m158.6`). To save his life she swears to become their sex
slave (`m159`). Kusanagi offers him a pill. If he refuses, he fights. If the rounds are right
Reiko dies, her head blown apart by his gun in her mouth. Kusanagi's needle gun ruins his
right arm. His last shot only tears Kusanagi's cheek open. Kusanagi takes aim. Then Sasame
walks in with the police special assault unit. They had lost two companies to the three other
dolls on the way, and they shoot Kusanagi to pieces. The shutdown was a lie: Sasame knew
Murakumo would go in alone, and tracked him by satellite (`m179.26`). "Thank God my good arm
doesn't work" (`m179.34`). Yuki, sobbing, sucks the needles out of his arm.

**Ending No.1.** Six weeks later Murakumo resigns at gunpoint. He wants to spend the rest of
his life on one woman, and he will take his freedom even if he has to kill the chief for it
(`m183.22`). Sasame answers that he will be a wanted man from the moment he leaves the room
(`m183.30`). Sasame gives him an envelope with Murakumo Amano's
death certificate, a new family register, a driving licence and a forest-ranger licence: "Go.
I am not your chief or your superior. I am a stranger to you" (`m183.55`). Months later, in a
lodge in Hokkaido, he marries Yuki before a few neighbours, without registering it. The implant
has been removed by a surgeon Shinobu found, but she still has nightmares and shrinks from his
touch. Their quarrel on the wedding night is the emotional climax (`m185`). She calls herself a
deformed woman. He answers that she loved him with breasts and dresses: "お前の事が好きなんだ! If
once isn't enough, I don't mind saying it a hundred times, a thousand" (`m185.28`). She sees the thorn-shaped
scar on his arm and understands that he was hurt too. They make love (§8). It is only her
second time, and the first with love (`m188.14`). The lodge is like
the cottage in the forest park, "where it began".

**Ending No.2.** The same night ends at `m182` without the epilogue: "this case bored something
into me that a lifetime won't erase. Deep, and deeper still in her".

**Ending No.3.** Captured, either after the pill or after a fight with the wrong rounds.
Murakumo wakes strapped to a bed with huge artificial breasts. The case has been handed to
police on Kusanagi's payroll, and a patsy will be found. Yuki has been made a body drug with a
mind-control chip, after she agreed to the operation to save his life. In the drug's haze they
have sex. When she cries that he said he loved her "even like this", he understands that she
has not changed inside, and he repeats `m185.28` almost word for word (`m202.16`). "And when it is
over, the two are wrapped in a pitch-black reality" (`m203.0`).

**Ending No.4.** Captured at the first blow (wrong or no armour). It is the same captivity cut
short at `m195`: he is falling under the drug that Yuki now secretes.

---

## 4. The world

- **Toan (都安)**: the Metropolitan Public Security Bureau. It is an independent elite force
  set up against large-scale organised crime and terrorism, with the right to use force
  (`bi.prologue.3`). Sasame founded it, and the police call it his private army. It is staffed
  with people the police and the army threw out for violence (Kenzo, Kandori) and with
  convicts bought out of prison (Murakumo). The police resent it (`m002.19`, `m003.15`). Its
  sections: **human rights** (人権課, Murakumo's: "only four investigators"), **information**
  (情報課, data searches, "famous for pretty women"), **forensics** (鑑識課) and
  **anti-terrorism** (防テロ課). There is an **armoury** (火器管理室) of special rounds and
  personal armour. Investigators hold graded "licences to kill" (殺人許可証, Murakumo's is class
  B for shooting). They may search without a warrant when evidence is at risk (`m074.42`).
- **The police**: 警視庁, the Metropolitan Police Department. Its pride is the special assault
  unit (特殊突撃部隊).
- **Body drugs** (ボディ・ドラッグ, `bi.prologue.1`): people, mostly women, surgically altered so
  that their glands make a narcotic, which their partners absorb through sex. They are
  kidnapped, sold and modified in slave markets. **Virgin Angel** (バージン・エンジェル) is the
  dearest of these narcotics: an aphrodisiac on contact, "the best match for sex" (`m021.5`),
  sold as powder and ointment. The game's title is the drug's name.
- **Combat dolls** (コンバット・ドール): military robots. The current AI can only repeat a
  programme or fire automatically. The **Statue 2H** type (`m104.29`) weighs 98 kg dry, has a
  reinforced plastic frame and light-titanium armour with an anti-optical coating, and carries a
  built-in stun gun. Kusanagi's secret is a living brain in one, kept from breaking down by sex
  with body drugs. Reiko is one; three more are being "adjusted" with the brains of UIA
  fanatics.
- **The Uroboros plan** (ウロボロス計画): a new-century space programme. Its **Prison Project**
  would send political prisoners, terrorists and crime bosses to mine the moon. An international
  conference with NASA staff is to be held in a week at the Urawa International Hotel, near
  the hospital. **UIA Hyōyoku** wants to stop it. The board in the lab shows two teams of two
  dolls: one a decoy, one coming from the bay.
- **Places**: reclaimed lot 13 (１３号地), the slum on Route 357 between "Big Bird" (the airport)
  and the artificial industrial islands; Shin-Kiba; the Metropolitan Expressway; the Toan
  building on Meiji-dōri in sight of the Shinjuku government tower; the old Arakawa bay
  district, block D (Kusanagi Hospital, the Urawa International Hotel); a forest park by the bay
  road; Chiba-Narashino (Misa's address); Hokkaido (the epilogue). The geography is the game's
  own (Urawa is not on the bay); do not correct it.
- **Money and time**: the contract is 65 700 hours; Shikakura has 80 years of accumulated
  sentences; the search runs over 1 263 prostitutes with records, then 98, then none.

---

## 5. Characters

Speech notes describe the Japanese. How each voice is rendered is the language guides' business.
The counts are speech passages, tagged and inline, and are approximate.

### Murakumo Amano (アマノ・ムラクモ), the narrator, about 425
He narrates everything as ボク (sometimes written 僕, with no difference). He has two registers.
**Surface:** camp, flirtatious, childish. He uses ☆ and drawn-out vowels, the katakana particles
ネ, ナ and ヨ, 〜のね, 〜だよん, 〜デース, and stage directions in brackets (`（しょぼん）`,
`（ぷんぷん）`, `（汗汗汗）`). He strikes coquettish poses (しなを作る) at Kenzo, calls him "Ken-chan",
and adds ちゃん to every girl. He is lazy and late, and he lies about road works. He ogles every
woman, including Reiko's backside, while Yuki stands behind him. **Underneath:** a slum-born
fighter who narrates violence with clinical precision: joint locks, a palm strike that "shakes
the brain like a broken pudding", a .45 tuned for impact over penetration. His speech turns
rough when he is angry: テメエ, ブチ殺す, 貴様ら. He believes that "a world where the poor live by
preying on the poor" is wrong (`m057.32`), and he does not mind mafia killing mafia but will not
have ordinary people harmed (`m035.30`).

**His body and his sex.** He is a man. He takes female hormones and has breasts, because a
girl he slept with said it felt like "being taken by a lesbian" and enjoyed it, "nothing
deeper" (`m015.32`). He insists he is straight ("I'm not homo, so relax", `m001.41`; "I'm
normal", `m060.1`). Others read him in different ways: Kenzo calls him "this effeminate man"
(`m060.7`). Sasame says of the female killer, "though with examples like you, one can't tell by looks"
(on one branch or the other: `m006.10` or `m007.14`). Yuki asks, "You are a man, aren't you?" (`m015.29`).
Gori takes him for a girl, and Snake corrects him (`m074.50`–`m074.60`). In the epilogue he
reminds Yuki that she loved him "with breasts, dressed like a woman" (`m185.33`). In Ending No.3
his body is altered against his will (`m193.37`). The text never treats his body as a mystery
to be solved. It is a fact everyone has an opinion on.

His arc: the flirt who cannot touch Yuki (`m043.4`), then the man who throws away his freedom
for her.

### Yuki Yasaka (ヤサカ・ユキ), about 285
She is a rookie at the information section, a volunteer, and good at searches and passwords.
**Her address arc.** She speaks polite です/ます to him: "アマノ先輩" at first, then ムラクモさん.
She keeps ムラクモさん through the park scene, the investigation, the raid and the rescue
(`m083.20`, `m083.48`, `m099.7`, `m104.5`, `m115.1`, `m126.13`, `m150.9`, `m159.0`, `m180.7`). The
bare ムラクモ comes only at peaks: her climax in the park (`m093.26`, `m094.0`) and when
drugged (`m149.4`). Then さん comes back. Steady casual speech arrives only in the epilogue
(`m184.29` だもん), still mixed with さん (`m184.36`, `m185.107`) and with one relapse into
polite speech under stress (`m185.17`). The last step is **あなた** (`m189.16`; in captivity
`m201.45`, and 貴方 `m196.107`). His side changes earlier: ユキちゃん becomes ユキ (and キミ) at
`m083.11`, and that is what Shinobu remarks on (`m099.46`). He still slips back to ユキちゃん
once (`m132.5`).

She calls herself ユキ in the third person when overwhelmed, and ユキ and 私 alternate within one
line (`m188.125`, `m196.30`). That is cute in the park and broken in `m159` and in captivity.
She is earnest to the point of pain: "I can't forgive crimes that treat women like sex tools"
(道具, `m027.8`, `m118.5`). Reiko's word for what Yuki is to become is a different one, 玩具, a
toy (`m153.39`, `m157.12`). She is afraid of men because of her sister's fate and her own near
escape. Recurring images:
- the cherry-like tongue, innocent at first (`m035.6`, `m061.27`, `m126.17`) and carried on
  purpose into the lab, the love scenes and the endings (`m157.26`, `m157.43`, `m184.40`,
  `m188.128`, `m196.9`);
- the sweet coffee he brings her (`m032.7`, `m032.26`, `m118.31`, `m118.39`);
- ずるい, "unfair": her answer to his kindness (`m029.19`) and to a forced kiss (`m118.22`),
  which he takes up himself (`m118.25`), and a lover's tease at the end (`m191.37`). He also
  says it of Gori (`m075.57`). She is an adult. She was a high-school girl when she was attacked, and her
sister died last year. The narration nevertheless describes her body again and again in terms
of a young girl (§8).

### Josetsu Sasame (ササメ・ジョウセツ), the bureau chief, about 68
Toan's founder. He can mobilise the police assault unit with one telephone call (`m005.23`).
Murakumo calls him 能面局長, "the Noh-mask chief", for his expressionless face and thin smile.
He speaks in precise, cold, faintly ironic Japanese: 私, 君 and キミ to Murakumo, 〜かね,
〜たまえ, 〜だよ, and contract terms. **Everything he says is written to be read twice.** He knows
or guesses far more than he says: "The body, yes" (`m098.29`); the key on the desk and the
drawer (`m055`, `m108`); "I expect great things of your work" (`m022.32`, `m098.35`). His
shutdown is a trap that uses Murakumo as bait. The epilogue then shows that the coldness was
not the whole man. **A translation must not warm him up early or make him sinister. He stays
opaque until `m179`.** His first warmth is `m179.10` (よく、生きていてくれた), which the
original tags as Kusanagi's by mistake. He says the bare ムラクモ when he commands and
ムラクモ君 when he is smooth (`m045.12`, `m178.6`, `m183.37`).

### Shinobu Yata (ヤタ・シノブ), forensic doctor, about 47
Medical examiner, older than the others ("お姉様", `m016.0`). She is called シノブ先生 by Yuki and
Hinamura, and シノブさん or シノブ先生☆ by Murakumo. Her speech switches between feminine (〜わ, 〜のよ,
あら) and gruff male speech when she scolds (おい！, お前, こっちにこい, 承知しないからね). She drags
Murakumo off by the ear (a running gag), straddles him on the corpse table, and has her assistant
"trained" to see nothing. She loves Yuki like a sister. She admits she is jealous of them
(`m048.28`) and then gives him up to Yuki. She is warm, rough, and sad under the jokes
(`m036.9`).

### Kenzo Tanaka (タナカ・ケンゾウ), about 15
The biggest man in the bureau, "stiff, stubborn, a blockhead" (`m001.23`). He was thrown out of
the police or army for violence. He uses 貴様 and 俺 and shouts in exclamation marks. Every
"Ken-chan" makes him explode. On the deck he reads his report in stiff officialese (`m037`).

### Reiko Takama (タカマ・レイコ) = Fubuki Izumo (イズモ・フブキ), about 77
Kusanagi's secretary. She is tall and voluptuous, with the polite speech of a high-class
secretary (わたくし, 〜ですわ, 〜して頂けますか, オホホ) laid over open contempt ("useless
security clown", "Oh, I didn't notice"). She is in fact a combat doll carrying the brain of
Fubuki Izumo, a former major general and terrorist, and she is the killer. **Her identity stays
hidden until `m134.23`.** Until then her lines must work as those of an insolent secretary.
The narration plants cracks, and they stay literal: her eyes do not smile (`m063.0` 目が笑って
いない), her face looks 無機質 for an instant (`m065.41`), and she overreacts to the
"science-fiction novel" (`m065.45`–`m065.56`). She drops into plain speech once before the
reveal (`m074.9`). After the reveal she speaks with soldierly finality once
("この世に蘇ったのだ"). Then she is a **mock-genteel dominatrix**. She uses mostly plain speech
with 貴方, with flashes of keigo (`m134.6`, `m165.0`), ☆, うふふ and a shrill, girlish キャハハ
(`m134.46`). Her orders come in ladylike forms: 眺めてらして☆ (`m150.19`), 嘘おっしゃい
(`m154.1`), 見えなくてよ (`m154.17`), 御上げ (`m157.12`), お見せっ (`m206.19`), お言い
(`m208.54`), and 〜おし, a commanding form Shinobu uses too (`m058.31` お行き). Once only, after
the buckshot, her line turns to katakana (`m168.18` ヤッテクレタワネ): the one moment she
sounds like a machine. In the opening she is the unnamed 女 (tags `name.15`, `name.17`), with
the same voice.
Murakumo calls her "the metal woman" and "the clockwork metal woman".

### Dr Ken Kusanagi (クサナギ・ケン), about 34
Hospital director, surgeon, UIA leader. He is nervous-looking, vain and contemptuous: "A
hospital lives by its image." He uses polite, clinical speech (〜ですな, 〜ですぞ, 〜たまえ, 君),
and he diagnoses injuries aloud as entertainment (`m148.1`). He is vain about his face
("this genius physician's face!", `m176.74`). His address to Murakumo falls in steps: 貴方
(`m051.7`), then 君 or ムラクモ君 with ですぞ (`m162.4`), then 貴様 when his face is shot
(`m176.74`). He laughs ウフフフ too (`m159.16`). He is not a fighter: "a needle gun; even an
amateur like me can hit with it" (`m176.19`).

### Hinamura (ヒナムラ), Shinobu's assistant, about 22
A young man (僕), polite (です/ます, ムラクモさん) and cheeky: the "blacklist of every girl in the
bureau" (`m056.14`). He stammers "あのあのあの…" and recites the weather in katakana when he must
"have seen nothing" (`m019.5`). On the Shinobu branch his throwaway remark about sex and stress
gives Murakumo the key deduction (`m100.30`). On the Yuki branch Murakumo gets there himself
(`m099.35`).

### Mami Inaba (イナバ・マミ), nurse, about 15
Misa's friend. She is frightened, polite, and tearful about Misa's lost dream of qualifying.

### Gori (ゴリ) and Snake (スネーク, also スネイク), about 10 and 6
Mafia muscle hired as guards. **Gori**: 2 m tall, killed three men in underground wrestling,
"steroids injected right into his brain", silicon and steel plates under his skin. His speech
is a slurred, drawling cartoon oaf's, and lewd (イヒヒヒ, お姉ちゃん達, 〜のだぁ, ぶん投げちゃるぅ,
痛えじゃねいか). Murakumo calls him 漫画みたいな奴 (`m075.57`). **Snake**: lanky,
reptilian, "draw faster than Snake and you still won't shoot faster". His reflexes were sped up
with drugs, so the pain of losing his hand is unbearable to him. The two spellings of his name
are one man.

### Shikakura (シカクラ), about 8
A bearded, middle-aged arms dealer serving 80 years. He is calm, amused, and won over by
Murakumo's frankness ("あんた、気に入った").

### Minor
Kandori (カンドリ), a woman colleague in the human rights section, seen once (`m008.44`). Takao
Yajima, the taxi driver, known only from the report. The uniformed police, silent and hostile.
Two guards with tonfas (警備員Ａ, Ｂ). Three homeless witnesses in the opening. A and B speak
rustic dialect (だべ, みようべ). C's line is brassy woman's speech (`m207.9` 〜じゃないのさぁ). Misa (ミサ), heard only on the recording
(`m129.15`) and, unnamed, in the opening.

---

## 6. What the game is doing, and how

- **A clown who is not a clown.** The hero's camp manner is introduced in the first minute and
  never explained away. Shinobu's account of his past (`m057`) and his own line about the slums
  (`m031.3`) give the second reading. A translation that makes him merely silly loses the raid;
  one that makes him brooding early loses the first half.
- **Women as objects, and a narration that both condemns and enjoys it.** Body drugs, the
  slave markets, the recordings, Reiko's sadism and what is done to Yuki all show women reduced
  to things, and Yuki states the theme (`m027.8`, `m118.5`). The narrator also consumes what he
  condemns. The sight in the lab is 淫らだった (`m157.47`, also `m158.26`), and in captivity
  he grows fond of her fallen state (`m198.56`). The healing scene speaks the same language
  of possession (`m185.117` 奪って, `m188.47` ボクのものだ, `m188.115` ムラクモのモノ), and it
  deliberately answers the lab's vow. A translation keeps both the indignation and the
  prurient gaze. Tilting the lab or captivity narration toward pity falsifies it.
- **The title.** The "Virgin" of the title is both the drug and Yuki, who is still a virgin
  when it is used on her (`m153.8`, `m158.6`). In Ending No.3 she becomes "an angel with broken
  wings" (`m202.11`). Murakumo's own body becomes the object in the captivity endings.
- **Echoes.** These come back within one playthrough, or across endings in the same words,
  and each gets one rendering, used every time:
  - 自分を責めるな, "don't blame yourself": `m081.44` → `m083.11` → `m185.28`;
  - お前の事が好きなんだ, "if once isn't enough, a hundred times, a thousand": `m185.28` ≈
    `m202.16` (only the last verb differs: 言い続けたっていい / 言い続けてやる);
  - 使う, to spend his all on her: `m177.0` → `m183.19`;
  - 私専用のボディ・ドラッグ: `m140.1` (and its twins) → `m138.6` / `m142.6` → `m195.5`;
  - ストレス, the plot's keyword: `m065.49`, `m099.13`, `m100.18`, `m123.0`, `m208.11`, one word
    everywhere;
  - プリン, the brain like a pudding: `m075.75` / `m076.77` → `m170.29`, `m175.0`;
  - オモチャ: the gun (`m165.34`) → Reiko (`m176.3`) → Yuki (`m198.26`, `m202.4`);
  - フェラチオ: the lab (`m157.2`) → the gun in Reiko's mouth (`m170.27`), which answers it;
  - 全治４週間: Kusanagi's diagnosis (`m148.1`) → the epilogue (`m183.0`);
  - 幸せになって: `m096.16` → `m188.77`;
  - 心のつながり: `m191.48` → `m191.58`;
  - 尻尾, the tail: `m101.8` → `m105.23` → `m125.0`;
  - 住む世界が違う, "another world": `m018.19` → `m025.5` → `m031.5`;
  - 道具 (Yuki: women as tools) against 玩具 (Reiko: a toy), kept as two different words;
  - the cherry-like tongue (§5, Yuki); the forest park and its cottage (`m081.3` → `m126.13` →
    `m191.42`); the ear-pulling cry (`m017.0` = `m057.62`).
- **Route twins are not echoes.** `m029.5` / `m032.14`, `m031.3` / `m033.3`, `m006.10` /
  `m007.14`, and the two versions of the palm strike and of the shot are alternatives on
  different branches, and a player sees one of each. They are translated alike (§2.3) but carry
  no recall. `m032.14`–`m032.20` is not a copy of `m029.5`: the speech is split around Yuki's
  silence and adds 時々は泣くこともネ☆, so the translated sentence must break at the same place.
  `m061.16` paraphrases it (付き物), and Murakumo notices (`m061.24`). The sweet coffee belongs to
  the leave-her branch (`m032`); `m029.16` is plain coffee.
- **Sasame's double reading** (§5).
- **Reiko's double reading** (§5).
- **Abrupt tonal cuts.** A joke follows a corpse (`m005.55`), and a quip follows a mutilation
  (`m075.27`, `m077.25`, `m176.77`). The gun in Reiko's mouth is narrated as a sexual act
  (`m170.27`–`m170.29`). These cuts are the game's manner; do not smooth them.
- **Genre-savvy narration.** "In an action movie I'd shoot the gun out of his hand" (`m077.20`),
  "like a manga" (`m006.31`, `m075.57`), "in a film my shot would have killed him" (`m176.68`).
  Keep it as plain as it is.
- **Names from myth** *(inference)*. Ame-no-Murakumo is the first name of the sword
  Kusanagi, and Yata and Yasaka(ni) are the mirror and the jewel: with the sword, the three
  imperial regalia. So the hero and the villain carry two names of one sword, and the two women
  on the hero's side carry the other two treasures. Izumo, where the sword was found in the
  serpent's tail, is the name of the killer, and Takama, the high heaven, is her cover name.
  Inaba is the white hare's province. The text never comments on this. Keep the
  romanisation exact so that the pattern stays visible, and never gloss it. The Japanese order
  matters: アマノ・ムラクモ reads as Ama-no-Murakumo, the sword's name, only surname first, and
  クサナギ・ケン can be read as "the sword Kusanagi" *(inference: ケン = 剣)*. The record screens
  give surnames first too (`m035.18`, `m062.0`).
- **Other patterns** *(inference)*: a snow set (ユキ snow, フブキ blizzard, ササメ as in
  細雪 fine snow, the ‑セツ of ジョウセツ, 氷翼 Ice Wing, the Hokkaido ending) and the tail
  (`m101.8`, `m105.23`, `m125.0`; the sword came out of the serpent's tail).

---

## 7. Running gags and wordplay (each needs a decision in the language guide)

| Where | What |
|---|---|
| `m001.29`–`m001.58`, `m012.4`, `m060.1`–`m060.22` | "Ken-chan" and Kenzo's fury; Murakumo's coquettish poses |
| everywhere | 能面局長, "the Noh-mask chief"; "the man I hate most in the world" (`m176.39`, `m178.4`) |
| `m005.28`–`m005.35` | late because of "road works, three of them" (穴堀工事); Sasame: "the only digging was with one red-haired girl" (穴掘り: digging / sex) |
| `m018.23`, `m042.6` | 暴れん坊将軍, a famous period-TV title used as his name for his penis; "closed for business today" |
| `m021.9` | Virgin Angel: "a feeling that takes you up to heaven like an angel" |
| `m012.8` | 現場百回, the detectives' saw "a hundred visits to the scene" |
| `m019.0`–`m019.8` | Hinamura's "あのあのあの…" and the weather report in katakana |
| `m036.2`–`m036.5` | "You, doing overtime? It'll rain tomorrow" / "don't use me as a weather forecast" |
| `m045.12`–`m045.24` | Sasame's recorded lecture predicts the hero's swear word, a row of symbols (`○♀♀＠＊☆♂`), and quotes it back |
| `m048.23` | 耳年増: Shinobu "knows it all by ear" |
| `m056.11`–`m056.27` | the blacklist; Hinamura's snicker |
| `m059.5`, `m060.1` | "Has Kenzo woken up gay?"; "I'm normal, don't ask to borrow my backside" |
| `m063.16`–`m064.0` | ogling Reiko; Yuki behind him; "I wasn't looking at any backsides!" |
| `m074.17`–`m074.26` | Gori's and Snake's legends |
| `m074.50`–`m074.60` | Gori takes him for a girl; Snake: "the Toan agent is a man" |
| `m075.27` | "If you're giving up being a man, I know a good doctor" |
| `m100.30`–`m100.44` | (Shinobu branch) Hinamura's silly word for sex (エッチ) becomes the breakthrough, shouted back at him (`m100.34` エッチだ！); he begs forgiveness while being throttled |
| `m110.9` | "Too much bother, take the lot!" (he cannot choose ammunition, then must choose one) |
| `m170.27`, `m174.10` | "like a blowjob" with the gun; `m170.29`, `m175.0` "ejaculates" the round |
| `m176.77` | "open a dentist's, that face would do as a specimen" |
| `m193.42` | jokes about his new giant breasts: "can't fold my arms" |
| narration | stage directions in brackets: `（しょぼん）` `（ぷんぷん）` `（汗汗汗）` `（ほえ～ほえ～）` `（かっくん）` `（怒々々々）` `（発想の飛躍）` |
| `m019.5`, `m168.18`, `m002.13`, `m003.13` | speech in katakana as a voice quality: Hinamura's robotic weather, Reiko as a machine, Murakumo's mock-official ゴクロウさん and デース |
| `menu03.1`, `menu11.1`, `menu11.2` | the menus are in his voice and carry jokes: 能面局長, 貞操の危機だ！ (his chastity in danger), しなを作り (echoing `m001.32`) |

---

## 8. Adult content

The explicit sexual passages, by function:

| Keys | Scene | Function | Kind |
|---|---|---|---|
| `m018.0`–`m018.30` | Shinobu straddles him on the corpse table; Hinamura walks in | farce; introduces their affair | consensual, comic |
| `m083.36`–`m095.2`, menus 14–16 | the forest park | the turn of the love story; no intercourse: her first orgasm (`m093.48`); she stays a virgin | consensual, explicit |
| `m129.15`–`m129.23`, `m130.11`–`m130.22` | the recordings in the files | proof of what was done to Misa and the others | depicted abuse |
| `m149.45`–`m161.16`, `m162.15` | the lab | the assault on Yuki; Kusanagi takes her virginity (`m158.6`); her vow (`m159`) to save him | rape, explicit |
| `m184.43`–`m185.13`, `m186.0`–`m190.0` | the wedding night | healing; only her second time, the first with love (`m188.14`) | consensual, explicit |
| `m193.29`–`m193.49`, `m194.2`–`m203.0` | captivity (Endings No.3, No.4) | both reduced to sex objects; he finds she is unchanged inside | coerced, drugged, explicit |
| `m206.0`–`m209.44` | the opening | the murder of Misa, before the title | rape, torture, explicit |

Together these come to 499 of the 1 954 passages, plus the nine choices of menus 14–16. They
are translated like everything else, at the strength of the original: farce stays farce,
tenderness stays tender, and the cruelty of the lab, captivity and the opening is neither
softened nor heightened.

**Each scene has its own vocabulary, and the vocabulary carries the tone.** The prose is
pulp-erotic, neither clinical nor plainly vulgar:
- the park is coy and soft (女性自身, ピンクの突起, キスの雨), with clinical loanwords (ヴァギナ, ラビア);
- the lab is grotesque (双頭の魔物, イモムシ, 肉穴, 凶器), and semen is 汚物;
- the wedding night is flowery (珊瑚の粒, 花びら, 愛の泉, 男のくさび), and semen is 熱い思い
  (`m189.10`);
- captivity puts porn slang in Yuki's own mouth (ザーメン, チン○ン, ハメられ);
- the opening is S&M (華芯, 愛汁, 黄金の雫);
- Reiko's nursery word オチンチン belittles (`m153.39`).

`○` is the period's censorship convention. It covers vulgar words (オマ○コ) and clinical ones
alike (クリ○リス, アヌ○).

**Six passages are the editor's.** In six narration passages of the park scene, the text
compares Yuki's body to a girl's or a child's: `m084.0`, `m085.10`, `m086.0`, `m089.0`,
`m090.0`, `m093.45`. Yuki is an adult (§5), and the point of these lines is that she is a
virgin and inexperienced. The editor translates them, in `text/translation/editor_pl.tsv`
(keys only; the Japanese for reading goes to `build/tl/editor_pl_ja.tsv`), and merges them
into the translation with `tl.py put`. A model working on the translation leaves these rows
as it finds them. 美少女 and 少女の香り (`m158.23`, `m184.45`, `m186.0`) are ordinary words for an
attractive young woman and are translated as such, like 少女のような and 子供っぽい outside the
sexual passages (`m061.0`, `m096.2`, `m046.4`).

What the story needs from each scene, for whoever checks the lines around them:

- **The park:** they become lovers, by her choice, without intercourse; afterwards she weeps
  from relief.
- **The lab:** she is drugged, mutilated and raped in front of him. She swears to submit in
  exchange for his life (`m159`). He is helpless, and her degradation is the villains' show
  for him.
- **The wedding night:** she lets herself be loved again, as she asked: "drive out of me
  everything that is not you" (`m185.117`).
- **Captivity:** she has been operated on and controlled. What matters is the moment he
  understands she is unchanged inside, and his "I love you", which echoes `m185.28`
  (`m202.7`–`m202.16`).
- **The opening:** an unnamed tall woman tortures and kills a young woman who escaped from
  "monsters" and promised to keep a secret. The motive is the woman's "stress".

## 9. Music and pictures as cues

The music room (`bi.music.*`) names the 18 songs. The scenario plays them as character themes
(ムラクモ, ササメ, ユキ, シノブ, レイコ), plus 捜査 (investigation), 交渉 (negotiation), 戦闘
(fight), 病院１/２ (hospital), えっち１/２ (the love scenes), the openings, the endings and the
staff roll. The titles are all Japanese words or katakana names and are all translated. Names
stay names.

No picture carries text to translate. The ending cards are text (messages 210–213).

---

## 10. Open questions

- Who put the armoury key on Murakumo's desk is never said *(inference: Sasame, who later
  shows him the drawer, `m055`, and leaves it there for the night, `m108`)*.
- How much Sasame knew from the start is never said. "The body, yes" (`m098.29`) and the trap
  suggest everything.
- Who in the police leaked the conference's security plan (`m131.3`–`m131.8`) is not resolved.
- Why Reiko killed Misa so publicly: the opening gives her ストレス (`m208.11`). It is the same
  word as the brain-stress theory (`m065.49`, `m099.13`, `m100.18`, `m123.0`), so the murder is
  the theory in action. Murakumo first guesses a mafia warning (`m008.22`).
- Why the wedding is not registered (`m184.17`) *(inference: he is legally dead)*.
- A 27-year-old major general (`m062.0`) is what the text says.
- `m179.10` is tagged クサナギ (`name.08`), but Kusanagi is dead by then and the line is
  Sasame's (he holds out his hand, and Murakumo answers him). The tag is an error in the
  original. See the general guide §3. The line is also Sasame's first warmth.
