/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The virtual machine: vm_run (001E:011F), vm_step (001E:0133) and the statements' handlers
 * (segment 001E), docs/re/scenario-format.md §5-6.
 *
 * Operands, in the pool from stmt->at (scb.c reads them in the file's order):
 *   15h time, skippable     19h message           1Ah to white, time    1Bh volume (+ str)
 *   1Ch time                1Eh expr, variable    1Fh expr, then, else  20h expr, default,
 *   n x (value, target)     21h, 22h target       23h expr (0: none)    24h menu
 *   25h n                   2Fh time              30h time, palette (0: none)
 *   31h buffer, x, y, flag (+ str)                32h src, sx, sy, w, h, dst, dx, dy, effect
 *   33h buffer              34h displacement      37h flag (1 / 0)
 *
 * Time: a statement charges the clocks the original's interpreter spends on it on the
 * reference machine (vm/vm_clk.h, re-tools/vm_cost.py): the fetch, the dispatch, the
 * handler's own instructions on the path it took, and expr_eval's nodes as they are evaluated;
 * not the subsystems it calls (the transitions charge their own), nor the turns of a wait
 * loop (those pass as frames). So a loop of statements that waits for nothing, the busy poll
 * of statement 35h, lets frames pass as it would on the machine. */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "vm/vm_clk.h"

/* ---- the engine's subsystems -------------------------------------------------------- */

/* a poll that counts as input for 15h and 16h (001E:088A): the device to release, or 0 */
static int poll_input(const struct vg_poll *p)
{
    if (p->kbd.event == 1)
        return VG_DEV_KBD;
    if (p->mouse.left == 1 || p->mouse.right == 1 || p->mouse.zero == 1)
        return VG_DEV_MOUSE;
    if (p->joy.b != 0)
        return VG_DEV_JOY;
    return 0;
}

/* op_15 (001E:081C): the timer slot, and with `skippable` the input, until one ends it */
static int io_wait(int t, int skippable)
{
    struct vg_poll p;
    int h = vg_timer_start(t), dev;
    if (!h)
        return -1;
    vg_wait_begin(VG_WAIT_TICKS);
    for (;;) {
        if (vg_timer_done(h))
            break;
        if (skippable) {
            memset(&p, 0, sizeof p);
            if (!vg_input_poll(&p))
                break;
            if ((dev = poll_input(&p)) != 0) {
                vg_input_release((unsigned)dev);
                vg.text.skip = 1;
                break;
            }
        }
        if (vg_frame())
            break;
    }
    vg_wait_end(VG_WAIT_TICKS);
    vg_timer_free(h);
    return 0;
}

/* op_16 (001E:08FB) */
static void io_wait_input(void)
{
    struct vg_poll p;
    int dev;
    vg_wait_begin(VG_WAIT_KEY);
    for (;;) {
        memset(&p, 0, sizeof p);
        if (!vg_input_poll(&p))
            break;
        if ((dev = poll_input(&p)) != 0) {
            vg_input_release((unsigned)dev);
            break;
        }
        if (vg_frame())
            break;
    }
    vg_wait_end(VG_WAIT_KEY);
}

static void io_msg(int n)
{
    vg_msg_show(n);
}

static void io_music_play(int volume, const char *name)
{
    vg_mus_play(name, volume);
}

static void io_music_fade(int t)
{
    vg_mus_fade_stop(t);
}

static int io_menu(long stmt, const struct vg_menu *m)
{
    return vg_op24(stmt, m);
}

/* the built-in sequences come with M5 */
static void io_builtin(int n)
{
    static const char *const names[VG_BUILTINS] = {
        "INIT", "OPENING", "ENDING", "ANNOUNCE", "MUSMODE", "ENDING2"
    };
    lrv_log(vg.hal, LRV_LOG_WARN, "built-in sequence %s: not yet (M5)", names[n]);
}

static void io_palette(const uint8_t *pal, int t)
{
    /* numbers <= 1 pass NULL, and the original reads 48 bytes at 0000:0000 (the interrupt
     * vectors); here: black */
    static const uint8_t black[VG_PAL_BYTES];
    vg_pal_op30(pal ? pal : black, t);
}

static void io_pic_load(int buf, int x, int y, int flag, const char *name)
{
    vg_pic_load(buf, x, y, flag, name);
}

static void io_rect_copy(const struct vg_rect_op *op)
{
    vg_rect_copy(op);
}

const struct vg_vm_io vg_vm_engine_io = {
    io_wait, io_wait_input, vg_win_restore, io_msg, vg_pal_fade_out, io_music_play,
    vg_mus_state, io_music_fade, io_menu, io_builtin, vg_pal_flash, io_palette,
    io_pic_load, io_rect_copy, vg_buf_clear, vg_mus_measure, vg_mouse_lock
};

/* ---- state ------------------------------------------------------------------------------ */

void vg_vm_charge(uint32_t n)
{
    vg.vm.clk += n;
    if (n)
        vg_cpu(n);
}

LRV_NORETURN void vg_vm_fault(const char *what, long n)
{
    lrv_log(vg.hal, LRV_LOG_ERROR, "the scenario reads outside its tables: %s %ld (pc %u)",
            what, n, (unsigned)vg.vm.pc);
    vg_exit(VG_EXIT_RUN);
}

LRV_NORETURN void vg_vm_error(const char *msg)
{
    if (msg)
        lrv_log(vg.hal, LRV_LOG_ERROR, "%s", msg);
    else
        lrv_log(vg.hal, LRV_LOG_ERROR, "the scenario is invalid at pc %u", (unsigned)vg.vm.pc);
    vg_exit(VG_EXIT_RUN);
}

struct vg_var *vg_vm_var(int n)
{
    if (n < 0 || n > vg.vm.scb.n_var)
        vg_vm_fault("variable", n);
    return &vg.vm.var[n];
}

void vg_vm_v1_bool(int b)
{
    struct vg_var *v = vg_vm_var(1);
    v->type = VG_T_BOOL;
    v->value = (int16_t)(b != 0);
}

void vg_vm_v1_int(int16_t n)
{
    struct vg_var *v = vg_vm_var(1);
    v->type = VG_T_INT;
    v->value = n;
}

int vg_vm_init(uint16_t entry)
{
    struct vg_vm *m = &vg.vm;
    size_t n = (size_t)(m->scb.n_var + 1) * sizeof *m->var;
    vg_vm_free();
    if (!(m->var = lrv_alloc(vg.hal, n)))
        return 0;
    memcpy(m->var, m->scb.var, n);
    m->var[0].type = 0;                 /* malloc's slot, never initialised: zero here */
    m->var[0].value = 0;
    m->pc = entry;
    m->depth = 0;
    memset(m->stack, 0, sizeof m->stack);
    if (!m->io)
        m->io = &vg_vm_engine_io;
    return 1;
}

void vg_vm_free(void)
{
    struct vg_vm *m = &vg.vm;
    if (m->var)
        lrv_free(vg.hal, m->var, (size_t)(m->scb.n_var + 1) * sizeof *m->var);
    m->var = NULL;
}

uint16_t vg_vm_entry(void)
{
    const struct vg_scb *s = &vg.vm.scb;
    if (s->entry >= 1 && s->entry <= (uint16_t)s->n_stmt && s->stmt[s->entry].op == 0x2D)
        return s->entry;
    return 1;
}

/* ---- the statements --------------------------------------------------------------------- */

static void call_push(uint16_t ret)     /* 001E:0004 */
{
    struct vg_vm *m = &vg.vm;
    if (m->depth == VG_CALL_MAX)
        vg_vm_error("Calling nested too much");
    if (m->depth < 0 || m->depth > VG_CALL_MAX)
        vg_vm_fault("call stack depth", m->depth);
    m->stack[m->depth++] = ret;
}

static uint16_t call_pop(void)          /* 001E:0039 */
{
    struct vg_vm *m = &vg.vm;
    if (m->depth == 0)
        vg_vm_error("No Calling stack (Invalid RETURN)");
    if (m->depth < 0 || m->depth > VG_CALL_STACK)
        vg_vm_fault("call stack depth", m->depth);
    return m->stack[--m->depth];
}

int vg_vm_step(void)
{
    struct vg_vm *m = &vg.vm;
    const struct vg_scb *s = &m->scb;
    const struct vg_vm_io *io = m->io;
    const struct vg_stmt *st;
    const int16_t *a;
    unsigned at = m->pc, clk = 0;
    int r, i;

    if (m->pc < 1 || m->pc > (uint16_t)s->n_stmt)
        vg_vm_fault("statement", m->pc);
    st = &s->stmt[m->pc];
    a = s->w + st->at;
    m->pc++;
    switch (st->op) {
    case 0x15:                          /* wait */
        if (a[0] == 0 && a[1] == 0) {
            clk = VG_CLK_15_ZERO;
            break;
        }
        vg.text.skip = 0;
        if (io->wait(a[0], a[1]) < 0) {
            clk = VG_CLK_15_NOTIMER;
            break;
        }
        clk = vg.text.skip == 1 ? VG_CLK_15_CUT : VG_CLK_15_DONE;
        vg_vm_v1_bool(vg.text.skip == 1);
        break;
    case 0x16:
        io->wait_input();
        clk = VG_CLK_16;
        break;
    case 0x17:
        clk = VG_CLK_17;
        break;
    case 0x18:
        io->win_restore();
        clk = VG_CLK_18;
        break;
    case 0x19:                          /* message */
        if (a[0] == 0)                  /* the index's entry 0 is NULL */
            vg_vm_fault("message", 0);
        vg.text.skip = 0;
        io->msg(a[0]);
        clk = vg.text.skip == 1 ? VG_CLK_19_1 : VG_CLK_19_0;
        vg_vm_v1_bool(vg.text.skip == 1);
        break;
    case 0x1A:
        io->fade_out(a[0], a[1]);
        clk = VG_CLK_1A;
        break;
    case 0x1B:
        io->music_play(a[0], s->str + st->str);
        clk = VG_CLK_1B;
        break;
    case 0x1C:                          /* 0000:0C32 */
        if (io->music_state() == 10) {
            io->music_fade(a[0]);
            clk = VG_CLK_1C_PLAY;
        } else {
            clk = VG_CLK_1C_IDLE;
        }
        break;
    case 0x1D:
    case 0x36:
        r = vg_vm_var(1)->value;
        if (r >= 1 && r <= 3) {
            if (st->op == 0x1D)
                vg_save_slot(r - 1);
            else
                vg_load_slot(r - 1);
            clk = st->op == 0x1D ? VG_CLK_1D_SAVE : VG_CLK_36_LOAD;
        } else {
            clk = st->op == 0x1D ? VG_CLK_1D_OUT : VG_CLK_36_OUT;
        }
        break;
    case 0x1E: {                        /* assign */
        int16_t x = vg_expr_eval(a[0]);
        struct vg_var *v = vg_vm_var(a[1]);
        if (v->type & 8) {
            v->value = x != 0;
            clk = VG_CLK_1E_BOOL;
        } else {
            v->value = x;
            clk = VG_CLK_1E_INT;
        }
        break;
    }
    case 0x1F:                          /* if */
        if (vg_expr_eval(a[0])) {
            m->pc = (uint16_t)a[1];
            clk = VG_CLK_1F_T;
        } else {
            m->pc = (uint16_t)a[2];
            clk = VG_CLK_1F_F;
        }
        break;
    case 0x20: {                        /* switch */
        int16_t x = vg_expr_eval(a[0]);
        for (i = 0; i < st->n; i++)
            if (a[2 + 2 * i] == x)
                break;
        if (i < st->n) {
            m->pc = (uint16_t)a[3 + 2 * i];
            clk = VG_CLK_20_CASE + (unsigned)i * VG_CLK_20_PER;
        } else {
            m->pc = (uint16_t)a[1];
            clk = VG_CLK_20_DEF + (unsigned)i * VG_CLK_20_PER;
        }
        break;
    }
    case 0x21:
        m->pc = (uint16_t)a[0];
        clk = VG_CLK_21;
        break;
    case 0x22:
        call_push(m->pc);
        m->pc = (uint16_t)a[0];
        clk = VG_CLK_22;
        break;
    case 0x23:                          /* return: v1 first, then the stack */
        if (a[0] > 0) {
            vg_vm_v1_int(vg_expr_eval(a[0]));
            clk = VG_CLK_23_EXPR;
        } else {
            vg_vm_v1_bool(1);
            clk = VG_CLK_23_NONE;
        }
        m->pc = call_pop();
        break;
    case 0x24: {                        /* menu */
        long id = (long)at;
        clk = vg.text.menu_last == id ? VG_CLK_24_SAME : VG_CLK_24_NEW;
        r = io->menu(id, &s->menu[a[0]]);
        vg_vm_v1_int((int16_t)r);
        break;
    }
    case 0x25:                          /* built-in sequence */
        vg.text.skip = 0;
        if (a[0] >= 0 && a[0] < VG_BUILTINS) {
            io->builtin(a[0]);
            clk = vg.text.skip == 1 ? VG_CLK_25_1 : VG_CLK_25_0;
        } else if (a[0] == VG_BUILTINS) {   /* the zero row: no routine */
            clk = VG_CLK_25_NULL;
        } else {
            vg_vm_fault("built-in sequence", a[0]);
        }
        vg_vm_v1_bool(vg.text.skip == 1);
        break;
    case 0x2B:
    case 0x2D:
        clk = VG_CLK_2B;
        break;
    case 0x2E:
        vg_vm_charge(VG_CLK_2E);
        if (m->on_step)
            m->on_step(m->on_step_ctx, at);
        return 0;
    case 0x2F:
        io->flash(a[0]);
        clk = VG_CLK_2F;
        break;
    case 0x30:
        if (a[1] > s->n_pal)
            vg_vm_fault("palette", a[1]);
        io->palette(a[1] ? s->pal[a[1]] : NULL, a[0]);
        clk = VG_CLK_30;
        break;
    case 0x31:
        io->pic_load(a[0], a[1], a[2], a[3], s->str + st->str);
        clk = VG_CLK_31;
        break;
    case 0x32: {
        struct vg_rect_op op;
        op.src = a[0]; op.sx = a[1]; op.sy = a[2]; op.w = a[3]; op.h = a[4];
        op.dst = a[5]; op.dx = a[6]; op.dy = a[7]; op.effect = a[8];
        io->rect_copy(&op);
        clk = VG_CLK_32;
        break;
    }
    case 0x33:
        io->clear(a[0]);
        clk = VG_CLK_33;
        break;
    case 0x34:
        m->pc = (uint16_t)(m->pc + a[0]);
        clk = VG_CLK_34;
        break;
    case 0x35:
        vg_vm_v1_int((int16_t)io->music_measure());
        clk = VG_CLK_35;
        break;
    case 0x37:
        if (a[0] == 0) {
            io->mouse_lock(1, 0);
            clk = VG_CLK_37_0;
        } else {
            io->mouse_lock(0, 0);
            clk = VG_CLK_37_1;
        }
        break;
    default:                            /* the loader takes no other opcode */
        vg_vm_error(NULL);
    }
    vg_vm_charge(clk);
    if (m->on_step)
        m->on_step(m->on_step_ctx, at);
    return 1;
}

int vg_vm_run(uint16_t entry)
{
    vg.vm.pc = entry;
    while (!lrv_sys_quitting(&vg.sys))
        if (!vg_vm_step())
            break;
    return VG_EXIT_OK;
}
