# Sound: music drivers, the engine's music layer and the song files (PC-98)

Scope: how `GAME.BAT` sets up the PMD family of drivers for each sound board, how M.EXE talks to
the resident driver (segments 048F and 04E4), the script statements that reach it, and the
inventory of `VA_Mnn.M/.N`, `VA_PCM__.PPC` and `VA_PPS.PPS`. Virgin Angel has **no sound
effects**: everything audible is background music.

The PC-98 `PMD.COM` is byte-identical (md5 `cd5634a197a3163734722da554ddadf8`) to the PMD 4.7g
that lrvne's PMD module reimplements (lrvne `docs/pmd.md`: the INT 60h API it models, the
parts, effects, fade and measure counter, and how it is checked against the real driver);
this document does not repeat the driver itself.

Conventions: M.EXE addresses are `SEG:OFF` of the unpacked image (as in `resources/derived/listing/m.asm`;
names in `docs/re/listing/m-names-sound.tsv`, sound listing `resources/derived/listing/sound.asm`).
Driver addresses are COM offsets (`PMD86:xxxx`, ORG 100h). Statement numbers `Snnnn` are the
0-based indices of `resources/derived/scenario/pc98_scb.txt`; call/goto targets in that dump are
1-based (call 1670 enters S1669). **verified** = read in code and, where marked *(emu)*, run;
**inferred** = reasoned, not proven.

Tools and data produced (all output in `resources/derived/music/`):
* `re-tools/sndcall.py` — runs M.EXE's sound layer under `re-tools/mcall.py` with a fake resident
  PMD at INT 60h (and fake PPSDRV at INT 64h); logs every driver call, every file the game tries
  to open, the music buffer contents and a simulated VSYNC for fades. Output: `sndcall.txt`.
* `re-tools/pmdinfo.py` — a `.M` dumper (OPNA part kinds, `t` tempo, per-driver
  audible parts, `--rhythm` drum bits). Output: `index.tsv` (one row per song).
* `re-tools/pmdemu.py` — a unicorn harness running the real `PMD.COM` on a fake YM2203,
  defaults changed to VA (`/DF5 /K /M8 /V0 /E0`, `VA_M*.M/.N`). Output: `vgm26k/*.vgm` + `render.log`.
* `va_pcm_ppc.tsv`, `va_pps.tsv` — sample tables of the PCM and PPS banks.

## 1. Summary

* The engine copies the song file straight into PMD's resident music buffer (address from INT 60h
  AH=06h) and starts it with AH=00h; it never asks the driver to load anything. Volume and fades
  are done by the engine itself through AH=19h (set fade-out volume), stepped on its own VSYNC
  timer, **blocking** the game while it fades.
* One `.M` per song serves every board ("兼用データ", dev notes). On OPNA drivers (PMD86, PMDB2) the
  engine masks the rhythm part K and unmasks the PCM part J, so drums come from PCM; on PMD.COM
  (26K) J is never processed and K plays SSG drums (or PPS samples through PPSDRV + PDR). FM parts
  D–F (FM4–6) are silent on PMD.COM. `.N` files are songs without a K part and get no K mask.
* Script statements: **1Bh** play (volume %, file), **1Ch** blocking fade-out-and-stop over n/100 s,
  **35h** var1 = PMD measure counter + 1 (−1 if no driver / not playing) — used twice to synchronise
  the opening with the music.
* GAME.BAT option 4 (no driver) leaves INT 60h without the "PMD" signature: every music call is a
  no-op, statement 35h yields −1 and the scenario then skips its music waits.

## 2. Driver set-up (GAME.BAT)

### 2.1 Board detection — ONGCHK.COM (**verified**, disassembly of all 851 bytes)

No banner; contains `*+=-PMD ADPCM RAM Check Data-=+*` (a KAJA-style board checker, author **inferred**).
Probes in this order, exit code in `0452h`:

| step | probe (ports as PMD.COM probes them) | code |
|---|---|---|
| `021E` | YM2608 with extended ports active at 088h/188h/288h/388h (A460h bits 0–1 cleared first) | 2 |
| `0177` | 86-type board: A460h present, ID 01h at 188h/288h with extended ports reading FFh; enables the extension (A460h bit0, A66Eh bit0 cleared, `out 6Eh,1` on PC-9821) | 3 |
| `0111` | YM2203 at 088h/188h/288h/388h (reg 0Bh write AAh / read back) | 1 |
| — | nothing found | 0 |
| `02BB` | if code ≥ 2: write the 32-byte check string to ADPCM RAM (bank-1 regs 00h/01h/02h–05h/0Ch–0Dh/08h) and read it back; equal → code += 2 | 4 / 5 |

