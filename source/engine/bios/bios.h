/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The input of M.EXE (docs/re/platform.md §3): its own keyboard interrupt handler, the MSZ
 * mouse driver through INT 33h, the joystick stub, and the device layer (segment 043A) that
 * polls them for the rest of the program.
 *
 * The machine below it is lrvne's frame: one input poll per VSYNC. The keyboard is modelled
 * as the PC-98's: every poll's key changes become the scan codes the keyboard would have sent
 * (breaks first, then makes), and each goes through the original's INT 09h handler, a latch
 * of the last code. The mouse driver answers from the pointer lrvne keeps (absolute, 640x400)
 * and the buttons held at the poll. What the original does between two VSYNCs it does here
 * at one instant: its busy loops that wait for the input are loops over frames. */
#ifndef VG_BIOS_BIOS_H
#define VG_BIOS_BIOS_H

#include <stdint.h>
#include "lrvne/pc98.h"

/* the devices, bits of the masks DS:0110 and DS:0112 */
#define VG_DEV_KBD   1
#define VG_DEV_MOUSE 2
#define VG_DEV_JOY   4

/* kbd_poll's codes (0401:0317); any other key is an event with code 0 */
enum vg_key_code {
    VG_KEY_ESC = 0x100, VG_KEY_RETURN, VG_KEY_SPACE, VG_KEY_UP, VG_KEY_LEFT, VG_KEY_RIGHT,
    VG_KEY_DOWN
};

/* input_poll's record (26 bytes in the original): per device "changed since its previous
 * reading", then the reading */
struct vg_reading_joy   { int changed, a, b; };
struct vg_reading_kbd   { int changed, event, code; };
struct vg_reading_mouse { int changed, x, y, right, left, zero; };
struct vg_poll {
    struct vg_reading_joy joy;          /* +2 */
    struct vg_reading_kbd kbd;          /* +8 */
    struct vg_reading_mouse mouse;      /* +0Eh */
};

struct vg_input {
    int ready;                          /* DS:010E */
    unsigned want;                      /* DS:0110: the devices to open */
    unsigned open;                      /* DS:0112: the devices that opened */
    /* the INT 09h latch */
    uint8_t kbd_scan;                   /* DS:00FE: the last scan code & 7Fh */
    uint8_t kbd_make;                   /* DS:00FF: 1 = a key event not read yet */
    /* the keyboard model: the scan-code bitmap of the poll fed last, and which poll that was */
    uint8_t kbd_down[LRV_PC98_KEYMAP_BYTES];
    uint32_t kbd_fed;                   /* frame number of the poll fed last + 1 */
    /* the previous readings (DS:1772, DS:177E, DS:1784) */
    struct vg_reading_mouse mouse_last;
    struct vg_reading_joy joy_last;
    struct vg_reading_kbd kbd_last;
    /* the pointer: shown (DS:00F6) and locked (DS:00F8) */
    int ptr_shown, ptr_locked;
    int ptr_overlay;                    /* the overlay is installed */
    /* tests: the scan codes come from the test (vg_kbd_isr), not from lrvne's keys */
    int kbd_external;
    /* tests: every INT 33h show (1) / hide (0) */
    void (*on_pointer)(void *ctx, int shown);
    void *on_pointer_ctx;
};

/* input.c */
/* input_init (043A:0008): opens the devices of `want` (VG_DEV_*); 1, or 0 when none opened.
 * input_term (043A:0066) closes them. */
int  vg_input_init(unsigned want);
void vg_input_term(void);
/* INT 09h (0401:0228) for one byte from the keyboard: a scan code, bit 7 set for a release */
void vg_kbd_isr(uint8_t data);
/* input_poll (043A:01DA): every open device into *p; 1 when any device is open */
int  vg_input_poll(struct vg_poll *p);
/* input_wait_release (043A:0236): for the devices in mask, reads until the event is gone
 * (keyboard), the left button is up (mouse; one frame per reading), the joystick is still */
void vg_input_release(unsigned mask);
/* The frame of a wait loop: lrv_sys_frame_wait. 1 when the player quit or reset meanwhile:
 * the loop must give up (the original has no such exit; the engine unwinds). */
int  vg_frame(void);
/* The trace events of a wait (LRV_TR_WAIT, kind enum vg_wait_kind): the test automation's
 * stops and autoplay's KEY:wait. */
void vg_wait_begin(int kind);
void vg_wait_end(int kind);

/* mouse.c: the MSZ driver and the pointer */
/* mouse_open (0401:001A): resets the driver, hides the pointer; 1 when there is a driver */
int  vg_mouse_open(void);
void vg_mouse_close(void);
/* mouse_poll (0401:008A): shows the pointer (unless locked), reads it into *m */
void vg_mouse_read(struct vg_reading_mouse *m);
/* mouse_show (0401:00F6): 1 shows, 0 hides, unless locked; only on a change */
void vg_mouse_show_raw(int show);
/* 043A:0295 / 043A:02A5: the same when the mouse is open */
void vg_mouse_show(void);
void vg_mouse_hide(void);
/* mouse_lock (043A:02B5 -> 0401:0154): lock 1 locks the pointer's state after applying show
 * (1 shown, 0 hidden); lock 0 unlocks it as it is. Statement 37h. */
void vg_mouse_lock(int lock, int show);

#endif
