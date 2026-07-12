# Elisa Screen-Understanding Orchestra

Turns the live macOS screen into a stream an LLM can *watch*: a symbolic pipeline (Elisa + Swift)
measures what changed and a small hierarchy of LLM agents interprets it. The design is an
"orchestra" — cheap deterministic members do everything measurable; neural members only interpret,
and each tier wakes the next on signal (see `SPEC.md`, the single source of truth for all
interfaces).

## How it works

`frame_dump` (Elisa, ScreenCaptureKit) captures the display and emits one **delta-encoded text
batch** every few seconds: a full ASCII+color keyframe, then per-frame deltas (`SAME`, `SHIFT dy=n`
for scrolls, `ROWS a-b` for changed rows), plus a `STATS` line and a symbolic `ACTIVITY` triage
label (`still|typing|scrolling|video|switching`). A calm batch is ~15–20K tokens at 192-cell width —
roughly 7× cheaper than full-frame dumps at 4× the resolution — and every frame is losslessly
reconstructable. Each batch also gets a **full-res JPEG keyframe sidecar**, and `screenocr`
(Swift/Vision) provides positioned text on demand, including `--crop` zooms for active perception.

On top of the stream sit the neural members (`watcher_protocol.md`): a cheap **watcher** agent
maintains a **3-tier structured memory** — a ≤2 KB working set (`state.md`: typed OBSERVATIONS /
OBJECTS / RELATIONS / HYPOTHESES, with stable object ids), an append-only episodic trace (`log.md`),
and a consolidated semantic story (`story.md`) that a slow **consolidator** pass folds aged episodes
into. Every tier forgets *representation* under a hard cap but keeps *evidence* pointers back into the
batch stream (and, before pruning, into the exact Tier-A archive). A **boss** agent, woken only by
escalations, dispatches budgeted zoom/OCR queries. Short-lived watchers inherit this external memory
and observe an unbounded stream while total memory stays compact — the point of the whole design.

## Files

| File | Role |
|---|---|
| `frame_dump.elisa` | delta encoder + triage (the always-on symbolic member) |
| `screencap.elisa` | ScreenCaptureKit bridge in pure Elisa (Obj-C runtime over FFI) |
| `archive.elisa` | Tier A exact-frame ring: XOR-delta + LZFSE, checksummed, byte-capped |
| `arch_tool.elisa` | archive verifier (`verify` = bit-exactness test) and frame extractor |
| `screenasr.swift` | system-audio speech transcription (SpeechAnalyzer) — parked, ready |
| `screenocr.swift` | Vision OCR CLI: positioned text, `--crop` region zoom |
| `ocr_watch.sh` | eager OCR trigger on scene-change batches |
| `SPEC.md` | system contracts: members, stream format v2, blackboard layout |
| `watcher_protocol.md` | watcher/boss agent protocol (external memory, escalation) |
| `eval/` | scoring harness: scripted-truth session + `score.py` |

## Build & run

Requires the Elisa compiler (`elisacore`) and the Screen Recording TCC permission (ScreenCaptureKit
prompts on first run).

```sh
elisacore build frame-dump --project .
./frame_dump [out_dir] [width=192] [fps=24] [n_seconds=3] [token_cap=40000] [retain=40] [imgs=1] [arch_mb=2048]

elisacore build arch-tool --project .
./arch_tool verify /tmp/screen_batches          # prove the exact ring is bit-exact
./arch_tool extract /tmp/screen_batches 20 f.ppm

swiftc -O screenocr.swift -o screenocr
./ocr_watch.sh /tmp/screen_batches ./screenocr   # eager OCR loop (optional)
```

Batches land in `/tmp/screen_batches/` (`batch_<n>.txt` + `batch_<n>.jpg`, `latest.txt` pointer,
pruned to the retention window); the agent blackboard lives in `/tmp/screen_watch/`. Point a watcher
agent at `watcher_protocol.md` to start observing.

## Verifying

`eval/session_terminal.command` drives a scripted ground-truth session; `eval/score.py` aligns its
phases against the recorded batches and scores the watcher's log. Reconstruction fidelity of the
delta stream itself is lossless by construction (churn re-keyframes; dropped frames never update the
baseline).

## History

This repo began as a "comic book" recorder (screen → PNG contact sheets of downscaled panels, the
Wolf3D comic-capture pipeline generalized off SDL). The delta-encoded text stream + keyframe-sidecar
system replaced it; the comic pipeline was removed (see git history — the living copy of
`comic_capture.elisa` remains in the elisa-wolf3d repo).
