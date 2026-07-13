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

## Members

| Role | Component | Kind |
|---|---|---|
| Drums | delta encoder (`frame_dump`, Elisa) | symbolic, always-on |
| Bass | ACTIVITY triage (inside `frame_dump`) | symbolic, per batch |
| Guitar | `screenocr` (Swift/Vision CLI) | symbolic, on-demand + scene-change |
| Violin | `screenvlm` (Qwen2.5-VL-3B, local) | neural, on-demand (boss-dispatched) |
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

## The cursor — unified active perception

The **cursor** is the agent-controlled attention pointer `(time-span, region, question-kind)` over the
recorded sequence. Four verbs answer at three rates; every answer carries an evidence pointer into the
Tier-A ring, so any neural claim is re-groundable and confab-scorable:

| verb | member | answers | kind |
|---|---|---|---|
| `show`     | arch_tool + vision-read | what does (t, region) look like, exactly | symbolic decode |
| `ocr`      | arch-ocr.sh (screenocr) | what text is at (t, region) | symbolic |
| `compare`  | arch_tool | did region R change between t1,t2 (count + bbox, exact) | symbolic |
| `describe` | screenvlm | what happens during [t0,t1] — motion, causality, events | **neural** |

Three-rate perception, one instrument: always-on symbolic stream for monitoring → exact tools for
text/change verification → VLM for event semantics. The always-on channel stays symbolic; `describe`
is the boss's budgeted deep-attention verb (the singer never calls it — see watcher_protocol).

### describe trust policy (I8) — PENDING the Phase-3 trap-test

Until the `motion`/`motion-trap` trap-test (cursor_vlm_plan.md §4) measures screenvlm's confab
profile, `describe` answers are **Inferred-only**: they may populate `state.md` HYPOTHESES /
OPEN_QUESTIONS and answer a boss query, but **may not create `story.md` EVENTS**, and a contradicting
symbolic result always wins. The measured trap numbers replace this paragraph with the graduated
policy (propose-events-if-corroborated / hypothesis-generator-only / benched).

## Query protocol (active perception)

`queries/q_<id>.md` (boss writes):
```markdown
# Query <id>
question: <one specific question>
type: temporal | spatial | zoom | describe
span: <t0,t1 in ms>            # describe only (the clip to interpret)
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
