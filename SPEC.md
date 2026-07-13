# Screen-Understanding Orchestra — System Contracts (SPEC)

This document is the single source of truth for the interfaces between orchestra members.
A member may be rewritten freely; these contracts may only change with a version bump.

## Invariants

- **I1** Neural members interpret; they never assert what a symbolic member could measure.
- **I2** Claims flow forward; evidence stays randomly accessible backward (retention window).
- **I3** Members communicate only via the stream + blackboard files — no direct member calls.
- **I4** Every stream section is ignorable by readers that don't know it (versioned, sectioned).
- **I5** Attention pyramid: each tier wakes the next on signal only (plus the singer's slow heartbeat).
- **I6** Every neural claim carries an evidence pointer; every re-watch is a specific question with a budget.
- **I7** Memory is a 3-tier hierarchy (working `state.md` → episodic `log.md` → semantic `story.md`);
  information only flows *down*, each tier has a hard size cap, and consolidation loses representation
  but never invents. Object ids are stable and reused across tiers and watcher rotations.
- **I8** A `describe` (VLM) answer is interpretation (I1, applied to a neural claimant, not an oracle):
  it must carry the exact archive seq span it actually saw; it may never override a symbolic member's
  measurement (an `ocr`/`compare` result contradicting the VLM wins); and it enters memory only per the
  **describe trust policy** (below), which is filled in by the Phase-3 trap-test, not assumed.
- **I9** OBSERVED vs INFERRED is structural, for symbolic members too. The viola (`tracker`) emits
  `OBS` records (a component existed with these cells/bbox/centroid — a deterministic measurement, no
  identity, no cross-frame claim) and `INF` records (every cross-frame claim: association, and the
  events APPEAR/VANISH/REVERSE/REACQUIRE/OCCLUDED), each `INF` carrying a confidence. A track may
  report `UNKNOWN` identity or legitimately end rather than guess — laundering an uncertain
  association into a confident one is the symbolic member's version of VLM prior-fill and is a bug.
  Confidences are placeholders until the trap suite calibrates them (see the tracker trust policy).

## Members

| Role | Component | Kind |
|---|---|---|
| Drums | delta encoder (`frame_dump`, Elisa) | symbolic, always-on |
| Bass | ACTIVITY triage (inside `frame_dump`) | symbolic, per batch |
| Guitar | `screenocr` (Swift/Vision CLI) | symbolic, on-demand + scene-change |
| Viola | `tracker` (Elisa, delta-stream object identity) | symbolic, on-demand (boss-dispatched) |
| Cymbal | `audiotriage` (Elisa DSP over the audio ring) | symbolic, always-on |
| Violin | `screenvlm` (Qwen2.5-VL-3B, local) | neural, on-demand (boss-dispatched) |
| Sax | `screenaud` (MiDashengLM-0.6B, local) | neural, triggered (boss-dispatched) |
| Singer | stream watcher (cheap LLM agent) | neural, event-woken |
| Boss | orchestrator (stronger LLM agent) | neural, escalation-woken |
| Referee | eval harness (`eval/`) | offline scoring |

## Directory layout & ownership

```
/tmp/screen_batches/            owner: recorder (except *.ocr.txt: screenocr/ocr_watch)
  batch_<n>.txt                 delta-encoded text chunk (stream format v2)
  batch_<n>.jpg                 full-res keyframe image (same instant as the text keyframe)
  batch_<n>.ocr.txt             OCR annotation (lazy or eager)
  arch_<s>.bin / arch_<s>.idx   Tier A exact-frame ring (see "Archival fidelity tiers")
  latest.txt                    newest complete batch number

/tmp/screen_watch/              the blackboard (3-tier memory, I7)
  goal.md                       owner: user/boss — what matters right now
  state.md                      owner: singer — Tier 1 working mem, REWRITTEN each cycle, <= 2 KB
  log.md                        owner: singer(+boss) — Tier 2 episodic trace, APPEND-ONLY
  story.md                      owner: consolidator — Tier 3 semantic mem, rewritten on fold, <= 6 KB
  log.archive.md                owner: consolidator — cold episodic events truncated from log.md
  escalation.md                 owner: singer — overwrite-style mailbox to the boss
  queries/q_<id>.md             owner: boss — one active-perception question
  queries/q_<id>.answer.md      owner: the dispatched sub-watcher
```

Single writer per file; every write is atomic (tmp + rename) or a single append.

## Stream format v2

```
BATCH <b> v=2 frames=<F> <w>x<h> fps=<fps> t0=<ms> cap=<tok>
STATS same=<s> shifted=<sh> keyframes=<k> churn_rows=<c> img=<batch_<b>.jpg|none>
ACTIVITY <still|typing|scrolling|video|switching> conf=<0-100>
KEYFRAME 0 t=<ms>
ASCII
<h rows of w luminance chars " .:-=+*#%@">
COLOR
<h rows: hue letters R O Y G C B M, uppercase=bright / lowercase=dim; grayscale uses the ramp>
FRAME <i> t=<ms>
SAME | [SHIFT dy=<d>] ROWS <a>-<b> + row content ...
... (KEYFRAME <i> may reappear mid-batch on a churn resync)
BATCH_END emitted=<E> changed_rows=<R> bytes=<N> rate=<K>
```

- `v=2` is the format version; readers must reject a major version they don't know.
- `STATS`: `same` = SAME frames, `shifted` = frames carrying SHIFT, `keyframes` = keyframe count
  including frame 0, `churn_rows` = total changed rows, `img` = the sidecar image filename or `none`.
- `ACTIVITY` is the bass's verdict (rules below). `conf` is a coarse 0–100.
- Unknown lines between the header and `KEYFRAME 0` must be skipped by readers (I4).

### Triage rules (bass), applied in priority order to the finished batch

1. `video`     — rate > 1, or mid-batch keyframes >= 2, or churn_rows >= emitted * h * 4/10
2. `switching` — exactly 1 mid-batch keyframe and churn otherwise below the video bar
3. `scrolling` — any SHIFT frame
4. `still`     — churn_rows <= h/8 and same >= 90% of emitted frames
5. `typing`    — everything else (light localized change)

Confidence: 90 when the winning rule's signal is >= 2x its threshold (or, for `still`, when
churn_rows == 0); else 60.

