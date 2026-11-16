/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Clocks of M.EXE's op 32 on an 80286 without wait states, made by
 * re-tools/fx_cost.py consts (the clock table: re-tools/m286.py). Do not edit. */
#ifndef VG_GFX_FX_CLK_H
#define VG_GFX_FX_CLK_H

/* branches and string instructions */
#define J_TAKEN            7     /* jcc, jmp short */
#define J_NOT              3
#define LOOP_TAKEN         8
#define LOOP_NOT           4
#define REP_MOVS           5     /* rep movsw of n words: REP_MOVS + n * REP_MOVS_EACH */
#define REP_MOVS_EACH      4

/* rect_copy's start to 00DD:059D, by source and destination kind: 10, 11, 12, other */
#define FX_HEAD { \
    { 196, 208, 196, 190 }, \
    { 208, 220, 208, 202 }, \
    { 192, 204, 192, 186 }, \
    { 189, 201, 189, 183 } \
}
/* 00DD:059D to the routine; the routine's retf to op 32's return (with win_snapshot) */
#define FX_SWITCH_OTHER    118  /* a code below 20 or above 34 */
#define FX_SWITCH_TABLE    130  /* 20..34 through the table, except 31 */
#define FX_SWITCH_31       152
#define FX_TAIL            49984
#define FX_TAIL_31         49984
#define FX_TAIL_34         49977

/* the routines (segment 0783; fx31_wait 00DD:04F9) */
#define FX10_SETUP         147
#define FX10_PLANE_PRE     18
#define FX10_PLANE_POST    10
#define FX10_LINE_POST     8
#define FX10_EXIT          39
#define FX20_SETUP         149
#define FX20_LINE_PRE      11
#define FX20_BYTE_PRE      49
#define FX20_PIXEL         23
#define FX20_PIXEL_OR      3
#define FX20_MASK          12
#define FX20_MASKED_PRE    10
#define FX20_MASKED_AND    12
#define FX20_MASKED_OR     7
#define FX20_MASKED_END    7
#define FX20_OPAQUE        8
#define FX20_BYTE_POST     9
#define FX20_JMP           7
#define FX20_LINE_POST     18
#define FX20_EXIT          39
#define FX30_SETUP         214
#define FX30_PASS_PRE      21
#define FX30_LINE_PRE      22
#define FX30_TMP_PLANE     15
#define FX30_TMP_END       22
#define FX30_PLANE_PRE     9
#define FX30_WORD          19
#define FX30_PLANE_POST    5
#define FX30_LINE_POST     30
#define FX30_JMP           7
#define FX30_PASS_POST     22
#define FX30_EXIT          39
#define FX31_SETUP         153
#define FX31_STEP_PRE      57
#define FX31_LINE_PRE      18
#define FX31_PLANE0_PRE    34
#define FX31_WORD          19
#define FX31_PLANE_NEXT    39
#define FX31_PLANE3_POST   15
#define FX31_LINE_POST     21
#define FX31_JMP           7
#define FX31_CALL          49
#define FX31_WAIT_PRE      4
#define FX31_WAIT_READ     10
#define FX31_WAIT_TEST     11
#define FX31_WAIT_LAST     5
#define FX31_WAIT_END      18
#define FX31_STEP_POST     44
#define FX31_EXIT          39
#define FX32_SETUP         226
#define FX32_SETUP2        5
#define FX32_ITER_PRE      38
#define FX32_BYTE          17
#define FX32_PLANE_NEXT    31
#define FX32_BOTTOM_PRE    41
#define FX32_ITER_POST     43
#define FX32_JMP           7
#define FX32_EXIT          39
#define FX33_SETUP         222
#define FX33_ODD_PRE       35
#define FX33_PLANE_NEXT    28
#define FX33_ODD_POST      28
#define FX33_PAIRS         7
#define FX33_TOP_PRE       28
#define FX33_BOTTOM_PRE    38
#define FX33_PAIR_POST     40
#define FX33_JMP           7
#define FX33_EXIT          39
#define FX34_SETUP         179
#define FX34_STEP_PRE      9
#define FX34_EVEN_PRE      31
#define FX34_PLANE_NEXT    27
#define FX34_ODD_PRE       54
#define FX34_PAIR_POST     31
#define FX34_JMP           7
#define FX34_STEP_POST     11
#define FX34_EXIT          34

#endif