So 0 none, 1 26K-compatible, 2 FM×6 without PCM, 3 86 board, 4 Speak Board (OPNA + ADPCM RAM),
5 "ちびおと" (86 + ADPCM). These match GAME.BAT's messages. ONGCHK never returns 6.

### 2.2 The five setups (GAME.BAT; `HDGAME.BAT` differs only in the `gdata.lib` path)

`if errorlevel==N` is DOS's "exit code ≥ N".

| key | menu text (abridged) | commands |
|---|---|---|
| 0 | 26K, no PSG-PCM (V30, 400 KB) | ONGCHK ≥ 6 (never): `pmd /DF0 /DS0 /K /M0 /V0 /E0`; ≥ 3 (86/SPB/ちびおと): `pmd /DF4 /K /M8 /V0 /E0`; else `pmd /DF5 /K /M8 /V0 /E0` |
| 1 | 26K with PSG-PCM (460 KB) | `pdr`, `ppsdrv /f va_pps.pps`, then the same three-way `pmd` choice as key 0 |
| 2 | 86 board / ちびおと, PCM (530 KB) | `p86drv /8`, `pmd86 /DF8 /DP50 /S /K /M8 /V0 /E0`, `cnvload va_pcm__.ppc` |
| 3 | Speak Board / 音美ちゃん, PCM (420 KB) | `pmdb2 /DF10 /DS0 /DP25 /K /M8 /V0 /E0`, `pmdpcm /lrva_pcm__.ppc` |
| 4 | no FM (390 KB) | nothing |

then `m cmd00.scb b:\gdata.lib`; afterwards `pmd -r`, `pmd86 -r`, `pmdb2 -r`, `p86drv -r`,
`ppsdrv -r`, `pdr -r`, `msz -r`.

Option meanings (PMD.COM: its installer code; PMD86/PMDB2: their usage text, **verified** strings):
* `/Mn` music buffer n KB — 8 is PMD's minimum; the largest song (`VA_M01.M`, 6431 B) fits. `/V0`
  no separate voice buffer (all songs embed their voices), `/E0` no FM-effect buffer (no effects).
* `/DFn /DSn /DPn` FM / SSG / PCM volume-down (0 = loudest). PMD.COM's default DF is 16, so the
  26K setup (`/DF5`) and the 86-via-PMD.COM setup (`/DF4`) make FM louder relative to SSG;
  PMD86 `/DF8 /DP50`, PMDB2 `/DF10 /DP25` balance FM against the PCM drums.
* `/K` ESC/GRPH stop/fast-forward hot keys off.
* `/S` (PMD86 only): "PCMパート仕様をPMDB2に合わせる" — PCM part J follows PMDB2 semantics, so the
  same J data plays on both OPNA drivers (`/S` is accepted but never read in PMD.COM).
* `p86drv /8`: 8 × 16 KB = 128 KB PCM buffer. `cnvload` converts the ADPCM bank `.PPC` into
  P86DRV's PCM buffer (help text: `.PPC loader for P86DRV *TEST*`; without `-f` it resamples
  16 kHz → 16.54 kHz, **inferred** from the help text). `pmdpcm /lr` = "PCM All Load (Always)" into
  the Speak Board's ADPCM RAM. Dev notes: "スピークボードと８６ボードでPCMデータを共有しています".
* `ppsdrv /f` sizes the PPS buffer to the file and loads it; `pdr` (no options) is the SSG-PCM
  player PPSDRV uses (INT 63h).