### Grid ↔ pixel mapping (for zoom queries)

Text cell (col cx, row cy) on a w×h grid over a W×H screen covers the pixel rectangle:

```
x0 = cx * W / w      x1 = (cx+1) * W / w
y0 = cy * H / h      y1 = (cy+1) * H / h
```

Rows a–b of the grid = pixel band `[a*H/h, (b+1)*H/h)`. The `batch_<n>.jpg` is captured from
the same grab as the keyframe, so these coordinates are exact for the keyframe (and approximate
for later frames in the batch).

## Archival fidelity tiers

The model stream (batches) is lossless at GRID resolution by construction. Source-resolution
archival is tiered, and each tier states its guarantee honestly:

- **Tier A — exact ring** (`archive.elisa`, inside the recorder): every grabbed full-res frame,
  XOR-delta vs the previous frame + LZFSE, in segments of ~10s that each start with a keyframe
  (independently decodable). Ring bounded by a byte cap (`frame_dump` arg 8, MB, default 2048,
  0 = off); oldest segments pruned. **Bit-exactness is a TESTED property**: every index line
  carries a checksum of the raw frame, and `arch_tool verify <dir>` re-decodes the whole live
  ring and fails on any bit difference. `arch_tool extract <dir> <seq> <out.ppm>` recovers any
  archived frame. Timestamps share the batch timeline (ms since recorder start).
  Cost honesty: a calm screen keeps minutes-to-hours in the ring; full-screen video churn is
  MBs/frame and shrinks the window — that is the price of "exact", by design.
- **Tier B — high-fidelity, continuous** (planned): HEVC long-term recording. Labeled a
  high-fidelity archive, NOT lossless.
- **Tier C — evidence pinning** (planned): watcher/boss marks copy exact frames/crops out of the
  Tier A ring before pruning, so consolidated memory keeps exact evidence pointers.

## screenocr CLI contract

