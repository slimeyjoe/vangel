# The scenario `CMD00.SCB` and the interpreter

`CMD00.SCB` holds the whole game logic: a compiled program of 2 034 statements for a small virtual
machine in `M.EXE`, with its variable, menu, expression and palette tables. The text it shows is
in a separate file (`CMD00.TXB`, [text.md](text.md)); pictures come from `GDATA.LIB`
([graphics.md](graphics.md)), songs from `VA_Mnn.M` ([sound.md](sound.md)). This document
specifies the file format, the virtual machine and every statement; the game's structure built
from it is in [script-catalog.md](script-catalog.md).

Addresses are `SEG:OFF` of the unpacked `M.EXE` (image-relative segments, as
`re-tools/madis.py` prints them). **Verified** = checked against the original code: the file
format by `source/tools/scb.py`, which consumes the file exactly (19 430 of 19 430 bytes, PC-98 and
X68000 copies), and by the original loader `063C:00E8` run under `re-tools/mcall.py`
(`re-tools/scb_verify.py`: header, counts and every table entry compared, both releases); semantics by reading the handlers.

The program looks compiled from a structured language: `if`/`else`, `switch` with `break`,
subroutines with `return`, typed variables (`int`, `bool`) and expressions with C-like
operators. The names of that language are not in the release; the names used here are ours.

## 1. Files and start-up

`GAME.BAT` runs `m cmd00.scb b:\gdata.lib`. `main` (`0468:000E`):

1. Without the scenario argument (argc < 2): prints `シナリオバイナリ(*.scb)を指定してください`
   and exits with code 1. (This is the one message of `main` that is printed: the others below
   go through `dbg_print` `0468:000C`, an empty routine, a debug print the release removed.)
2. `sys_init` (`0504:0004`, built-in 0 "INIT"): the console prompt `マウスを使用しますか?[Y/N]`
   ([platform.md](platform.md) §3), then `プログラムのロード中です...`.
3. Default file names are set (`0468:0191`): text `scenario.txb` (0BA1:0016), scenario
   `scenario.scb` (0BA1:002A), pictures `gdata.lib` (0BA1:008C). `argv[2]` (or NULL when absent)
   is kept as a far pointer at 0BA1:006C: the picture library's path
   ([graphics.md](graphics.md) for how it is opened).
4. `argv[1]` is copied over the scenario name (0BA1:002A) and opened with `fopen(.., "rb")`;
   failure: exit 1 (`file not found`, not printed).
   `scb_load` (`063C:00E8`, §2–§3); failure: exit 2 (`scenario reading...`, `error!`, `OK` are
   not printed).
5. `txb_load` (`0724:0018`) loads the text file named by the scenario (section 0Ah,
   `cmd00.txb`; without the section `scenario.txb`); failure: exit 2.
6. The entry statement (header word, §2.1) must be opcode 2Dh; otherwise execution starts at
   statement 1 (the warning `開始番地が設定されていません。先頭から実行します` is not printed). The
   test reads the statement table at the entry's number unchecked: an entry outside the table
   reads memory that is not the scenario's.
7. `run_game` (`001E:0069`) initialises the timer (`0752:0002`), sound (`04E4:0004`), input
   (`043A:0008`) and graphics (`0315:000E`) subsystems, registering each one's shutdown with
   `atexit`. A failing timer, input or graphics init prints `タイマーの初期化に失敗しました`,
   `入力系の初期化に失敗しました` or `グラフィックの初期化に失敗しました` and exits (4, 4, 1).
   Then `vm_run(entry)` (`001E:011F`) runs until a statement stops the machine (§5), and the four
   shutdown routines run in reverse order.

The console prompt of step 2 is on the DOS console (the text screen) before the game's
graphics start. **Verified** (code read; steps 4–6 also run under emulation; the loader by
`source/tests/check_scb.py`, which compares the engine's loader with the original's on both
releases and on damaged copies of the PC-98 file).

## 2. File layout

### 2.1 Plain header (read with `fgetc`, `scb_read_header` 06BB:01AB)

