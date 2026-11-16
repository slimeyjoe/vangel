/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Op 32h: the rectangle copy and its transitions (docs/re/graphics.md §5). rect_copy
 * (0315:07CB) -> rect_dispatch (00DD:051A) -> the routines of segment 0783.
 *
 * Every routine is the original's loops written out, in its order of writes. As it goes it
 * charges the clocks of the original's instructions (gfx/fx_clk.h, made by
 * re-tools/fx_cost.py), each block before the write that ends it. A frame passes whenever the
 * reference machine would have spent one (lrv_sys_cpu), and the destination's picture at
 * every frame is then the original's at the same clock (tests/check_fx.py checks the clock
 * of every write). A read of the VSYNC counter (effect 31) is charged with the instruction
 * that reads it, as the interrupt comes before an instruction.
 *
 * Offsets are 16 bits, as the original's: writes past a plane's 32 000 bytes are dropped and
 * reads there give 0 (in VRAM they would reach the gap after each plane). Counts of zero, which
 * the original's loops would take as 65 536 (a width below 9 pixels in the word routines, a
 * height of 0, an odd height of 1 in effect 33, fewer than 2 lines or 16 pixels in effect 34),
 * never occur in the scenario; here such a loop does nothing. */
#include "vg.h"
#include "gfx/fx_clk.h"

static const uint16_t fx_head[4][4] = FX_HEAD;

struct fx {
    uint8_t *s[4], *d[4];               /* the source's and the destination's planes */
    int page;                           /* the destination's VRAM page, -1: memory */
    unsigned so, dof;                   /* byte offsets of the rectangles */
    int w, h;
};

/* ---- time ---------------------------------------------------------------------------------- */

static struct fx *cur;                  /* the transition running: marked before a present */

static void mark_dest(void)
{
    if (cur && cur->page >= 0)          /* the lines the rectangle may reach, whole */
        vg_mark_lines(cur->page, (int)(cur->dof / VG_PLANE_STRIDE),
                      (int)(cur->dof / VG_PLANE_STRIDE) + cur->h + 1);
}

void vg_cpu(uint32_t n)
{
    struct lrv_sys *s = &vg.sys;
    vg.gfx.clk += n;
    if (s->cpu_per_frame && s->cpu + n >= s->cpu_per_frame)
        mark_dest();
    lrv_sys_cpu(s, n);
}

#define clk(n) vg_cpu((uint32_t)(n))

static void wait_vsync(void)
{
    mark_dest();
    lrv_sys_frame_wait(&vg.sys);
}

/* ---- planes -------------------------------------------------------------------------------- */

static uint8_t rd(uint8_t *const *p, int q, unsigned o)
{
    o &= 0xFFFF;
    return o < VG_PLANE_BYTES ? p[q][o] : 0;
}

static void wr(struct fx *f, int q, unsigned o, uint8_t v)
{
    o &= 0xFFFF;
    if (o < VG_PLANE_BYTES)
        f->d[q][o] = v;
    if (vg.gfx.on_write)
        vg.gfx.on_write(vg.gfx.on_write_ctx, q, o, v);
}

/* rep movsw of n words of plane q from s to d, the clocks per word */
static void rep_words(struct fx *f, int q, unsigned s, unsigned d, int n)
{
    int k;
    if (n <= 0) {
        clk(REP_MOVS);
        return;
    }
    for (k = 0; k < 2 * n; k += 2) {
        clk(k ? REP_MOVS_EACH : REP_MOVS + REP_MOVS_EACH);
        wr(f, q, d + k, rd(f->s, q, s + k));
        wr(f, q, d + k + 1, rd(f->s, q, s + k + 1));
    }
}

/* a masked word, dst = src & m | dst & ~m, low byte first (lodsw ... stosw) */
static void put_masked(struct fx *f, int q, unsigned s, unsigned d, uint8_t lo, uint8_t hi)
{
    uint8_t a = (uint8_t)((rd(f->s, q, s) & lo) | (rd(f->d, q, d) & (uint8_t)~lo));
    uint8_t b = (uint8_t)((rd(f->s, q, s + 1) & hi) | (rd(f->d, q, d + 1) & (uint8_t)~hi));
    wr(f, q, d, a);
    wr(f, q, d + 1, b);
}

