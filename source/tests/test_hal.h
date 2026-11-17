/* SPDX-License-Identifier: GPL-3.0-or-later */
/* A HAL for the test programs, after lrvne's tests/test_hal.h: no display, no audio device, no
 * real time, malloc, messages on stderr. Unlike lrvne's own tests these run on a game's packs,
 * so the packs and the storage are files: lrvne's pack and storage functions on plain files
 * (backends/common/paths.h), told where they are instead of searching. Every frame presented
 * is audited: what changed on the page must lie in the frame's dirty rectangle. A test replaces the
 * members it wants to observe (trace, input_poll, frame_wait, ...). */
#ifndef VG_TESTS_TEST_HAL_H
#define VG_TESTS_TEST_HAL_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lrvne/hal.h"
#include "paths.h"
#include "shot.h"

static uint32_t th_frames;              /* frame_wait calls */

static int th_video_open(const struct lrv_video_cfg *cfg) { (void)cfg; return 0; }
static void th_video_close(void) {}

/* No display, but every frame's dirty rectangle is audited (lrvne's shot.h): a change of the
 * page that was not reported would be missing on a real display, and fails the test here. */
static void th_video_present(const struct lrv_frame *frame)
{
    static struct lrv_shot shown;
    int col = 0, line = 0;
    if (lrv_shot_audit(&shown, frame, &col, &line) == 1) {
        fprintf(stderr, "present: the page changed outside its dirty rectangle (column %d, "
                "line %d)\n", col, line);
        exit(1);
    }
}

static void th_frame_wait(void) { th_frames++; }
static void th_input_poll(struct lrv_input *in) { (void)in; }   /* nothing is pressed */
static void th_input_flush(void) {}
static void *th_alloc(size_t n, unsigned flags) { (void)flags; return malloc(n); }
static void th_free(void *p, size_t n) { (void)n; free(p); }

static void th_log(int level, const char *msg)
{
    if (level >= LRV_LOG_WARN)
        fprintf(stderr, "%s\n", msg);
}

static void th_fatal(const char *msg)
{
    fprintf(stderr, "fatal: %s\n", msg);
    exit(1);
}

/* Fills *hal. `pak` is the main pack's file, `voice_pak` the voice pack's or NULL, `storage`
 * the directory of the records or NULL (the current directory). */
static inline void th_hal(struct lrv_hal *hal, const char *pak, const char *voice_pak,
                          const char *storage)
{
    static struct lrv_paths_cfg paths;

    memset(&paths, 0, sizeof paths);
    paths.app_name = "test";
    paths.pak = pak;
    paths.voice_pak = voice_pak;
    paths.voice_explicit = 1;
    paths.storage = storage;
    paths.storage_default = ".";
    lrv_paths_init(&paths);

    memset(hal, 0, sizeof *hal);
    hal->video_open = th_video_open;
    hal->video_close = th_video_close;
    hal->video_present = th_video_present;
    hal->frame_wait = th_frame_wait;
    hal->input_poll = th_input_poll;
    hal->input_flush = th_input_flush;
    hal->storage_open = lrv_paths_storage_open;
    hal->storage_read = lrv_paths_storage_read;
    hal->storage_write = lrv_paths_storage_write;
    hal->pack_open = lrv_paths_pack_open;
    hal->pack_read = lrv_paths_pack_read;
    hal->pack_close = lrv_paths_pack_close;
    hal->mem_alloc = th_alloc;
    hal->mem_free = th_free;
    hal->log = th_log;
    hal->fatal = th_fatal;
}

#endif
