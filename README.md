# Comic Book Video — desktop screen recorder → comic-strip contact sheets

Records the live macOS screen into "comic book" contact-sheet PNGs: each captured frame is
box-downscaled into a panel, panels tile into a grid "page", every panel gets a burned-in capture
number + timestamp, and full pages are written as PNGs plus a sidecar CSV. Reading one page lets a
vision model reconstruct on-screen motion the way a comic strip conveys action across panels.

This is the Wolfenstein-3D comic recorder generalized off SDL — instead of being handed an in-memory
SDL framebuffer, it grabs the real display each tick.

## Layout

- `screencap.elisa` — ScreenCaptureKit capture driven **entirely from Elisa** (no Objective-C source file).
  ScreenCaptureKit is an Obj-C framework, so this drives the Obj-C runtime over plain-C FFI: `objc_msgSend`
  (address taken via `dlsym`, invoked per-call-site with `call_as` for the exact arm64 prototype),
  `objc_allocateClassPair`/`class_addMethod` to build the `SCStreamOutput` delegate with an Elisa `@c_abi`
  function as its IMP, and hand-assembled global blocks for the async completion handlers. It runs a
  continuous `SCStream`, stages the latest frame behind an `os_unfair_lock`, computes per-frame motion
  energy and system-audio RMS, and exposes the `screencap_*` API. `screencap_grab()` is a cheap memcpy, so
  capture runs at ~45 fps. (CGDisplayCreateImage is obsoleted on macOS 15+, so SCK is the only path.)
- `comic_capture.elisa` — project-agnostic comic pipeline (downscale/blit, annotation, hand-rolled PNG
  encoder, CSV). Shared verbatim with the Wolf3D recorder.
- `screen_recorder.elisa` — the `main` loop: grab → `comic_capture_rgb` → pace with `usleep` → flush.

## Build & run

```sh
elisac build screen-rec --project .
./screen_rec [out_prefix] [delay_ms] [cols] [rows] [panel_w] [panel_h] [max_frames]
```

It records **continuously until you press Ctrl-C** (or until `max_frames`), streaming each page to disk
the moment it fills, then flushing the partial last page on exit. Args (all optional, positional):

| arg | default | meaning |
|---|---|---|
| `out_prefix` | `/tmp/screen_comic_page` | page prefix → `<prefix>000.png`, `<prefix>_frames.csv` |
| `delay_ms` | `-1` (motion-adaptive) | `<0` = capture on motion (see below); `>0` = fixed every N ms; `0` = max (~45 fps) |
| `cols` `rows` | `3` `3` | panels per page grid (= 9 frames/page); max 12×12 |
| `panel_w` `panel_h` | `440` `auto` | panel pixel size; `panel_h 0` = match screen aspect; max 1000×560 |
| `max_frames` | `0` | stop after N frames (`0` = unlimited) |

**The defaults are tuned for an LLM watching the screen.** A 3×3 page comes out ~1344×876 (~1.18 MP) —
right at the vision-input sweet spot (~1.15 MP / ~1568 px long edge), so the sheet is read ~1:1 with
each panel still recognizable. Panel height auto-matches the captured screen's aspect ratio, so nothing
is distorted.

**Motion-adaptive sampling (default).** Rather than a fixed frame rate, the SCStream's 60 fps frames are
diffed on the bridge side (cheap sparse-grid motion energy), and a panel is captured only when the screen
*changes*: as fast as ~7.5 fps during heavy activity (the `KF_MIN_MS` floor), and as slow as one frame
per `KF_MAX_MS` (2.5 s heartbeat) when idle. This concentrates the limited panel budget on the moments
that actually move — the decisive frames a fixed clock would miss between samples. Tunables live in
`screen_recorder.elisa` (`KF_MIN_MS`, `KF_MAX_MS`, `KF_THRESH`). Pass a positive `delay_ms` for old-style
fixed-rate instead.

The CSV's `stamp_ms` is a real monotonic timeline (ms since recording started), so panels can be aligned
to other timestamped streams.

**Audio (native, cheap layer).** The same `SCStream` also captures system audio. Each buffer's RMS
loudness (0–1000) is computed on the bridge side and (a) recorded per panel in the CSV — the `keymask`
column carries the RMS level, the `keys` column carries a tag (`snd`/`loud`) — and (b) fed into the
keyframe trigger, so a loud spike (an impact, a crowd surge) forces a capture even when the picture
barely moved. This is the cheap real-time audio-event signal. Full ASR/transcription and a many-class
audio-event classifier are deliberately *not* built in — they're external model integrations; the real
monotonic timeline is the anchor they'd align to. Tunables: `KF_AUDIO_THRESH`, `AUDIO_LABEL_LOUD/SND`.

Examples:
- `./screen_rec` → motion-adaptive, watch-optimized 3×3 ~1.18 MP scenes, until Ctrl-C.
- `./screen_rec /tmp/hi 0 10 10 760 428` → fixed **~8K (7666×4346) pages at ~45 fps** for fast motion.
- `./screen_rec /tmp/demo 500 3 3 440 0 9` → fixed 2 fps, exactly one page then exit.

Requires the **Screen Recording** permission (System Settings → Privacy & Security → Screen Recording);
ScreenCaptureKit raises the prompt on first run.

## Note on the Objective-C-from-Elisa port

The whole bridge is Elisa — there is no `.m` file. This exercises the Obj-C runtime via FFI (see
`screencap.elisa`). It also drove one compiler fix in Elisa-core: aggregates larger than 16 bytes passed
or returned **by value** across the C ABI (e.g. `CMTime`, 24 bytes) now use the platform memory class
(`sret` returns; arm64 indirect-pointer args / x86-64 `byval`). This applies only at the C-ABI boundary —
`@c_abi` functions and `call_as` indirect calls — so Elisa's internal calling convention is unchanged.
Calling a plain `extern` that returns such a struct by value is still unsupported; construct the struct in
Elisa or go through `call_as` (as this code does for `setMinimumFrameInterval:`).

## Resolution limits

The page is assembled in one static RGB buffer and the PNG encoder uses 32-bit offset math, so the
hard ceiling is ~716M pixels (≈26000² ). The practical ceiling is the buffer: `comic_capture.elisa`
caps a page at 256 MB (`CC_MAX_PAGE_BYTES`) — enough for 12×12 @ 1000×560 ≈ a 12078×6798 sheet. Raise
`CC_MAX_PAGE_BYTES`, the `page_rgb` array size, and the `CC_MAX_*` caps together to go larger.

Source frames are captured at the display's **full backing-pixel (Retina) resolution** (resolved via
`CGDisplayModeGetPixelWidth/Height`), so panels downscale from the sharpest available image. The source
buffer caps at 24M px (`GRAB_CAP`), covering 4K/5K/6K displays. The recorder prints the captured source
resolution at startup.