| Offset | Size | Value | Meaning |
|---|---|---|---|
| 00h | 4 | `CRSC` | signature, compared byte by byte (DS:1088); mismatch = load error |
| 04h | 2 | 01 01 | skipped (a version, inferred) |
| 06h | 4 | `DOS ` | skipped (target system, inferred) |
| 0Ah | 4 | 19 430 | file size, little endian; stored (0BA1:0006) but not checked |
| 0Eh | 4 | 0 | stored (0BA1:0070), not used elsewhere |
| 12h | 2 | 1 979 | **entry statement** (0BA1:0002) |
| 14h | 1 | 6Ah | **key** of the encryption (0BA1:0010); 0 = not encrypted |

### 2.2 Sections (plain, `scb_read_sections` 06BB:00F7)

A sequence of `tag` bytes, each followed by its data, ended by tag 0. Tags 1–3 and > 0Ch fail the
load. All counts are little-endian words.

| Tag | Data | Value in VA | Global | Meaning |
|---|---|---|---|---|
| 04h | count | 2 034 | 0BA1:000E | statements |
| 05h | count | 43 | 0BA1:0044 | menus |
| 06h | count | 430 | 0BA1:000C | expression nodes |
| 07h | count | 213 | 0BA1:0052 | messages in the text file (op 19h's limit) |
| 08h | count | 44 | 0BA1:000A | palettes |
| 09h | count | 20 | 0BA1:0042 | variables |
| 0Ah | word n (1..13), C string | 10, `cmd00.txb` | 0BA1:0016 | text file name (n is checked, then the string is read to its NUL) |
| 0Bh | count | 199 | 0BA1:00D4 | stored, never read (meaning unknown) |
| 0Ch | count | 61 | 0BA1:0004 | stored, never read (meaning unknown) |
| 00h | — | | | end |

VA's order: 04, 07, 05, 06, 08, 09, 0B, 0C, 0A, 00.

### 2.3 Encryption

Everything after the sections is read through `scb_getc` (`063C:0045`):

```
state = 0                      (a word, DS:1086, initially 0)
getc():  b = fgetc(f);  if key: state ^= b + key;  b = state & 0FFh
         return (signed char) b          ; cwde: the callers see -128..127
getw():  lo = getc() & 0FFh; hi = getc() & 0FFh; return hi << 8 | lo
gets():  bytes until a 0 byte (decrypted), the 0 included
```

Carries of `b + key` reach only the high byte of `state`, so the low byte evolves as
`s = s ^ ((b + key) & 0FFh)`. Signedness matters: a byte operand ≥ 80h is negative unless the
loader masks it (noted per operand below). **Verified.**

### 2.4 Tables, in file order

All tables are referenced **1-based** by the statements. Each loader allocates a pointer array
whose entry 0 points to an unused slot (see §7 for a consequence).

1. **Variables** (count tag 09h; `06DD:0004`): per variable `type` (byte), `initial value`
   (word). `type` must have bit 1 set (load fails otherwise). Types: 6 = integer, 10 (0Ah) =
   boolean — the same bits as expression leaves (§4). VA: 20 variables, all initial 0;
   bool: v3 v4 v12 v13 v15 v16 v18.
2. **Menus** (tag 05h; `06DD:016C`): per menu `n` (byte, 1..4, else load error), `size` (word:
   the total length of the strings plus their NULs, used to size the buffer), then `n` C strings
   (Shift-JIS) — the choices. Display and selection: [text.md](text.md).
3. **Expression nodes** (tag 06h; `06DD:021B`): per node a byte `form`:
   * 0 → operator node: `op` (byte), `left` (word), `right` (word) — node numbers;
   * 1 → leaf: `kind` (byte), `value` (word);
   * other → load error.
4. **Palettes** (tag 08h; `06DD:0347`): per palette 24 bytes = 48 nibbles, high nibble first;
   entry *i* (0..15) takes nibbles 3i, 3i+1, 3i+2 as its components c0, c1, c2 (stored as three
   16-byte arrays). Which component is red, green, blue and how a palette reaches the hardware:
   [graphics.md](graphics.md). VA: 44 palettes; statements use #2..#44 (§6, op 30h: #1 cannot be
   addressed).
5. **Statements** (tag 04h; `063C:011E`): per statement an opcode byte and its operands
   (§6). The opcode selects a loader from the table at 0B77:0000 (rows: opcode word, far loader
   pointer; `063C:01E0`); an opcode not in the table, or a loader returning NULL (invalid
   operands), makes `scb_load` call `exit(2)`.

After the last statement the file ends (no trailer). **Verified.**

## 3. Loader checks (exit code 2 when violated)