```
screenocr <image> [--crop x,y,w,h] [--min-conf 0.4]
```
stdout: one line per recognized string: `<x> <y> <w> <h> <conf> <text>` (pixel coords in the
FULL image's space even when cropped; conf 0–1). Exit 0 on success, 1 on unreadable image.
`batch_<n>.ocr.txt` holds the full-frame output for that batch's jpg.

## tracker CLI contract (the viola — symbolic object-identity member)

Answers *where things moved and whether they are the same thing over time* — the motion predicates a
VLM prior-fills (I8) and OCR/compare can't phrase. Model-free, deterministic, dependency-free; it
reconstructs each frame's grid from the delta stream and threads foreground components into persistent
tracks. A symbolic member, so its output is the authority over any `describe` motion claim (I1/I8).

```
tracker run   <batch_dir>       process batch_0.txt, batch_1.txt, … in order (tracks persist across)
tracker batch <file.txt>        process a single batch file
```
stdout — line records, OBSERVED vs INFERRED structural (I9):
```
OBS frame t=<ms> ncomp=<n> dw=<cells>              a deterministic per-frame component count
OBS comp  t=<ms> cx=<> cy=<> area=<> bbox=<a,b,c,d> a component existed (grid cells) — no identity
INF track t=<ms> id=<> cx=<> cy=<> vx=<> dir=<+1|-1|0> state=<A|L> conf=<>   this comp == track id
INF event id=<> kind=<APPEAR|VANISH|REVERSE|REACQUIRE|OCCLUDED> t=<ms> cx=<> cy=<> conf=<>
```
Exit 0 success; 1 no batches found; 2 bad args. Coordinates are grid cells (map to pixels via the
grid↔pixel mapping). Deterministic: identical input ⇒ byte-identical output (the repro gate).

- **Pipeline:** grid reconstruction (keyframe + delta ROWS/SHIFT) → mode-background foreground →
  4-connected components → gated nearest-centroid association (constant-velocity prediction) →
  ACTIVE→LOST→ENDED lifecycle. A LOST track overlapping a static, ≥-as-large track is inferred
  OCCLUDED (extended patience, may REACQUIRE); one lost in the open field VANISHes after LOST_MAX.
  Reversals use peak-detection with hysteresis.
- **tracker trust policy — MEASURED (M2 trap suite).** Trusted (100% perception, 0% confab,
  deterministic, reconstruction 1.0): object *count* (peak concurrent), *direction* over a span,
  *reversal presence + zone* (edge vs mid-field), *position*, *vanish/discontinuity* (`ncomp=0`
  gaps + VANISH), and *occlusion inference* (OCCLUDED event) — the exact predicates the violin missed
  (motion 50%→100%, motion-trap 25%→100%). **Measured LIMITS** (foreground connected-components,
  recorded not hidden): identity through a long same-colour occlusion or a full same-lane merge is NOT
  maintained (re-emerges as a new id — event-level OCCLUDED/VANISH is right, id-level REACQUIRE is
  not); textured/scrolling backgrounds defeat mode-background segmentation. These need an appearance
  model / Kalman prediction / the changed-cell+SHIFT camera path — deferred. Identity through a
  crossing is honest UNKNOWN (no confident wrong swap). Reproduce: `eval/track_test.sh motion-trap`.

## audiotriage CLI contract (the cymbal — symbolic audio triage)

The bass's audio twin: always-on, deterministic DSP over the audio ring (or a WAV) that emits cheap
symbolic AUDIO events so the singer sees audio in its normal cycle with no protocol change. A 512-pt
radix-2 FFT gives the spectrum; RMS + zero-crossings do the rest. No model — the authority over any
`describe`-style audio *timing/count* claim the sax makes (I1).

```
audiotriage <in.wav>            16 kHz mono s16le (parses the RIFF header)
```
stdout — one event per line:
```
AUDIO <TRANSIENT|SILENCE_START|SILENCE_END|LEVEL_SHIFT|TONE> t=<ms> [dur=<ms>] [freq=<hz>] conf=<c>
```
Exit 0 success; 1 unreadable WAV; 2 bad args. Deterministic: identical input ⇒ byte-identical output.

- **Detectors:** TRANSIENT = sharp RMS onset vs the previous 32 ms hop (catches an impact out of
  silence *and* two impacts 150 ms apart, each preceded by a bed hop); SILENCE_START/END = RMS below
  a floor, min-duration gated; TONE = one FFT bin holding > 30% of spectral energy for ≥ 128 ms (emits
  its frequency); LEVEL_SHIFT = a ≥ 6 dB (2×) change in the ~0.6 s moving RMS vs a hysteresis reference.
- **cymbal trust policy — MEASURED (M5 audio trap suite).** 100% perception / 0% confab / deterministic
  on all five scenes: transient count incl. the 150 ms ordering, silence onset (±hop), single
  LEVEL_SHIFT (not machine-gunned), tone count + frequency (1000 Hz exact), and an impact within one
  16 ms hop of 10.000 s (the a/v-skew gate, direct-PCM path). The cymbal owns audio *timing and count*;
  the sax may name *what* a sound is but never overrides the cymbal's when/how-many. Reproduce:
  `eval/audio_test.sh <scene>`. Live source: `audiocap` (SCStream system audio → `aud_*.pcm` ring).

## screenvlm CLI contract (the violin — local video-VLM member)

Answers *what happens* during a recorded time span, for non-textual motion content the symbolic
members can only report as statistics. Stateless like screenocr; a **neural claimant, not an oracle**
(I1/I8). Frames are pulled from the Tier-A ring via `arch_tool show` (no video decode), so every
answer is automatically evidence-pointed and re-groundable to exact pixels.

```
screenvlm <batch_dir> --span t0,t1 [--frames 16] [--region x,y,w,h]
          [--q "question"] [--arch-tool ./arch_tool] [--model ...] [--json]
```
stdout (text mode):
```
ANSWER <one-paragraph answer>
EVIDENCE arch seq <s0>..<s1> t=<t0>..<t1> frames=<n> region=<x,y,w,h|full>[ partial=true]
COST load=<s> infer=<s> model=Qwen2.5-VL-3B device=<mps|cpu>
```
Exit 0 success; 2 bad args; 1 when the span is not fully in the live ring — with a *partial* answer
marked `partial=true` if ≥ 4 frames were recoverable, else no answer and an `evidence-exhausted`
reason on stderr (distinct message, so the boss separates "pruned" from "error").

- **Model:** Qwen2.5-VL-3B-Instruct, fp16, MPS; greedy decode (`do_sample=False`) → reproducible.
  Provision the pinned venv once with `./setup_vlm.sh`; HF model cache (~7 GB) is shared with the
  VJEPA2 project. The 7B is a `--model` swap for offline use only, never while recording.
- **Frame selection:** uniform sample of ≤ `--frames` (cap 32) archive seqs across the span, each
  decoded and resized to 448-wide before the vision encoder (the proven recipe); `--region` crops at
  source resolution first, preserving native detail when zoomed.
- **Measured cost** (M1, this machine, 16 frames, full-frame 2880×1864→448): load ≈ 10 s, infer
  ≈ 12 s per call, peak RSS ≈ 10.7 GB. Per-call model load is the v1 price of statelessness; a
  `--stdin` load-once batch mode is a later add for boss sessions.

## screenaud CLI contract (the sax — local audio-LM member)

`screenaud.py` (MiDashengLM-0.6B, greedy) is the neural audio interpreter: it names *what a sound is*
(impact, tone, music-state, off-screen activity) above the cymbal's symbolic timing. Same stance as
the violin — Inferred, never overrides the cymbal's when/how-many.
```
screenaud <in.wav> [--q "question"] [--model ...] [--json]   ->  ANSWER <text> / COST …
```
Runs in its **own venv** `.venv-aud` (transformers **4.57**, via `./setup_aud.sh`) — separate from the
violin's `.venv-vlm` (transformers 5.13), because MiDashengLM's remote code emits garbage (token 0,
`"!!!!"`) under 5.x. On 4.57 it loads on MPS in ~5 s and infers in ~1 s.

- **sax trust policy — MEASURED (M6 audition).** The sax is **fluent but untrusted on synthetic audio
  and it confabulates.** On the audiogen scenes it mischaracterizes out-of-distribution content (1 kHz
  beeps → "a person speaking"; noise impacts → "the sound of a cat"), and on the absent-event probe
  ("is there an alarm?" over a no-alarm scene) it answers **"yes"** — a fabrication. So, exactly like
  the violin (I8), a sax answer is **Inferred-only, split by claim type**: it may seed a hypothesis
  about *what kind* of real-world sound is present, but it **never overrides the cymbal's timing/count**
  and a bare sax claim never becomes a `story.md` EVENT. The synthetic trap scenes measure the model's
  OOD/confab floor, not its real competence — a **real-audio audition (live `audiocap` capture)** is
  needed for the positive trust policy; until then the sax is a low-trust hypothesis source, the cymbal
  is the audio authority. Reproduce: `./screenaud /tmp/ag_tone-alarm.wav`.

## The cursor — unified active perception

The **cursor** is the agent-controlled attention pointer `(time-span, region, question-kind)` over the
recorded sequence. Five verbs answer at three rates; every answer carries an evidence pointer into the
Tier-A ring, so any neural claim is re-groundable and confab-scorable:

| verb | member | answers | kind |
|---|---|---|---|
| `show`     | arch_tool + vision-read | what does (t, region) look like, exactly | symbolic decode |
| `ocr`      | arch-ocr.sh (screenocr) | what text is at (t, region) | symbolic |
| `compare`  | arch_tool | did region R change between t1,t2 (count + bbox, exact) | symbolic |
| `track`    | tracker | what moved during [t0,t1] — count, direction, reversal, vanish, occlusion | symbolic |
| `describe` | screenvlm | what happens during [t0,t1] — semantics, causality, text/scene | **neural** |

Three-rate perception, one instrument: always-on symbolic stream for monitoring → exact tools for
text/change/motion verification → VLM for event semantics. The always-on channel stays symbolic;
`track` and `describe` are the boss's budgeted deep-attention verbs (the singer never calls them — see
watcher_protocol).

