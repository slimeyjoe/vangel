/* SPDX-License-Identifier: GPL-3.0-or-later */
/* The music: the machine's sound (a resident PMD.COM on a 26K board, or nothing), M.EXE's PMD
 * binding (segment 048F) and its music layer (segment 04E4). docs/re/sound.md §2-4.
 *
 * The binding is the only part of the original that calls the driver: every INT 60h goes
 * through vg.mus.int60 here as it went through int86x there, so that a test sees the calls the
 * original makes, in order, and answers them as re-tools/sndcall.py's stand-in does. The
 * engine's int60 is the PMD module of lrvne, run by lrvne's music path (the audio thread, or
 * a frame's worth of samples per frame without a device: the measure counter of statement 35h
 * advances as the frames pass). Every call into the module's state is made under the mixer's
 * lock, file reads before it. */
#include <stdio.h>
#include <string.h>
#include "vg.h"
#include "lrvne/sjis.h"

#define QUEUE_SIZE   1024               /* a song start writes some 200 registers */
#define IDLE_RATE    44100              /* the driver's clock without a device */
#define BUF_DEFAULT  16                 /* KB, without /M on the driver's command line */

/* ---- the machine ------------------------------------------------------------------------ */

static void lock(void)
{
    if (vg.mus.open)
        lrv_mixer_lock(&vg.mus.music.mixer);
}

static void unlock(void)
{
    if (vg.mus.open)
        lrv_mixer_unlock(&vg.mus.music.mixer);
}

/* the driver writes to the chip through the music path's queue */
static void chip_write(void *ctx, uint8_t reg, uint8_t val)
{
    (void)ctx;
    lrv_opnq_write(&vg.mus.music.q, reg, val);
}

/* the driver's own options, from its command line in GAME.BAT (the profile's pmd=): /DFn /DSn
 * (FM, SSG volume-down), /Mn (the music buffer, KB), /F (a finished fade does not stop the
 * song); the rest (/K hot keys, /V /E buffers the game does not use) change nothing here */
static void parse_options(const char *s, int *df, int *ds, int *kb, int *keep)
{
    *df = 16;                           /* PMD.COM's defaults */
    *ds = 0;
    *kb = BUF_DEFAULT;
    *keep = 0;
    while (*s) {
        const char *w;
        int *dst = NULL, v = 0;
        while (*s == ' ' || *s == '\t')
            s++;
        if (*s != '/' && *s != '-') {
            while (*s && *s != ' ' && *s != '\t')
                s++;
            continue;
        }
        w = ++s;
        if ((w[0] == 'D' || w[0] == 'd') && (w[1] == 'F' || w[1] == 'f')) {
            dst = df;
            s += 2;
        } else if ((w[0] == 'D' || w[0] == 'd') && (w[1] == 'S' || w[1] == 's')) {
            dst = ds;
            s += 2;
        } else if (w[0] == 'M' || w[0] == 'm') {
            dst = kb;
            s++;
        } else if ((w[0] == 'F' || w[0] == 'f') && (!w[1] || w[1] == ' ' || w[1] == '/')) {
            *keep = 1;
            s++;
        }
        if (dst && *s >= '0' && *s <= '9') {
            while (*s >= '0' && *s <= '9')
                v = v * 10 + (*s++ - '0');
            *dst = v;
        }
        while (*s && *s != ' ' && *s != '\t' && *s != '/')
            s++;
    }
}

/* the music path: driver -> write queue -> OPN core -> mixer -> the HAL's stream */
static int path_open(int offline)
{
    struct lrv_music_cfg mc;
    memset(&mc, 0, sizeof mc);
    lrv_pmd_seq(&vg.mus.pmd, &mc.seq);
    mc.core = vg.cfg.opn_core;
    mc.rate = vg.cfg.audio_rate;
    mc.clock_hz = LRV_OPN_CLOCK_PC98;
    mc.bus_clocks = LRV_OPN_FM_DIV;
    mc.queue_size = QUEUE_SIZE;
    mc.queue_flags = LRV_OPNQ_FLUSH_ON_FULL;
    mc.idle_rate = IDLE_RATE;
    mc.frame_num = 5642;                /* the 56.42 Hz VSYNC */
    mc.frame_den = 100;
    mc.gain_floor = 1;
    mc.flags = offline ? LRV_MUSIC_OFFLINE : 0;
    return lrv_music_open(&vg.mus.music, vg.hal, &mc);
}

