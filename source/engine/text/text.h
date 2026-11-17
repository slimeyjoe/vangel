/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The text of M.EXE (docs/re/text.md): the message file "CRTX" (txb.c), the message window
 * and its glyphs (win.c), statement 19h's page loop and waits (msg.c), and statement 24h's
 * menus (menu.c).
 *
 * The window is drawn as the original draws it: a page is composed in a work buffer over the
 * window's background (the save buffer, gfx.h) and copied to VRAM at once. Full-width
 * characters come from the kanji ROM, which the pack's font16 / font8 stand in for (lrvne's
 * lrv_font_rom_glyph), half-width ones from the game's own 8x16 font (the pack's ank8). */
#ifndef VG_TEXT_TEXT_H
#define VG_TEXT_TEXT_H

#include <stdint.h>
#include "lrvne/font.h"

#define VG_TXB_MAX      1000            /* messages the loader accepts (0724:00A4) */
#define VG_TXB_BUF      0x2000          /* the message buffer DS:108E */
#define VG_MSG_LINE     79              /* txb_line's output limit in msg_show */
#define VG_WIN_ROWS     4
#define VG_WIN_COLS     68              /* half-width cells: columns 0..43h */
#define VG_MENU_MAX     4

/* the message file (txb.c) */
struct vg_txb {
    uint8_t *file;                      /* the whole file from the pack */
    uint32_t size;
    int count;                          /* messages indexed (SCB tag 7) */
    uint32_t *off;                      /* [1..count]: file offset of the message */
    uint16_t *len;                      /* [1..count]: its length, the 1Ah included */
    uint8_t dict[180];                  /* the 90 two-byte characters of 0B85:0000 */
    uint8_t buf[VG_TXB_BUF];            /* the message read last, decoded */
};

/* a menu of the scenario's table T44: 1..4 Shift-JIS strings */
struct vg_menu {
    int number;                         /* statement 24h's operand (1-based): its key */
    int n;
    const uint8_t *item[VG_MENU_MAX];
};

/* a choice's hit rectangle, inclusive (menu_choice 02BE:020E) */
struct vg_menu_rect { int x0, x1, y0, y1; };

/* test events (vg_text.on_event) */
enum vg_text_event {
    VG_TEV_SHOW = 1,                    /* win_show: a page or a menu appeared */
    VG_TEV_ICON_ON,                     /* the page-wait icon drawn */
    VG_TEV_ICON_OFF,                    /* ... and its cell restored */
    VG_TEV_RESTORE,                     /* win_restore_screen: the text erased */
    VG_TEV_INVERT,                      /* rect_invert, arg = its first line */
    VG_TEV_PAGE                         /* a page shown, before its wait: arg = the wait's
                                         * mode << 16 | the cells (bytes) it counts */
};

/* the language's text (lang.c; docs/translation.md): the pack's string table "text" (VGTX) of
 * the selected language, its full-width glyphs "wide16" and the half-width "latin8", both
 * keyed by code point. Not active for the original's language, which has no table. */
struct vg_lang {
    uint8_t *tab;
    uint32_t size, count;
    struct lrv_font latin8, wide16;
};

/* the layout of a translated text (layout.c): its lines, where each is drawn */
#define VG_LAY_MAX 256                  /* LRV_REFLOW_MAX_LINES */
struct vg_lay_line {
    const uint8_t *s;                   /* UTF-8, n bytes */
    uint32_t n;
    int page, row, col, cols;
};
struct vg_lay {
    int nlines, npages;
    struct vg_lay_line line[VG_LAY_MAX];
};

struct vg_text {
    struct vg_txb txb;
    struct lrv_font font16, font8;      /* the kanji ROM's stand-in */
    struct lrv_font ank8;               /* the game's half-width font */
    struct vg_lang lang;
    uint8_t skip;                       /* the skip flag, byte 0BA1:0000 */
    /* op 24h's memory: the statement of the last menu and its result (DS:00C0, DS:00C4) */
    long menu_last;
    int menu_choice;
    /* tests */
    void (*on_event)(void *ctx, int event, int arg);
    void *on_event_ctx;
    /* a line drawn into the window: its row, column and bytes (utf8 1: a translation's) */
    void (*on_line)(void *ctx, int row, int col, const uint8_t *s, uint32_t n, int utf8);
    /* a translated line of a built-in or the console (enum vg_tl_where), page of its text */
    void (*on_text)(void *ctx, int where, int page, int row, int col, const uint8_t *s,
                    uint32_t n);
};

enum vg_tl_where {
    VG_TL_PROLOGUE = 1,                 /* row: of the page; col: the byte column x */
    VG_TL_STAFF,                        /* row, col: of the roll's double-size grid */
    VG_TL_ANNOUNCE,                     /* row, col: of the 80-column grid */
    VG_TL_LINE,                         /* an 80-column line (the music mode, the prompts) */
    VG_TL_CONSOLE                       /* a console string */
};
/* the hook of a translated line, if a test set one */
void vg_text_tl(int where, int page, int row, int col, const uint8_t *s, uint32_t n);

