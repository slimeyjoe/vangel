/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The scenario and its interpreter (docs/re/scenario-format.md): the loader of "CRSC" files
 * (scb.c), expressions (expr.c), the virtual machine and its 34 statements (vm.c), the
 * storage record GAME.DAT (game/saves.c).
 *
 * The tables keep the original's numbering: everything is 1-based, and entry 0 of each table
 * exists, as the original's pointer arrays have an entry 0 (an unused variable slot, which the
 * save file's off-by-one reaches; a NULL statement and message).
 *
 * Where the original reads outside its tables (a jump past the last statement, a variable
 * the table does not have, a call stack a damaged save made too deep), it reads memory that
 * is not the scenario's; the engine ends the program there as the interpreter's own run-time
 * errors do, with exit code 4 (vg_vm_fault). The scenario never does it. */
#ifndef VG_VM_VM_H
#define VG_VM_VM_H

#include <stdint.h>
#include "lrvne/core.h"
#include "gfx/gfx.h"
#include "text/text.h"

#define VG_CALL_STACK   32              /* words of 0A9F:0000; 31 calls deep at most */
#define VG_CALL_MAX     31
#define VG_CASES_MAX    15              /* switch (20h): cases per statement */
#define VG_BUILTINS     6               /* table 0AB1:0000; row 6 is zeros */

/* the exit codes of M.EXE (docs/re/platform.md §4) */
enum vg_exit_code {
    VG_EXIT_OK = 0,                     /* statement 2Eh */
    VG_EXIT_USAGE = 1,                  /* no scenario, it cannot be opened, graphics fail */
    VG_EXIT_LOAD = 2,                   /* the scenario or the text does not load */
    VG_EXIT_MEMORY = 3,                 /* out of memory while loading */
    VG_EXIT_RUN = 4,                    /* the interpreter's run-time errors */
    VG_EXIT_CRT = 255                   /* the C library's (R6003) */
};

/* variable and leaf types: bit 1 literal, 2 variable, 4 integer, 8 boolean */
#define VG_T_INT        6
#define VG_T_BOOL       10

struct vg_var {
    int16_t type, value;
};

/* an expression node: form 0 = operator (k = op, a = left, b = right), 1 = leaf (k = kind,
 * a = value) */
struct vg_expr {
    int16_t form, k, a, b;
};

/* a statement: its opcode and operands, words of the pool from `at`, in the order below
 * (vm.c); a string operand (31h, 1Bh) is `str`, an offset into the string pool. Op 20h has
 * expr, default and then n pairs (value, target). */
struct vg_stmt {
    uint8_t op;
    uint8_t n;                          /* 20h: the cases */
    uint32_t at;
    uint32_t str;
};

struct vg_scb {
    /* the header and the sections (§2.1, §2.2) */
    uint16_t entry;                     /* 0BA1:0002 */
    uint16_t key;                       /* 0BA1:0010 */
    uint32_t size, h0e;                 /* stored, not used */
    int16_t n_stmt, n_menu, n_expr, n_msg, n_pal, n_var, n_0b, n_0c;
    char text[64];                      /* the text file's name (section 0Ah) */
    /* the tables, [0..n] */
    struct vg_var *var;                 /* the initial values */
    struct vg_menu *menu;
    struct vg_expr *expr;
    uint8_t (*pal)[48];                 /* R[16] G[16] B[16] */
    struct vg_stmt *stmt;
    /* pools */
    int16_t *w;
    uint32_t nw, cap_w;
    char *str;
    uint32_t nstr, cap_str;
    uint8_t *menu_str;
    uint32_t menu_bytes;
};

/* What the statements call outside the interpreter: the engine's subsystems, or a test's
 * stand-ins (tests/test_vm.c). The result flag (byte 0BA1:0000) is vg.text.skip: the
 * statements clear it before and read it after msg, builtin and wait. */