**Motion questions route to `track` first.** Any question about direction, (dis)appearance, reversal
location, motion continuity, or moving-object count is a symbolic measurement (I1/I8/I9): the boss
dispatches `track`, and a `describe` motion claim may at most *corroborate* it, never stand alone.
`describe` owns semantics/text; `track` owns motion; where they overlap, `track` is the authority.

**Evidence-family weighting.** Each witness carries a family tag (`symbolic-tracker`, `ocr`,
`qwen-visual`, `audio`). Agreement *within* a family already measured-untrusted for the claim type
adds ≈ 0 confidence (e.g. two Qwen-lineage VLMs agreeing on a motion predicate — Marlin-2B is a
Qwen fine-tune, so it and screenvlm are ONE witness, not two); within a partially-trusted family,
modest; *across* families (a tracker centroid + an OCR string + an audio transient), substantial. A
claim graduates to a `story.md` EVENT only with evidence appropriate to its type — for motion, that
means a `symbolic-tracker` (or `compare`) witness.

### describe trust policy (I8) — MEASURED (Phase-3 trap-test)

The `motion`/`motion-trap` trap-test (eval/scenarios.md "VLM trap-test") measured screenvlm's confab
profile: on abstract motion it reports the physically *expected* motion over the actual pixels — the
3B fails the honest scene (perception 50%, direction called backwards) and both the 3B and the 7B
fail the traps (25% / 75% confab; miss a 2s vanish, call a mid-field reversal an edge-bounce). Scale
and frame density do not fix it. On text/scene content the same model is strong (read title-card text
verbatim on a real capture). So `describe` is **Inferred-only and split by claim type**:

