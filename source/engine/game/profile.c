/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The game profile: what makes the generic engine run one particular game. It is the pack's
 * "profile" entry (tools/mkpack.py writes it from tools/games.py), key=value lines in UTF-8,
 * parsed by lrvne's profile parser (lrvne/profile.h) over the table below:
 *   id=...               the game's short name: names its saves' directory
 *   title=...            window title
 *   lang=ja              the language of the original text
 *   scenario=NAME        the scenario the original's command line names (GAME.BAT)
 *   library=NAME         ... and the picture library
 *   sound=pmd26k|none    the sound setup (GAME.BAT's choice: PMD on a 26K board, or none)
 *   pmd=OPTIONS          the driver's command line in GAME.BAT for that setup: /DFn /DSn
 *                        (volume-down), /Mn (music buffer, KB), /F; others are ignored
 *   mouse=ask|on|off     the start-up question whether to use the mouse: asked, or answered
 *   cpu_per_frame=N      the reference machine: 80286 clocks per VSYNC (re-tools/m286.py;
 *                        0: what runs at CPU speed takes no time) */
#include <string.h>
#include "vg.h"

static const struct lrv_pfield fields[] = {
    LRV_PROFILE_BASE_FIELDS(struct vg_profile, base),
    LRV_PF_STR("scenario", struct vg_profile, scenario),
    LRV_PF_STR("library", struct vg_profile, library),
    LRV_PF_STR("sound", struct vg_profile, sound),
    LRV_PF_STR("pmd", struct vg_profile, pmd),
    LRV_PF_STR("mouse", struct vg_profile, mouse),
    LRV_PF_INT("cpu_per_frame", struct vg_profile, cpu_per_frame, 0, 100000000)
};

int vg_profile_load(struct vg_profile *p, const struct lrv_pack *pk)
{
    memset(p, 0, sizeof *p);
    strcpy(p->base.title, "vangel");
    strcpy(p->scenario, "CMD00.SCB");
    strcpy(p->library, "GDATA.LIB");
    strcpy(p->sound, "pmd26k");
    strcpy(p->pmd, "/DF5 /K /M8 /V0 /E0");
    strcpy(p->mouse, "ask");
    return lrv_profile_load(pk, fields, (int)(sizeof fields / sizeof fields[0]), p);
}
