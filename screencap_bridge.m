// screencap_bridge.m — continuous-stream screen capture for the Elisa comic recorder.
//
// macOS 15+ obsoleted CGDisplayCreateImage, so capture goes through ScreenCaptureKit. Rather than take
// a fresh synchronous screenshot per frame (~80ms each, capping us at ~10fps), this runs a continuous
// SCStream that pushes frames on a background queue; the bridge keeps only the LATEST frame in a small
// staging buffer behind a lock. The Elisa loop then samples that latest frame with a cheap memcpy via
// screencap_grab(), so the comic FPS is limited only by how fast the loop chooses to sample (and the
// stream's 60fps cap), not by a per-frame round trip.
//
// Public C API (all callable straight from Elisa `extern`):
//   int  screencap_start(void)            -- begin the stream; 1 if running
//   int  screencap_wait_first_frame(void) -- block (<=2s) until a frame has arrived; 1 if one did
//   int  screencap_grab(uint32_t* dst, int cap_px) -- copy latest frame as 0x00RRGGBB; 1 on success
//   int  screencap_w(void) / screencap_h(void)     -- latest frame dims
//   void screencap_stop(void)             -- stop the stream
//   void screencap_install_sigint(void) / int screencap_should_stop(void) -- Ctrl-C plumbing
//
// Requires the "Screen Recording" permission; SCK raises the prompt on first use.
// Link: -framework ScreenCaptureKit -framework CoreMedia -framework CoreVideo -framework Foundation

#import <ScreenCaptureKit/ScreenCaptureKit.h>
#import <CoreMedia/CoreMedia.h>
#import <CoreVideo/CoreVideo.h>
#import <CoreGraphics/CoreGraphics.h>
#import <AudioToolbox/AudioToolbox.h>
#import <Foundation/Foundation.h>
#import <dispatch/dispatch.h>
#import <os/lock.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <math.h>

// ---- Ctrl-C plumbing: the recorder polls screencap_should_stop() so it can flush the partial page. --
static volatile sig_atomic_t g_stop = 0;
static void screencap_on_sigint(int sig) { (void)sig; g_stop = 1; }
void screencap_install_sigint(void) { signal(SIGINT, screencap_on_sigint); }
int screencap_should_stop(void) { return (int)g_stop; }

// ---- monotonic millisecond clock (real timeline for the CSV; later, audio alignment hangs off this) -
static long screencap_now_ms_internal(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long)ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}
long screencap_now_ms(void) { return screencap_now_ms_internal(); }

// ---- latest-frame staging (BGRA, tightly packed), shared between the SCK queue and the caller. ------
static os_unfair_lock g_lock = OS_UNFAIR_LOCK_INIT;
static uint8_t *g_stage = NULL;       // latest frame bytes, g_w*g_h*4
static size_t   g_stage_cap = 0;      // allocated bytes
static int g_w = 0, g_h = 0;
static int g_have = 0;
// Motion energy accumulated (across stream callbacks) since the last keyframe was taken. Each frame
// contributes its mean per-pixel BGR delta vs the previous frame, sampled on a sparse grid (cheap).
static long g_motion_accum = 0;

// ---- audio energy (system audio captured by the same SCStream) -------------------------------------
// g_audio_level is the most recent RMS (0..1000). g_audio_accum sums loudness-above-floor since the
// last keyframe, so a sound spike (an impact, a crowd-noise surge) can force a capture even when the
// picture barely moved — the signal that compensates for visual temporal undersampling.
static int  g_audio_level = 0;
static long g_audio_accum = 0;
static int  g_audio_floor = 25;     // ignore quiet room tone below this RMS
static long g_audio_kf_thresh = 0;  // 0 = audio never forces a keyframe (set via screencap_set_audio_trigger)

int screencap_audio_level(void) {
    os_unfair_lock_lock(&g_lock);
    int v = g_audio_level;
    os_unfair_lock_unlock(&g_lock);
    return v;
}
void screencap_set_audio_trigger(int thresh) {
    os_unfair_lock_lock(&g_lock);
    g_audio_kf_thresh = (long)thresh;
    os_unfair_lock_unlock(&g_lock);
}

int screencap_w(void) { return g_w; }
int screencap_h(void) { return g_h; }
int screencap_motion_accum(void) {
    os_unfair_lock_lock(&g_lock);
    long m = g_motion_accum;
    os_unfair_lock_unlock(&g_lock);
    return (int)(m > 2000000000L ? 2000000000L : m);
}

// Print the captured source resolution (backing pixels) — startup diagnostic.
void screencap_log_dims(void) {
    fprintf(stderr, "screen_rec: capturing source at %dx%d px\n", g_w, g_h);
}