- **Text / scene / semantic claims** (what app, title, on-screen text, general content) — usable as
  Inferred hypotheses and to answer a boss query; still **never override** an `ocr`/`compare`
  measurement, and pin the arch seq span.
- **Spatial-motion event claims** (direction, appearance/disappearance, reversal location, motion
  continuity, moving-object count) — **untrusted**. They may only raise a `state.md` OPEN_QUESTION
  that a symbolic verb (`compare` / churn signal) must resolve; they may **never** become a
  `story.md` EVENT on the VLM's word alone.

In all cases a describe answer carries its exact seq span and is tagged `Inferred(vlm)`. The 7B is
offline-audition only (it did not clear the traps and is too heavy to run beside the recorder).

## Query protocol (active perception)

`queries/q_<id>.md` (boss writes):
```markdown
# Query <id>
question: <one specific question>
type: temporal | spatial | zoom | track | describe
span: <t0,t1 in ms>            # track/describe (the clip to analyse/interpret)
region: <x,y,w,h>             # optional, describe/zoom (source pixels)
evidence: [batch <b> f<i> rows <a>-<b>] | [arch seq <s0>..<s1> t=<t0>..<t1>]
budget: <max sub-watcher dispatches>   # for describe: max screenvlm invocations
deadline_batch: <give up after this batch number>
```

