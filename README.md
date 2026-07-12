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
| `frame_dump.elisa` | live recorder: ScreenCaptureKit source + main (drives the encoder) |
| `encoder.elisa` | the delta encoder + batch serializer + triage, shared by the recorder and scenegen |
| `scenegen.elisa` | deterministic synthetic scene source → real encoder (eval fixtures) |
| `screencap.elisa` | ScreenCaptureKit bridge in pure Elisa (Obj-C runtime over FFI) |
| `archive.elisa` | Tier A exact-frame ring: XOR-delta + LZFSE, checksummed, byte-capped |
| `arch_tool.elisa` | archive verifier + query engine: `verify` / `show` / `replay` / `compare` |
| `arch-ocr.sh` | OCR an exact archived frame (resolve an evidence pin to positioned text) |
| `screenasr.swift` | system-audio speech transcription (SpeechAnalyzer) — parked, ready |
| `screenocr.swift` | Vision OCR CLI: positioned text, `--crop` region zoom |
| `ocr_watch.sh` | eager OCR trigger on scene-change batches |
| `SPEC.md` | system contracts: members, stream format v2, blackboard layout |
| `watcher_protocol.md` | watcher/boss agent protocol (external memory, escalation) |
| `eval/` | scoring harness: `score.py` (triage) + `score_memory.py` (watcher memory) + `scenarios.md` |

## Build & run

Requires the Elisa compiler (`elisacore`) and the Screen Recording TCC permission (ScreenCaptureKit
prompts on first run).

```sh
elisacore build frame-dump --project .
./frame_dump [out_dir] [width=192] [fps=24] [n_seconds=3] [token_cap=40000] [retain=40] [imgs=1] [arch_mb=2048]

elisacore build arch-tool --project .
./arch_tool verify /tmp/screen_batches            # prove the exact ring is bit-exact
./arch_tool show    /tmp/screen_batches 20 f.ppm  # decode frame 20 (add "x y w h" to crop)
./arch_tool replay  /tmp/screen_batches 20 60 5 rp_   # lossless replay 20..60 step 5
./arch_tool compare /tmp/screen_batches 20 40 d.ppm   # exact pixel diff: changed count + bbox
./arch-ocr.sh       /tmp/screen_batches 20 0,0,600,120  # OCR an exact archived frame

swiftc -O screenocr.swift -o screenocr
./ocr_watch.sh /tmp/screen_batches ./screenocr   # eager OCR loop (optional)

elisacore build scenegen --project .              # deterministic eval fixtures (no screen perms)
./scenegen counter /tmp/run 192 10 20000          # render a scenario through the real encoder
python3 eval/score_memory.py /tmp/run --arch-tool ./arch_tool   # after a watcher fills answers.jsonl
```

Batches land in `/tmp/screen_batches/` (`batch_<n>.txt` + `batch_<n>.jpg`, `latest.txt` pointer,
pruned to the retention window); the agent blackboard lives in `/tmp/screen_watch/`. Point a watcher
agent at `watcher_protocol.md` to start observing.

## Verifying

Two levels of scoring. `eval/score.py` grades the **symbolic** triage: it aligns a scripted session's
phases (`eval/session_terminal.command`) against the recorded batches and checks the ACTIVITY labels.
`eval/score_memory.py` grades the **neural** watcher: against a scenario's authored ground truth
(`eval/scenarios/<name>/{truth,probes}.jsonl`) it scores perception accuracy, memory retention,
event order, and — the metric that matters most — confabulation rate, plus tokens/latency. Honest
"unknown" answers are misses but never confabulations, so the harness rewards a watcher that declines
over one that guesses. `python3 eval/score_memory.py --selftest` checks the metric math. See
`eval/scenarios.md` for the 8-scenario battery. Reconstruction fidelity of the delta stream is
lossless by construction (churn re-keyframes; dropped frames never update the baseline) and of the
archive is a tested property (`arch_tool verify`).

## History

This repo began as a "comic book" recorder (screen → PNG contact sheets of downscaled panels, the
Wolf3D comic-capture pipeline generalized off SDL). The delta-encoded text stream + keyframe-sidecar
system replaced it; the comic pipeline was removed (see git history — the living copy of
`comic_capture.elisa` remains in the elisa-wolf3d repo).