Quirks (**verified** against ONGCHK and the board probe of PMD.COM): the Speak Board branch of keys 0/1 is
dead (ONGCHK's maximum is 5) and would fail anyway (`/M0` < 8 KB: PMD refuses to install). A Speak
Board or ちびおと with key 0/1 therefore gets `pmd /DF4`, and code 2 (OPNA without PCM) and code 0
(no board: PMD installs with its no-board stub) get `/DF5`. Keys 2/3 are not checked against the
board ("搭載音源以上の物を選択しても正常に鳴りません").

### 2.3 Driver versions

| file | size | md5 | identification (strings) |
|---|---|---|---|
| PMD.COM | 19699 | cd5634a197a3163734722da554ddadf8 | PMD 4.7g, 1994-07-17, KAJA |
| PMD86.COM | 25297 | beeaaf7afc89facb13a50aa3fbc9b981 | "Ｍｕｓｉｃ　Ｄｒｉｖｅｒ　Ｐ．Ｍ．Ｄ． for PC9801/88VA Version 4.7g", "PMD86 ver.4.7g" (YM2608 + 86 PCM) |
| PMDB2.COM | 24903 | 384103e43052f25b97891d7dfdfe58f6 | same banner, "PMDB2 ver.4.7g" (YM2608 + ADPCM) |
| PPSDRV.COM | 2127 | 638be054bb39c2c8b22572daf2778c46 | "PDR Driver [PPSDRV] for PMD ver.4.2～ version 0.3", 1994/06/08, Kaja; signature `PMP` at INT 64h vector+2 |
| PDR.COM | 4203 | 8e152c8cee1ca6afea7af21948c5c12e | "SSGPCM(x2)sound driver for PC-9801 Version 2.9", 1992, Jul.8th 1994, NaoNeko, Kaja |
| P86DRV.COM | 1721 | 44b1ddfab1b3510884d38b0756341d38 | "Resident .P86/.PC8 Driver for PMD86 version 0.2", Jun.6th 1994 |
| PMDPCM.EXE | 5551 | (not hashed) | "PMD ADPCM Setting Tool for PMD ver.4.4～", Jul.5th 1994 |
| CNVLOAD.COM | 5197 | a61223e0db99d804848aec67cfcb2079 | ".PPC loader for P86DRV *TEST*" (file date 1994-12-20, no version) |
| ONGCHK.COM | 851 | 7cd2e864e7cc9a7e07fff28cb96c76d0 | no banner (§2.1) |

What M.EXE can tell apart (**verified**): INT 60h AH=09h returns AL = **00h** in PMD.COM (`PMD:2492`,
also on an 86 board), **02h** in PMD86 (`PMD86:31DE`), **01h** in PMDB2 (`PMDB2:2ED6`), FFh when PMD
has no board; constants, never patched. All three drivers carry `"PMD"` at
vector+2. PMD86's part-mask table (AH=1Eh, `PMD86:3583`, table `PMD86:368B`, 3 bytes: part,
channel, type): 0–2 FM1–3 A–C, 3–5 FM4–6 D–F (type 1 = bank 1), 6–8 SSG G–I, 9 PCM J (type 3),
0Ah rhythm K (type 4), 0Bh–0Dh FM3-extended parts, 0Fh effect part (**verified** table; that D–F
of a `.M` header land on FM4–6 is **inferred** from this table and PMD's part order).

## 3. The engine's music layer (segments 048F and 04E4)

048F is a thin PMD binding (all driver calls go through the MS C `int86x` at `0886:0B1A`; its 13
call sites are all in 048F — **verified** by a listing search: there is no INT 60h/61h/64h
instruction anywhere else); 04E4 is the API the VM and the built-ins use.

### 3.1 State

| variable | meaning |
|---|---|
| `DS:01CC` g_mus_ok | 04E4 initialised (1) — every 04E4 call is a no-op when 0 |
| `DS:01B2` g_pmd_present | PMD detected |
| `DS:17A6` g_pmd_state | **0Ah playing, 0Bh idle, 0Ch no driver** (`04E4:01D8`/`048F:025C` return it) |
| `DS:17A4` g_pmd_board | AH=09h AL as a signed word: 0 PMD.COM, 1 PMDB2, 2 PMD86, −1 PMD without board |
| `DS:17A0` | far pointer from AH=06h (= byte 0 of the `.M` image) |
| `DS:01D0` g_mus_name | char[19], the name as the script wrote it (`"va_m01.m"`), initially `"none"` |
| `DS:01CE` g_mus_vol | current volume in percent (0–100) |
| `DS:178C`, `DS:17BE`, `DS:179C/179E/178A` | /M size, PPS flag, PPSDRV buffer address/size — written at init, **never read** |

### 3.2 Initialisation and termination

`run_game` (`001E:0096`) calls `mus_init 04E4:0004` once (and registers `mus_term 04E4:0021` with
atexit); MUSMODE (`0504:0B16`) calls it again (no-op when already done).

`pmd_init 048F:0008` (**verified**, *(emu)* `sndcall.txt`):
1. `pmd_detect 048F:0282`: far pointer at 0000:0180 (INT 60h vector); bytes +2..+4 must be `P M D`.
   No signature → state 0Ch, return 0 (no message; the game runs silent).
2. `pmd_query 048F:02B2`: `segread`; **AH=06h** → music buffer DS:DX; **AH=22h** → AL = /M KB (stored
   ×1024, unused); **AH=09h** → board type; **AH=17h** → PPS flag (AL==1); `pps_probe 048F:0422`: if
   INT 64h vector+2 = `PMP` (PPSDRV) then **INT 64h AH=04h** (PPSDRV returns DS:DX = its PPS buffer,
   CX = size — PPSDRV:01C7) else PPS flag = 0. All results stored, none used later.
3. state 0Bh; **AH=01h** (stop).

`pmd_term 048F:0054`: if playing, AH=01h; state 0Ch. The engine never calls PMD's own removal; the
batch file does.

### 3.3 Play — `mus_play 04E4:0034(char far *name, int vol)` (statement 1Bh, MUSMODE)

```
if !g_mus_ok: return 0
if state == 0Ah:
    if strcmp(name, g_mus_name) == 0: return 1          ; exact, case-sensitive: song keeps playing
    mus_stop()                                          ; AH=01h, no fade
strncpy(g_mus_name, name, 19)
pmd_load_play(name, vol); g_mus_vol = vol; return state
```
`pmd_load_play 048F:0073` (**verified**, *(emu)* with all four board types):
```
if state == 0Ah: AH=01h; state = 0Bh
base = name up to the first '.' (SJIS-aware, mk_song_name 048F:04B3)   ; the script's ".m" is ignored
try base".n"  -> found: masks(2)
else if board == 0 (PMD.COM): try base".s" -> found: masks(1); else masks(0), try base".m"
else (PMD86, PMDB2, no board): masks(0), try base".m"
not found: return 0 (state stays 0Bh: the old song is stopped, silence)
pmd_read_song 048F:03DD: if board == -1 -> fail (nothing read, nothing started)
                         fseek(fp,0); fread(musbuf, filelength, 1, fp)     ; no size check vs /M
fclose; pmd_set_vol(vol) (AH=19h); cli; AH=00h; sti; state = 0Ah; return 1
```
`pmd_set_masks 048F:0376(kind)` acts only when board is 1 or 2 (PMDB2/PMD86):
kind 0 (`.m`) → **AH=1Eh AL=0Ah** (mask part K), then AH=1Eh AL=89h (unmask J);
kind 2 (`.n`) → AH=1Eh AL=88h (unmask I), then AL=89h; kind 1 (`.s`) → nothing.
A PMD mask survives song starts, so after the first `.m` K stays masked for
the rest of the session; `.n` songs have no K part, so this is harmless. Nothing ever masks I or
J, so the two unmask calls have no effect (purpose unknown, perhaps defensive). No `.s` file
ships: on PMD.COM every `.m` song costs one failed open of `.n` and one of `.s` (**verified** *(emu)*:
`va_m01.n, va_m01.s, va_m01.m`).

The volume operand: `pmd_set_vol 048F:0227(v)` writes AH=19h AL = (−trunc(255·v/100) − 1) & FFh,
i.e. 255 − trunc(2.55·v): 100 → 00h, 75 → 40h, 50 → 80h, 25 → C0h, 1 → FDh, 0 → FFh *(emu)*. At
song start it is immediately overridden: AH=00h clears the fade volume (PMD.COM `PMD:037F`,
PMD86 `PMD86:0CF8`; PMDB2 **inferred** the same). The operand therefore only matters as the
starting level of a later fade; every script use is 100.

### 3.4 Stop and fade

* `mus_stop 04E4:00A7`: if playing, `pmd_stop 048F:01F7` (AH=01h, state 0Bh); g_mus_vol = 0. The
  name is kept, but the same-name test only applies while playing, so the next play of that name
  restarts it. No retry on a busy driver (PMD only defers when called from inside its own
  interrupt, which cannot happen here).
* `mus_set_vol 04E4:00C9(v)`: if playing, AH=19h and g_mus_vol = v (used only by the fade).
* `mus_fade_stop 04E4:00F0(t)` (statement 1Ch, MUSMODE) — **blocking**, **verified** *(emu, simulated VSYNC)*:
  ```
  if !playing: return 0                         ; no wait at all
  h = timer_start(t)                            ; 0752:0026, t in 1/100 s, target = t*564/1000 VSYNCs
  v0 = g_mus_vol
  until timer_done(h):
      e = timer_elapsed(h)                      ; 1/100 s, = VSYNC count*1000/564
      pmd_set_vol((t - e) * v0 / t)             ; AH=19h
      busy-wait until timer_elapsed changes     ; i.e. one VSYNC
  timer_free(h); mus_set_vol(0) (AH=19h AL=FFh); mus_stop() (AH=01h)
  ```
  Linear in percent, one AH=19h per VSYNC. `t = 320` → 180 VSYNCs, 181 AH=19h writes, ≈3.19 s at
  56.42 Hz; 200 → 112 (≈1.99 s); 150 → 84 (≈1.49 s); 1 → target 0, ends at the first VSYNC. The
  timer counts VSYNC interrupts with the fixed constant 564 (graphics/platform docs), so at a
  31 kHz display the same fades are shorter. If no timer slot is free (16 in use) or the timer is
  not initialised, it stops at once. The game does not poll input during a fade.
  PMD applies the fade volume per part at its next note/LFO update and
  PMD.COM plays no K drums while the fade volume ≠ 0 (lrvne `docs/pmd.md`), so on a 26K the drums
  drop out at the first step of every fade.
* PMD's own fade (AH=02h) and the `/F` option are not used.

### 3.5 Measure query — `mus_measure 04E4:01E9` (statement 35h)

Returns −1 if no driver or not playing, else AH=05h (PMD measure counter) + 1 (`048F:026B`,
`048F:0494`). PMD's measure counter starts at 0 on AH=00h. Nothing reads AH=0Ah status or the
loop counter: the engine never waits for a loop or song end.

### 3.6 Complete list of driver calls

| when | calls |
|---|---|
| start-up (`mus_init`) | INT 60h AH=06h, 22h, 09h, 17h; INT 64h AH=04h if PPSDRV is resident; INT 60h AH=01h |
| play | [AH=01h if playing] [PMD86/PMDB2: AH=1Eh AL=0Ah or 88h, AH=1Eh AL=89h] — file copied into the buffer — AH=19h AL=vol, AH=00h |
| stop | AH=01h (only while playing) |
| fade | AH=19h every VSYNC, AH=19h AL=FFh, AH=01h |
| statement 35h | AH=05h (only while playing) |
| exit (`mus_term`) | AH=01h if playing |

Not used: AH=02h–04h, 07h, 08h, 0Ah, 0Bh–0Fh (no FM/SSG/PCM effects), 10h–18h except 17h, 1Ah–1Dh,
1Fh–21h; PPSDRV is never asked to play anything (PPS samples are only reached through PMD's K part).

### 3.7 Without a driver, or with PMD but no board (**verified** *(emu)*)

* No `PMD` at INT 60h (key 4, or a failed install): `mus_init` returns 0, g_mus_ok = 0; play/fade
  return 0 immediately, `mus_state` = 0Ch, statement 35h → −1. MUSMODE refuses to start
  ([platform.md](platform.md) §5.5).
* PMD installed without a board (keys 0/1 on a machine without FM): init succeeds (board −1), every
  play opens the file but reads nothing and never sends AH=00h, so state stays 0Bh and statement 35h
  gives −1 as well; the same song name is retried (opened) on every request.

## 4. Script side

| statement | operands (dump order) | handler | effect |
|---|---|---|---|
| 1Bh | `w` volume % (always 100), `s` file (`"va_mNN.m"`) | `001E:0A3F` → `mus_play(name, vol)` (name at operand +0, vol at +14h) | §3.3 |
| 1Ch | `w` t (1, 200, 320) | `001E:0A52` → if `mus_state` == 0Ah: `mus_fade_stop(t)` | blocking fade over t/100 s, then stop |
| 35h | — | `001E:0A6D` → var1 = (int) `mus_measure()` | §3.5 |

The scenario never uses 1Bh directly for story cues: it sets v20 = song number and calls
subroutine 1670 (S1669), which compares v19 (current song), fades the old song out with 1Ch 320
(sub 1667), sets v19 = v20 and dispatches v20 = 1..21 to the 21 statements 1Bh at S1678–S1727;
v20 = 0 means "fade out, silence". Sub 1664 (1Ch 1, v19 = 0) stops at boot. Details, save/load
handling of v19 and the song use per chapter: [script-catalog.md](script-catalog.md) §7.
One inline 1Ch 200 (S699, chapter 9).

The two **music synchronisations** (statement 35h polled in a tight VM loop, no wait in between):

| where | song | loop | condition | measured time after song start *(emu, PMD.COM)* |
|---|---|---|---|---|
| S1757–S1765 (opening) | 1 (`VA_M01.M`) | until var1 ≥ 3, then wait 100 (1 s) | PMD measure counter ≥ 2 | 3.56 s (+1 s) |
| S1888–S1895 (opening, title/staff part) | 19 (`VA_M19.M`) | until var1 ≥ 5 | measure counter ≥ 4 | 7.32 s |

With var1 < 0 (no music) both loops are skipped — and at S1759 the following 1 s wait too. If a
driver is present but the song is not playing (file missing), var1 is also −1, so the game cannot
hang there.

**MUSMODE** (sound side; screen flow in [platform.md](platform.md) §5.5): song list at `0ABB:0728`
(8-byte rows: far file name, far title — the strings are in DGROUP), 18 rows, counted at
`0504:0B25`. RETURN/SPACE/left button: if a song was already started in this visit,
`mus_fade_stop(150)` (1.5 s, blocking), then `mus_play(file, 100)` (`0504:0AB3–0AD1`). Because the
fade stops the song, re-selecting the playing title restarts it. Leaving: `mus_fade_stop(150)` if
a song was started (`0504:0AFD`). Not listed: VA_M08, VA_M20, VA_M21.

Engine-internal music: none besides MUSMODE (no music in the other built-ins; xrefs of
`mus_play`/`mus_fade_stop` are only `op_1b`/`op_1c` and MUSMODE).

## 5. The song files

### 5.1 Format and the `.N` files

All 21 files are MC 4.7 compiled PMD songs (`00` type byte, version byte 47h, `FEh` marker, voices
embedded), parsed completely by `pmdinfo.py` (every part ends exactly where the next begins — **verified**).
Header and bytecode: `re-tools/pmdinfo.py`, lrvne `docs/pmd.md`. Memo table (MC 4.7): [0] `#PPSFile` (`VA_PPS.PPS`,
empty in VA_M11), [1] `#PCMFile` (`VA_PCM__.PPC`), [2] title `Ｖirgin ＡNGEL (C)CRYSTAL SOFT ～ …`,
[3] composer and [4] arranger `せんたろ`, [5..] memo (dev notes name 柴田 泉 as composer; that
`せんたろ` is his handle is **inferred**).

`.N` is not a different format: the five `.N` songs (02, 11, 14, 18, 20) are exactly the songs
**without a K part** (none of the `.M` songs lacks one). The extension only steers `pmd_set_masks`
(§3.3): `.N` songs do not mask K on OPNA drivers. The script always names `va_mNN.m`.

Command bytes worth noting: pan `p` (ECh) in A–F/J (ignored by PMD.COM), no `s`/CFh slot masks and
no FM3-extended `C6`, no SSG/FM effect commands, no `~` status marks; tempos are `t` (FC FF), with
ritardandi in VA_M01 and relative changes in VA_M11.

### 5.2 What each board plays (**verified** for PMD.COM by emulation; OPNA **inferred**)

| setup | driver | FM | SSG | drums | other |
|---|---|---|---|---|---|
| 0: 26K (also 86/SPB on key 0) | PMD.COM | A B C | G H I | K → PMD's built-in SSG drum effects on SSG3 (only the lowest set bit of each hit) | D–F silent, J ignored, pan ignored |
| 1: 26K + PSG-PCM | PMD.COM + PPSDRV + PDR | A B C | G H I | K → PPS samples from `VA_PPS.PPS` (PDR single mode: one at a time) | as above |
| 2: 86 / ちびおと | PMD86 /S + P86DRV | A–F | G H I | J (PCM samples, converted from the `.PPC`); K masked | stereo pan |
| 3: Speak Board / 音美ちゃん | PMDB2 + ADPCM RAM | A–F | G H I | J (ADPCM from the `.PPC`); K masked | stereo pan |

PMD.COM evidence *(emu, `vgm26k/`)*: across all 21 renders the only key-on values are 00–02/F0–F2
(channels 1–3, all slots) and reg 27h never leaves normal FM3 mode, i.e. parts D–F never sound
(their slot mask stays empty without CFh); SSG noise (reg 06h) is written
hundreds of times in every song with a K part and 0–1 times in the `.N` songs. PMD86's handling of
J/K and pans was read only from the mask table and usage text — not run.
The composer's own remark: "パート割りが強引にまとめているので、26kユーザーの方にはちょっとツラいかも".

### 5.3 Inventory (`resources/derived/music/index.tsv`)

Times: real PMD.COM under `pmdemu.py` (intro + loop body; status2 1→2), **inferred** identical on
PMD86/PMDB2 (same Timer-B tempo model). Titles: music-mode table (MUSMODE), else memo title.
"used" = v20 requests in the scenario (statement indices of `call 1670`, script-catalog.md §7).

| file | size | MUSMODE title | memo title / line | parts | tempo | intro + loop s | J samples | K drum bits | used |
|---|---|---|---|---|---|---|---|---|---|
| VA_M01.M | 6431 | オープニング１ | Prologue.1/3 / プロローグその１ | ABCDE GH J K | t137, ritardando to t100, no L | 132.4, ends | 2 3 4 5 7 10 11 | 0 1 4–10 | S1755 (opening, measure sync) |
| VA_M02.N | 769 | えっち２ | Hｼｰﾝ２ | ABC GHI | t132 | 0.5 + 65.8 | – | – | S1560 |
| VA_M03.M | 2821 | ムラクモ | ﾑﾗｸﾓ / ムラクモのテーマ | ABCD GH J K | t147 | 1.1 + 29.9 | 2 3 4 5 7 10 | 0 1 4–7 9 10 | 2× |
| VA_M04.M | 1935 | ササメ | ｻｻﾒ / ササメ様のテーマ | ABCD GH J K | t137 | 0.3 + 35.5 | 3 4 5 7 | 0 1 4–7 | 2× |
| VA_M05.M | 2712 | 捜査 | 捜査 / 捜査シーン | ABCD GH J K | t127 | 4.2 + 45.2 | 3–7 9 10 | 0 1 4–7 9–11 | 4× |
| VA_M06.M | 1221 | ユキ | ﾕｷ / ゆきちゃんのテーマ | ABC GH J K | t127 | 0.4 + 45.2 | 3 4 7 | 0 1 7 | 9× |
| VA_M07.M | 1820 | シノブ | ｼﾉﾌﾞ / シノブさんのテーマ | ABCD GH J K | t137 | 0.3 + 42.5 | 3 4 5 7 | 0 1 4–7 | 5× |
| VA_M08.M | 3200 | – | ｼﾞｬｰﾝ;_; / 捜査シーン２ | ABCDE GHI J K | t117 | 10.1 + 45.2 | 3–7 9 10 | 0 1 4–7 9–11 | S149 |
| VA_M09.M | 2289 | 病院１ | 病院 | ABC F GH J K | t137 | 0.0 + 63.8 | 3–7 | 0 1 4 5 7 9 | 2× |
| VA_M10.M | 3161 | 戦闘 | 戦闘 | ABCDEF GH J K | t137 | 1.9 + 49.6 | 3 4 5 7 9 | 0 1 4–7 11 | 3× |
| VA_M11.N | 977 | えっち１ | Hｼｰﾝ１ | ABC GHI | t123/t140, SSG tempo changes | 29.1 + 28.8 | – | – | S617 |
| VA_M12.M | 877 | 病院２ | 病院2 | ABC GH J K | t111 | 0.3 + 13.0 | 3 | 0 | 3× |
| VA_M13.M | 753 | レイコ | ﾚｲｺ / 最強のぼでぃ女のテーマ | ABC GH J K | t102 | 4.8 + 38.1 | 3 6 | 0 9 | S1238 |
| VA_M14.N | 566 | エンディング１ | ｴﾝﾃﾞｨﾝｸﾞ(bad) | BC GHI | t137 | 0.3 + 39.9 | – | – | 2× |
| VA_M15.M | 2012 | 交渉 | 交渉 | ABC GH J K | t113 | 0.3 + 35.8 | 3 4 7 | 0 1 7 | 2× |
| VA_M16.M | 2700 | エンディング２ | ｴﾝﾃﾞｨﾝｸﾞ(good) | ABCDEF GH J K | t129 | 15.4 + 49.0 | 3 4 5 7 9 10 | 0 1 4–7 10 11 | S1532 |
| VA_M17.M | 4092 | スタッフロール | vaのﾃｰﾏ２ / スタッフロール | ABCDEF GH J K | t125 | 15.9 + 62.0 | 3 4 9 | 0 1 11 | 2× |
| VA_M18.N | 3873 | オープニング２ | Prologue.2/3 | ABCDEF GHI J | t123 | 146.7 + 67.9 | 1–4 6 7 9–11 | – | S1797 |
| VA_M19.M | 4959 | タイトル | Prologue.3/3(vaのﾃｰﾏ１) / タイトル画面 | ABCDEF GH J K | t131 | 22.3 + 58.5 | 3–9 11 | 0–2 4–9 11 | S1887 (measure sync) |
| VA_M20.N | 545 | – | ｺﾝﾋﾟｭｰﾀｰ / こんぴゅうた音 | AB GHI | t137 | 0.0 + 19.1 | – | – | S495 |
| VA_M21.M | 3093 | – | Inforation [sic] / 容量余ったからおまけ | ABCDE GH J K | TB 237 | 0.3 + 33.7 | 3 4 5 9 | 0–6 | S2005 (behind ANNOUNCE) |

The dev notes count 20 songs; VA_M21 is the leftover-space bonus its memo admits. MUSMODE calls
M14 "エンディング１" and M16 "エンディング２" where the memos say bad / good.

### 5.4 PCM and PPS banks

* `VA_PCM__.PPC` (62240 B): PMD ADPCM bank, header `ADPCM DATA for  PMD ver.4.4-  `, word = next
  free ADPCM-RAM address (079Eh, 32-byte units), 256 × (start, stop) in 32-byte units, then the
  YM2608 ADPCM data for addresses 0026h–079Dh (file offset = 420h + (addr − 26h)·32 — **verified** by
  the size). 11 samples, numbers 1–11, 768–13280 bytes (≈0.1–1.7 s at 16 kHz, rate **inferred**);
  table in `va_pcm_ppc.tsv`. Used by part J through PMDB2 (directly) and PMD86 (via CNVLOAD/P86DRV).
* `VA_PPS.PPS` (52246 B): 14 × (u16 offset, u16 length, u8 tone, u8 volume), 4-bit sample data from
  54h; 12 samples (0–11; 4, 5, 6 have tone 30 — the pitched drums of the frequent 4-5-6 fills,
  **inferred** toms), table in `va_pps.tsv`. Reached only via part K drum bit n → PPS sample n
  (PMD.COM).

## 6. Reference recordings

`resources/derived/music/vgm26k/VA_Mnn.vgm`: every song rendered by the real `PMD.COM` with GAME.BAT's
26K options on a fake YM2203 (`re-tools/pmdemu.py --all-music`; intro + two passes, VGM loop over
pass 2; VA_M01 ends without loop). These are what a **PC-9801-26K with setup 0** plays (also an 86
board or Speak Board with setup 0/1, since PMD.COM uses only the OPN subset there). They contain no PPS (setup 1) and nothing of parts D–F/J or the pans (setups 2/3).
Recording the OPNA setups would need `pmdemu.py` adapted to PMD86/PMDB2 (installer addresses,
the calibration patch, OPNA port 1, an 86-PCM / ADPCM model) — not done.

The 26K setup is also covered interrupt by interrupt: lrvne's PMD module was replayed against
real-driver logs of all 21 songs (`/DF5`, PMD's own SSG table, 30 000 interrupts each) with no
difference in any register write, clock, status or measure count ([../lrvne-fit.md](../lrvne-fit.md),
gap 10).

## 7. X68000 music (brief)

`resources/original/x68k/VA_Mnn.M`: 21 files, all `.M` (no `.N`), for `PMD.X` "for X68000 (Version
3.9f) Copyright (C) Aug.18th 1992 by M.Kajihara" (OPM). Type byte 01h, 12 little-endian part/table
offsets, data from 1Ah; no memo strings. Sizes 9–36 % below the PC-98 files. Part offsets show the
same arrangement: e.g. VA_M02 A/B/C start at 1Ah/A6h/130h vs the PC-98 `.N`'s 1Ah/A7h/131h, and the
three PC-98 SSG parts reappear as the next three parts (**inferred**: SSG lines moved to OPM FM
channels). Same 21 songs, converted rather than re-composed (**inferred**); not analysed further.

## 8. Behaviour a reimplementation must reproduce

* Engine semantics to keep: same name while playing = no-op (exact, case-sensitive compare of the
  script string); a new song stops the old one without fade (the scenario fades first via sub
  1667); fades block the game and step once per VSYNC; statement 35h exposes PMD's measure
  counter (+1, −1 when silent) and drives the opening timing; no driver ⇒ −1 and skipped waits.
* File choice: ignore the script's extension, prefer `.n`, else `.m` (`.s` only matters for
  PMD.COM and does not exist).
* A faithful port must pick a board profile: 26K (A–C, G–I, SSG/PPS drums from K, no pan) or
  OPNA (A–F, G–I, PCM drums from J, K muted, pan). The OPNA profile is what the composer intended
  ("86ボードをお持ちの方は更に素晴らしい曲が聞けるわけですね"). The 26K profile is verified by the
  VGMs; lrvne's PMD module models exactly this PMD.COM.
* AH=19h volume follows `255 − trunc(2.55·v)`; PMD applies it at each part's next note/LFO step.

## 9. Open questions

* PMD86/PMDB2 behaviour was only read statically (AH=09h, AH=1Eh, mstart, usage); their part
  handling (D–F = FM4–6, J sample playback, `/S`, the effect of the K mask on the rhythm source)
  is not emulated, and no OPNA reference recording exists.
* What PMD.COM's built-in SSG drum effects 0–11 sound like for VA's bit layout (VA's PPS order
  has pitched samples at 4–6, while the bits follow the PPS bank) — irrelevant on PPS setups.
* Why the engine unmasks I (AH=1Eh 88h) for `.n` songs; and the intended content of `.s` files
  (perhaps the "music upgrade disk" the dev notes promise, whose files would replace these).
* Sample rates of the PPC (16 kHz assumed) and PPS (PDR picks 8 or 16 kHz automatically) banks.