`queries/q_<id>.answer.md` (sub-watcher writes):
```markdown
# Answer <id>
status: answered | evidence-exhausted | pruned
answer: <the finding, OBSERVED/INFERRED separated; all describe content is INFERRED>
evidence: [batch <b> f<i> ...] | [arch seq <s0>..<s1> t=<t0>..<t1>]
```

Execution: temporal → read the pointed batch range closely; spatial → read only the pointed
rows of the keyframe grid; zoom → map rows to pixels (formula above), run
`screenocr batch_<b>.jpg --crop ...`, read the strings; **describe** → resolve `span` (+`region`)
and run `screenvlm <batch_dir> --span t0,t1 [--region ...] --q "<question>"`, copy its `ANSWER` as
INFERRED with its `EVIDENCE` line verbatim (never re-label VLM content as OBSERVED — I8).

**Evidence-pointer grammar.** Two forms, used interchangeably wherever evidence is cited:
`[batch <b> f<i> rows <a>-<b>]` (inside the retention window) and
`[arch seq <s0>..<s1> t=<t0>..<t1>]` (against the Tier-A ring, surviving batch pruning — the form
every `describe`/`show`/`compare` answer carries).

### Archive queries (`arch_tool`) — resolving evidence at exact-pixel fidelity

The batch keyframe JPEG covers only the *retention window*. Once a batch is pruned, a claim's exact
pixels survive only in the Tier-A ring, addressed by archive **seq** (not batch number). These verbs
resolve `story.md` EVIDENCE pins and zoom queries against the ring, and are the pixel-truth backing
for I2 (evidence stays randomly accessible backward):

```
arch_tool show    <dir> <seq> <out.ppm> [x y w h]   exact frame (optional full-res pixel crop)
arch_tool replay  <dir> <s0> <s1> <stride> <pfx>    lossless replay of a span → <pfx><s>.ppm
arch_tool compare <dir> <sA> <sB> [out.ppm]         exact pixel diff: prints changed count + bbox
```

- **OCR** over an archived frame = `arch_tool show … f.ppm` then `screenocr f.ppm --crop x,y,w,h`
  (`screenocr` reads PPM directly). `arch-ocr.sh <dir> <seq> x,y,w,h` wraps the pair.
- For a neural reader that needs to *see* a frame, convert the PPM once: `sips -s format png f.ppm
  --out f.png`. Coordinates are full-res pixels; use SPEC.md's grid↔pixel formula to turn a grid
  region into a crop.
- `compare` answers "did region R change between t1 and t2?" at the pixel — the boss uses it to
  confirm or refute a claimed change before it is consolidated. `changed=0` proves two instants are
  byte-identical; the bbox localises change without a neural read.

Stopping rules (hard): <= 3 queries per escalation; an `evidence-exhausted`/`pruned` question
is recorded under state.md's Unknown and never re-asked for the same event; introspective
"do I understand?" is never a loop condition.

## Attention pyramid (who wakes whom)

recorder (always) → triage (free, per batch) → OCR (scene-change batches only)
→ singer (event boundary or ~30s heartbeat; `still` batches cost ~zero tokens)
→ consolidator (slow heartbeat or log.md past its line cap; folds Tier 2 → Tier 3)
→ boss (escalation.md changes only) → sub-watchers (bounded by query budgets; a `describe`
sub-watcher spends the violin/`screenvlm` — deep attention is the boss's budget, never the singer's).