// Compute RMS loudness of one audio sample buffer (assumed PCM Float32) and fold it into the audio
// level + spike accumulator. Cheap: one pass over the samples.
static void screencap_process_audio(CMSampleBufferRef sb) {
    CMBlockBufferRef block = NULL;
    char ablMem[sizeof(AudioBufferList) + sizeof(AudioBuffer)];   // room for up to 2 channel buffers
    AudioBufferList *abl = (AudioBufferList *)ablMem;
    OSStatus s = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
        sb, NULL, abl, sizeof(ablMem), NULL, NULL,
        kCMSampleBufferFlag_AudioBufferList_Assure16ByteAlignment, &block);
    if (s != noErr || !block) { if (block) CFRelease(block); return; }

    double sumsq = 0.0; long n = 0;
    for (UInt32 i = 0; i < abl->mNumberBuffers; i++) {
        const float *d = (const float *)abl->mBuffers[i].mData;
        if (!d) continue;
        long cnt = (long)(abl->mBuffers[i].mDataByteSize / sizeof(float));
        for (long k = 0; k < cnt; k++) { double v = d[k]; sumsq += v * v; }
        n += cnt;
    }
    CFRelease(block);
    if (n <= 0) return;

    int level = (int)(sqrt(sumsq / (double)n) * 1000.0);   // RMS scaled to 0..1000
    os_unfair_lock_lock(&g_lock);
    g_audio_level = level;
    if (level > g_audio_floor) g_audio_accum += (level - g_audio_floor);
    os_unfair_lock_unlock(&g_lock);
}

// ---- the SCStream output sink ----------------------------------------------------------------------
@interface ScreencapOutput : NSObject <SCStreamOutput, SCStreamDelegate>
@end

@implementation ScreencapOutput
- (void)stream:(SCStream *)stream
  didOutputSampleBuffer:(CMSampleBufferRef)sampleBuffer
                 ofType:(SCStreamOutputType)type {
    if (!sampleBuffer || !CMSampleBufferIsValid(sampleBuffer)) return;
    if (type == SCStreamOutputTypeAudio) { screencap_process_audio(sampleBuffer); return; }
    if (type != SCStreamOutputTypeScreen) return;

    CVImageBufferRef px = CMSampleBufferGetImageBuffer(sampleBuffer);
    if (!px) return;

    CVPixelBufferLockBaseAddress(px, kCVPixelBufferLock_ReadOnly);
    int w = (int)CVPixelBufferGetWidth(px);
    int h = (int)CVPixelBufferGetHeight(px);
    size_t bpr = CVPixelBufferGetBytesPerRow(px);
    const uint8_t *base = (const uint8_t *)CVPixelBufferGetBaseAddress(px);

    if (base && w > 0 && h > 0) {
        size_t need = (size_t)w * (size_t)h * 4;
        os_unfair_lock_lock(&g_lock);
        if (!g_stage || g_stage_cap < need) {
            free(g_stage);
            g_stage = (uint8_t *)malloc(need);
            g_stage_cap = g_stage ? need : 0;
        }
        if (g_stage) {
            // Motion energy vs the previous frame (still in g_stage), on a sparse grid so it stays
            // cheap even at 60fps/Retina. Skip if dims changed or there's no previous frame yet.
            if (g_have && g_w == w && g_h == h) {
                const int STRIDE = 8;
                long sad = 0, cnt = 0;
                for (int y = 0; y < h; y += STRIDE) {
                    const uint8_t *srow = base + (size_t)y * bpr;
                    const uint8_t *prow = g_stage + (size_t)y * w * 4;
                    for (int x = 0; x < w; x += STRIDE) {
                        const uint8_t *sp = srow + (size_t)x * 4;
                        const uint8_t *pp = prow + (size_t)x * 4;
                        sad += abs((int)sp[0] - pp[0]) + abs((int)sp[1] - pp[1]) + abs((int)sp[2] - pp[2]);
                        cnt++;
                    }
                }
                if (cnt > 0) g_motion_accum += sad / cnt;   // mean per-pixel delta (0..765), accumulated
            }
            // drop any row padding -> tightly packed BGRA
            for (int y = 0; y < h; y++) {
                memcpy(g_stage + (size_t)y * w * 4, base + (size_t)y * bpr, (size_t)w * 4);
            }
            g_w = w; g_h = h; g_have = 1;
        }
        os_unfair_lock_unlock(&g_lock);
    }
    CVPixelBufferUnlockBaseAddress(px, kCVPixelBufferLock_ReadOnly);
}

- (void)stream:(SCStream *)stream didStopWithError:(NSError *)error { (void)stream; (void)error; }
@end

static SCStream *g_stream = nil;
static ScreencapOutput *g_sink = nil;