| Operand | Check |
|---|---|
| message number (19h) | 0 ≤ n ≤ message count |
| expression number (1Eh, 1Fh, 20h, 23h) | 0 ≤ n ≤ node count |
| menu number (24h) | 1 ≤ n ≤ menu count |
| variable number (1Eh) | ≥ 1 |
| 1Fh targets | both ≥ 0; if the first is 0 the second must be 0 too |
| 20h | case count 1..15, default ≥ 0 |
| opcodes 26h–2Ah, 2Ch | always invalid (loader returns NULL); an opcode not in the table (anything below 15h, above 37h, or ≥ 80h, which `scb_getc` sign-extends) too |
| 1Eh expression, 20h expression, 20h default | also ≥ 0 (a negative one is NULL) |
| 1Fh, 20h, 23h expression 0 | accepted: `expr_eval(0)` ends the program with exit(4) at run time |

Every failure ends with exit code 2: a check's own `exit(2)`, a loader's NULL (`scb_load_stmts`
calls `exit(2)`), or `scb_load` returning 0 (`main`). Only a failed `malloc` of a statement record
(`stmt_alloc` `063C:0012`) exits with 3; the tables' own allocations failing return 0 (exit 2).

What is not checked:
* jump targets (1Fh, 20h, 21h, 22h, 34h) against the statement count; the VM does not check
  them either: an out-of-range pc reads past the pointer table (pc 0: entry 0 is NULL, which
  reads the opcode from 0000:0000);
* variable numbers (1Eh, and the leaves of expressions) against the variable count; the
  number 0 is the unused slot (§2.4), a real record;
* message 0 (19h): the message index's entry 0 is NULL; palettes (30h) above the count, whose
  pointer is read at load time past the palette table;
* the strings' lengths: a picture name (31h) has 13 bytes before it overwrites the record's
  other fields (flag, buffer, x, y, written before it), a song name (1Bh) 19, a menu's strings
  the menu's `size` word, the text file's name the 20 bytes up to the scenario's name;
* the counts: each table is allocated with a 16-bit size, (n + 1) × entry size, which wraps for
  large counts; a negative count reads no entries, but the checks then compare against it.

The end of the file reads as fgetc's −1: the plain readers return it (a tag of −1 fails the
sections), `scb_getc` adds it to the key like a byte FFh would be added and returns the low byte
sign-extended, so a file cut short reads on as if FFh bytes followed and fails or loads as such
bytes decide. A string cut short never ends (the low byte alternates between two values) and
the loader reads for ever. **Verified** (`check_scb.py`: files cut short at 25 points, among
others).

## 4. Expressions (`expr_eval` 0000:0089)

`eval(n)`: n must be 1..count (else `exit(4)`).

* **Leaf** (`expr_leaf` 0000:0000), `kind` bits: 1 = literal, 2 = variable, 4 = integer,
  8 = boolean, tested in this order:
  * bit 1 and bit 4 (5, 7, ...): `value`; bit 1 and bit 8 (9, ...): `value != 0`;
  * bit 2 and bit 4 (6, ...): `var[value].value`; bit 2 and bit 8 (10, ...):
    `var[value].value != 0` (a kind of 3 = literal and variable without a type: the variable
    paths decide);
  * anything else: `exit(4)`.
  The leaf's kind decides how a variable is read, not the variable's own type. The variable's
  number is not checked (0 is the unused slot).
* **Operator node**, `op`:
  * 3: `-eval(left)`; 4: `~eval(left)` (bitwise; `right` unused);
  * 5..16: both operands evaluated, left first (no short-circuit), 16-bit signed:
    5 `+`, 6 `-`, 7 `*` (low word of `imul`), 8 `/` (`idiv`, truncating), 9 `%` (`idiv`
    remainder, sign of the dividend), 10 `&`, 11 `|`, 12 `^`, 13 `==`, 14 `!=`, 15 `>`,
    16 `<` (comparisons give 1 or 0; there are no `>=`/`<=`/logical operators);
  * other: `exit(4)`, after both operands were evaluated. A zero divisor, and −32768 / −1
    (whose quotient does not fit), raise the CPU's divide exception for 8 and 9 alike; the C
    runtime prints `run-time error R6003` / `- integer divide by 0` and exits with code 255.

