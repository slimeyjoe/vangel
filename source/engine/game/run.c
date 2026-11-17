/* SPDX-License-Identifier: GPL-3.0-or-later */
/* vg_run: start-up, the game (or the picture viewer), shutdown. */
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include "vg.h"

struct vg_state vg;

/* ---- picture viewer (--view): the library's pictures as op 31h draws them into a cleared
 * page 0 at their own position, opaque. The pictures have no palette (the scenario sets one
 * with op 30h): the viewer takes the palette the scenario shows each picture with from the
 * pack's "viewer" entry (tools/mkpack.py), else the engine's default palette. Left/right (or
 * up/down, Return, Space, left click) step, Esc / right click quits. ---- */

static int hexval(int c)
{
    return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 :
           c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1;
}

/* the viewer palette of a picture: 48 hex digits R G B per colour */
static int viewer_palette(const char *name, uint8_t *rgb)
{
    char buf[64];
    int k;
    if (lrv_pack_meta_get(&vg.pak, "viewer", name, buf, sizeof buf) != LRV_OK &&
        lrv_pack_meta_get(&vg.pak, "viewer", "default", buf, sizeof buf) != LRV_OK)
        return 0;
    if (strlen(buf) != VG_PAL_BYTES)
        return 0;
    for (k = 0; k < VG_PAL_BYTES; k++) {
        int v = hexval(buf[k]);
        if (v < 0)
            return 0;
        rgb[k] = (uint8_t)v;
    }
    return 1;
}

static void viewer_show(int i)
{
    struct lrv_surface *page = lrv_screen_access(&vg.screen);
    struct gf_header h;
    struct lrv_rect r;
    char name[13];
    uint8_t rgb[VG_PAL_BYTES];
    int rc, k;

    gf_lib_member(&vg.lib, i, name, NULL, NULL);
    lrv_screen_clear_access(&vg.screen);
    if (viewer_palette(name, rgb)) {
        lrv_screen_set_palette(&vg.screen, rgb);
    } else {
        for (k = 0; k < 16; k++)        /* a grey ramp */
            lrv_screen_set_colour(&vg.screen, k, k, k, k);
    }
    rc = gf_draw(&vg.lib, i, page, -1, -1, 0, &h, &r);
    if (rc != LRV_OK) {
        lrv_log(vg.hal, LRV_LOG_WARN, "viewer: %s: cannot be decoded", name);
        return;
    }
    lrv_screen_mark_surface(&vg.screen, page, &r);
    lrv_sys_trace(&vg.sys, VG_TR_PICTURE, name, 0, 10, h.x, h.y, 0);
    lrv_log(vg.hal, LRV_LOG_INFO, "%s: %dx%d at (%d, %d)", name, h.w, h.h, h.x, h.y);
}

/* a key of the viewer: 1 / -1 = the next / the previous picture, 2 = quit, 0 = none */
static int viewer_key(int key)
{
    switch (key) {
    case LRV_K_RIGHT: case LRV_K_DOWN: case LRV_K_RETURN: case LRV_K_SPACE:
        return 1;
    case LRV_K_LEFT: case LRV_K_UP:
        return -1;
    case LRV_K_ESC:
        return 2;
    default:
        return 0;
    }
}

static int run_viewer(void)
{
    int i = 0, n = vg.lib.count;
    if (n <= 0) {
        lrv_log(vg.hal, LRV_LOG_ERROR, "viewer: the library has no pictures");
        return 1;
    }
    if (vg.opt.view_picture) {
        i = gf_lib_find(&vg.lib, vg.opt.view_picture);
        if (i < 0) {
            lrv_log(vg.hal, LRV_LOG_WARN, "viewer: no picture %s", vg.opt.view_picture);
            i = 0;
        }
    }
    viewer_show(i);
    lrv_sys_trace(&vg.sys, LRV_TR_WAIT, 0, 0, VG_WAIT_KEY, 0, 0, 0);
    for (;;) {
        struct lrv_keypress press;
        int dir = 0;
        lrv_sys_frame_wait(&vg.sys);
        if (lrv_sys_resetting(&vg.sys)) {   /* the reset key: back to the first picture */
            lrv_sys_reset_done(&vg.sys);
            i = 0;
            viewer_show(i);
            continue;
        }
        if (lrv_sys_quitting(&vg.sys))
            break;
        while (lrv_sys_key_read(&vg.sys, &press)) {
            int d = viewer_key(press.key);
            if (d == 2)
                lrv_sys_request_quit(&vg.sys);
            else if (d)
                dir = d;
        }
        if (lrv_sys_mouse_pressed(&vg.sys, LRV_EV_MOUSE_L))
            dir = 1;
        if (lrv_sys_mouse_pressed(&vg.sys, LRV_EV_MOUSE_R))
            lrv_sys_request_quit(&vg.sys);
        if (dir && !lrv_sys_quitting(&vg.sys)) {
            lrv_sys_trace(&vg.sys, LRV_TR_WAIT, 0, 0, VG_WAIT_KEY, 1, VG_LEAVE_KEY, 0);
            i = ((i + dir) % n + n) % n;
            viewer_show(i);
            lrv_sys_trace(&vg.sys, LRV_TR_WAIT, 0, 0, VG_WAIT_KEY, 0, 0, 0);
        }
    }
    lrv_sys_trace(&vg.sys, LRV_TR_WAIT, 0, 0, VG_WAIT_KEY, 1, VG_LEAVE_QUIT, 0);
    return 0;
}