void vg_snd_open(int offline)
{
    struct vg_mus *m = &vg.mus;
    const struct lrv_pack_entry *e;
    int kb, v;

    memset(m, 0, sizeof *m);
    m->int60 = vg_snd_int60;
    strcpy(m->name, "none");            /* g_mus_name's initial value */
    if (!strcmp(vg.profile.sound, "pmd26k")) {
        m->setup = VG_SOUND_PMD26K;
    } else {
        if (strcmp(vg.profile.sound, "none"))
            lrv_log(vg.hal, LRV_LOG_WARN, "sound=%s: not a setup of this engine, none taken",
                    vg.profile.sound);
        m->setup = VG_SOUND_NONE;
        return;                         /* GAME.BAT's option 4: no driver at INT 60h */
    }
    parse_options(vg.profile.pmd, &m->voldown_fm, &m->voldown_ssg, &kb, &m->keep_after_fade);
    if (kb < 8)                         /* PMD refuses to install with less */
        lrv_log(vg.hal, LRV_LOG_WARN, "pmd: /M%d is below PMD's minimum of 8 KB", kb);
    m->buf_size = (uint32_t)(kb < 8 ? 8 : kb) * 1024u;
    m->buf = lrv_xalloc(vg.hal, m->buf_size);
    memset(m->buf, 0, m->buf_size);
    e = lrv_pack_find(&vg.pak, "ssgtab", LRV_PT_BLOB);
    if (e)
        m->ssgtab = lrv_pack_load(&vg.pak, e, &m->ssgtab_size);
    if (!m->ssgtab)
        lrv_log(vg.hal, LRV_LOG_WARN, "sound: the pack has no SSG-effect table (the drums)");
    if (path_open(offline) != LRV_OK)
        lrv_fatal(vg.hal, "sound: cannot create the FM chip");
    m->open = 1;
    v = vg.cfg.volume;
    lrv_mixer_set_volume(&m->music.mixer, v < 0 ? 0 : v ? v : 100);

    /* the driver as installed: its options, its tables, its music buffer from the data on
     * (the file's byte 0, the sound-source type, is the byte before) */
    lrv_mixer_lock(&m->music.mixer);
    lrv_pmd_init(&m->pmd, chip_write, NULL, lrv_music_rate(&m->music));
    lrv_pmd_set_options(&m->pmd, m->voldown_fm, m->voldown_ssg, !m->keep_after_fade);
    if (m->ssgtab)
        lrv_pmd_set_ssgtab(&m->pmd, m->ssgtab, m->ssgtab_size);
    lrv_pmd_load_music(&m->pmd, m->buf + 1, m->buf_size - 1);
    lrv_mixer_unlock(&m->music.mixer);
    lrv_music_start(&m->music);
    m->resident = 1;
    if (!offline) {
        if (lrv_sys_add_hook(&vg.sys, LRV_HOOK_PUMP, lrv_mixer_pump, &m->music.mixer) != LRV_OK)
            lrv_fatal(vg.hal, "sound: no room for the mixer's hook");
        m->hooked = 1;
    }
}

void vg_snd_close(void)
{
    struct vg_mus *m = &vg.mus;
    if (m->hooked)
        lrv_sys_remove_hook(&vg.sys, LRV_HOOK_PUMP, lrv_mixer_pump, &m->music.mixer);
    m->hooked = 0;
    if (m->open) {
        lrv_music_close(&m->music);     /* first: the sources are not called after it */
        m->open = 0;
    }
    if (m->ssgtab)
        lrv_pack_free(&vg.pak, m->ssgtab, m->ssgtab_size);
    if (m->buf)
        lrv_free(vg.hal, m->buf, m->buf_size);
    m->ssgtab = NULL;
    m->buf = NULL;
    m->resident = 0;
}