VA uses ops 5, 7, 11, 13, 14, 16 and leaves of kinds 5, 6, 9, 10. **Verified**
(`source/tests/check_expr.py`: 800 random trees over random variables, every operator and
leaf kind, the edges of 16 bits, the exits).

## 5. The virtual machine

### 5.1 State

| State | Where | Notes |
|---|---|---|
| `pc` | DS:005A | number of the next statement, 1-based |
| call stack | 0A9F:0000, 32 words; depth DS:005C | return statement numbers |
| variables | records (`type` word, `value` word) via 0BA1:0068 | v1 is also the result register |
| result flag | byte 0BA1:0000 | set by message display, waits and built-ins (see each op) |
| pictures, palette, text window, music | subsystems | [graphics.md](graphics.md), [text.md](text.md), [sound.md](sound.md) |

### 5.2 Loop

`vm_run(entry)` sets `pc = entry` and calls `vm_step` until it returns ≠ 1. `vm_step`
(`001E:0133`): `s = statement[pc]; pc += 1;` dispatch on `s.opcode − 15h` through the table at
001E:016E (35 entries, 15h..37h); opcodes 26h–2Ah and 2Ch dispatch to `exit(4)`. Every handler
returns 1 except opcode 2Eh, which returns 0 and so ends `vm_run`. Because `pc` is incremented
before the handler runs, every jump simply stores its target, and a relative jump counts from
the following statement. There is no instruction budget or yield: waiting happens inside the
handlers (input, timers, effects).

### 5.3 Results in v1

Several statements write v1 with a type: "v1 := bool b" stores type 0Ah and value b (0/1);
"v1 := int n" stores type 6 and n. The type written matters for a later `var = expr`
assignment to v1 (bool variables store `value != 0`) and for the save file.

## 6. Statements

Operands are listed in file order; `b` = byte (signed unless noted), `w` = word, `s` = C string.
Counts are the number of statements in VA.