static uint16_t ror16(uint16_t v)
{
    return (uint16_t)((v >> 1) | (v << 15));
}

static uint8_t rol8(uint8_t v)
{
    return (uint8_t)((v << 1) | (v >> 7));
}

/* ---- the routines --------------------------------------------------------------------------- */

/* 10 and every unknown code: fx_copy 0783:0000, (w + 7) >> 4 words a line and plane */
static void fx_copy(struct fx *f)
{
    int nw = (f->w + 7) >> 4, i, q;
    clk(FX10_SETUP);
    for (i = 0; i < f->h; i++) {
        unsigned s = f->so + 80u * (unsigned)i, d = f->dof + 80u * (unsigned)i;
        for (q = 0; q < 4; q++) {
            clk(FX10_PLANE_PRE);
            rep_words(f, q, s, d, nw);
            clk(FX10_PLANE_POST);
        }
        clk(FX10_LINE_POST + (i + 1 < f->h ? J_TAKEN : J_NOT));
    }
    clk(FX10_EXIT);
}

/* 20: fx_masked 0783:007C, byte by byte, the source's colour-8 pixels left out */
static void fx_masked(struct fx *f)
{
    int nb = (f->w + 7) >> 3, i, c, q, k;
    clk(FX20_SETUP);
    for (i = 0; i < f->h; i++) {
        clk(FX20_LINE_PRE);
        for (c = 0; c < nb; c++) {
            unsigned s = f->so + 80u * (unsigned)i + (unsigned)c;
            unsigned d = f->dof + 80u * (unsigned)i + (unsigned)c;
            uint8_t v[4], m = 0;
            clk(FX20_BYTE_PRE);
            for (q = 0; q < 4; q++)
                v[q] = rd(f->s, q, s);
            for (k = 0; k < 8; k++) {
                int b = 7 - k;
                int col = ((v[0] >> b) & 1) | ((v[1] >> b) & 1) << 1 | ((v[2] >> b) & 1) << 2 |
                          ((v[3] >> b) & 1) << 3;
                clk(FX20_PIXEL);
                if (col == 8) {
                    clk(J_NOT + FX20_PIXEL_OR);
                    m |= (uint8_t)(0x80 >> k);
                } else {
                    clk(J_TAKEN);
                }
            }
            clk(FX20_MASK);
            if (m) {
                clk(J_NOT + FX20_MASKED_PRE);
                for (q = 0; q < 4; q++) {
                    uint8_t a;
                    clk(FX20_MASKED_AND);
                    a = (uint8_t)(rd(f->d, q, d) & m);
                    wr(f, q, d, a);
                    clk(FX20_MASKED_OR);
                    wr(f, q, d, (uint8_t)(a | (v[q] & (uint8_t)~m)));
                }
                clk(FX20_MASKED_END);
            } else {
                clk(J_TAKEN);
                for (q = 0; q < 4; q++) {
                    clk(FX20_OPAQUE);
                    wr(f, q, d, v[q]);
                }
            }
            clk(FX20_BYTE_POST + (c + 1 < nb ? LOOP_TAKEN : LOOP_NOT) + FX20_JMP);
        }
        clk(FX20_LINE_POST + (i + 1 < f->h ? J_NOT + FX20_JMP : J_TAKEN));
    }
    clk(FX20_EXIT);
}

/* 30: fx_dissolve4 0783:0350, four passes; pass p, line i takes the pixels with
 * x mod 4 = (p + i) mod 4 (8888h ror (p + i)); the source line goes to a temporary first */
