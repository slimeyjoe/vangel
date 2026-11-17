/* SPDX-License-Identifier: GPL-3.0-or-later */
/* vangel: the engine's state and what its modules share.
 *
 * The original is one DOS program, M.EXE (Microsoft C, 1995), with global state: the graphics
 * buffers, the message window, the timer slots, the scenario VM (docs/re/). The engine keeps
 * that shape in one structure, `vg`, so the modules can be read next to the research
 * documents; comments name the original's addresses (SEG:OFF of the unpacked image) where a
 * field models one.
 *
 * Everything below the original program is lrvne (source/lrvne: the frame and the input
 * queue, the screen, the FM chip and the mixer, PMD, fonts, the pack, the profile parser, the
 * backends); its instances are members of `vg`. The engine names no game: a game is the
 * profile and the data of its pack. */
#ifndef VG_VG_H
#define VG_VG_H

#include <setjmp.h>
#include <stddef.h>
#include <stdint.h>
#include "lrvne/app.h"
#include "lrvne/core.h"
#include "lrvne/font.h"
#include "lrvne/gfx.h"
#include "lrvne/hal.h"
#include "lrvne/pack.h"
#include "lrvne/pc98.h"
#include "lrvne/profile.h"
#include "lrvne/sys.h"
#include "bios/bios.h"
#include "gfx/gf.h"
#include "gfx/gfx.h"
#include "snd/snd.h"
#include "text/text.h"
#include "vm/timer.h"
#include "vm/vm.h"

#define VG_NAME "vangel"                /* the program: usage, messages, the saves' directory */

/* The machine: the PC-98's 640x400 graphics, four bit-planes B, R, G, I of 80 bytes a line,
 * addressed by offset y * 80 + x / 8 as the original does. One tick is one VSYNC of that
 * mode, 56.42 Hz; the original's timers count them (docs/re/platform.md §2). */
#define VG_SCREEN_W     LRV_PC98_W
#define VG_SCREEN_H     LRV_PC98_H
#define VG_PLANE_STRIDE LRV_PC98_STRIDE
#define VG_PLANE_BYTES  (VG_PLANE_STRIDE * VG_SCREEN_H)     /* 32 000 */

/* ---- the pack: this engine's entry types (tools/vgpak.py has the same numbers) ------------- */
enum vg_pack_type {
    VG_PT_SCENARIO = LRV_PT_ENGINE,     /* the compiled scenario "CRSC", byte-exact */
    VG_PT_TEXT,                         /* the message file "CRTX", byte-exact */
    VG_PT_LIBRARY,                      /* the picture library "GA00", byte-exact */
    VG_PT_SONG,                         /* a PMD song, byte-exact */
    VG_PT_FILE                          /* another file of the original (ANNOUNCE.TXT) */
};

/* ---- trace events (test automation; lrvne/trace.h has the kinds every engine shares) ------- */
enum vg_trace_kind {
    VG_TR_PICTURE = LRV_TR_ENGINE,      /* name = picture, a0 = buffer, a1 = x, a2 = y,
                                           a3 = flag (1: colour 8 transparent) */
    VG_TR_KIND_END
};
/* their names for the control protocol, in this order (app.c) */
#define VG_TRACE_NAMES "picture"

/* a0 of LRV_TR_WAIT */
enum vg_wait_kind {
    VG_WAIT_TICKS = 0,                  /* a timed wait */
    VG_WAIT_KEY                         /* a wait for input */
};
enum vg_wait_leave { VG_LEAVE_KEY = 0, VG_LEAVE_QUIT };

/* ---- the engine's own command-line options (app.c) ----------------------------------------- */
struct vg_options {
    /* picture viewer (a tool, not the game): 1 = browse the library's pictures instead of
     * running the game; view_picture names the first one (NULL = the library's first) */
    int view;
    const char *view_picture;
};