| Op | Count | Operands | Semantics (handler) |
|---|---|---|---|
| 15h | 29 | `w` time, `b` skippable (≠0) | **wait** `time` hundredths of a second (VSYNC-counted: `frames = time × 564 / 1000`, [platform.md](platform.md) §2). If skippable, a new key press or a held mouse button ends it early, followed by the input "release" step of [platform.md](platform.md) §3. The result flag is cleared first; v1 := bool interrupted. If both operands are 0 nothing happens and v1 is unchanged; with no free timer slot the flag is cleared and nothing else happens (v1 unchanged). (`001E:081C`) |
| 16h | 1 | — | **wait for input**: polls until a new key press or a held mouse button, then the "release" step (`001E:08FB`). v1 unchanged. |
| 17h | 0 | — | no operation (`001E:095E`) |
| 18h | 0 | — | erases the text window (restores it from the saved background; `0315:07F5`, [text.md](text.md)) |
| 19h | 267 | `w` message | **show message** n ([text.md](text.md): window, paging, keys). Clears the result flag first; v1 := bool result flag afterwards (set when a key or click interrupts a timed page, which aborts the rest of the message; text.md) (`001E:0965`). Message 0 passes the index's NULL entry |
| 1Ah | 86 | `b` to-white (≠0), `w` time | **fade out** the current palette to black (or white) over `time` hundredths of a second; time < 1: at once ([graphics.md](graphics.md), `0315:04E2`) |
| 1Bh | 21 | `w` volume % (always 100), `s` file | **play song**: the engine picks `.n`/`.s`/`.m` by driver (the script's extension is ignored), copies the file into PMD's buffer and starts it; the volume only sets where a later fade starts ([sound.md](sound.md), `04E4:0034`) |
| 1Ch | 3 | `w` time (1, 200, 320) | **fade out and stop** over `time` hundredths of a second, linearly, one volume step per VSYNC; **blocking** (the game waits) ([sound.md](sound.md), `04E4:01D8`, `04E4:00F0`) |
| 1Dh | 1 | — | **save** to slot v1 (1..3; other values: nothing) (`001E:0378`, §7) |
| 1Eh | 187 | `w` expr, `b` var | **assign**: `x = eval(expr)`; if the variable's type has bit 8 (bool) it stores `x != 0`, else `x` (`001E:06B2`) |
| 1Fh | 49 | `w` expr, `w` then, `w` else | **if**: `pc = eval(expr) ? then : else` (`001E:06FC`) |
| 20h | 44 | `b` (ignored), `w` expr, `b` n (1..15), `w` default, n × (`w` value, `w` target) | **switch**: first case whose value equals `eval(expr)` → `pc = target`; none → `pc = default` (`001E:0725`) |
| 21h | 16 | `w` target | **goto** (`001E:07FF`) |
| 22h | 107 | `w` target | **call**: push pc (the next statement) on the call stack, `pc = target`. Depth 31 before the push → `Calling nested too much`, `exit(4)` (so at most 31 nested calls) (`001E:078A`, `001E:0004`) |
| 23h | 25 | `w` expr (0 = none) | **return**: with expr > 0, v1 := int eval(expr); else v1 := bool 1. Then `pc = pop()`; empty stack → `No Calling stack (Invalid RETURN)`, `exit(4)` (v1 is written first) (`001E:07A1`, `001E:0039`) |
| 24h | 58 | `w` menu | **menu**: show the choices, v1 := int the chosen number (1 when the loop's choice is outside 1..n) ([text.md](text.md); `001E:0A8D`) |
| 25h | 5 | `b` n | **built-in sequence** n from the table 0AB1:0000 (§8). Clears the result flag, calls the routine (none for n = 6, the zero row after the table; other numbers read past it), v1 := bool result flag (`001E:0310`) |
| 26h–2Ah, 2Ch | 0 | — | invalid (load error; would be `exit(4)` at run time) |
| 2Bh | 93 | — | no operation (the compiler's join point after `if`/`switch`) |
| 2Dh | 1 | — | no operation; marks the entry statement (§1) |
| 2Eh | 2 | — | **end**: stops the machine; `run_game` shuts down and the program exits to DOS (`001E:0299`) |
| 2Fh | 2 | `w` time | **white flash**: fade to white over time/2, back to the saved palette over time/2 ([graphics.md](graphics.md), `0315:06C2`) |
| 30h | 81 | `w` time, `b` palette (unsigned, 1-based) | **set palette**: with time > 0 fade in from black (from white if the screen is all white) over time/100 s, then set it; palette numbers ≤ 1 are passed as NULL ([graphics.md](graphics.md), `0315:0176`) |
| 31h | 266 | `b` buffer, `w` x, `w` y, `b` flag, `s` name | **load picture** `name` (without `.gf`) from the library into buffer at (x, y) — flag 1 = colour 8 transparent; buffers 10 = screen (page 0), 11 = page 1 (never shown), 12 = memory copy ([graphics.md](graphics.md), `0315:070D`) |
| 32h | 235 | `b` src, `w` x, `w` y, `w` w, `w` h, `b` dst, `w` x2, `w` y2, `b` effect | **copy rectangle** between buffers with a transition effect — effects 10 copy, 20 transparent, 30 じわ出し dissolve, 31 ordered dissolve, 32 top/bottom, 33 interlaced, 34 line slide ([graphics.md](graphics.md), `0315:07CB`) |
| 33h | 56 | `b` buffer | **clear** buffer 10/11/12 (anything else: 10) ([graphics.md](graphics.md), `0315:01BE`) |
| 34h | 380 | `b` d (signed) | **relative jump**: `pc += d` (from the next statement; d = 0 is a no-op) (`001E:080D`) |
| 35h | 2 | — | **music position**: v1 := int (PMD's measure count + 1), or −1 when no song plays / no driver ([sound.md](sound.md), `04E4:01E9`). The scenario polls it in a loop of statements (1757–1762 until 3, 1889–1893 until 5): the loop waits for nothing but the music, which the VSYNC drives |
| 36h | 1 | — | **load** from slot v1 (1..3) (`001E:039B`, §7) |
| 37h | 16 | `b` flag (==1) | mouse pointer: flag 0 → hide and keep hidden; 1 → allow showing again ([platform.md](platform.md) §3; `043A:02B5`) |

Ops 1Ah, 18h, 2Fh, 30h–33h, 1Bh/1Ch/35h and 24h are specified in detail in the subsystem documents; their
operand encodings above are **verified** from the loaders. The handlers are **verified** by
`source/tests/check_vmstep.py`: the original's `vm_step` with the subsystems stood in for, on 44
routes through the scenario (250 000 statements, 1 898 of the 1 947 reachable ones: the others are
43 defaults of a menu's switch, which a menu's result never takes, and six defaults and joins
of switches on values the scenario never produces: 677, 1042, 1235, 1444, 1722, 1730), compared
statement by statement with the engine; on four routes also the 80286 clocks of each
statement (`re-tools/vm_cost.py`).

## 7. Saves (`GAME.DAT`)

Three slots of 132 bytes, slot *k* (1..3) at offset `(k−1) × 132`. Record size
`= (variables + 24) × 3 = 132`. All words are **big-endian** (`fput_be16` 001E:03D1).

| Offset | Size | Content |
|---|---|---|
| 0 | 2 | `S` `D` |
| 2 | 2 | 132 (record size) |
| 4 | 2 | pc (the statement after the save statement) |
| 6 | 2 | call-stack depth |
| 8 | 64 | the 32 call-stack words (all, used or not) |
| 72 | 60 | 20 × (`type` byte, `value` word) |

**Save** (`save_slot` 001E:042C): `fopen("game.dat", "r+b")`, or `"wb"` if that fails (a new
file); `fseek` to the slot (the offset is the low word of size × slot, sign-extended: `imul`,
then `cwd`); write; `fclose`. A slot past the end of a shorter file extends it (DOS leaves the
gap's clusters as they were). **Load** (`load_slot` 001E:0577):
`fopen("game.dat", "rb")` (missing file: nothing happens); `fseek`; the record must start with
`S`, `D` and size 132, else nothing is loaded; then pc, depth, the 32 stack words and the 20
variable records are read back, with nothing checked: past the end of the file every `fgetc`
is −1, so a type reads FFFFh and a word `(−1 << 8) + −1` = FEFFh (or the byte that is there
plus FF00h). A depth or pc read so is used as it is. A failed load leaves the machine as it was, so execution simply
continues with the statement after the load statement (VA's load menu shows message 205
`不正なセーブデータです` there). A successful load therefore resumes right after the save
statement that wrote the record, inside the same subroutine nest.

**Off-by-one (original behaviour):** the variable loop runs over pointer-table entries 0..19,
and entry 0 is the unused slot (§2.4). The record holds that slot's (uninitialised, normally
zero) contents followed by v1..v19; **v20 is never saved or loaded**, and loading writes the
first record into the unused slot. In VA v20 is the "requested song" variable (script-catalog.md
§music), so it keeps its value across a load. The PC-98 `GAME.DAT` on the disk holds three
slots (pc 06CEh, depth 2, the first record type/value 0). **Verified** (code read; the
`GAME.DAT` on the disk parses accordingly; `source/tests/check_save.py` compares the engine's
file and loads with the original's `save_slot` and `load_slot`, damaged and short files
included).

## 8. Built-in sequences (op 25h)

Table 0AB1:0000, 8-byte rows (DGROUP name pointer, far routine pointer):

| n | Name | Routine | Used by VA | What it does |
|---|---|---|---|---|
| 0 | `INIT` | 0504:0004 | (called by `main`) | mouse Y/N prompt on the console ([platform.md](platform.md) §3) |
| 1 | `OPENING` | 0504:0295 | statement 1771 | the prologue text pages ([platform.md](platform.md) §5) |
| 2 | `ENDING` | 0504:0568 | 1939 | staff roll, ending 1 |
| 3 | `ANNOUNCE` | 0504:0114 | 2007 | shows `announce.txt` |
| 4 | `MUSMODE` | 0504:088E | 2001 | music mode |
| 5 | `ENDING2` | 0504:05CA | 1920 | staff roll, ending 2 |

The result flag (→ v1) reports whether the player skipped the sequence.

## 9. Compiler idioms (useful when reading the listing)

* `if c then A else B` compiles to `1Fh c, T, E` where T starts the then-branch; the then-branch
  ends with `34h +k` over the else-branch; both branches end at a `2Bh` join. An `if` without
  `else` has `E` pointing at a `34h 0` before the join.
* `switch` compiles to `20h` with one target per case; each case body ends with `34h` to the
  join `2Bh`; the compiler also emits an unreachable `34h` after each case's own jump (a
  `break` after a `goto`-like body): 87 statements of VA are unreachable, nearly all of them
  these (`re-tools/scbdis.py --graph`).
* Subroutines end with `23h 0`; many are called once (chapters, script-catalog.md).

`re-tools/scbdis.py SCB [--out FILE]` prints the program in this notation (1-based numbers as
the VM's pc, expressions in infix, menus inline); `--graph` lists reachability and subroutines.