static void fx_dissolve4(struct fx *f)
{
    int nw = (f->w + 7) >> 4, p, i, q, k;
    uint16_t dxp = 0x8888;
    uint8_t tmp[4][160];

    if (nw > 80)
        nw = 80;
    clk(FX30_SETUP);
    for (p = 0; p < 4; p++) {
        uint16_t m = dxp;
        clk(FX30_PASS_PRE);
        for (i = 0; i < f->h; i++) {
            unsigned s = f->so + 80u * (unsigned)i, d = f->dof + 80u * (unsigned)i;
            uint8_t lo = (uint8_t)m, hi = (uint8_t)(m >> 8);
            clk(FX30_LINE_PRE);
            for (q = 0; q < 4; q++) {
                if (q)
                    clk(FX30_TMP_PLANE);
                clk(REP_MOVS + REP_MOVS_EACH * nw);
                for (k = 0; k < 2 * nw; k++)
                    tmp[q][k] = rd(f->s, q, s + (unsigned)k);
            }
            clk(FX30_TMP_END);
            for (q = 0; q < 4; q++) {
                clk(FX30_PLANE_PRE);
                for (k = 0; k < nw; k++) {
                    unsigned o = d + 2u * (unsigned)k;
                    clk(FX30_WORD);
                    wr(f, q, o, (uint8_t)((tmp[q][2 * k] & lo) | (rd(f->d, q, o) & (uint8_t)~lo)));
                    wr(f, q, o + 1, (uint8_t)((tmp[q][2 * k + 1] & hi) |
                                              (rd(f->d, q, o + 1) & (uint8_t)~hi)));
                    clk(k + 1 < nw ? LOOP_TAKEN : LOOP_NOT);
                }
                if (q < 3)
                    clk(FX30_PLANE_POST);
            }
            clk(FX30_LINE_POST + (i + 1 < f->h ? LOOP_TAKEN : LOOP_NOT) + FX30_JMP);
            m = ror16(m);
        }
        clk(FX30_PASS_POST + (p < 3 ? LOOP_TAKEN : LOOP_NOT) + FX30_JMP);
        dxp = ror16(dxp);
    }
    clk(FX30_EXIT);
}

/* fx31_wait (00DD:04F9), the routine's callback after each step: until the VSYNC counter has
 * moved by 2 since the last step */
static void fx31_wait(void)
{
    clk(FX31_CALL + FX31_WAIT_PRE);
    for (;;) {
        uint32_t at = vg.sys.frame;     /* at the loop's head */
        int d;
        clk(FX31_WAIT_READ);
        d = (int16_t)(vg.gfx.fx31_last - vg.timers.vsync);
        clk(FX31_WAIT_TEST);
        if ((d < 0 ? -d : d) >= 2)
            break;
        clk(J_TAKEN);
        if (vg.sys.frame == at)         /* it spins until the next VSYNC */
            wait_vsync();
    }
    clk(J_NOT + FX31_WAIT_LAST);
    vg.gfx.fx31_last = vg.timers.vsync;
    clk(FX31_WAIT_END);
}

/* 31: fx_dissolve64 0783:07C0, 64 steps of one pixel column in every byte on one line in 8,
 * each followed by fx31_wait */
static void fx_dissolve64(struct fx *f)
{
    int nw = (f->w + 7) >> 4, c, i, q, k;
    clk(FX31_SETUP);
    for (c = 64; c >= 1; c--) {
        int b = vg.gfx.fx31_order[c - 1];
        uint16_t mask = (uint16_t)(0x0101 << (b & 7));
        int phase = (b >> 3) & 7;
        clk(FX31_STEP_PRE);
        for (i = 0; i < f->h; i++) {
            clk(FX31_LINE_PRE);
            if (((f->h - i) & 7) != phase) {
                clk(J_TAKEN);
            } else {
                unsigned s = f->so + 80u * (unsigned)i, d = f->dof + 80u * (unsigned)i;
                clk(J_NOT + FX31_PLANE0_PRE);
                for (q = 0; q < 4; q++) {
                    if (q)
                        clk(FX31_PLANE_NEXT);
                    for (k = 0; k < nw; k++) {
                        clk(FX31_WORD);
                        put_masked(f, q, s + 2u * k, d + 2u * k, (uint8_t)mask,
                                   (uint8_t)(mask >> 8));
                        clk(k + 1 < nw ? LOOP_TAKEN : LOOP_NOT);
                    }
                }
                clk(FX31_PLANE3_POST);
            }
            clk(FX31_LINE_POST + (i + 1 < f->h ? LOOP_TAKEN : LOOP_NOT) + FX31_JMP);
        }
        fx31_wait();
        clk(FX31_STEP_POST + (c > 1 ? LOOP_TAKEN : LOOP_NOT) + FX31_JMP);
    }
    clk(FX31_EXIT);
}