/* ---- the game profile (game/profile.c, from the pack's "profile" entry) -------------------- */
struct vg_profile {
    struct lrv_profile_base base;       /* id, title, lang (of the original text), modules */
    char scenario[16];                  /* the program's arguments (GAME.BAT): the scenario */
    char library[16];                   /* ... and the picture library */
    char sound[16];                     /* the sound setup: pmd26k, none */
    char pmd[64];                       /* the driver's command line (GAME.BAT), "/DF5 /M8" */
    char mouse[8];                      /* the console question "use the mouse?": ask, on, off */
    /* the reference machine: 80286 clocks per VSYNC (re-tools/m286.py), the time base of
     * what the original runs at CPU speed (most transitions); 0 = such loops take no time */
    int cpu_per_frame;
};

/* ---- the state ----------------------------------------------------------------------------- */
struct vg_state {
    const struct lrv_hal *hal;
    struct lrv_run_cfg cfg;             /* what the command line asked for */
    struct vg_options opt;
    struct lrv_pack pak;
    struct vg_profile profile;

    /* the frame (the VSYNC tick), the input queue, quit and reset */
    struct lrv_sys sys;

    /* graphics (docs/re/graphics.md §8): VRAM pages 0 and 1 (buffers 10 and 11 of the
     * scenario) and the memory planes of buffer 12; screen.rgb is the DAC */
    struct lrv_screen screen;

    /* the picture library GDATA.LIB */
    struct gf_lib lib;

    /* the VSYNC timer: the frame counter and the 16 timer slots */
    struct vg_timers timers;

    /* the buffers' state, the palettes, the window's background and work buffer */
    struct vg_gfx gfx;

    /* the keyboard latch, the mouse, the device layer */
    struct vg_input input;

    /* the message file, the fonts, the skip flag, the menus' memory */
    struct vg_text text;

    /* the scenario and its interpreter */
    struct vg_vm vm;

    /* the music: the sound board and its driver, the binding, the music layer */
    struct vg_mus mus;

    /* the program's exit (vg_exit): where it unwinds to, and its code */
    jmp_buf *exit_to;
    int exit_code;
};

extern struct vg_state vg;

/* app.c: the engine as a backend sees it; main() is vg_main */
extern const struct lrv_app vg_app;
int vg_main(int argc, char **argv);

/* game/run.c: runs the game (or the viewer) until it quits; returns the process exit code */
int vg_run(const struct lrv_hal *hal, const struct lrv_run_cfg *cfg,
           const struct vg_options *opt);
/* The steps of vg_run, for the tests, on a zeroed vg: vg_open_pack opens the pack, loads the
 * profile and selects the language (LRV_OK or enum lrv_err, logged); vg_machine_open does that
 * and brings the machine up: display and screen, the frame, the library (failures are fatal);
 * vg_machine_close undoes it. */
int  vg_open_pack(const struct lrv_hal *hal, const struct lrv_run_cfg *cfg);
void vg_machine_open(const struct lrv_hal *hal, const struct lrv_run_cfg *cfg);
void vg_machine_close(void);

/* game/run.c: the original's exit(code): the program unwinds to vg_exit_to (vg_run, or a
 * test's own setjmp), which shuts down; fatal when nothing is armed. */
LRV_NORETURN void vg_exit(int code);
/* a run-time error of the original's C library ends the program as it did: the message,
 * exit code 255 */
enum vg_runtime_error { VG_R6003 };     /* integer divide by 0 */
LRV_NORETURN void vg_runtime_error(int which);

/* game/console.c: built-in 0 INIT (0504:0004), the DOS console's question whether to use the
 * mouse, answered by the profile's mouse=on|off or asked (ask). 1 = yes. */
int  vg_console_init(void);

/* game/profile.c: the defaults, then the pack's "profile" entry; LRV_OK or enum lrv_err */
int vg_profile_load(struct vg_profile *p, const struct lrv_pack *pk);

#endif