/* INT 60h of PMD.COM 4.7g on a 26K, the functions M.EXE calls (sound.md §3.6) */
uint16_t vg_snd_int60(uint16_t ax)
{
    struct vg_mus *m = &vg.mus;
    unsigned ah = ax >> 8, al = ax & 0xFFu;
    uint16_t r = ax;
    static int warned;

    if (!m->open)
        return ax;
    lrv_mixer_lock(&m->music.mixer);
    switch (ah) {
    case 0x00:                          /* start the song in the buffer */
        lrv_pmd_mstart(&m->pmd);
        break;
    case 0x01:
        lrv_pmd_mstop(&m->pmd);
        break;
    case 0x05:                          /* AX = the measure counter */
        r = (uint16_t)lrv_pmd_measure(&m->pmd);
        break;
    case 0x06:                          /* DS:DX = the music buffer: here m->buf */
        break;
    case 0x09:                          /* AL = the sound source: 0, the YM2203 */
        r = (uint16_t)(ax & 0xFF00u);
        break;
    case 0x17:                          /* AL = PPS: 0, no PPSDRV (setup 0) */
        r = (uint16_t)(ax & 0xFF00u);
        break;
    case 0x19:                          /* the fade-out volume */
        lrv_pmd_set_fadevol(&m->pmd, (uint8_t)al);
        break;
    case 0x22:                          /* AL = the music buffer in KB */
        r = (uint16_t)((ax & 0xFF00u) | ((m->buf_size >> 10) & 0xFFu));
        break;
    default:                            /* the binding makes no other call on this board */
        if (!warned++)
            lrv_log(vg.hal, LRV_LOG_WARN, "pmd: INT 60h AH=%02Xh is not modelled", ah);
        break;
    }
    lrv_mixer_unlock(&m->music.mixer);
    return r;
}

/* ---- 048F: the PMD binding ----------------------------------------------------------------- */

static uint16_t drv(unsigned ax)
{
    return vg.mus.int60((uint16_t)ax);
}

/* 048F:0227: AH=19h with AL = 255 - trunc(2.55 v), computed as the original does: a 16-bit
 * product v * -255, a division toward zero by 100, then dec al */
static void pmd_set_vol(int v)
{
    int16_t p, q;
    if (vg.mus.present != 1)
        return;
    p = (int16_t)(uint16_t)((unsigned)v * 0xFF01u);
    q = (int16_t)(p / 100);
    drv(0x1900u | (uint8_t)(q - 1));
}

/* 048F:01F7 */
static void pmd_stop(void)
{
    if (vg.mus.present != 1 || vg.mus.state != VG_MUS_PLAYING)
        return;
    drv(0x0100);
    vg.mus.state = VG_MUS_IDLE;
}

/* 048F:0008: the driver's signature at the INT 60h vector; then what pmd_query (048F:02B2)
 * asks: the music buffer (AH=06h), its size (22h), the board (09h), PPS (17h); then a stop.
 * pps_probe (048F:0422) looks for PPSDRV's "PMP" at INT 64h, which setup 0 does not load:
 * no call. Only the board is used later. */
static int pmd_init(void)
{
    struct vg_mus *m = &vg.mus;
    uint16_t r;
    if (m->present == 1)
        return 1;
    m->present = 0;
    m->state = VG_MUS_NODRIVER;
    if (!m->resident)
        return 0;
    drv(0x0600);
    drv(0x2200);
    r = drv(0x0900);
    m->board = (r & 0xFFu) == 0xFFu ? -1 : (int)(r & 0xFFu);
    drv(0x1700);
    m->present = 1;
    m->state = VG_MUS_IDLE;
    drv(0x0100);
    return 1;
}

/* 048F:0054 */
static void pmd_term(void)
{
    if (vg.mus.present != 1)
        return;
    if (vg.mus.state == VG_MUS_PLAYING)
        pmd_stop();
    vg.mus.present = 0;
    vg.mus.state = VG_MUS_NODRIVER;
}

/* 048F:04B3: the name up to its first '.' (a '.' after a double-byte character's lead byte is
 * not looked at, inferred: the C library's lead-byte table), then '.' and ext */
static void mk_song_name(char *dst, size_t size, const char *name, const char *ext)
{
    const unsigned char *s = (const unsigned char *)name;
    size_t n = 0;
    int dbcs = 0;
    if (*s) {
        do {
            if (!dbcs) {
                if (lrv_sjis_is_lead(*s)) {
                    dbcs = 1;
                    continue;           /* the lead byte is copied on the next turn */
                }
                if (n + 1 < size)
                    dst[n++] = (char)*s;
                s++;
                if (*s == '.')
                    break;
            } else {
                dbcs = 0;
                if (n + 1 < size)
                    dst[n++] = (char)*s;
                s++;
            }
        } while (*s);
    }
    if (n + 1 < size)
        dst[n++] = '.';
    while (*ext && n + 1 < size)
        dst[n++] = *ext++;
    dst[n] = 0;
}

