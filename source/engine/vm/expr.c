/* SPDX-License-Identifier: GPL-3.0-or-later */
/* expr_eval (0000:0089) and expr_leaf (0000:0000): docs/re/scenario-format.md §4.
 *
 * 16-bit signed arithmetic; both operands of a binary operator are evaluated, the left one
 * first; a node number outside the table, an unknown operator or leaf kind end the program
 * with exit(4). Division (8) and remainder (9) are idiv: a zero divisor, or -32768 / -1 which
 * does not fit, raise the CPU's divide error, and the C library ends the program with R6003. */
#include "vg.h"
#include "vm/vm_clk.h"

/* expr_leaf: the kind's bits tested in this order */
static int16_t leaf(const struct vg_expr *e)
{
    int k = e->k;
    if (k & 1) {
        if (k & 4)
            return e->a;
        if (k & 8)
            return e->a != 0;
    }
    if (k & 2) {
        if (k & 4)
            return vg_vm_var(e->a)->value;
        if (k & 8)
            return vg_vm_var(e->a)->value != 0;
    }
    vg_vm_error(NULL);
}

int16_t vg_expr_eval(int n)
{
    const struct vg_scb *s = &vg.vm.scb;
    const struct vg_expr *e;
    int16_t l, r;

    if (n < 1 || n > s->n_expr)
        vg_vm_error(NULL);
    e = &s->expr[n];
    if (e->form == 1) {
        vg_vm_charge(vg_clk_leaf(e->k));
        return leaf(e);
    }
    if (e->k == 3 || e->k == 4) {
        l = vg_expr_eval(e->a);
        vg_vm_charge(e->k == 3 ? VG_CLK_EXPR_NEG : VG_CLK_EXPR_NOT);
        return e->k == 3 ? (int16_t)-l : (int16_t)~l;
    }
    l = vg_expr_eval(e->a);
    r = vg_expr_eval(e->b);
    switch (e->k) {
    case 5:  vg_vm_charge(VG_CLK_EXPR_ADD); return (int16_t)(l + r);
    case 6:  vg_vm_charge(VG_CLK_EXPR_SUB); return (int16_t)(l - r);
    case 7:  vg_vm_charge(VG_CLK_EXPR_MUL); return (int16_t)((int32_t)l * r);
    case 8:
    case 9:
        if (r == 0 || (l == -32768 && r == -1))
            vg_runtime_error(VG_R6003);
        vg_vm_charge(e->k == 8 ? VG_CLK_EXPR_DIV : VG_CLK_EXPR_MOD);
        return e->k == 8 ? (int16_t)(l / r) : (int16_t)(l % r);
    case 10: vg_vm_charge(VG_CLK_EXPR_AND); return (int16_t)(l & r);
    case 11: vg_vm_charge(VG_CLK_EXPR_OR); return (int16_t)(l | r);
    case 12: vg_vm_charge(VG_CLK_EXPR_XOR); return (int16_t)(l ^ r);
    case 13: vg_vm_charge(l == r ? VG_CLK_EXPR_EQ_T : VG_CLK_EXPR_EQ_F); return l == r;
    case 14: vg_vm_charge(l != r ? VG_CLK_EXPR_NE_T : VG_CLK_EXPR_NE_F); return l != r;
    case 15: vg_vm_charge(l > r ? VG_CLK_EXPR_GT_T : VG_CLK_EXPR_GT_F); return l > r;
    case 16: vg_vm_charge(l < r ? VG_CLK_EXPR_LT_T : VG_CLK_EXPR_LT_F); return l < r;
    default: vg_vm_error(NULL);
    }
}
