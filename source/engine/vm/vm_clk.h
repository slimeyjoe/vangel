/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Made by re-tools/vm_cost.py consts: what the original's interpreter spends, in 80286
 * clocks (re-tools/m286.py), on an expression node (its expr_eval from entry to return)
 * and on a statement by the path it takes (vm_step from entry to return, less the
 * subsystems it calls and expr_eval). _PER: a switch's turn per case compared. */
#ifndef VG_VM_VM_CLK_H
#define VG_VM_VM_CLK_H

#define VG_CLK_LEAF_LIT_INT    229
#define VG_CLK_LEAF_LIT_BOOL   247
#define VG_CLK_LEAF_VAR_INT    278
#define VG_CLK_LEAF_VAR_BOOL   303
#define VG_CLK_EXPR_NEG        213
#define VG_CLK_EXPR_NOT        236
#define VG_CLK_EXPR_ADD        280
#define VG_CLK_EXPR_SUB        280
#define VG_CLK_EXPR_MUL        299
#define VG_CLK_EXPR_DIV        312
#define VG_CLK_EXPR_MOD        305
#define VG_CLK_EXPR_AND        280
#define VG_CLK_EXPR_OR         280
#define VG_CLK_EXPR_XOR        280
#define VG_CLK_EXPR_EQ_T       280
#define VG_CLK_EXPR_EQ_F       283
#define VG_CLK_EXPR_NE_T       283
#define VG_CLK_EXPR_NE_F       287
#define VG_CLK_EXPR_GT_T       283
#define VG_CLK_EXPR_GT_F       287
#define VG_CLK_EXPR_LT_T       276
#define VG_CLK_EXPR_LT_F       287

#define VG_CLK_15_ZERO         250
#define VG_CLK_15_NOTIMER      309
#define VG_CLK_15_DONE         420
#define VG_CLK_15_CUT          521
#define VG_CLK_16              277
#define VG_CLK_17              183
#define VG_CLK_18              196
#define VG_CLK_19_0            337
#define VG_CLK_19_1            340
#define VG_CLK_1A              233
#define VG_CLK_1B              224
#define VG_CLK_1C_IDLE         216
#define VG_CLK_1C_PLAY         242
#define VG_CLK_1D_OUT          217
#define VG_CLK_1D_SAVE         239
#define VG_CLK_1E_INT          305
#define VG_CLK_1E_BOOL         315
#define VG_CLK_1F_T            248
#define VG_CLK_1F_F            245
#define VG_CLK_20_CASE         338
#define VG_CLK_20_DEF          302
#define VG_CLK_20_PER          48
#define VG_CLK_21              208
#define VG_CLK_22              293
#define VG_CLK_23_EXPR         358
#define VG_CLK_23_NONE         321
#define VG_CLK_24_NEW          445
#define VG_CLK_24_SAME         445
#define VG_CLK_25_0            327
#define VG_CLK_25_1            330
#define VG_CLK_25_NULL         315
#define VG_CLK_2B              129
#define VG_CLK_2E              136
#define VG_CLK_2F              223
#define VG_CLK_30              228
#define VG_CLK_31              226
#define VG_CLK_32              226
#define VG_CLK_33              223
#define VG_CLK_34              212
#define VG_CLK_35              231
#define VG_CLK_36_OUT          217
#define VG_CLK_36_LOAD         239
#define VG_CLK_37_0            238
#define VG_CLK_37_1            235

/* expr_leaf's paths by the kind's bits */
static inline unsigned vg_clk_leaf(int k)
{
    if ((k & 1) && (k & 4)) return VG_CLK_LEAF_LIT_INT;
    if ((k & 1) && (k & 8)) return VG_CLK_LEAF_LIT_BOOL;
    if ((k & 2) && (k & 4)) return VG_CLK_LEAF_VAR_INT;
    return VG_CLK_LEAF_VAR_BOOL;
}

#endif