/* fopen(name.ext, "rb"), or with ext NULL fopen(name): DOS finds the file whatever the case */
static const struct lrv_pack_entry *song_open(const char *name, const char *ext)
{
    char fname[34];                     /* the original's buffer, bp-22h */
    const struct lrv_pack_entry *e;
    if (ext) {
        mk_song_name(fname, sizeof fname, name, ext);
    } else {
        strncpy(fname, name, sizeof fname - 1);
        fname[sizeof fname - 1] = 0;
    }
    e = lrv_pack_find(&vg.pak, fname, VG_PT_SONG);
    if (vg.mus.on_open)
        vg.mus.on_open(fname, e != NULL);
    return e;
}

/* 048F:0376: kind 0 = .m, 1 = .s, 2 = .n; only the OPNA drivers (board 1 PMDB2, 2 PMD86)
 * are told anything: mask part K (.m) or unmask I (.n), then unmask J */
static void pmd_set_masks(int kind)
{
    if (kind == 1 || vg.mus.board < 1 || vg.mus.board > 2)
        return;
    drv(kind == 0 ? 0x1E0Au : 0x1E88u);
    drv(0x1E89u);
}

/* 048F:03DD: fseek(fp, 0), fread(the music buffer, filelength, 1, fp): nothing without a
 * board, nothing read from an empty file. The original checks no size against the buffer; a
 * file longer than it is cut here (the game's longest is 6431 bytes, the buffer 8 KB). */
static int pmd_read_song(const struct lrv_pack_entry *e)
{
    struct vg_mus *m = &vg.mus;
    uint8_t *data;
    uint32_t size, n;
    if (m->board == -1)
        return 0;
    data = lrv_pack_load(&vg.pak, e, &size);
    if (!data)
        return 0;
    if (size == 0) {
        lrv_pack_free(&vg.pak, data, size);
        return 0;
    }
    n = size;
    if (n > m->buf_size) {
        lrv_log(vg.hal, LRV_LOG_WARN, "music: %s (%lu bytes) does not fit the %lu-byte buffer",
                e->name, (unsigned long)size, (unsigned long)m->buf_size);
        n = m->buf_size;
    }
    lock();                             /* the driver is stopped, but the buffer is its */
    memcpy(m->buf, data, n);
    unlock();
    m->song_size = n;
    lrv_pack_free(&vg.pak, data, size);
    return 1;
}

/* 048F:0073: the file .n, else on PMD.COM .s, else .m (the script's extension is not used);
 * stopped first; a missing file leaves silence. On the other drivers the last try opens the
 * name as the script wrote it, not the name made with .m (048F:01AE: fopen is given the
 * argument), so "va_m01.m" is still found. */
static int pmd_load_play(const char *name, int vol)
{
    struct vg_mus *m = &vg.mus;
    const struct lrv_pack_entry *e;
    if (m->present != 1)
        return 0;
    if (m->state == VG_MUS_PLAYING) {
        drv(0x0100);
        m->state = VG_MUS_IDLE;
    }
    if ((e = song_open(name, "n")) != NULL) {
        pmd_set_masks(2);
    } else if (m->board == 0) {
        if ((e = song_open(name, "s")) != NULL) {
            pmd_set_masks(1);
        } else {
            pmd_set_masks(0);
            e = song_open(name, "m");
        }
    } else {
        pmd_set_masks(0);
        e = song_open(name, NULL);
    }
    if (!e || !pmd_read_song(e))
        return 0;
    pmd_set_vol(vol);                   /* overridden by the start, which clears the fade */
    drv(0x0000);
    m->state = VG_MUS_PLAYING;
    lrv_log(vg.hal, LRV_LOG_INFO, "music: %s (%s, %lu bytes)", name, e->name,
            (unsigned long)m->song_size);
    return 1;
}

/* ---- 04E4: the music layer ------------------------------------------------------------------- */

int vg_mus_init(void)
{
    if (vg.mus.ok == 1)
        return 1;
    if (pmd_init() != 1)
        return 0;
    vg.mus.ok = 1;
    return 1;
}

void vg_mus_term(void)
{
    if (vg.mus.ok != 1)
        return;
    pmd_term();
    vg.mus.ok = 0;
}

int vg_mus_state(void)
{
    if (vg.mus.ok != 1)
        return VG_MUS_NODRIVER;
    return vg.mus.present == 1 ? vg.mus.state : VG_MUS_NODRIVER;
}