/* one line of effect 32: dst = src & a | dst & b, byte by byte, the four planes */
static void fx32_line(struct fx *f, int line, int nb, uint8_t a, uint8_t b)
{
    unsigned s = f->so + 80u * (unsigned)line, d = f->dof + 80u * (unsigned)line;
    int q, k;
    for (q = 0; q < 4; q++) {
        if (q)
            clk(FX32_PLANE_NEXT);
        for (k = 0; k < nb; k++) {
            clk(FX32_BYTE);
            wr(f, q, d + (unsigned)k,
               (uint8_t)((rd(f->s, q, s + (unsigned)k) & a) | (rd(f->d, q, d + (unsigned)k) & b)));
            clk(k + 1 < nb ? LOOP_TAKEN : LOOP_NOT);
        }
    }
}

/* 32: fx_checker_tb 0783:05DD, h steps: line i from the top and line h-1-i from the bottom,
 * with the byte masks AAh / 55h alternating per step */
static void fx_checker_tb(struct fx *f)
{
    int nb = (f->w + 7) >> 3, i;
    uint8_t dl = 0x55, dh = 0xAA;
    clk(FX32_SETUP + ((f->h & 1) ? J_NOT : J_TAKEN) + FX32_SETUP2);
    for (i = 0; i < f->h; i++) {
        clk(FX32_ITER_PRE);
        dl = rol8(dl);
        dh = rol8(dh);
        fx32_line(f, i, nb, dl, dh);
        clk(FX32_BOTTOM_PRE);
        fx32_line(f, f->h - 1 - i, nb, dl, dh);
        clk(FX32_ITER_POST + (i + 1 < f->h ? LOOP_TAKEN : LOOP_NOT) + FX32_JMP);
    }
    clk(FX32_EXIT);
}

/* one line of effect 33: four planes of rep movsw */
static void fx33_line(struct fx *f, int line, int nw)
{
    unsigned s = f->so + 80u * (unsigned)line, d = f->dof + 80u * (unsigned)line;
    int q;
    for (q = 0; q < 4; q++) {
        if (q)
            clk(FX33_PLANE_NEXT);
        rep_words(f, q, s, d, nw);
    }
}

/* 33: fx_interlace_tb 0783:0494, an odd height's last line first; then line 2k from the top
 * and line h'-1-2k from the bottom */
static void fx_interlace_tb(struct fx *f)
{
    int nw = (f->w + 7) >> 4, h = f->h, top = 0, bot = f->h - 1, k, pairs;
    clk(FX33_SETUP);
    if (h & 1) {
        clk(J_NOT + FX33_ODD_PRE);
        fx33_line(f, bot, nw);
        clk(FX33_ODD_POST);
        h--;
        bot--;
    } else {
        clk(J_TAKEN);
    }
    clk(FX33_PAIRS);
    pairs = h >> 1;
    for (k = 0; k < pairs; k++) {
        clk(FX33_TOP_PRE);
        fx33_line(f, top, nw);
        clk(FX33_BOTTOM_PRE);
        fx33_line(f, bot, nw);
        clk(FX33_PAIR_POST + (k + 1 < pairs ? J_NOT + FX33_JMP : J_TAKEN));
        top += 2;
        bot -= 2;
    }
    clk(FX33_EXIT);
}

/* 34: fx_slide_lr 0783:08DA, nb/2 steps: even lines get the rightmost 2k bytes of their source
 * at their left edge, odd lines the leftmost 2k bytes at their right edge; always into VRAM */
