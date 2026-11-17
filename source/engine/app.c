/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The engine as a backend sees it (lrvne/app.h): its name and version, its own options, how
 * it runs a game, and what its trace events are called. */
#include <string.h>
#include "vg.h"
#include "version.h"

static struct vg_options options;

static const struct lrv_option option_table[] = {
    { "view", LRV_OPT_OPTARG, "PICTURE",
      "browse the library's pictures instead of playing, from PICTURE (e.g. va_main.gf)" }
};

static int on_option(void *ctx, const char *name, const char *arg)
{
    (void)ctx;
    if (!strcmp(name, "view")) {
        options.view = 1;
        options.view_picture = arg;
        return 0;
    }
    return 1;
}

static int run(void *ctx, const struct lrv_hal *hal, const struct lrv_run_cfg *cfg)
{
    (void)ctx;
    return vg_run(hal, cfg, &options);
}

static int wait_is_input(int wait_kind)
{
    return wait_kind != VG_WAIT_TICKS;
}

static const char *const trace_names[] = { VG_TRACE_NAMES };

const struct lrv_app vg_app = {
    .name = VG_NAME,
    .version = VG_VERSION,
    .options = option_table,
    .noptions = (int)(sizeof option_table / sizeof option_table[0]),
    .option = on_option,
    .help = "keys: the PC-98 keyboard; in the picture viewer the cursor keys, Return or Space\n"
            "  step, Esc quits",
    .run = run,
    .trace_names = trace_names,
    .ntrace_names = (int)(sizeof trace_names / sizeof trace_names[0]),
    .wait_is_input = wait_is_input,
    .render_music = vg_render_music
};

int vg_main(int argc, char **argv)
{
    return lrv_app_main(&vg_app, argc, argv);
}