int vg_mus_stop(void)
{
    if (vg.mus.ok != 1 || vg_mus_state() != VG_MUS_PLAYING)
        return 0;
    pmd_stop();
    vg.mus.vol = 0;
    return 1;
}

/* the same name (exact, case-sensitive) while it plays: nothing; else the old song stops
 * without a fade */
int vg_mus_play(const char *name, int vol)
{
    struct vg_mus *m = &vg.mus;
    if (m->ok != 1)
        return 0;
    if (vg_mus_state() == VG_MUS_PLAYING) {
        if (!strcmp(m->name, name))
            return 1;
        vg_mus_stop();
    }
    strncpy(m->name, name, VG_MUS_NAME);
    m->name[VG_MUS_NAME] = 0;
    pmd_load_play(name, vol);
    m->vol = (int16_t)vol;
    return vg_mus_state();
}

void vg_mus_set_vol(int vol)
{
    if (vg.mus.ok != 1 || vg_mus_state() != VG_MUS_PLAYING)
        return;
    pmd_set_vol(vol);
    vg.mus.vol = (int16_t)vol;
}

/* Blocking: the volume from g_mus_vol down to 0 over t/100 s, one AH=19h per VSYNC; then
 * volume 0 and stop. Without a free timer slot it stops at once. The volume is the original's
 * long arithmetic, (t - elapsed) * v0 / t; t = 0 divides by 0 as it does. */
int vg_mus_fade_stop(int t)
{
    int32_t t32 = (int16_t)t, v0, e, now;
    int h;
    if (vg.mus.ok != 1 || vg_mus_state() != VG_MUS_PLAYING)
        return 0;
    h = vg_timer_start(t32);
    if (h) {
        v0 = vg.mus.vol;
        if (!vg_timer_done(h)) {
            int quit = 0;
            do {
                e = vg_timer_elapsed(h);
                if (e == -1)
                    break;
                if (t32 == 0)
                    vg_runtime_error(VG_R6003);
                pmd_set_vol((int16_t)((int32_t)((uint32_t)(t32 - e) * (uint32_t)v0) / t32));
                /* until the elapsed time changes: the next VSYNC */
                while ((now = vg_timer_elapsed(h)) == e)
                    if ((quit = vg_frame()) != 0)
                        break;
            } while (!quit && !vg_timer_done(h));
        }
        lrv_log(vg.hal, LRV_LOG_INFO, "music: faded out over %d VSYNCs (t = %d)",
                (int)vg.timers.slot[h - 1].elapsed, (int)t32);
        vg_timer_free(h);
    }
    vg_mus_set_vol(0);
    vg_mus_stop();
    return 1;
}

int vg_mus_measure(void)
{
    if (vg.mus.ok != 1 || vg_mus_state() != VG_MUS_PLAYING)
        return -1;
    if (vg.mus.present != 1 || vg.mus.state != VG_MUS_PLAYING)
        return 0;                       /* pmd_measure1's other answer: not reached */
    return (int16_t)(uint16_t)(drv(0x0500) + 1u);
}

/* ---- offline ------------------------------------------------------------------------------- */

int vg_render_music(void *ctx, const struct lrv_hal *hal, const struct lrv_run_cfg *cfg,
                    const char *name, double seconds, uint32_t *rate,
                    void (*sink)(void *sctx, const int16_t *pcm, int frames), void *sctx)
{
    int16_t buf[LRV_MIXER_BLOCK];
    uint64_t total, done = 0;
    int rc;

    (void)ctx;
    memset(&vg, 0, sizeof vg);
    if ((rc = vg_open_pack(hal, cfg)) != LRV_OK)
        return rc;
    vg_snd_open(1);
    vg_mus_init();
    if (vg_mus_play(name, 100) != VG_MUS_PLAYING) {
        lrv_log(hal, LRV_LOG_ERROR, "music: %s does not play (sound=%s)", name,
                vg.profile.sound);
        rc = LRV_ERR_NOTFOUND;
    } else {
        *rate = lrv_music_rate(&vg.mus.music);
        total = (uint64_t)(seconds * *rate);
        while (done < total) {
            int n = (int)(total - done > LRV_MIXER_BLOCK ? LRV_MIXER_BLOCK : total - done);
            lrv_mixer_render(&vg.mus.music.mixer, buf, n);
            sink(sctx, buf, n);
            done += (uint64_t)n;
        }
    }
    vg_mus_term();
    vg_snd_close();
    lrv_pack_close(&vg.pak);
    return rc;
}