/* ---- the program's exit ----------------------------------------------------------------- */

void vg_exit(int code)
{
    vg.exit_code = code;
    if (!vg.exit_to)
        lrv_fatal(vg.hal, "exit %d", code);
    longjmp(*vg.exit_to, 1);
}

/* run-time errors of the original's C library (Microsoft C): the message, _exit(255) */
void vg_runtime_error(int which)
{
    static const char *const msg[] = { "R6003 - integer divide by 0" };
    (void)which;
    lrv_log(vg.hal, LRV_LOG_ERROR, "run-time error %s", msg[0]);
    vg_exit(VG_EXIT_CRT);
}

/* ---- the game: main (0468:000E) and run_game (001E:0069) ---------------------------------- */

/* the scenario, its text and the interpreter's state; VG_EXIT_OK or the exit code */
static int game_load(void)
{
    const struct lrv_pack_entry *e;
    uint8_t *data;
    uint32_t size;
    int rc;

    /* fopen(argv[1]) fails: exit(1) (the "file not found" is a debug print it no longer
     * makes) */
    e = lrv_pack_find(&vg.pak, vg.profile.scenario, VG_PT_SCENARIO);
    if (!e || !(data = lrv_pack_load(&vg.pak, e, &size))) {
        lrv_log(vg.hal, LRV_LOG_ERROR, "the pack has no scenario %s", vg.profile.scenario);
        return VG_EXIT_USAGE;
    }
    rc = vg_scb_load(data, size);
    lrv_pack_free(&vg.pak, data, size);
    if (rc != VG_EXIT_OK) {
        lrv_log(vg.hal, LRV_LOG_ERROR, "%s does not load (exit %d)", vg.profile.scenario, rc);
        return rc;
    }
    if (!vg_txb_load(vg.vm.scb.text, vg.vm.scb.n_msg)) {
        lrv_log(vg.hal, LRV_LOG_ERROR, "%s does not load", vg.vm.scb.text);
        return VG_EXIT_LOAD;
    }
    if (!vg_vm_init(vg_vm_entry()))
        return VG_EXIT_MEMORY;
    return VG_EXIT_OK;
}

static void game_free(void)
{
    vg_input_term();
    vg_mus_term();                      /* also an atexit function of run_game */
    vg_vm_free();
    vg_scb_free();
    vg_txb_free();
}

/* the subsystems run_game starts, the interpreter, and their shutdown; the exit code */
static int game_run(unsigned devices)
{
    jmp_buf here;
    int rc;

    vg.exit_to = &here;
    if (setjmp(here)) {
        rc = vg.exit_code;
    } else {
        rc = game_load();
        if (rc == VG_EXIT_OK) {
            /* timer_init: installed with the machine; mus_init's result is not looked at:
             * without a driver the game is silent */
            vg_mus_init();
            if (!vg_input_init(devices)) {
                lrv_log(vg.hal, LRV_LOG_ERROR, "input init failed");
                rc = VG_EXIT_RUN;
            } else {
                vg_gfx_init();
                rc = vg_vm_run(vg.vm.pc);
            }
        }
    }
    vg.exit_to = NULL;
    game_free();
    return rc;
}

/* the reset key: the program from its start, the mouse's answer kept */
static void game_reset(void)
{
    vg_timer_remove();
    vg.gfx.ready = 0;
    vg.gfx.fade_in_last = vg.gfx.fade_out_last = 0;
    vg.gfx.fx31_last = 0;
    vg.text.skip = 0;
    vg.text.menu_last = 0;
    vg.text.menu_choice = 0;
    strcpy(vg.mus.name, "none");
    vg.mus.vol = 0;
    vg.mus.in_al = 0;
    memset(&vg.input, 0, sizeof vg.input);
    lrv_screen_clear_access(&vg.screen);
    vg_timer_install();
}