static void fx_slide_lr(struct fx *f)
{
    int nb = (f->w + 7) >> 3, steps = nb >> 1, pairs = f->h >> 1, k, j, q;
    clk(FX34_SETUP);
    for (k = 1; k <= steps; k++) {
        unsigned n = 2u * (unsigned)k;
        clk(FX34_STEP_PRE);
        for (j = 0; j < pairs; j++) {
            unsigned ea = 80u * (unsigned)(2 * j), oa = ea + 80u;
            clk(FX34_EVEN_PRE);
            for (q = 0; q < 4; q++) {
                if (q)
                    clk(FX34_PLANE_NEXT);
                rep_words(f, q, f->so + ea + (unsigned)nb - n, f->dof + ea, k);
            }
            clk(FX34_ODD_PRE);
            for (q = 0; q < 4; q++) {
                if (q)
                    clk(FX34_PLANE_NEXT);
                rep_words(f, q, f->so + oa, f->dof + oa + (unsigned)nb - n, k);
            }
            clk(FX34_PAIR_POST + (j + 1 < pairs ? LOOP_TAKEN : LOOP_NOT) + FX34_JMP);
        }
        clk(FX34_STEP_POST + (k < steps ? LOOP_TAKEN : LOOP_NOT) + FX34_JMP);
    }
    clk(FX34_EXIT);
}

/* ---- rect_copy -------------------------------------------------------------------------------- */

static int kind(int buf)
{
    return buf >= 10 && buf <= 12 ? buf - 10 : 3;
}

/* the planes of a buffer as rect_dispatch selects them: VRAM through the access page, which
 * 10 and 11 set (0 or 1) and another number leaves; 12 the memory planes */
static int select_buf(int buf, int *vram)
{
    if (buf == 10 || buf == 11)
        lrv_screen_set_access(&vg.screen, buf - 10);
    *vram = buf != 12;
    return buf;
}

static void planes_of(uint8_t **p, int vram)
{
    struct lrv_surface *s = vram ? lrv_screen_access(&vg.screen) : &vg.screen.buffer[0];
    int q;
    for (q = 0; q < 4; q++)
        p[q] = s->plane[q];
}

int vg_rect_copy(const struct vg_rect_op *op)
{
    struct fx f;
    int svram, dvram, e = op->effect;

    if (!vg.gfx.ready)
        return 0;
    /* (the pointer is hidden here: the mouse comes with the input, M2) */
    clk(fx_head[kind(op->src)][kind(op->dst)]);
    select_buf(op->src, &svram);
    select_buf(op->dst, &dvram);
    /* the source is selected first, then the destination: VRAM to VRAM reads the
     * destination's page */
    planes_of(f.s, svram);
    if (e == 34)
        dvram = 1;                      /* A800h.. whatever dst says */
    planes_of(f.d, dvram);
    f.page = dvram ? vg.screen.access_page : -1;
    f.so = (unsigned)(op->sy * 80 + (op->sx >> 3));
    f.dof = (unsigned)(op->dy * 80 + (op->dx >> 3));
    f.w = op->w;
    f.h = op->h;
    cur = &f;

    if (e < 20 || e > 34) {
        clk(FX_SWITCH_OTHER);
        fx_copy(&f);
        clk(FX_TAIL);
    } else if (e == 31) {
        vg.timers.vsync = 0;
        vg.gfx.fx31_last = 0;
        clk(FX_SWITCH_31);
        fx_dissolve64(&f);
        clk(FX_TAIL_31);
    } else {
        clk(FX_SWITCH_TABLE);
        switch (e) {
        case 20: fx_masked(&f); break;
        case 30: fx_dissolve4(&f); break;
        case 32: fx_checker_tb(&f); break;
        case 33: fx_interlace_tb(&f); break;
        case 34: fx_slide_lr(&f); break;
        default: fx_copy(&f); break;
        }
        clk(e == 34 ? FX_TAIL_34 : FX_TAIL);
    }
    mark_dest();
    cur = NULL;
    lrv_screen_set_access(&vg.screen, 0);
    vg_win_snapshot();
    return 1;
}
