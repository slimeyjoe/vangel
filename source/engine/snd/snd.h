/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The music: M.EXE's music layer (segment 04E4, the API the interpreter and the music mode
 * call) over its PMD binding (segment 048F, every INT 60h call of the program), and below them
 * the machine's sound: a resident PMD 4.7g on a 26K board, which is lrvne's PMD module
 * (lrvne/pmd.h) on lrvne's music path (lrvne/music.h). docs/re/sound.md §3.
 *
 * The binding reaches the driver through one entry, vg.mus.int60 (AX in, AX out, as the
 * original's int86x does); the engine's is the module, a test puts the stand-in of
 * re-tools/sndcall.py there. The driver's music buffer is the engine's (the original copies the
 * song file into PMD's, whose address AH=06h gives). */
#ifndef VG_SND_SND_H
#define VG_SND_SND_H

#include <stdint.h>
#include "lrvne/app.h"
#include "lrvne/music.h"
#include "lrvne/pmd.h"

/* g_pmd_state (DS:17A6), what mus_state returns */
#define VG_MUS_PLAYING  0x0A
#define VG_MUS_IDLE     0x0B
#define VG_MUS_NODRIVER 0x0C

#define VG_MUS_NAME 19                  /* g_mus_name, char[19] */

/* the sound setups (the profile's sound=) */
enum vg_sound { VG_SOUND_NONE = 0, VG_SOUND_PMD26K };

struct vg_mus {
    /* ---- the machine ---- */
    int setup;                          /* enum vg_sound */
    int open;                           /* the music path is there (vg_snd_open) */
    int hooked;                         /* its pump is a hook of the frame (not offline) */
    struct lrv_music music;
    struct lrv_pmd pmd;
    uint8_t *buf;                       /* PMD's music buffer (/Mn KB): the song file's bytes */
    uint32_t buf_size;
    uint8_t *ssgtab;                    /* PMD.COM's SSG effects: the drums of part K */
    uint32_t ssgtab_size;
    int resident;                       /* "PMD" at the INT 60h vector */
    int voldown_fm, voldown_ssg;        /* /DFn /DSn */
    int keep_after_fade;                /* /F */

    /* the driver's entry: AX in, AX out (the real driver, or a test's stand-in) */
    uint16_t (*int60)(uint16_t ax);
    /* tests: each file the binding tries to open, and whether it is there */
    void (*on_open)(const char *name, int found);

    /* ---- 048F, the binding ---- */
    int present;                        /* g_pmd_present DS:01B2 */
    int state;                          /* g_pmd_state DS:17A6 */
    int board;                          /* g_pmd_board DS:17A4: AH=09h's AL, -1 for FFh */
    uint32_t song_size;                 /* the bytes the last song put into buf */
    uint8_t in_al;                      /* AL of g_pmd_inregs DS:178E, kept between calls */

    /* ---- 04E4, the API ---- */
    int ok;                             /* g_mus_ok DS:01CC */
    char name[VG_MUS_NAME + 1];         /* g_mus_name DS:01D0, initially "none" */
    int16_t vol;                        /* g_mus_vol DS:01CE, percent */
};

/* The machine's sound (vg_machine_open / _close): with sound=pmd26k the music path and the
 * driver as GAME.BAT installs it; with none nothing. Offline: no device, the caller renders
 * (vg_render_music). */
void vg_snd_open(int offline);
void vg_snd_close(void);

/* the real driver's INT 60h (the default vg.mus.int60) */
uint16_t vg_snd_int60(uint16_t ax);

/* 04E4, as the original: */
int  vg_mus_init(void);                         /* 04E4:0004: 1 when a driver is there */
void vg_mus_term(void);                         /* 04E4:0021 */
int  vg_mus_play(const char *name, int vol);    /* 04E4:0034: the state, or 0 / 1 */
int  vg_mus_stop(void);                         /* 04E4:00A7 */
void vg_mus_set_vol(int vol);                   /* 04E4:00C9 */
int  vg_mus_fade_stop(int t);                   /* 04E4:00F0: blocking, t in 1/100 s */
int  vg_mus_state(void);                        /* 04E4:01D8 */
int  vg_mus_measure(void);                      /* 04E4:01E9: statement 35h */

/* app.c's render_music: song `name` for `seconds` through the game's sound path, offline */
int vg_render_music(void *ctx, const struct lrv_hal *hal, const struct lrv_run_cfg *cfg,
                    const char *name, double seconds, uint32_t *rate,
                    void (*sink)(void *sctx, const int16_t *pcm, int frames), void *sctx);

#endif
