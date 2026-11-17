/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The built-in sequences of M.EXE (segment 0504; docs/re/platform.md §5, text.md §5), which
 * statement 25h n calls: 0 INIT (the console's mouse question), 1 OPENING (the prologue's
 * pages), 2 ENDING and 5 ENDING2 (the staff roll), 3 ANNOUNCE (the text file announce.txt),
 * 4 MUSMODE (the music mode). They draw straight into VRAM with the glyph routines of segment
 * 05C3 (gfx/glyph.c).
 *
 * Their tables, strings and palettes are M.EXE's, from the pack (tools/mexe.py builtin). A
 * sequence the player skips sets the result flag (vg.text.skip), which 25h hands to v1.
 *
 * Time, as everywhere in the engine: a wait loop's turn that finds nothing ends with a frame;
 * the drawing itself takes none (the 80286 clocks of the glyph routines, of the staff roll's
 * colour change and outline, are not charged). */
#ifndef VG_BI_BI_H
#define VG_BI_BI_H

#include <stdint.h>
#include "gfx/gfx.h"

#define VG_BI_PROLOGUE_MAX  64          /* records of the prologue's table (27 in the game) */
#define VG_BI_STAFF_MAX     128         /* lines of the staff roll (44) */
#define VG_BI_SONGS_MAX     64          /* songs of the music mode (18) */
#define VG_BI_RECTS         6

/* a string of the pack's tables: NULL ends a table, as the original's NULL pointer */
struct vg_bi_row { int row; const uint8_t *s; };
struct vg_bi_song { const uint8_t *file, *title; };

enum vg_bi_str {
    VG_BI_ANNOUNCE_FILE,                /* "announce.txt" DS:0254 */
    VG_BI_ANNOUNCE_MISSING,             /* 0ABB:0000 */
    VG_BI_ANNOUNCE_PROMPT,              /* 0ABB:0023, after a page */
    VG_BI_ANNOUNCE_LAST,                /* 0ABB:0046, at the end */
    VG_BI_MUSIC_HEADING,                /* 0ABB:06B6 */
    VG_BI_MUSIC_HELP,                   /* 0ABB:06DD */
    VG_BI_STRS
};

/* the music layer as the music mode calls it (a test replaces them) */
struct vg_bi_mus {
    int (*init)(void);                  /* 04E4:0004 */
    int (*play)(const char *name, int vol);     /* 04E4:0034 */
    int (*fade_stop)(int t);            /* 04E4:00F0 */
};

struct vg_bi {
    uint8_t *blob[4];                   /* the pack's entries the pointers below point into */
    uint32_t blob_size[4];
    struct vg_bi_row prologue[VG_BI_PROLOGUE_MAX];
    const uint8_t *staff[VG_BI_STAFF_MAX];
    struct vg_bi_song song[VG_BI_SONGS_MAX];
    const uint8_t *str[VG_BI_STRS];
    struct vg_rect_op rect[VG_BI_RECTS];        /* DS:04CC, 04DE, 04F0, 0502, 0514, 0526 */
    uint8_t pal_prologue[VG_PAL_BYTES];         /* 0ABB:0566 */
    /* ENDING (0) and ENDING2 (1): the working palette, which the fade changes for good (it
     * is M.EXE's data: a second staff roll starts from where the first ended), its target
     * and the roll's palette */
    uint8_t pal_from[2][VG_PAL_BYTES];
    uint8_t pal_to[2][VG_PAL_BYTES];
    uint8_t pal_roll[2][VG_PAL_BYTES];

    /* the prologue's wipe: the steps taken (DS:04CA, never reset) and the VSYNCs a character
     * may have taken by now (DS:17C0) */
    uint16_t wipe_steps, wipe_due;
    /* the music mode: 2 once it found no driver (DS:0682), the row shown selected (DS:0680,
     * -1 = nothing drawn yet), the songs (DS:17C2) */
    int mus_mode, mus_shown, mus_count;

    struct vg_bi_mus mus;
};

/* bi.c */
/* The tables from the pack (at start-up; fatal when missing) and their release. */
void vg_bi_load(void);
void vg_bi_free(void);
/* statement 25h's routine n (0..5) */
void vg_builtin(int n);
/* text80_line (0504:007C): str on the 80-column grid at column col, text row row; attribute
 * E1h white on black, any other inverse */
void vg_bi_line(int col, int row, const uint8_t *s, int attr);
/* input_check (0504:039C): one reading; on a key, the left button or a joystick button, its
 * release step and 1. With wait 1 it polls until there is one (a frame each turn). */
int  vg_bi_input_check(int wait);
/* bi_wait_any (0504:0257): until a key, either mouse button or a joystick button, then its
 * release step; at once when no device is open */
void vg_bi_wait_any(void);

/* the sequences (opening.c, ending.c, announce.c, musmode.c) */
void vg_bi_opening(void);               /* 0504:0295 */
void vg_bi_ending(int which);           /* 0504:0568 (0), 0504:05CA (1) */
void vg_bi_announce(void);              /* 0504:0114 */
void vg_bi_musmode(void);               /* 0504:088E */

#endif