struct vg_vm_io {
    int  (*wait)(int t, int skippable);         /* 15h: 0, or -1 with no free timer */
    void (*wait_input)(void);                   /* 16h */
    void (*win_restore)(void);                  /* 18h */
    void (*msg)(int n);                         /* 19h: msg_show */
    void (*fade_out)(int to_white, int t);      /* 1Ah */
    void (*music_play)(int volume, const char *name);   /* 1Bh */
    int  (*music_state)(void);                  /* 1Ch: 10 = a song plays */
    void (*music_fade)(int t);
    int  (*menu)(long stmt, const struct vg_menu *m);   /* 24h: the choice */
    void (*builtin)(int n);                     /* 25h: routine n of the table (0..5) */
    void (*flash)(int t);                       /* 2Fh */
    void (*palette)(const uint8_t *pal, int t); /* 30h; pal NULL for numbers <= 1 */
    void (*pic_load)(int buf, int x, int y, int flag, const char *name);    /* 31h */
    void (*rect_copy)(const struct vg_rect_op *op);     /* 32h */
    void (*clear)(int buf);                     /* 33h */
    int  (*music_measure)(void);                /* 35h */
    void (*mouse_lock)(int lock, int show);     /* 37h */
};

struct vg_vm {
    struct vg_scb scb;
    const struct vg_vm_io *io;
    uint16_t pc;                        /* DS:005A: the next statement */
    int16_t depth;                      /* DS:005C */
    uint16_t stack[VG_CALL_STACK];      /* 0A9F:0000 */
    struct vg_var *var;                 /* [0..n_var], entry 0 the unused slot */
    uint64_t clk;                       /* clocks charged since the start (tests) */
    /* tests: after every statement, the number it had */
    void (*on_step)(void *ctx, unsigned pc);
    void *on_step_ctx;
};

/* scb.c */
/* scb_load (063C:00E8) from the file's bytes: VG_EXIT_OK, or the exit code the original ends
 * with (VG_EXIT_LOAD, VG_EXIT_MEMORY). The scenario's tables in vg.vm.scb. */
int  vg_scb_load(const uint8_t *data, uint32_t size);
void vg_scb_free(void);

/* expr.c: expr_eval (0000:0089); ends the program with exit 4 or R6003 as the original */
int16_t vg_expr_eval(int n);

/* vm.c */
extern const struct vg_vm_io vg_vm_engine_io;
/* The variables set from the scenario, the stack empty, pc = entry. 1, or 0 when out of
 * memory. vg_vm_free undoes it. */
int  vg_vm_init(uint16_t entry);
void vg_vm_free(void);
/* vm_step (001E:0133): one statement; 1, or 0 after 2Eh. */
int  vg_vm_step(void);
/* vm_run (001E:011F): from statement `entry` until 2Eh, a quit or a reset; returns the exit
 * code (0). */
int  vg_vm_run(uint16_t entry);
/* The statement main() starts with (§1 step 6): the entry statement when it is 2Dh, else 1
 * (the original's warning is a debug print it no longer makes). */
uint16_t vg_vm_entry(void);
/* A variable by number for the original's unchecked reads and writes; vg_vm_fault when the
 * table has no such entry. */
struct vg_var *vg_vm_var(int n);
/* v1 := bool b / int n (§5.3) */
void vg_vm_v1_bool(int b);
void vg_vm_v1_int(int16_t n);
/* Clocks of the reference machine the interpreter spends (vm/vm_clk.h): frames pass as
 * they are spent (vg_cpu); vg.vm.clk counts them for the tests. */
void vg_vm_charge(uint32_t n);
/* A reference outside the scenario's tables: logged, the program ends with exit 4. */
LRV_NORETURN void vg_vm_fault(const char *what, long n);
/* The interpreter's own run-time errors: the message, then exit(4). */
LRV_NORETURN void vg_vm_error(const char *msg);

/* game/saves.c (docs/re/scenario-format.md §7) */
/* save_slot (001E:042C) / load_slot (001E:0577) of slot 0..2 of the storage record "game.dat" */
void vg_save_slot(int slot);
void vg_load_slot(int slot);
/* the record's size: (variables + 24) * 3, 16-bit */
int  vg_save_record_size(void);

#endif