/* lang.c */
/* The language's table and fonts, after the pack's language is selected (vg_open_pack) and
 * the fonts are loaded; nothing when the language has no table. A damaged one is logged and
 * the original text is shown. */
void vg_lang_init(void);
void vg_lang_free(void);
int  vg_lang_active(void);
/* the translation of key (printf-style), NULL when there is none */
const uint8_t *vg_lang_get(const char *fmt, ...) LRV_PRINTF(1, 2);
/* the translation of a speaker's name (the bytes of a 13h line after the code): the table
 * always has every name in a language that is active (tools/vgtext.py) */
const uint8_t *vg_lang_name(const uint8_t *name);
/* columns of a code point (an lrv_cols_fn): 0 below U+0020, 1 when latin8 has it, else 2 */
int  vg_lang_cols(void *ctx, uint32_t cp);
/* the glyph of a code point, not emboldened: returns its columns (1: rows of 8 bits, 2: of 16;
 * the msb leftmost) and fills rows[16]; a character without one is blank */
int  vg_lang_glyph(uint32_t cp, uint16_t rows[16]);
/* the columns of n bytes of UTF-8 (0 = up to the NUL) */
int  vg_lang_width(const uint8_t *s, uint32_t n);

/* layout.c: lrvne's reflow of a translation, the layout every kind of text gets
 * (docs/translation.md). The lines point into text, which must stay. */
void vg_lay(const uint8_t *text, int width, int height, int last, int first_line, int first_col,
            int indent, int keep_indent, struct vg_lay *out);
/* a single-line item cut at width columns: its bytes; *cols its columns */
uint32_t vg_lay_fit(const uint8_t *text, int width, int *cols);

/* txb.c */
/* txb_load (0724:0018): the message file `name` from the pack, `count` messages (the
 * scenario's tag 7). 1, or 0 when it is missing or not a message file of that many messages. */
int  vg_txb_load(const char *name, int count);
void vg_txb_free(void);
/* txb_read_msg (0724:0186): message n (1..count) and the 10 bytes after it into txb.buf */
void vg_txb_read(int n);
/* txb_line (0724:0206): the line at buf[pos] expanded into out (at most max bytes, two more
 * if a two-byte character ends it, then 00h); returns the source length + 1 */
int  vg_txb_line(unsigned pos, uint8_t *out, int max);

/* win.c */
/* INT 18h AH=14h for the Shift-JIS character lead, trail (sjis_to_jis 0A96:0002 first): the
 * kanji ROM's 16 x 16 pattern, two bytes a row */
void vg_kanji_rom(unsigned lead, unsigned trail, uint8_t g[32]);
/* The fonts from the pack (at start-up; fatal when missing). */
void vg_text_load_fonts(void);
void vg_text_free_fonts(void);
/* win_clear (02BE:00CC): the work buffer := the window's background */
void vg_win_clear(void);
/* win_show (02BE:00BC): the work buffer to VRAM */
void vg_win_show(void);
/* win_line (02BE:015F): string s into the work buffer at row 0..3, column 0..67; 1, or 0
 * when the position is refused */
int  vg_win_line(const uint8_t *s, int row, int col);
/* the same for n bytes of a translation (UTF-8, lang.c's glyphs), cut where the row ends */
int  vg_win_utf8(const uint8_t *s, uint32_t n, int row, int col);
/* msg_icon (0315:0EAD): 1 draws the page-wait icon into VRAM, 0 restores its cell from the
 * work buffer */
void vg_icon(int on);
/* rect_invert (02BE:0263): all four planes of a rectangle of VRAM inverted */
void vg_rect_invert(const struct vg_menu_rect *r);
/* menu_choice (02BE:020E): choice i drawn at row i and its rectangle; 1, or 0 when refused */
int  vg_menu_choice(const uint8_t *s, struct vg_menu_rect *r, int i);
/* the same for a translated choice t (cut at the row's end): the original's place, or centred
 * on the original's text when the original is centred with leading spaces (vg_menu_col: the
 * column of a translation `cols` wide in place of the original orig) */
int  vg_menu_choice_tl(const uint8_t *orig, const uint8_t *t, struct vg_menu_rect *r, int i);
int  vg_menu_col(const uint8_t *orig, int cols);
/* the event to the test's hook */
void vg_text_event(int event, int arg);

/* msg.c */
/* op 19h (001E:0965): the skip flag cleared, message n shown (msg_show 0315:07FC); the
 * result v1: 1 when the player cut a timed page short (the flag), else 0 */
int  vg_op19(int n);
/* msg_show (0315:07FC) itself; returns 1 */
int  vg_msg_show(int n);
/* what the page loop keeps between messages (a translated passage's buffer), at shutdown */
void vg_msg_free(void);
/* msg_poll (0315:0B7C): an input to go on, then its release step; with block 1 waits for
 * one. 1, or 0 when there was none (or no device). */
int  vg_msg_poll(int block);

/* menu.c */
/* op 24h (001E:0A8D): menu m of statement `stmt` (any number naming the statement: the
 * same statement starts with its last choice); the result v1, the choice 1..n */
int  vg_op24(long stmt, const struct vg_menu *m);

#endif
