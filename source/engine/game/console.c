/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Built-in 0 INIT, sys_init (0504:0004): before the scenario loads, on the DOS console, the
 * question whether to use the mouse (docs/re/platform.md §3.1):
 *     マウスを使用しますか?[Y/N]
 * keys read through the keyboard BIOS (INT 18h AH=03h, AH=00h; 0504:0B7E) until Y, y or ﾝ
 * (yes) or N, n or ﾐ (no); then マウスを使用します / マウスを使用しません and
 * プログラムのロード中です.... The answer clears or keeps the mouse's bit of the device mask.
 *
 * The console is the PC-98's text screen, which the game's graphics turn off (gfx_mode,
 * graphics.md §8). Here it is drawn into graphics page 0 as 80x25 cells of 8x16 in white with
 * the kanji-ROM stand-in (the pack's font16 / font8), and the graphics start clears it. The
 * profile's mouse=on|off answers the question without showing it (lrvne-fit.md). A
 * translation (con.*) is printed in its place, between the original's line controls. */
#include <string.h>
#include "lrvne/sjis.h"
#include "lrvne/utf8.h"
#include "vg.h"

/* DS:01E4, DS:0203, DS:021A, DS:0233 (Shift-JIS) */
static const char s_ask[] = "\n\r\x83\x7d\x83\x45\x83\x58\x82\xf0\x8e\x67\x97\x70\x82\xb5"
                            "\x82\xdc\x82\xb7\x82\xa9?[Y/N]  ";
static const char s_yes[] = "\n\r\x83\x7d\x83\x45\x83\x58\x82\xf0\x8e\x67\x97\x70\x82\xb5"
                            "\x82\xdc\x82\xb7\n\r";
static const char s_no[] = "\n\r\x83\x7d\x83\x45\x83\x58\x82\xf0\x8e\x67\x97\x70\x82\xb5"
                           "\x82\xdc\x82\xb9\x82\xf1\n\r";
static const char s_loading[] = "\x83\x76\x83\x8d\x83\x4f\x83\x89\x83\x80\x82\xcc\x83\x8d"
                                "\x81\x5b\x83\x68\x92\x86\x82\xc5\x82\xb7...";

static int con_x, con_y;

static void con_glyph(const uint8_t *g, int wbytes)
{
    struct lrv_surface *pg = lrv_screen_access(&vg.screen);
    struct lrv_rect dirty;
    lrv_rect_clear(&dirty);
    lrv_glyph_blit(pg, con_x, con_y * 16, g, wbytes, 16, 15, 0, 15, &dirty);
    lrv_screen_mark_surface(&vg.screen, pg, &dirty);
}

/* INT 21h AH=09h, the text up to the "$" dos_print appends */
static void con_print(const char *s)
{
    const uint8_t *p = (const uint8_t *)s;
    while (*p) {
        if (*p == '\n') {
            if (++con_y > 24)
                con_y = 24;
            p++;
            continue;
        }
        if (*p == '\r') {
            con_x = 0;
            p++;
            continue;
        }
        if (con_x > 79) {
            con_x = 0;
            if (++con_y > 24)
                con_y = 24;
        }
        if (lrv_sjis_is_lead(*p) && p[1]) {
            uint8_t g[32];
            lrv_font_rom_glyph(&vg.text.font16, &vg.text.font8, lrv_sjis_to_jis(p[0], p[1]), g);
            con_glyph(g, 2);
            con_x += 2;
            p += 2;
        } else {
            const uint8_t *g = lrv_font_glyph(&vg.text.font8, *p);
            static const uint8_t blank[16];
            con_glyph(g ? g : blank, 1);
            con_x++;
            p++;
        }
    }
}

/* a translation (UTF-8, the language's glyphs, as the console's: not emboldened) */
static void con_utf8(const uint8_t *s)
{
    uint32_t i = 0;
    while (s[i]) {
        uint16_t g[16];
        uint8_t b[32];
        uint32_t cp;
        int w, r;
        i += (uint32_t)lrv_utf8_decode(s + i, &cp);
        if (cp == '\n') {
            con_print("\n\r");
            continue;
        }
        if (cp < 0x20)
            continue;
        w = vg_lang_glyph(cp, g);
        if (con_x + w > 80) {
            con_x = 0;
            if (++con_y > 24)
                con_y = 24;
        }
        for (r = 0; r < 16; r++) {
            if (w == 2) {
                b[2 * r] = (uint8_t)(g[r] >> 8);
                b[2 * r + 1] = (uint8_t)g[r];
            } else {
                b[r] = (uint8_t)g[r];
            }
        }
        con_glyph(b, w);
        con_x += w;
    }
}

/* a string of the console, or its translation between the original's line controls */
static void con_say(const char *orig, const char *key, const char *pre, const char *post)
{
    const uint8_t *t = vg_lang_get("%s", key);
    if (!t) {
        con_print(orig);
        return;
    }
    con_print(pre);
    vg_text_tl(VG_TL_CONSOLE, 0, con_y, con_x, t, (uint32_t)strlen((const char *)t));
    con_utf8(t);
    con_print(post);
}

int vg_console_ask(int shown)
{
    int yes = -1;

    if (lrv_name_eq(vg.profile.mouse, "on"))
        return 1;
    if (lrv_name_eq(vg.profile.mouse, "off"))
        return 0;
    con_x = con_y = 0;
    if (shown) {
        lrv_screen_set_colour(&vg.screen, 15, 15, 15, 15);
        con_say(s_ask, "con.ask", "\n\r", "  ");
    }
    lrv_sys_key_flush(&vg.sys);
    lrv_sys_trace(&vg.sys, LRV_TR_WAIT, 0, 0, VG_WAIT_KEY, 0, 0, 0);
    while (yes < 0) {
        struct lrv_keypress k;
        lrv_sys_frame_wait(&vg.sys);
        if (lrv_sys_quitting(&vg.sys)) {
            lrv_sys_trace(&vg.sys, LRV_TR_WAIT, 0, 0, VG_WAIT_KEY, 1, VG_LEAVE_QUIT, 0);
            return 0;
        }
        while (yes < 0 && lrv_sys_key_read(&vg.sys, &k)) {
            if (k.key == LRV_K_Y)
                yes = 1;
            else if (k.key == LRV_K_N)
                yes = 0;
        }
    }
    lrv_sys_trace(&vg.sys, LRV_TR_WAIT, 0, 0, VG_WAIT_KEY, 1, VG_LEAVE_KEY, 0);
    if (shown) {
        if (yes)
            con_say(s_yes, "con.yes", "\n\r", "\n\r");
        else
            con_say(s_no, "con.no", "\n\r", "\n\r");
        con_say(s_loading, "con.loading", "", "");
        lrv_sys_present_now(&vg.sys);
    }
    return yes;
}

int vg_console_init(void)
{
    return vg_console_ask(1);
}