static int run_game(void)
{
    unsigned devices = VG_DEV_KBD | VG_DEV_MOUSE | VG_DEV_JOY;     /* DS:0110 */
    int rc;

    if (!vg_console_init())
        devices &= ~(unsigned)VG_DEV_MOUSE;
    if (lrv_sys_quitting(&vg.sys))
        return 0;
    for (;;) {
        rc = game_run(devices);
        if (!lrv_sys_resetting(&vg.sys))
            return rc;
        lrv_sys_reset_done(&vg.sys);
        game_reset();
    }
}

/* ---- the engine --------------------------------------------------------------------------- */

int vg_open_pack(const struct lrv_hal *hal, const struct lrv_run_cfg *cfg)
{
    const char *lang;
    int rc;

    vg.hal = hal;
    vg.cfg = *cfg;
    if ((rc = lrv_pack_open(&vg.pak, hal, LRV_PACK_MAIN)) != LRV_OK)
        return rc;
    rc = vg_profile_load(&vg.profile, &vg.pak);
    if (rc == LRV_ERR_NOTFOUND || !vg.profile.base.id[0]) {
        lrv_log(hal, LRV_LOG_ERROR, "pack: no game profile, or one without an id");
        lrv_pack_close(&vg.pak);
        return LRV_ERR_FORMAT;
    }
    lang = cfg->lang ? cfg->lang : vg.profile.base.lang;
    lrv_pack_set_lang(&vg.pak, lrv_pack_lang_id(&vg.pak, lang));
    if (!vg.pak.lang && !lrv_name_eq(lang, vg.profile.base.lang))
        lrv_log(hal, LRV_LOG_WARN, "the pack has no language \"%s\": the original text is "
                "shown", lang);
    return LRV_OK;
}

void vg_machine_open(const struct lrv_hal *hal, const struct lrv_run_cfg *cfg)
{
    struct lrv_video_cfg video;
    const struct lrv_pack_entry *e;

    if (vg_open_pack(hal, cfg) != LRV_OK)
        lrv_fatal(hal, "cannot open the game pack (make pack; docs/game-data.md)");

    memset(&video, 0, sizeof video);
    video.mode = lrv_pc98_video_mode;
    video.title = vg.profile.base.title;
    video.fullscreen = cfg->fullscreen;
    video.scale_mode = cfg->scale_mode;
    video.host_mode = cfg->host_mode;
    if (hal->video_open(&video) != LRV_OK)
        lrv_fatal(hal, "cannot open the display");
    /* graphics pages 0 and 1, and buffer 12 (the original's memory planes, 0BA1:0046) */
    if (lrv_screen_init(&vg.screen, hal, &video.mode, 2, 1, LRV_MEM_ANY) != LRV_OK)
        lrv_fatal(hal, "out of memory (the screen)");

    lrv_sys_init(&vg.sys, hal, video.mode.w, video.mode.h);
    vg.sys.cpu_per_frame = (uint32_t)vg.profile.cpu_per_frame;
    lrv_sys_set_present(&vg.sys, lrv_screen_present_hook, &vg.screen);
    vg_snd_open(0);                     /* the board and the driver, as GAME.BAT set them up */

    e = lrv_pack_find(&vg.pak, vg.profile.library, VG_PT_LIBRARY);
    if (!e)
        lrv_fatal(hal, "the pack has no picture library %s", vg.profile.library);
    if (gf_lib_open(&vg.lib, hal, &vg.pak, e) != LRV_OK)
        lrv_fatal(hal, "%s is not a picture library", vg.profile.library);
    vg_gfx_load_builtin();
    vg_text_load_fonts();
    vg_bi_load();
    vg_timer_install();
    /* the input devices are opened by the game (run_game), after the console's question */
}

void vg_machine_close(void)
{
    vg_input_term();
    vg_txb_free();
    vg_bi_free();
    vg_text_free_fonts();
    vg_timer_remove();
    vg_snd_close();
    gf_lib_close(&vg.lib);
    vg.hal->video_close();
    lrv_screen_free(&vg.screen);
    lrv_pack_close(&vg.pak);
}

int vg_run(const struct lrv_hal *hal, const struct lrv_run_cfg *cfg,
           const struct vg_options *opt)
{
    int rc;

    memset(&vg, 0, sizeof vg);
    vg.opt = *opt;
    vg_machine_open(hal, cfg);
    if (vg.opt.view) {
        rc = run_viewer();
    } else {
        rc = run_game();
    }
    lrv_sys_trace(&vg.sys, LRV_TR_QUIT, 0, 0, rc, 0, 0, 0);
    vg_machine_close();
    return rc;
}