// Build the filter+config for the main display and start the stream. Blocks until startCapture
// reports back. Returns 1 if the stream is running.
int screencap_start(void) {
    __block int ok = 0;
    dispatch_semaphore_t sem = dispatch_semaphore_create(0);

    [SCShareableContent getShareableContentWithCompletionHandler:^(SCShareableContent *content, NSError *err) {
        if (!content || content.displays.count == 0) {
            dispatch_semaphore_signal(sem);
            return;
        }
        SCDisplay *display = content.displays[0];
        SCContentFilter *filter = [[SCContentFilter alloc] initWithDisplay:display excludingWindows:@[]];

        // Capture at the display's full backing-pixel resolution (Retina), not point resolution:
        // SCDisplay.width/height are points, so resolve the current mode's pixel dims.
        size_t capW = (size_t)display.width;
        size_t capH = (size_t)display.height;
        CGDisplayModeRef mode = CGDisplayCopyDisplayMode(display.displayID);
        if (mode) {
            capW = CGDisplayModeGetPixelWidth(mode);
            capH = CGDisplayModeGetPixelHeight(mode);
            CGDisplayModeRelease(mode);
        }

        SCStreamConfiguration *cfg = [[SCStreamConfiguration alloc] init];
        cfg.width = capW;
        cfg.height = capH;
        cfg.pixelFormat = kCVPixelFormatType_32BGRA;
        cfg.minimumFrameInterval = CMTimeMake(1, 60); // allow up to 60fps
        cfg.queueDepth = 6;
        cfg.showsCursor = YES;
        cfg.capturesAudio = YES;                      // system audio on the same stream/clock
        cfg.excludesCurrentProcessAudio = YES;

        g_sink = [[ScreencapOutput alloc] init];
        g_stream = [[SCStream alloc] initWithFilter:filter configuration:cfg delegate:g_sink];

        NSError *addErr = nil;
        dispatch_queue_t q = dispatch_queue_create("screencap.output", DISPATCH_QUEUE_SERIAL);
        [g_stream addStreamOutput:g_sink type:SCStreamOutputTypeScreen sampleHandlerQueue:q error:&addErr];
        // Audio is best-effort: if it can't be added, keep recording video-only.
        NSError *audioErr = nil;
        dispatch_queue_t aq = dispatch_queue_create("screencap.audio", DISPATCH_QUEUE_SERIAL);
        [g_stream addStreamOutput:g_sink type:SCStreamOutputTypeAudio sampleHandlerQueue:aq error:&audioErr];
        if (audioErr) fprintf(stderr, "screen_rec: audio capture unavailable (%s)\n",
                              audioErr.localizedDescription.UTF8String);

        [g_stream startCaptureWithCompletionHandler:^(NSError *startErr) {
            ok = (startErr == nil) ? 1 : 0;
            dispatch_semaphore_signal(sem);
        }];
    }];

    dispatch_semaphore_wait(sem, DISPATCH_TIME_FOREVER);
    return ok;
}

// Wait up to ~2s for the first frame so the caller can size buffers / fail fast on permission denial.
int screencap_wait_first_frame(void) {
    for (int i = 0; i < 2000; i++) {
        os_unfair_lock_lock(&g_lock);
        int have = g_have;
        os_unfair_lock_unlock(&g_lock);
        if (have) return 1;
        usleep(1000);
    }
    return 0;
}

// Motion-adaptive keyframe gate. Blocks until (after min_ms) EITHER visual motion OR audio loudness
// has accumulated past its threshold since the last keyframe, OR max_ms elapses (a heartbeat so static
// scenes still get sampled). Resets both accumulators on return. Returns 1 if motion-triggered, 3 if
// audio-triggered, 2 if it fired on the heartbeat. Audio triggering only applies once a caller has set
// a non-zero audio threshold via screencap_set_audio_trigger().
int screencap_wait_keyframe(int min_ms, int max_ms, int thresh) {
    long start = screencap_now_ms_internal();
    int reason = 2;
    for (;;) {
        if (g_stop) { reason = 2; break; }
        long elapsed = screencap_now_ms_internal() - start;
        os_unfair_lock_lock(&g_lock);
        long m = g_motion_accum;
        long a = g_audio_accum;
        long akf = g_audio_kf_thresh;
        os_unfair_lock_unlock(&g_lock);
        if (elapsed >= min_ms && m >= (long)thresh) { reason = 1; break; }
        if (elapsed >= min_ms && akf > 0 && a >= akf) { reason = 3; break; }
        if (elapsed >= max_ms) { reason = 2; break; }
        usleep(6000);
    }
    os_unfair_lock_lock(&g_lock);
    g_motion_accum = 0;
    g_audio_accum = 0;
    os_unfair_lock_unlock(&g_lock);
    return reason;
}

// Copy the latest frame into `dst` (capacity_px u32 entries, written 0x00RRGGBB). 1 on success.
int screencap_grab(uint32_t *dst, int capacity_px) {
    os_unfair_lock_lock(&g_lock);
    int w = g_w, h = g_h, have = g_have;
    if (!have || w <= 0 || h <= 0 || (int64_t)w * (int64_t)h > (int64_t)capacity_px || !g_stage) {
        os_unfair_lock_unlock(&g_lock);
        return 0;
    }
    for (int y = 0; y < h; y++) {
        const uint8_t *row = g_stage + (size_t)y * w * 4;
        uint32_t *out = dst + (size_t)y * w;
        for (int x = 0; x < w; x++) {
            const uint8_t *p = row + (size_t)x * 4;     // BGRA
            out[x] = ((uint32_t)p[2] << 16) | ((uint32_t)p[1] << 8) | (uint32_t)p[0];
        }
    }
    os_unfair_lock_unlock(&g_lock);
    return 1;
}

void screencap_stop(void) {
    if (g_stream) {
        [g_stream stopCaptureWithCompletionHandler:^(NSError *e) { (void)e; }];
    }
}
